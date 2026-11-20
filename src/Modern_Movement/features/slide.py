"""Slide: crouch while sprinting (or land from a jump with crouch on) to slide.

How it starts
  * Press crouch while sprinting on the ground, moving at least "Min Slide Speed".
  * Press crouch in the air no more than "Slide Landing Window (ms)" before touching down, then
    land with crouch on while moving forward at least "Min Slide Speed" ("Slide From Landing").

How it moves
  The slide starts at the speed you had going in plus "Slide Boost (%)" (capped at "Max Slide
  Speed"), so the more momentum you bring, the further you go. Flat ground bleeds speed quickly
  ("Slide Friction"); hills stretch or cut it ("Slope Effect (%)": downhill lasts longer, uphill
  ends sooner). The direction is the one you entered with; the movement keys can turn it a little
  ("Slide Steering", degrees per second), never sideways at will.

  The game would normally hold a crouching character to crouch-walking speed, so while the
  slide runs its crouch speed limit (CrouchedPct) is raised to the slide's speed, and put back
  afterwards. The pawn's horizontal velocity is set every tick (like the air dash); vertical
  velocity is never touched.

Momentum carry: ending a slide by standing up or jumping keeps its speed. Your top speed starts
at the slide's speed and eases back to normal over "Slide Momentum Carry (ms)", so sprinting or
jumping out carries the boost (and landing from the jump while it lasts keeps it on the ground).
Coming to a stop on the ground cancels the carry straight away.

How it ends
  * You slow to crouch-walking speed: you stay crouched.
  * You stand up (toggle crouch off): you stand and walk on.
  * You jump (at any point): you stand up and launch with the slide's current speed and
    direction ("Slide Jump Momentum (%)") and your normal jump height ("Slide Jump Height (%)").
    The mod's jump key handles this before the game would turn the press into "stand up".
  * You press back (move backward, "Back Cancels Slide"): you stay crouched.
  * You hit a wall or something stops you, or you leave the ground.

Speeds are in Unreal units per second; "walking speed" is the pawn's own GroundSpeed.
"""

import math
from dataclasses import dataclass, field

from mods_base import BoolOption, SliderOption, hook
from unrealsdk import logging
from unrealsdk.hooks import Block, Type

from .. import authority, camera, core, fx, hudfx, network, tracing
from ..protocol import Reason
from ..runtime import ExecutionRole, REGISTRY

enabled_option = BoolOption("Slide Enabled", True, "On", "Off", description="Turn slide on or off.")

boost_slider = SliderOption(
    "Slide Boost (%)", value=55, min_value=0, max_value=100, step=5, is_integer=True,
    description="Extra speed added on top of entry momentum when a slide starts.",
)
friction_slider = SliderOption(
    "Slide Friction", value=480, min_value=100, max_value=3000, step=50, is_integer=True,
    description="How quickly a slide loses speed on flat ground (units/s²). Higher = shorter flat slides.",
)
slope_slider = SliderOption(
    "Slope Effect (%)", value=250, min_value=0, max_value=400, step=10, is_integer=True,
    description="Hills vs flat: downhill stretches a slide, uphill cuts it short. 0 = flat everywhere.",
)
steer_slider = SliderOption(
    "Slide Steering", value=45, min_value=0, max_value=180, step=5, is_integer=True,
    description="How fast the movement keys can turn a slide, in degrees per second. 0 = straight line.",
)
min_speed_slider = SliderOption(
    "Min Slide Speed (%)", value=110, min_value=50, max_value=250, step=5, is_integer=True,
    description="How fast you must be going to slide, as a percentage of walking speed.",
)
max_speed_slider = SliderOption(
    "Max Slide Speed (%)", value=340, min_value=100, max_value=500, step=10, is_integer=True,
    description="The fastest a slide can start, as a percentage of walking speed.",
)
landing_option = BoolOption(
    "Slide From Landing", False, "On", "Off",
    description="Landing with crouch on while moving forward fast enough starts a slide.",
)
landing_window_slider = SliderOption(
    "Slide Landing Window (ms)", value=700, min_value=0, max_value=1500, step=50, is_integer=True,
    description="With Slide From Landing: how long before touching down you can press crouch and "
                "still slide on landing.",
)
sprint_req_slider = SliderOption(
    "Sprint Before Next Slide (ms)", value=200, min_value=0, max_value=3000, step=50, is_integer=True,
    description="Not used. The next slide can start as soon as the last one ends.",
)
back_cancel_option = BoolOption(
    "Back Cancels Slide", True, "On", "Off",
    description="Pressing back (move backward) during a slide stops it; you stay crouched.",
)
jump_momentum_slider = SliderOption(
    "Slide Jump Momentum (%)", value=100, min_value=0, max_value=200, step=5, is_integer=True,
    description="How much of the slide's speed a jump out of it keeps. 100 = all of it.",
)
jump_height_slider = SliderOption(
    "Slide Jump Height (%)", value=125, min_value=25, max_value=200, step=5, is_integer=True,
    description="Height of a jump out of a slide, compared with a normal jump.",
)
carry_slider = SliderOption(
    "Slide Momentum Carry (ms)", value=1000, min_value=0, max_value=5000, step=100, is_integer=True,
    description="After a slide ends by standing up or jumping, your top speed starts at the slide's "
                "speed and eases back to normal over this long (sprint or jump out to keep it). Stopping "
                "cancels it. 0 = off.",
)
push_slider = SliderOption(
    "Slide Camera Push (%)", value=90, min_value=0, max_value=200, step=10, is_integer=True,
    description="The view tilts back while you slide, more the faster you go, and eases level as the slide slows. Your aim moves with it and returns exactly. 0 = off.",
)

shake_slider = SliderOption(
    "Slide Camera Shake (%)", value=45, min_value=0, max_value=200, step=10, is_integer=True,
    description="A light camera bob and tilt while sliding, strongest at the start and fading as you "
                "slow down. Does not move your aim. 0 = off.",
)
distance_slider = SliderOption(
    "Slide Distance (%)", value=90, min_value=50, max_value=140, step=5, is_integer=True,
    description="Fine trim for slide length. Higher = longer coast on flat ground.",
)
speed_slider = SliderOption(
    "Slide Speed (%)", value=120, min_value=70, max_value=180, step=5, is_integer=True,
    description="How fast the slide moves. 100 is the original coast. Distance still sets how long it lasts.",
)
indicator_option = BoolOption(
    "Slide Indicator", True, "On", "Off",
    description="A bar below the crosshair shows how much momentum your slide has left to carry into a slide jump.",
)
audio_option = BoolOption(
    "Slide Audio Effect", True, "On", "Off",
    description="Footsteps on the ground for as long as the slide lasts.",
)

scrape_variant_slider = SliderOption(
    "Slide Sound Variant", value=1, min_value=1, max_value=12, step=1, is_integer=True,
    description="Which footstep sound the slide scrape is made from. The console lists them the first time you slide.",
)

scrape_rate_slider = SliderOption(
    "Slide Sound Rate (%)", value=70, min_value=25, max_value=300, step=5, is_integer=True,
    description="How fast the scrape's steps repeat (they start fast and slow down with the slide). Higher = faster.",
)

# A slide repeats a real footstep for the whole slide. There is no whoosh.
# Those events are in both games' always-loaded player banks.

_DEBUG = False

_FALLBACK_GRAVITY = 1000.0   # units/s^2 along a slope at 100% if the world's gravity can't be read
_FORWARD_DOT = 0.5           # landing slide: moving at least this much along where you look
_STALL_TICKS = 3
_STALL_RATIO = 0.10
# About three quarters of the previous coast. Speed falls on that shorter clock,
# so the slide slows earlier instead of holding full speed until a late stop.
_LENGTH = 0.75
_MAX_FLAT_S = 1.75 * _LENGTH
_MAX_DOWNHILL_S = 3.15 * _LENGTH
_FLAT_SLOPE_EPS = 0.08       # |floor·dir| below this counts as flat for the time cap
_MIN_FLAT_DRAG = 320.0       # floor on flat bleed (saved ultra-low friction can't make endless slides)

_JUMP_GRACE = 0.2           # seconds: a jump this soon after the slide ended still launches it
_HIT_GRACE = 0.4            # seconds after you're hit that a hit's push or flinch can't end the slide
def _on_player_hit(**_kw) -> None:
    _state().hit_at = core.clock


_FLOOR_NEAR = 60.0          # units: a floor this close below still counts as "on the ground" after a hit


def _falling_is_crouch_dip(vz: float, floor: bool) -> bool:
    """A crouch shrinks the capsule and reports falling for a frame. A jump climbs. A cliff has no floor."""
    return bool(floor) and float(vz) < 250.0


def _floor_below(pawn) -> bool:
    """A floor just under your feet (one short trace down)."""
    try:
        x, y, z = core.position(pawn)
        _radius, half = tracing.body(pawn)
        feet = z - half
        with tracing.session(pawn, 3):
            return tracing.trace(pawn, (x, y, feet - 2.0), (x, y, feet - 2.0 - _FLOOR_NEAR)) is not None
    except Exception:  # noqa: BLE001
        return False


def _hit_recently() -> bool:
    return 0.0 <= core.clock - _state().hit_at < _HIT_GRACE


@dataclass
class SlideCrouchLease:
    """Generation-bound crouch ownership for Slide so native Slam is not left armed."""

    pawn_generation: int = -1
    duck_before: bool = False
    owned: bool = False


@dataclass
class SlideState:
    slide: dict | None = None
    last_end: float = -100.0
    need_sprint: bool = False
    sprint_run: float = 0.0
    slide_queued: bool = False
    ended: dict | None = None
    prev_crouch: bool = False
    prev_sprint: bool = False
    prev_phys: int = -1
    prev_speed: float = 0.0
    crouch_pressed_at: float = -100.0
    crouch_pressed_while_airborne: bool = False
    cp_base: float | None = None
    cp_written: float | None = None
    icon_alpha: float | None = None
    icon_hold: tuple[float, float] = (-100.0, -100.0)
    carry: dict | None = None
    launch: dict | None = None
    shake_t: float = 0.0
    push_want: float = 0.0
    push_level: float = 0.0
    scrape_next: float = 0.0
    hit_at: float = -100.0
    crouch_owned: bool = False
    suppress_crouch_until_release: bool = False
    # Slide jump while crouch is held: land in another slide instead of a slam.
    # chain_hold follows the crouch press, not the crouched pose. The pose stays
    # down because the slide forces it. crouch_down is set on the press and cleared
    # on DuckReleased. An unreadable key list must not cancel a hold or invent one.
    chain: dict | None = None
    chain_hold: bool = False
    chain_was_air: bool = False
    crouch_down: bool = False
    ignore_release_until: float = -100.0
    slide_jump: dict | None = None
    # Set only by a crouch press while already in the air. A hold carried out of
    # a slide does not count, or every cliff and landing starts another slide.
    air_pressed: bool = False
    # Horizontal speed saved when a real in-air crouch starts a slam.
    slam_bank: tuple[float, float] | None = None
    # Fastest horizontal speed while crouch is held in the air with no slide
    # before it. A sprint jump uses this to slide on landing.
    air_slide: dict | None = None
    # The crouch that started a slam. It stays blocked until the key comes up,
    # so the landing does not turn into a slide.
    slam_hold: bool = False
    crouch_lease: SlideCrouchLease = field(default_factory=SlideCrouchLease)
    action_id: int = 0
    # First-person arms pose only (juso-style). Never offset Mesh.Translation — that fights the
    # anim tree and makes other players' bodies freak out until the engine resets.
    arms: dict | None = None


_fallback_state = SlideState()


def _state(ctx=None) -> SlideState:
    ctx = ctx or core.current_context()
    return ctx.state("slide", SlideState) if ctx is not None else _fallback_state


def _log(msg: str) -> None:
    """Debug output (py ...slide._DEBUG = True in the console to see it)."""
    if _DEBUG:
        print(f"[Slide] {msg}")


_warned: set = set()


def _warn(msg: str) -> None:
    if msg not in _warned:
        _warned.add(msg)
        print(f"[Modern Movement] [Slide] {msg}")


def _flag(obj, name) -> bool:
    try:
        return bool(getattr(obj, name))
    except Exception:  # noqa: BLE001
        return False


def _bl2_key_up(state, pc) -> bool:
    """The crouch key came up. Both games use this, not the crouched pose.

    PressedKeys omits a held crouch, and that read is None rather than a release.
    The input hook or the keyboard saying up ends the slide and drops a landing chain.
    """
    if core.clock < state.ignore_release_until:
        return False
    return _crouch_held(pc) is False


