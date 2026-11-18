"""Slide: crouch while sprinting (or land from a jump with crouch on) to slide.

How it starts
  * Press crouch while sprinting on the ground, moving at least "Min Slide Speed".
  * Press crouch in the air no more than "Slide Landing Window (ms)" before touching down, then
    land with crouch on while moving forward at least "Min Slide Speed" ("Slide From Landing").

How it moves
  The slide starts at the speed you had going in plus "Slide Boost (%)" (capped at "Max Slide
  Speed"), so the more momentum you bring, the further you go. Every tick it loses "Slide
  Friction" units/s of speed; slopes add or remove speed ("Slope Effect (%)": downhill keeps you
  going, uphill stops you sooner). The direction is the one you entered with; the movement keys
  can turn it a little ("Slide Steering", degrees per second), never sideways at will.

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

from mods_base import BoolOption, SliderOption
from unrealsdk import logging

from .. import camera, core, fx, hudfx, tracing

enabled_option = BoolOption("Slide Enabled", True, "On", "Off", description="Turn slide on or off.")

boost_slider = SliderOption(
    "Slide Boost (%)", value=100, min_value=0, max_value=100, step=5, is_integer=True,
    description="Extra speed added to your momentum when a slide starts.",
)
friction_slider = SliderOption(
    "Slide Friction", value=300, min_value=100, max_value=3000, step=50, is_integer=True,
    description="How quickly a slide loses speed (units per second, every second). Lower slides further.",
)
slope_slider = SliderOption(
    "Slope Effect (%)", value=200, min_value=0, max_value=300, step=10, is_integer=True,
    description="How much hills matter: downhill keeps a slide going, uphill stops it sooner. 0 = flat everywhere.",
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
    "Max Slide Speed (%)", value=350, min_value=100, max_value=500, step=10, is_integer=True,
    description="The fastest a slide can start, as a percentage of walking speed.",
)
landing_option = BoolOption(
    "Slide From Landing", True, "On", "Off",
    description="Landing with crouch on while moving forward fast enough starts a slide.",
)
landing_window_slider = SliderOption(
    "Slide Landing Window (ms)", value=700, min_value=0, max_value=1500, step=50, is_integer=True,
    description="With Slide From Landing: how long before touching down you can press crouch and "
                "still slide on landing.",
)
sprint_req_slider = SliderOption(
    "Sprint Before Next Slide (ms)", value=200, min_value=0, max_value=3000, step=50, is_integer=True,
    description="After a slide, how long you must sprint before you can slide again. 0 = no wait.",
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
    "Slide Camera Push (%)", value=80, min_value=0, max_value=200, step=10, is_integer=True,
    description="The view tilts back while you slide, more the faster you go, and eases level as the slide slows. Your aim moves with it and returns exactly. 0 = off.",
)

shake_slider = SliderOption(
    "Slide Camera Shake (%)", value=30, min_value=0, max_value=200, step=10, is_integer=True,
    description="A light camera bob and tilt while sliding, strongest at the start and fading as you "
                "slow down. Does not move your aim. 0 = off.",
)
distance_slider = SliderOption(
    "Slide Distance (%)", value=80, min_value=25, max_value=300, step=5, is_integer=True,
    description="How far a slide carries you on flat ground. 100 = the original distance, 200 = twice as far.",
)
indicator_option = BoolOption(
    "Slide Indicator", True, "On", "Off",
    description="A bar below the crosshair shows how much momentum your slide has left to carry into a slide jump.",
)
audio_option = BoolOption("Slide Audio Effect", True, "On", "Off", description="Adds a sound effect when sliding.")

scrape_variant_slider = SliderOption(
    "Slide Sound Variant", value=1, min_value=1, max_value=12, step=1, is_integer=True,
    description="Temporary: which footstep sound the slide scrape is made from. The console lists them the first time you slide.",
)

scrape_rate_slider = SliderOption(
    "Slide Sound Rate (%)", value=70, min_value=25, max_value=300, step=5, is_integer=True,
    description="Temporary: how fast the scrape's steps repeat (they start fast and slow down with the slide). Higher = faster.",
)

# Sound played as a slide starts (an AkEvent path). Empty = no sound yet.
# The stalker's scraping step: gritty and short, like boots skidding into a slide. fx.play_sound
# loads its bundle (Ake_Mon_Stalker) itself when the map doesn't have it.
SOUND = "Ake_Mon_Stalker.Ak_Play_Mon_Stalker_Step_Scrape"

_DEBUG = False

_FALLBACK_GRAVITY = 1000.0   # units/s^2 along a slope at 100% if the world's gravity can't be read
_FORWARD_DOT = 0.5           # landing slide: moving at least this much along where you look
_STALL_TICKS = 3
_STALL_RATIO = 0.10
_MAX_TIME = 6.0              # safety net, seconds

_JUMP_GRACE = 0.2           # seconds: a jump this soon after the slide ended still launches it
_HIT_GRACE = 0.4            # seconds after you're hit that a hit's push or flinch can't end the slide
_hit_at = -100.0


def _on_player_hit(**_kw) -> None:
    global _hit_at
    _hit_at = core.clock


_FLOOR_NEAR = 60.0          # units: a floor this close below still counts as "on the ground" after a hit


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
    return 0.0 <= core.clock - _hit_at < _HIT_GRACE

_slide: dict | None = None
_last_end = -100.0
_need_sprint = False      # a slide has ended: sprint "Sprint Before Next Slide" before the next
_sprint_run = 0.0         # seconds of unbroken sprinting so far
_ended: dict | None = None   # {"dir", "speed", "at"} of the slide that just ended (not by a jump)
_prev_crouch = False
_prev_sprint = False
_prev_phys = -1
_prev_speed = 0.0
_crouch_pressed_at = -100.0   # clock time crouch was last switched on (for the landing window)
# CrouchedPct bookkeeping: the game's own value, and the raised value we last wrote.
_cp_base = None
_cp_written = None


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


def _set_crouch_limit(pawn, speed) -> None:
    """Raise the crouch speed limit so the game lets the slide go `speed` (None = restore)."""
    global _cp_base, _cp_written
    try:
        current = float(pawn.CrouchedPct)
    except Exception:  # noqa: BLE001
        return
    if speed is None:
        if _cp_written is not None and abs(current - _cp_written) < 1e-4:
            pawn.CrouchedPct = _cp_base          # still ours: put the game's value back
        _cp_base = _cp_written = None
        return
    if _cp_written is None or abs(current - _cp_written) > 1e-4:
        _cp_base = current                       # first slide tick, or the game changed it
    target = max(_cp_base, speed / _walk_speed(pawn) * 1.05)
    if abs(current - target) > 1e-4:
        pawn.CrouchedPct = target
    _cp_written = target


def _crouch_walk_speed(pawn) -> float:
    base = _cp_base
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
_icon_alpha = None   # the icon's own opacity before the slide (a number)


def _hide_crouch_icon(pc) -> None:
    global _icon_alpha
    if pc is None:
        return
    if _icon_alpha is None:
        a = fx.clip_alpha(pc, CROUCH_ICON)
        _icon_alpha = a if a is not None and a > 0.0 else 100.0
    fx.set_clip_alpha(pc, CROUCH_ICON, 0.0)       # every slide tick (the HUD rebuilds after menus)


_ICON_HOLD_S = 2.0          # the crouch icon stays hidden this long after a slide or a slam...
_ICON_IGNORE_S = 0.3        # ...unless crouch is pressed again in it (after this much)
_icon_hold = (-100.0, -100.0)  # (from, until) clock times


def _hold_crouch_icon(**_kw) -> None:
    global _icon_hold
    _icon_hold = (core.clock, core.clock + _ICON_HOLD_S)


def _icon_held() -> bool:
    start, until = _icon_hold
    # (a crouch flicker in the first moments, as the slam stands you up, is not a press)
    return core.clock < until and _crouch_pressed_at <= start + _ICON_IGNORE_S


def _show_crouch_icon(pc) -> None:
    global _icon_alpha
    if _icon_alpha is None:
        return
    if pc is not None:
        fx.set_clip_alpha(pc, CROUCH_ICON, _icon_alpha)
    _icon_alpha = None


# ---- start / end -------------------------------------------------------------------------


def _start(pc, pawn, reason: str) -> None:
    global _slide
    vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
    speed = math.hypot(vx, vy)
    if speed < 1.0:
        return
    walk = _walk_speed(pawn)
    start_speed = min(speed * (1.0 + boost_slider.value / 100.0), walk * max_speed_slider.value / 100.0)
    start_speed = max(start_speed, speed)        # never slower than you came in
    core.begin("slide")
    loc = (float(pawn.Location.X), float(pawn.Location.Y))
    _stop_carry()                                # a new slide replaces any carry still running
    _slide = {"dir": (vx / speed, vy / speed), "speed": start_speed, "start": start_speed,
              "entry": speed,
              "elapsed": 0.0, "last": loc, "commanded": 0.0, "stalled": 0}
    try:
        pawn.ShouldCrouch(True)                  # make sure the body is down for the slide
    except Exception:  # noqa: BLE001
        pass
    _set_crouch_limit(pawn, start_speed)
    _hide_crouch_icon(pc)                        # straight away, so it never flashes up
    global _scrape_next
    _scrape_next = 0.0  # the scrape starts with the slide
    _log(f"start ({reason}): {speed:.0f} -> {start_speed:.0f} u/s, walk {walk:.0f}")


def _end(pawn, reason: str) -> None:
    global _slide, _last_end, _ended, _need_sprint, _sprint_run
    if _slide is None:
        return
    _ended = {"dir": _slide["dir"], "speed": _slide["speed"], "at": core.clock}
    if reason in _CARRY_REASONS:
        _start_carry(_slide["speed"], _slide["entry"])
    _slide = None
    _last_end = core.clock
    hudfx.slide_end()
    _hold_crouch_icon()
    _need_sprint, _sprint_run = True, 0.0
    core.end("slide")
    if pawn is not None:
        _set_crouch_limit(pawn, None)
    _clear_shake(core.get_pc_pawn()[0], pawn)
    _log(f"end ({reason})")


def _cancel() -> None:
    """Another movement action is taking over."""
    _end(core.get_pc_pawn()[1], "interrupted")


# ---- momentum carry ---------------------------------------------------------------------
# Standing up or jumping out of a slide keeps its speed for a while: the top speed (a
# GroundSpeed multiplier, applied by core together with Sprint Surge) starts at the slide's
# speed relative to the speed you had going in, and eases back to 1x.
_CARRY_REASONS = ("stood up", "jump", "left the ground")
_carry: dict | None = None    # {"from": multiplier, "at": clock, "dur": seconds}


def _start_carry(end_speed: float, entry_speed: float) -> None:
    global _carry
    dur = carry_slider.value / 1000.0
    ratio = end_speed / max(1.0, entry_speed)
    if dur <= 0.0 or ratio <= 1.0:
        _stop_carry()
        return
    _carry = {"from": ratio, "at": core.clock, "dur": dur}
    core.set_speed_mult("slide", ratio)
    _log(f"momentum carry x{ratio:.2f} for {dur:.1f}s")


def _stop_carry() -> None:
    global _carry
    _carry = None
    core.set_speed_mult("slide", None)


_CARRY_STOP = 0.2   # on the ground below this fraction of walking speed = stopped: carry ends


def _update_carry(pawn) -> None:
    if _carry is None:
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
    t = (core.clock - _carry["at"]) / _carry["dur"]
    if t >= 1.0:
        _stop_carry()
        return
    ease = t * t * (3.0 - 2.0 * t)
    core.set_speed_mult("slide", 1.0 + (_carry["from"] - 1.0) * (1.0 - ease))


# ---- jumping out of a slide -------------------------------------------------------------


_launch: dict | None = None   # a slide jump being made to stick: {"v": (x, y, z), "until": clock}
_LAUNCH_HOLD = 0.15           # seconds the launch is re-applied if the game pulls you back down


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
    pawn.Velocity.X = vx
    pawn.Velocity.Y = vy
    pawn.Velocity.Z = vz
    return True


def _ground_jump(pc, pawn) -> None:
    """Jump pressed on the ground. During a slide (or just after the game stood you up
    from one) this launches a jump that keeps the slide's speed and direction, instead of
    the game's crouched "jump = stand up"."""
    global _ended, _launch
    if _slide is not None:
        dx, dy = _slide["dir"]
        speed = _slide["speed"]
        _end(pawn, "jump")
    elif _ended is not None and core.clock - _ended["at"] <= _JUMP_GRACE:
        dx, dy = _ended["dir"]
        speed = _ended["speed"]
    else:
        _log("jump pressed: no slide running")
        return
    _ended = None
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
        _launch = {"v": v, "until": core.clock + _LAUNCH_HOLD}
        core.emit("slide_jump")
        if indicator_option.value:
            hudfx.slide_launch()
    _log(f"slide jump at {speed:.0f} u/s (airborne: {ok})")


