"""Shared plumbing for Modern Movement.

Why this exists
  * ONE PlayerTick hook for every feature (instead of one each). It finds the local
    player once per frame, parses DeltaTime once, advances a game-time clock, and then
    calls each feature's tick function in a fixed order.
  * ONE jump key. Double Jump and Mantle used to each bind SpaceBar and ask each other
    questions. Now a single handler decides what a jump press does, so a ledge is only
    searched for once per press and rebinding the key can never leave a dead press.
  * A "busy" flag so only one movement action (air dash / mantle) is in charge at a time.
  * A tiny event bus (emit / events=...) so features can react to each other
    ("dash_end") without importing each other.
  * Shared helpers (vehicle / dead check, facing vector, jump strength, physics constants).
  * One owner of the pawn's GroundSpeed: features ask for speed multipliers (set_speed_mult)
    and core applies them together, so Sprint Surge and the slide never fight over it.

Features register with core from their on_enable() and unregister in on_disable().
"""

from __future__ import annotations

import math

from mods_base import get_pc, hook, keybind
from unrealsdk import logging
from unrealsdk.hooks import Type

from . import camera, tracing

PHYS_WALKING = 1
PHYS_FALLING = 2
PHYS_FLYING = 4

# Game-time seconds, advanced by DeltaTime every tick (so pausing / slow-mo are respected).
clock = 0.0
# The pawn's Physics value as of this tick (-1 = no pawn). Read by features instead of re-querying.
phys = -1
# Name of the movement action currently in charge ("dash", "mantle", or None).
busy: str | None = None

# A jump press this soon after a ground press is the same jump, not a mid-air press.
_GROUND_GUARD = 0.15
_last_ground_press = -100.0

_entries: dict[str, dict] = {}
_tickers: list = []
_ground_handlers: list = []
_air_handlers: list = []
_cancellers: dict = {}
_warned: set = set()


def settings(children: list, description: str = "") -> list:
    """A "Settings" submenu inside a section (or the options shown directly if submenus aren't available)."""
    try:
        from mods_base import NestedOption
    except ImportError:
        return list(children)
    for build in (
        lambda: NestedOption("Settings", list(children), description=description),
        lambda: NestedOption("Settings", list(children)),
    ):
        try:
            return [build()]
        except Exception:  # noqa: BLE001
            pass
    return list(children)


def log(tag: str, msg: str) -> None:
    logging.info(f"[{tag}] {msg}")


# ---------------------------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------------------------


def _rebuild() -> None:
    global _tickers, _ground_handlers, _air_handlers
    ordered = sorted(_entries.items(), key=lambda kv: kv[1]["priority"])
    _tickers = [(n, e["tick"]) for n, e in ordered if e["tick"]]
    _ground_handlers = [(n, e["ground"]) for n, e in ordered if e["ground"]]
    _air_handlers = [(n, e["air"]) for n, e in ordered if e["air"]]


def register(name, *, tick=None, ground=None, air=None, cancel=None, events=None, priority=50) -> None:
    """Register a feature.

    tick(pc, pawn, dt)    - called every frame (pawn may be None)
    ground(pc, pawn)      - jump pressed while standing
    air(pc, pawn) -> bool - jump pressed in the air; return True if it used the press
    cancel()              - stop this feature's action because another one is taking over
    events                - {event_name: fn(**kwargs)} handlers for emit()
    Lower priority numbers run first.
    """
    _entries[name] = {
        "tick": tick,
        "ground": ground,
        "air": air,
        "events": dict(events or {}),
        "priority": priority,
    }
    if cancel is not None:
        _cancellers[name] = cancel
    _rebuild()


def unregister(name) -> None:
    global busy
    _entries.pop(name, None)
    _cancellers.pop(name, None)
    if busy == name:
        busy = None
    _rebuild()


def emit(event: str, **kwargs) -> None:
    """Tell every feature that listens for `event` (errors in one never stop the others)."""
    for name, entry in list(_entries.items()):
        fn = entry["events"].get(event)
        if fn is not None:
            _safe(name, lambda f=fn: f(**kwargs))


def begin(name) -> None:
    """Take charge of movement, cancelling any other action that is running."""
    global busy
    if busy is not None and busy != name:
        cancel = _cancellers.get(busy)
        if cancel is not None:
            try:
                cancel()
            except Exception as e:  # noqa: BLE001
                logging.warning(f"[Modern Movement] cancel of '{busy}' failed: {e!r}")
    busy = name


