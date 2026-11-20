"""Mantle: jump near a ledge to pull yourself up onto it.

How it works
  A mantle only targets the ledge you are LOOKING at. Look traces go out from your eyes along
  the crosshair, then 10 and 20 degrees below it (so a low obstacle ahead is found while you
  look at the horizon). The first one that lands on a ledge wins:

    1. Look:        the trace hits either the wall face, or the top of the ledge (then a
                    flat trace finds the wall under its edge). The wall must be within 160
                    units and roughly facing you.
    2. Top check:   a trace straight down just behind the wall face finds the top of the
                    ledge. It has to be between the minimum height and the max height above
                    your feet, flat enough to stand on.
    3. Room check:  traces up from the ledge (centre, left and right) for headroom, and
                    along the wall for anything overhead.

  If all pass, gravity is switched off and the pawn follows a timed curve up the wall and
  over the lip. The climb time scales with the ledge height (and a far start gets extra time),
  the motion going in is blended into the climb, and at the top you are handed back to walking
  physics with forward momentum, so you run straight on. The camera dips as you grab, rises as
  you pull up and tilts slightly during the climb.

Vault
  Pressing jump on the ground while moving into a low obstacle (up to Vault Max Height)
  climbs straight onto it, with no jump first. Taller ledges still need a jump, then a
  press in the air (or Auto Mantle).

Seamless-feel features
  * Jump buffering: pressing jump slightly BEFORE a ledge is in reach is remembered for
    the jump buffer (250 ms); the mod keeps checking and climbs as soon as the ledge is
    reachable.
  * Auto Mantle only triggers while you are actually moving into the wall.
  * Starting a mantle cancels an air dash in progress (shared "busy" flag in core.py).
  * After an air dash (only with Auto Mantle on): when an air dash ends (usually against the wall under a ledge), the mod
    checks for a ledge for a moment and climbs it automatically. Air dash up to a ledge that is out
    of reach and you simply end up on top of it.

Traces
  Line traces live in ../tracing.py (see the notes there).

Heights and distances are in Unreal units, measured from your feet when the attempt is
made. Only level geometry is checked; moving platforms and other actors are ignored.
"""

import json
import math
import os
from dataclasses import dataclass, field

from mods_base import BoolOption, SliderOption
from unrealsdk import logging

from .. import authority, camera, core, fx, gravity, network, tracing
from ..gravity import GravityState
from ..protocol import Reason
from ..runtime import ExecutionRole, REGISTRY

enabled_option = BoolOption(
    "Mantle Enabled",
    True,
    "On",
    "Off",
    description="Turn mantle on or off.",
)

audio_option = BoolOption(
    "Mantle Audio Effect",
    True,
    "On",
    "Off",
    description="Adds a grab sound as you start a mantle and a landing sound when you reach the top.",
)

vault_option = BoolOption(
    "Vault",
    True,
    "On",
    "Off",
    description="Press jump while running at a low obstacle to climb straight onto it, without jumping first. (requires mantle)",
)

vault_height_slider = SliderOption(
    "Vault Max Height",
    value=160,
    min_value=50,
    max_value=160,
    step=5,
    is_integer=True,
    description="Tallest obstacle you can vault from the ground, in units from your feet (waist height is about 90). Taller ledges still need a jump first.",
)

max_height_slider = SliderOption(
    "Mantle Max Height",
    value=200,
    min_value=100,
    max_value=260,
    step=5,
    is_integer=True,
    description="The tallest ledge you can mantle, in units above your feet when you press. For reference, your eyes are about 140 above your feet.",
)

mantle_angle_slider = SliderOption(
    "Mantle Look Angle (°)",
    value=60,
    min_value=0,
    max_value=60,
    step=5,
    is_integer=True,
    description="How far below your crosshair mantles look for a ledge, in degrees. Traces go along the crosshair, halfway down and at this angle. 0 = only exactly where you aim.",
)

vault_angle_slider = SliderOption(
    "Vault Look Angle (°)",
    value=20,
    min_value=0,
    max_value=60,
    step=5,
    is_integer=True,
    description="How far below your crosshair vaults look for an obstacle, in degrees. Higher catches lower obstacles while you look ahead.",
)

fail_boost_slider = SliderOption(
    "Failed Mantle Boost (%)",
    value=65,
    min_value=0,
    max_value=100,
    step=5,
    is_integer=True,
    description="When a climb is stopped partway up, how much lift you keep as you let go, as a percentage of your normal jump. 0 = just drop.",
)

debug_option = BoolOption(
    "Mantle Debug Log",
    False,
    "On",
    "Off",
    description="Prints a line to the console (~) for every jump press saying whether it climbed and, if not, why, and records every attempt in full to Modern_Movement_mantle_debug.txt in the SDK settings folder.",
)

lower_weapon_option = BoolOption(
    "Lower Weapon While Mantling",
    True,
    "On",
    "Off",
    description="Puts your weapon away while you climb and draws it again at the top. Firing or aiming draws it straight away.",
)

shake_slider = SliderOption(
    "Mantle Camera Shake (%)",
    value=30,
    min_value=0,
    max_value=200,
    step=10,
    is_integer=True,
    description="A short camera bob and tilt as you reach the top of a mantle. Does not move your aim. 0 = off.",
)

# Tuned climb values (fixed).
_CLIMB_TIME = 0.40         # seconds a climb takes for the tallest ledge (shorter ledges: down to 55%)
_EXIT_MOMENTUM = 0.60      # share of the speed going in (or run speed while holding forward) kept at the top
_ENTRY_BLEND = 0.09        # seconds the motion going in is blended into the climb
_CAMERA_MOTION = 1.0       # strength of the climb camera dip / rise / tilt

# Player sounds, loaded on every map: the ladder-climb step as you grab the ledge, the landing
# footstep on reaching the top.
_GRAB_SOUNDS = fx.LADDER
_TOP_SOUNDS = fx.LAND

# Camera shake burst on reaching the top (applied by camera.py, shared with the other features).
_SHAKE_EYE = 2.0      # bob at 100%, units
_SHAKE_ROLL = 0.9     # tilt at 100%, degrees
_SHAKE_RISE = 0.04    # seconds to full strength
_SHAKE_FALL = 0.35    # seconds to settle
_DEBUG = False  # set to True to print diagnostic messages to the console

_MAX_HEIGHT = 160.0        # (default of Mantle Max Height) tallest ledge you can mantle, up from your feet
_UP_SHARE = 0.6            # share of the climb time spent rising to the lip (the rest goes over it)
_SHORT_TIME = 0.55         # a minimum-height ledge takes this share of the climb time
_TRACK_GAIN = 18.0         # 1/s: how hard the pawn is pulled back onto the path if it drifts
_ARRIVE_TOP = 16.0         # within this of the end spot at the end of the curve = on top
_OVERTIME = 0.25           # extra seconds allowed to reach the end spot before giving up
_DIP_EYE = 6.0             # camera dip / rise at 100%, units of eye height
_DIP_ROLL = 1.5            # camera tilt during the climb at 100%, degrees
_COOLDOWN = 0.3            # seconds between mantles
_JUMP_BUFFER = 0.25        # seconds a too-early jump press is remembered
_MIN_LEDGE_HEIGHT = 45.0   # lower than this is an ordinary step, not a mantle
_LOOK_FAN = (0.0, 10.0, 20.0)  # look traces: the crosshair, then this many degrees below it
_LOW_LIFT = 3.0            # body sweeps: the lower arc tried in a tight gap (units over the edge)
_SWEEP_STEPS = 10          # body sweeps: the path is checked in this many straight pieces...
_SWEEP_RADIUS = 1.0        # ...with a box as wide as your body (its corners reach a little further)...
_SWEEP_GAP = 2.0           # ...and as tall, less this much at the top and bottom (feet clear the floor)
_SWEEP_INNER = 0.7         # a box this share of your width settles "already touching at the start"
# The climb runs in falling physics, its velocity set every frame. (Until 3.16.2 the switch to flying never
# took effect, so every climb really ran like this, and that is the tested behaviour.)
_CLIMB_PHYS = 2            # core.PHYS_FALLING
_HANDOFF = True            # rise scripted, then hop over the edge under the game's own physics
_HOP_SPEED = 340.0         # hop: forward speed tried first (units/s)...
_HOP_MIN_SPEED = 160.0     # ...slowed (and raised) down to this to clear what is in the way
_HOP_VZ_MAX = 700.0        # hop: most upward speed it may add
_HOP_CLEAR = 3.0           # hop over a drop / obstacle: feet at least this far above its top
_LAND_WATCH = 1.5          # seconds after a hop during which touching down plays the landing effects
_HELD_GRACE = 0.06         # held back: not judged in the first moments of a climb...
_HELD_GAP = 30.0           # ...then: this many units short of where the plan has you, toward the ledge...
_HELD_SHARE = 0.4          # ...and under this share of the planned way...
_HELD_TICKS = 3            # ...for this many frames in a row: let go
_FOOT_SHARE = 0.97         # landing: also check this share of your radius ahead, behind and to the sides...
_FOOT_STEP = 24.0          # ...for surfaces up to this much higher than the spot itself
_HIGH_EXTRA = 12.0         # the higher arc clears the edge by this much more (bricks, small lips)
_MIN_CAP = 300.0           # speed cap going into a climb is your run speed, never below this
_FLAT_SHARES = (0.45, 0.7)  # vault flat traces: at these shares of the vault max height (and just under it)
_VAULT_REACH = 50.0        # vault flat traces reach this far past your body...
_VAULT_REACH_TIME = 0.3    # ...plus this many seconds of your speed...
_VAULT_REACH_MAX = 120.0   # ...up to this much extra
_JUMP_GRACE = 0.2          # an air press this soon after leaving the ground is still the vault press
_OVER_MARGIN = 10.0        # vault over: land this far past the far side (plus your radius)
_OVER_DROP = 120.0         # ...onto floor at most this far below your feet
_OVER_SEARCH = 40.0        # ...an obstacle may reach at most this much further back lower down
_OVER_PROBE_SHARES = (0.15, 0.5, 0.85)  # ...measured at these shares of its height
_OVER_FALL_MAX = 600.0     # ...or, hopping over into a fall, ground at most this far below
_OVER_CLEAR = 10.0         # ...with your feet passing this far above the top
_OVER_UP = 0.4             # share of the vault spent rising to the top of the arc...
_OVER_ACROSS = 0.68        # ...and by this share your body is past the far side (then down)
_LOOK_RANGE = 300.0        # how far each look trace reaches from your eyes
_DEEP_EXTRA = 30.0         # last try: further in, for a rounded top that only flattens out deeper
_GAP_SPAN = 36.0           # rails: a face that starts again within this span above an edge was a gap
_GAP_DEPTH = 24.0          # ...looking this deep (a top rail is often set back from the base)
_GAP_PROBE = 9.0           # ...checked every this many units
_FACE_DEPTH = 8.0          # face edge: how deep a flat trace counts as "the wall face itself"
_LIP_STEP = 20.0           # edge finder: step size up the wall face...
_LIP_REFINE = 4            # ...then this many halvings (about 1.3 units)
_LIP_ABOVE = 10.0          # top check starts this far above the edge...
_LIP_BELOW = 30.0          # ...and looks this far below it (a top that slopes down from the edge)
_TOP_PASSES = 8            # overhangs the top check may look under
_NARROW_DEPTH = 0.6        # narrow ledge retry: land this share of your radius past the edge (+4)
_TRACE_START = 0.5         # look traces start this far outside your collision cylinder
_STEEP_LEVELS = (30.0, 15.0, 0.0)  # looking steeply up: also trace at these angles above level
_LOOK_REACH = 160.0        # the wall you look at can be at most this far from you
_APPROACH_MIN_DOT = 0.6    # climb along your movement when it is within ~53 degrees of straight at the wall
_APPROACH_MIN_SPEED = 150.0  # ...and you are actually moving (slower: along where you look)
_HOLD_INTERVAL = 0.05      # seconds between ledge checks while jump is held in the air
_TRACE_BUDGET = 120        # traces one ledge search may use before it gives up (no frame hitches)
_MEMO_GRID = 16.0          # wall spots this close are measured once per search
_VAULT_BUFFER = 0.35       # a ground press that didn't vault keeps looking this long into the jump
_BUFFER_MIN_HEIGHT = 15.0  # ...and also accepts ledges this low (you have already risen)
_MIN_WALL_DOT = 0.5        # you must be facing within 60 degrees of the wall
_MAX_WALL_NORMAL_Z = 0.4   # a "wall" is steeper than this (|normal.z|)
_MIN_FLOOR_NORMAL_Z = 0.7  # a ledge top must be at least this flat
_TOP_MARGIN = 8.0          # how far past the wall face the pawn's centre ends up (plus radius)
_LIP_CLEARANCE = 12.0      # how far above the final spot the pawn passes over the lip
_STALL_TICKS = 4           # consecutive ticks of almost no progress = we hit something
_STALL_RATIO = 0.10        # "almost no progress" = under 10% of the expected movement
_BUFFER_INTERVAL = 0.08    # seconds between ledge checks while a jump press is buffered

