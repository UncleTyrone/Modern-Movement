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

from mods_base import BoolOption, SliderOption, keybind

from unrealsdk import logging
from unrealsdk.hooks import Block, Type, add_hook, remove_hook

from .. import camera, core, fx, hudfx

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

_dash: dict | None = None
_exit: dict | None = None  # {"dir": (dx, dy), "until": clock} while the post-air-dash straight lock runs
_last_end = -100.0
_air_used = 0
_READY_SOUND = "Ake_UI.UI_Shields.Ak_Play_UI_Shield_Impact_The_Bee_Res"
_ready_pending = False  # a dash has finished and its "ready again" sound has not played yet


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
_cam: dict | None = None   # {"t0", "end", "side", "t"} while a dash's camera effect runs


def _cam_start(pc, dx, dy) -> None:
    global _cam
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
    _cam = {"t0": core.clock, "end": None, "side": side, "ahead": ahead, "t": 0.0}


def _cam_update(dt) -> None:
    global _cam
    c = _cam
    if c is None:
        return
    rise = min(1.0, (core.clock - c["t0"]) / _CAM_RISE)
    env = rise * rise * (3.0 - 2.0 * rise)
    if c["end"] is not None:
        f = (core.clock - c["end"]) / c.get("fall", _CAM_FALL)
        if f >= 1.0:
            _cam = None                      # done: camera.py takes the offsets out
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


def _end(pawn, reason: str, restore: bool = True, lock: bool = True) -> None:
    """Finish the air dash and hand the pre-air-dash velocity back (unless another action took over)."""
    global _dash, _last_end, _exit, _ready_pending
    if _dash is None:
        return
    d = _dash
    _dash = None
    _last_end = core.clock
    _ready_pending = int(cooldown_slider.value) > 0
    core.end("dash")
    _log(f"air dash ended ({reason}) after {d['elapsed']:.2f}s")
    core.emit("dash_end", reason=reason, air=d["air"])
    if _cam is not None and _cam["end"] is None:
        _cam["end"] = core.clock
        _cam["fall"] = _CAM_FALL if lock else _CAM_CUT  # taken over: get the camera out of the way fast
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
                _exit = {"dir": (dx, dy), "until": core.clock + _EXIT_LOCK}
        except Exception:  # noqa: BLE001
            pass


def _cancel() -> None:
    """Another movement action (the mantle) is taking over: stop at once. Your speed goes back to
    what it was before the air dash (in the dash direction), with no straight lock afterwards,
    and the dash's camera shake and lean end quickly."""
    global _exit
    _exit = None
    _end(core.get_pc_pawn()[1], "interrupted", restore=True, lock=False)


def _skim_speed(pc) -> float:
    """Upward speed for a skim that lands as a full-length dash ends (time = distance / speed)."""
    try:
        g = abs(float(pc.WorldInfo.WorldGravityZ))
    except Exception:  # noqa: BLE001
        g = 0.0
    if g < 100.0:
        g = _FALLBACK_GRAVITY
    return 0.5 * g * (_DISTANCE / _SPEED) * _SKIM_MARGIN


def _set_physics(pawn, phys: int) -> None:
    core.set_physics(pawn, phys)


def _dash_pressed_impl() -> None:
    global _dash, _air_used, _exit

    if not enabled_option.value or _dash is not None or core.busy is not None:
        return
    if core.clock - _last_end < float(int(cooldown_slider.value)):
        return

    pc, pawn = core.get_pc_pawn()
    if pawn is None or core.unusable(pawn):
        return

    # Air dashes, plus ground dashes with Ground Dash on (not while swimming, climbing, etc.).
    # On the ground or in the air (not while swimming, climbing, etc.); the cooldown is the only limit.
    phys = int(pawn.Physics)
    if phys == core.PHYS_FALLING:
        air = True
    elif phys == core.PHYS_WALKING:
        if air_only_option.value:
            return
        air = False
    else:
        return

    dx, dy = _direction(pc, pawn)
    loc = (float(pawn.Location.X), float(pawn.Location.Y))
    entry_vel = (float(pawn.Velocity.X), float(pawn.Velocity.Y))
    entry_speed = math.hypot(*entry_vel)

    _exit = None
    core.begin("dash")
    _dash = {
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
    }
    if not air:
        # A ground dash is an air dash taken just above the floor: walking caps your speed at your run
        # speed (and flying caps it too), so it starts with a tiny skim timed to land as it ends.
        _set_physics(pawn, core.PHYS_FALLING)
        try:
            pawn.Velocity.Z = _skim_speed(pc)
        except Exception:  # noqa: BLE001
            pass
    if screen_option.value:
        hudfx.dash_arrows(pc, (dx, dy))
    _cam_start(pc, dx, dy)
    if audio_option.value:
        fx.play_sound(pc, pawn)
    _log(
        f"air dash start: dir=({dx:.2f}, {dy:.2f}) distance={_dash['distance']:.0f} "
        f"speed={_dash['speed']:.0f} air={air} entry speed={entry_speed:.0f}"
    )