def end(name) -> None:
    global busy
    if busy == name:
        busy = None


def _safe(name, fn, *args):
    """Call a feature callback; one feature failing must never take down the others."""
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001
        if name not in _warned:
            _warned.add(name)
            logging.warning(f"[Modern Movement] {name} raised {e!r} (further errors from it are hidden)")
        return False


# ---------------------------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------------------------


def get_pc_pawn():
    pc = get_pc()
    if pc is None:
        return None, None
    try:
        return pc, pc.Pawn
    except Exception:  # noqa: BLE001
        return pc, None


_vehicle_pawn = None
_vehicle_flag = False


def unusable(pawn) -> bool:
    """True for no pawn, vehicles and dead pawns (the class check is cached per pawn)."""
    global _vehicle_pawn, _vehicle_flag
    if pawn is None:
        return True
    try:
        same = _vehicle_pawn is not None and pawn == _vehicle_pawn
    except Exception:  # noqa: BLE001
        same = False
    if not same:
        try:
            flag = "Vehicle" in str(pawn.Class.Name)
        except Exception:  # noqa: BLE001
            flag = False
        _vehicle_pawn, _vehicle_flag = pawn, flag
    if _vehicle_flag:
        return True
    try:
        if float(pawn.Health) <= 0.0:
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def facing(pc) -> tuple[float, float]:
    """Flat (x, y) unit vector for the way the camera / controller is facing."""
    yaw = int(pc.Rotation.Yaw) * (2.0 * math.pi / 65536.0)
    return math.cos(yaw), math.sin(yaw)


_FALLBACK_JUMP = 600.0


def base_jump(pawn) -> float:
    """The pawn's own jump strength (JumpZ), or 600 if it can't be read."""
    try:
        value = float(pawn.JumpZ)
        if value > 0.0:
            return value
    except Exception:  # noqa: BLE001
        pass
    return _FALLBACK_JUMP


def position(pawn) -> tuple[float, float, float]:
    """The pawn's (x, y, z) location."""
    loc = pawn.Location
    return float(loc.X), float(loc.Y), float(loc.Z)


def hspeed(pawn) -> float:
    return math.hypot(float(pawn.Velocity.X), float(pawn.Velocity.Y))


# ---------------------------------------------------------------------------------------------
# Shared ground speed
# ---------------------------------------------------------------------------------------------
# Features that change how fast you can run (Sprint Surge, the slide's momentum carry) never
# write the pawn's GroundSpeed themselves: each asks for a multiplier here, and core applies
# the product once per tick. The game may write GroundSpeed itself (sprint start / stop, buffs),
# so each tick the value found is compared with what core last wrote: if it differs, the game
# changed it and that becomes the new base.

_speed_mults: dict = {}
_gs_base = None
_gs_written = None


def set_speed_mult(name: str, factor) -> None:
    """Ask for GroundSpeed x factor (None or 1.0 = no change from this feature)."""
    if factor is None or abs(factor - 1.0) < 1e-6:
        _speed_mults.pop(name, None)
    else:
        _speed_mults[name] = float(factor)


def ground_speed_base(pawn) -> float:
    """The pawn's GroundSpeed without any boost from this mod."""
    try:
        current = float(pawn.GroundSpeed)
    except Exception:  # noqa: BLE001
        return 440.0
    if _gs_written is not None and abs(current - _gs_written) <= 0.5 and _gs_base is not None:
        return _gs_base
    return current


def _apply_speed(pawn) -> None:
    global _gs_base, _gs_written
    if pawn is None:
        _gs_base = _gs_written = None
        return
    try:
        current = float(pawn.GroundSpeed)
    except Exception:  # noqa: BLE001
        return
    if not _speed_mults:
        if _gs_written is not None:
            if abs(current - _gs_written) <= 0.5:
                pawn.GroundSpeed = _gs_base          # still ours: put the game's value back
            _gs_base = _gs_written = None
        return
    if _gs_written is None or abs(current - _gs_written) > 0.5:
        _gs_base = current                          # first boosted tick, or the game changed it
    factor = 1.0
    for f in _speed_mults.values():
        factor *= f
    target = _gs_base * factor
    if abs(current - target) > 0.01:
        pawn.GroundSpeed = target
    _gs_written = target