@dataclass
class MantleState:
    mantle: dict | None = None
    last_end: float = -100.0
    buffer_until: float = -1.0
    buffer_vault: bool = False
    last_walk: float = -100.0
    last_check: float = -100.0
    trace_warned: bool = False
    last_reason: str = ""
    shake: dict | None = None
    hold_block: bool = False
    hold_state_reported: bool = False
    start_mode: str | None = None
    self_hits: int = 0
    lip_note: str = ""
    landing_until: float = 0.0
    action_id: int = 0
    gravity: GravityState = field(default_factory=GravityState)


_fallback_state = MantleState()


def _state(ctx=None) -> MantleState:
    ctx = ctx or core.current_context()
    return ctx.state("mantle", MantleState) if ctx is not None else _fallback_state


def _gravity_signature(ctx) -> str:
    if ctx is None or ctx.pawn_key is None:
        return ""
    player = ctx.pawn_key.player
    return f"{player.world_epoch}:{ctx.pawn_generation}"


def _log(msg: str, ctx=None) -> None:
    _state(ctx).last_reason = msg
    if _DEBUG:
        core.log("Mantle", msg)


def _report(msg: str) -> None:
    """One line for the Mantle Debug Log option."""
    if debug_option.value:
        logging.warning(f"[Mantle] {msg}")


# ---------------------------------------------------------------------------------------------
# Ledge search (line traces live in ../tracing.py)
# ---------------------------------------------------------------------------------------------


def _find_ledge(pawn, pc, min_height=None, spread=None, flat=None, flat_max=None, over=False, max_height=None, ctx=None):
    """Look for the ledge you are looking at. Returns a dict, or None if there isn't one.
    min_height overrides the lowest ledge accepted."""
    state = _state(ctx)
    ctx = ctx or core.current_context()
    state.start_mode = None
    state.self_hits = 0
    try:
        with tracing.session(ctx or pc, pawn, limit=_TRACE_BUDGET):
            return _find_ledge_inner(
                pawn, pc, min_height, spread, flat, flat_max, over, max_height, ctx=ctx,
            )
    except tracing.BudgetSpent:
        reason = state.last_reason
        state.last_reason = (reason + "; " if reason else "") + f"gave up after {_TRACE_BUDGET} traces"
        return None
    except tracing.TraceUnavailable:
        if not state.trace_warned:
            state.trace_warned = True
            logging.warning(
                "[Mantle] Could not perform weapon trace (CalcWeaponFire), so ledges can't be detected."
            )
        return None
    except Exception as e:  # noqa: BLE001
        _log(f"ledge search failed: {e!r}", ctx)
        return None


def _approach_dir(pc, pawn):
    """Flat direction you are moving (if moving), else where the camera faces."""
    try:
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
        n = math.hypot(vx, vy)
        if n >= _APPROACH_MIN_SPEED:
            return vx / n, vy / n
    except Exception:  # noqa: BLE001
        pass
    return core.facing(pc)


_SELF_HITS_TO_EDGE = 6  # ...before traces are known NOT to ignore your body (decided once, at the start)


def _look_trace(pawn, eye, facing, radius, end, ctx=None):
    """One look trace. Starts from the middle of your body at eye height (clear of any wall you are
    pressed against) when traces ignore your own body; otherwise just outside your body."""
    state = _state(ctx)
    x, y, ez = eye
    fx, fy = facing
    if state.start_mode != "edge":
        tracing.saw_self = False
        hit = tracing.trace(pawn, (x, y, ez), end)
        if hit is not None and math.dist(hit[0], (x, y, ez)) < 2.0:
            tracing.saw_self = True  # a "hit" right where it started: it is you, whatever it says
        if not tracing.saw_self:
            state.self_hits = 0
            if state.start_mode is None:
                state.start_mode = "centre"
                _report("look traces ignore your body: starting from its centre")
            return hit
        state.self_hits += 1
        if state.start_mode is None and state.self_hits >= _SELF_HITS_TO_EDGE:
            state.start_mode = "edge"
            _report("look traces hit your own body: starting just outside it instead")
    start = (x + fx * (radius + _TRACE_START), y + fy * (radius + _TRACE_START), ez)
    return tracing.trace(pawn, start, end)


def _pitch_deg(pc) -> float:
    pitch = int(pc.Rotation.Pitch) & 0xFFFF
    if pitch > 32767:
        pitch -= 65536
    return pitch * 360.0 / 65536.0


def _fan(pc, spread=None):
    """Degrees below the crosshair for each look trace: the crosshair, halfway and `spread` below
    it, plus, when you look steeply up (right under a tall ledge), extra traces stepping down
    toward level so the lip is still found."""
    spread = _LOOK_FAN[-1] if spread is None else max(0.0, float(spread))
    angles = [0.0] if spread <= 0.0 else [0.0, spread / 2.0, spread]
    pitch = _pitch_deg(pc)
    lowest = pitch - spread
    for level in _STEEP_LEVELS:
        if level < lowest - 5.0:
            angles.append(pitch - level)
    return angles


def _look_dir(pc, down_deg: float):
    """Unit vector along the camera's aim, tilted down_deg degrees further down."""
    pitch = int(pc.Rotation.Pitch) & 0xFFFF
    if pitch > 32767:
        pitch -= 65536
    p = math.radians(pitch * 360.0 / 65536.0 - down_deg)
    fx, fy = core.facing(pc)
    return fx * math.cos(p), fy * math.cos(p), math.sin(p)


def _find_ledge_inner(pawn, pc, min_height=None, spread=None, flat=None, flat_max=None, over=False, max_height=None, ctx=None):
    """Look traces: along the crosshair, then a little below it. The first one that lands on a
    ledge (its top, or the wall under it) and passes every check wins.
    flat (vaults): first, flat traces straight ahead the way you face (whatever your pitch) at a few
    heights up to flat_max, reaching `flat` units past your body: a low obstacle in front of you is
    found without looking down at it."""
    state = _state(ctx)
    radius, half = tracing.body(pawn)
    x, y, z = tracing.vec(pawn.Location)
    feet = z - half
    fx, fy = core.facing(pc)
    min_h = _MIN_LEDGE_HEIGHT if min_height is None else min_height
    try:
        eye_z = z + float(pawn.EyeHeight)
    except Exception:  # noqa: BLE001
        eye_z = z + half * 0.8

    rays = []
    if flat is not None:
        top = flat_max if flat_max is not None else _MAX_HEIGHT
        heights = sorted({max(min_h + 5.0, top * k) for k in _FLAT_SHARES} | {max(min_h + 5.0, top - 8.0)})
        for h in heights:
            hz = feet + h
            far = radius + flat
            rays.append((f"ahead +{h:.0f}", (x, y, hz), (x + fx * far, y + fy * far, hz)))
    for down in _fan(pc, spread):
        dx, dy, dz = _look_dir(pc, down)
        rays.append((
            "crosshair" if down == 0 else f"{down:.0f}deg below",
            (x, y, eye_z),
            (x + dx * _LOOK_RANGE, y + dy * _LOOK_RANGE, eye_z + dz * _LOOK_RANGE),
        ))

    reasons = []
    for label, origin, end in rays:
        hit = _look_trace(pawn, origin, (fx, fy), radius, end, ctx=ctx)
        if hit is None:
            reasons.append(f"{label}: nothing in range")
            continue
        (hx, hy, hz), (nx, ny, nz) = tracing.pair(hit)
        if abs(nz) <= _MAX_WALL_NORMAL_Z:
            wall = hit  # looking at the wall face
        elif nz > _MAX_WALL_NORMAL_Z:  # a top, flat or sloped (a rounded top is checked further in)
            if hz - feet < min_h:
                reasons.append(f"{label}: floor (only {hz - feet:.0f} up)")
                continue
            # Looking at the top of a ledge: find the wall face under its lip.
            flat = math.hypot(hx - x, hy - y)
            if flat < 1e-3:
                reasons.append(f"{label}: ledge top right above you")
                continue
            ux, uy = (hx - x) / flat, (hy - y) / flat
            wz = hz - 6.0
            wall = tracing.trace(
                pawn, (x + ux * (radius + _TRACE_START), y + uy * (radius + _TRACE_START), wz), (hx + ux * 4.0, hy + uy * 4.0, wz)
            )
            if wall is None or abs(wall[1][2]) > _MAX_WALL_NORMAL_Z:
                reasons.append(f"{label}: ledge top with no wall under its edge")
                continue
        else:
            reasons.append(f"{label}: underside (normal z={nz:.2f})")
            continue

        (wx, wy, _wz), (wnx, wny, _wnz) = tracing.pair(wall)
        wl = math.hypot(wnx, wny)
        if wl < 1e-6:
            reasons.append(f"{label}: bad wall")
            continue
        ix, iy = -wnx / wl, -wny / wl  # into the wall
        if fx * ix + fy * iy < _MIN_WALL_DOT:
            reasons.append(f"{label}: wall at too sharp an angle")
            continue
        gap = (wx - x) * ix + (wy - y) * iy - radius
        if gap > _LOOK_REACH:
            reasons.append(f"{label}: too far ({gap:.0f} > {_LOOK_REACH:.0f})")
            continue
        # Land along the way you are moving when it is close enough to straight on (else square up).
        ax, ay = _approach_dir(pc, pawn)
        dot = ax * ix + ay * iy
        paths = [(ax, ay, dot), (ix, iy, 1.0)] if dot >= _APPROACH_MIN_DOT and dot < 0.999 else [(ix, iy, 1.0)]
        ledge = None
        max_h = float(max_height_slider.value) if max_height is None else float(max_height)
        # The same wall seen by several traces is measured once.
        key = ("lip", round(wx / _MEMO_GRID), round(wy / _MEMO_GRID), round(ix, 1), round(iy, 1), round(feet), round(max_h))
        if key in tracing.cache:
            edges, note, lnote = tracing.cache[key]
            state.lip_note = lnote
        else:
            edges, note = _find_lip(
                pawn, wall[0], (ix, iy), max(0.0, gap), feet, max_h, radius + _TOP_MARGIN + 4.0, ctx=ctx,
            )
            tracing.cache[key] = (edges, note, state.lip_note)
        if not edges:
            reasons.append(f"{label}: wall at +{wall[0][2] - feet:.0f}, {note}")
            continue
        fails = []
        for lip in edges:
            for ux, uy, d in paths:
                state.last_reason = ""
                ledge = _ledge_from_wall(
                    pawn, (x, y, z), feet, radius, half, (wx, wy), (ix, iy), max_h, min_h,
                    path=(ux, uy, d), lip=lip, over=over, ctx=ctx,
                )
                if ledge is not None and _sweeps(ctx):
                    why = _sweep_path(pawn, pc, ledge, ctx=ctx)  # check the move: does your body fit the path?
                    if why is not None:
                        state.last_reason = ("vault over: " if ledge.get("over") else "") + why
                        ledge = None
                if ledge is not None:
                    break
            if ledge is not None:
                break
            fails.append(f"from +{lip - feet:.0f}: {state.last_reason}")
        state.last_reason = "; ".join(fails)
        if ledge is not None:
            ledge["look"] = label
            return ledge
        reasons.append(f"{label}: wall at +{wall[0][2] - feet:.0f}, {state.lip_note}, {state.last_reason}")
    state.last_reason = "; ".join(reasons) or "no ledge"
    return None


