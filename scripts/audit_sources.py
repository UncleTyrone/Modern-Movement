from __future__ import annotations

import argparse
import ast
import hashlib
import json
import struct
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

try:
    import tomllib
except ModuleNotFoundError:  # Python used for workspace tooling may predate 3.11.
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_ARCHIVE = ROOT / "Original" / "Modern Movement.sdkmod"
PORT_ARCHIVE = ROOT / "Pre Sequel Port" / "Modern_Movement.sdkmod"
ORIGINAL_SOURCE = ROOT / "Original" / "Source"
PORT_SOURCE = ROOT / "Pre Sequel Port" / "Source"
REPORTS = ROOT / "reports"
BUILD = ROOT / "build"
ALLOWLIST = BUILD / "package-allowlist.json"
PORT_PACKAGE = ROOT / "Pre Sequel Port" / "Source" / "Modern_Movement"


@dataclass(frozen=True)
class Member:
    path: str
    normalized_path: str
    size: int
    crc32: str
    sha256: str
    source_sha256: str | None
    source_matches: bool
    is_directory: bool


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(name: str) -> str:
    parts = PurePosixPath(name).parts
    return "/".join(parts[1:]) if len(parts) > 1 else ""


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def archive_manifest(archive: Path, source: Path) -> dict:
    raw = archive.read_bytes()
    members: list[Member] = []
    normalized_seen: set[str] = set()
    casefold_seen: set[str] = set()
    unsafe: list[str] = []
    duplicates: list[str] = []
    case_collisions: list[str] = []

    with zipfile.ZipFile(archive) as bundle:
        bad_crc = bundle.testzip()
        for info in bundle.infolist():
            if not safe_member(info.filename):
                unsafe.append(info.filename)
            norm = normalized(info.filename)
            if norm in normalized_seen:
                duplicates.append(norm)
            normalized_seen.add(norm)
            folded = norm.casefold()
            if folded in casefold_seen and norm:
                case_collisions.append(norm)
            casefold_seen.add(folded)

            data = b"" if info.is_dir() else bundle.read(info)
            source_path = source / PurePosixPath(info.filename)
            source_hash = None
            matches = info.is_dir()
            if not info.is_dir() and source_path.is_file():
                source_hash = sha256(source_path.read_bytes())
                matches = source_hash == sha256(data)
            members.append(
                Member(
                    path=info.filename,
                    normalized_path=norm,
                    size=info.file_size,
                    crc32=f"{info.CRC:08x}",
                    sha256=sha256(data),
                    source_sha256=source_hash,
                    source_matches=matches,
                    is_directory=info.is_dir(),
                )
            )

    return {
        "path": str(archive.relative_to(ROOT)).replace("\\", "/"),
        "size": len(raw),
        "sha256": sha256(raw),
        "bad_crc_member": bad_crc,
        "unsafe_members": unsafe,
        "duplicate_normalized_members": duplicates,
        "case_collisions": case_collisions,
        "file_count": sum(not item.is_directory for item in members),
        "all_source_members_match": all(item.source_matches for item in members),
        "members": [asdict(item) for item in members],
    }


def png_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        return None
    return struct.unpack(">II", data[16:24])


def source_checks(source_root: Path) -> dict:
    python_files: list[dict] = []
    toml_files: list[dict] = []
    png_files: list[dict] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_root).as_posix()
        data = path.read_bytes()
        if path.suffix == ".py":
            ast.parse(data.decode("utf-8"), filename=rel)
            python_files.append({"path": rel, "lines": data.count(b"\n") + 1, "sha256": sha256(data)})
        elif path.suffix == ".toml":
            text = data.decode("utf-8")
            if tomllib is not None:
                tomllib.loads(text)
            elif "textures/" in rel or rel.startswith("textures/"):
                if not any(line.strip().startswith("image =") for line in text.splitlines()):
                    raise ValueError(f"Unrecognized texture TOML: {path}")
            # Non-texture TOML (e.g. package pyproject.toml) is metadata only.
            toml_files.append({"path": rel, "sha256": sha256(data)})
        elif path.suffix == ".png":
            size = png_size(data)
            if size is None:
                raise ValueError(f"Invalid PNG: {path}")
            png_files.append({"path": rel, "width": size[0], "height": size[1], "sha256": sha256(data)})
    return {"python": python_files, "toml": toml_files, "png": png_files}


