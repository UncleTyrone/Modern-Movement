"""Rate-limited structured diagnostics used by capability and authority tests."""

from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, Callable


_counters: Counter[str] = Counter()
_last_log: dict[str, float] = {}
_sink: Callable[[str], None] = print
enabled = False


def set_sink(sink: Callable[[str], None]) -> None:
    global _sink
    _sink = sink


def event(name: str, *, interval: float = 0.0, **fields: Any) -> None:
    _counters[name] += 1
    if not enabled:
        return
    now = time.monotonic()
    if interval > 0.0 and now - _last_log.get(name, -1e9) < interval:
        return
    _last_log[name] = now
    payload = {"event": name, **fields}
    try:
        _sink("[Modern Movement] " + json.dumps(payload, sort_keys=True, default=str))
    except Exception:
        pass


def count(name: str, amount: int = 1) -> None:
    _counters[name] += amount


def counters() -> dict[str, int]:
    return dict(_counters)


def reset() -> None:
    _counters.clear()
    _last_log.clear()


def controller_snapshot(pc: Any) -> dict[str, Any]:
    pawn = getattr(pc, "Pawn", None)
    pri = getattr(pc, "PlayerReplicationInfo", None)
    world = getattr(pc, "WorldInfo", None)
    data: dict[str, Any] = {
        "player_id": getattr(pri, "PlayerID", None),
        "party_leader": bool(getattr(pri, "bIsPartyLeader", False)) if pri is not None else False,
        "role": _safe_value(pc, "Role"),
        "local": _safe_call(pc, "IsLocalPlayerController"),
        "net_mode": _safe_value(world, "NetMode"),
        "has_pawn": pawn is not None,
    }
    if pawn is not None:
        data.update(
            {
                "physics": _safe_value(pawn, "Physics"),
                "health": _safe_value(pawn, "Health"),
                "bDuck": _safe_value(pc, "bDuck"),
                "bWantsToCrouch": _safe_value(pawn, "bWantsToCrouch"),
                "bIsCrouched": _safe_value(pawn, "bIsCrouched"),
                "bIsSprinting": _safe_value(pawn, "bIsSprinting"),
                "velocity": _vector(getattr(pawn, "Velocity", None)),
                "acceleration": _vector(getattr(pawn, "Acceleration", None)),
            }
        )
    return data


def _safe_value(obj: Any, name: str) -> Any:
    try:
        value = getattr(obj, name)
        return int(value) if not isinstance(value, (str, bool, int, float, type(None))) else value
    except Exception:
        return None


def _safe_call(obj: Any, name: str) -> Any:
    try:
        return bool(getattr(obj, name)())
    except Exception:
        return None


def _vector(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(value.X), float(value.Y), float(value.Z)]
    except Exception:
        return None
