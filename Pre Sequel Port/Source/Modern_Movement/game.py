"""Which Borderlands game is running.

Borderlands 2 and Borderlands: The Pre-Sequel are both supported. Detection fails closed:
anything else leaves features disabled. Custom Slam loads only on Borderlands 2, because
The Pre-Sequel already has Oz slam.
"""

from __future__ import annotations

import os
import sys

_cached: str | None = None
_UNSUPPORTED = "UNSUPPORTED"


def _detect() -> str:
    # 1) the mod manager's own game flag
    try:
        from mods_base import Game

        current = Game.get_current()
        label = (getattr(current, "name", None) or str(current)).upper()
        compact = label.replace("-", "").replace("_", "").replace(" ", "")
        if "TPS" in compact or "PRESEQUEL" in compact:
            return "TPS"
        if "BL2" in compact or "BORDERLANDS2" in compact:
            return "BL2"
        if "AODK" in compact:
            return "AODK"
    except Exception:  # noqa: BLE001
        pass

    # 2) the name of the running executable (BorderlandsPreSequel.exe / Borderlands2.exe)
    try:
        exe = os.path.basename(sys.executable or "").lower()
        if "presequel" in exe or "tps" in exe:
            return "TPS"
        if "borderlands2" in exe:
            return "BL2"
    except Exception:  # noqa: BLE001
        pass

    return _UNSUPPORTED


def current() -> str:
    """'BL2', 'TPS', or an unsupported label."""
    global _cached
    if _cached is None:
        _cached = _detect()
    return _cached


def is_bl2() -> bool:
    return current() == "BL2"


def is_tps() -> bool:
    return current() == "TPS"


def supported() -> bool:
    return is_bl2() or is_tps()