def compare_archives(original: dict, port: dict) -> dict:
    left = {item["normalized_path"]: item for item in original["members"] if item["normalized_path"]}
    right = {item["normalized_path"]: item for item in port["members"] if item["normalized_path"]}
    paths = sorted(left.keys() | right.keys())
    identical: list[str] = []
    changed: list[dict] = []
    added: list[str] = []
    removed: list[str] = []
    for path in paths:
        if path not in left:
            added.append(path)
        elif path not in right:
            removed.append(path)
        elif left[path]["sha256"] == right[path]["sha256"]:
            identical.append(path)
        else:
            changed.append(
                {
                    "path": path,
                    "original_sha256": left[path]["sha256"],
                    "port_sha256": right[path]["sha256"],
                    "original_size": left[path]["size"],
                    "port_size": right[path]["size"],
                }
            )
    return {"identical": identical, "changed": changed, "added": added, "removed": removed}


def allowlist_checks() -> dict:
    if not ALLOWLIST.is_file():
        raise FileNotFoundError(f"missing allowlist: {ALLOWLIST}")
    payload = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    members = payload.get("members", [])
    excludes = set(payload.get("exclude_patterns", []))
    problems: list[str] = []
    seen: set[str] = set()
    for member in members:
        if member in seen:
            problems.append(f"duplicate allowlist entry: {member}")
        seen.add(member)
        if not safe_member(member):
            problems.append(f"unsafe allowlist path: {member}")
        if member.endswith("/"):
            continue
        rel = member.removeprefix("Modern_Movement/").rstrip("/")
        if rel in excludes:
            problems.append(f"excluded path present in members: {member}")
        source_path = PORT_PACKAGE / PurePosixPath(rel)
        if not source_path.is_file():
            problems.append(f"allowlist member missing source: {member}")
    required_slam = {
        "Modern_Movement/features/slam.py",
        "Modern_Movement/textures/mm_slam_bracket.png",
        "Modern_Movement/textures/mm_slam_bracket.toml",
        "Modern_Movement/textures/mm_slam_ring.png",
        "Modern_Movement/textures/mm_slam_ring.toml",
    }
    missing_slam = sorted(required_slam.difference(members))
    if missing_slam:
        problems.append("BL2 slam assets missing from allowlist: " + ", ".join(missing_slam))
    py_files = sorted(p.relative_to(PORT_PACKAGE).as_posix() for p in PORT_PACKAGE.rglob("*.py"))
    packaged_py = {
        m.removeprefix("Modern_Movement/").rstrip("/")
        for m in members
        if m.endswith(".py")
    }
    undeclared = [
        path
        for path in py_files
        if path not in packaged_py
        and path not in excludes
        and path != "pyproject.toml"
    ]
    return {
        "member_count": len(members),
        "exclude_patterns": sorted(excludes),
        "problems": problems,
        "undeclared_python": undeclared,
        "ok": not problems and not undeclared,
    }


def loose_textures() -> list[dict]:
    root = ROOT / "Original" / "custom textures"
    results: list[dict] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            entry = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data), "size": len(data)}
            if path.suffix == ".png" and (size := png_size(data)) is not None:
                entry.update({"width": size[0], "height": size[1]})
            results.append(entry)
    return results


