"""Double Jump: press jump again in mid-air to get an extra boost.

Driven by the shared jump key in core.py (Mantle gets the first chance at every
mid-air press, so a ledge in reach is climbed instead of spending your extra jump).

  * Strength is a percentage of a normal jump's HEIGHT (from the pawn's own JumpZ, via
    core.base_jump), so it scales with jump-height buffs: 200% rises twice as high.
  * Coyote jump: walk or run off a ledge and press jump within 0.15 s: that is your normal jump,
    and the double jump is still there.
  * Directional: the sideways speed bends most of the way toward the keys you hold.
  * It never makes you slower: if you're already rising faster than the boost would
    take you, the press is not spent.
  * "Only While Rising" has a small grace past the peak so it doesn't feel stingy.
  * The counter resets every frame you are not falling (landing, mantle, ladders...).
"""

from mods_base import BoolOption, SliderOption

from .. import camera, core, fx, hudfx

enabled_option = BoolOption(
    "Double Jump Enabled",
    True,
    "On",
    "Off",
    description="Turn double jump on or off.",
)

strength_slider = SliderOption(
    "Double Jump Strength (%)",
    value=100,
    min_value=50,
    max_value=300,
    step=10,
    is_integer=True,
    description="Control the height of the additional jumps. 100 = same height as a normal jump, 200 = twice as high.",
)

extra_jumps_slider = SliderOption(
    "Extra Jumps",
    value=1,
    min_value=1,
    max_value=5,
    step=1,
    is_integer=True,
    description="How many extra jumps you get in the air before landing.",
)

only_rising_option = BoolOption(
    "Only While Rising",
    False,
    "On",
    "Off",
    description="Only allow additional jumps if you're not falling.",
)


sound_option = BoolOption(
    "Double Jump Audio Effect",
    True,
    "On",
    "Off",
    description="Adds a sound effect when double jumping.",
)

shake_slider = SliderOption(
    "Double Jump Camera Shake (%)",
    value=50,
    min_value=0,
    max_value=200,
    step=10,
    is_integer=True,
    description="A short camera bob and tilt on each double jump. Does not move your aim. 0 = off.",
)

push_slider = SliderOption(
    "Double Jump Camera Push (%)",
    value=50,
    min_value=0,
    max_value=200,
    step=10,
    is_integer=True,
    description="Temporary: the view nods up briefly on each double jump, then eases back. Your aim moves with it and returns exactly. 0 = off.",
)

counter_option = BoolOption(
    "Jump Counter",
    True,
    "On",
    "Off",
    description="While airborne, chevrons next to the crosshair show how many extra jumps you have left.",
)

# Camera shake burst per double jump (applied by camera.py, shared with the slide and air dash).
_SHAKE_EYE = 2.0      # bob at 100%, units
_SHAKE_ROLL = 0.9     # tilt at 100%, degrees
_SHAKE_RISE = 0.04    # seconds to full strength
_SHAKE_FALL = 0.35    # seconds to settle
_shake: dict | None = None   # {"t0", "t"} while a burst runs

_SOUND = "Ake_Wep_Assault_Rifles.Rifle_Torgue.Ak_Play_Wep_Rifle_Torgue_Ignite"

_PEAK_GRACE = 150.0  # units/s: how far past the peak (how fast you are already falling) the extra jump still works

_jumps_used = 0
_COUNTER_AIR_S = 0.15   # seconds of falling before the jump counter shows (ignores landing flickers)
_air_since = None       # clock time falling began (None = on the ground)

# Coyote jump: walk / run off a ledge and press jump a moment later = your normal jump, not the double.
_COYOTE = 0.15          # seconds after leaving the ground (without jumping) a press is still a ground jump
_last_walk = -100.0     # game time you were last on the ground
_left_by_jump = False   # you left the ground with a jump (so no coyote jump)

# Directional double jump: your sideways speed bends toward the keys you hold.
_REDIRECT = 0.65        # share of the way from your sideways velocity to the held direction
_REDIRECT_MIN = 0.6     # ...aiming for at least this share of your run speed

# Camera push: a short upward nod per double jump (applied by camera.py).
_PUSH = 3.0             # degrees at 100%
_PUSH_RISE = 0.06
_PUSH_FALL = 0.30
_push: dict | None = None


def _on_ground_press(pc, pawn) -> None:
    global _jumps_used, _left_by_jump
    _jumps_used = 0
    _left_by_jump = True  # this press is the game's own jump