def _top_down(pawn, px, py, top_start, low_z, feet, cap=None):
    key = ("top", round(px / 4.0), round(py / 4.0), round(top_start / 4.0), round(low_z / 4.0))
    if key not in tracing.cache:
        tracing.cache[key] = _top_down_inner(pawn, px, py, top_start, low_z, feet, cap)
    return tracing.cache[key]


def _top_down_inner(pawn, px, py, top_start, low_z, feet, cap=None):
    """Trace down at (px, py) for the top of a ledge. An underside hit (an overhang or ceiling above
    the ledge, or a start inside something solid) is passed: tracing continues from just below
    it. Starting inside something (roof trim, a cornice) steps the start up, as far as `cap`.
    Returns (hit, why-not)."""
    start = top_start
    for _ in range(_TOP_PASSES):
        if start <= low_z + 1.0:
            return None, "no room under an overhang"
        hit = tracing.trace(pawn, (px, py, start), (px, py, low_z))
        if hit is None:
            # Nothing: either really nothing there, or we started inside a roof that rises behind
            # the edge (the game often reports nothing from inside). Try again from higher up.
            if cap is not None and start + _LIP_STEP <= cap:
                start += _LIP_STEP
                continue
            return None, "nothing (too thin, or it drops away)"
        (_hx, _hy, hz), (_nx, _ny, nz) = tracing.pair(hit)
        if hz >= start - 2.0:
            if cap is not None and start + _LIP_STEP <= cap:
                start += _LIP_STEP  # inside trim / a cornice: look again from higher up
                continue
            return None, f"solid up to +{start - feet:.0f} (taller than your max height)"
        if nz < 0.0:
            start = hz - 2.0  # underside: look again from just below it
            continue
        return hit, ""
    return None, "too many overhangs"


def _wall_at(pawn, wx, wy, ix, iy, h, s, depth) -> bool:
    """Is there still something solid at height h, anywhere from the wall face to `depth` past it
    (as deep as you would stand)? A flat trace into it, starting s in front. Checking that deep
    means a rounded or sloped top that leans back is measured at its real top, not where it
    first leans away from the face."""
    hit = tracing.trace(pawn, (wx - ix * s, wy - iy * s, h), (wx + ix * depth, wy + iy * depth, h))
    return hit is not None and abs(hit[1][2]) < _MIN_FLOOR_NORMAL_Z


def _scan_up(pawn, wx, wy, ix, iy, s, depth, start_z, limit):
    """Step up from start_z while something is solid (face to `depth` past it). Returns the edge
    height, or None if it is still solid at `limit` (then the second value is the last solid height)."""
    h = start_z
    below = start_z
    while True:
        h += _LIP_STEP
        if h > limit:
            return None, below
        if not _wall_at(pawn, wx, wy, ix, iy, h, s, depth):
            break
        below = h
    lo, hi = below, h  # solid at lo, open at hi: narrow it down
    for _ in range(_LIP_REFINE):
        mid = (lo + hi) / 2.0
        if _wall_at(pawn, wx, wy, ix, iy, mid, s, depth):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0, lo


def _find_lip(pawn, wall_pt, into, gap, feet, max_height, depth=50.0, ctx=None):
    """Find the top edge of the wall with flat traces stepping up it. Two heights:
      face edge - where the wall face itself ends (8 units deep), and
      deep edge - where everything up to `depth` past the face ends (a rounded top that leans
                  back, or the wall's top with something taller just behind it).
    Returns ([edges to try, best first], None) or ([], why-not). No trace starts inside the wall."""
    wx, wy, wz = wall_pt
    ix, iy = into
    s = min(8.0, max(0.25, gap * 0.5))  # start between you and the wall (never inside you)
    limit = feet + max_height + _LIP_STEP
    face, face_solid = _scan_up(pawn, wx, wy, ix, iy, s, _FACE_DEPTH, wz, limit)
    if face is None:
        return [], f"wall taller than {max_height:.0f} (face still solid at +{face_solid - feet:.0f})"
    # A gap between rails (or bars) is not the top: if the face starts again within a short span
    # above, keep climbing to the real top. The lower edges are kept as fallbacks.
    lower = []
    while True:
        resumed = None
        h = face + _GAP_PROBE
        while h <= min(limit, face + _GAP_SPAN):
            if _wall_at(pawn, wx, wy, ix, iy, h, s, _GAP_DEPTH):
                resumed = h
                break
            h += _GAP_PROBE
        if resumed is None:
            break
        nxt, nxt_solid = _scan_up(pawn, wx, wy, ix, iy, s, _GAP_DEPTH, resumed, limit)
        if nxt is None:
            break  # the part above is too tall: keep the edge below it
        lower.append(face)
        face = nxt
    deep, deep_solid = _scan_up(pawn, wx, wy, ix, iy, s, depth, face - 1.0, limit)
    edges = []
    if deep is not None and deep > face + 2.0:
        edges.append(deep)
    edges.append(face)
    edges.extend(reversed(lower))
    state = _state(ctx)
    state.lip_note = (
        f"edge at +{face - feet:.0f}"
        + ("" if deep is not None and deep <= face + 2.0 else
           f" (behind it: {'solid past +%.0f' % (deep_solid - feet) if deep is None else 'up to +%.0f' % (deep - feet)})")
    )
    return edges, None


def _over_ledge(pawn, pos, feet, radius, half, wall_xy, into, lip, min_h, why_not_on, ctx=None):
    """A thin obstacle (a railing, a barrier, a low wall): can a vault carry you over it?
    Measures how thick its top is, finds floor on the far side within a safe drop, and checks
    there is room to pass over the top and to land."""
    x, y, z = pos
    wx, wy = wall_xy
    dx, dy = into
    height = lip - feet
    if height < min_h:
        _log(f"only {height:.0f} high: an ordinary jump clears it")
        return None

    def top_at(depth):
        px, py = wx + dx * depth, wy + dy * depth
        hit = tracing.trace(pawn, (px, py, lip + 8.0), (px, py, lip - 14.0))
        return hit is not None and hit[1][2] >= _MAX_WALL_NORMAL_Z

    # How thick: the top is there just past the face, gone by the narrow landing depth.
    lo, hi = 2.0, radius * _NARROW_DEPTH + 4.0
    if top_at(lo):
        for _ in range(4):
            mid = (lo + hi) / 2.0
            if top_at(mid):
                lo = mid
            else:
                hi = mid
        thick = hi
    else:
        thick = 4.0  # a rounded or knife-edge top
    # How far the obstacle reaches on the far side, at several heights: its top can be thinner than
    # its base (a balustrade, a jersey barrier). Traced back toward it from well past it.
    far = thick
    out = thick + radius * 2.0 + _OVER_MARGIN + _OVER_SEARCH
    for k in _OVER_PROBE_SHARES:
        hz = feet + max(6.0, (lip - feet) * k)
        hit = tracing.trace(pawn, (wx + dx * out, wy + dy * out, hz), (wx - dx * 1.0, wy - dy * 1.0, hz))
        if hit is not None:
            reach = (hit[0][0] - wx) * dx + (hit[0][1] - wy) * dy
            if reach < out - 2.0:
                far = max(far, reach)
    if far > thick + _OVER_SEARCH:
        _log(f"can't vault over: it is {far:.0f} deep lower down")
        return None
    # Landing spot: clear of the far side by your radius and a margin.
    land = far + radius + _OVER_MARGIN
    lx, ly = wx + dx * land, wy + dy * land
    floor = tracing.trace(pawn, (lx, ly, lip + 8.0), (lx, ly, feet - _OVER_DROP))
    drop = False
    if floor is None:
        # Further down: hop over and fall, as long as there IS ground below (never into a void).
        floor = tracing.trace(pawn, (lx, ly, feet - _OVER_DROP), (lx, ly, feet - _OVER_FALL_MAX))
        if floor is None:
            _log(f"can't vault over: no ground within {_OVER_FALL_MAX:.0f} below the far side")
            return None
        drop = True
    (_fx, _fy, fz), (_fnx, _fny, fnz) = tracing.pair(floor)
    if fnz < _MIN_FLOOR_NORMAL_Z:
        _log(f"can't vault over: the far side is too steep (normal z={fnz:.2f})")
        return None
    if fz > lip - 20.0:
        _log("can't vault over: the far side is nearly as high as the top")
        return None
    fz = _footprint_top(pawn, lx, ly, dx, dy, radius, fz)
    peak_feet = lip + _OVER_CLEAR
    if drop:
        # Room to pass over, then release into the fall just past the far side.
        if not _sweeps():  # (with body sweeps, the path check below covers this)
            bx, by = x + dx * (radius + _TRACE_START), y + dy * (radius + _TRACE_START)
            for hz in (peak_feet + 2.0, peak_feet + half, peak_feet + 2.0 * half - 6.0):
                if tracing.trace(pawn, (bx, by, hz), (lx + dx * radius, ly + dy * radius, hz)) is not None:
                    _log(f"can't vault over: no room above the top (something at +{hz - feet:.0f})")
                    return None
            if tracing.trace(pawn, (x, y, z + half), (x, y, peak_feet + 2.0 * half)) is not None:
                _log("can't vault over: something overhead")
                return None
        gap = max(0.0, (wx - x) * dx + (wy - y) * dy - radius)
        _log(f"vault over a drop: {height:.0f} high, {thick:.0f} thick, ground {fz - feet:+.0f}")
        return {
            "target": (lx, ly, peak_feet + half),
            "height": height,
            "gap": gap,
            "top": lip,
            "over": True,
            "drop": True,
            "peak": peak_feet + half,
            "clear": gap + 2.0 * radius + far,
        }
    # Room to pass over: from in front of the face to past the landing spot, at feet, waist and head height.
    # (Started from just in front of you, in open air: not from the face, which can be inside a beam.)
    if not _sweeps():  # (with body sweeps, the path check below covers this)
        bx, by = x + dx * (radius + _TRACE_START), y + dy * (radius + _TRACE_START)
        for hz in (peak_feet + 2.0, peak_feet + half, peak_feet + 2.0 * half - 6.0):
            if tracing.trace(pawn, (bx, by, hz), (lx + dx * radius, ly + dy * radius, hz)) is not None:
                _log(f"can't vault over: no room above the top (something at +{hz - feet:.0f})")
                return None
        if tracing.trace(pawn, (x, y, z + half), (x, y, peak_feet + 2.0 * half)) is not None:
            _log("can't vault over: something overhead")
            return None
        # Room to land: headroom (centre and both sides) and nothing right behind the obstacle.
        sx, sy = -dy * radius * 0.8, dx * radius * 0.8
        for ox, oy in ((0.0, 0.0), (sx, sy), (-sx, -sy)):
            if tracing.trace(pawn, (lx + ox, ly + oy, fz + 4.0), (lx + ox, ly + oy, fz + 2.0 * half)) is not None:
                _log("can't vault over: no room to land")
                return None
        back = (lx - dx * radius, ly - dy * radius)  # the back of your body when you land
        if tracing.trace(pawn, (back[0], back[1], fz + 14.0), (lx + dx * radius, ly + dy * radius, fz + 14.0)) is not None:
            _log("can't vault over: something right behind it")
            return None
    gap = max(0.0, (wx - x) * dx + (wy - y) * dy - radius)
    _log(f"vault over: {height:.0f} high, {thick:.0f} thick, landing {fz - feet:+.0f}")
    return {
        "target": (lx, ly, fz + half + 2.0),
        "height": height,
        "gap": gap,
        "top": lip,
        "over": True,
        "peak": peak_feet + half,       # pawn centre height at the top of the arc
        "clear": gap + 2.0 * radius + far,  # centre travel until your body is past the far side
    }


