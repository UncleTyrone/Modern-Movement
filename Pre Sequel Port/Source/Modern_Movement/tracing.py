"""Level tracing for features that need to "see" walls and ledges (currently Mantle).

Actor.Trace never returned hits in this game/SDK combination, so a hidden WillowWeapon's
CalcWeaponFire is used instead. That weapon is created for ONE ledge search (`with session():`) and
destroyed straight afterwards. It is never kept between searches: an unowned weapon can be deleted by
the game at any moment, and calling CalcWeaponFire on a deleted object crashes the whole game.
A trace that hits a living actor carries on past it instead of reporting "no wall".

Weapons and trace memo are scoped per player (controller + pawn generation) and never shared.
This module must not import core (core imports it).
"""

from __future__ import annotations

import math
from typing import Any

import unrealsdk
from mods_base import ENGINE, get_pc
from unrealsdk import logging

_DEBUG = False  # set to True to print diagnostic messages to the console

_DEFAULT_RADIUS = 34.0
_DEFAULT_HALF_HEIGHT = 90.0
_MAX_RETRACE = 3  # how many living actors a single trace may look through
_MAX_ENGINE_CALLS_PER_FRAME = 48  # host-wide: simultaneous ledge searches share this cap

_frame_time: float | None = None
_frame_calls = 0


def _r(v):
    return [round(float(c), 1) for c in v]


def _record(session: "TraceSession", start, end, extent, result) -> None:
    if session.recorder is None or len(session.recorder) >= 4000:
        return
    entry = {"s": _r(start), "e": _r(end)}
    if extent is not None:
        entry["x"] = _r(extent)
    if result is not None:
        entry["h"] = _r(result[0])
        entry["n"] = [round(float(c), 3) for c in result[1]]
    session.recorder.append(entry)


class TraceUnavailable(Exception):
    """CalcWeaponFire could not be called."""


class BudgetSpent(Exception):
    """This search has used up its trace budget (it gives up instead of hitching the frame)."""


def _log(msg: str) -> None:
    if _DEBUG:
        logging.info(f"[Trace] {msg}")


def _world_time() -> float | None:
    try:
        return float(ENGINE.GetCurrentWorldInfo().TimeSeconds)
    except Exception:  # noqa: BLE001
        return None


def _consume_frame_budget() -> None:
    """Raise BudgetSpent when too many CalcWeaponFire calls happen in one world tick."""
    global _frame_time, _frame_calls
    now = _world_time()
    if now is None:
        return
    if _frame_time != now:
        _frame_time = now
        _frame_calls = 0
    _frame_calls += 1
    if _frame_calls > _MAX_ENGINE_CALLS_PER_FRAME:
        raise BudgetSpent


def _player_id(pc) -> int:
    try:
        pri = pc.PlayerReplicationInfo
        if pri is not None:
            return int(pri.PlayerID)
    except Exception:  # noqa: BLE001
        pass
    try:
        return id(pc)
    except Exception:  # noqa: BLE001
        return 0


def _session_key(pc, pawn, ctx: Any = None) -> tuple[int, int]:
    if ctx is not None and hasattr(ctx, "key"):
        return int(ctx.key.player_id), int(ctx.pawn_generation)
    return _player_id(pc), 0


