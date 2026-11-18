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
import time

from mods_base import ENGINE, get_pc, hook, keybind
from unrealsdk import logging
from unrealsdk.hooks import Type

from . import camera, diagnostics, tracing
from .runtime import ExecutionRole, PlayerContext, REGISTRY, TickFrame, is_authority

# Debounce so the Space keybind and PlayerInput:Jump hook do not double-fire one press.
_JUMP_EDGE_S = 0.05
_last_jump_edge = -100.0

PHYS_WALKING = 1
PHYS_FALLING = 2
PHYS_FLYING = 4

# Compatibility views for existing feature code. They are rebound from the active PlayerContext
# before a callback and copied back afterward. New code must use current_context()/TickFrame.
clock = 0.0
phys = -1
busy: str | None = None
_active_context: PlayerContext | None = None
_local_context: PlayerContext | None = None
_world_clock = 0.0
_world_frame = 0
_remote_tick_callbacks: list = []

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


def current_context() -> PlayerContext | None:
    return _active_context


def local_context() -> PlayerContext | None:
    return _local_context


def register_remote_tick(callback) -> None:
    if callback not in _remote_tick_callbacks:
        _remote_tick_callbacks.append(callback)


def unregister_remote_tick(callback) -> None:
    if callback in _remote_tick_callbacks:
        _remote_tick_callbacks.remove(callback)


def _activate(ctx: PlayerContext, frame: TickFrame) -> None:
    global _active_context, clock, phys, busy, _last_ground_press
    _active_context = ctx
    clock = frame.now
    phys = frame.phys_at_start
    busy = ctx.busy
    _last_ground_press = ctx.last_ground_press


def _deactivate(ctx: PlayerContext) -> None:
    global _active_context
    ctx.clock = clock
    ctx.busy = busy
    ctx.last_ground_press = _last_ground_press
    _active_context = None


def execute(ctx: PlayerContext, fn, *args, **kwargs):
    """Run one callback with the supplied player as the active compatibility context."""
    global _active_context, clock, phys, busy, _last_ground_press
    if _active_context is ctx:
        return fn(*args, **kwargs)
    previous = (_active_context, clock, phys, busy, _last_ground_press)
    try:
        try:
            current_phys = int(ctx.pawn.Physics) if ctx.pawn is not None else -1
        except Exception:  # noqa: BLE001
            current_phys = -1
        _activate(
            ctx,
            TickFrame(
                now=ctx.clock,
                dt=0.0,
                phys_at_start=current_phys,
                world_epoch=ctx.key.world_epoch,
            ),
        )
        return fn(*args, **kwargs)
    finally:
        _deactivate(ctx)
        _active_context, clock, phys, busy, _last_ground_press = previous


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
    for ctx in REGISTRY.contexts():
        if ctx.busy == name:
            ctx.busy = None
    if busy == name:
        busy = None
    _rebuild()


def emit(event: str, *, ctx: PlayerContext | None = None, **kwargs) -> None:
    """Tell every feature that listens for `event` (errors in one never stop the others)."""
    ctx = ctx or _active_context
    for name, entry in list(_entries.items()):
        fn = entry["events"].get(event)
        if fn is not None:
            _safe(name, lambda f=fn: f(**kwargs))


def begin(name, ctx: PlayerContext | None = None) -> None:
    """Take charge of movement, cancelling any other action that is running."""
    global busy
    ctx = ctx or _active_context
    owner = ctx.busy if ctx is not None else busy
    if owner is not None and owner != name:
        cancel = _cancellers.get(owner)
        if cancel is not None:
            try:
                cancel()
            except Exception as e:  # noqa: BLE001
                logging.warning(f"[Modern Movement] cancel of '{owner}' failed: {e!r}")
    if ctx is not None:
        ctx.busy = name
    busy = name


def end(name, ctx: PlayerContext | None = None) -> None:
    global busy
    ctx = ctx or _active_context
    if ctx is not None and ctx.busy == name:
        ctx.busy = None
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


def get_pc_pawn(ctx: PlayerContext | None = None):
    ctx = ctx or _active_context
    if ctx is not None:
        return ctx.controller, ctx.pawn
    pc = get_pc()
    if pc is None:
        return None, None
    try:
        return pc, pc.Pawn
    except Exception:  # noqa: BLE001
        return pc, None


def unusable(pawn) -> bool:
    """True for no pawn, vehicles and dead pawns."""
    if pawn is None:
        return True
    try:
        if "Vehicle" in str(pawn.Class.Name):
            return True
    except Exception:  # noqa: BLE001
        pass
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