def _crouch_blip_on_ground(state, pawn, phys: int) -> bool:
    """The crouch frame where the capsule dips and the pawn reports falling.

    They are still on the ground. Starting the slide here is what keeps that
    frame from becoming a slam.
    """
    if phys != core.PHYS_FALLING or state.prev_phys != core.PHYS_WALKING or state.slide is not None:
        return False
    try:
        return abs(float(pawn.Velocity.Z)) < 180.0
    except Exception:  # noqa: BLE001
        return False


def _bl2_slide_ready(state, pawn, sprint, speed: float) -> bool:
    """True once a Borderlands 2 sprint has started. Do not wait out a sprint-sized GroundSpeed."""
    if sprint or state.prev_sprint:
        return True
    walk = min(_walk_speed(pawn), 480.0)
    need = walk * float(min_speed_slider.value) / 100.0
    return max(speed, state.prev_speed) >= need


def _crouch_held(pc):
    """True while the crouch key is down, False if it is up, None if it cannot be read.

    The Pre-Sequel turns a crouch press in the air into an Oz slam. Borderlands 2's
    custom slam does the same after a slide jump. A key that never came up is the
    slide key still held, not a new slam press.
    """
    try:
        from . import slam

        return slam._crouch_key_down(pc)
    except Exception:  # noqa: BLE001
        return None


def _crouching(pc, pawn) -> bool:
    """Crouch is on: the pawn wants to / is crouched, or the controller's crouch input (bDuck,
    which toggle crouch flips) is set."""
    return _flag(pawn, "bWantsToCrouch") or _flag(pawn, "bIsCrouched") or _flag(pc, "bDuck")


def _walk_speed(pawn) -> float:
    """Walking speed without any of this mod's boosts (Sprint Surge, momentum carry)."""
    return max(1.0, core.ground_speed_base(pawn))


def _gravity(pc) -> float:
    try:
        g = abs(float(pc.WorldInfo.WorldGravityZ))
        if g > 0.0:
            return g
    except Exception:  # noqa: BLE001
        pass
    return _FALLBACK_GRAVITY


# ---- crouch speed limit ------------------------------------------------------------------


def _require_authority(operation: str) -> None:
    ctx = core.current_context()
    if ctx is None:
        raise PermissionError(f"{operation} requires an active player context")
    ctx.require_authority(operation)


def _set_crouch_limit(pawn, speed) -> None:
    """Raise the crouch speed limit so the game lets the slide go `speed` (None = restore)."""
    _require_authority("CrouchedPct write")
    state = _state()
    try:
        current = float(pawn.CrouchedPct)
    except Exception:  # noqa: BLE001
        return
    if speed is None:
        if state.cp_written is not None and abs(current - state.cp_written) < 1e-4:
            pawn.CrouchedPct = state.cp_base
        state.cp_base = state.cp_written = None
        return
    if state.cp_written is None or abs(current - state.cp_written) > 1e-4:
        state.cp_base = current
    # The cap is the coast. A few percent of headroom is room the engine
    # accelerates into, and the next tick snaps it back (the slide stutter).
    target = max(float(state.cp_base), speed / _walk_speed(pawn))
    if abs(current - target) > 1e-4:
        pawn.CrouchedPct = target
    state.cp_written = target


# juso sliding: CrouchedPct decays from ~2.25 back to 0.5 and times the slide.
# CrouchedPct only raises the engine crouch-speed cap. With no movement input the
# pawn brakes to a stop, so a network slide also re-applies the entry direction
# every tick (same coast as the local slide). Decay is scaled so the coast
# lasts about three quarters as long and speed drops on that same clock.
_JUSO_SLIDE_PCT = 2.25
_JUSO_CROUCH_PCT = 0.5
_JUSO_DECAY = 1.25 / _LENGTH  # CrouchedPct / s on flat
_ENTRY_KEEP = 1.0  # keep full sprint speed into the slide

_JUSO_DOWNHILL = 0.0012  # CrouchedPct gain per unit dropped
_JUSO_UPHILL = 0.005  # extra loss per unit climbed
_HOST_SLIDES: dict[int, dict] = {}
# Slide-jump launches. One write loses to the server move, same as a double jump.
_HOST_JUMPS: dict[int, dict] = {}


def _decay_juso_pct(cp: float, z_diff: float, dt: float, drop_run: float = 0.0) -> float:
    """Drain on a clock. A real climb shortens it. A sustained drop slows the drain.

    One noisy Z sample must not add CrouchedPct back. `drop_run` is how long the
    body has actually been descending (ramps and stairs), and it only changes the
    rate. The meter still falls.
    """
    loss = dt * _JUSO_DECAY
    if z_diff > 12.0:
        loss += z_diff * _JUSO_UPHILL
    elif drop_run > 0.12:
        # The longer hill has to stay a slide. 0.40 still bled the coast down to a crouch walk.
        loss *= 0.12
    elif drop_run < -0.12:
        loss *= 1.35
    return cp - loss


def _track_drop(store: dict, z_diff: float, dt: float) -> float:
    """Build up while Z keeps falling (a ramp or a run of stairs). One spike fades."""
    run = float(store.get("drop_run", 0.0))
    if z_diff <= -3.0:
        run = min(0.60, run + dt + min(0.08, (-float(z_diff) - 3.0) / 250.0))
    elif z_diff >= 8.0:
        run = max(-0.60, run - dt)
    else:
        run *= max(0.0, 1.0 - dt * 2.5)
    store["drop_run"] = run
    return run


def _vertical_slope(pc, drop_run: float) -> float:
    """Positive when a sustained drop should stretch the slide. Independent of Floor."""
    if not slope_slider.value or abs(drop_run) < 0.12:
        return 0.0
    share = min(abs(drop_run) / 0.45, 1.0) * 0.45
    signed = share if drop_run > 0.0 else -share
    return _gravity(pc) * signed * float(slope_slider.value) / 100.0


def _slope_along(pc, pawn, dx: float, dy: float) -> float:
    """Positive = sliding downhill along dir; ~0 on flat."""
    if not slope_slider.value:
        return 0.0
    try:
        n = pawn.Floor
        return _gravity(pc) * (float(n.X) * dx + float(n.Y) * dy) * slope_slider.value / 100.0
    except Exception:  # noqa: BLE001
        return 0.0


def _slide_time_cap(slope_along: float) -> float:
    if slope_along > _FLAT_SLOPE_EPS * _FALLBACK_GRAVITY * max(slope_slider.value, 1) / 100.0:
        return _MAX_DOWNHILL_S
    return _MAX_FLAT_S


def _slide_fill(elapsed: float, cap: float, speed: float, start: float, floor: float) -> float:
    """1 at the start of a slide, 0 when the slide is out of time or out of speed.

    Speed stays high for most of the coast, so a bar drawn from speed sits in
    one place and the slide ends while the line is still long. The time cap is
    what ends the slide, and the line follows that.
    """
    by_time = 1.0 - min(1.0, max(0.0, float(elapsed)) / max(0.05, float(cap)))
    span = max(1.0, float(start) - float(floor))
    by_speed = max(0.0, min(1.0, (float(speed) - float(floor)) / span))
    return max(0.0, min(1.0, by_time, by_speed))


def note_slam_hold() -> None:
    """The crouch that started a slam does not also start a slide."""
    _state().slam_hold = True


def _slam_hold_blocks(state, held) -> bool:
    """True until that slam crouch is released. A key-up clears it."""
    if held is False:
        state.slam_hold = False
        return False
    return bool(state.slam_hold)


def _slam_diving() -> bool:
    """True while a Borderlands 2 slam is still coming down. Slide must not take the landing."""
    try:
        from . import slam

        return slam._slam is not None
    except Exception:  # noqa: BLE001
        return False


def _distance_scale(distance_percent: float) -> float:
    """Map Slide Distance (%) onto timed/juso length (0.5x .. 1.4x)."""
    return max(0.5, min(1.4, float(distance_percent) / 100.0))


def _speed_scale(speed_percent: float) -> float:
    """Map Slide Speed (%) onto coast speed. 100 = original. Independent of distance."""
    return max(0.7, min(1.8, float(speed_percent) / 100.0))


def _coast_velocity(cp: float, walk: float, speed_percent: float) -> float:
    return float(cp) * float(walk) * _speed_scale(speed_percent)


def release_player(player_id: int | None) -> None:
    """Drop host slide holds. None clears every joiner (level change)."""
    if player_id is None:
        _HOST_SLIDES.clear()
        _HOST_JUMPS.clear()
        return
    _HOST_SLIDES.pop(int(player_id), None)
    _HOST_JUMPS.pop(int(player_id), None)


def _unit_dir(dx: float, dy: float) -> tuple[float, float]:
    mag = math.hypot(dx, dy)
    if mag < 1e-3:
        return 0.0, 0.0
    return dx / mag, dy / mag


# Non-zero so walking physics does not treat the coast as "no input" and brake.
# AccelRate itself (often 2048) makes that same step lunge, then the next coast
# snaps the speed back. That snap is the slide stutter.
_COAST_PUSH = 96.0


def _coast_slide(pawn, dx: float, dy: float, speed: float) -> None:
    """Keep sliding after movement keys are released.

    Walking physics brakes when Acceleration is zero. A small push keeps the
    coast without lunging past the speed we just wrote.
    """
    if pawn is None or speed <= 1.0:
        return
    dx, dy = _unit_dir(dx, dy)
    if dx == 0.0 and dy == 0.0:
        return
    core.set_velocity(pawn, dx * speed, dy * speed)
    try:
        pawn.Acceleration.X = dx * _COAST_PUSH
        pawn.Acceleration.Y = dy * _COAST_PUSH
    except Exception:  # noqa: BLE001
        pass


def host_enter_juso(
    ctx,
    crouched_pct: float,
    distance_percent: float = 80.0,
    dir_x: float = 0.0,
    dir_y: float = 0.0,
    speed_percent: float = 100.0,
) -> None:
    """Listen-host: raise CrouchedPct and remember the joiner's entry direction."""
    if ctx.pawn is None:
        return
    pct = max(_JUSO_CROUCH_PCT, float(crouched_pct))
    dx, dy = _unit_dir(dir_x, dir_y)
    if dx == 0.0 and dy == 0.0:
        try:
            dx, dy = _unit_dir(float(ctx.pawn.Velocity.X), float(ctx.pawn.Velocity.Y))
        except Exception:  # noqa: BLE001
            dx, dy = 0.0, 0.0
    _HOST_JUMPS.pop(ctx.key.player_id, None)
    _HOST_SLIDES[ctx.key.player_id] = {
        "pawn": ctx.pawn,
        "cp": pct,
        "old_z": None,
        "elapsed": 0.0,
        "distance": float(distance_percent),
        "speed_percent": float(speed_percent),
        "dir": (dx, dy),
    }

    def apply() -> None:
        try:
            _HOST_SLIDES[ctx.key.player_id]["old_z"] = float(ctx.pawn.Location.Z)
        except Exception:  # noqa: BLE001
            _HOST_SLIDES[ctx.key.player_id]["old_z"] = 0.0
        ctx.pawn.CrouchedPct = pct
        try:
            ctx.pawn.ShouldCrouch(True)
        except Exception:  # noqa: BLE001
            pass

    core.execute(ctx, apply)


def _stand_host_pawn(ctx) -> None:
    """Drop the server crouch latch. Does not touch a slide-jump hold."""
    if ctx.pawn is None and ctx.controller is None:
        return

    def apply() -> None:
        if ctx.pawn is not None:
            try:
                ctx.pawn.CrouchedPct = _JUSO_CROUCH_PCT
            except Exception:  # noqa: BLE001
                pass
            try:
                ctx.pawn.ShouldCrouch(False)
            except Exception:  # noqa: BLE001
                pass
        try:
            if ctx.controller is not None:
                ctx.controller.bDuck = 0
        except Exception:  # noqa: BLE001
            pass

    core.execute(ctx, apply)


def host_exit_juso(ctx) -> None:
    """Listen-host: juso server_exit_slide — restore CrouchedPct."""
    _HOST_SLIDES.pop(ctx.key.player_id, None)
    # A slide jump sends exit, then the launch. A second exit must not plant them
    # while that launch is still being held, or the landing slide never sticks.
    if ctx.key.player_id in _HOST_JUMPS:
        return
    _stand_host_pawn(ctx)


def _push_slide_jump(pawn, vx: float, vy: float, vz: float, *, force_z: bool) -> None:
    """Write the slide-jump launch. A rising pawn keeps its Z so gravity can work."""
    try:
        if int(pawn.Physics) == core.PHYS_WALKING:
            pawn.Physics = core.PHYS_FALLING
    except Exception:  # noqa: BLE001
        pass
    rising = False
    if not force_z:
        try:
            rising = int(pawn.Physics) == core.PHYS_FALLING and float(pawn.Velocity.Z) > 0.0
        except Exception:  # noqa: BLE001
            rising = False
    core.set_velocity(pawn, float(vx), float(vy), None if rising else float(vz))