def restore_speed() -> None:
    """Put the game's GroundSpeed back now (mod disabled)."""
    _speed_mults.clear()
    try:
        _apply_speed(get_pc_pawn()[1])
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------------------------
# The one PlayerTick hook
# ---------------------------------------------------------------------------------------------


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST_UNCONDITIONAL)
def _tick(obj, args, _ret, _func) -> None:
    global clock, phys

    pc = get_pc()
    if pc is None:
        return
    try:
        if obj != pc:  # other players' controllers (co-op host) tick this too
            return
    except Exception:  # noqa: BLE001
        return

    try:
        dt = float(args.DeltaTime)
    except Exception:  # noqa: BLE001
        dt = 1.0 / 60.0
    if dt <= 0.0:
        return
    clock += dt

    try:
        pawn = pc.Pawn
    except Exception:  # noqa: BLE001
        pawn = None
    if pawn is None:
        phys = -1
    else:
        try:
            phys = int(pawn.Physics)
        except Exception:  # noqa: BLE001
            phys = -1

    for name, fn in _tickers:
        _safe(name, fn, pc, pawn, dt)
    try:
        camera.apply(pc, None if pawn is None or unusable(pawn) else pawn)
    except Exception as e:  # noqa: BLE001
        if "camera" not in _warned:
            _warned.add("camera")
            logging.warning(f"[Modern Movement] camera effect failed: {e!r}")
    try:
        _apply_speed(None if pawn is None or unusable(pawn) else pawn)
    except Exception as e:  # noqa: BLE001
        if "speed" not in _warned:
            _warned.add("speed")
            logging.warning(f"[Modern Movement] could not set GroundSpeed: {e!r}")


# ---------------------------------------------------------------------------------------------
# The one jump key
# ---------------------------------------------------------------------------------------------


@keybind("Jump / Mantle / Double Jump", "SpaceBar")
def _jump_pressed() -> None:
    """Decide what a jump press means: ground jump, mantle, or double jump."""
    global _last_ground_press

    pc, pawn = get_pc_pawn()
    if pawn is None or unusable(pawn):
        return
    try:
        p = int(pawn.Physics)
    except Exception:  # noqa: BLE001
        return

    if p == PHYS_WALKING:
        _last_ground_press = clock
        for name, fn in _ground_handlers:
            _safe(name, fn, pc, pawn)
        return
    if p != PHYS_FALLING:
        return  # flying, ladders, swimming...: leave jump alone
    if busy == "mantle":
        return  # mid-climb (a climb runs in falling physics): a press does nothing

    if clock - _last_ground_press < _GROUND_GUARD:
        return  # still the same press that started the ground jump

    for name, fn in _air_handlers:
        if _safe(name, fn, pc, pawn):
            break  # first feature to use the press wins (mantle, then double jump)


def set_physics(pawn, phys: int) -> None:
    """Change the pawn's movement state (walking / falling / flying). SetPhysics is an engine function
    that does nothing from Python in this game (tested: it left you walking), so the value is written
    directly, which works (tested: falling + an upward speed pops you up). SetPhysics is still called
    first in case a build of the game does honour it."""
    try:
        pawn.SetPhysics(phys)
    except Exception:  # noqa: BLE001
        pass
    try:
        pawn.Physics = phys
    except Exception:  # noqa: BLE001
        pass


def jump_held(pc):
    """True while the jump key is held down, False if not, None if it can't be read.
    Reads the game's own list of held keys (PlayerInput.PressedKeys)."""
    key = getattr(_jump_pressed, "key", None) or "SpaceBar"
    try:
        keys = pc.PlayerInput.PressedKeys
        for k in keys:
            if str(k) == key:
                return True
        return False
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------------------------


def on_enable() -> None:
    global busy, _last_ground_press, _gs_base, _gs_written
    busy = None
    _speed_mults.clear()
    _gs_base = _gs_written = None
    _last_ground_press = -100.0
    _warned.clear()


def on_disable() -> None:
    global busy
    busy = None
    restore_speed()
    try:
        pc, pawn = get_pc_pawn()
        camera.reset(pc, pawn)
    except Exception:  # noqa: BLE001
        pass
    tracing.destroy()


KEYBINDS = [_jump_pressed]
HOOKS = [_tick]