def _on_air_press(pc, pawn) -> bool:
    """Returns True if this press was used for the extra jump."""
    global _jumps_used

    global _shake, _push, _left_by_jump
    if not enabled_option.value:
        return False
    vz = float(pawn.Velocity.Z)

    # 1. Coyote jump: just walked off a ledge (not jumped): this press is your normal jump.
    if not _left_by_jump and core.clock - _last_walk <= _COYOTE and vz <= 0.0:
        _left_by_jump = True  # used up: the next press is the double jump
        pawn.Velocity.Z = core.base_jump(pawn)
        return True

    if _jumps_used >= int(extra_jumps_slider.value):
        return False
    if only_rising_option.value and vz <= -_PEAK_GRACE:
        return False

    # 2. Height: Strength is a share of a normal jump's HEIGHT (height grows with speed squared).
    target = core.base_jump(pawn) * (int(strength_slider.value) / 100.0) ** 0.5
    if vz >= target:
        return False  # already going up faster than the boost: don't waste it

    _jumps_used += 1
    pawn.Velocity.Z = target
    _redirect(pc, pawn)
    _shake = {"t0": core.clock, "t": 0.0}
    _push = {"t0": core.clock}
    if sound_option.value:
        fx.play_sound(pc, pawn, _SOUND)
    return True


def _redirect(pc, pawn) -> None:
    """3. Directional: bend your sideways speed toward the movement keys you are holding."""
    try:
        ax, ay = float(pawn.Acceleration.X), float(pawn.Acceleration.Y)
        size = (ax * ax + ay * ay) ** 0.5
        if size <= 1.0:
            return  # no keys held: keep going the way you were
        dx, dy = ax / size, ay / size
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
        speed = max((vx * vx + vy * vy) ** 0.5, float(pawn.GroundSpeed) * _REDIRECT_MIN)
        pawn.Velocity.X = vx + (dx * speed - vx) * _REDIRECT
        pawn.Velocity.Y = vy + (dy * speed - vy) * _REDIRECT
    except Exception:  # noqa: BLE001
        pass


def _update_push() -> None:
    """4. A short upward nod per double jump. Your aim moves with it and returns exactly."""
    global _push
    if _push is None:
        return
    age = core.clock - _push["t0"]
    if age >= _PUSH_RISE + _PUSH_FALL:
        _push = None
        return
    if age < _PUSH_RISE:
        e = age / _PUSH_RISE
    else:
        f = (age - _PUSH_RISE) / _PUSH_FALL
        e = 1.0 - f * f * (3.0 - 2.0 * f)
    amount = push_slider.value / 100.0 * e
    if amount > 0.0:
        camera.request("double_jump_push", pitch=_PUSH * amount)


def _update_shake(dt) -> None:
    global _shake
    if _shake is None:
        return
    age = core.clock - _shake["t0"]
    if age >= _SHAKE_RISE + _SHAKE_FALL:
        _shake = None                       # done: camera.py takes the offsets out
        return
    if age < _SHAKE_RISE:
        e = age / _SHAKE_RISE
    else:
        f = (age - _SHAKE_RISE) / _SHAKE_FALL
        e = 1.0 - f * f * (3.0 - 2.0 * f)
    _shake["t"] += dt
    amount = shake_slider.value / 100.0 * e
    if amount <= 0.0:
        return
    bob, tilt = camera.wave(_shake["t"])
    camera.request("double_jump", eye=bob * _SHAKE_EYE * amount, roll=tilt * _SHAKE_ROLL * amount)


def _tick(pc, pawn, dt) -> None:
    global _jumps_used, _last_walk, _left_by_jump
    _update_shake(dt)
    _update_push()
    if core.phys == core.PHYS_WALKING:
        _last_walk = core.clock
        _left_by_jump = False
    if _jumps_used and core.phys != core.PHYS_FALLING:
        _jumps_used = 0
    global _air_since
    falling = core.phys == core.PHYS_FALLING
    if not falling:
        _air_since = None
    elif _air_since is None:
        _air_since = core.clock
    # The game can report "falling" for a frame or two around a landing (bumps, slopes, step-downs):
    # only count it as airborne once it has lasted a moment, or once a double jump was used.
    airborne = falling and (_jumps_used > 0 or core.clock - _air_since >= _COUNTER_AIR_S)
    total = int(extra_jumps_slider.value)
    show = enabled_option.value and counter_option.value and total >= 1 and pawn is not None
    hudfx.jump_state(total - _jumps_used, total if show else 0, show and airborne)


def on_enable() -> None:
    global _jumps_used, _shake, _push, _last_walk, _left_by_jump
    _jumps_used = 0
    _shake = None
    _push = None
    _last_walk = -100.0
    _left_by_jump = False
    core.register("double_jump", tick=_tick, ground=_on_ground_press, air=_on_air_press, priority=20)


def on_disable() -> None:
    global _jumps_used
    _jumps_used = 0
    core.unregister("double_jump")


# Double Jump Camera Shake is fixed at its tuned value (not in the menu).
# Camera Push (50) is fixed: not in the menu.
OPTIONS = [
    enabled_option,
    *core.settings(
        [sound_option, counter_option, only_rising_option, strength_slider, extra_jumps_slider],
        "Fine-tune how the double jump behaves.",
    ),
]
KEYBINDS = []
HOOKS = []
