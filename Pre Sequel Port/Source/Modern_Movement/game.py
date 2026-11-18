"""Which Borderlands game is running.

This TPS co-op package is TPS-only. Detection fails closed: if the game cannot be identified
as The Pre-Sequel, features stay disabled rather than loading BL2-only behaviour such as custom
Slam.
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
        if "TPS" in label or "PRESEQUEL" in label or "PRE-SEQUEL" in label:
            return "TPS"
        if "BL2" in label:
            return "BL2"
        if "AODK" in label:
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
    """'TPS' when supported; otherwise an unsupported label (never silently BL2)."""
    global _cached
    if _cached is None:
        _cached = _detect()
    return _cached


def is_tps() -> bool:
    return current() == "TPS"


def supported() -> bool:
    return is_tps()