def set_speed_mult(name: str, factor, ctx: PlayerContext | None = None) -> None:
    """Ask for GroundSpeed x factor (None or 1.0 = no change from this feature)."""
    ctx = ctx or _active_context
    if ctx is None:
        return
    if factor is None or abs(factor - 1.0) < 1e-6:
        ctx.speed_multipliers.pop(name, None)
    else:
        ctx.speed_multipliers[name] = float(factor)


def ground_speed_base(pawn, ctx: PlayerContext | None = None) -> float:
    """The pawn's GroundSpeed without any boost from this mod."""
    ctx = ctx or _active_context
    try:
        current = float(pawn.GroundSpeed)
    except Exception:  # noqa: BLE001
        return 440.0
    if ctx is not None:
        lease = ctx.ground_speed
        if lease.written is not None and abs(current - lease.written) <= 0.5 and lease.base is not None:
            return lease.base
    return current


def _apply_speed(ctx: PlayerContext, pawn) -> None:
    lease = ctx.ground_speed
    if pawn is None:
        lease.clear()
        return
    ctx.require_authority("GroundSpeed write")
    try:
        current = float(pawn.GroundSpeed)
    except Exception:  # noqa: BLE001
        return
    pawn_key = ctx.pawn_key
    if pawn_key is None:
        lease.clear()
        return
    if not ctx.speed_multipliers:
        if lease.written is not None:
            if lease.can_restore(pawn_key, current):
                pawn.GroundSpeed = lease.base
            lease.clear()
        return
    lease.adopt(pawn_key, current)
    factor = 1.0
    for f in ctx.speed_multipliers.values():
        factor *= f
    target = float(lease.base) * factor
    if abs(current - target) > 0.01:
        pawn.GroundSpeed = target
    lease.written = target


def restore_speed(ctx: PlayerContext | None = None) -> None:
    """Put the game's GroundSpeed back now (mod disabled)."""
    targets = (ctx,) if ctx is not None else REGISTRY.contexts()
    for target in targets:
        target.speed_multipliers.clear()
        try:
            _apply_speed(target, target.pawn)
        except Exception:  # noqa: BLE001
            target.ground_speed.clear()


# ---------------------------------------------------------------------------------------------
# The one PlayerTick hook
# ---------------------------------------------------------------------------------------------


def _world_info(pc):
    try:
        return pc.WorldInfo
    except Exception:  # noqa: BLE001
        try:
            return ENGINE.GetCurrentWorldInfo()
        except Exception:  # noqa: BLE001
            return None


def _role_for(pc, local_pc) -> ExecutionRole | None:
    local = False
    try:
        local = pc == local_pc
    except Exception:  # noqa: BLE001
        pass
    authority = is_authority(pc)
    if local and authority:
        world = _world_info(pc)
        try:
            if int(world.NetMode) == 0:
                return ExecutionRole.LOCAL_STANDALONE
        except Exception:  # noqa: BLE001
            pass
        return ExecutionRole.LOCAL_HOST
    if local:
        return ExecutionRole.LOCAL_REQUESTER
    if authority:
        return ExecutionRole.REMOTE_AUTHORITY
    return None


def _now(world, dt: float, local: bool) -> float:
    global _world_clock
    try:
        value = float(world.TimeSeconds)
        if value >= 0.0:
            _world_clock = value
            return value
    except Exception:  # noqa: BLE001
        pass
    if local:
        _world_clock += dt
    return _world_clock


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST_UNCONDITIONAL)
def _tick(obj, args, _ret, _func) -> None:
    global _local_context, _world_frame

    local_pc = get_pc()
    if local_pc is None:
        return
    role = _role_for(obj, local_pc)
    if role is None:
        return

    try:
        dt = float(args.DeltaTime)
    except Exception:  # noqa: BLE001
        dt = 1.0 / 60.0
    if dt <= 0.0:
        return

    world = _world_info(obj)
    REGISTRY.observe_world(world)
    now = _now(world, dt, role.local)
    try:
        pawn = obj.Pawn
    except Exception:  # noqa: BLE001
        pawn = None
    ctx = REGISTRY.observe(obj, role, now, pawn)
    if ctx is None:
        return
    if role.local:
        _local_context = ctx
        _world_frame += 1
    try:
        frame_phys = int(pawn.Physics) if pawn is not None else -1
    except Exception:  # noqa: BLE001
        frame_phys = -1
    frame = TickFrame(now=now, dt=dt, phys_at_start=frame_phys, world_epoch=REGISTRY.world_epoch)
    _activate(ctx, frame)
    try:
        # Local players run feature ticks (feel + HUD). On the listen host, REMOTE_AUTHORITY
        # contexts also tick so mirrored client actions stick on the server pawn.
        try:
            from . import input_state, network

            if role.local:
                if ctx.input_state is None:
                    ctx.input_state = input_state.InputTracker()
                network.tick(ctx, frame)
        except Exception as e:  # noqa: BLE001
            if "network" not in ctx.warned:
                ctx.warned.add("network")
                logging.warning(f"[Modern Movement] network tick failed: {e!r}")
        if role.local:
            for name, fn in _tickers:
                _safe(name, fn, obj, pawn, dt)
        if ctx.authority:
            for callback in tuple(_remote_tick_callbacks):
                _safe("authority", callback, ctx, frame)
        if ctx.presentation:
            try:
                camera.apply(obj, None if pawn is None or unusable(pawn) else pawn)
            except Exception as e:  # noqa: BLE001
                if "camera" not in ctx.warned:
                    ctx.warned.add("camera")
                    logging.warning(f"[Modern Movement] camera effect failed: {e!r}")
        if ctx.authority:
            try:
                _apply_speed(ctx, None if pawn is None or unusable(pawn) else pawn)
            except Exception as e:  # noqa: BLE001
                if "speed" not in ctx.warned:
                    ctx.warned.add("speed")
                    logging.warning(f"[Modern Movement] could not set GroundSpeed: {e!r}")
        diagnostics.event(
            "mm.tick",
            interval=5.0,
            player=ctx.key.player_id,
            role=ctx.role.value,
            pawn=ctx.pawn_generation,
        )
    finally:
        _deactivate(ctx)