def host_apply_slide_jump(ctx, vx: float, vy: float, vz: float) -> None:
    """Listen-host: stop the slide coast and hold the joiner's launch."""
    if ctx.pawn is None:
        return
    _HOST_SLIDES.pop(ctx.key.player_id, None)
    _HOST_JUMPS[ctx.key.player_id] = {
        "pawn": ctx.pawn,
        "vx": float(vx),
        "vy": float(vy),
        "vz": float(vz),
        "left": _LAUNCH_HOLD,
    }
    _stand_host_pawn(ctx)

    def apply() -> None:
        if ctx.pawn is None:
            return
        _push_slide_jump(ctx.pawn, vx, vy, vz, force_z=True)

    core.execute(ctx, apply)


def _service_host_jumps(dt: float) -> None:
    """Re-apply a joiner slide jump until the launch has stuck."""
    if not _HOST_JUMPS:
        return
    done: list[int] = []
    for pid, d in _HOST_JUMPS.items():
        d["left"] = float(d["left"]) - dt
        pawn = d["pawn"]
        try:
            if d["left"] <= 0.0 or pawn is None:
                done.append(pid)
                continue
            _push_slide_jump(pawn, d["vx"], d["vy"], d["vz"], force_z=False)
        except Exception:  # noqa: BLE001
            done.append(pid)
    for pid in done:
        _HOST_JUMPS.pop(pid, None)


def _service_host_slides(dt: float) -> None:
    """juso host PlayerMove loop: decay CrouchedPct for every sliding joiner."""
    if not _HOST_SLIDES:
        return
    done: list[int] = []
    for pid, d in _HOST_SLIDES.items():
        pawn = d["pawn"]
        try:
            z = float(pawn.Location.Z)
            old_z = d["old_z"]
            if old_z is None:
                old_z = z
            z_diff = z - float(old_z)
            d["elapsed"] = float(d.get("elapsed", 0.0)) + dt
            scale = _distance_scale(float(d.get("distance", 80.0)))
            drop_run = _track_drop(d, z_diff, dt)
            if not slope_slider.value:
                drop_run = 0.0
            cp = _decay_juso_pct(float(d["cp"]), z_diff, dt / scale, drop_run)
            d["old_z"] = z
            d["cp"] = cp
            speed_percent = float(d.get("speed_percent", 100.0))
            pawn.CrouchedPct = cp * _speed_scale(speed_percent)
            # TP look = engine crouch locomotion (juso never offsets Mesh). Keep it latched.
            try:
                pawn.ShouldCrouch(True)
            except Exception:  # noqa: BLE001
                pass
            # A sustained ramp or stair run uses the long cap. One Z spike does not.
            cap = (_MAX_DOWNHILL_S if drop_run > 0.12 else _MAX_FLAT_S) * scale
            if cp < _JUSO_CROUCH_PCT or d["elapsed"] > cap:
                pawn.CrouchedPct = _JUSO_CROUCH_PCT
                done.append(pid)
            else:
                # Same coast as the local slide: no movement keys must not brake them.
                dx, dy = d.get("dir", (0.0, 0.0))
                _coast_slide(pawn, dx, dy, _coast_velocity(cp, _walk_speed(pawn), speed_percent))
        except Exception:  # noqa: BLE001
            done.append(pid)
    for pid in done:
        _HOST_SLIDES.pop(pid, None)


def _crouch_walk_speed(pawn) -> float:
    base = _state().cp_base
    if base is None:
        try:
            base = float(pawn.CrouchedPct)
        except Exception:  # noqa: BLE001
            base = 0.4
    return _walk_speed(pawn) * base


# ---- crouch icon ------------------------------------------------------------------------
# The HUD's crouch indicator is hidden while a slide runs (a slide is not "crouching"), and
# while crouch is on in the air (so jumping into a landing slide never shows it); it is shown
# again otherwise. Only its opacity is changed, so the game keeps deciding when the
# icon is there at all.
CROUCH_ICON = "_root.p1.crouch"


def _hide_crouch_icon(pc) -> None:
    state = _state()
    if pc is None:
        return
    if state.icon_alpha is None:
        a = fx.clip_alpha(pc, CROUCH_ICON)
        state.icon_alpha = a if a is not None and a > 0.0 else 100.0
    fx.set_clip_alpha(pc, CROUCH_ICON, 0.0)       # every slide tick (the HUD rebuilds after menus)


_ICON_HOLD_S = 2.0          # the crouch icon stays hidden this long after a slide or a slam...
_ICON_IGNORE_S = 0.3        # ...unless crouch is pressed again in it (after this much)
def _hold_crouch_icon(**_kw) -> None:
    _state().icon_hold = (core.clock, core.clock + _ICON_HOLD_S)


def _icon_held() -> bool:
    state = _state()
    start, until = state.icon_hold
    # (a crouch flicker in the first moments, as the slam stands you up, is not a press)
    return core.clock < until and state.crouch_pressed_at <= start + _ICON_IGNORE_S


def _show_crouch_icon(pc) -> None:
    state = _state()
    if state.icon_alpha is None:
        return
    if pc is not None:
        fx.set_clip_alpha(pc, CROUCH_ICON, state.icon_alpha)
    state.icon_alpha = None


# ---- start / end -------------------------------------------------------------------------


def _slide_fresh(slide) -> bool:
    """True for a moment after a landing slide. The old momentum must not cancel it."""
    if not slide:
        return False
    try:
        return core.clock < float(slide.get("fresh_until", -100.0))
    except Exception:  # noqa: BLE001
        return False


def _sprint_press_is_cancel(slide, prev_sprint: bool, key_down: bool | None = None) -> bool:
    """A new sprint press ends the slide. The sprint already held at the start does not.

    BeginSprint repeats while that sprint stays on. Once the key has come up, the next press
    (the key is down again) ends the slide. A repeat while the key is up does not, so the
    leftover time is not a wait and a held sprint does not eat the slide.
    """
    if not slide or _slide_fresh(slide):
        return False
    if not prev_sprint:
        return True
    return bool(slide.get("sprint_released")) and key_down is True


_sprint_names: tuple = ()
_sprint_names_at = -100.0


def _sprint_key_names(pc) -> tuple:
    """Keys bound to sprint. Left Shift is the Borderlands 2 default when the list is empty."""
    global _sprint_names, _sprint_names_at
    if _sprint_names and 0.0 <= core.clock - _sprint_names_at < 5.0:
        return _sprint_names
    found: list[str] = []
    try:
        from . import slam

        for binding in pc.PlayerInput.Bindings:
            try:
                name = slam._key_token(binding.Name)
                command = str(binding.Command).lower()
            except Exception:  # noqa: BLE001
                continue
            if "sprint" in command and not name.startswith("gba_"):
                found.append(name)
    except Exception:  # noqa: BLE001
        found = []
    _sprint_names = tuple(found) if found else ("leftshift",)
    _sprint_names_at = core.clock
    return _sprint_names


def _note_sprint_release(state, pc) -> None:
    """Remember that the sprint key came up, so the next press can end the slide."""
    slide = state.slide
    if slide is None or slide.get("sprint_released"):
        return
    down = None
    try:
        from .. import input_state

        down = input_state.willow_held(_sprint_key_names(pc))
    except Exception:  # noqa: BLE001
        down = None
    if down is None:
        try:
            from . import slam

            down = slam._physical_down(_sprint_key_names(pc))
        except Exception:  # noqa: BLE001
            return
    if down is False:
        slide["sprint_released"] = True


def _start(
    pc,
    pawn,
    reason: str,
    face_x: float | None = None,
    face_y: float | None = None,
    carry: float | None = None,
) -> None:
    _require_authority("slide start")
    state = _state()
    if state.slide is not None:
        return
    ctx = core.current_context()
    try:
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
    except Exception:  # noqa: BLE001
        vx, vy = 0.0, 0.0
    speed = math.hypot(vx, vy)
    # A landing slide aims where the player is looking. Velocity is still the
    # previous slide, and reading it back after a write often still is.
    forced = False
    if face_x is not None and face_y is not None:
        fdx, fdy = _unit_dir(float(face_x), float(face_y))
        if fdx != 0.0 or fdy != 0.0:
            vx, vy = fdx, fdy
            forced = True
            if carry is not None:
                speed = max(speed, float(carry))
    if speed < 1.0:
        return
    walk = _walk_speed(pawn)
    # Keep most sprint speed, modest boost, capped — a slide coast, not a lunge or a sprint burst.
    start_speed = min(
        speed * _ENTRY_KEEP * (1.0 + boost_slider.value / 100.0),
        walk * max_speed_slider.value / 100.0,
    )
    start_speed = max(start_speed, walk * min_speed_slider.value / 100.0)
    speed_percent = float(speed_slider.value)
    start_speed *= _speed_scale(speed_percent)

    core.begin("slide", ctx=ctx)
    loc = (float(pawn.Location.X), float(pawn.Location.Y))
    _stop_carry()                                # a new slide replaces any carry still running
    state.crouch_down = True
    # Both games end the slide when the crouch key comes up. A longer Pre-Sequel
    # window kept the slide going after a let-go and forced the landing slide.
    state.ignore_release_until = core.clock + 0.05
    dir_x, dir_y = (vx, vy) if forced else (vx / speed, vy / speed)
    state.slide = {
        "dir": (dir_x, dir_y),
        "fresh_until": core.clock + _LAND_GRACE,
        "stick": forced,
        "speed": start_speed,
        "start": start_speed,
        "entry": speed,
        "elapsed": 0.0,
        "last": loc,
        "commanded": 0.0,
        "stalled": 0,
        "speed_percent": speed_percent,
        # Joiners are "local" but networked — location stall was ending slides in ~1 frame.
        "timed": ctx is not None
        and ctx.role in (ExecutionRole.LOCAL_REQUESTER, ExecutionRole.REMOTE_AUTHORITY),
    }
    state.crouch_owned = True
    state.crouch_lease = SlideCrouchLease(
        pawn_generation=ctx.pawn_generation if ctx is not None else -1,
        duck_before=_flag(pc, "bDuck"),
        owned=True,
    )
    try:
        pawn.ShouldCrouch(True)                  # make sure the body is down for the slide
    except Exception:  # noqa: BLE001
        pass
    # juso can_slide requires bDuck; engine crouch-move needs the duck flag held.
    if pc is not None:
        try:
            pc.bDuck = 1
        except Exception:  # noqa: BLE001
            pass
    _set_crouch_limit(pawn, start_speed)
    # Write the coast after the crouch cap. A landing that turned around has to
    # replace the old velocity, and a slam may have zeroed it already.
    z_write = None
    if forced:
        try:
            z_write = min(0.0, float(pawn.Velocity.Z))
        except Exception:  # noqa: BLE001
            z_write = 0.0
    core.set_velocity(pawn, dir_x * start_speed, dir_y * start_speed, z_write)
    if ctx is None or ctx.presentation:
        _hide_crouch_icon(pc)                        # straight away, so it never flashes up
    state.scrape_next = 0.0  # ground footsteps for the whole slide, no whoosh
    # Network slides time from a fixed CrouchedPct. Scaling that by entry speed
    # made a fast joiner slide both longer and stuck at a full meter.
    juso_pct = _JUSO_SLIDE_PCT
    state.slide["cp"] = juso_pct
    state.slide["meter_from"] = juso_pct
    state.slide["distance"] = float(distance_slider.value)
    try:
        state.slide["old_z"] = float(pawn.Location.Z)
    except Exception:  # noqa: BLE001
        state.slide["old_z"] = 0.0
    if state.slide.get("timed"):
        try:
            pawn.CrouchedPct = juso_pct
            state.cp_base = _JUSO_CROUCH_PCT
            state.cp_written = juso_pct
        except Exception:  # noqa: BLE001
            pass
    _begin_slide_pose(pc, pawn)
    _log(f"start ({reason}): {speed:.0f} -> {start_speed:.0f} u/s, walk {walk:.0f}")
    try:
        from .. import diagnostics

        diagnostics.event(
            "mm.slide.start",
            reason=reason,
            role=ctx.role.value if ctx is not None else "",
            speed=round(start_speed, 1),
            timed=bool(state.slide.get("timed")),
        )
    except Exception:  # noqa: BLE001
        pass
    # Joiner sets CrouchedPct locally and sends entry direction. Host coasts the same vector.
    try:
        from .. import coop_rpc

        if coop_rpc.is_requester(ctx):
            dx, dy = state.slide["dir"]
            coop_rpc.call_host(
                coop_rpc.server_slide_enter,
                float(juso_pct),
                float(distance_slider.value),
                float(dx),
                float(dy),
                float(speed_percent),
            )
    except Exception:  # noqa: BLE001
        pass