def _footprint_top(pawn, px, py, ux, uy, radius, base_z):
    """Highest standable surface under your body around (px, py), up to a small step above base_z."""
    best = base_z
    sx, sy = -uy, ux
    for ox, oy in ((ux, uy), (sx, sy), (-sx, -sy), (-ux, -uy)):
        qx, qy = px + ox * radius * _FOOT_SHARE, py + oy * radius * _FOOT_SHARE
        hit = tracing.trace(pawn, (qx, qy, base_z + _FOOT_STEP + 8.0), (qx, qy, base_z - 4.0))
        # A small step is stood on; anything taller is an obstacle (the room checks deal with it).
        if hit is not None and hit[1][2] >= _MIN_FLOOR_NORMAL_Z and hit[0][2] <= base_z + _FOOT_STEP:
            best = max(best, hit[0][2])
    return best


def _ledge_from_wall(pawn, pos, feet, radius, half, wall_xy, into, max_height, min_h, path=None, lip=None, over=False, ctx=None):
    """Given a wall face spot and the direction into it: is there a ledge on top we can climb onto?
    path = (ux, uy, dot): the flat direction to climb along (and its dot with `into`); the end
    spot is the same depth past the wall face either way."""
    x, y, z = pos
    wx, wy = wall_xy
    dx, dy = into
    ux, uy, along = path if path is not None else (dx, dy, 1.0)

    # 2. Top check: trace down just past the edge, from just above the lip (open air, so never
    # inside the wall). Normal depth first; for a narrow top, closer to the edge.
    if lip is not None:
        top_start, low_z = lip + _LIP_ABOVE, max(feet + min_h - 2.0, lip - _LIP_BELOW)
    else:
        top_start, low_z = feet + max_height, feet + min_h + 10.0
    top = None
    notes = []
    narrow = False
    for depth in (radius + _TOP_MARGIN, radius * _NARROW_DEPTH + 4.0, radius + _DEEP_EXTRA):
        narrow = depth < radius + _TOP_MARGIN
        px = wx + ux * depth / along
        py = wy + uy * depth / along
        top, note = _top_down(pawn, px, py, top_start, low_z, feet, cap=feet + max_height + 10.0)
        if top is not None and top[1][2] < _MIN_FLOOR_NORMAL_Z:
            note = f"slope at +{top[0][2] - feet:.0f} (normal z={top[1][2]:.2f})"
            top = None
        if top is not None:
            break
        notes.append(f"{depth:.0f} in: {note}")
    if top is None:
        if over and lip is not None:
            # Too thin to stand on: a vault can go OVER it instead.
            return _over_ledge(pawn, pos, feet, radius, half, (wx, wy), (dx, dy), lip, min_h, "; ".join(notes), ctx=ctx)
        _log("nothing to stand on past the edge (" + ", ".join(notes) + ")")
        return None
    if top[0][2] - feet > max_height:
        _log(f"ledge top at +{top[0][2] - feet:.0f} is higher than {max_height:.0f}")
        return None
    (_tx, _ty, top_z), (_tnx, _tny, tnz) = tracing.pair(top)
    if tnz < _MIN_FLOOR_NORMAL_Z:
        _log(f"ledge top at +{top_z - feet:.0f} is too steep to stand on (normal z={tnz:.2f})")
        return None
    height = top_z - feet
    if height < min_h:
        _log(f"ledge is only {height:.0f} units high")
        return None
    # Land on the highest surface under your whole footprint (a raised brick, a small step just
    # past the spot): while climbing you fly, and a flying body doesn't step up even a few units.
    top_z = _footprint_top(pawn, px, py, ux, uy, radius, top_z)
    if top_z - feet > max_height:
        _log(f"the spot you'd stand on is at +{top_z - feet:.0f}, higher than {max_height:.0f}")
        return None

    # 3. Room check: headroom on the ledge (centre + both sides), and nothing overhead along the wall.
    if not _sweeps():  # (with body sweeps, the path check below covers this)
        sx, sy = -dy * radius * 0.8, dx * radius * 0.8
        for ox, oy in ((0.0, 0.0), (sx, sy), (-sx, -sy)):
            if tracing.trace(pawn, (px + ox, py + oy, top_z + 4.0), (px + ox, py + oy, top_z + 2.0 * half)) is not None:
                _log("not enough headroom on top of the ledge")
                return None
    # ...and a clear way in: flat traces from the open air just above the edge, through the landing
    # spot, out to the far side of your body. Catches a raised roof between the edge and the spot,
    # something right behind a thin ledge, and a "top" that was really found from inside something.
    if not _sweeps():  # (with body sweeps, the path check below covers this)
        for hz in (top_z + 12.0, top_z + half):
            if tracing.trace(pawn, (wx - dx * 1.0, wy - dy * 1.0, hz), (px + ux * radius, py + uy * radius, hz)) is not None:
                _log(f"no room to stand on the top at +{top_z - feet:.0f} (something in the way)")
                return None
    target_z = top_z + half + 2.0
    if not _sweeps() and tracing.trace(pawn, (x, y, z + half), (x, y, target_z + half)) is not None:
        _log("something overhead blocks the climb")
        return None

    gap = (wx - x) * dx + (wy - y) * dy - radius  # pawn's edge to the wall face
    gap = max(0.0, gap)
    _log(f"ledge found: {height:.0f} units above feet, {gap:.0f} from the wall")
    return {"target": (px, py, target_z), "height": height, "gap": gap / along, "top": top_z, "narrow": narrow}


# ---------------------------------------------------------------------------------------------
# The climb
# ---------------------------------------------------------------------------------------------


def _set_physics(pawn, phys: int) -> None:
    core.set_physics(pawn, phys)


# Host-side climb holds for joiners (Eternal/DJ pattern). Remote PlayerTick alone rubber-bands.
_HOST_MANTLES: dict[int, dict] = {}


def release_player(player_id: int | None) -> None:
    """Drop host mantle holds. None clears every joiner (level change)."""
    if player_id is None:
        _HOST_MANTLES.clear()
        return
    _HOST_MANTLES.pop(int(player_id), None)


def _serialize_climb(m: dict) -> dict:
    """JSON-safe climb plan so the listen host can replay the same motion."""
    out = {
        "start": [float(v) for v in m["start"]],
        "dir": [float(v) for v in m["dir"]],
        "hdist": float(m["hdist"]),
        "lip": float(m["lip"]),
        "target": [float(v) for v in m["target"]],
        "T": float(m["T"]),
        "h": [float(v) for v in m["h"]],
        "z": [float(v) for v in m["z"]],
        "exit": float(m["exit"]),
        "v_in": [float(v) for v in m["v_in"]],
        "top": float(m.get("top", m["target"][2])),
        "drop": bool(m.get("drop")),
        "handoff_u": float(m.get("handoff_u", _UP_SHARE)),
        "clear": None if m.get("clear") is None else float(m["clear"]),
        "narrow": bool(m.get("narrow")),
        "look": str(m.get("look", "?")),
        "lift": None if m.get("lift") is None else float(m["lift"]),
    }
    if m.get("over"):
        hk, zk = m["over"]
        out["over"] = [
            [[float(x) for x in hk[0]], [float(x) for x in hk[1]], [float(x) for x in hk[2]]],
            [[float(x) for x in zk[0]], [float(x) for x in zk[1]], [float(x) for x in zk[2]]],
        ]
    return out


def _deserialize_climb(plan: dict) -> dict | None:
    try:
        start = tuple(float(v) for v in plan["start"])
        target = tuple(float(v) for v in plan["target"])
        m = {
            "start": start,
            "dir": tuple(float(v) for v in plan["dir"]),
            "hdist": float(plan["hdist"]),
            "lip": float(plan["lip"]),
            "target": target,
            "T": max(0.05, float(plan["T"])),
            "h": tuple(float(v) for v in plan["h"]),
            "z": tuple(float(v) for v in plan["z"]),
            "exit": float(plan["exit"]),
            "v_in": tuple(float(v) for v in plan["v_in"]),
            "top": float(plan.get("top", target[2])),
            "drop": bool(plan.get("drop")),
            "handoff_u": float(plan.get("handoff_u", _UP_SHARE)),
            "clear": None if plan.get("clear") is None else float(plan["clear"]),
            "narrow": bool(plan.get("narrow")),
            "look": str(plan.get("look", "rpc")),
            "lift": None if plan.get("lift") is None else float(plan["lift"]),
            "elapsed": 0.0,
            "last": start,
            "commanded": 0.0,
            "stalled": 0,
            "remote": True,  # ignore Location stall on host replica
        }
        if plan.get("over"):
            hk, zk = plan["over"]
            m["over"] = (
                (tuple(float(x) for x in hk[0]), tuple(float(x) for x in hk[1]), tuple(float(x) for x in hk[2])),
                (tuple(float(x) for x in zk[0]), tuple(float(x) for x in zk[1]), tuple(float(x) for x in zk[2])),
            )
        return m
    except Exception:  # noqa: BLE001
        return None