def _hold_launch(pc, pawn) -> None:
    """For a moment after a slide jump: if the game put the pawn back on the ground (its own
    crouched-jump handling), launch it again."""
    global _launch
    if _launch is None:
        return
    if pawn is None or core.clock > _launch["until"]:
        _launch = None
        return
    if core.phys == core.PHYS_FALLING:
        try:
            if float(pawn.Velocity.Z) > 0.0:
                return                         # rising: it stuck
        except Exception:  # noqa: BLE001
            return
    _log(f"slide jump re-applied (physics {core.phys})")
    try:
        _launch_now(pc, pawn, *_launch["v"])
    except Exception as e:  # noqa: BLE001
        _warn(f"slide jump re-apply failed: {e!r}")
        _launch = None


# ---- camera shake ---------------------------------------------------------------------
# A light bob and tilt while sliding (applied by camera.py, shared with the air dash). Roll never
# changes where you aim. Strength follows the slide's speed.
_SHAKE_EYE = 1.6        # eye-height bob at 100%, units
_SHAKE_ROLL = 0.7       # tilt at 100%, degrees
_shake_t = 0.0


def _apply_shake(pc, pawn, dt, strength) -> None:
    global _shake_t, _push_want
    _push_want = max(0.0, min(1.0, strength))   # the camera push follows the slide's speed
    amount = shake_slider.value / 100.0 * max(0.0, min(1.0, strength))
    if amount <= 0.0:
        return
    _shake_t += dt
    bob, tilt = camera.wave(_shake_t)
    camera.request("slide", eye=bob * _SHAKE_EYE * amount, roll=tilt * _SHAKE_ROLL * amount)