class TraceSession:
    """One player's trace weapon, budget, and memo for the current open search."""

    def __init__(self, key: tuple[int, int], pawn, controller=None) -> None:
        self.key = key
        self.pawn = pawn
        self.controller = controller
        self.weapon = None
        self.saw_self = False
        self.recorder: list | None = None
        self.budget: int | None = None
        self.used = 0
        self.cache: dict = {}
        self.depth = 0
        self._saved: tuple[int | None, int] | None = None

    def _spawn_weapon(self):
        if self.weapon is not None:
            return self.weapon
        try:
            # Prefer the session's own controller so remote-host searches do not depend on get_pc().
            pc = self.controller if self.controller is not None else get_pc()
            cls = unrealsdk.find_class("WillowWeapon")
            if pc is None or cls is None:
                return None
            weap = pc.Spawn(cls)
            try:
                weap.SetHidden(True)
                weap.SetCollision(False, False, False)
            except Exception:  # noqa: BLE001
                pass
            self.weapon = weap
            if self.pawn is not None:
                try:
                    weap.Instigator = self.pawn
                except Exception as e:  # noqa: BLE001
                    _log(f"could not set Instigator: {e!r}")
            return weap
        except Exception as e:  # noqa: BLE001
            _log(f"could not spawn trace weapon: {e!r}")
            return None

    def destroy_weapon(self) -> None:
        weap, self.weapon = self.weapon, None
        try:
            if weap is not None:
                weap.Destroy()
        except Exception:  # noqa: BLE001
            pass

    def push(self, limit: int | None) -> None:
        if self.depth > 0:
            self.depth += 1
            self._saved = (self.budget, self.used)
            self.budget = None if limit is None else self.used + int(limit)
            return
        self.saw_self = False
        self.budget = limit
        self.used = 0
        self.cache.clear()
        self.depth = 1

    def pop(self) -> None:
        if self.depth > 1:
            self.depth -= 1
            if self._saved is not None:
                self.budget = self._saved[0]
            return
        self.depth = 0
        self.destroy_weapon()
        self.budget = None
        self.cache.clear()


_sessions: dict[tuple[int, int], TraceSession] = {}
_stack: list[TraceSession] = []


def _active() -> TraceSession | None:
    return _stack[-1] if _stack else None


class session:
    """Use as `with tracing.session(pc, pawn):` or `with tracing.session(ctx):` around one search."""

    def __init__(self, pc_or_ctx, pawn=None, limit=None):
        if hasattr(pc_or_ctx, "controller"):
            self._ctx = pc_or_ctx
            self._pc = pc_or_ctx.controller
            self._pawn = pawn if pawn is not None else pc_or_ctx.pawn
        else:
            self._ctx = None
            self._pc = pc_or_ctx
            self._pawn = pawn
        self._limit = limit
        self._session: TraceSession | None = None

    def __enter__(self):
        key = _session_key(self._pc, self._pawn, self._ctx)
        sess = _sessions.get(key)
        if sess is None or sess.depth == 0:
            sess = TraceSession(key, self._pawn, controller=self._pc)
            _sessions[key] = sess
        else:
            if self._pawn is not None:
                sess.pawn = self._pawn
            if self._pc is not None:
                sess.controller = self._pc
        sess.push(self._limit)
        _stack.append(sess)
        self._session = sess
        return self

    def __exit__(self, *exc):
        sess = self._session
        if sess is not None and _stack and _stack[-1] is sess:
            _stack.pop()
            sess.pop()
            if sess.depth == 0:
                _sessions.pop(sess.key, None)
        return False


def destroy() -> None:
    """Tear down every open trace session (mod disable / world reset)."""
    global _frame_time, _frame_calls
    while _stack:
        sess = _stack.pop()
        sess.depth = 1
        sess.pop()
    for sess in list(_sessions.values()):
        sess.destroy_weapon()
    _sessions.clear()
    _frame_time = None
    _frame_calls = 0


def body(pawn) -> tuple[float, float]:
    """(radius, half height) of the pawn's collision cylinder."""
    try:
        cyl = pawn.CylinderComponent
        return float(cyl.CollisionRadius), float(cyl.CollisionHeight)
    except Exception:  # noqa: BLE001
        return _DEFAULT_RADIUS, _DEFAULT_HALF_HEIGHT


def vec(v) -> tuple[float, float, float]:
    try:
        return float(v.X), float(v.Y), float(v.Z)
    except AttributeError:
        return float(v[0]), float(v[1]), float(v[2])


def make_vec(x: float, y: float, z: float):
    """Create a real Vector WrappedStruct. CalcWeaponFire rejects plain tuples."""
    try:
        return unrealsdk.make_struct("Vector", X=float(x), Y=float(y), Z=float(z))
    except Exception:  # noqa: BLE001
        return unrealsdk.make_struct("Core.Object.Vector", True, X=float(x), Y=float(y), Z=float(z))