# ---------------------------------------------------------------------------------------------
# The one jump key
# ---------------------------------------------------------------------------------------------


@keybind("Jump / Mantle / Double Jump", "SpaceBar")
def _jump_pressed() -> None:
    _jump_logic()


# Controller twin of the jump key. A on the pad is also the game's own jump button, so this only
# adds the mantle / double jump decision on top of the normal jump. Rebind it in the menu if you
# have changed your controller layout.
@keybind("Jump / Mantle / Double Jump (Controller)", "XboxTypeS_A")
def _jump_pressed_pad() -> None:
    _jump_logic()


@hook("WillowGame.WillowPlayerInput:Jump", Type.POST)
def _on_player_input_jump(obj, _args, _ret, _func) -> None:
    """Game jump path (Space / pad). More reliable than the keybind alone for mid-air presses."""
    try:
        # PlayerInput lives on the controller as .Outer in Willow.
        pc = getattr(obj, "Outer", None) or get_pc()
    except Exception:  # noqa: BLE001
        pc = get_pc()
    local = local_context()
    if local is not None and pc is not None:
        try:
            if pc != local.controller:
                return
        except Exception:  # noqa: BLE001
            pass
    _jump_logic()


def _slide_owns_jump(pc, pawn) -> bool:
    """Active Slide (or its short grace window) consumes the jump before other features."""
    try:
        from .features import slide
    except Exception:  # noqa: BLE001
        return False
    try:
        return bool(slide.try_consume_jump(pc, pawn))
    except Exception as exc:  # noqa: BLE001
        diagnostics.event("mm.input.slide_jump_error", error=repr(exc))
        return False


def gameplay_ready() -> bool:
    """Local movement never waits on peer handshake (own-pawn client simulation)."""
    return True


def _jump_logic() -> None:
    """Decide what a jump press means: slide exit, ground jump, mantle, or double jump."""
    global _last_ground_press, _last_jump_edge

    now_edge = time.monotonic()
    if now_edge - _last_jump_edge < _JUMP_EDGE_S:
        return
    _last_jump_edge = now_edge

    pc = get_pc()
    ctx = local_context()
    if ctx is None and pc is not None:
        ctx = REGISTRY.resolve_controller(pc)
    if pc is None and ctx is not None:
        pc = ctx.controller
    if ctx is None or not ctx.authority:
        # Still allow a best-effort path from get_pc when context has not ticked yet.
        if pc is None:
            diagnostics.event("mm.input.no_context", interval=2.0)
            return
        try:
            pawn = pc.Pawn
        except Exception:  # noqa: BLE001
            return
        if pawn is None or unusable(pawn):
            return
        try:
            p = int(pawn.Physics)
        except Exception:  # noqa: BLE001
            return
        if p == PHYS_WALKING:
            _last_ground_press = clock
            for name, fn in _ground_handlers:
                if name == "slide":
                    continue
                _safe(name, fn, pc, pawn)
            return
        if p != PHYS_FALLING:
            return
        if busy == "mantle":
            return
        if clock - _last_ground_press < _GROUND_GUARD:
            return
        for name, fn in _air_handlers:
            if _safe(name, fn, pc, pawn):
                break
        return

    pc, pawn = ctx.controller, ctx.pawn
    if pawn is None or unusable(pawn):
        return
    try:
        p = int(pawn.Physics)
    except Exception:  # noqa: BLE001
        return

    # Keybinds / input hooks fire outside PlayerTick. Activate context so handlers can write.
    def _with_ctx(fn):
        return execute(ctx, fn)

    if p == PHYS_WALKING:

        def _ground() -> None:
            global _last_ground_press
            _last_ground_press = clock
            ctx.last_ground_press = clock
            if _slide_owns_jump(pc, pawn):
                return
            for name, fn in _ground_handlers:
                if name == "slide":
                    continue
                _safe(name, fn, pc, pawn)

        _with_ctx(_ground)
        return
    if p != PHYS_FALLING and p != PHYS_FLYING:
        return  # ladders / swimming / etc.

    def _air() -> bool:
        if busy == "mantle":
            return False
        if clock - _last_ground_press < _GROUND_GUARD:
            return False
        if _slide_owns_jump(pc, pawn):
            return True
        for name, fn in _air_handlers:
            if _safe(name, fn, pc, pawn):
                return True
        return False

    _with_ctx(_air)