_PUSH = 3.0             # camera push (view tilts back) at 100%, degrees
_PUSH_RISE = 0.12       # seconds to tilt back as a slide starts...
_PUSH_FALL = 0.30       # ...and to come back level as it slows or ends
_push_want = 0.0        # this frame: how far back, 0..1 (set while sliding)
_push_level = 0.0       # eased


def _update_push(dt) -> None:
    """Ease the push toward what the slide asked for last frame (0 once it has ended)."""
    global _push_want, _push_level
    want = _push_want
    _push_want = 0.0
    if want > _push_level:
        _push_level = min(want, _push_level + dt / _PUSH_RISE)
    else:
        _push_level = max(want, _push_level - dt / _PUSH_FALL)
    amount = push_slider.value / 100.0
    if _push_level > 0.0 and amount > 0.0:
        e = _push_level * _push_level * (3.0 - 2.0 * _push_level)
        camera.request("slide_push", pitch=_PUSH * amount * e)


def _clear_shake(pc, pawn) -> None:
    """Slide ended: stop asking (camera.py takes the offsets out)."""
    global _shake_t
    _shake_t = 0.0


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
    dx, dy = _slide["dir"]
    want = math.atan2(ay, ax)
    have = math.atan2(dy, dx)
    diff = (want - have + math.pi) % (2.0 * math.pi) - math.pi
    if abs(diff) > math.radians(100):
        return                                   # pulling backwards: no turn (friction does it)
    turn = max(-rate * dt, min(rate * dt, diff))
    a = have + turn
    _slide["dir"] = (math.cos(a), math.sin(a))


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
_scrape_next = 0.0
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


