"""Rate-limited structured diagnostics used by capability and authority tests.

While the mod is enabled, the same lines are appended to Modern_Movement.log.txt
in the folder that holds the installed sdkmod, so two players can compare sessions.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from typing import Any, Callable


_counters: Counter[str] = Counter()
_last_log: dict[str, float] = {}
_sink: Callable[[str], None] = print
enabled = False
file_log = False
_LOG_NAME = "Modern_Movement.log.txt"
_LOG_MAX_BYTES = 2_000_000
_log_path_cached: str | None = None
_log_failed = False


def set_sink(sink: Callable[[str], None]) -> None:
    global _sink
    _sink = sink


def log_path() -> str:
    """Folder that contains the installed mod, plus Modern_Movement.log.txt."""
    global _log_path_cached
    if _log_path_cached is not None:
        return _log_path_cached
    folder = None
    try:
        from .hudfx import _sdk_mods_dir

        folder, _zip, _inner = _sdk_mods_dir()
    except Exception:
        folder = None
    if not folder:
        folder = os.getcwd()
    _log_path_cached = os.path.join(str(folder), _LOG_NAME)
    return _log_path_cached


def _append(line: str) -> None:
    global _log_failed
    if not file_log or _log_failed:
        return
    try:
        path = log_path()
        if os.path.exists(path) and os.path.getsize(path) > _LOG_MAX_BYTES:
            os.replace(path, path + ".old")
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {line}\n")
    except Exception as exc:
        _log_failed = True
        try:
            import unrealsdk

            unrealsdk.logging.warning(
                f"[Modern Movement] session log could not be written ({exc!r})"
            )
        except Exception:
            pass


def _context_fields() -> dict[str, Any]:
    """Who this line is about, so a refusal explains the pawn it happened on."""
    try:
        from . import core

        ctx = core.current_context() or core.local_context()
    except Exception:
        return {}
    if ctx is None:
        return {}
    phys = None
    speed = None
    try:
        if ctx.pawn is not None:
            phys = int(ctx.pawn.Physics)
            speed = round((float(ctx.pawn.Velocity.X) ** 2 + float(ctx.pawn.Velocity.Y) ** 2) ** 0.5, 1)
    except Exception:
        pass
    return {
        "player": getattr(getattr(ctx, "key", None), "player_id", None),
        "role": getattr(getattr(ctx, "role", None), "value", ""),
        "busy": ctx.busy or "",
        "phys": phys,
        "speed": speed,
        "pawn": ctx.pawn_generation,
    }


def _interval_key(name: str, fields: dict[str, Any]) -> str:
    parts = [name]
    for part in ("reason", "result", "feature", "operation", "fn"):
        if part in fields:
            parts.append(str(fields[part]))
    return "|".join(parts)


def note(message: str) -> None:
    """One plain line in the session log and, when console diagnostics are on, the console."""
    _append(message)
    if not enabled:
        return
    try:
        _sink("[Modern Movement] " + message)
    except Exception:
        pass


def event(name: str, *, interval: float = 0.0, **fields: Any) -> None:
    _counters[name] += 1
    for key, value in _context_fields().items():
        fields.setdefault(key, value)
    now = time.monotonic()
    key = _interval_key(name, fields)
    if interval > 0.0 and now - _last_log.get(key, -1e9) < interval:
        return
    _last_log[key] = now
    payload = {"event": name, **fields}
    try:
        line = json.dumps(payload, sort_keys=True, default=str)
    except Exception:
        line = json.dumps({"event": name, "error": "unserializable"})
    _append(line)
    if not enabled:
        return
    try:
        _sink("[Modern Movement] " + line)
    except Exception:
        pass


def count(name: str, amount: int = 1) -> None:
    _counters[name] += amount


def counters() -> dict[str, int]:
    return dict(_counters)


def reset() -> None:
    global _log_failed, _log_path_cached
    _counters.clear()
    _last_log.clear()
    _log_failed = False
    _log_path_cached = None


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