def _run_dash(pawn, dt: float) -> None:
    d = _dash
    if core.unusable(pawn):
        _end(pawn, "vehicle or dead", restore=False)
        return

    dx, dy = d["dir"]
    x, y = float(pawn.Location.X), float(pawn.Location.Y)

    # How far have we really gone along the air dash line?
    travelled = (x - d["start"][0]) * dx + (y - d["start"][1]) * dy
    remaining = d["distance"] - travelled

    # How much did the last tick's command actually move us? (friction / walls)
    if d["elapsed"] > 0.0 and d["commanded"] > 0.0:
        moved = (x - d["last"][0]) * dx + (y - d["last"][1]) * dy
        d["stalled"] = d["stalled"] + 1 if moved < _STALL_RATIO * d["commanded"] else 0
    d["last"] = (x, y)
    d["elapsed"] += dt

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
    pawn.Velocity.X = dx * speed - dy * fix
    pawn.Velocity.Y = dy * speed + dx * fix
    if not d["air"] and core.phys == core.PHYS_WALKING:
        # Touched the floor early (a bump, an upward slope): skim off again at full speed.
        _set_physics(pawn, core.PHYS_FALLING)
        try:
            pawn.Velocity.Z = _RESKIM
        except Exception:  # noqa: BLE001
            pass
    # Held forward / sprint input must not keep pushing us while the air dash is in charge.
    try:
        pawn.Acceleration.X = 0.0
        pawn.Acceleration.Y = 0.0
    except Exception:  # noqa: BLE001
        pass
    _log(f"t={d['elapsed']:.3f} travelled={travelled:.0f} remaining={remaining:.0f} cmd={speed:.0f}u/s")


def _run_exit_lock(pawn) -> None:
    """Briefly after an air dash: cancel sideways drift so you keep the direction you aimed."""
    global _exit
    if _exit is None:
        return
    if pawn is None or core.clock >= _exit["until"] or core.busy is not None or core.unusable(pawn):
        _exit = None
        return
    dx, dy = _exit["dir"]
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
        _exit = None


_pip_on = False   # the ready indicator is showing this cooldown


def _update_pip() -> None:
    """Feed the ready indicator: empty while dashing, filling during the cooldown, then ready."""
    global _pip_on
    if not (enabled_option.value and pip_option.value):
        if _pip_on:
            hudfx.pip_clear()
            _pip_on = False
        return
    cool = float(int(cooldown_slider.value))
    if _dash is not None:
        hudfx.pip_progress(0.0)
        _pip_on = True
    elif _pip_on:
        p = (core.clock - _last_end) / cool if cool > 0 else 1.0
        if p >= 1.0:
            hudfx.pip_ready()
            _pip_on = False
        else:
            hudfx.pip_progress(p)


def _tick(pc, pawn, dt) -> None:
    global _air_used
    global _ready_pending
    _cam_update(dt)
    if core.phys == core.PHYS_WALKING:
        _air_used = 0
    _update_pip()
    # Cooldown over: play the ready sound once.
    if _ready_pending and _dash is None and pawn is not None:
        if not (enabled_option.value and ready_option.value):
            _ready_pending = False
        elif core.clock - _last_end >= float(int(cooldown_slider.value)):
            _ready_pending = False
            fx.play_sound(pc, pawn, _READY_SOUND)
    if _dash is None:
        _run_exit_lock(pawn)
        return
    if pawn is None or not enabled_option.value:
        _end(pawn, "pawn gone or air dash disabled", restore=False)
        return
    _run_dash(pawn, dt)


def on_enable() -> None:
    global _dash, _last_end, _air_used, _exit, _ready_pending, _cam
    _cam = None
    hudfx.reset()
    hudfx.install_textures()
    _hook_dodge()
    global _pip_on
    _pip_on = False
    _ready_pending = False
    _dash = None
    _exit = None
    _last_end = -100.0
    _air_used = 0
    core.register("dash", tick=_tick, cancel=_cancel, priority=10)


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


def _dodge_active() -> bool:
    return _dash is not None or (core.clock - _last_end) < DODGE_GRACE_S


def _perfect() -> bool:
    """The hit lands within the perfect window from the start of the dash."""
    window = float(int(perfect_slider.value)) / 1000.0
    return window > 0.0 and _dash is not None and (core.clock - _dash.get("t0", -100.0)) < window


_dodge_inside = False      # True while we re-send a reduced hit (so we don't catch it again)
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
    global _dodge_inside
    if _dodge_inside:
        return None                          # the reduced hit we are sending ourselves
    try:
        pc, pawn = core.get_pc_pawn()
        if pawn is None or obj != pawn:
            return None                      # someone else being hit
        core.emit("player_hit")              # (the slide keeps going through hits)
        if not enabled_option.value or not dodge_option.value or not _dodge_active():
            return None
        try:
            if args.InstigatedBy is not None and args.InstigatedBy == pc:
                return None                  # your own damage (grenades, rockets...)
        except Exception:  # noqa: BLE001
            pass
        perfect = _perfect()
        pct = 100.0 if perfect else DODGE_PCT
        before = float(args.Damage)
        after = before * (1.0 - pct / 100.0)
        # Changing the hit in place is ignored by the game, so the original call is blocked and
        # the same hit is sent again with the reduced amount.
        params = _call_args(args)
        params["Damage"] = after
        _dodge_inside = True
        try:
            if after > 0.0:
                func(**params)               # the exact same function that was hooked
        finally:
            _dodge_inside = False
        if _DODGE_DEBUG:
            logging.info(f"[Dash] {'perfect ' if perfect else ''}dodge: {before:.0f} damage re-sent as {after:.0f}")
        if perfect:
            hudfx.perfect_dodge()
        return Block
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
    global _exit, _ready_pending
    _ready_pending = False
    try:
        _end(core.get_pc_pawn()[1], "mod disabled")
    except Exception:  # noqa: BLE001
        pass
    _exit = None
    core.unregister("dash")


@keybind("Dash", "X")
def _dash_pressed() -> None:
    _dash_pressed_impl()


OPTIONS = [
    enabled_option,
    *core.settings([cooldown_slider, air_only_option, audio_option, ready_option, screen_option, pip_option, dodge_option, perfect_slider], "Fine-tune the dash."),
    # Dash Camera Shake / Camera Lean, and the Forward / Backward Camera Push (80%), are fixed at
    # their tuned values (not in the menu).
]
KEYBINDS = [_dash_pressed]
HOOKS = list(hudfx.HOOKS)
