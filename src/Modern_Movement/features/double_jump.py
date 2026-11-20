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
  * Extra jumps reset every frame you are not falling (landing, mantle, ladders...).
"""

from dataclasses import dataclass

from mods_base import BoolOption, SliderOption

from .. import authority, camera, core, fx, hudfx, network
from ..protocol import Reason

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
    description="The view nods up briefly on each double jump, then eases back. Your aim moves with it and returns exactly. 0 = off.",
)

counter_option = BoolOption(
    "Jump Counter",
    False,
    "On",
    "Off",
    description="While airborne, chevrons next to the crosshair show how many extra jumps you have left.",
)

# Camera shake burst per double jump (applied by camera.py, shared with the slide and air dash).
_SHAKE_EYE = 2.0      # bob at 100%, units
_SHAKE_ROLL = 0.9     # tilt at 100%, degrees
_SHAKE_RISE = 0.04    # seconds to full strength
_SHAKE_FALL = 0.35    # seconds to settle
_SOUND = "Ake_Fs_Player.Ak_Play_Fs_Jump"

_PEAK_GRACE = 150.0  # units/s: how far past the peak (how fast you are already falling) the extra jump still works

# Coyote jump: walk / run off a ledge and press jump a moment later = your normal jump, not the double.
_COYOTE = 0.15          # seconds after leaving the ground (without jumping) a press is still a ground jump

# Directional double jump: your sideways speed bends toward the keys you hold.
_REDIRECT = 0.65        # share of the way from your sideways velocity to the held direction
_REDIRECT_MIN = 0.6     # ...aiming for at least this share of your run speed

# Camera push: a short upward nod per double jump (applied by camera.py).
_PUSH = 3.0             # degrees at 100%
_PUSH_RISE = 0.06
_PUSH_FALL = 0.30
@dataclass
class DoubleJumpState:
    shake: dict | None = None
    push: dict | None = None
    jumps_used: int = 0
    air_since: float | None = None
    last_walk: float = -100.0
    left_by_jump: bool = False
    air_epoch: int = 0
    # Host-side hold: one Velocity write loses to owner move packets (Eternal rewrites every tick).
    hold_until: float = -100.0
    hold_vel: tuple[float, float, float] | None = None
    # Per-player jump budget from the requester (not the host menu).
    max_jumps: int | None = None


_fallback_state = DoubleJumpState()
_HOLD_S = 0.12


def _state() -> DoubleJumpState:
    ctx = core.current_context()
    return ctx.state("double_jump", DoubleJumpState) if ctx is not None else _fallback_state


def _apply_impulse(pawn, vx: float, vy: float, vz: float) -> None:
    core.set_velocity(pawn, float(vx), float(vy), float(vz))


def host_apply_impulse(ctx, vx: float, vy: float, vz: float, max_jumps: int | None = None) -> None:
    """Listen-host path for a joiner's double jump (sender.Owner pawn).

    Impulse values come from the requester. Do not re-read the host menu strength slider.
    """
    if ctx.pawn is not None and core.downed(ctx.pawn):
        return
    state = _state_for(ctx)
    if max_jumps is not None:
        state.max_jumps = max(1, int(max_jumps))
    state.jumps_used = state.jumps_used + 1
    state.hold_vel = (float(vx), float(vy), float(vz))
    state.hold_until = float(ctx.clock) + _HOLD_S

    def apply() -> None:
        if ctx.pawn is None:
            return
        _apply_impulse(ctx.pawn, vx, vy, vz)

    core.execute(ctx, apply)


def _on_ground_press(pc, pawn) -> None:
    state = _state()
    state.jumps_used = 0
    state.left_by_jump = True  # this press is the game's own jump
    state.hold_vel = None
    state.hold_until = -100.0


def _on_air_press(pc, pawn) -> bool:
    """Returns True if this press was used for the extra jump."""
    from .. import coop_rpc

    state = _state()
    ctx = core.current_context() or core.local_context()
    if ctx is not None and not ctx.authority:
        return False
    if not enabled_option.value:
        return False
    if core.downed(pawn):
        return False
    try:
        vz = float(pawn.Velocity.Z)
    except Exception:  # noqa: BLE001
        return False

    # 1. Coyote jump: just walked off a ledge (not jumped): this press is your normal jump.
    if not state.left_by_jump and core.clock - state.last_walk <= _COYOTE and vz <= 0.0:
        state.left_by_jump = True  # used up: the next press is the double jump
        target = core.base_jump(pawn)
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
        # Predict locally + host hold (same values) so joiners feel the jump immediately.
        _apply_impulse(pawn, vx, vy, target)
        if coop_rpc.is_requester(ctx):
            coop_rpc.call_host(
                coop_rpc.server_double_jump,
                float(target),
                float(vx),
                float(vy),
                int(extra_jumps_slider.value),
            )
        return True

    if state.jumps_used >= int(extra_jumps_slider.value):
        return False
    if only_rising_option.value and vz <= -_PEAK_GRACE:
        return False

    # 2. Height: Strength is a share of a normal jump's HEIGHT (height grows with speed squared).
    target = core.base_jump(pawn) * (int(strength_slider.value) / 100.0) ** 0.5
    # Allow the boost whenever it would raise you; refuse only if already clearly faster.
    if vz > target + 25.0:
        return False

    state.jumps_used += 1
    # Redirect intent for host apply (compute desired XY before writing).
    try:
        ax, ay = float(pawn.Acceleration.X), float(pawn.Acceleration.Y)
        size = (ax * ax + ay * ay) ** 0.5
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
        if size > 1.0:
            dx, dy = ax / size, ay / size
            speed = max((vx * vx + vy * vy) ** 0.5, float(pawn.GroundSpeed) * _REDIRECT_MIN)
            vx = vx + (dx * speed - vx) * _REDIRECT
            vy = vy + (dy * speed - vy) * _REDIRECT
    except Exception:  # noqa: BLE001
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)

    _apply_impulse(pawn, vx, vy, target)
    try:
        from . import surfacefx

        surfacefx.burst(pc, pawn, vx, vy, 4)
    except Exception:  # noqa: BLE001
        pass
    if coop_rpc.is_requester(ctx):
        coop_rpc.call_host(
            coop_rpc.server_double_jump,
            float(target),
            float(vx),
            float(vy),
            int(extra_jumps_slider.value),
        )
    state.shake = {"t0": core.clock, "t": 0.0}
    state.push = {"t0": core.clock}
    if sound_option.value and (ctx is None or ctx.presentation):
        fx.play_first(pc, pawn, fx.jump_paths())
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
    state = _state()
    if state.push is None:
        return
    age = core.clock - state.push["t0"]
    if age >= _PUSH_RISE + _PUSH_FALL:
        state.push = None
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
    state = _state()
    if state.shake is None:
        return
    age = core.clock - state.shake["t0"]
    if age >= _SHAKE_RISE + _SHAKE_FALL:
        state.shake = None                       # done: camera.py takes the offsets out
        return
    if age < _SHAKE_RISE:
        e = age / _SHAKE_RISE
    else:
        f = (age - _SHAKE_RISE) / _SHAKE_FALL
        e = 1.0 - f * f * (3.0 - 2.0 * f)
    state.shake["t"] += dt
    amount = shake_slider.value / 100.0 * e
    if amount <= 0.0:
        return
    bob, tilt = camera.wave(state.shake["t"])
    camera.request("double_jump", eye=bob * _SHAKE_EYE * amount, roll=tilt * _SHAKE_ROLL * amount)


def _tick(pc, pawn, dt) -> None:
    state = _state()
    ctx = core.current_context()
    if ctx is not None and ctx.presentation:
        _update_shake(dt)
        _update_push()
    if core.phys == core.PHYS_WALKING:
        state.last_walk = core.clock
        state.left_by_jump = False
        state.air_since = None
    elif core.phys == core.PHYS_FALLING:
        if state.air_since is None:
            state.air_since = core.clock
    if state.jumps_used and core.phys != core.PHYS_FALLING:
        state.jumps_used = 0
        state.air_epoch += 1
    if ctx is not None and ctx.presentation:
        falling = core.phys == core.PHYS_FALLING
        airborne = falling and (
            state.jumps_used > 0
            or (state.air_since is not None and core.clock - state.air_since >= 0.15)
        )
        total = int(extra_jumps_slider.value)
        show = enabled_option.value and counter_option.value and total >= 1 and pawn is not None
        hudfx.jump_state(total - state.jumps_used, total if show else 0, show and airborne)


def _authority_input(ctx, payload):
    kind = payload.get("kind")
    pawn = ctx.pawn
    if pawn is None or core.unusable(pawn) or core.downed(pawn):
        return Reason.NO_PAWN, {}
    try:
        physics = int(pawn.Physics)
    except Exception:
        return Reason.WRONG_PHYSICS, {}
    if kind == "ground":
        core.execute(ctx, _on_ground_press, ctx.controller, pawn)
        return Reason.OK, _snapshot(ctx)
    if kind != "jump" or physics != core.PHYS_FALLING:
        return Reason.WRONG_PHYSICS, {}
    before = _state_for(ctx).jumps_used
    accepted = core.execute(ctx, _on_air_press, ctx.controller, pawn)
    if not accepted:
        return Reason.INVALID_INPUT, _snapshot(ctx)
    action_id = authority.allocate_action(ctx, "double_jump")
    response = _snapshot(ctx)
    response["action"] = action_id
    response["mode"] = "coyote" if response["jumps_used"] == before else "extra"
    authority.end_action(ctx, "double_jump", "impulse_applied")
    return Reason.OK, response


def _state_for(ctx) -> DoubleJumpState:
    return ctx.state("double_jump", DoubleJumpState)


def _authority_tick(ctx, frame) -> None:
    if ctx.local:
        return

    def remote() -> None:
        state = _state_for(ctx)
        pawn = ctx.pawn
        if pawn is not None and core.downed(pawn):
            state.hold_vel = None
            return
        if (
            pawn is not None
            and state.hold_vel is not None
            and frame.now <= state.hold_until
        ):
            _apply_impulse(pawn, *state.hold_vel)
        elif state.hold_vel is not None and frame.now > state.hold_until:
            state.hold_vel = None
        _tick(ctx.controller, pawn, frame.dt)

    core.execute(ctx, remote)


def _snapshot(ctx) -> dict:
    state = _state_for(ctx)
    total = (
        max(1, int(state.max_jumps))
        if state.max_jumps is not None
        else int(extra_jumps_slider.value)
    )
    return {
        "jumps_used": state.jumps_used,
        "jumps_total": total,
        "jumps_left": max(0, total - state.jumps_used),
        "air_epoch": state.air_epoch,
        "falling": int(getattr(ctx.pawn, "Physics", -1)) == core.PHYS_FALLING
        if ctx.pawn is not None
        else False,
    }


def _presentation(event: str, payload: dict) -> None:
    if event == "desync":
        return
    if event == "accept" and sound_option.value:
        ctx = core.local_context()
        if ctx is not None and ctx.pawn is not None:
            fx.play_all(ctx.controller, ctx.pawn, fx.jump_paths())


def on_enable() -> None:
    core.register("double_jump", tick=_tick, ground=_on_ground_press, air=_on_air_press, priority=20)
    authority.register_feature(
        "double_jump",
        authority.FeatureController(
            input=_authority_input,
            tick=_authority_tick,
            snapshot=_snapshot,
        ),
    )
    network.register_presentation("double_jump", _presentation)


def on_disable() -> None:
    authority.unregister_feature("double_jump")
    network.unregister_presentation("double_jump")
    core.unregister("double_jump")


OPTIONS = [
    enabled_option,
    *core.settings(
        [
            sound_option,
            counter_option,
            only_rising_option,
            strength_slider,
            extra_jumps_slider,
            shake_slider,
            push_slider,
        ],
        "Fine-tune how the double jump behaves.",
    ),
]
KEYBINDS = []
HOOKS = []