def host_apply_mantle(ctx, plan: dict) -> None:
    """Listen-host: install the joiner's climb plan on sender.Owner.Pawn."""
    if not enabled_option.value or ctx.pawn is None or not isinstance(plan, dict):
        return
    climb = _deserialize_climb(plan)
    if climb is None:
        return
    _HOST_MANTLES[ctx.key.player_id] = {"pawn": ctx.pawn, "ctx": ctx}

    def apply() -> None:
        state = _state(ctx)
        state.mantle = climb
        core.begin("mantle", ctx=ctx)
        _set_physics(ctx.pawn, _CLIMB_PHYS)
        vx, vy, vz = climb["v_in"]
        core.set_velocity(ctx.pawn, vx, vy, vz)

    core.execute(ctx, apply)


def host_end_mantle(ctx) -> None:
    """Listen-host: joiner cancelled — stop the mirrored climb."""
    _HOST_MANTLES.pop(ctx.key.player_id, None)
    if ctx.pawn is None:
        return

    def cancel() -> None:
        if _state(ctx).mantle is not None:
            _end(ctx.pawn, "rpc_exit", ctx=ctx)

    core.execute(ctx, cancel)


def _service_host_mantles(dt: float) -> None:
    """Run joiner climbs from the listen-host local tick (remote PlayerTick is unreliable)."""
    if not _HOST_MANTLES:
        return
    done: list[int] = []
    for pid, entry in list(_HOST_MANTLES.items()):
        ctx = entry.get("ctx")
        pawn = entry.get("pawn")
        if ctx is None or pawn is None:
            done.append(pid)
            continue
        state = _state(ctx)
        if state.mantle is None:
            done.append(pid)
            continue

        def run(c=ctx, p=pawn, step=dt) -> None:
            _run_mantle(p, step, ctx=c)

        try:
            core.execute(ctx, run)
        except Exception:  # noqa: BLE001
            done.append(pid)
            continue
        if _state(ctx).mantle is None:
            done.append(pid)
    for pid in done:
        _HOST_MANTLES.pop(pid, None)


def _end(pawn, reason: str, ctx=None) -> None:
    """Finish the mantle and give the pawn back to the normal physics."""
    state = _state(ctx)
    if state.mantle is None:
        return
    m = state.mantle
    state.mantle = None
    state.last_end = core.clock
    core.end("mantle", ctx=ctx)
    core.emit("mantle_end", ctx=ctx, reason=reason)
    ctx = ctx or core.current_context()
    if ctx is not None:
        _HOST_MANTLES.pop(ctx.key.player_id, None)
    action_id = state.action_id
    state.action_id = 0
    if ctx is not None and ctx.authority and action_id:
        authority.end_action(ctx, "mantle", reason)
    try:
        from .. import coop_rpc

        if coop_rpc.is_requester(ctx) and reason != "rpc_exit":
            coop_rpc.call_host(coop_rpc.server_mantle_end)
    except Exception:  # noqa: BLE001
        pass
    try:
        pc_now = ctx.controller if ctx is not None else core.get_pc_pawn()[0]
        state.hold_block = pc_now is not None and bool(core.jump_held(pc_now))
    except Exception:  # noqa: BLE001
        state.hold_block = False
    if debug_option.value:
        try:
            _rec_write({
                "t": round(core.clock, 3), "end": reason, "elapsed": round(m.get("elapsed", 0.0), 3),
                "pos": tracing._r(tracing.vec(pawn.Location)) if pawn is not None else None,
                "target": tracing._r(m["target"]) if m.get("target") is not None else None,
                "ticks": m.get("ticks", []),  # [time, position, velocity found, physics, velocity set]
                "hop": [round(c, 1) for c in m["hop"]] if m.get("hop") else None,
            })
        except Exception:  # noqa: BLE001
            pass
        if reason not in ("reached the top", "handed over"):
            _report(f"climb ended early: {reason}")
    _log(f"mantle ended ({reason}) after {m['elapsed']:.2f}s")
    if pawn is not None:
        # On top: carry the exit momentum forward (2). Anywhere else: let go with no velocity.
        top = reason == "reached the top"
        ex, ey = m.get("dir", (0.0, 0.0)) if top else (0.0, 0.0)
        speed = m.get("exit", 0.0) if top else 0.0
        # Held back while rising: let go into a normal fall with a little lift (Failed Mantle Boost, as a
        # share of your own jump), never more than the climb was rising at.
        vz = 0.0
        if reason == "held back":
            boost = core.base_jump(pawn) * fail_boost_slider.value / 100.0
            vz = max(0.0, min(float(m.get("vz", 0.0)), boost))
        if reason == "handed over" and m.get("hop"):
            ex, ey = m["dir"]
            speed, vz = m["hop"][0], m["hop"][1]
        core.set_velocity(pawn, ex * speed, ey * speed, vz)
        # On top of the ledge: walk. Anywhere else (blocked / timed out), or released over a drop: fall.
        walk = reason == "reached the top" and not m.get("drop")
        if reason == "handed over":
            walk = False
        _set_physics(pawn, core.PHYS_WALKING if walk else core.PHYS_FALLING)
    if reason == "reached the top" and not m.get("drop"):
        _on_top(pawn, pc=ctx.controller if ctx is not None else None, mantle_ctx=ctx)
    if reason == "handed over":
        state.landing_until = core.clock + _LAND_WATCH  # landing sound and shake when you touch down
        if debug_option.value and m.get("hop"):
            _report(f"hop: forward {m['hop'][0]:.0f}, up {m['hop'][1]:.0f} (gravity {m['hop'][2]:.0f})")  # (over a drop the game plays its own landing when you land)


def _on_top(pawn, pc=None, mantle_ctx=None) -> None:
    """Made it onto the ledge: sound and camera shake."""
    ctx = mantle_ctx or core.current_context()
    if ctx is not None and not ctx.presentation:
        return
    if pc is None:
        pc = ctx.controller if ctx is not None else core.get_pc_pawn()[0]
    if audio_option.value and pawn is not None and pc is not None:
        fx.play_all(pc, pawn, _TOP_SOUNDS)
    _state(ctx).shake = {"t0": core.clock, "t": 0.0}


def _update_shake(dt, ctx=None) -> None:
    ctx = ctx or core.current_context()
    if ctx is not None and not ctx.presentation:
        return
    state = _state(ctx)
    if state.shake is None:
        return
    age = core.clock - state.shake["t0"]
    if age >= _SHAKE_RISE + _SHAKE_FALL:
        state.shake = None
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
    camera.request("mantle", eye=bob * _SHAKE_EYE * amount, roll=tilt * _SHAKE_ROLL * amount)


def _plan(pawn, pc, ground: bool = False, preview: bool = False, ctx=None, **search):
    """The ledge a press right now would climb, or None (the reason is in state.last_reason).
    ground=True is a vault: from walking, only for ledges up to the vault height."""
    state = _state(ctx)
    state.last_reason = "no ledge in front of you"

    if not enabled_option.value or state.mantle is not None:
        _log("mantle off or already mantling", ctx)
        return None
    if core.busy not in (None, "dash"):
        _log(f"busy with {core.busy}", ctx)
        return None
    if core.clock - state.last_end < _COOLDOWN:
        _log("cooldown from the last mantle")
        return None
    if pawn is None or core.unusable(pawn):
        _log("no usable pawn")
        return None
    try:
        phys = int(pawn.Physics)
    except Exception:  # noqa: BLE001
        return None
    if phys != (core.PHYS_WALKING if (ground or preview) else core.PHYS_FALLING):
        _log(f"wrong movement state ({phys})")
        return None
    if ground and not (vault_option.value and _moving_into_wall(pc, pawn)):
        _log("not moving forward")
        return None

    if ground:
        search.update(_vault_search(pc, pawn))
    vault_max = search.pop("vault_max", None)
    search.setdefault("spread", mantle_angle_slider.value)
    ledge = _find_ledge(pawn, pc, ctx=ctx, **search)
    if ledge is None:
        return None
    if vault_max is not None and ledge["height"] > vault_max:
        _log(f"too tall to vault ({ledge['height']:.0f} > {vault_max:.0f})")
        return None
    return ledge


def _build_climb(pawn, pc, ledge):
    """Plan the climb for this ledge: the path, its timing and the momentum at the end. Pure: reads
    the pawn, changes nothing. Returns the climb dict, or None if no path makes sense."""
    sx, sy, sz = tracing.vec(pawn.Location)
    tx, ty, tz = ledge["target"]
    hx, hy = tx - sx, ty - sy
    hdist = math.hypot(hx, hy)
    if hdist < 1e-3:
        return None
    ux, uy = hx / hdist, hy / hdist          # flat direction of the climb (into the wall)
    lip = tz + ledge.get("lift", _LIP_CLEARANCE)

    # 1. Climb time scales with the ledge height.
    frac = min(1.6, max(0.0, ledge["height"] / _MAX_HEIGHT))  # taller than 160 (raised max height): longer
    T = _CLIMB_TIME * (_SHORT_TIME + (1.0 - _SHORT_TIME) * frac)
    T = max(0.08, T)
    a = _UP_SHARE

    # Motion going in.
    try:
        vx, vy, vz = float(pawn.Velocity.X), float(pawn.Velocity.Y), float(pawn.Velocity.Z)
    except Exception:  # noqa: BLE001
        vx = vy = vz = 0.0
    # Never more than your run speed going in (a dash, a launcher, a long fall): the blend and the
    # momentum kept at the top stay calm whatever you were doing.
    try:
        cap = max(_MIN_CAP, float(pawn.GroundSpeed))
    except Exception:  # noqa: BLE001
        cap = 440.0
    flat = math.hypot(vx, vy)
    if flat > cap:
        vx, vy = vx * cap / flat, vy * cap / flat
    vz = max(-cap, min(cap, vz))
    v_in = vx * ux + vy * uy                  # speed toward the wall
    # A long approach (vault from further out) gets extra time instead of a lunge.
    T += max(0.0, ledge["gap"] - 40.0) / max(v_in, 300.0) * 0.5

    # 2. Exit speed: a share of the speed going in, or of run speed while holding forward.
    basis = max(0.0, v_in, math.hypot(vx, vy) * 0.5)
    if _moving_into_wall(pc, pawn):
        try:
            basis = max(basis, float(pawn.GroundSpeed))
        except Exception:  # noqa: BLE001
            pass
    exit_speed = min(basis, cap) * _EXIT_MOMENTUM

    # Horizontal progress h(u) 0..1 (u = time / T). Until the feet are over the lip it may only
    # close the gap to the wall face, so the climb never scrapes the lip.
    g = min(0.9, max(0.0, ledge["gap"] - 3.0) / hdist)
    sec1, sec2 = g / a, (1.0 - g) / (1.0 - a)
    h_mid = 0.0 if sec1 <= 0.0 else 2.0 * sec1 * sec2 / (sec1 + sec2)
    h0 = min(3.0 * sec1, max(0.0, v_in) * T / hdist)
    h1 = min(3.0 * sec2, exit_speed * T / hdist)

    # Vertical z(u): up to the lip (rising from the start), then settle onto the ledge.
    if ledge.get("over"):
        lip = ledge["peak"] - _OVER_CLEAR + ledge.get("lift", _OVER_CLEAR)
    rise = lip - sz
    if rise <= 0.0:
        return None
    zsec = rise / a
    z0 = min(2.5 * zsec, max(0.6 * zsec, vz * T))

    over_path = None
    if ledge.get("over"):
        # Up to the arc's top, across until your body is past the far side, then down onto the floor.
        a1, a2 = _OVER_UP, _OVER_ACROSS
        g2 = min(0.97, max(g + 0.01, ledge["clear"] / hdist))
        peak = lip - sz
        z_start = min(2.5 * peak / a1, max(0.6 * peak / a1, vz * T))
        if ledge.get("drop"):
            # Up and across; released at the top of the arc, just past the far side.
            hk = _monotone([0.0, a1, 1.0], [0.0, g, 1.0], max(0.0, v_in) * T / hdist, exit_speed * T / hdist)
            zk = ([0.0, a1, 1.0], [0.0, peak, peak], [z_start, 0.0, 0.0])
        else:
            hk = _monotone([0.0, a1, a2, 1.0], [0.0, g, g2, 1.0], max(0.0, v_in) * T / hdist, exit_speed * T / hdist)
            zk = ([0.0, a1, a2, 1.0], [0.0, peak, peak, tz - sz], [z_start, 0.0, 0.0, 0.0])
        over_path = (hk, zk)

    return {
        "over": over_path,
        "drop": bool(ledge.get("drop")),
        "start": (sx, sy, sz),
        "dir": (ux, uy),
        "hdist": hdist,
        "lip": lip,
        "target": (tx, ty, tz),
        "T": T,
        "h": (g, h0, h_mid, h1),
        "z": (z0,),
        "exit": exit_speed,
        "look": ledge.get("look", "?"),
        "lift": ledge.get("lift"),
        "v_in": (vx, vy, vz),
        "top": ledge.get("top", tz),
        "clear": ledge.get("clear"),
        "narrow": bool(ledge.get("narrow")),
        "handoff_u": _OVER_UP if ledge.get("over") else _UP_SHARE,
    }


