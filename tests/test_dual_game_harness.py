from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dual_game_harness_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dual_game_harness.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "HARNESS_OK" in result.stdout
    assert "HARNESS_GAME_OK BL2" in result.stdout or "games=BL2,TPS" in result.stdout
