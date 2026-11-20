from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "build" / "package-allowlist.json"
SOURCE = ROOT / "src" / "Modern_Movement"


def test_allowlist_includes_bl2_slam_and_sources_exist():
    payload = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    members = payload["members"]
    joined = "\n".join(members)
    assert "Modern_Movement/features/slam.py" in members
    assert "Modern_Movement/textures/mm_slam_bracket.png" in members
    assert "Modern_Movement/textures/mm_slam_ring.png" in members
    assert "features/slam.py" not in payload.get("exclude_patterns", [])
    assert "slam" in joined.lower()
    for member in members:
        if member.endswith("/"):
            continue
        rel = member.removeprefix("Modern_Movement/")
        assert (SOURCE / rel).is_file(), rel