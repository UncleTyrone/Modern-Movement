"""Dash: press a key to dash a fixed distance (800 units), forward, backward, left or right, on the
ground or in the air. The cooldown is the only limit on how often.

On the ground a dash is the same as in the air: it starts with a tiny skim just above the floor
(walking physics would cap your speed at your run speed), timed to land as the dash ends.

How it works
  A single velocity impulse would travel a different distance depending on ground
  friction, air physics and frame rate. Instead, for the length of the air dash the mod
  sets the pawn's horizontal velocity every tick and measures how far the pawn has
  really moved from where the air dash started.

  Speed:              a fixed, fast speed (4000 units/s) the whole way, stopping exactly
                      on its distance (800 units).
  After the air dash: speed you had in the air dash direction is handed back, so an air dash
                      out of a sprint carries on sprinting in a straight line, and standing
                      still you stop cleanly. Sideways speed is never carried over.
  Straight line:      the path is held on the aimed line, and for a tenth of a second after
                      the air dash sideways drift is cancelled so you keep exactly the
                      direction you aimed.

Direction: the movement keys you hold, snapped to forward, backward, left or right of the camera
(no diagonals). With no keys held it dashes forward.

The air dash ends early if you hit a wall or something else stops you. Vertical velocity is
never touched, so jumping and falling work normally.

Distances and speeds are in Unreal units.
"""

import math
from dataclasses import dataclass

from mods_base import BoolOption, SliderOption, keybind

from unrealsdk import logging
from unrealsdk.hooks import Block, Type, add_hook, remove_hook

from .. import authority, camera, core, fx, hudfx, network
from ..protocol import Reason
from ..runtime import REGISTRY

enabled_option = BoolOption(
    "Dash Enabled",
    True,
    "On",
    "Off",
    description="Turn dash on or off. Works on the ground and in the air.",
)


air_only_option = BoolOption(
    "Air Dash Only", False, "On", "Off",
    description="Only allow dashing while airborne.",
)
cooldown_slider = SliderOption(
    "Dash Cooldown (s)",
    value=2,
    min_value=0,
    max_value=5,
    step=1,
    is_integer=True,
    description="Time until you can dash again.",
)

audio_option = BoolOption(
    "Dash Audio Effect",
    True,
    "On",
    "Off",
    description="Adds a sound effect when dashing.",
)

screen_option = BoolOption(
    "Dash Screen Effect",
    True,
    "On",
    "Off",
    description="Shows ECHO arrows around the crosshair in the direction you dash.",
)

pip_option = BoolOption(
    "Dash Ready Indicator",
    True,
    "On",
    "Off",
    description="A small hex next to the crosshair fills while the dash cools down and flashes when it is ready.",
)

dodge_option = BoolOption(
    "Dash Damage Reduction",
    True,
    "On",
    "Off",
    description="Ignore 30% of damage when dashing and a 100% reduction for perfectly timed dashes.",
)
perfect_fx_option = BoolOption(
    "Perfect Dodge Effect",
    True,
    "On",
    "Off",
    description="ECHO chevron burst around the crosshair when a perfect dash dodge lands.",
)
perfect_slider = SliderOption(
    "Perfect Dash Window (ms)", value=150, min_value=0, max_value=400, step=10, is_integer=True,
    description="Adjust the timing window for a perfect dash.",
)

cam_shake_slider = SliderOption(
    "Dash Camera Shake (%)", value=20, min_value=0, max_value=200, step=10, is_integer=True,
    description="A camera bob and tilt during the dash, settling just after it. Does not move your aim. 0 = off.",
)
push_forward_slider = SliderOption(
    "Forward Dash Camera Push (%)", value=80, min_value=0, max_value=200, step=10, is_integer=True,
    description="The view nods down briefly as you dash forward, then eases back. Your aim moves with it and returns exactly. 0 = off.",
)

push_back_slider = SliderOption(
    "Backward Dash Camera Push (%)", value=80, min_value=0, max_value=200, step=10, is_integer=True,
    description="The view nods up briefly as you dash backward, then eases back. Your aim moves with it and returns exactly. 0 = off.",
)

cam_lean_slider = SliderOption(
    "Dash Camera Lean (%)", value=50, min_value=0, max_value=200, step=10, is_integer=True,
    description="The camera tilts toward the side you dash to, then levels out. Does not move your aim. 0 = off.",
)
ready_option = BoolOption(
    "Dash Cooldown Audio Effect",
    True,
    "On",
    "Off",
    description="Adds a sound effect when the dash cooldown finishes.",
)

_DEBUG = False  # set to True to print diagnostic messages to the console

_DONE_WITHIN = 2.0   # units: close enough to the target to call the air dash finished
_STALL_TICKS = 3     # consecutive ticks of almost no progress = we hit something
_STALL_RATIO = 0.10  # "almost no progress" = under 10% of the expected movement

