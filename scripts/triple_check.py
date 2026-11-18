#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ARCHIVES = [
    (
        ROOT / "Original" / "Modern Movement.sdkmod",
        "d9431034750f6a8739841220a60a8da391f5a20772eb3affb3fedb4c8774278e",
    ),
    (
        ROOT / "Pre Sequel Port" / "Modern_Movement.sdkmod",
        "4f7c1fbeda6bc75e1d624123e323f109e716fc0d3b0ca2026939aee1919a2429",
    ),
]


def main() -> None:
    for path, expected in ARCHIVES:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        status = "OK" if digest == expected else f"BAD ({digest})"
        print(f"archive {path.name}: {status}")

    allowlist = set(json.loads((ROOT / "build" / "package-allowlist.json").read_text())["members"])
    with zipfile.ZipFile(ROOT / "dist" / "Modern_Movement.sdkmod") as bundle:
        names = set(bundle.namelist())
    print(f"zip_eq_allowlist: {allowlist == names}")
    slam_in_zip = any("features/slam.py" in name.lower() for name in names)
    print(f"slam_in_zip: {slam_in_zip}")
    if not slam_in_zip:
        raise SystemExit("BL2 slam.py missing from package")
    print(f"member_count: {len(names)}")
    dist_sha = (ROOT / "dist" / "Modern_Movement.sdkmod.sha256").read_text().split()[0]
    notes = (ROOT / "reports" / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    print(f"release_notes_has_sha: {dist_sha in notes}")


if __name__ == "__main__":
    main()