_USE_SWEEPS = False  # body sweeps (3.13) are switched off: the line-trace room checks are used instead


def _sweeps(ctx=None) -> bool:
    """Body sweeps: only if switched on, and only once traces are known to ignore your own body."""
    return _USE_SWEEPS and _state(ctx).start_mode == "centre"


def _sweep_path(pawn, pc, ledge, ctx=None):
    """Check the move: push a box about the size of your body along the planned path. The normal
    arc first, then a lower one (a tight gap under an awning or beam). Returns None if one fits
    all the way (and keeps its arc height in the ledge), else why not."""
    radius, half = tracing.body(pawn)
    ext = (radius * _SWEEP_RADIUS, radius * _SWEEP_RADIUS, max(half * 0.5, half - _SWEEP_GAP))
    small = (radius * _SWEEP_INNER, radius * _SWEEP_INNER, max(half * 0.5, half - _SWEEP_GAP))
    base = _OVER_CLEAR if ledge.get("over") else _LIP_CLEARANCE
    lifts = (base, base + _HIGH_EXTRA, _LOW_LIFT)  # normal arc, higher (small lips), lower (tight gaps)
    why = "no sensible path"
    for lift in lifts:
        ledge["lift"] = lift
        m = _build_climb(pawn, pc, ledge)
        if m is None:
            continue
        prev = m["start"]
        feet0 = m["start"][2] - half
        blocked = None
        for k in range(1, _SWEEP_STEPS + 1):
            u = k / _SWEEP_STEPS
            pos, _vel = _path(m, u)
            hit = tracing.trace(pawn, prev, pos, extent=ext)
            if hit is not None and math.dist(hit[0], prev) < 2.0:
                # Hit right where this piece starts: the square box's corner already overlaps a wall
                # your round body only touches. Count it only if a box well inside your body hits too.
                hit = tracing.trace(pawn, prev, pos, extent=small)
            if hit is not None:
                blocked = f"your body would hit something at +{hit[0][2] - feet0:.0f} ({int(u * 100)}% of the way)"
                break
            prev = pos
        if blocked is None:
            return None
        why = blocked
    ledge.pop("lift", None)
    return why


# ---------------------------------------------------------------------------------------------
# Debug recording: with Mantle Debug Log on, every attempt is written in full (all traces) to a file
# ---------------------------------------------------------------------------------------------

_REC_NAME = "Modern_Movement_mantle_debug.txt"
_REC_MAX_BYTES = 3_000_000
_rec_path = None
_rec_failed = False


def _rec_file():
    """Where the recording goes: the SDK settings folder (next to Modern_Movement.json) if it can be
    found, else the first real folder above this mod (an .sdkmod is a zip and can't be written)."""
    global _rec_path
    if _rec_path is not None:
        return _rec_path
    folder = None
    try:
        import mods_base as _mb
        folder = getattr(_mb, "SETTINGS_DIR", None)
        if folder is None:
            from mods_base import settings as _mbs  # noqa: PLC0415
            folder = getattr(_mbs, "SETTINGS_DIR", None)
    except Exception:  # noqa: BLE001
        folder = None
    if folder is None or not os.path.isdir(str(folder)):
        here = os.path.abspath(__file__)
        while here and not os.path.isdir(here):
            here = os.path.dirname(here)
        here = os.path.dirname(here)  # the folder holding this mod
        folder = os.path.join(here, "settings") if os.path.isdir(os.path.join(here, "settings")) else here
    _rec_path = os.path.join(str(folder), _REC_NAME)
    return _rec_path


def _rec_write(entry: dict) -> None:
    global _rec_failed
    if _rec_failed:
        return
    try:
        path = _rec_file()
        if os.path.exists(path) and os.path.getsize(path) > _REC_MAX_BYTES:
            os.replace(path, path + ".old")
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            f.flush()
        if new:
            _report(f"recording every attempt to {path}")
    except Exception as e:  # noqa: BLE001
        _rec_failed = True
        logging.warning(f"[Mantle] debug recording could not be written: {e!r}")


def _rec_header(pawn, pc, source, ground, search, ctx=None) -> dict:
    h = {"t": round(core.clock, 3), "src": source, "ground": ground, "mode": _state(ctx).start_mode}
    try:
        h["pos"] = tracing._r(tracing.vec(pawn.Location))
        h["vel"] = tracing._r(tracing.vec(pawn.Velocity))
        h["yaw"] = int(pc.Rotation.Yaw) & 0xFFFF
        h["pitch"] = round(_pitch_deg(pc), 1)
        h["eye"] = round(float(pawn.EyeHeight), 1)
        h["body"] = tracing._r(tracing.body(pawn))
    except Exception:  # noqa: BLE001
        pass
    h["set"] = {
        "max": max_height_slider.value, "vmax": vault_height_slider.value,
        "ma": mantle_angle_slider.value, "va": vault_angle_slider.value,
    }
    h["search"] = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in search.items()}
    return h


def _try_start(pawn, pc, source: str, ground: bool = False, ctx=None, **search) -> bool:
    """Start a mantle if a ledge is in reach. Returns True if one started. With Mantle Debug Log
    on, the whole attempt (every trace) is recorded to a file."""
    ctx = ctx or core.current_context()
    if not debug_option.value:
        return _try_start_inner(pawn, pc, source, ground, ctx=ctx, **search)
    entry = _rec_header(pawn, pc, source, ground, search, ctx=ctx)
    tracing.recorder = []
    ok = False
    try:
        ok = _try_start_inner(pawn, pc, source, ground, ctx=ctx, **search)
    finally:
        entry["traces"] = tracing.recorder
        tracing.recorder = None
        entry["ok"] = ok
        state = _state(ctx)
        if ok and state.mantle is not None:
            m = state.mantle
            entry["climb"] = {
                "target": tracing._r(m["target"]), "T": round(m["T"], 3), "look": m.get("look"),
                "over": bool(m.get("over")), "drop": bool(m.get("drop")), "lift": m.get("lift"),
            }
        else:
            entry["why"] = state.last_reason
        _rec_write(entry)
    return ok


def _try_start_inner(pawn, pc, source: str, ground: bool = False, ctx=None, **search) -> bool:
    ctx = ctx or core.current_context()
    state = _state(ctx)
    ledge = _plan(pawn, pc, ground, ctx=ctx, **search)
    if ledge is None:
        return False

    took_over = core.busy is not None and core.busy != "mantle"
    if took_over:
        core.begin("mantle", ctx=ctx)

    m = _build_climb(pawn, pc, ledge)
    if m is None:
        if took_over:
            core.end("mantle", ctx=ctx)
        return False

    core.begin("mantle", ctx=ctx)
    m.update({"elapsed": 0.0, "last": m["start"], "commanded": 0.0, "stalled": 0})
    # Joiners predict locally; host mirrors the same plan (DJ/dash dual-write).
    if ctx is not None and ctx.role == ExecutionRole.LOCAL_REQUESTER:
        m["remote"] = False
    state.mantle = m
    _set_physics(pawn, _CLIMB_PHYS)
    if audio_option.value and (ctx is None or ctx.presentation):
        fx.play_all(pc, pawn, _GRAB_SOUNDS)
    core.emit("mantle_start", ctx=ctx, lower_weapon=bool(lower_weapon_option.value))
    try:
        from .. import coop_rpc

        if coop_rpc.is_requester(ctx):
            coop_rpc.call_host(coop_rpc.server_mantle_start, _serialize_climb(m))
    except Exception:  # noqa: BLE001
        pass
    _log(
        f"mantle start ({source}): height={ledge['height']:.0f} time={m['T']:.2f}s "
        f"gap={ledge['gap']:.0f} exit={m['exit']:.0f}",
        ctx,
    )
    return True