_DISTANCE = 800.0  # how far an air dash carries you, in Unreal units
_SPEED = 4000.0    # air dash top speed, units/s
_EXIT_LOCK = 0.10  # seconds of post-air-dash straight lock
_LAT_GAIN = 0.6    # fraction of any sideways offset from the air dash line corrected per tick
_LAT_MAX = 500.0   # cap on that correction, units/s

_READY_SOUND = "Ake_UI.UI_Shields.Ak_Play_UI_Shield_Impact_The_Bee_Res"


# ---- camera effects (applied by camera.py, shared with the slide) ------------------------
_CAM_SHAKE_EYE = 2.5    # bob at 100%, units
_CAM_SHAKE_ROLL = 1.0   # shake tilt at 100%, degrees
_CAM_LEAN = 4.0         # lean at 100%, degrees
_SKIM_MARGIN = 1.15     # ground dash: skim timed to land just after the dash's own 0.2 s...
_RESKIM = 90.0          # ...and if the floor is touched early, this small upward speed again
_FALLBACK_GRAVITY = 1050.0
_CAM_PUSH = 3.0         # forward / backward push (view nod) at 100%, degrees
_CAM_RISE = 0.06        # seconds to reach full strength
_CAM_FALL = 0.30        # seconds to settle after the dash ends
_CAM_CUT = 0.10         # ...or this fast when a mantle takes over
@dataclass
class DashState:
    dash: dict | None = None
    exit: dict | None = None
    last_end: float = -100.0
    ready_pending: bool = False
    cam: dict | None = None
    pip_on: bool = False
    dodge_inside: bool = False


_fallback_state = DashState()


def _state(ctx=None) -> DashState:
    ctx = ctx or core.current_context()
    return ctx.state("dash", DashState) if ctx is not None else _fallback_state


def _cam_start(pc, dx, dy) -> None:
    state = _state()
    side = 0
    ahead = 0
    try:
        fx_, fy_ = core.facing(pc)
        right = dx * -fy_ + dy * fx_
        side = 1 if right > 0.7 else (-1 if right < -0.7 else 0)
        along = dx * fx_ + dy * fy_
        ahead = 1 if along > 0.7 else (-1 if along < -0.7 else 0)
    except Exception:  # noqa: BLE001
        pass
    state.cam = {"t0": core.clock, "end": None, "side": side, "ahead": ahead, "t": 0.0}


def _cam_update(dt) -> None:
    state = _state()
    c = state.cam
    if c is None:
        return
    rise = min(1.0, (core.clock - c["t0"]) / _CAM_RISE)
    env = rise * rise * (3.0 - 2.0 * rise)
    if c["end"] is not None:
        f = (core.clock - c["end"]) / c.get("fall", _CAM_FALL)
        if f >= 1.0:
            state.cam = None                      # done: camera.py takes the offsets out
            return
        env *= 1.0 - f * f * (3.0 - 2.0 * f)
    c["t"] += dt
    bob, tilt = camera.wave(c["t"])
    shake = cam_shake_slider.value / 100.0 * env
    # Push: forward dash nods the view down, backward nods it up.
    push = 0.0
    if c["ahead"] > 0:
        push = -_CAM_PUSH * push_forward_slider.value / 100.0 * env
    elif c["ahead"] < 0:
        push = _CAM_PUSH * push_back_slider.value / 100.0 * env
    camera.request(
        "dash",
        eye=bob * _CAM_SHAKE_EYE * shake,
        roll=tilt * _CAM_SHAKE_ROLL * shake + c["side"] * _CAM_LEAN * cam_lean_slider.value / 100.0 * env,
        pitch=push,
    )


def _log(msg: str) -> None:
    if _DEBUG:
        core.log("Dash", msg)


def _direction(pc, pawn) -> tuple[float, float]:
    """Which way to air dash: forward, backward, left or right (never diagonal).

    The movement keys you are holding are snapped to the nearest of the four directions
    relative to the camera. With no keys held (or a perfect diagonal) it dashes forward.
    """
    fx, fy = core.facing(pc)
    try:
        ax, ay = float(pawn.Acceleration.X), float(pawn.Acceleration.Y)
    except Exception:  # noqa: BLE001
        return fx, fy
    if math.hypot(ax, ay) <= 1.0:
        return fx, fy  # no keys held: forward
    ahead = ax * fx + ay * fy      # how far the input points forward (+) or back (-)
    right = ax * -fy + ay * fx     # how far it points to the right (+) or left (-)
    if abs(ahead) >= abs(right):
        return (fx, fy) if ahead >= 0 else (-fx, -fy)
    return (-fy, fx) if right > 0 else (fy, -fx)


def _direction_code(pc, pawn) -> str:
    fx_, fy_ = core.facing(pc)
    dx, dy = _direction(pc, pawn)
    ahead = dx * fx_ + dy * fy_
    right = dx * -fy_ + dy * fx_
    if abs(ahead) >= abs(right):
        return "forward" if ahead >= 0.0 else "back"
    return "right" if right >= 0.0 else "left"


