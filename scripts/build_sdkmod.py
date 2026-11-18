#!/usr/bin/env python3
"""Deterministic TPS Modern_Movement.sdkmod builder (never overwrites supplied archives)."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Pre Sequel Port" / "Source" / "Modern_Movement"
ALLOWLIST = ROOT / "build" / "package-allowlist.json"
DIST = ROOT / "dist"
OUTPUT = DIST / "Modern_Movement.sdkmod"
SHA_PATH = DIST / "Modern_Movement.sdkmod.sha256"

PROTECTED_ARCHIVES = (
    ROOT / "Original" / "Modern Movement.sdkmod",
    ROOT / "Pre Sequel Port" / "Modern_Movement.sdkmod",
)

FIXED_TIMESTAMP = (2020, 1, 1, 0, 0, 0)
FIXED_PERMS = 0o644
EXTERNAL_FILE = (FIXED_PERMS << 16) | 0x20


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_allowlist() -> list[str]:
    payload = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    members = payload["members"]
    if not isinstance(members, list) or not members:
        raise SystemExit("package-allowlist.json has no members")
    members = sorted(set(members), key=lambda item: PurePosixPath(item).as_posix())
    for pattern in payload.get("exclude_patterns", []):
        for member in members:
            rel = member.removeprefix("Modern_Movement/")
            if rel == pattern or rel.endswith("/" + pattern):
                raise SystemExit(f"allowlist contradicts exclude_patterns: {member}")
    return members


def source_path(archive_member: str) -> Path:
    rel = archive_member.removeprefix("Modern_Movement/").rstrip("/")
    if not rel:
        raise SystemExit(f"directory member has no source mapping: {archive_member}")
    return SOURCE / PurePosixPath(rel)


def ensure_safe(member: str) -> None:
    path = PurePosixPath(member)
    if path.is_absolute() or ".." in path.parts or "\\" in member:
        raise SystemExit(f"unsafe archive member: {member}")


def build_archive(destination: Path) -> str:
    members = load_allowlist()
    if destination.resolve() in {item.resolve() for item in PROTECTED_ARCHIVES}:
        raise SystemExit(f"refusing to overwrite protected archive: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    casefold: set[str] = set()

    with zipfile.ZipFile(destination, "w") as bundle:
        for member in members:
            ensure_safe(member)
            folded = member.casefold()
            if folded in casefold:
                raise SystemExit(f"case collision in allowlist: {member}")
            casefold.add(folded)
            if member in seen:
                raise SystemExit(f"duplicate allowlist member: {member}")
            seen.add(member)

            if member.endswith("/"):
                info = zipfile.ZipInfo(member)
                info.date_time = FIXED_TIMESTAMP
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = (0o755 << 16) | 0x10
                bundle.writestr(info, b"")
                continue

            src = source_path(member)
            if not src.is_file():
                raise SystemExit(f"missing source file for {member}: {src}")
            data = src.read_bytes()
            info = zipfile.ZipInfo(member)
            info.date_time = FIXED_TIMESTAMP
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = EXTERNAL_FILE
            bundle.writestr(info, data, compress_type=zipfile.ZIP_STORED)

    return sha256_file(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Output sdkmod path (default: dist/Modern_Movement.sdkmod)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate sources and allowlist without writing an archive",
    )
    args = parser.parse_args()
    out = args.output.resolve()
    if out in {item.resolve() for item in PROTECTED_ARCHIVES}:
        raise SystemExit(f"refusing to write protected archive: {out}")

    members = load_allowlist()
    for member in members:
        ensure_safe(member)
        if not member.endswith("/"):
            src = source_path(member)
            if not src.is_file():
                raise SystemExit(f"missing source file for {member}: {src}")

    if args.dry_run:
        print(f"dry-run ok: {len(members)} members from {SOURCE}")
        return

    digest = build_archive(out)
    SHA_PATH.write_text(f"{digest}  {out.name}\n", encoding="utf-8", newline="\n")
    if out.is_relative_to(ROOT):
        archive_name = out.relative_to(ROOT).as_posix()
        manifest_path = DIST / "Modern_Movement.manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "archive": archive_name,
                    "sha256": digest,
                    "member_count": len(members),
                    "members": members,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    try:
        label = out.relative_to(ROOT)
    except ValueError:
        label = out
    print(f"built={label} sha256={digest}")


if __name__ == "__main__":
    main()