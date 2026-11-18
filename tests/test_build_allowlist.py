from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "build" / "package-allowlist.json"
SOURCE = ROOT / "Pre Sequel Port" / "Source" / "Modern_Movement"


def test_allowlist_excludes_slam_and_sources_exist():
    payload = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    members = payload["members"]
    joined = "\n".join(members)
    assert "slam" not in joined.lower()
    for member in members:
        if member.endswith("/"):
            continue
        rel = member.removeprefix("Modern_Movement/")
        assert (SOURCE / rel).is_file(), rel