def _direction_from_code(pc, code: str) -> tuple[float, float] | None:
    fx_, fy_ = core.facing(pc)
    return {
        "forward": (fx_, fy_),
        "back": (-fx_, -fy_),
        "right": (-fy_, fx_),
        "left": (fy_, -fx_),
    }.get(code)


def _end(pawn, reason: str, restore: bool = True, lock: bool = True) -> None:
    """Finish the air dash and hand the pre-air-dash velocity back (unless another action took over)."""
    state = _state()
    if state.dash is None:
        return
    d = state.dash
    state.dash = None
    state.last_end = core.clock
    state.ready_pending = int(cooldown_slider.value) > 0
    ctx = core.current_context()
    core.end("dash", ctx=ctx)
    if ctx is not None and d.get("action"):
        authority.end_action(ctx, "dash", reason)
    _log(f"air dash ended ({reason}) after {d['elapsed']:.2f}s")
    core.emit("dash_end", reason=reason, air=d["air"])
    if state.cam is not None and state.cam["end"] is None:
        state.cam["end"] = core.clock
        state.cam["fall"] = _CAM_FALL if lock else _CAM_CUT
    if pawn is not None and restore:
        try:
            dx, dy = d["dir"]
            ex, ey = d["entry_vel"]
            # Only speed IN the air dash direction comes back, so you leave it going exactly the
            # way you aimed. Sideways speed is dropped (it is what made you drift), speed AGAINST
            # the air dash is dropped (it bounced you backwards), and so is anything into a wall.
            along = ex * dx + ey * dy
            along = 0.0 if reason.startswith("blocked") else max(0.0, along)
            pawn.Velocity.X = along * dx
            pawn.Velocity.Y = along * dy
            if lock:
                state.exit = {"dir": (dx, dy), "until": core.clock + _EXIT_LOCK}
        except Exception:  # noqa: BLE001
            pass


def _cancel() -> None:
    """Another movement action (the mantle) is taking over: stop at once. Your speed goes back to
    what it was before the air dash (in the dash direction), with no straight lock afterwards,
    and the dash's camera shake and lean end quickly."""
    _state().exit = None
    ctx = core.current_context()
    pawn = ctx.pawn if ctx is not None else None
    _end(pawn, "interrupted", restore=True, lock=False)


def _surface_burst(pc, pawn, vx: float, vy: float, airborne: bool) -> None:
    """Dash kicks up the same dust as a slide, on the ground and in the air."""
    try:
        from . import surfacefx

        mag = math.hypot(vx, vy) or 1.0
        del airborne
        surfacefx.burst(pc, pawn, vx / mag, vy / mag, 6)
    except Exception:  # noqa: BLE001
        pass


def _skim_speed(pc) -> float:
    """Upward speed for a skim that lands as a full-length dash ends (time = distance / speed)."""
    try:
        g = abs(float(pc.WorldInfo.WorldGravityZ))
    except Exception:  # noqa: BLE001
        g = 0.0
    # Known world gravity (including moon values below 100) must win over the BL2 fallback.
    if g <= 0.0:
        g = _FALLBACK_GRAVITY
    return 0.5 * g * (_DISTANCE / _SPEED) * _SKIM_MARGIN


def _set_physics(pawn, phys: int) -> None:
    core.set_physics(pawn, phys)


# Eternal: host dashes live in a module dict and are serviced every local tick.
# DJ-proven for our stack: joiner must ALSO hold Velocity locally — a 0.15s host-only
# dash finishes before autonomous-proxy replication arrives, which feels like "nothing".
_HOST_DASHES: dict[int, dict] = {}
_CLIENT_DASH: dict | None = None
_HOST_DASH_S = 0.15  # Eternal coroutine_tick_dash duration


def release_player(player_id: int | None) -> None:
    """Drop host dash holds. None clears every joiner (level change)."""
    if player_id is None:
        _HOST_DASHES.clear()
        return
    _HOST_DASHES.pop(int(player_id), None)


def release_client() -> None:
    """Drop the local predicted dash after a respawn or travel."""
    global _CLIENT_DASH
    _CLIENT_DASH = None


def _hold_dash(pawn, vx: float, vy: float, left: float, vz: float = 0.0) -> dict:
    return {"pawn": pawn, "vx": float(vx), "vy": float(vy), "vz": float(vz), "left": float(left)}


def host_apply_dash(ctx, vx: float, vy: float, vz: float = 0.0) -> None:
    """Eternal-style: register a timed full-Vector Velocity hold on the joiner's server pawn."""
    if not enabled_option.value or ctx.pawn is None:
        return
    mag = math.hypot(vx, vy)
    if mag < 1.0:
        return
    # Ground skim is applied once below. Later ticks keep whatever Z the pawn has.
    _HOST_DASHES[ctx.key.player_id] = _hold_dash(ctx.pawn, vx, vy, _HOST_DASH_S, vz)

    def apply() -> None:
        try:
            if int(ctx.pawn.Physics) == core.PHYS_WALKING:
                core.set_physics(ctx.pawn, core.PHYS_FALLING)
        except Exception:  # noqa: BLE001
            pass
        # Stamp the skim once. Later ticks must not rewrite Z: a constant Z
        # fights gravity on the way back from the host and the joiner rubber-bands.
        z = float(vz) if abs(float(vz)) > 1.0 else None
        core.set_velocity(ctx.pawn, float(vx), float(vy), z)

    core.execute(ctx, apply)
    _surface_burst(ctx.controller, ctx.pawn, float(vx), float(vy), abs(float(vz)) < 1.0)


