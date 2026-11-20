"""Level tracing for features that need to "see" walls and ledges (currently Mantle).

Actor.Trace never returned hits in this game/SDK combination, so a hidden WillowWeapon's
CalcWeaponFire is used instead. That weapon is created for ONE ledge search (`with session():`) and
destroyed straight afterwards. It is never kept between searches: an unowned weapon can be deleted by
the game at any moment, and calling CalcWeaponFire on a deleted object crashes the whole game.
A trace that hits a living actor carries on past it instead of reporting "no wall".

This module must not import core (core imports it).
"""

import math

import unrealsdk
from mods_base import get_pc
from unrealsdk import logging

_DEBUG = False  # set to True to print diagnostic messages to the console

# Used only if the pawn's collision cylinder can't be read.
_DEFAULT_RADIUS = 34.0
_DEFAULT_HALF_HEIGHT = 90.0
_MAX_RETRACE = 3  # how many living actors a single trace may look through

_weapon = None  # only set while a session() is open
saw_self = False  # a trace in this session hit the player's own body (traces don't ignore it)
recorder = None   # a list while a debug recording is on: every trace() appends one entry to it


def _r(v):
    return [round(float(c), 1) for c in v]


def _record(start, end, extent, result) -> None:
    if recorder is None or len(recorder) >= 4000:
        return
    entry = {"s": _r(start), "e": _r(end)}
    if extent is not None:
        entry["x"] = _r(extent)
    if result is not None:
        entry["h"] = _r(result[0])
        entry["n"] = [round(float(c), 3) for c in result[1]]
    recorder.append(entry)


class TraceUnavailable(Exception):
    """CalcWeaponFire could not be called."""


class BudgetSpent(Exception):
    """This search has used up its trace budget (it gives up instead of hitching the frame)."""


_depth = 0      # open sessions: an inner session reuses the outer one's weapon and memo
_pending_pawn = None  # the open session's pawn, for the weapon made on its first trace
budget = None   # traces still allowed in the open session (None = no limit)
used = 0        # traces used in the open session
cache: dict = {}  # per-session memo for callers (cleared when a session opens)


def _log(msg: str) -> None:
    if _DEBUG:
        logging.info(f"[Trace] {msg}")


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


def destroy() -> None:
    global _weapon
    weap, _weapon = _weapon, None
    try:
        if weap is not None:
            weap.Destroy()
    except Exception:  # noqa: BLE001
        pass


def _spawn_weapon():
    """A hidden WillowWeapon for CalcWeaponFire, or None if it can't be made."""
    try:
        pc = get_pc()
        cls = unrealsdk.find_class("WillowWeapon")
        if pc is None or cls is None:
            return None
        weap = pc.Spawn(cls)
        try:
            weap.SetHidden(True)
            weap.SetCollision(False, False, False)
        except Exception:  # noqa: BLE001
            pass
        return weap
    except Exception as e:  # noqa: BLE001
        _log(f"could not spawn trace weapon: {e!r}")
        return None


class session:
    """Use as `with tracing.session(pawn):` around one ledge search; trace() only works inside it.
    With a pawn, the trace weapon is given that pawn as its Instigator: a weapon's traces normally
    ignore their instigator, so traces can start inside the player's own body. Whether they really
    do is reported through `saw_self`."""

    def __init__(self, pawn=None, limit=None):
        self._pawn = pawn
        self._limit = limit

    def __enter__(self):
        global _weapon, saw_self, budget, used, _depth
        if _depth > 0:
            # Inside another search's session: share its weapon and memo, with its own budget.
            _depth += 1
            self._saved = (budget, used)
            budget = None if self._limit is None else used + self._limit
            return self
        destroy()  # (nothing should be left over, but never keep an old one)
        saw_self = False
        budget = self._limit
        used = 0
        cache.clear()
        _depth = 1
        # The weapon is only created on the first trace (a check that ends early never makes one).
        global _pending_pawn
        _pending_pawn = self._pawn
        return self

    def __exit__(self, *exc):
        global budget, _depth
        if _depth > 1:
            _depth -= 1
            budget = self._saved[0]
            return False
        _depth = 0
        destroy()
        budget = None
        cache.clear()
        return False


def _is_living(impact) -> bool:
    try:
        actor = getattr(impact, "HitActor", None)
        if actor is None:
            return False
        name = str(actor.Class.Name)
        return any(bad in name for bad in ("Pawn", "Projectile", "WillowAI", "PlayerController"))
    except Exception:  # noqa: BLE001
        return False


def trace(pawn, start, end, extent=None):
    global used
    used += 1
    if budget is not None and used > budget:
        raise BudgetSpent
    result = _trace(pawn, start, end, extent)
    if recorder is not None:
        _record(start, end, extent, result)
    return result


def _ensure_weapon():
    """The open session's trace weapon, created now if this is its first trace."""
    global _weapon
    if _weapon is None and _depth > 0:
        _weapon = _spawn_weapon()
        if _weapon is None:
            raise TraceUnavailable
        if _pending_pawn is not None:
            try:
                _weapon.Instigator = _pending_pawn
            except Exception as e:  # noqa: BLE001
                _log(f"could not set Instigator: {e!r}")
    return _weapon


def _trace(pawn, start, end, extent=None):
    """Trace a line through the level. Returns (hit_location, hit_normal) or None for no hit.

    extent: (x, y, z) half size of a box to sweep instead of a line (None = a line).
    Raises TraceUnavailable if the trace machinery can't be used at all.
    """
    weap = _ensure_weapon()
    if weap is None:
        raise TraceUnavailable  # not inside a session()

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
                # A box sweep: Extent is the box's half size (tested in game: a 60 box stops 60 short).
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

        # No hit: HitLocation equals (or is extremely close to) the end point.
        if math.dist(hit_loc, (ex, ey, ez)) < 4.0:
            return None

        try:
            if pawn is not None and impact.HitActor == pawn:
                global saw_self
                saw_self = True
        except Exception:  # noqa: BLE001
            pass
        if _is_living(impact):
            # An enemy / ally / projectile is in the way: look past it for the level behind.
            cx, cy, cz = hit_loc[0] + ux * 2.0, hit_loc[1] + uy * 2.0, hit_loc[2] + uz * 2.0
            if math.dist((cx, cy, cz), (ex, ey, ez)) < 4.0:
                return None
            _log("looked past a living actor")
            continue
        _log(f"hit {hit_loc} normal {hit_norm}")
        return hit_loc, hit_norm
    return None