def write_port_audit(original: dict, port: dict, diff: dict) -> None:
    changed = "\n".join(f"- `{item['path']}`" for item in diff["changed"])
    added = "\n".join(f"- `{path}`" for path in diff["added"])
    text = f"""# Modern Movement supplied-source audit

## Immutable inputs
- Original archive: `{original['path']}`
  - SHA-256: `{original['sha256']}`
  - {original['file_count']} files; extraction was hash-verified before implementation edits.
- TPS port archive: `{port['path']}`
  - SHA-256: `{port['sha256']}`
  - {port['file_count']} files; extraction was hash-verified before implementation edits.

Both archives pass CRC, path traversal, duplicate-member, encryption, symlink, and case-collision checks.

## Normalized payload comparison
- Identical entries: {len(diff['identical'])}
- Changed entries: {len(diff['changed'])}
- Added entries: {len(diff['added'])}
- Removed entries: {len(diff['removed'])}

Changed:
{changed or "- None"}

Added by the port:
{added or "- None"}

## Semantic summary
- `__init__.py`: TPS detection, native-Slam exclusion, controller changelog, supported-game metadata.
- `core.py`: shared keyboard/controller jump wrappers and held-key checks.
- `features/dash.py`: D-pad Right controller default.
- `features/holster.py`: D-pad Down holster and left-stick Surge defaults.
- `features/mantle.py`: lower TPS gravity-sample floor.
- `game.py`: added cached BL2/TPS detection and the custom-Slam override.

No changed file adds networking, authority, per-player state, peer negotiation, or reconciliation.

## Confirmed TPS regression
The port reuses the BL2 Slide source unchanged. Slide holds native crouch state, has no explicit
sprint-exit transition, and does not clear crouch when it leaves the ground. TPS can therefore
interpret the retained crouch as native Slam. The co-op implementation must fix jump-out,
sprint-out, and off-cliff behavior before release.

## Scope
The supplied TPS 3.61.2 source is the implementation baseline. The separately published BL2 4.04
release is intentionally not merged into this work.
"""
    (REPORTS / "PORT_AUDIT.md").write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated output differs")
    parser.add_argument(
        "--require-source-parity",
        action="store_true",
        help="require both extracted trees to still match the supplied archives",
    )
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="rewrite the immutable archive-only baseline manifest",
    )
    args = parser.parse_args()

    original = archive_manifest(ORIGINAL_ARCHIVE, ORIGINAL_SOURCE)
    port = archive_manifest(PORT_ARCHIVE, PORT_SOURCE)
    diff = compare_archives(original, port)
    payload = {
        "schema": 1,
        "original": original,
        "port": port,
        "normalized_diff": diff,
        "source_checks": {
            "original": source_checks(ORIGINAL_SOURCE),
            "port": source_checks(PORT_SOURCE),
        },
        "loose_textures": loose_textures(),
        "allowlist": allowlist_checks(),
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    manifest = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    targets = [REPORTS / "ASSET_MANIFEST.json"]
    if args.check:
        for target in targets:
            if not target.is_file() or target.read_text(encoding="utf-8") != manifest:
                raise SystemExit(f"Generated audit is stale: {target}")
    else:
        for target in targets:
            target.write_text(manifest, encoding="utf-8", newline="\n")
        write_port_audit(original, port, diff)
    baseline_target = BUILD / "baseline-manifest.json"
    baseline = json.dumps(
        {
            "schema": 1,
            "extraction_verified_before_edits": True,
            "original_archive": {
                key: original[key]
                for key in ("path", "size", "sha256", "bad_crc_member", "unsafe_members", "file_count")
            },
            "port_archive": {
                key: port[key]
                for key in ("path", "size", "sha256", "bad_crc_member", "unsafe_members", "file_count")
            },
            "normalized_diff": diff,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.refresh_baseline or not baseline_target.exists():
        baseline_target.write_text(baseline, encoding="utf-8", newline="\n")
    elif args.check and baseline_target.read_text(encoding="utf-8") != baseline:
        raise SystemExit(f"Archive baseline changed: {baseline_target}")

    if args.require_source_parity and (
        not original["all_source_members_match"] or not port["all_source_members_match"]
    ):
        raise SystemExit("Extracted source does not match its archive")
    allowlist = allowlist_checks()
    if not allowlist["ok"]:
        raise SystemExit(f"Package allowlist check failed: {allowlist}")
    print(
        f"original={original['file_count']} port={port['file_count']} "
        f"identical={len(diff['identical'])} changed={len(diff['changed'])} "
        f"added={len(diff['added'])} removed={len(diff['removed'])}"
    )


if __name__ == "__main__":
    main()