def _keep_dash_airborne(pawn) -> None:
    """If the burst touches walking, run speed clamps it. Leave Z alone."""
    try:
        if int(pawn.Physics) == core.PHYS_WALKING:
            pawn.Physics = core.PHYS_FALLING
    except Exception:  # noqa: BLE001
        pass


def _service_one_dash(d: dict, dt: float) -> bool:
    """Apply one Eternal hold step. Returns True when finished."""
    d["left"] -= dt
    pawn = d["pawn"]
    try:
        _keep_dash_airborne(pawn)
        if d["left"] <= 0.0:
            mag = math.hypot(d["vx"], d["vy"])
            if mag > 1.0:
                # Ease the horizontal burst only. Forcing Z to -10 snapped the joiner
                # against the host correction at the end of every dash.
                core.set_velocity(pawn, d["vx"] / mag * 200.0, d["vy"] / mag * 200.0, None)
            return True
        core.set_velocity(pawn, d["vx"], d["vy"], None)
    except Exception:  # noqa: BLE001
        return True
    return False


def _service_host_dashes(dt: float) -> None:
    """Run once per local frame on the listen host — mirrors Eternal's coroutine_tick_dash."""
    if not _HOST_DASHES:
        return
    done: list[int] = []
    for pid, d in _HOST_DASHES.items():
        if _service_one_dash(d, dt):
            done.append(pid)
    for pid in done:
        _HOST_DASHES.pop(pid, None)


def _service_client_dash(dt: float) -> None:
    """Joiner local predict — same numbers/duration as the host hold (DJ dual-write)."""
    global _CLIENT_DASH
    if _CLIENT_DASH is None:
        return
    if _service_one_dash(_CLIENT_DASH, dt):
        _CLIENT_DASH = None
        # Cooldown starts when the dash ends, same as a local dash. The ready hex fills from here.
        state = _state()
        state.last_end = core.clock
        state.ready_pending = int(cooldown_slider.value) > 0
        state.pip_on = True


def _dash_pressed_impl(direction_code: str | None = None) -> bool:
    state = _state()
    ctx = core.current_context()
    if ctx is None or not ctx.authority:
        return False
    ctx.require_authority("dash start")
    # Per-player busy only — global core.busy would block joiner dashes while the host acts.
    if not enabled_option.value or state.dash is not None or ctx.busy is not None:
        return False
    if core.clock - state.last_end < float(int(cooldown_slider.value)):
        return False

    pc = ctx.controller
    pawn = ctx.pawn
    if pawn is None or core.unusable(pawn):
        return False

    # Air dashes, plus ground dashes with Ground Dash on (not while swimming, climbing, etc.).
    # On the ground or in the air (not while swimming, climbing, etc.); the cooldown is the only limit.
    phys = int(pawn.Physics)
    if phys == core.PHYS_FALLING:
        air = True
    elif phys == core.PHYS_WALKING:
        if air_only_option.value:
            return False
        air = False
    else:
        return False

    selected = _direction_from_code(pc, direction_code) if direction_code is not None else _direction(pc, pawn)
    if selected is None:
        return False
    dx, dy = selected
    loc = (float(pawn.Location.X), float(pawn.Location.Y))
    entry_vel = (float(pawn.Velocity.X), float(pawn.Velocity.Y))
    entry_speed = math.hypot(*entry_vel)

    state.exit = None
    core.begin("dash", ctx=ctx)
    state.dash = {
        "dir": (dx, dy),
        "start": loc,
        "last": loc,
        "distance": _DISTANCE,
        "speed": _SPEED,
        "floor": max(0.0, entry_vel[0] * dx + entry_vel[1] * dy),  # speed you already had in the air dash direction
        "entry_vel": entry_vel,
        "air": air,
        "elapsed": 0.0,
        "stalled": 0,
        "commanded": 0.0,
        "t0": core.clock,
        # Eternal-style: joiner server pawns must not use Location stall (client owns moves).
        "remote": not ctx.local,
    }
    if not air:
        # A ground dash is an air dash taken just above the floor: walking caps your speed at your run
        # speed (and flying caps it too), so it starts with a tiny skim timed to land as it ends.
        _set_physics(pawn, core.PHYS_FALLING)
        try:
            pawn.Velocity.Z = _skim_speed(pc)
        except Exception:  # noqa: BLE001
            pass
    if screen_option.value and ctx.presentation:
        hudfx.dash_arrows(pc, (dx, dy))
    if ctx.presentation:
        _cam_start(pc, dx, dy)
    if audio_option.value and ctx.presentation:
        fx.play_first(pc, pawn, fx.dash_paths())
    _surface_burst(pc, pawn, dx * _SPEED, dy * _SPEED, air)
    _log(
        f"air dash start: dir=({dx:.2f}, {dy:.2f}) distance={state.dash['distance']:.0f} "
        f"speed={state.dash['speed']:.0f} air={air} entry speed={entry_speed:.0f}"
    )
    return True