def set_physics(pawn, phys: int, ctx: PlayerContext | None = None) -> None:
    """Change the pawn's movement state (walking / falling / flying). SetPhysics is an engine function
    that does nothing from Python in this game (tested: it left you walking), so the value is written
    directly, which works (tested: falling + an upward speed pops you up). SetPhysics is still called
    first in case a build of the game does honour it."""
    ctx = ctx or _active_context
    if ctx is None:
        raise RuntimeError("Physics write has no player context")
    ctx.require_authority("Physics write")
    try:
        pawn.SetPhysics(phys)
    except Exception:  # noqa: BLE001
        pass
    try:
        pawn.Physics = phys
    except Exception:  # noqa: BLE001
        pass


def set_velocity(pawn, x: float, y: float, z: float | None = None) -> None:
    """Write Velocity the Eternal way: assign a full Vector struct (component writes often no-op)."""
    try:
        if z is None:
            z = float(pawn.Velocity.Z)
    except Exception:  # noqa: BLE001
        z = 0.0
    try:
        import unrealsdk

        vec = unrealsdk.make_struct("Vector", X=float(x), Y=float(y), Z=float(z))
        if vec is not None:
            pawn.Velocity = vec
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        pawn.Velocity.X = float(x)
        pawn.Velocity.Y = float(y)
        pawn.Velocity.Z = float(z)
    except Exception:  # noqa: BLE001
        pass


def jump_held(pc):
    """True while the jump key (keyboard or controller) is held down, False if not, None if it
    can't be read. Reads the game's own list of held keys (PlayerInput.PressedKeys)."""
    wanted = {
        getattr(_jump_pressed, "key", None) or "SpaceBar",
        getattr(_jump_pressed_pad, "key", None) or "XboxTypeS_A",
    }
    try:
        keys = pc.PlayerInput.PressedKeys
        for k in keys:
            if str(k) in wanted:
                return True
        return False
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------------------------


def _detach_context(ctx: PlayerContext, pawn, reason: str) -> None:
    try:
        from . import authority

        if ctx.authority:
            authority.cancel_all(ctx, reason)
    except Exception:  # noqa: BLE001
        pass
    try:
        restore_speed(ctx)
    except Exception:  # noqa: BLE001
        pass
    if ctx.presentation:
        try:
            camera.reset(ctx.controller, pawn)
        except Exception:  # noqa: BLE001
            pass


def on_enable() -> None:
    global busy, _last_ground_press, _active_context, _local_context, _world_clock, _world_frame
    from . import authority, network, rules

    REGISTRY.clear("mod_enable")
    REGISTRY.add_detach_callback(_detach_context)
    busy = None
    _last_ground_press = -100.0
    _active_context = None
    _local_context = None
    _world_clock = 0.0
    _world_frame = 0
    _warned.clear()
    diagnostics.reset()
    register_remote_tick(authority.tick)
    network.set_rules(rules.EMPTY_RULES)
    network.enable()


def on_disable() -> None:
    global busy, _active_context, _local_context
    from . import authority, network

    busy = None
    restore_speed()
    try:
        network.disable()
    except Exception:  # noqa: BLE001
        pass
    unregister_remote_tick(authority.tick)
    REGISTRY.clear("mod_disable")
    _active_context = None
    _local_context = None
    tracing.destroy()


KEYBINDS = [_jump_pressed, _jump_pressed_pad]
HOOKS = [_tick, _on_player_input_jump]