def _scrape(pc, pawn, strength) -> None:
    """One step of the scrape when it is due; steps come faster the faster you slide."""
    global _scrape_next, _scrape_told
    if not audio_option.value or core.clock < _scrape_next:
        return
    names = _scrape_names()
    if not names:
        return
    k = max(1, min(len(names), int(scrape_variant_slider.value))) - 1
    if _DEBUG and _scrape_told != k + 1:
        _scrape_told = k + 1
        listing = ", ".join(f"{i + 1}={n}" for i, n in enumerate(names[:12]))
        logging.warning(f"[Slide] scrape sound: variant {k + 1} = {names[k]}  (all: {listing})")
    fx.set_switch(pawn, _SCRAPE_SURFACE)  # always the sand / dirt version, whatever you slide on
    fx.play_named(pc, pawn, (names[k],))
    strength = max(0.0, min(1.0, strength))
    gap = _SCRAPE_SLOW + (_SCRAPE_FAST - _SCRAPE_SLOW) * strength
    _scrape_next = core.clock + gap * 100.0 / max(1, scrape_rate_slider.value)


def _run(pc, pawn, dt) -> None:
    s = _slide
    if core.unusable(pawn):
        _end(pawn, "vehicle or dead")
        return
    if core.phys != core.PHYS_WALKING:
        if (core.phys == core.PHYS_FALLING and _hit_recently() and _launch is None
                and _floor_below(pawn)):                 # (knocked loose, not off a ledge)
            # a hit's push lifted you off the floor: put you back on it and keep sliding
            try:
                pawn.Velocity.Z = min(float(pawn.Velocity.Z), 0.0)
                pawn.Physics = core.PHYS_WALKING
            except Exception:  # noqa: BLE001
                _end(pawn, "left the ground")
                return
        else:
            _end(pawn, "left the ground")            # jumped / fell: velocity is kept
            return
    if not _crouching(pc, pawn):
        if _hit_recently():
            try:                                     # a hit's flinch stood you up: crouch again
                pawn.ShouldCrouch(True)
            except Exception:  # noqa: BLE001
                pass
        else:
            _end(pawn, "stood up")
            return

    x, y = float(pawn.Location.X), float(pawn.Location.Y)
    dx, dy = s["dir"]
    if s["elapsed"] > 0.0 and s["commanded"] > 0.0:
        moved = (x - s["last"][0]) * dx + (y - s["last"][1]) * dy
        if _hit_recently():
            s["stalled"] = 0                         # a hit's push isn't a wall
        else:
            s["stalled"] = s["stalled"] + 1 if moved < _STALL_RATIO * s["commanded"] else 0
    s["last"] = (x, y)
    s["elapsed"] += dt
    if s["stalled"] >= _STALL_TICKS:
        _end(pawn, "blocked")
        return
    if s["elapsed"] > _MAX_TIME * max(1.0, distance_slider.value / 100.0):
        _end(pawn, "timed out")
        return

    if back_cancel_option.value and _pressing_back(pc, pawn):
        _end(pawn, "moved back")                 # stays crouched; the game slows you to crouch speed
        return
    _steer(pc, pawn, dt)
    dx, dy = s["dir"]

    # speed: friction, plus gravity along the floor (the floor's tilt toward the slide direction)
    accel = -float(friction_slider.value) * 100.0 / max(distance_slider.value, 1)
    if slope_slider.value:
        try:
            n = pawn.Floor
            accel += _gravity(pc) * (float(n.X) * dx + float(n.Y) * dy) * slope_slider.value / 100.0
        except Exception:  # noqa: BLE001
            pass
    walk = _walk_speed(pawn)
    s["speed"] = min(s["speed"] + accel * dt, walk * max_speed_slider.value / 100.0)
    if s["speed"] <= _crouch_walk_speed(pawn):
        _end(pawn, "slowed to crouch speed")      # stays crouched, the game takes over
        return

    _set_crouch_limit(pawn, s["speed"])
    if indicator_option.value:
        low = _crouch_walk_speed(pawn)
        hudfx.slide_momentum((s["speed"] - low) / max(1.0, s["start"] - low))
    else:
        hudfx.slide_end()
    s["commanded"] = s["speed"] * dt
    pawn.Velocity.X = dx * s["speed"]
    pawn.Velocity.Y = dy * s["speed"]
    try:                                          # "accelerating" along the slide, so no braking
        rate = float(pawn.AccelRate)
        pawn.Acceleration.X = dx * rate
        pawn.Acceleration.Y = dy * rate
    except Exception:  # noqa: BLE001
        pass
    _apply_shake(pc, pawn, dt, s["speed"] / max(1.0, s["start"]))
    _scrape(pc, pawn, s["speed"] / max(1.0, s["start"]))