def _run_dash(pawn, dt: float) -> None:
    d = _state().dash
    if d is None:
        return
    if core.unusable(pawn):
        _end(pawn, "vehicle or dead", restore=False)
        return

    dx, dy = d["dir"]
    d["elapsed"] += dt

    # Joiner server pawns: Eternal pattern — timed Velocity override only.
    # Location barely moves on the listen host (client owns moves), so stall/distance checks
    # ended the dash in ~3 ticks and the joiner saw absolutely nothing.
    if d.get("remote"):
        duration = d["distance"] / max(1.0, d["speed"])
        if d["elapsed"] >= duration:
            _end(pawn, "reached distance")
            return
        speed = max(d["speed"], d["floor"])
        hold_z = d.get("hold_z")
        if hold_z is None:
            try:
                hold_z = float(pawn.Velocity.Z)
            except Exception:  # noqa: BLE001
                hold_z = 0.0
        # Eternal: assign a full Vector each tick (component writes are unreliable on TPS).
        core.set_velocity(pawn, dx * speed, dy * speed, float(hold_z))
        try:
            pawn.Acceleration.X = 0.0
            pawn.Acceleration.Y = 0.0
        except Exception:  # noqa: BLE001
            pass
        return

    x, y = float(pawn.Location.X), float(pawn.Location.Y)

    # How far have we really gone along the air dash line?
    travelled = (x - d["start"][0]) * dx + (y - d["start"][1]) * dy
    remaining = d["distance"] - travelled

    # How much did the last tick's command actually move us? (friction / walls)
    if d["elapsed"] > 0.0 and d["commanded"] > 0.0:
        moved = (x - d["last"][0]) * dx + (y - d["last"][1]) * dy
        d["stalled"] = d["stalled"] + 1 if moved < _STALL_RATIO * d["commanded"] else 0
    d["last"] = (x, y)

    if remaining <= _DONE_WITHIN:
        _end(pawn, "reached distance")
        return
    if d["stalled"] >= _STALL_TICKS:
        _end(pawn, f"blocked after {travelled:.0f} units")
        return
    # Safety net: never run away if something keeps resisting the air dash.
    if d["elapsed"] > max(0.5, 4.0 * d["distance"] / d["speed"]):
        _end(pawn, f"timed out after {travelled:.0f} units")
        return

    # Constant top speed (or your own speed if that is higher), never more than what is left in
    # one tick, so the air dash stops exactly on its distance.
    speed = min(max(d["speed"], d["floor"]), remaining / dt)

    # Hold the path dead straight: any sideways offset from the air dash line (collision slide, game
    # air control) is pulled back in, so the air dash goes exactly where you aimed it.
    lateral = (x - d["start"][0]) * -dy + (y - d["start"][1]) * dx
    fix = max(-_LAT_MAX, min(_LAT_MAX, -lateral * _LAT_GAIN / dt))

    d["commanded"] = speed * dt
    try:
        vz = float(pawn.Velocity.Z)
    except Exception:  # noqa: BLE001
        vz = 0.0
    if not d["air"] and core.phys == core.PHYS_WALKING:
        # Touched the floor early (a bump, an upward slope): skim off again at full speed.
        _set_physics(pawn, core.PHYS_FALLING)
        vz = _RESKIM
    core.set_velocity(pawn, dx * speed - dy * fix, dy * speed + dx * fix, vz)
    # Held forward / sprint input must not keep pushing us while the air dash is in charge.
    try:
        pawn.Acceleration.X = 0.0
        pawn.Acceleration.Y = 0.0
    except Exception:  # noqa: BLE001
        pass
    _log(f"t={d['elapsed']:.3f} travelled={travelled:.0f} remaining={remaining:.0f} cmd={speed:.0f}u/s")


def _run_exit_lock(pawn) -> None:
    """Briefly after an air dash: cancel sideways drift so you keep the direction you aimed."""
    state = _state()
    if state.exit is None:
        return
    if pawn is None or core.clock >= state.exit["until"] or core.busy is not None or core.unusable(pawn):
        state.exit = None
        return
    dx, dy = state.exit["dir"]
    try:
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
        along = vx * dx + vy * dy
        pawn.Velocity.X = dx * along
        pawn.Velocity.Y = dy * along
        ax, ay = float(pawn.Acceleration.X), float(pawn.Acceleration.Y)
        side = ax * -dy + ay * dx  # steering input across the air dash line
        pawn.Acceleration.X = ax + dy * side
        pawn.Acceleration.Y = ay - dx * side
    except Exception:  # noqa: BLE001
        state.exit = None