# Always release slide-owned crouch on end. Leaving crouch stuck was the joiner "stuck crouched"
# report — only a few reasons used to uncrouch before.
_UNCROUCH_REASONS = frozenset(
    {
        "jump",
        "sprint",
        "stood up",
        "off_cliff",
        "pawn gone or slide disabled",
        "mod disabled",
        "slowed",
        "blocked",
        "timed out",
        "back_cancel",
        "interrupted",
        "rpc_exit",
        "vehicle or dead",
    }
)


def _clear_crouch_intent(pc, pawn, *, suppress_until_release: bool) -> None:
    state = _state()
    ctx = core.current_context()
    lease = state.crouch_lease
    if ctx is not None and lease.owned and lease.pawn_generation != ctx.pawn_generation:
        # Pawn replaced: never write crouch onto the new generation; drop the stale lease only.
        state.crouch_owned = False
        state.crouch_lease = SlideCrouchLease()
        state.cp_base = state.cp_written = None
        state.suppress_crouch_until_release = suppress_until_release
        return
    if pc is not None:
        try:
            pc.bDuck = 0
        except Exception:  # noqa: BLE001
            pass
    if pawn is not None:
        for call in (lambda: pawn.ShouldCrouch(False), lambda: pawn.UnCrouch()):
            try:
                call()
            except Exception:  # noqa: BLE001
                pass
    state.crouch_owned = False
    state.crouch_lease = SlideCrouchLease()
    state.suppress_crouch_until_release = suppress_until_release
    if ctx is not None and ctx.input_state is not None and suppress_until_release:
        try:
            ctx.input_state.suppress_crouch_until_release()
        except Exception:  # noqa: BLE001
            pass


def _end(pawn, reason: str, pc=None) -> None:
    state = _state()
    if state.slide is None:
        return
    slide = state.slide
    state.ended = {"dir": slide["dir"], "speed": slide["speed"], "at": core.clock}
    if reason in _CARRY_REASONS:
        _start_carry(slide["speed"], slide["entry"])
    state.slide = None
    state.air_pressed = False
    state.air_slide = None
    state.slam_bank = None
    state.last_end = core.clock
    ctx = core.current_context()
    if ctx is None or ctx.presentation:
        hudfx.slide_end()
        _hold_crouch_icon()
    state.need_sprint, state.sprint_run = False, 0.0
    state.slide_queued = False
    state.suppress_crouch_until_release = False
    # A jump arms the landing chain after this returns. Any other end leaves
    # the next crouch free. A chain left over from the last slide was swallowing it.
    if reason != "jump":
        state.chain = None
        state.chain_hold = False
        state.chain_was_air = False
        state.slide_jump = None
    core.end("slide")
    if pawn is not None and slide.get("timed"):
        # The timed write is cp * Slide Speed. The lease compared the unscaled
        # cp and left the fast crouch cap on for a moment after the bar died.
        try:
            pawn.CrouchedPct = _JUSO_CROUCH_PCT
        except Exception:  # noqa: BLE001
            pass
        state.cp_base = state.cp_written = None
    elif pawn is not None:
        _set_crouch_limit(pawn, None)
    if pc is None:
        pc = ctx.controller if ctx is not None else None
    _end_slide_pose(pc, pawn)
    # Stand up after a slide. Do not keep crouch blocked — that made the next press do nothing.
    if reason in _UNCROUCH_REASONS or (ctx is not None and ctx.role == ExecutionRole.LOCAL_REQUESTER):
        _clear_crouch_intent(
            pc,
            pawn,
            suppress_until_release=False,
        )
    if ctx is None or ctx.presentation:
        _clear_shake(pc, pawn)
    if ctx is not None and state.action_id:
        authority.end_action(ctx, "slide", reason)
        state.action_id = 0
    try:
        from .. import coop_rpc

        if coop_rpc.is_requester(ctx):
            coop_rpc.call_host(coop_rpc.server_slide_exit)
    except Exception:  # noqa: BLE001
        pass
    _log(f"end ({reason})")
    try:
        from .. import diagnostics

        diagnostics.event(
            "mm.slide.end",
            reason=reason,
            role=ctx.role.value if ctx is not None else "",
        )
    except Exception:  # noqa: BLE001
        pass


def _cancel() -> None:
    """Another movement action is taking over."""
    ctx = core.current_context()
    pc = ctx.controller if ctx is not None else None
    pawn = ctx.pawn if ctx is not None else None
    _end(pawn, "interrupted", pc)


# ---- momentum carry ---------------------------------------------------------------------
# Standing up or jumping out of a slide keeps its speed for a while: the top speed (a
# GroundSpeed multiplier, applied by core together with Sprint Surge) starts at the slide's
# speed relative to the speed you had going in, and eases back to 1x.
_CARRY_REASONS = ("stood up", "jump", "sprint", "off_cliff")
def _start_carry(end_speed: float, entry_speed: float) -> None:
    state = _state()
    dur = carry_slider.value / 1000.0
    ratio = end_speed / max(1.0, entry_speed)
    if dur <= 0.0 or ratio <= 1.0:
        _stop_carry()
        return
    state.carry = {"from": ratio, "at": core.clock, "dur": dur}
    core.set_speed_mult("slide", ratio)
    _log(f"momentum carry x{ratio:.2f} for {dur:.1f}s")


def _stop_carry() -> None:
    _state().carry = None
    core.set_speed_mult("slide", None)


_CARRY_STOP = 0.2   # on the ground below this fraction of walking speed = stopped: carry ends


def _update_carry(pawn) -> None:
    state = _state()
    if state.carry is None:
        return
    if pawn is None or core.unusable(pawn):
        _stop_carry()
        return
    if core.phys == core.PHYS_WALKING:
        try:
            if core.hspeed(pawn) < _walk_speed(pawn) * _CARRY_STOP:
                _log("momentum carry cancelled: stopped moving")
                _stop_carry()
                return
        except Exception:  # noqa: BLE001
            pass
    t = (core.clock - state.carry["at"]) / state.carry["dur"]
    if t >= 1.0:
        _stop_carry()
        return
    ease = t * t * (3.0 - 2.0 * t)
    core.set_speed_mult("slide", 1.0 + (state.carry["from"] - 1.0) * (1.0 - ease))


# ---- jumping out of a slide -------------------------------------------------------------


_LAUNCH_HOLD = 0.15           # seconds the launch is re-applied if the game pulls you back down
_LAND_GRACE = 0.35            # a landing slide ignores stall, back-cancel, and a one-frame hop
# A slide cancel has to actually leave the ground. Anything shorter is a tap
# that refreshes the slide the moment you jump, which can be repeated forever.
_CHAIN_MIN_AIR = 0.40


def _launch_now(pc, pawn, vx, vy, vz) -> bool:
    """Get the pawn off the ground with this velocity. Tries the game's own jump first
    (DoJump, after uncrouching), then switching physics to falling. True = airborne."""
    for call in (lambda: pawn.ShouldCrouch(False), lambda: pawn.UnCrouch()):
        try:
            call()
        except Exception:  # noqa: BLE001
            pass
    jumped = False
    try:
        jumped = bool(pawn.DoJump(False))       # the game's jump: sets falling, jump anim / sound
    except Exception as e:  # noqa: BLE001
        _log(f"DoJump failed: {e!r}")
    if not jumped or int(pawn.Physics) != core.PHYS_FALLING:
        core.set_physics(pawn, core.PHYS_FALLING)
        try:
            if int(pawn.Physics) != core.PHYS_FALLING:
                _warn("slide jump could not leave the ground")
                return False
        except Exception:  # noqa: BLE001
            pass
    # Component writes often no-op. The full vector is what the host holds too.
    core.set_velocity(pawn, vx, vy, vz)
    return True


def _ground_jump(pc, pawn) -> None:
    """Jump pressed on the ground. During a slide (or just after the game stood you up
    from one) this launches a jump that keeps the slide's speed and direction, instead of
    the game's crouched "jump = stand up"."""
    state = _state()
    ctx = core.current_context()
    if ctx is None or not ctx.authority:
        return
    # Sample the hold before the slide ends. Ending the slide stands you up, and that
    # uncrouch fires DuckReleased while C is still down. On a joiner the key list usually
    # misses that hold, so the release was clearing the landing slide.
    holding = False
    if state.slide is not None or (
        state.ended is not None and core.clock - state.ended["at"] <= _JUMP_GRACE
    ):
        holding = _wants_chain(state, pc)
        if holding:
            state.crouch_down = True
            # Long enough to ignore the uncrouch's release, short enough that a
            # let-go during the jump is seen before landing.
            state.ignore_release_until = core.clock + 0.12
    if state.slide is not None:
        dx, dy = state.slide["dir"]
        speed = state.slide["speed"]
        _end(pawn, "jump", pc)
        if holding:
            state.crouch_down = True
    elif state.ended is not None and core.clock - state.ended["at"] <= _JUMP_GRACE:
        dx, dy = state.ended["dir"]
        speed = state.ended["speed"]
    else:
        _log("jump pressed: no slide running")
        return
    state.ended = None
    if core.unusable(pawn):
        return
    speed *= jump_momentum_slider.value / 100.0
    try:
        pc.bDuck = 0                           # crouch toggle off: you land standing
    except Exception:  # noqa: BLE001
        try:
            pc.bDuck = False
        except Exception:  # noqa: BLE001
            pass
    v = (dx * speed, dy * speed, core.base_jump(pawn) * jump_height_slider.value / 100.0)
    try:
        ok = _launch_now(pc, pawn, *v)
    except Exception as e:  # noqa: BLE001
        _warn(f"slide jump failed: {e!r}")
        return
    if ok:
        state.launch = {"v": v, "until": core.clock + _LAUNCH_HOLD}
        _remember_slide_jump(state, holding, dx, dy, speed)
        if holding:
            state.crouch_down = True
            if state.ignore_release_until < core.clock + 0.12:
                state.ignore_release_until = core.clock + 0.12
        state.slam_bank = None
        try:
            from .. import coop_rpc

            if coop_rpc.is_requester(ctx):
                coop_rpc.call_host(
                    coop_rpc.server_slide_jump,
                    float(v[0]),
                    float(v[1]),
                    float(v[2]),
                )
        except Exception:  # noqa: BLE001
            pass
        core.emit("slide_jump")
        if indicator_option.value and ctx.presentation:
            hudfx.slide_launch()
    _log(f"slide jump at {speed:.0f} u/s (airborne: {ok})")


def _hold_launch(pc, pawn) -> None:
    """For a moment after a slide jump: if the game put the pawn back on the ground (its own
    crouched-jump handling), launch it again."""
    state = _state()
    if state.launch is None:
        return
    if pawn is None or core.clock > state.launch["until"]:
        state.launch = None
        return
    if core.phys == core.PHYS_FALLING:
        try:
            if float(pawn.Velocity.Z) > 0.0:
                return                         # rising: it stuck
        except Exception:  # noqa: BLE001
            return
    _log(f"slide jump re-applied (physics {core.phys})")
    try:
        _launch_now(pc, pawn, *state.launch["v"])
    except Exception as e:  # noqa: BLE001
        _warn(f"slide jump re-apply failed: {e!r}")
        state.launch = None


# ---- camera shake ---------------------------------------------------------------------
# A light bob and tilt while sliding (applied by camera.py, shared with the air dash). Roll never
# changes where you aim. Strength follows the slide's speed.
_SHAKE_EYE = 2.2        # eye-height bob at 100%, units
_SHAKE_ROLL = 1.1       # tilt at 100%, degrees
_SLIDE_EYE_DIP = 14.0   # settle the camera lower while sliding (reads as a slide, not crouch-run)


def _apply_shake(pc, pawn, dt, strength) -> None:
    state = _state()
    state.push_want = max(0.0, min(1.0, strength))
    amount = shake_slider.value / 100.0 * max(0.0, min(1.0, strength))
    dip = max(0.0, min(1.0, strength))
    camera.request("slide_dip", eye=-_SLIDE_EYE_DIP * dip)
    if amount <= 0.0:
        return
    state.shake_t += dt
    bob, tilt = camera.wave(state.shake_t)
    camera.request("slide", eye=bob * _SHAKE_EYE * amount, roll=tilt * _SHAKE_ROLL * amount)


_PUSH = 3.8             # camera push (view tilts back) at 100%, degrees
_PUSH_RISE = 0.12       # seconds to tilt back as a slide starts...
_PUSH_FALL = 0.30       # ...and to come back level as it slows or ends