def _is_living(impact) -> bool:
    try:
        actor = getattr(impact, "HitActor", None)
        if actor is None:
            return False
        name = str(actor.Class.Name)
        return any(bad in name for bad in ("Pawn", "Projectile", "WillowAI", "PlayerController"))
    except Exception:  # noqa: BLE001
        return False


class _SawSelf:
    def __get__(self, _obj, _typ=None) -> bool:
        sess = _active()
        return False if sess is None else sess.saw_self

    def __set__(self, _obj, value: bool) -> None:
        sess = _active()
        if sess is not None:
            sess.saw_self = bool(value)


class _CacheView:
    def __getitem__(self, key):
        sess = _active()
        if sess is None:
            raise KeyError(key)
        return sess.cache[key]

    def __setitem__(self, key, value):
        sess = _active()
        if sess is None:
            raise RuntimeError("trace cache used outside a session()")
        sess.cache[key] = value

    def __contains__(self, key):
        sess = _active()
        return sess is not None and key in sess.cache

    def get(self, key, default=None):
        sess = _active()
        if sess is None:
            return default
        return sess.cache.get(key, default)

    def clear(self) -> None:
        sess = _active()
        if sess is not None:
            sess.cache.clear()


class _RecorderView:
    def __get__(self, _obj, _typ=None):
        sess = _active()
        return None if sess is None else sess.recorder

    def __set__(self, _obj, value) -> None:
        sess = _active()
        if sess is not None:
            sess.recorder = value


saw_self = _SawSelf()
cache = _CacheView()
recorder = _RecorderView()


def trace(pawn, start, end, extent=None):
    sess = _active()
    if sess is None:
        raise TraceUnavailable  # not inside a session()
    sess.used += 1
    if sess.budget is not None and sess.used > sess.budget:
        raise BudgetSpent
    _consume_frame_budget()
    result = _trace(sess, pawn, start, end, extent)
    if sess.recorder is not None:
        _record(sess, start, end, extent, result)
    return result


def _trace(sess: TraceSession, pawn, start, end, extent=None):
    """Trace a line through the level. Returns (hit_location, hit_normal) or None for no hit."""
    weap = sess._spawn_weapon()
    if weap is None:
        raise TraceUnavailable

    cx, cy, cz = start
    ex, ey, ez = end
    total = math.dist(start, end)
    if total < 1e-3:
        return None
    ux, uy, uz = (ex - cx) / total, (ey - cy) / total, (ez - cz) / total

    for _ in range(_MAX_RETRACE):
        try:
            if extent is None:
                result = weap.CalcWeaponFire(
                    StartTrace=make_vec(cx, cy, cz),
                    EndTrace=make_vec(ex, ey, ez),
                    bTestTrace=True,
                )
            else:
                result = weap.CalcWeaponFire(
                    StartTrace=make_vec(cx, cy, cz),
                    EndTrace=make_vec(ex, ey, ez),
                    bTestTrace=True,
                    Extent=make_vec(*extent),
                )
        except Exception as e:  # noqa: BLE001
            _log(f"CalcWeaponFire failed: {e!r}")
            raise TraceUnavailable from e

        impact = result[0] if isinstance(result, (tuple, list)) else result
        if impact is None:
            return None
        try:
            hit_loc = vec(impact.HitLocation)
            hit_norm = vec(impact.HitNormal)
        except Exception as e:  # noqa: BLE001
            _log(f"could not read ImpactInfo: {e!r}")
            return None

        if math.dist(hit_loc, (ex, ey, ez)) < 4.0:
            return None

        try:
            if pawn is not None and impact.HitActor == pawn:
                sess.saw_self = True
        except Exception:  # noqa: BLE001
            pass
        if _is_living(impact):
            cx, cy, cz = hit_loc[0] + ux * 2.0, hit_loc[1] + uy * 2.0, hit_loc[2] + uz * 2.0
            if math.dist((cx, cy, cz), (ex, ey, ez)) < 4.0:
                return None
            _log("looked past a living actor")
            continue
        _log(f"hit {hit_loc} normal {hit_norm}")
        return hit_loc, hit_norm
    return None