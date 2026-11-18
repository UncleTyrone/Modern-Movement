#!/usr/bin/env python3
"""Verify a Modern_Movement.sdkmod against the allowlist and build determinism."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "build" / "package-allowlist.json"
BUILD_SCRIPT = ROOT / "scripts" / "build_sdkmod.py"

PROTECTED_ARCHIVES = (
    ROOT / "Original" / "Modern Movement.sdkmod",
    ROOT / "Pre Sequel Port" / "Modern_Movement.sdkmod",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_allowlist() -> set[str]:
    payload = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    return set(payload["members"])


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def verify_archive(archive: Path, allowed: set[str]) -> dict:
    if archive.resolve() in {item.resolve() for item in PROTECTED_ARCHIVES}:
        raise SystemExit(
            f"refusing to verify protected supplied archive in place: {archive}. "
            "Copy it elsewhere or use dist/Modern_Movement.sdkmod."
        )
    if not archive.is_file():
        raise SystemExit(f"archive not found: {archive}")

    with zipfile.ZipFile(archive) as bundle:
        bad_crc = bundle.testzip()
        names = sorted(bundle.namelist())
        extra = sorted(set(names) - allowed)
        missing = sorted(allowed - set(names))
        unsafe = [name for name in names if not safe_member(name)]
        stored_ok = all(
            info.compress_type == zipfile.ZIP_STORED for info in bundle.infolist() if not info.is_dir()
        )

    return {
        "archive": str(archive.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256_file(archive),
        "member_count": len(names),
        "bad_crc_member": bad_crc,
        "unsafe_members": unsafe,
        "missing_members": missing,
        "extra_members": extra,
        "all_zip_stored": stored_ok,
        "members": names,
    }


def run_build(destination: Path) -> None:
    cmd = [sys.executable, str(BUILD_SCRIPT), "--output", str(destination)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout or "build failed")


def verify_deterministic_build() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = root / "first.sdkmod"
        second = root / "second.sdkmod"
        run_build(first)
        run_build(second)
        hash_first = sha256_file(first)
        hash_second = sha256_file(second)
        return {
            "first_sha256": hash_first,
            "second_sha256": hash_second,
            "identical": hash_first == hash_second,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        type=Path,
        default=ROOT / "dist" / "Modern_Movement.sdkmod",
        help="Archive to verify (default: dist/Modern_Movement.sdkmod)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Build twice in temp dirs and require identical SHA-256",
    )
    parser.add_argument(
        "--build-first",
        action="store_true",
        help="Build dist/Modern_Movement.sdkmod before verification",
    )
    args = parser.parse_args()
    allowed = load_allowlist()

    rebuild = None
    if args.rebuild:
        rebuild = verify_deterministic_build()
        if not rebuild["identical"]:
            raise SystemExit("deterministic build mismatch")

    archive = args.archive
    if args.build_first:
        run_build(archive)

    report = verify_archive(archive, allowed)
    report["deterministic_rebuild"] = rebuild
    report["allowlist_count"] = len(allowed)

    problems: list[str] = []
    if report["missing_members"]:
        problems.append(f"missing: {report['missing_members']}")
    if report["extra_members"]:
        problems.append(f"extra: {report['extra_members']}")
    if report["unsafe_members"]:
        problems.append(f"unsafe: {report['unsafe_members']}")
    if report["bad_crc_member"]:
        problems.append(f"bad_crc: {report['bad_crc_member']}")
    if not report["all_zip_stored"]:
        problems.append("not all members use ZIP_STORED")

    out = ROOT / "reports" / "SDKMOD_VERIFY.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    if problems:
        raise SystemExit("; ".join(problems))

    print(
        f"verified={report['archive']} sha256={report['sha256']} "
        f"members={report['member_count']} allowlist={report['allowlist_count']}"
    )
    if rebuild:
        print(f"deterministic={rebuild['first_sha256']}")


if __name__ == "__main__":
    main()