def _tick(pc, pawn, dt) -> None:
    global _prev_crouch, _prev_sprint, _prev_phys, _prev_speed
    _update_push(dt)
    _hold_launch(pc, pawn)
    _update_carry(pawn)
    if _slide is not None:
        if pawn is None or not enabled_option.value:
            _end(pawn, "pawn gone or slide disabled")
        else:
            _run(pc, pawn, dt)
    if pawn is None or core.unusable(pawn):
        _show_crouch_icon(pc)
        _prev_crouch = _prev_sprint = False
        _prev_phys, _prev_speed = -1, 0.0
        return

    crouch = _crouching(pc, pawn)
    global _crouch_pressed_at
    if crouch and not _prev_crouch:
        _crouch_pressed_at = core.clock
    sprint = _flag(pawn, "bIsSprinting")
    phys = core.phys
    # sprint requirement after a slide: unbroken sprinting on the ground unlocks the next one
    global _need_sprint, _sprint_run
    if _need_sprint:
        if sprint and phys == core.PHYS_WALKING and _slide is None:
            _sprint_run += dt
            if _sprint_run >= sprint_req_slider.value / 1000.0:
                _need_sprint = False
        elif not (_prev_sprint and crouch and not _prev_crouch):   # (crouch press ends sprint)
            _sprint_run = 0.0
    try:
        speed = core.hspeed(pawn)
    except Exception:  # noqa: BLE001
        speed = 0.0

    if (_slide is None and enabled_option.value and core.busy is None
            and (not _need_sprint or sprint_req_slider.value <= 0)
            and phys == core.PHYS_WALKING):
        need = _walk_speed(pawn) * min_speed_slider.value / 100.0
        # 1) crouch pressed while sprinting (sprint may already be cancelled this tick)
        if crouch and not _prev_crouch and (sprint or _prev_sprint) and max(speed, _prev_speed) >= need:
            _start(pc, pawn, "crouch while sprinting")
        # 2) landed with crouch on, moving forward fast enough
        elif (landing_option.value and crouch and _prev_phys == core.PHYS_FALLING
              and core.clock - _crouch_pressed_at <= landing_window_slider.value / 1000.0 + dt
              and max(speed, _prev_speed) >= need):
            try:
                fx_, fy_ = core.facing(pc)
                vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
                fwd = (vx * fx_ + vy * fy_) / max(1.0, math.hypot(vx, vy))
            except Exception:  # noqa: BLE001
                fwd = 0.0
            if fwd >= _FORWARD_DOT:
                _start(pc, pawn, "landing")

    _prev_crouch, _prev_sprint, _prev_phys, _prev_speed = crouch, sprint, phys, speed
    # crouch icon: hidden while sliding, while crouch is on in the air (so a jump into a landing
    # slide never shows it), and for _ICON_HOLD_S after a slide or a slam unless you press crouch
    # again; shown again otherwise
    # (core.busy == "slam": on the frame you land a slam this runs before the slam's own impact,
    # which is what starts the hold, so the plunge itself keeps it hidden)
    if (_slide is not None or (phys == core.PHYS_FALLING and crouch) or core.busy == "slam"
            or _icon_held()):
        _hide_crouch_icon(pc)
    else:
        _show_crouch_icon(pc)