def _update_push(dt) -> None:
    """Ease the push toward what the slide asked for last frame (0 once it has ended)."""
    state = _state()
    want = state.push_want
    state.push_want = 0.0
    if want > state.push_level:
        state.push_level = min(want, state.push_level + dt / _PUSH_RISE)
    else:
        state.push_level = max(want, state.push_level - dt / _PUSH_FALL)
    amount = push_slider.value / 100.0
    if state.push_level > 0.0 and amount > 0.0:
        e = state.push_level * state.push_level * (3.0 - 2.0 * state.push_level)
        camera.request("slide_push", pitch=_PUSH * amount * e)


def _clear_shake(pc, pawn) -> None:
    """Slide ended: stop asking (camera.py takes the offsets out)."""
    _state().shake_t = 0.0


# ---- first-person arms (juso-style) + third-person crouch latch ---------------------------
# juso TP slide = crouch anim via bDuck/ShouldCrouch + high CrouchedPct. No Mesh.Translation.
# juso FP = tween Pawn.Arms.SkeletalMesh Origin/RotOrigin. Component field writes often no-op in
# pyunrealsdk — assign full Vector/Rotator structs every tick (same lesson as Velocity).

_ARMS_ENTER_S = 0.22
_ARMS_EXIT_S = 0.35
# juso sliding targets (rotator UU / mesh origin). Rest defaults match juso tween_reset.
_ARMS_REST = {
    "pitch": 0.0,
    "yaw": 0.0,
    "roll": 0.0,
    "ox": 40.0,
    "oy": 0.0,
    "oz": -167.0,
}
_ARMS_SLIDE = {
    "pitch": 900.0,
    "yaw": -350.0,
    "roll": -7800.0,
    "ox": 28.0,
    "oy": -18.0,
    "oz": -188.0,
}
_FP_ROLL = -5.5  # view lean (degrees) via camera.py while sliding


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _arms_mesh(pc):
    """Resolve first-person arms mesh; do not require Attachments (holster clears them)."""
    if pc is None:
        return None
    try:
        pawn = pc.Pawn
    except Exception:  # noqa: BLE001
        return None
    if pawn is None:
        return None
    for getter in (
        lambda: pawn.Arms.SkeletalMesh,
        lambda: pawn.Arms,
        lambda: getattr(pawn, "FirstPersonMesh", None),
    ):
        try:
            mesh = getter()
            if mesh is None:
                continue
            # Need Origin + RotOrigin like a SkeletalMeshComponent.
            _ = mesh.Origin.X
            _ = mesh.RotOrigin.Pitch
            return mesh
        except Exception:  # noqa: BLE001
            continue
    return None


def _read_arms(mesh) -> dict:
    return {
        "pitch": float(mesh.RotOrigin.Pitch),
        "yaw": float(mesh.RotOrigin.Yaw),
        "roll": float(mesh.RotOrigin.Roll),
        "ox": float(mesh.Origin.X),
        "oy": float(mesh.Origin.Y),
        "oz": float(mesh.Origin.Z),
    }


def _write_arms(mesh, pose: dict) -> bool:
    """Full-struct assign — field writes on RotOrigin/Origin often silently no-op."""
    try:
        import unrealsdk

        rot = unrealsdk.make_struct(
            "Rotator",
            Pitch=int(round(pose["pitch"])),
            Yaw=int(round(pose["yaw"])),
            Roll=int(round(pose["roll"])),
        )
        org = unrealsdk.make_struct(
            "Vector",
            X=float(pose["ox"]),
            Y=float(pose["oy"]),
            Z=float(pose["oz"]),
        )
        if rot is not None:
            mesh.RotOrigin = rot
        else:
            mesh.RotOrigin.Pitch = pose["pitch"]
            mesh.RotOrigin.Yaw = pose["yaw"]
            mesh.RotOrigin.Roll = pose["roll"]
        if org is not None:
            mesh.Origin = org
        else:
            mesh.Origin.X = pose["ox"]
            mesh.Origin.Y = pose["oy"]
            mesh.Origin.Z = pose["oz"]
        return True
    except Exception:  # noqa: BLE001
        try:
            mesh.RotOrigin.Pitch = pose["pitch"]
            mesh.RotOrigin.Yaw = pose["yaw"]
            mesh.RotOrigin.Roll = pose["roll"]
            mesh.Origin.X = pose["ox"]
            mesh.Origin.Y = pose["oy"]
            mesh.Origin.Z = pose["oz"]
            return True
        except Exception:  # noqa: BLE001
            return False


def _lerp_pose(a: dict, b: dict, t: float) -> dict:
    u = _smoothstep(t)
    return {k: a[k] + (b[k] - a[k]) * u for k in a}


def _gun_is_tilted(pose: dict) -> bool:
    """True when the first-person gun is still at a slide angle."""
    return abs(float(pose.get("roll", 0.0))) > 400.0 or abs(float(pose.get("pitch", 0.0))) > 200.0


def _begin_slide_pose(pc, pawn) -> None:
    """Start local FP arms lean only (never touch third-person Mesh — anim freak-outs).

    The level pose is the known rest. Reading the live gun saved a tilted slide as the
    rest pose, so the next slide ended and the gun stayed leaned over.
    """
    state = _state()
    ctx = core.current_context()
    if ctx is not None and not ctx.presentation:
        return
    rest = dict(_ARMS_REST)
    current = dict(rest)
    mesh = _arms_mesh(pc)
    if mesh is not None:
        try:
            current = _read_arms(mesh)
        except Exception:  # noqa: BLE001
            current = dict(rest)
    state.arms = {
        "phase": "enter",
        "t0": core.clock,
        "rest": rest,
        "from": current,
        "to": dict(_ARMS_SLIDE),
    }


def _tick_slide_pose(pc, dt: float) -> None:
    state = _state()
    arms = state.arms
    if arms is None:
        return
    phase = arms.get("phase", "hold")
    # Camera roll lean every presentation tick — always visible even if arms fail.
    ctx = core.current_context()
    if ctx is None or ctx.presentation:
        if phase == "exit":
            t = (core.clock - arms["t0"]) / max(0.05, _ARMS_EXIT_S)
            lean = max(0.0, 1.0 - _smoothstep(t))
        elif phase == "enter":
            t = (core.clock - arms["t0"]) / max(0.05, _ARMS_ENTER_S)
            lean = _smoothstep(t)
        else:
            lean = 1.0
        camera.request("slide_lean", roll=_FP_ROLL * lean)

    mesh = _arms_mesh(pc)
    if mesh is None:
        if phase == "exit" and (core.clock - arms["t0"]) >= _ARMS_EXIT_S:
            state.arms = None
        return
    try:
        if phase == "hold":
            # The slide is already over. Painting the lean again is how the gun stays tilted.
            if state.slide is None:
                _write_arms(mesh, _ARMS_REST)
                state.arms = None
                return
            _write_arms(mesh, arms["to"])
            return
        dur = _ARMS_ENTER_S if phase == "enter" else _ARMS_EXIT_S
        t = (core.clock - arms["t0"]) / max(0.05, dur)
        pose = _lerp_pose(arms["from"], arms["to"], t)
        _write_arms(mesh, pose)
        if t >= 1.0:
            if phase == "enter":
                arms["phase"] = "hold"
                _write_arms(mesh, arms["to"])
            else:
                _write_arms(mesh, arms["rest"])
                state.arms = None
    except Exception:  # noqa: BLE001
        if phase == "exit":
            state.arms = None


def _end_slide_pose(pc, pawn) -> None:
    state = _state()
    arms = state.arms
    if arms is None:
        return
    rest = dict(_ARMS_REST)
    try:
        mesh = _arms_mesh(pc)
        # Snap to level and drop the pose. A lerp that started from the lean painted it
        # back on the next tick, so a chain of slides left the gun tilted.
        if mesh is not None:
            _write_arms(mesh, rest)
        state.arms = None
    except Exception:  # noqa: BLE001
        state.arms = None


def _settle_arms(pc) -> None:
    """Not sliding: finish the lean, and put a gun that is still tilted back to level."""
    state = _state()
    if state.slide is not None:
        return
    if state.arms is not None:
        _end_slide_pose(pc, None)
        return
    mesh = _arms_mesh(pc)
    if mesh is None:
        return
    try:
        current = _read_arms(mesh)
    except Exception:  # noqa: BLE001
        return
    if _gun_is_tilted(current):
        _write_arms(mesh, _ARMS_REST)


# ---- every tick --------------------------------------------------------------------------


def _steer(pc, pawn, dt) -> None:
    """Turn the slide a little toward the movement keys (at most Slide Steering deg/s)."""
    rate = math.radians(steer_slider.value)
    if rate <= 0.0:
        return
    try:
        ax, ay = float(pawn.Acceleration.X), float(pawn.Acceleration.Y)   # this tick's input
    except Exception:  # noqa: BLE001
        return
    size = math.hypot(ax, ay)
    if size <= 1.0:
        return
    # Holding forward (where you look) barely steers; strafing steers at the full rate.
    try:
        fx_, fy_ = core.facing(pc)
        forward = abs(ax * fx_ + ay * fy_) / size
        rate *= 1.0 - (1.0 - _FORWARD_STEER) * forward
    except Exception:  # noqa: BLE001
        pass
    state = _state()
    if state.slide is None:
        return
    dx, dy = state.slide["dir"]
    want = math.atan2(ay, ax)
    have = math.atan2(dy, dx)
    diff = (want - have + math.pi) % (2.0 * math.pi) - math.pi
    if abs(diff) > math.radians(100):
        return                                   # pulling backwards: no turn (friction does it)
    turn = max(-rate * dt, min(rate * dt, diff))
    a = have + turn
    state.slide["dir"] = (math.cos(a), math.sin(a))


_FORWARD_STEER = 0.25  # share of Slide Steering that forward input (W) gets; strafing gets all of it
_BACK_DOT = -0.5   # input pointing at least this much behind where you look = "moving back"


def _pressing_back(pc, pawn) -> bool:
    """The movement keys point backward (relative to the camera), e.g. holding S."""
    try:
        ax, ay = float(pawn.Acceleration.X), float(pawn.Acceleration.Y)   # this tick's input
    except Exception:  # noqa: BLE001
        return False
    size = math.hypot(ax, ay)
    if size <= 1.0:
        return False
    fx_, fy_ = core.facing(pc)
    return (ax * fx_ + ay * fy_) / size <= _BACK_DOT


# ---- the scrape: a footstep repeated fast, slowing with the slide ------------------------
# Footsteps are in the always-loaded player bank and follow the floor (dirt, metal, snow...).

_SCRAPE_SURFACE = "Aks_Global_Switches.Ground_Textures.AkSwitch_PM_Sand"  # the footstep surface used
_SCRAPE_FAST = 0.065   # seconds between steps at the start of a slide...
_SCRAPE_SLOW = 0.17    # ...and as it runs out (at 100% Slide Sound Rate)
_SCRAPE_SKIP = ("Land", "Ladder", "Jump", "Mantle", "Stop", "Swim", "Wade", "Vehicle", "Veh_")
_SCRAPE_PREFER = ("Crouch", "Walk", "Run", "Sprint", "Step")
_scrape_list = None
_scrape_told = 0


def _scrape_names():
    """Player footstep sounds to make the scrape from, best guesses first."""
    global _scrape_list
    if not _scrape_list:
        names = [n for n in fx.event_names(refresh=_scrape_list is not None)
                 if "_Fs_" in n and n.startswith("Ak_Play") and not any(b in n for b in _SCRAPE_SKIP)]

        def rank(n):
            for i, k in enumerate(_SCRAPE_PREFER):
                if k in n:
                    return (i, n)
            return (len(_SCRAPE_PREFER), n)

        _scrape_list = sorted(names, key=rank)
    return _scrape_list


def _scrape_paths() -> tuple[str, ...]:
    """Footsteps for the scrape. Known banks first, then any extra the game already loaded."""
    paths = list(fx.scrape_paths())
    for name in _scrape_names():
        if name.startswith("Ake_"):
            paths.append(name)
        else:
            paths.append(f"Ake_Fs_Player.{name}")
    seen: list[str] = []
    for path in paths:
        if path not in seen:
            seen.append(path)
    return tuple(seen)