def _update_pip() -> None:
    """Feed the ready indicator: empty while dashing, filling during the cooldown, then ready."""
    state = _state()
    if not (enabled_option.value and pip_option.value):
        if state.pip_on:
            hudfx.pip_clear()
            state.pip_on = False
        return
    cool = float(int(cooldown_slider.value))
    if state.dash is not None or _CLIENT_DASH is not None:
        hudfx.pip_progress(0.0)
        state.pip_on = True
    elif state.pip_on:
        p = (core.clock - state.last_end) / cool if cool > 0 else 1.0
        if p >= 1.0:
            hudfx.pip_ready()
            state.pip_on = False
        else:
            hudfx.pip_progress(p)


def _tick(pc, pawn, dt) -> None:
    state = _state()
    ctx = core.current_context()
    if ctx is None:
        return
    # Eternal services host dashes from a global tick; we use the local player's tick.
    if ctx.local:
        _service_host_dashes(dt)
        _service_client_dash(dt)
    if ctx.presentation:
        _cam_update(dt)
        _update_pip()
    # Cooldown over: play the ready sound once.
    if state.ready_pending and state.dash is None and pawn is not None:
        if not (enabled_option.value and ready_option.value):
            state.ready_pending = False
        elif core.clock - state.last_end >= float(int(cooldown_slider.value)):
            state.ready_pending = False
            if ctx.presentation:
                fx.play_sound(pc, pawn, _READY_SOUND)
    if state.dash is None:
        _run_exit_lock(pawn)
        return
    if pawn is None or not enabled_option.value:
        _end(pawn, "pawn gone or air dash disabled", restore=False)
        return
    _run_dash(pawn, dt)


def _authority_start(ctx, payload):
    direction = payload.get("direction")
    if direction not in ("forward", "back", "left", "right"):
        return Reason.INVALID_INPUT, {}
    started = core.execute(ctx, _dash_pressed_impl, direction)
    if not started:
        state = _state(ctx)
        if state.dash is not None:
            return Reason.BUSY, _snapshot(ctx)
        if core.clock - state.last_end < float(int(cooldown_slider.value)):
            return Reason.COOLDOWN, _snapshot(ctx)
        return Reason.INVALID_INPUT, _snapshot(ctx)
    action_id = authority.allocate_action(ctx, "dash")
    state = _state(ctx)
    if state.dash is not None:
        state.dash["action"] = action_id
    response = _snapshot(ctx)
    response["action"] = action_id
    return Reason.OK, response


def _authority_tick(ctx, frame) -> None:
    if ctx.local:
        return
    core.execute(ctx, _tick, ctx.controller, ctx.pawn, frame.dt)


def _authority_cancel(ctx, reason: str) -> None:
    def cancel():
        state = _state(ctx)
        if state.dash is not None:
            _end(ctx.pawn, reason, restore=False, lock=False)
        state.exit = None

    core.execute(ctx, cancel)


def _snapshot(ctx) -> dict:
    state = _state(ctx)
    dash = state.dash
    cooldown = float(int(cooldown_slider.value))
    left = max(0.0, cooldown - (ctx.clock - state.last_end))
    return {
        "active": dash is not None,
        "action": int(dash.get("action", 0)) if dash is not None else 0,
        "direction": list(dash["dir"]) if dash is not None else [0.0, 0.0],
        "elapsed": float(dash["elapsed"]) if dash is not None else 0.0,
        "cooldown_left": left,
        "perfect": bool(dash is not None and _perfect(state)),
    }


def _presentation(event: str, payload: dict) -> None:
    if event == "desync":
        hudfx.pip_clear()
        return
    state_payload = payload.get("state", payload)
    if not isinstance(state_payload, dict):
        return
    ctx = core.local_context()
    if event == "accept" and ctx is not None and ctx.pawn is not None:
        direction = state_payload.get("direction", [0.0, 0.0])
        if isinstance(direction, list) and len(direction) == 2:
            if screen_option.value:
                hudfx.dash_arrows(ctx.controller, (float(direction[0]), float(direction[1])))
            if audio_option.value:
                fx.play_first(ctx.controller, ctx.pawn, fx.dash_paths())
    if state_payload.get("perfect_dodge") and perfect_fx_option.value:
        hudfx.perfect_dodge()
    # Never call pip_ready() from network state digests — that flashed the hex on every
    # jump/land when double-jump snapshots changed. Local _update_pip owns the ready flash.
    if not pip_option.value:
        return
    # Joiner dashes are a local hold. Host snapshots never record that cooldown, and a
    # digest with cooldown_left 0 was clearing the hex every time it arrived.
    from .. import coop_rpc

    if ctx is not None and coop_rpc.is_requester(ctx):
        return
    cooldown_left = float(state_payload.get("cooldown_left", 0.0))
    cooldown = float(int(cooldown_slider.value))
    if state_payload.get("active"):
        hudfx.pip_progress(0.0)
    elif cooldown > 0.0 and cooldown_left > 0.0:
        hudfx.pip_progress(1.0 - cooldown_left / cooldown)
    else:
        hudfx.pip_clear()


