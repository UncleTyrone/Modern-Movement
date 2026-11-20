from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_static_policy_script():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "static_policy.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_allowlist_ships_bl2_slam():
    import json

    payload = json.loads((ROOT / "build" / "package-allowlist.json").read_text(encoding="utf-8"))
    members = payload["members"]
    assert "Modern_Movement/features/slam.py" in members
    assert "features/slam.py" not in payload.get("exclude_patterns", [])