def _scrape(pc, pawn, strength) -> None:
    """One step of the scrape when it is due; steps come faster the faster you slide."""
    global _scrape_told
    state = _state()
    strength = max(0.0, min(1.0, strength))
    kind = "dirt"
    try:
        from . import surfacefx

        kind = surfacefx.slide(pc, pawn, strength)
    except Exception:  # noqa: BLE001
        pass
    if not audio_option.value or core.clock < state.scrape_next:
        return
    paths = _scrape_paths()
    if not paths:
        return
    k = (max(1, int(scrape_variant_slider.value)) - 1) % len(paths)
    if _DEBUG and _scrape_told != k + 1:
        _scrape_told = k + 1
        listing = ", ".join(f"{i + 1}={n}" for i, n in enumerate(paths[:12]))
        logging.warning(f"[Slide] scrape sound: variant {k + 1} = {paths[k]}  (all: {listing})")
    try:
        from . import surfacefx

        fx.set_switch(pawn, surfacefx.switch_path(kind))
    except Exception:  # noqa: BLE001
        fx.set_switch(pawn, _SCRAPE_SURFACE)
    fx.play_sound(pc, pawn, paths[k])
    strength = max(0.0, min(1.0, strength))
    gap = _SCRAPE_SLOW + (_SCRAPE_FAST - _SCRAPE_SLOW) * strength
    state.scrape_next = core.clock + gap * 100.0 / max(1, scrape_rate_slider.value)


def _run(pc, pawn, dt) -> None:
    _require_authority("slide tick")
    state = _state()
    s = state.slide
    if s is None:
        return
    if core.unusable(pawn):
        _end(pawn, "vehicle or dead", pc)
        return
    ctx = core.current_context()
    timed = bool(s.get("timed")) or (ctx is not None and not ctx.local)
    fresh = _slide_fresh(s)

    if core.phys != core.PHYS_WALKING:
        if s.get("stick") and core.phys == core.PHYS_FALLING:
            # Turning the landing slide can hop for a frame. Stay on the floor.
            # A normal slide must not do this: vault and jump use falling physics.
            try:
                z_now = min(0.0, float(pawn.Velocity.Z))
            except Exception:  # noqa: BLE001
                z_now = 0.0
            try:
                core.set_velocity(pawn, s["dir"][0] * s["speed"], s["dir"][1] * s["speed"], z_now)
                core.set_physics(pawn, core.PHYS_WALKING)
            except Exception:  # noqa: BLE001
                _end(pawn, "off_cliff", pc)
                return
        elif timed:
            # Network slides: brief falling blips must not kill the slide into a stuck crouch.
            pass
        elif (core.phys == core.PHYS_FALLING and _hit_recently() and state.launch is None
                and _floor_below(pawn)):                 # (knocked loose, not off a ledge)
            # a hit's push lifted you off the floor: put you back on it and keep sliding
            try:
                _require_authority("slide hit recovery")
                pawn.Velocity.Z = min(float(pawn.Velocity.Z), 0.0)
                core.set_physics(pawn, core.PHYS_WALKING)
            except Exception:  # noqa: BLE001
                _end(pawn, "off_cliff", pc)
                return
        elif core.phys == core.PHYS_FALLING and state.launch is None:
            # The crouch at the start of a slide dips the capsule. Ending there
            # cleared the bar and the next frame started a second slide.
            try:
                vz = float(pawn.Velocity.Z)
            except Exception:  # noqa: BLE001
                vz = 0.0
            if _falling_is_crouch_dip(vz, _floor_below(pawn)):
                try:
                    core.set_velocity(
                        pawn,
                        s["dir"][0] * s["speed"],
                        s["dir"][1] * s["speed"],
                        min(0.0, vz),
                    )
                    core.set_physics(pawn, core.PHYS_WALKING)
                except Exception:  # noqa: BLE001
                    _end(pawn, "off_cliff", pc)
                    return
            else:
                _end(pawn, "off_cliff", pc)
                return
        else:
            _end(pawn, "off_cliff", pc)
            return

    # The player at the keyboard cancels by releasing crouch, same as a local slide.
    # The host's copy of a joiner rarely has their bDuck, so it stays down until
    # the joiner's exit RPC. Re-latching the owner hid that release and the slide
    # only ran out on the timer.
    owns_crouch = ctx is None or ctx.local
    if owns_crouch and not _hit_recently():
        key = _crouch_held(pc)
        # Borderlands 2 toggle crouch never sends a release on key-up, and the
        # body stays crouched, so the latch would run the whole slide after a tap.
        if _bl2_key_up(state, pc):
            _end(pawn, "stood up", pc)
            return
        # PressedKeys does not list a held crouch key. DuckReleased clears the latch.
        released = not state.crouch_down and key is not True
        if released and (timed or not _crouching(pc, pawn)):
            _end(pawn, "stood up", pc)
            return
    if not _crouching(pc, pawn):
        try:
            if pc is not None:
                pc.bDuck = 1
            pawn.ShouldCrouch(True)
        except Exception:  # noqa: BLE001
            pass

    x, y = float(pawn.Location.X), float(pawn.Location.Y)
    dx, dy = s["dir"]
    s["elapsed"] += dt
    # Network slide: CrouchedPct times the coast, and velocity keeps it moving
    # after the player releases forward (CrouchedPct alone does not).
    if timed:
        cp = float(s.get("cp", _JUSO_SLIDE_PCT))
        try:
            z = float(pawn.Location.Z)
        except Exception:  # noqa: BLE001
            z = s.get("old_z", 0.0)
        old_z = s.get("old_z", z)
        z_diff = float(z) - float(old_z)
        scale = _distance_scale(float(s.get("distance", distance_slider.value)))
        drop_run = _track_drop(s, z_diff, dt)
        if not slope_slider.value:
            drop_run = 0.0
        cp = _decay_juso_pct(cp, z_diff, dt / scale, drop_run)
        s["old_z"] = z
        s["cp"] = cp
        speed_percent = float(s.get("speed_percent", speed_slider.value))
        s["speed"] = _coast_velocity(cp, _walk_speed(pawn), speed_percent)
        try:
            written = cp * _speed_scale(speed_percent)
            pawn.CrouchedPct = written
            state.cp_written = written
            if state.cp_base is None:
                state.cp_base = _JUSO_CROUCH_PCT
        except Exception:  # noqa: BLE001
            pass
        # Holding crouch must not keep a flat slide alive past the hard cap.
        # A ramp or a run of stairs, once it has been dropping for a moment, may.
        cap = (_MAX_DOWNHILL_S if drop_run > 0.12 else _MAX_FLAT_S) * scale
        if cp < _JUSO_CROUCH_PCT or s["elapsed"] > cap:
            _end(pawn, "slowed" if cp < _JUSO_CROUCH_PCT else "timed out", pc)
            return
        # Engine crouch-move stops cold when W is released. Coast on the entry
        # direction the same way the local slide does, so letting go still slides.
        _coast_slide(pawn, dx, dy, s["speed"])
        if ctx is None or ctx.presentation:
            if indicator_option.value:
                s["cap"] = cap
                low = _crouch_walk_speed(pawn)
                hudfx.slide_momentum(_slide_fill(s["elapsed"], cap, s["speed"], s["start"], low))
            _apply_shake(pc, pawn, dt, max(0.0, min(1.0, cp / _JUSO_SLIDE_PCT)))
            _scrape(pc, pawn, max(0.0, min(1.0, cp / _JUSO_SLIDE_PCT)))
        return

    if fresh:
        s["stalled"] = 0
    elif s["elapsed"] > 0.0 and s["commanded"] > 0.0:
        moved = (x - s["last"][0]) * dx + (y - s["last"][1]) * dy
        if _hit_recently():
            s["stalled"] = 0                         # a hit's push isn't a wall
        else:
            s["stalled"] = s["stalled"] + 1 if moved < _STALL_RATIO * s["commanded"] else 0
    s["last"] = (x, y)
    if s["stalled"] >= _STALL_TICKS:
        _end(pawn, "blocked", pc)
        return

    if not fresh and back_cancel_option.value and _pressing_back(pc, pawn):
        _end(pawn, "back_cancel", pc)
        return
    _steer(pc, pawn, dt)
    dx, dy = s["dir"]

    # Flat coasts; downhill stretches; still always ends.
    dist = max(50.0, min(140.0, float(distance_slider.value)))
    flat_drag = max(_MIN_FLAT_DRAG, float(friction_slider.value) * 100.0 / dist) / _LENGTH
    try:
        z_now = float(pawn.Location.Z)
    except Exception:  # noqa: BLE001
        z_now = float(s.get("old_z", 0.0))
    z_prev = float(s.get("old_z", z_now))
    drop_run = _track_drop(s, z_now - z_prev, dt)
    s["old_z"] = z_now
    slope = _slope_along(pc, pawn, dx, dy)
    vertical = _vertical_slope(pc, drop_run)
    # Stairs keep a flat floor normal on each tread. The drop is what stretches them.
    if abs(vertical) > abs(slope):
        slope = vertical
    if slope > 0.0 and _slide_time_cap(slope) > _MAX_FLAT_S:
        # The time cap already stretches. Keep the speed with it, and pick up a little.
        # Capping the boost under the flat drag used to leave a long crouch-walk at the bottom.
        accel = min(slope * 0.15, flat_drag * 0.35)
    elif slope > 0.0:
        accel = -flat_drag + min(slope, flat_drag * 0.88)
    else:
        accel = -flat_drag + slope  # uphill (negative) shortens further
    if s["elapsed"] > _slide_time_cap(slope):
        _end(pawn, "timed out", pc)
        return
    walk = _walk_speed(pawn)
    cap_scale = _speed_scale(float(s.get("speed_percent", speed_slider.value)))
    s["speed"] = min(s["speed"] + accel * dt, walk * max_speed_slider.value / 100.0 * cap_scale)
    if s["speed"] <= _crouch_walk_speed(pawn):
        _end(pawn, "slowed", pc)
        return

    _set_crouch_limit(pawn, s["speed"])
    if ctx is None or ctx.presentation:
        if indicator_option.value:
            cap = _slide_time_cap(slope)
            s["cap"] = cap
            low = _crouch_walk_speed(pawn)
            hudfx.slide_momentum(_slide_fill(s["elapsed"], cap, s["speed"], s["start"], low))
        else:
            hudfx.slide_end()
    s["commanded"] = s["speed"] * dt
    _coast_slide(pawn, dx, dy, s["speed"])
    if ctx is None or ctx.presentation:
        _apply_shake(pc, pawn, dt, s["speed"] / max(1.0, s["start"]))
        _scrape(pc, pawn, s["speed"] / max(1.0, s["start"]))