def _hermite(p0, p1, m0, m1, s):
    """Cubic Hermite on 0..1: value and derivative (m0 / m1 are slopes per unit of s)."""
    s2, s3 = s * s, s * s * s
    v = (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * m1
    d = (6 * s2 - 6 * s) * p0 + (3 * s2 - 4 * s + 1) * m0 + (-6 * s2 + 6 * s) * p1 + (3 * s2 - 2 * s) * m1
    return v, d


def _two_part(u, a, v0, va, v1, m0, ma, m1):
    """Two Hermite pieces joined at u = a (slopes are per unit of u). Returns value, d/du."""
    if u <= a:
        v, d = _hermite(v0, va, m0 * a, ma * a, u / a)
        return v, d / a
    L = 1.0 - a
    v, d = _hermite(va, v1, ma * L, m1 * L, (u - a) / L)
    return v, d / L


def _monotone(us, vs, m_start, m_end):
    """Knots and slopes (per unit of u) for a piecewise Hermite through (us, vs) that never runs
    backwards (Fritsch-Carlson); the end slopes are given, capped so the curve stays monotone."""
    n = len(us)
    sec = [(vs[i + 1] - vs[i]) / (us[i + 1] - us[i]) for i in range(n - 1)]
    ms = [0.0] * n
    ms[0] = min(3.0 * sec[0], max(0.0, m_start))
    ms[-1] = min(3.0 * sec[-1], max(0.0, m_end))
    for i in range(1, n - 1):
        a, b = sec[i - 1], sec[i]
        ms[i] = 0.0 if a <= 0.0 or b <= 0.0 else 2.0 * a * b / (a + b)
    return us, vs, ms


def _piecewise(u, knots):
    """Value and d/du of a piecewise Hermite (us, vs, ms) at u."""
    us, vs, ms = knots
    i = 0
    while i < len(us) - 2 and u > us[i + 1]:
        i += 1
    L = us[i + 1] - us[i]
    v, d = _hermite(vs[i], vs[i + 1], ms[i] * L, ms[i + 1] * L, min(1.0, max(0.0, (u - us[i]) / L)))
    return v, d / L


def _path(m, u):
    """Where the pawn should be at u (0..1) and its velocity there (units per second)."""
    T = m["T"]
    if m.get("over"):
        hk, zk = m["over"]
        u = min(1.0, max(0.0, u))
        h, dh = _piecewise(u, hk)
        zr, dz = _piecewise(u, zk)
        sx, sy, sz = m["start"]
        ux, uy = m["dir"]
        d = m["hdist"]
        return (sx + ux * h * d, sy + uy * h * d, sz + zr), (ux * dh * d / T, uy * dh * d / T, dz / T)
    g, h0, h_mid, h1 = m["h"]
    (z0,) = m["z"]
    sx, sy, sz = m["start"]
    ux, uy = m["dir"]
    tz = m["target"][2]
    u = min(1.0, max(0.0, u))
    h, dh = _two_part(u, _UP_SHARE, 0.0, g, 1.0, h0, h_mid, h1)
    zr, dz = _two_part(u, _UP_SHARE, 0.0, m["lip"] - sz, tz - sz, z0, 0.0, 0.0)
    d = m["hdist"]
    pos = (sx + ux * h * d, sy + uy * h * d, sz + zr)
    vel = (ux * dh * d / T, uy * dh * d / T, dz / T)
    return pos, vel


def _past_face(m, pos) -> bool:
    """True once the pawn's centre is at least as far into the ledge as the end spot, near enough."""
    sx, sy, _ = m["start"]
    ux, uy = m["dir"]
    return (pos[0] - sx) * ux + (pos[1] - sy) * uy >= m["hdist"] - _ARRIVE_TOP


def _camera_motion(m, u, ctx=None) -> None:
    """4. Dip as you grab, rise as you pull up, slight tilt during the climb."""
    ctx = ctx or core.current_context()
    if ctx is not None and not ctx.presentation:
        return
    amount = _CAMERA_MOTION
    if amount <= 0.0:
        return
    if _HANDOFF:
        u = u / max(0.05, m.get("handoff_u", 1.0))  # the climb's own part ends at the hand-off
    u = min(1.0, max(0.0, u))
    if u < 0.4:
        eye = -math.sin(math.pi * u / 0.4)
    else:
        eye = 0.4 * math.sin(math.pi * (u - 0.4) / 0.6)
    roll = math.sin(math.pi * u)
    camera.request("mantle_climb", eye=eye * _DIP_EYE * amount, roll=roll * _DIP_ROLL * amount)


def _gravity_value(pc=None, ctx=None) -> float:
    """Gravity in units/s^2 for mantle hop timing."""
    ctx = ctx or core.current_context()
    state = _state(ctx)
    if pc is None:
        pc = ctx.controller if ctx is not None else core.get_pc_pawn()[0]
    return gravity.gravity_for(pc, state.gravity)


def _watch_gravity(pawn, dt, ctx=None) -> None:
    """While you fall normally, measure gravity from how your vertical speed changes."""
    ctx = ctx or core.current_context()
    state = _state(ctx)
    try:
        vz = float(pawn.Velocity.Z)
    except Exception:  # noqa: BLE001
        state.gravity.previous_vz = None
        return
    if core.phys != core.PHYS_FALLING or state.mantle is not None or dt <= 0.0:
        state.gravity.previous_vz = None
        return
    pc = ctx.controller if ctx is not None else core.get_pc_pawn()[0]
    state.gravity.observe(vz, dt, True, _gravity_signature(ctx))


def _hop(m, pos, half, g):
    """The hop from here: (forward speed, upward speed) that lands your feet on the ledge about where
    the climb was going to (or, over a drop, carries your body past the far side first)."""
    ux, uy = m["dir"]
    sx, sy, _sz = m["start"]
    prog = (pos[0] - sx) * ux + (pos[1] - sy) * uy
    hf = (pos[2] - half) - m["top"]          # your feet above the top / edge, now
    v = _HOP_MIN_SPEED if m.get("narrow") else _HOP_SPEED  # a narrow top: land almost in place
    for _ in range(24):
        if m.get("drop") or m.get("over"):
            # Over an obstacle: only clear it (feet above its top until your body is past its far
            # side); where the arc comes down on the far side is left to the game's physics.
            xc = max(1.0, (m["clear"] or m["hdist"]) - prog)
            t = xc / v
            vz = max(0.0, (_HOP_CLEAR - hf + 0.5 * g * t * t) / t)
            return v, min(vz, _HOP_VZ_MAX)
        dist = max(1.0, m["hdist"] - prog)
        land_h = (m["target"][2] - half - 2.0) - m["top"]  # where your feet end up, relative to the top
        t = dist / v
        vz = (land_h - hf + 0.5 * g * t * t) / t
        ok = vz <= _HOP_VZ_MAX
        if ok and m.get("over") and m.get("clear"):
            # Over an obstacle: still above its top when your body is past its far side.
            tc = max(0.0, m["clear"] - prog) / v
            ok = hf + vz * tc - 0.5 * g * tc * tc >= _HOP_CLEAR
        if ok or v <= _HOP_MIN_SPEED:
            return v, max(0.0, min(vz, _HOP_VZ_MAX))
        v *= 0.9  # slower and higher
    return v, max(0.0, min(vz, _HOP_VZ_MAX))


def _hand_off(pawn, m, pos, ctx=None) -> None:
    """Risen to just above the edge: hop over it under normal physics."""
    radius, half = tracing.body(pawn)
    g = _gravity_value(ctx=ctx)
    v, vz = _hop(m, pos, half, g)
    m["hop"] = (v, vz, g)
    _end(pawn, "handed over", ctx=ctx)


def _run_mantle(pawn, dt: float, ctx=None) -> None:
    state = _state(ctx)
    m = state.mantle
    if core.unusable(pawn):
        _end(pawn, "vehicle or dead", ctx=ctx)
        return

    # Something else (the game's own jump, a landing on the way) may change physics: keep control.
    if core.phys != _CLIMB_PHYS:
        _set_physics(pawn, _CLIMB_PHYS)

    pos = tracing.vec(pawn.Location)
    if debug_option.value:
        try:
            m.setdefault("ticks", []).append([
                round(m["elapsed"], 3), tracing._r(pos), tracing._r(tracing.vec(pawn.Velocity)), core.phys,
            ])
        except Exception:  # noqa: BLE001
            pass

    # Host replica of a joiner climb: Location often does not advance → never stall/held-back.
    remote_hold = bool(m.get("remote"))

    # Held back: while rising, your body has barely moved toward the ledge although the plan has
    # you well on the way (something only your body collides with). Let go now as a normal jump,
    # keeping your upward speed, instead of floating to the top and dropping.
    if (
        not remote_hold
        and m["elapsed"] > _HELD_GRACE
        and m["elapsed"] < m["T"] * _UP_SHARE
    ):
        plan, _v = _path(m, m["elapsed"] / m["T"])
        ux, uy = m["dir"]
        sx, sy, _sz = m["start"]
        want = (plan[0] - sx) * ux + (plan[1] - sy) * uy
        got = (pos[0] - sx) * ux + (pos[1] - sy) * uy
        if want - got > _HELD_GAP and got < want * _HELD_SHARE:
            m["held"] = m.get("held", 0) + 1
        else:
            m["held"] = 0
        if m["held"] >= _HELD_TICKS:
            _end(pawn, "held back", ctx=ctx)
            return

    if _HANDOFF and m["elapsed"] >= m["T"] * m["handoff_u"]:
        _hand_off(pawn, m, pos, ctx=ctx)
        return

    # How much did the last tick's command actually move us? (walls / ceilings)
    if not remote_hold and m["elapsed"] > 0.0 and m["commanded"] > 0.0:
        moved = math.dist(pos, m["last"])
        m["stalled"] = m["stalled"] + 1 if moved < _STALL_RATIO * m["commanded"] else 0
    m["last"] = pos
    m["elapsed"] += dt

    if not remote_hold and m["stalled"] >= _STALL_TICKS:
        _end(pawn, "blocked", ctx=ctx)
        return

    T = m["T"]
    u = m["elapsed"] / T
    tx, ty, tz = m["target"]
    if u >= 1.0:
        if math.dist(pos, m["target"]) <= _ARRIVE_TOP or pos[2] >= tz - 4.0 and _past_face(m, pos):
            _end(pawn, "reached the top", ctx=ctx)
            return
        if m["elapsed"] > T + _OVERTIME:
            _end(pawn, "timed out", ctx=ctx)
            return

    # Follow the curve: its own velocity plus a pull back toward it if we drifted.
    want, vel = _path(m, u + dt / T)
    # Velocity that lands us on next tick's point, softened by the tracking gain.
    k = min(1.0, _TRACK_GAIN * dt)
    cmd = [vel[i] + (want[i] - pos[i] - vel[i] * dt) * k / dt for i in range(3)]
    if u >= 1.0:  # past the end of the curve: just home in on the end spot
        cmd = [(m["target"][i] - pos[i]) / max(dt, 0.05) for i in range(3)]
        cmd[0] += m["dir"][0] * m["exit"]
        cmd[1] += m["dir"][1] * m["exit"]

    # 3. Blend from the motion going in over the first moments.
    blend = _ENTRY_BLEND
    if blend > 0.0 and m["elapsed"] < blend:
        w = m["elapsed"] / blend
        w = w * w * (3.0 - 2.0 * w)
        cmd = [m["v_in"][i] * (1.0 - w) + cmd[i] * w for i in range(3)]

    _camera_motion(m, u, ctx=ctx)

    m["commanded"] = math.sqrt(sum(c * c for c in cmd)) * dt
    core.set_velocity(pawn, cmd[0], cmd[1], cmd[2])
    m["vz"] = cmd[2]
    if debug_option.value and m.get("ticks"):
        m["ticks"][-1].append(tracing._r(cmd))
    # Held movement input must not push us around while the mantle is in charge.
    try:
        pawn.Acceleration.X = 0.0
        pawn.Acceleration.Y = 0.0
        pawn.Acceleration.Z = 0.0
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------------------------
# Hooks into core: jump presses and the per-frame tick
# ---------------------------------------------------------------------------------------------


def _on_air_press(pc, pawn) -> bool:
    """Mid-air jump press. Returns True if it started a mantle (the press is then used up)."""
    ctx = core.current_context()
    state = _state(ctx)
    if not enabled_option.value:
        return False
    state.last_check = core.clock
    if (
        vault_option.value
        and core.clock - state.last_walk < _JUMP_GRACE
        and _moving_into_wall(pc, pawn)
        and _try_start(pawn, pc, "vault", ctx=ctx, **_vault_search(pc, pawn, airborne=True))
    ):
        _report(f"VAULT (just after takeoff, {_mantle_look(ctx)})")
        state.buffer_until = -1.0
        return True
    if _try_start(pawn, pc, "jump", ctx=ctx):
        _report(f"MANTLE ({_mantle_look(ctx)})")
        state.buffer_until = -1.0
        return True
    _report(f"air jump: no mantle ({state.last_reason})")
    state.buffer_until = core.clock + _JUMP_BUFFER
    state.buffer_vault = False
    return False


def _mantle_look(ctx=None) -> str:
    m = _state(ctx).mantle or {}
    return m.get("look", "?") + (", over a drop" if m.get("drop") else ", over" if m.get("over") else "")


def _vault_search(pc, pawn, airborne=False) -> dict:
    """Ledge-search settings for a vault: flat traces straight ahead (reaching further the faster you
    move), the vault look angle and the vault max height. In the air (a vault caught during the
    jump), also accept obstacles you have partly risen past."""
    try:
        speed = core.hspeed(pawn)
    except Exception:  # noqa: BLE001
        speed = 0.0
    vmax = float(vault_height_slider.value)
    search = {
        "flat": _VAULT_REACH + min(_VAULT_REACH_MAX, speed * _VAULT_REACH_TIME),
        "flat_max": vmax,
        "spread": vault_angle_slider.value,
        "vault_max": vmax,
        "over": True,
    }
    if airborne:
        search["min_height"] = _BUFFER_MIN_HEIGHT
    return search


def _on_ground_press(pc, pawn) -> None:
    """Jump pressed on the ground: vault onto a low obstacle you are running at."""
    ctx = core.current_context()
    state = _state(ctx)
    if not (enabled_option.value and vault_option.value):
        return None
    if not _moving_into_wall(pc, pawn):
        _report("jump: not moving forward, ordinary jump")
        _vault_note("not_moving")
        return None
    if _try_start(pawn, pc, "vault", ground=True, ctx=ctx):
        _report(f"VAULT ({_mantle_look(ctx)})")
        _vault_note("started")
        return None
    _report(f"jump: no vault ({state.last_reason}); still looking for {int(_VAULT_BUFFER * 1000)} ms into the jump")
    _vault_note(state.last_reason or "no_ledge")
    state.buffer_until = core.clock + _VAULT_BUFFER
    state.buffer_vault = True
    return None


def _vault_note(result: str) -> None:
    try:
        from .. import diagnostics

        diagnostics.event("mm.vault", result=result)
    except Exception:  # noqa: BLE001
        pass


def _moving_into_wall(pc, pawn) -> bool:
    """True when you are running at the obstacle.

    Sprint and super sprint often leave Acceleration at zero while Velocity is
    still carrying you forward. Speed toward the camera counts as moving in.
    """
    try:
        fx, fy = core.facing(pc)
    except Exception:  # noqa: BLE001
        return True
    try:
        ax, ay = float(pawn.Acceleration.X), float(pawn.Acceleration.Y)
    except Exception:  # noqa: BLE001
        ax, ay = 0.0, 0.0
    accel = math.hypot(ax, ay)
    if accel >= 1.0 and (ax * fx + ay * fy) / accel > 0.3:
        return True
    try:
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
    except Exception:  # noqa: BLE001
        return True
    speed = math.hypot(vx, vy)
    if speed < 200.0:
        return False
    return (vx * fx + vy * fy) / speed > 0.3


# ---------------------------------------------------------------------------------------------
# Hold to mantle
# ---------------------------------------------------------------------------------------------

def _held(pc, ctx=None) -> bool:
    """Jump held down right now (False if the held keys can't be read: the press buffer still works)."""
    state = _state(ctx)
    held = core.jump_held(pc)
    if state.hold_block:
        if not held:
            state.hold_block = False
        return False
    if not state.hold_state_reported and debug_option.value:
        state.hold_state_reported = True
        _report("hold to mantle: " + ("can't read held keys, only presses work" if held is None else "reading held keys OK"))
    return bool(held)


def _tick(pc, pawn, dt) -> None:
    ctx = core.current_context()
    state = _state(ctx)
    # Mirror joiner climbs from the listen-host local tick (same idea as Eternal dash).
    if ctx is not None and ctx.local and ctx.role != ExecutionRole.LOCAL_REQUESTER:
        _service_host_mantles(dt)
    _update_shake(dt, ctx=ctx)
    if pawn is not None:
        _watch_gravity(pawn, dt, ctx=ctx)
    if state.landing_until > 0.0:
        if core.phys == core.PHYS_WALKING:
            state.landing_until = 0.0
            _on_top(pawn, pc=pc, mantle_ctx=ctx)
        elif core.clock > state.landing_until:
            state.landing_until = 0.0
    if core.phys == core.PHYS_WALKING:
        state.last_walk = core.clock
    if state.buffer_vault and core.clock >= state.buffer_until:
        state.buffer_vault = False

    if not enabled_option.value:
        if state.mantle is not None:
            _end(pawn, "mantle disabled", ctx=ctx)
        return
    if pawn is None:
        if state.mantle is not None:
            _end(None, "pawn gone", ctx=ctx)
        return
    if state.mantle is not None:
        _run_mantle(pawn, dt, ctx=ctx)
        return

    if core.phys != core.PHYS_FALLING:
        if core.phys != core.PHYS_WALKING or core.clock >= state.buffer_until or not state.buffer_vault:
            state.buffer_until = -1.0
        return

    now = core.clock
    buffered = now < state.buffer_until
    held = _held(pc, ctx=ctx)
    if not (buffered or held):
        return
    interval = _BUFFER_INTERVAL if buffered else _HOLD_INTERVAL
    if now - state.last_check < interval:
        return
    state.last_check = now
    search = _vault_search(pc, pawn, airborne=True) if (buffered and state.buffer_vault) else {}
    source = "buffered jump" if buffered else "held jump"
    if _try_start(pawn, pc, source, ctx=ctx, **search):
        if buffered and state.buffer_vault:
            _report(f"VAULT (caught during the jump, {_mantle_look(ctx)})")
        elif held and not buffered:
            _report(f"MANTLE (jump held, {_mantle_look(ctx)})")
        state.buffer_until = -1.0


def _snapshot(ctx) -> dict:
    state = _state(ctx)
    climb = state.mantle
    return {
        "active": climb is not None,
        "action": state.action_id,
        "buffered": core.clock < state.buffer_until,
        "vault_buffer": state.buffer_vault,
        "look": climb.get("look", "") if climb is not None else "",
        "elapsed": float(climb.get("elapsed", 0.0)) if climb is not None else 0.0,
    }


def _fall_through_double_jump(ctx, payload):
    """Preserve local jump order: Mantle first, then Double Jump on the same press."""
    from . import double_jump

    kind = payload.get("fallback_kind") or payload.get("kind", "jump")
    if kind == "double_jump_ground" or payload.get("fallback") == "double_jump_ground":
        kind = "ground"
    elif kind not in ("ground", "jump"):
        kind = "jump"
    return double_jump._authority_input(ctx, {"kind": kind})


def _authority_input(ctx, payload):
    kind = payload.get("kind", "jump")
    pawn = ctx.pawn
    pc = ctx.controller
    if pawn is None or core.unusable(pawn):
        return Reason.NO_PAWN, {}
    if kind == "ground":
        core.execute(ctx, _on_ground_press, pc, pawn)
        snap = _snapshot(ctx)
        if snap.get("active"):
            action = authority.allocate_action(ctx, "mantle")
            _state(ctx).action_id = action
            snap["action"] = action
            return Reason.OK, snap
        if payload.get("fallback") in ("double_jump", "double_jump_ground"):
            return _fall_through_double_jump(
                ctx, {**payload, "fallback_kind": "ground"}
            )
        return Reason.OK, snap
    if kind != "jump":
        return Reason.UNSUPPORTED, {}
    try:
        physics = int(pawn.Physics)
    except Exception:
        return Reason.WRONG_PHYSICS, {}
    if physics == core.PHYS_WALKING:
        core.execute(ctx, _on_ground_press, pc, pawn)
        snap = _snapshot(ctx)
        if snap.get("active"):
            action = authority.allocate_action(ctx, "mantle")
            _state(ctx).action_id = action
            snap["action"] = action
            return Reason.OK, snap
        if payload.get("fallback") in ("double_jump", "double_jump_ground"):
            return _fall_through_double_jump(
                ctx, {**payload, "fallback_kind": "ground"}
            )
        return Reason.INVALID_INPUT, snap
    if physics != core.PHYS_FALLING:
        return Reason.WRONG_PHYSICS, {}
    accepted = core.execute(ctx, _on_air_press, pc, pawn)
    snap = _snapshot(ctx)
    if not accepted and not snap.get("active"):
        # Default air path from core requesters asks Mantle with double-jump fallback.
        if payload.get("fallback", "double_jump") == "double_jump":
            return _fall_through_double_jump(ctx, payload)
        return Reason.INVALID_INPUT, snap
    if snap.get("active") and not _state(ctx).action_id:
        action = authority.allocate_action(ctx, "mantle")
        _state(ctx).action_id = action
        snap["action"] = action
    return Reason.OK, snap


def _authority_start(ctx, payload):
    return Reason.UNSUPPORTED, {}


def _authority_tick(ctx, frame) -> None:
    if ctx.local:
        return
    core.execute(ctx, _tick, ctx.controller, ctx.pawn, frame.dt)


def _authority_cancel(ctx, reason: str) -> None:
    def cancel():
        if _state(ctx).mantle is not None:
            _end(ctx.pawn, reason, ctx=ctx)

    core.execute(ctx, cancel)


def _presentation(event: str, payload: dict) -> None:
    if event == "desync":
        return
    state_payload = payload.get("state", payload)
    if not isinstance(state_payload, dict):
        return
    if event == "accept" and audio_option.value:
        ctx = core.local_context()
        if ctx is not None and ctx.pawn is not None:
            features = state_payload.get("features", state_payload)
            mantle_payload = features.get("mantle", state_payload) if isinstance(features, dict) else state_payload
            if mantle_payload.get("active"):
                fx.play_all(ctx.controller, ctx.pawn, _GRAB_SOUNDS)


def on_enable() -> None:
    core.register(
        "mantle",
        tick=_tick,
        ground=_on_ground_press,
        air=_on_air_press,
        priority=15,
    )
    authority.register_feature(
        "mantle",
        authority.FeatureController(
            start=_authority_start,
            input=_authority_input,
            tick=_authority_tick,
            cancel=_authority_cancel,
            snapshot=_snapshot,
        ),
    )
    network.register_presentation("mantle", _presentation)


def on_disable() -> None:
    _HOST_MANTLES.clear()
    for ctx in REGISTRY.contexts():
        if ctx.authority:
            _authority_cancel(ctx, "mod disabled")
    authority.unregister_feature("mantle")
    network.unregister_presentation("mantle")
    core.unregister("mantle")


OPTIONS = [
    enabled_option,
    vault_option,
    *core.settings(
        [audio_option, max_height_slider, shake_slider, lower_weapon_option],
        "Fine-tune mantling and vaulting.",
    ),
]
KEYBINDS = []
HOOKS = []