def on_enable() -> None:
    hudfx.reset()
    hudfx.install_textures()
    _hook_dodge()
    core.register("dash", tick=_tick, cancel=_cancel, priority=10)
    authority.register_feature(
        "dash",
        authority.FeatureController(
            start=_authority_start,
            tick=_authority_tick,
            cancel=_authority_cancel,
            snapshot=_snapshot,
        ),
    )
    network.register_presentation("dash", _presentation)


# ---- dodge: less damage while dashing ----------------------------------------------------
# The player's incoming damage is caught at the game's TakeDamage, on the most specific class
# that has one (hooking several would scale the same hit more than once), and scaled down
# while a dash runs or ended less than DODGE_GRACE_S ago. Damage you deal yourself is untouched.
DODGE_GRACE_S = 0.18
DODGE_PCT = 30.0       # a missed (not perfect) dodge
_DODGE_FUNCS = ("WillowGame.WillowPlayerPawn:TakeDamage", "WillowGame.WillowPawn:TakeDamage",
                "Engine.Pawn:TakeDamage")
_DODGE_ID = "ModernMovement_DashDodge"
_dodge_hooked: str | None = None
_DODGE_DEBUG = False  # True: a console line for every reduced hit


def _dodge_active(state: DashState) -> bool:
    return state.dash is not None or (core.clock - state.last_end) < DODGE_GRACE_S


def _perfect(state: DashState) -> bool:
    """The hit lands within the perfect window from the start of the dash."""
    window = float(int(perfect_slider.value)) / 1000.0
    return (
        window > 0.0
        and state.dash is not None
        and (core.clock - state.dash.get("t0", -100.0)) < window
    )


_CPF_PARM, _CPF_RETURN = 0x80, 0x400


def _call_args(args):
    """The parameters of the hooked call, by name (not its locals or return value)."""
    out = {}
    own = args._type
    for prop in own._fields():
        try:
            if prop.Outer != own:
                continue                     # a parent version's parameters (different names)
            flags = int(prop.PropertyFlags)
        except Exception:  # noqa: BLE001
            continue
        if flags & _CPF_PARM and not flags & _CPF_RETURN:
            name = str(prop.Name)
            out[name] = getattr(args, name)
    return out


def _on_take_damage(obj, args, _ret, func):
    ctx = REGISTRY.resolve_pawn(obj)
    if ctx is None or not ctx.authority:
        return None
    state = _state(ctx)
    if state.dodge_inside:
        return None
    try:
        def apply():
            pc, pawn = ctx.controller, ctx.pawn
            if pawn is None or obj != pawn:
                return None
            core.emit("player_hit", ctx=ctx)
            if not enabled_option.value or not dodge_option.value or not _dodge_active(state):
                return None
            try:
                if args.InstigatedBy is not None and args.InstigatedBy == pc:
                    return None
            except Exception:  # noqa: BLE001
                pass
            perfect = _perfect(state)
            pct = 100.0 if perfect else DODGE_PCT
            before = float(args.Damage)
            after = before * (1.0 - pct / 100.0)
            params = _call_args(args)
            params["Damage"] = after
            state.dodge_inside = True
            try:
                if after > 0.0:
                    func(**params)
            finally:
                state.dodge_inside = False
            if _DODGE_DEBUG:
                logging.info(
                    f"[Dash] {'perfect ' if perfect else ''}dodge: "
                    f"{before:.0f} damage re-sent as {after:.0f}"
                )
            if perfect and perfect_fx_option.value:
                if ctx.presentation:
                    hudfx.perfect_dodge()
                else:
                    authority.send(
                        ctx,
                        "state",
                        {"features": {"dash": {"perfect_dodge": True}}},
                    )
            return Block

        return core.execute(ctx, apply)
    except Exception as e:  # noqa: BLE001
        logging.warning(f"[Modern Movement] Dash: dodge re-send failed, hit applied normally ({e!r})")
    return None


def _hook_dodge() -> None:
    global _dodge_hooked
    _unhook_dodge()
    import unrealsdk
    for path in _DODGE_FUNCS:
        try:
            try:   # does this class declare its own TakeDamage? (object paths use "." for functions)
                found = unrealsdk.find_object("Function", path.replace(":", "."))
            except Exception:  # noqa: BLE001
                found = None
            if found is None:
                continue
            add_hook(path, Type.PRE, _DODGE_ID, _on_take_damage)
            _dodge_hooked = path
            if _DODGE_DEBUG:
                logging.info(f"[Dash] dodge: watching {path}")
            return
        except Exception:  # noqa: BLE001
            continue
    logging.warning("[Modern Movement] Dash: no TakeDamage function found; dash damage reduction is off")


def _unhook_dodge() -> None:
    global _dodge_hooked
    if _dodge_hooked:
        try:
            remove_hook(_dodge_hooked, Type.PRE, _DODGE_ID)
        except Exception:  # noqa: BLE001
            pass
        _dodge_hooked = None