def _tick(pc, pawn, dt) -> None:
    state = _state()
    ctx = core.current_context()
    if ctx is None:
        return
    # juso math, Eternal scheduling: decay joiner slides once per local frame (not also
    # from PlayerMove — double service made CrouchedPct fall at 2×).
    if ctx.local and ctx.role != ExecutionRole.LOCAL_REQUESTER:
        _service_host_slides(dt)
        _service_host_jumps(dt)
    if ctx.presentation:
        _update_push(dt)
    if state.arms is not None:
        _tick_slide_pose(pc, dt)
    _hold_launch(pc, pawn)
    _update_carry(pawn)
    if state.slide is not None:
        if pawn is None or not enabled_option.value:
            _end(pawn, "pawn gone or slide disabled", pc)
        else:
            _run(pc, pawn, dt)
    if pawn is None or core.unusable(pawn):
        if ctx.presentation:
            _show_crouch_icon(pc)
            _settle_arms(pc)
        state.prev_crouch = state.prev_sprint = False
        state.prev_phys, state.prev_speed = -1, 0.0
        return

    crouch = _crouching(pc, pawn)
    held = _crouch_held(pc)
    if _bl2_key_up(state, pc):
        state.crouch_down = False
    _update_chain_hold(state, held)
    # A held crouch stays blocked after the slide ends. A button that is already up does not.
    if (
        state.suppress_crouch_until_release
        and not state.crouch_down
        and held is not True
        and not crouch
    ):
        state.suppress_crouch_until_release = False
    if not crouch:
        state.crouch_pressed_while_airborne = False
    effective_crouch = crouch and not state.suppress_crouch_until_release
    phys = core.phys
    if held is True:
        state.crouch_down = True
    if phys == core.PHYS_FALLING and state.air_pressed and (held is True or state.crouch_down):
        _note_air_speed(state, pawn)
    elif phys == core.PHYS_FALLING:
        state.air_slide = None
    if effective_crouch and not state.prev_crouch:
        state.crouch_pressed_at = core.clock
        state.crouch_pressed_while_airborne = phys == core.PHYS_FALLING
    try:
        from . import holster

        sprint_reading = holster.is_sprinting(pc, pawn)
    except Exception:  # noqa: BLE001
        sprint_reading = None
    sprint = sprint_reading if sprint_reading is not None else _flag(pawn, "bIsSprinting")
    # A sprint flag that is already on is how the slide started. It is not a cancel
    # until that key has come up. The next press then ends the slide at once.
    _note_sprint_release(state, pc)
    try:
        speed = core.hspeed(pawn)
    except Exception:  # noqa: BLE001
        speed = 0.0
    if state.need_sprint:
        sprinting_now = bool(sprint or state.prev_sprint or speed >= _walk_speed(pawn) * 1.2)
        if sprinting_now and phys == core.PHYS_WALKING and state.slide is None:
            state.sprint_run += dt
            if state.sprint_run >= sprint_req_slider.value / 1000.0:
                state.need_sprint = False
        elif not sprinting_now:
            state.sprint_run = 0.0

    # Held crouch through a slide jump lands in another slide. This does not wait
    # out "Sprint Before Next Slide", and it does not require Slide From Landing.
    if state.chain is not None and phys == core.PHYS_FALLING:
        state.chain_was_air = True
    slam_coming_down = _slam_diving()
    # A slam used to leave this set, and the sprint wait used to block the next slide.
    state.slam_hold = False
    state.need_sprint = False
    if (
        state.chain is not None
        and state.slide is None
        and enabled_option.value
        and ctx.authority
        and phys == core.PHYS_WALKING
        and (state.prev_phys == core.PHYS_FALLING or state.chain_was_air)
        and state.chain_hold
        and held is True
        and not slam_coming_down
    ):
        link = state.chain
        # A touch of ground before the jump has been airborne long enough is not the landing.
        # Clearing the chain there dropped the slide cancel when the host pulled a joiner down early.
        if _chain_air_ok(link):
            state.chain = None
            state.need_sprint = False
            state.suppress_crouch_until_release = False
            state.chain_was_air = False
            offer_landing(pc, pawn, link["dir"][0], link["dir"][1], link["speed"], "slide cancel")

    # Sprint, jump, hold crouch, land. No slide before the jump. Slide From Landing
    # stays off; that option is a separate ground-crouch landing.
    if (
        state.slide is None
        and enabled_option.value
        and ctx.authority
        and phys == core.PHYS_WALKING
        and state.prev_phys == core.PHYS_FALLING
        and not slam_coming_down
    ):
        _air_crouch_landing(state, pc, pawn)

    on_ground = phys == core.PHYS_WALKING or _crouch_blip_on_ground(state, pawn, phys)
    if (
        state.slide is None
        and enabled_option.value
        and core.busy is None
        and ctx.authority
        and on_ground
        and not slam_coming_down
    ):
        need = _walk_speed(pawn) * min_speed_slider.value / 100.0
        crouch_edge = effective_crouch and not state.prev_crouch
        # Borderlands 2: hold crouch while sprinting. The speed check used the
        # sprint GroundSpeed, so the slide waited until the sprint was already over.
        from .. import game

        if game.is_bl2() and held is True and _bl2_slide_ready(state, pawn, sprint, speed):
            if phys != core.PHYS_WALKING:
                try:
                    pawn.Physics = core.PHYS_WALKING
                except Exception:  # noqa: BLE001
                    pass
            _start(pc, pawn, "crouch held while sprinting")
        # Crouch while sprinting starts a slide, including the one after the last slide.
        elif crouch_edge and (sprint or state.prev_sprint or max(speed, state.prev_speed) >= need) and max(speed, state.prev_speed) >= need:
            if phys != core.PHYS_WALKING:
                try:
                    pawn.Physics = core.PHYS_WALKING
                except Exception:  # noqa: BLE001
                    pass
            _start(pc, pawn, "crouch while sprinting")
        # 2) landed with crouch on, moving forward fast enough — never from a crouch that
        # began while airborne (that press belongs to native Slam, not a landing slide).
        elif (
            landing_option.value
            and effective_crouch
            and not _slide_jump_blocks_landing(state)
            and not state.crouch_pressed_while_airborne
            and state.prev_phys == core.PHYS_FALLING
            and core.clock - state.crouch_pressed_at <= landing_window_slider.value / 1000.0 + dt
            and max(speed, state.prev_speed) >= need
        ):
            try:
                fx_, fy_ = core.facing(pc)
                vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
                fwd = (vx * fx_ + vy * fy_) / max(1.0, math.hypot(vx, vy))
            except Exception:  # noqa: BLE001
                fwd = 0.0
            if fwd >= _FORWARD_DOT:
                _start(pc, pawn, "landing")

    if phys == core.PHYS_WALKING and state.prev_phys == core.PHYS_FALLING:
        state.slide_jump = None

    state.prev_crouch = effective_crouch
    state.prev_sprint = sprint
    state.prev_phys = phys
    state.prev_speed = speed
    # crouch icon: hidden while sliding, while crouch is on in the air (so a jump into a landing
    # slide never shows it), and for _ICON_HOLD_S after a slide or a slam unless you press crouch
    # again; shown again otherwise
    # (core.busy == "slam": on the frame you land a slam this runs before the slam's own impact,
    # which is what starts the hold, so the plunge itself keeps it hidden)
    if ctx.presentation:
        if state.slide is not None or (phys == core.PHYS_FALLING and effective_crouch) or _icon_held():
            _hide_crouch_icon(pc)
        else:
            _show_crouch_icon(pc)
    if ctx.presentation:
        _settle_arms(pc)


def _note_air_speed(state, pawn) -> None:
    """Remember the fastest horizontal speed while crouch is held with no prior slide."""
    if state.slide is not None or state.slide_jump is not None:
        state.air_slide = None
        return
    try:
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
    except Exception:  # noqa: BLE001
        return
    speed = math.hypot(vx, vy)
    if speed < 1.0:
        return
    prev = state.air_slide
    if prev is not None and float(prev["speed"]) >= speed:
        return
    state.air_slide = {"dir": (vx / speed, vy / speed), "speed": speed}


def take_air_slide():
    """Hand the saved air speed to a slam landing, then clear it."""
    state = _state()
    link = state.air_slide
    state.air_slide = None
    return link


def _air_crouch_landing(state, pc, pawn) -> None:
    """Slide out of a sprint jump when crouch is held at the landing. A slide jump uses its own chain."""
    if state.slide is not None or state.slide_jump is not None:
        if state.slide_jump is not None:
            state.air_slide = None
        return
    if core.phys != core.PHYS_WALKING:
        return
    try:
        if int(pawn.Physics) != core.PHYS_WALKING:
            return
    except Exception:  # noqa: BLE001
        return
    # A slide that just ended is not a new landing. Holding crouch through that
    # ending used to start another slide on top of the one still tilting the gun.
    if state.suppress_crouch_until_release or not state.air_pressed:
        return
    if _crouch_held(pc) is True:
        state.crouch_down = True
    if not state.crouch_down:
        state.air_slide = None
        state.slam_bank = None
        return
    try:
        from . import slam as slam_mod

        if slam_mod._slam is not None:
            return
    except Exception:  # noqa: BLE001
        pass
    link = state.air_slide
    if link is None and state.slam_bank is not None:
        bx, by = float(state.slam_bank[0]), float(state.slam_bank[1])
        speed = math.hypot(bx, by)
        if speed > 1.0:
            link = {"dir": (bx / speed, by / speed), "speed": speed}
    state.air_slide = None
    state.slam_bank = None
    if link is None:
        return
    try:
        need = _walk_speed(pawn) * float(min_speed_slider.value) / 100.0
    except Exception:  # noqa: BLE001
        need = 1.0
    if float(link["speed"]) < need:
        return
    offer_landing(pc, pawn, link["dir"][0], link["dir"][1], float(link["speed"]), "air crouch")


def _wants_chain(state, pc) -> bool:
    """True only while the crouch key is down. The slide's pose is not a hold.

    The Pre-Sequel used to keep that pose after a let-go, so every slide jump
    landed in another slide. A missed key read is not a hold either.
    """
    del state
    return _crouch_held(pc) is True


def _remember_slide_jump(state, holding: bool, dx: float, dy: float, speed: float) -> None:
    """Save the jump. Arm a landing slide only when the crouch key is down right now."""
    link = {"dir": (float(dx), float(dy)), "speed": max(float(speed), 1.0), "at": core.clock}
    state.slide_jump = link
    state.chain_hold = bool(holding)
    state.chain = dict(link) if holding else None
    try:
        from .. import diagnostics

        diagnostics.event(
            "mm.slide.chain",
            holding=bool(holding),
            key=bool(holding),
            latch=bool(state.crouch_down),
        )
    except Exception:  # noqa: BLE001
        pass


def _update_chain_hold(state, held) -> None:
    """Keep the landing slide only while the crouch key is down.

    A missed key read (None) leaves the chain alone. A real release clears it,
    including a pose left over from the slide. Both games use that rule.
    """
    if held is True:
        state.crouch_down = True
    if state.slide_jump is None:
        return
    if held is True:
        state.chain_hold = True
        if state.chain is None:
            state.chain = dict(state.slide_jump)
        return
    if held is None and state.crouch_down and state.chain_hold:
        return
    state.chain = None
    state.chain_hold = False
    state.chain_was_air = False
    if held is False:
        state.crouch_down = False


def _slide_jump_blocks_landing(state) -> bool:
    """A slide jump does not use the normal landing slide. Only a held crouch key continues it."""
    link = state.slide_jump
    if link is None:
        return False
    try:
        return core.clock - float(link.get("at", -100.0)) < 3.0
    except Exception:  # noqa: BLE001
        return False


def _chain_air_ok(link) -> bool:
    """True once the slide jump has been airborne long enough to be a real cancel."""
    try:
        return core.clock - float(link.get("at", -100.0)) >= _CHAIN_MIN_AIR
    except Exception:  # noqa: BLE001
        return False


def chain_blocks_slam() -> bool:
    """True while a held slide-jump crouch is reserved for the landing slide."""
    return _state().chain is not None


def offer_landing(pc, pawn, dx: float, dy: float, speed: float, reason: str) -> bool:
    """Start a landing slide. Speed is the saved carry. Direction is where you are facing now."""
    state = _state()
    if not enabled_option.value or pawn is None or state.slide is not None:
        return False
    try:
        fx, fy = core.facing(pc)
        if fx != 0.0 or fy != 0.0:
            dx, dy = fx, fy
    except Exception:  # noqa: BLE001
        pass
    dx, dy = _unit_dir(float(dx), float(dy))
    if dx == 0.0 and dy == 0.0:
        return False
    speed = max(float(speed), 1.0)
    state.need_sprint = False
    state.suppress_crouch_until_release = False
    state.chain = None
    state.chain_was_air = False
    state.launch = None
    state.slam_bank = None
    state.air_slide = None
    _start(pc, pawn, reason, dx, dy, speed)
    return state.slide is not None


def try_consume_jump(pc, pawn) -> bool:
    """Active Slide owns the jump edge before Mantle/Double Jump/native Slam."""
    state = _state()
    if state.slide is None and not (
        state.ended is not None and core.clock - state.ended["at"] <= _JUMP_GRACE
    ):
        return False
    _ground_jump(pc, pawn)
    return True


def _note_sprint_jump(pc, pawn) -> None:
    """A fast jump with no slide keeps that run. Holding crouch then lands like a slide cancel.

    The crouch press in the air was the only thing that armed this, and that press
    is gone by the time you land. The slide cancel does not depend on it. This
    saves the same link at the moment of the jump, in both games. A later hold
    arms the chain. A release clears it. A walk that is too slow to slide does not.
    """
    state = _state()
    if not enabled_option.value or pawn is None or core.unusable(pawn):
        return
    if state.slide is not None or state.slide_jump is not None:
        return
    try:
        if int(pawn.Physics) != core.PHYS_WALKING:
            return
    except Exception:  # noqa: BLE001
        return
    try:
        vx = float(pawn.Velocity.X)
        vy = float(pawn.Velocity.Y)
    except Exception:  # noqa: BLE001
        return
    speed = math.hypot(vx, vy)
    try:
        need = _walk_speed(pawn) * float(min_speed_slider.value) / 100.0
    except Exception:  # noqa: BLE001
        need = 1.0
    if speed < max(need, 1.0):
        return
    holding = _crouch_held(pc) is True
    if holding:
        state.crouch_down = True
    _remember_slide_jump(
        state,
        holding,
        vx / speed,
        vy / speed,
        speed * float(jump_momentum_slider.value) / 100.0,
    )


def try_consume_sprint(pc, pawn) -> bool:
    """Active Slide owns the sprint edge before Surge; exits cleanly with carry."""
    state = _state()
    if state.slide is None:
        return False
    _end(pawn, "sprint", pc)
    try:
        if hasattr(pc, "BeginSprint"):
            pc.BeginSprint()
    except Exception:  # noqa: BLE001
        pass
    return True