def on_enable() -> None:
    global _slide, _last_end, _prev_crouch, _prev_sprint, _prev_phys, _prev_speed, _cp_base, _cp_written
    global _need_sprint, _sprint_run, _push_want, _push_level
    _need_sprint, _sprint_run = False, 0.0
    _push_want = _push_level = 0.0
    _slide = None
    _last_end = -100.0
    _prev_crouch = _prev_sprint = False
    _prev_phys, _prev_speed = -1, 0.0
    _cp_base = _cp_written = None
    global _ended, _crouch_pressed_at, _launch, _shake_t
    _crouch_pressed_at = -100.0
    _launch = None
    _shake_t = 0.0
    _stop_carry()
    _ended = None
    global _icon_hold, _hit_at
    _icon_hold = (-100.0, -100.0)
    _hit_at = -100.0
    core.register("slide", tick=_tick, ground=_ground_jump, cancel=_cancel, priority=20,
                  events={"slam_impact": _hold_crouch_icon, "player_hit": _on_player_hit})


def on_disable() -> None:
    try:
        _end(core.get_pc_pawn()[1], "mod disabled")
    except Exception:  # noqa: BLE001
        pass
    _stop_carry()
    _show_crouch_icon(core.get_pc_pawn()[0])
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
    *core.settings([audio_option, indicator_option, distance_slider], "Fine-tune sliding."),
]
# Fixed (not in the menu): Slide Sound Variant 1, Slide Sound Rate 70%, Slide Camera Push 80%.
KEYBINDS = []
HOOKS = []