def on_disable() -> None:
    """Drop any air dash that is still running."""
    _unhook_dodge()
    for ctx in REGISTRY.contexts():
        if ctx.authority:
            _authority_cancel(ctx, "mod disabled")
    authority.unregister_feature("dash")
    network.unregister_presentation("dash")
    core.unregister("dash")


@keybind("Dash", "X")
def _dash_pressed() -> None:
    _dash_request()


# Controller dash is unbound by default: TPS D-pad Right is a native weapon-slot command.
@keybind("Dash (Controller)", None)
def _dash_pressed_pad() -> None:
    _dash_request()


def _dash_refuse(reason: str, **fields) -> None:
    try:
        from .. import diagnostics

        diagnostics.event("mm.dash.refuse", interval=1.0, reason=reason, **fields)
    except Exception:  # noqa: BLE001
        pass


def _dash_request() -> None:
    from .. import coop_rpc

    local = core.local_context()
    ctx = local or REGISTRY.resolve_controller(core.get_pc_pawn()[0])
    if ctx is None:
        _dash_refuse("no_context")
        return
    pc, pawn = ctx.controller, ctx.pawn
    if pawn is None:
        _dash_refuse("no_pawn", role=getattr(ctx.role, "value", ""))
        return
    direction = _direction_code(pc, pawn)
    # Eternal host hold + DJ local predict: same Velocity/duration on both sides.
    # Host-only was a no-op feel — 0.15s ends before autonomous-proxy replication arrives.
    if coop_rpc.is_requester(ctx):
        global _CLIENT_DASH
        if not enabled_option.value:
            _dash_refuse("disabled", role=ctx.role.value)
            return
        state = _state(ctx)
        cool = float(int(cooldown_slider.value))
        # The local dash refuses inside _dash_pressed_impl. This path skipped that,
        # so a joiner could tap dash again with no wait and no ready hex.
        if _CLIENT_DASH is not None:
            _dash_refuse("already_dashing", role=ctx.role.value)
            return
        if cool > 0.0 and core.clock - state.last_end < cool:
            _dash_refuse("cooldown", role=ctx.role.value)
            return
        phys = int(pawn.Physics)
        if phys == core.PHYS_WALKING and air_only_option.value:
            _dash_refuse("air_only", role=ctx.role.value, phys=phys)
            return
        if phys not in (core.PHYS_FALLING, core.PHYS_WALKING):
            _dash_refuse("physics", role=ctx.role.value, phys=phys)
            return
        dx, dy = _direction(pc, pawn)
        if abs(dx) + abs(dy) < 1e-3:
            dx, dy = core.facing(pc)
        speed = _SPEED
        vx, vy = float(dx) * speed, float(dy) * speed
        # Walking clamps a sideways burst to run speed. Leave the ground with the same
        # skim the local dash uses, and keep that Z in the hold. Forcing Z to 0
        # while still walking made a standing joiner dash do nothing.
        vz = _skim_speed(pc) if phys == core.PHYS_WALKING else 0.0

        def launch() -> None:
            if phys == core.PHYS_WALKING:
                _set_physics(pawn, core.PHYS_FALLING)
                core.set_velocity(pawn, vx, vy, vz)
            else:
                # Air dash keeps the fall you already have. Stamping Z to 0 each
                # tick is what made a joiner dash hitch against the host.
                core.set_velocity(pawn, vx, vy, None)

        core.execute(ctx, launch)
        _surface_burst(pc, pawn, vx, vy, phys != core.PHYS_WALKING)
        if screen_option.value:
            hudfx.dash_arrows(pc, (dx, dy))
        if audio_option.value:
            fx.play_first(pc, pawn, fx.dash_paths())
        _CLIENT_DASH = _hold_dash(pawn, vx, vy, _HOST_DASH_S, vz)
        sent = coop_rpc.call_host(coop_rpc.server_dash, vx, vy, vz)
        try:
            from .. import diagnostics

            diagnostics.event(
                "mm.dash.start",
                role=ctx.role.value,
                phys=phys,
                sent=bool(sent),
                vx=round(vx, 1),
                vy=round(vy, 1),
                vz=round(float(vz), 1),
            )
        except Exception:  # noqa: BLE001
            pass
        return
    network.send_intent("dash", "start", {"direction": direction})


OPTIONS = [
    enabled_option,
    *core.settings(
        [
            cooldown_slider,
            air_only_option,
            audio_option,
            ready_option,
            screen_option,
            pip_option,
            perfect_fx_option,
            dodge_option,
            perfect_slider,
            cam_shake_slider,
            cam_lean_slider,
            push_forward_slider,
            push_back_slider,
        ],
        "Fine-tune the dash.",
    ),
]
KEYBINDS = [_dash_pressed, _dash_pressed_pad]
# HUD PostRender hooks are registered centrally from package bootstrap, not through Dash.
HOOKS = []