def _authority_start(ctx, payload):
    if not enabled_option.value:
        return Reason.DISABLED, {}
    pawn = ctx.pawn
    if pawn is None or core.unusable(pawn):
        return Reason.NO_PAWN, {}
    # Remotes: host dict coasts CrouchedPct + entry direction (server_slide_enter).
    if ctx.role == ExecutionRole.REMOTE_AUTHORITY:
        try:
            pct = float(payload.get("crouched_pct", _JUSO_SLIDE_PCT) or _JUSO_SLIDE_PCT)
        except Exception:  # noqa: BLE001
            pct = _JUSO_SLIDE_PCT
        host_enter_juso(ctx, pct)
        return Reason.OK, {"active": True, "crouched_pct": pct}

    reason = str(payload.get("reason", "request"))

    def start():
        state = _state()
        if state.slide is not None or core.busy not in (None, "slide"):
            return False
        try:
            pawn.ShouldCrouch(True)
        except Exception:  # noqa: BLE001
            pass
        _start(ctx.controller, pawn, reason)
        return _state().slide is not None

    if not core.execute(ctx, start):
        return Reason.BUSY, _snapshot(ctx)
    action_id = authority.allocate_action(ctx, "slide")
    _state(ctx).action_id = action_id
    response = _snapshot(ctx)
    response["action"] = action_id
    return Reason.OK, response


def _authority_input(ctx, payload):
    kind = payload.get("kind")
    pawn = ctx.pawn
    if pawn is None:
        return Reason.NO_PAWN, {}
    if kind == "jump":
        accepted = core.execute(ctx, try_consume_jump, ctx.controller, pawn)
        return (Reason.OK if accepted else Reason.INVALID_INPUT), _snapshot(ctx)
    if kind == "sprint":
        accepted = core.execute(ctx, try_consume_sprint, ctx.controller, pawn)
        return (Reason.OK if accepted else Reason.INVALID_INPUT), _snapshot(ctx)
    return Reason.UNSUPPORTED, {}


def _authority_tick(ctx, frame) -> None:
    """Joiner slides are already coasted from `_HOST_SLIDES` on the host's own tick.

    Running `_tick` here treated the joiner's server pawn like a local keyboard.
    That copy has no crouch keys, so the slide-cancel block stuck on, `DuckPressed`
    was swallowed, and `core.begin("slide")` cancelled their dash. `frame` is unused
    because this tick must not run the input machine.
    """
    del ctx, frame


def _authority_cancel(ctx, reason: str) -> None:
    def cancel():
        if _state().slide is not None:
            _end(ctx.pawn, reason, ctx.controller)
        _stop_carry()

    core.execute(ctx, cancel)


def _snapshot(ctx) -> dict:
    state = _state(ctx)
    slide = state.slide
    return {
        "active": slide is not None,
        "action": state.action_id,
        "speed": float(slide["speed"]) if slide is not None else 0.0,
        "start": float(slide["start"]) if slide is not None else 0.0,
        "elapsed": float(slide["elapsed"]) if slide is not None else 0.0,
        "cap": float(slide.get("cap", _MAX_FLAT_S)) if slide is not None else 0.0,
        "direction": list(slide["dir"]) if slide is not None else [0.0, 0.0],
        "suppress_crouch": state.suppress_crouch_until_release,
    }


def _presentation(event: str, payload: dict) -> None:
    if event == "desync":
        hudfx.slide_end()
        return
    state_payload = payload.get("state", payload)
    if not isinstance(state_payload, dict):
        return
    local = core.local_context()
    # The owning client already draws from its own decay. A host echo of that
    # same slide arrives late and with a different speed, which jitters the bar.
    if local is not None and _state(local).slide is not None:
        return
    if local is not None and core.clock - _state(local).last_end < 0.35:
        hudfx.slide_end()
        return
    if state_payload.get("active") and indicator_option.value:
        speed = float(state_payload.get("speed", 0.0))
        start = max(1.0, float(state_payload.get("start", speed)))
        elapsed = float(state_payload.get("elapsed", 0.0))
        cap = float(state_payload.get("cap", 0.0))
        if cap > 0.0:
            hudfx.slide_momentum(_slide_fill(elapsed, cap, speed, start, 0.0))
        else:
            hudfx.slide_momentum(max(0.0, min(1.0, speed / start)))
    else:
        hudfx.slide_end()
    if event == "accept" and payload.get("operation") == "jump" and indicator_option.value:
        hudfx.slide_launch()


@hook("WillowGame.WillowPawn:DoJump", Type.PRE)
def _pre_do_jump(obj, _args, _ret, _func):
    """Slide owns the jump edge before native jump/Slam can consume a crouch-latched press."""
    ctx = REGISTRY.resolve_pawn(obj)
    if ctx is None:
        return None
    if not ctx.authority:
        return None
    if core.downed(obj):
        return Block
    if core.execute(ctx, try_consume_jump, ctx.controller, obj):
        # _ground_jump already told the host the slide ended and sent the launch.
        # A second exit here arrives after the launch and stands the body up.
        return Block
    # No slide under this jump. Keep the run so a crouch held in the air lands
    # the same way a slide cancel does.
    core.execute(ctx, _note_sprint_jump, ctx.controller, obj)
    return None


@hook("WillowGame.WillowPlayerController:DuckPressed", Type.PRE)
def _pre_duck_pressed(obj, _args, _ret, _func):
    """While crouch is suppressed after off-cliff/jump exit, block native Slam re-arm."""
    ctx = REGISTRY.resolve_controller(obj)
    # The listen server also receives the joiner's crouch. Blocking it from the
    # server-side chain (which never sees their keyboard) made every later move
    # get corrected back to vanilla. The owning client still blocks its own press.
    if ctx is None or not ctx.local:
        return None
    state = _state(ctx)
    if state.slide is not None:
        return Block
    # A slide-jump chain stays blocked, so that hold is not a new slam.
    # A finished slide must not block the next press. Doing that made the first slide the last.
    if state.chain is not None:
        return Block
    state.suppress_crouch_until_release = False
    state.crouch_down = True
    # A new crouch press in the air is a slam. Keep the speed so the landing can
    # become a slide if the key is still held when they hit the ground.
    try:
        pawn = ctx.pawn
        if pawn is not None and int(pawn.Physics) == core.PHYS_FALLING:
            state.air_pressed = True
            state.slam_bank = (float(pawn.Velocity.X), float(pawn.Velocity.Y))
            _note_air_speed(state, pawn)
    except Exception:  # noqa: BLE001
        pass
    return None


@hook("WillowGame.WillowPlayerController:DuckReleased", Type.PRE)
def _pre_duck_released(obj, _args, _ret, _func):
    """Key up. The crouched pose stays during a slide, so this is the release signal."""
    ctx = REGISTRY.resolve_controller(obj)
    if ctx is None or not ctx.local:
        return None
    state = _state(ctx)
    if core.clock < state.ignore_release_until:
        return None
    state.crouch_down = False
    state.air_pressed = False
    state.air_slide = None
    state.suppress_crouch_until_release = False
    state.slide_queued = False
    if state.chain_hold:
        state.chain = None
        state.chain_hold = False
    return None


@hook("WillowGame.WillowPlayerPawn:Landed", Type.POST)
def _post_landed(obj, _args, _ret, _func):
    """After a real slam, a held crouch slides away with the speed from before the dive."""
    ctx = REGISTRY.resolve_pawn(obj)
    if ctx is None or not ctx.authority or not ctx.local:
        return
    def go() -> None:
        _air_crouch_landing(_state(ctx), ctx.controller, ctx.pawn)

    core.execute(ctx, go)


@hook("WillowGame.WillowPlayerController:BeginSprint", Type.PRE)
def _pre_begin_sprint(obj, _args, _ret, _func):
    """Active Slide owns sprint before native sprint stutter or Surge."""
    from .. import coop_rpc

    ctx = REGISTRY.resolve_controller(obj)
    if ctx is None:
        return None
    state = _state(ctx)
    if state.slide is None:
        return None
    # The sprint already held when the slide began repeats BeginSprint. That is not a cancel.
    # After that key comes up, the next press ends the slide now. The leftover time is not a wait.
    try:
        from . import slam

        sprint_down = slam._physical_down(_sprint_key_names(ctx.controller))
    except Exception:  # noqa: BLE001
        sprint_down = None
    if not _sprint_press_is_cancel(state.slide, state.prev_sprint, sprint_down):
        return None
    if not ctx.authority:
        return None
    if core.execute(ctx, try_consume_sprint, ctx.controller, ctx.pawn):
        if coop_rpc.is_requester(ctx):
            coop_rpc.call_host(coop_rpc.server_slide_exit)
        return Block
    return None


@hook("WillowGame.WillowPlayerController:PlayerWalking.PlayerMove", Type.POST)
def _post_player_move(obj, args, _ret, _func):
    """Re-assert a slide after PlayerMove. A released movement key brakes first."""
    ctx = REGISTRY.resolve_controller(obj)
    if ctx is None or not ctx.authority or ctx.pawn is None:
        return
    state = _state(ctx)
    hosted = _HOST_SLIDES.get(ctx.key.player_id)
    jump = _HOST_JUMPS.get(ctx.key.player_id)
    if state.slide is None and hosted is None and jump is None:
        return

    def assert_crouch() -> None:
        slide = state.slide
        launched = _HOST_JUMPS.get(ctx.key.player_id)
        if slide is None and launched is not None:
            _push_slide_jump(
                ctx.pawn,
                launched["vx"],
                launched["vy"],
                launched["vz"],
                force_z=False,
            )
            return
        if slide is not None:
            if slide.get("timed") and "cp" in slide:
                speed_percent = float(slide.get("speed_percent", 100.0))
                ctx.pawn.CrouchedPct = float(slide["cp"]) * _speed_scale(speed_percent)
                # Joiner: PlayerMove already braked the released key. Put the coast back.
                dx, dy = slide.get("dir", (0.0, 0.0))
                _coast_slide(ctx.pawn, dx, dy, float(slide.get("speed", 0.0)))
            else:
                _set_crouch_limit(ctx.pawn, slide["speed"])
                # PlayerMove already braked along the old momentum. Put the new facing back.
                if _slide_fresh(slide):
                    dx, dy = slide.get("dir", (0.0, 0.0))
                    _coast_slide(ctx.pawn, dx, dy, float(slide.get("speed", 0.0)))
            return
        # Host replay of that same move brakes the server pawn and would correct
        # the joiner to a stop. The slide lives in _HOST_SLIDES, not slide state.
        if hosted is None:
            return
        speed_percent = float(hosted.get("speed_percent", 100.0))
        try:
            ctx.pawn.CrouchedPct = float(hosted["cp"]) * _speed_scale(speed_percent)
        except Exception:  # noqa: BLE001
            pass
        dx, dy = hosted.get("dir", (0.0, 0.0))
        _coast_slide(
            ctx.pawn,
            dx,
            dy,
            _coast_velocity(float(hosted["cp"]), _walk_speed(ctx.pawn), speed_percent),
        )

    core.execute(ctx, assert_crouch)


def on_enable() -> None:
    core.register(
        "slide",
        tick=_tick,
        ground=_ground_jump,
        cancel=_cancel,
        priority=20,
        events={"player_hit": _on_player_hit, "slam_impact": _hold_crouch_icon},
    )
    authority.register_feature(
        "slide",
        authority.FeatureController(
            start=_authority_start,
            input=_authority_input,
            tick=_authority_tick,
            cancel=_authority_cancel,
            snapshot=_snapshot,
        ),
    )
    network.register_presentation("slide", _presentation)


def on_disable() -> None:
    for ctx in REGISTRY.contexts():
        if ctx.authority:
            _authority_cancel(ctx, "mod disabled")
    authority.unregister_feature("slide")
    network.unregister_presentation("slide")
    try:
        _show_crouch_icon(core.get_pc_pawn()[0])
    except Exception:  # noqa: BLE001
        pass
    core.unregister("slide")


# Only these two are shown in the menu. Every other setting above is fixed at its tuned value
# (the author's settings) and is simply how the slide works; they stay as objects so the code
# reads one place, and can be put back in this list for tuning.
TUNING_OPTIONS = [
    boost_slider,
    friction_slider,
    slope_slider,
    steer_slider,
    min_speed_slider,
    max_speed_slider,
    landing_option,
    landing_window_slider,
    sprint_req_slider,
    back_cancel_option,
    jump_momentum_slider,
    jump_height_slider,
    carry_slider,
    shake_slider,
]
OPTIONS = [
    enabled_option,
    *core.settings(
        [audio_option, indicator_option, distance_slider, speed_slider, shake_slider, push_slider],
        "Fine-tune sliding.",
    ),
]
KEYBINDS = []
HOOKS = [
    _pre_do_jump,
    _pre_duck_pressed,
    _pre_duck_released,
    _pre_begin_sprint,
    _post_player_move,
    _post_landed,
]
