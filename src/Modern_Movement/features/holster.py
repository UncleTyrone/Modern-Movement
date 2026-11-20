"""Holster: holster your weapon by hotkey or automatically when sprinting.

H toggles the holster by hand.

Holster While Sprinting (optional)
  While you sprint the weapon is put away straight away, and drawn again as soon as the sprint
  ends. Drawing it yourself mid-sprint (H, fire or aim) leaves it out until the sprint ends.

Sprint Surge (options in surge.py)
  Action skills are blocked while a Sprint Surge is active.
  Press your sprint key again while already sprinting (or tap it twice within a quarter of a
  second, which covers hold-to-sprint) and the weapon is stowed on the spot. Stowed that way
  you also get a speed boost, scaled from the pawn's own GroundSpeed, for as long as the weapon
  stays stowed: until the sprint ends and the weapon is redrawn, or until you draw it yourself
  (H, fire or aim). A weapon that is already away — Holster While Sprinting or the holster key —
  still takes the boost when you press sprint again while sprinting.
  Set "Sprint Surge" to the same key as the game's own sprint binding.

What's different from earlier versions
  * The "don't auto-equip while holstered" block only applies to YOUR inventory manager.
    (It used to block SwitchToBestWeapon for every inventory manager in the game.)
  * Vehicles and dead pawns are ignored, so H in a vehicle no longer holsters the vehicle gun.
  * Fire or aim while holstered by sprinting draws the weapon immediately instead of waiting for the
    sprint to end.
  * Manual equips are detected by watching the weapon slot (it goes empty, then fills
    again) instead of a fixed 1 second grace window.
  * The weapon is checked before it is re-drawn; if it was dropped or sold while holstered
    the best available weapon is drawn instead.
  * If sprint detection fails it backs off instead of retrying every frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mods_base import BoolOption, hook, keybind
from unrealsdk import logging
from unrealsdk import find_class
from unrealsdk.hooks import Block, Type, add_hook, remove_hook

from .. import authority, camera, core, hudfx, network
from ..protocol import Reason
from ..runtime import REGISTRY, ExecutionRole, PlayerContext, object_identity
from . import surge


enabled_option = BoolOption(
    "Holster Enabled",
    True,
    "On",
    "Off",
    description="Turn holster on or off.",
)

holster_sprinting_option = BoolOption(
    "Holster While Sprinting",
    False,
    "On",
    "Off",
    description="When sprinting automatically holster your weapon.",
)

_DEBUG = False  # set to True to print diagnostic messages to the console

_TAP_WINDOW = 0.25  # seconds: how soon a second tap of sprint still counts as 'sprint again'
_HOLSTER_TIMEOUT = 1.5
_SPRINT_RETRY = 2.0
_SURGE_EXIT_GUARD = 0.3
_TILT = 3.0
_TILT_RISE = 0.25
_TILT_FALL = 0.30

_SPRINT_FLAG_NAMES = ["bIsSprinting", "bSprinting", "bSprintActive", "bSprintingMode"]
_SPRINT_FUNC_NAMES = ["IsSprinting"]

_SKILL_FUNCS = (
    "ActionSkillPressed",
    "PressActionSkill",
    "StartActionSkill",
    "ActivateActionSkill",
    "UseActionSkill",
    "ActionSkillButtonPressed",
    "ActionSkillStarted",
)
_SKILL_HOOK_ID = "ModernMovement_SurgeNoSkill"
_skill_hooked: list = []


@dataclass
class StowTransaction:
    """Generation-bound lease on a stowed weapon reference."""

    generation: int = -1
    weapon: Any = None
    weapon_id: int | str | None = None

    def begin(self, ctx: PlayerContext, weapon) -> None:
        self.generation = ctx.pawn_generation
        self.weapon = weapon
        self.weapon_id = object_identity(weapon)

    def clear(self) -> None:
        self.generation = -1
        self.weapon = None
        self.weapon_id = None

    def live(self, ctx: PlayerContext) -> bool:
        return self.weapon is not None and self.generation == ctx.pawn_generation


@dataclass
class HolsterState:
    holstered: bool = False
    stow: StowTransaction = field(default_factory=StowTransaction)
    holster_time: float = 0.0
    seen_empty: bool = False
    sprint_holstered: bool = False
    stow_kind: str | None = None
    sprinting_now: bool | None = None
    last_sprint_active: float = -100.0
    last_tap: float = -100.0
    sprint_suppressed: bool = False
    mantle_holstered: bool = False
    surge_started: float = -100.0
    # GroundSpeed captured once when the surge starts, sprint included.
    # Later samples are the boost itself, and multiplying those stacks.
    surge_reference: float = 0.0
    reference_locked: bool = False
    # Horizontal speed captured once. Later frames scale toward this times the boost,
    # so the bonus cannot stack and a look direction cannot launch them.
    run_pin: float = 0.0
    # Joiner's own GroundSpeed multiplier. The host keeps this instead of its own ramp slider.
    peer_factor: float | None = None
    sent_factor: float = 0.0
    next_speed_send: float = -100.0
    tilt_level: float = 0.0
    sprint_sources: list = field(default_factory=list)
    sprint_source_ok: Any = None
    sprint_scanned: bool = False
    sprint_warned: bool = False
    next_sprint_probe: float = 0.0


_fallback_state = HolsterState()
# Walk GroundSpeed sits near 440. Anything higher is a sprint or a boost we already wrote.
_WALK_PIN_MAX = 520.0
_SURGE_FACTOR_MAX = 1.70


def _state(ctx=None) -> HolsterState:
    ctx = ctx or core.current_context()
    return ctx.state("holster", HolsterState) if ctx is not None else _fallback_state


def _log(msg: str) -> None:
    if _DEBUG:
        logging.info(f"[Holster] {msg}")


# ---------------------------------------------------------------------------------------------
# Sprint detection
# ---------------------------------------------------------------------------------------------


def _scan_for_sprint_fields(state: HolsterState, pawn, pc) -> None:
    for owner_name, owner in (("pawn", pawn), ("pc", pc)):
        if owner is None:
            continue
        try:
            for fld in owner.Class._fields():
                name = str(fld.Name)
                if "sprint" not in name.lower():
                    continue
                _log(f"Found sprint-related field on {owner_name}: {name}")
                entry = (owner_name, name, False)
                if entry not in state.sprint_sources:
                    state.sprint_sources.append(entry)
        except Exception as e:  # noqa: BLE001
            _log(f"Could not scan {owner_name} class fields: {e!r}")


def _build_sprint_sources(state: HolsterState, pawn, pc) -> None:
    if state.sprint_scanned:
        return
    state.sprint_scanned = True
    for owner_name in ("pawn", "pc"):
        for name in _SPRINT_FLAG_NAMES:
            state.sprint_sources.append((owner_name, name, False))
        for name in _SPRINT_FUNC_NAMES:
            state.sprint_sources.append((owner_name, name, True))
    _scan_for_sprint_fields(state, pawn, pc)


def _read_source(src, pawn, pc):
    owner_name, member, is_call = src
    owner = pawn if owner_name == "pawn" else pc
    if owner is None:
        return None
    try:
        value = getattr(owner, member)
        if is_call:
            value = value()
        if isinstance(value, (int, float, bool)):
            return bool(value)
    except Exception:  # noqa: BLE001
        pass
    return None


def is_sprinting(pc, pawn, ctx: PlayerContext | None = None) -> bool | None:
    """True/False if we can tell, None if no sprint source works (retried every few seconds)."""
    ctx = ctx or core.current_context()
    state = _state(ctx)
    if state.sprint_source_ok is not None:
        return _read_source(state.sprint_source_ok, pawn, pc)

    if core.clock < state.next_sprint_probe:
        return None
    _build_sprint_sources(state, pawn, pc)
    for src in state.sprint_sources:
        value = _read_source(src, pawn, pc)
        if value is not None:
            state.sprint_source_ok = src
            _log(f"Using {src[0]}.{src[1]}{'()' if src[2] else ''} to detect sprinting.")
            return value

    state.next_sprint_probe = core.clock + _SPRINT_RETRY
    if not state.sprint_warned:
        state.sprint_warned = True
        logging.warning(
            "[Holster] Could not find a way to detect sprinting, so Sprint Surge falls back to a double tap of the key."
        )
    return None


# ---------------------------------------------------------------------------------------------
# Holster / unholster
# ---------------------------------------------------------------------------------------------


def _on_mantle_start(lower_weapon=False, **_) -> None:
    ctx = core.current_context()
    if ctx is None or not ctx.authority:
        return
    state = _state(ctx)
    if not lower_weapon or state.holstered:
        return
    pawn = ctx.pawn
    if pawn is None or core.unusable(pawn) or pawn.Weapon is None:
        return
    _holster(ctx, pawn)
    if state.holstered:
        state.mantle_holstered = True
        _log("Mantling, holstering.")


def _on_mantle_end(**_) -> None:
    ctx = core.current_context()
    if ctx is None or not ctx.authority:
        return
    state = _state(ctx)
    if not state.mantle_holstered:
        return
    state.mantle_holstered = False
    if state.holstered:
        _log("Mantle ended, drawing weapon.")
        _unholster(ctx, ctx.pawn)


def _clear_state(ctx: PlayerContext | None = None) -> None:
    state = _state(ctx)
    state.mantle_holstered = False
    state.holstered = False
    state.stow.clear()
    state.stow_kind = None
    state.sprint_holstered = False
    state.seen_empty = False
    state.peer_factor = None
    state.sent_factor = 0.0
    state.next_speed_send = -100.0
    state.surge_reference = 0.0
    state.reference_locked = False
    state.run_pin = 0.0


def _holster(ctx: PlayerContext, pawn) -> None:
    ctx.require_authority("holster")
    state = _state(ctx)
    if pawn is None or core.unusable(pawn) or pawn.Weapon is None or pawn.InvManager is None:
        _log("Nothing to holster.")
        return

    state.stow.begin(ctx, pawn.Weapon)
    state.holstered = True
    state.stow_kind = None
    state.seen_empty = False
    state.holster_time = core.clock
    _log(f"Holstering {state.stow.weapon}")
    pawn.InvManager.SetCurrentWeapon(None, False)


def _weapon_still_ours(pawn, weapon) -> bool:
    try:
        if bool(weapon.bDeleteMe):
            return False
        owner = weapon.Owner
        if owner is None or owner != pawn:
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


def _unholster(ctx: PlayerContext, pawn) -> None:
    ctx.require_authority("unholster")
    state = _state(ctx)
    was_surge = state.stow_kind == "surge"
    state.mantle_holstered = False
    state.holstered = False
    state.seen_empty = False
    state.stow_kind = None
    if was_surge:
        try:
            from .. import coop_rpc

            if coop_rpc.is_requester(ctx):
                coop_rpc.call_host(coop_rpc.server_holster, "surge_end")
        except Exception:  # noqa: BLE001
            pass
    if pawn is None or pawn.InvManager is None:
        state.stow.clear()
        return

    weapon = state.stow.weapon if state.stow.live(ctx) else None
    state.stow.clear()
    if weapon is None or not _weapon_still_ours(pawn, weapon):
        _log("Stored weapon is gone, falling back to best weapon.")
        pawn.InvManager.SwitchToBestWeapon()
        return

    _log(f"Drawing {weapon}")
    try:
        pawn.InvManager.SetCurrentWeapon(weapon, False)
    except Exception as e:  # noqa: BLE001
        _log(f"Draw failed ({e!r}), falling back to best weapon.")
        pawn.InvManager.SwitchToBestWeapon()


def _holster_toggle_logic() -> None:
    ctx = core.current_context()
    if ctx is None:
        return
    state = _state(ctx)
    pawn = ctx.pawn
    if pawn is None or core.unusable(pawn):
        return

    if state.holstered:
        if state.sprint_holstered:
            state.sprint_suppressed = True
        state.sprint_holstered = False
        _unholster(ctx, pawn)
    elif enabled_option.value:
        state.sprint_holstered = False
        _holster(ctx, pawn)


@keybind("Toggle Holster", "LeftAlt")
def _holster_toggle() -> None:
    _holster_toggle_request()


@keybind("Toggle Holster (Controller)", None)
def _holster_toggle_pad() -> None:
    _holster_toggle_request()


def _holster_toggle_request() -> None:
    from .. import coop_rpc

    ctx = core.local_context() or REGISTRY.resolve_controller(core.get_pc_pawn()[0])
    if ctx is None:
        return
    if coop_rpc.is_requester(ctx):
        core.execute(ctx, _holster_toggle_logic)
        coop_rpc.call_host(coop_rpc.server_holster, "toggle")
        return
    network.send_intent("holster", "input", {"kind": "toggle"})


@hook("Engine.InventoryManager:SwitchToBestWeapon")
def _holster_block_auto_equip(obj, *_args):
    try:
        pawn = obj.Owner
    except Exception:  # noqa: BLE001
        return None
    ctx = REGISTRY.resolve_pawn(pawn)
    if ctx is None or not ctx.authority:
        return None
    state = _state(ctx)
    if not state.holstered:
        return None
    try:
        if pawn is not None and obj == pawn.InvManager:
            return Block
    except Exception:  # noqa: BLE001
        pass
    return None


def _bl2_second_sprint(state: HolsterState, now: float, previous_tap: float) -> bool:
    """Borderlands 2 toggles sprint. The first Shift press only starts that sprint.

    `sprinting_now` is the previous tick, so this press has not flipped the flag yet.
    """
    if state.sprinting_now is True:
        return True
    if state.last_sprint_active > -50.0 and now - state.last_sprint_active <= _TAP_WINDOW:
        return True
    if state.sprinting_now is None and previous_tap > -50.0 and now - previous_tap <= _TAP_WINDOW:
        return True
    return False


def _sprint_surge_logic() -> None:
    ctx = core.current_context()
    if ctx is None:
        return
    state = _state(ctx)
    pc, pawn = ctx.controller, ctx.pawn
    now = core.clock
    previous_tap = state.last_tap
    state.last_tap = now

    if not surge.enabled_option.value:
        return
    if pawn is None or core.unusable(pawn):
        return

    if _boost_active(ctx) and now - state.surge_started > _SURGE_EXIT_GUARD:
        _log("Sprint Surge pressed again while surging: ending the surge.")
        state.sprint_holstered = False
        state.sprint_suppressed = False
        try:
            _unholster(ctx, pawn)
        except Exception:  # noqa: BLE001
            pass
        state.holstered = False
        state.stow_kind = None
        state.sprint_holstered = False
        return

    from .. import game

    # The Pre-Sequel already treats this key as the second press. Borderlands 2
    # fires it on the same Shift that starts a normal sprint.
    if game.is_bl2() and not _bl2_second_sprint(state, now, previous_tap):
        return

    # The surge key is the request. A sprint flag that dropped after the last surge
    # must not throw this press away.
    if state.holstered or pawn.Weapon is None:
        state.holstered = True
        state.seen_empty = pawn.Weapon is None
        state.sprint_holstered = True
        state.sprint_suppressed = False
        state.stow_kind = "surge"
        _mark_surge_start(ctx)
        _log("Sprint pressed again while holstered: Sprint Surge on (boost).")
        return
    _log("Sprint pressed again: stowing weapon.")
    _holster(ctx, pawn)
    if state.holstered:
        state.sprint_holstered = True
        state.sprint_suppressed = False
        state.stow_kind = "surge"
        _mark_surge_start(ctx)


@keybind("Sprint Surge", "LeftShift")
def _sprint_surge_pressed() -> None:
    _sprint_surge_request()


@keybind("Sprint Surge (Controller)", "XboxTypeS_LeftThumbstick")
def _sprint_surge_pressed_pad() -> None:
    _sprint_surge_request()


def _sprint_surge_request() -> None:
    from .. import coop_rpc

    ctx = core.local_context() or REGISTRY.resolve_controller(core.get_pc_pawn()[0])
    if ctx is None:
        return
    # A sprint press ends a slide immediately. BeginSprint misses that press while the
    # sprint that started the slide is still flagged on, and the slide then sits until
    # its old timer runs out.
    if ctx.local and ctx.authority and not coop_rpc.is_requester(ctx):
        from . import slide

        core.execute(ctx, slide.try_consume_sprint, ctx.controller, ctx.pawn)
    if coop_rpc.is_requester(ctx):
        from . import slide

        if core.execute(ctx, slide.try_consume_sprint, ctx.controller, ctx.pawn):
            coop_rpc.call_host(coop_rpc.server_slide_exit)
        before = _boost_active(ctx)
        core.execute(ctx, _sprint_surge_logic)
        after = _boost_active(ctx)
        if after and not before:
            coop_rpc.call_host(coop_rpc.server_holster, "surge")
            state = _state(ctx)
            state.next_speed_send = -100.0
            _publish_surge_speed(ctx, True)
        elif before and not after:
            coop_rpc.call_host(coop_rpc.server_holster, "surge_end")
            state = _state(ctx)
            state.next_speed_send = -100.0
            if state.sent_factor <= 1.01:
                state.sent_factor = 1.1
            _publish_surge_speed(ctx, False)
        return
    network.send_intent("holster", "input", {"kind": "surge"})


def _mark_surge_start(ctx: PlayerContext | None = None) -> None:
    """Super sprint keeps the game's own sprinting sounds. No extra whoosh."""
    _state(ctx).surge_started = core.clock


def _update_tilt(ctx: PlayerContext, dt: float, active: bool) -> None:
    state = _state(ctx)
    if active:
        state.tilt_level = min(1.0, state.tilt_level + dt / _TILT_RISE)
    else:
        state.tilt_level = max(0.0, state.tilt_level - dt / _TILT_FALL)
    amount = surge.tilt_slider.value / 100.0
    if state.tilt_level > 0.0 and amount > 0.0:
        e = state.tilt_level * state.tilt_level * (3.0 - 2.0 * state.tilt_level)
        camera.request("surge", pitch=-_TILT * amount * e)


def _local_surge_factor(ctx: PlayerContext) -> float:
    """This machine's ramp, as a multiplier on the speed they already had (1.30 .. 1.70)."""
    state = _state(ctx)
    return 1.0 + surge.boost(core.clock - state.surge_started) / 100.0


def _clamp_factor(value: float) -> float:
    """1.30..1.70. A larger number is an old absolute speed, and writing that launches them."""
    return min(_SURGE_FACTOR_MAX, max(1.0, float(value)))


def _note_base(ctx: PlayerContext, pawn, factor: float) -> float:
    """The run this surge multiplies. A sprint counts. Our own boosted write does not."""
    state = _state(ctx)
    if state.reference_locked and state.surge_reference >= 200.0:
        return state.surge_reference
    try:
        current = float(pawn.GroundSpeed) if pawn is not None else 440.0
    except Exception:  # noqa: BLE001
        current = 440.0
    factor = _clamp_factor(factor)
    if state.surge_reference >= 200.0:
        boosted = state.surge_reference * factor
        own = abs(current - boosted) <= max(30.0, boosted * 0.08)
        if own:
            state.reference_locked = True
            return state.surge_reference
        # The game turned a walk sample into the sprint. Take that once.
        if _WALK_PIN_MAX < current <= 1100.0 and current > state.surge_reference + 40.0:
            state.surge_reference = current
            state.reference_locked = True
            return current
        if current > 1100.0:
            state.reference_locked = True
        return state.surge_reference
    if 200.0 <= current <= 1100.0:
        state.surge_reference = current
    else:
        state.surge_reference = 440.0
    if state.surge_reference > _WALK_PIN_MAX:
        state.reference_locked = True
    return state.surge_reference


def _speed_multiplier(ctx: PlayerContext, pawn) -> float:
    """Same 30–70% GroundSpeed boost the local player gets. Not a second speed on top."""
    del pawn
    state = _state(ctx)
    if not ctx.local and state.peer_factor is not None and state.peer_factor > 1.001:
        return _clamp_factor(state.peer_factor)
    return _clamp_factor(_local_surge_factor(ctx))


def _write_surge_speed(ctx: PlayerContext, pawn, factor: float) -> None:
    """Multiply the GroundSpeed they already have. Do not touch Velocity.

    Forcing the base down to a walk made a sprint slower, so the surge vanished.
    Writing Velocity made other players run ahead and then snap back.
    """
    if pawn is None:
        return
    factor = _clamp_factor(factor)
    base = _note_base(ctx, pawn, factor)
    core.set_speed_mult("surge", factor, ctx)
    try:
        current = float(pawn.GroundSpeed)
    except Exception:  # noqa: BLE001
        current = base
    lease = ctx.ground_speed
    # Hold the pin. If the lease adopted the boosted GroundSpeed, the next
    # multiply would stack and they would run away from the host.
    lease.pawn_key = ctx.pawn_key
    lease.base = base
    lease.written = current
    try:
        core._apply_speed(ctx, pawn)
    except Exception:  # noqa: BLE001
        try:
            pawn.GroundSpeed = base * factor
        except Exception:  # noqa: BLE001
            pass
    _scale_run(ctx, pawn, factor)


def _scale_run(ctx: PlayerContext, pawn, factor: float) -> None:
    """Bring an existing run up to the pinned speed times the boost. Never invent a direction."""
    if pawn is None or ctx.busy in ("slide", "dash", "mantle", "slam"):
        return
    try:
        if int(pawn.Physics) != core.PHYS_WALKING:
            return
        vx = float(pawn.Velocity.X)
        vy = float(pawn.Velocity.Y)
    except Exception:  # noqa: BLE001
        return
    speed = math.hypot(vx, vy)
    state = _state(ctx)
    if state.run_pin < 350.0:
        if speed < 350.0:
            return
        state.run_pin = speed
    target = state.run_pin * _clamp_factor(factor)
    if speed < 350.0 or speed >= target * 0.92:
        return
    core.set_velocity(pawn, vx / speed * target, vy / speed * target)


def _apply_speed_boost(ctx: PlayerContext, pawn, active: bool) -> None:
    state = _state(ctx)
    if pawn is None or not active:
        state.peer_factor = None
        state.surge_reference = 0.0
        state.reference_locked = False
        state.run_pin = 0.0
        core.set_speed_mult("surge", None, ctx)
        try:
            core._apply_speed(ctx, pawn)
        except Exception:  # noqa: BLE001
            pass
        return
    _write_surge_speed(ctx, pawn, _speed_multiplier(ctx, pawn))


def apply_peer_factor(ctx: PlayerContext, value: float) -> None:
    """Host: store the joiner's boost (1.30–1.70) and set GroundSpeed. Velocity stays theirs."""

    def apply() -> None:
        state = _state(ctx)
        pawn = ctx.pawn
        if value <= 1.001:
            state.peer_factor = None
            _apply_speed_boost(ctx, pawn, False)
            return
        state.peer_factor = _clamp_factor(value)
        _write_surge_speed(ctx, pawn, state.peer_factor)

    core.execute(ctx, apply)


def _publish_surge_speed(ctx: PlayerContext, active: bool) -> None:
    """Joiner: tell the host this player's boost, the same 1.30–1.70 the host uses."""
    from .. import coop_rpc

    if not coop_rpc.is_requester(ctx):
        return
    state = _state(ctx)
    if not active:
        if state.sent_factor > 1.01 and core.clock >= state.next_speed_send:
            state.next_speed_send = core.clock + 0.25
            if coop_rpc.call_host(coop_rpc.server_speed_mult, 1.0):
                state.sent_factor = 0.0
        return
    factor = _clamp_factor(_local_surge_factor(ctx))
    due = core.clock >= state.next_speed_send
    changed = abs(factor - state.sent_factor) >= 0.01
    if not due and not changed:
        return
    state.next_speed_send = core.clock + 0.25
    if coop_rpc.call_host(coop_rpc.server_speed_mult, factor):
        state.sent_factor = factor


def _service_host_surges() -> None:
    """Keep a joiner's GroundSpeed on their own boost. Do not write their Velocity."""
    try:
        from . import slide as slide_mod

        busy = slide_mod._HOST_SLIDES
        airborne = slide_mod._HOST_JUMPS
    except Exception:  # noqa: BLE001
        busy = {}
        airborne = {}
    for ctx in REGISTRY.contexts():
        if ctx.local or ctx.pawn is None or core.unusable(ctx.pawn):
            continue
        if ctx.key.player_id in busy or ctx.key.player_id in airborne:
            continue
        state = _state(ctx)
        if state.peer_factor is None or state.peer_factor <= 1.001:
            continue
        try:
            core.execute(ctx, _write_surge_speed, ctx, ctx.pawn, state.peer_factor)
        except Exception:  # noqa: BLE001
            pass


def _boost_active(ctx: PlayerContext | None = None) -> bool:
    state = _state(ctx)
    return bool(state.holstered and state.stow_kind == "surge" and surge.enabled_option.value)


def _draw_now_for_fire(ctx: PlayerContext, obj) -> None:
    state = _state(ctx)
    if not (state.holstered and (state.sprint_holstered or state.mantle_holstered)):
        return
    try:
        if ctx.controller is None or obj != ctx.controller:
            return
    except Exception:  # noqa: BLE001
        return
    _log("Fire/aim pressed while holstered, drawing.")
    if state.sprint_holstered:
        state.sprint_suppressed = True
    state.sprint_holstered = False
    _unholster(ctx, ctx.pawn)


@hook("Engine.PlayerController:StartFire")
def _holster_on_fire(obj, *_args) -> None:
    ctx = REGISTRY.resolve_controller(obj)
    if ctx is None:
        return
    if not ctx.authority:
        network.send_intent("holster", "input", {"kind": "draw"})
        return
    core.execute(ctx, _draw_now_for_fire, obj)


@hook("Engine.PlayerController:StartAltFire")
def _holster_on_aim(obj, *_args) -> None:
    ctx = REGISTRY.resolve_controller(obj)
    if ctx is None:
        return
    if not ctx.authority:
        network.send_intent("holster", "input", {"kind": "draw"})
        return
    core.execute(ctx, _draw_now_for_fire, obj)


def _surge_blocks_skill(obj, *_args):
    try:
        ctx = REGISTRY.resolve_controller(obj)
        if ctx is None or not ctx.authority:
            return None
        state = _state(ctx)
        if not (state.holstered and state.stow_kind == "surge" and surge.enabled_option.value):
            return None
        if ctx.controller is not None and obj == ctx.controller:
            _log("Action skill blocked during Sprint Surge.")
            if ctx.presentation:
                hudfx.surge_blocked()
            return Block
    except Exception:  # noqa: BLE001
        pass
    return None


def _hook_action_skill() -> None:
    _unhook_action_skill()
    try:
        names = sorted(
            str(f.Name) for f in find_class("WillowPlayerController")._fields() if "actionskill" in str(f.Name).lower()
        )
        logging.info(f"[Sprint Surge] action skill related controller members: {names}")
    except Exception:  # noqa: BLE001
        pass
    for fn in _SKILL_FUNCS:
        path = f"WillowGame.WillowPlayerController:{fn}"
        try:
            add_hook(path, Type.PRE, _SKILL_HOOK_ID, _surge_blocks_skill)
            _skill_hooked.append(path)
        except Exception:  # noqa: BLE001
            pass


def _unhook_action_skill() -> None:
    while _skill_hooked:
        try:
            remove_hook(_skill_hooked.pop(), Type.PRE, _SKILL_HOOK_ID)
        except Exception:  # noqa: BLE001
            pass


def _update_sprint_holster(ctx: PlayerContext, pc, pawn, sprinting) -> None:
    state = _state(ctx)
    sprinting_ok = bool(enabled_option.value and holster_sprinting_option.value)
    surge_ok = bool(surge.enabled_option.value)
    if state.sprint_holstered and not (sprinting_ok if state.stow_kind == "sprinting" else surge_ok):
        state.sprint_holstered = False
        _unholster(ctx, pawn)
    if sprinting is None:
        return

    if sprinting:
        if sprinting_ok and not state.holstered and not state.sprint_suppressed and pawn.Weapon is not None:
            _log("Sprinting, holstering.")
            _holster(ctx, pawn)
            if state.holstered:
                state.sprint_holstered = True
                state.stow_kind = "sprinting"
        return

    state.sprint_suppressed = False
    if state.sprint_holstered:
        _log("Sprint ended, drawing weapon.")
        state.sprint_holstered = False
        _unholster(ctx, pawn)


def _tick(pc, pawn, dt) -> None:
    ctx = core.current_context()
    if ctx is None or not ctx.authority:
        return
    if ctx.role == ExecutionRole.LOCAL_HOST:
        _service_host_surges()
    state = _state(ctx)

    if pawn is None or core.unusable(pawn):
        if state.holstered or state.sprint_holstered:
            _clear_state(ctx)
        state.sprinting_now = None
        _apply_speed_boost(ctx, pawn if pawn is not None and not core.unusable(pawn) else None, False)
        _publish_surge_speed(ctx, False)
        if ctx.presentation:
            _update_tilt(ctx, dt, False)
            hudfx.surge_state(False, 0.0)
        return

    sprinting = is_sprinting(pc, pawn, ctx)
    state.sprinting_now = sprinting
    if sprinting:
        state.last_sprint_active = core.clock

    # Remote sprint flags on the listen host are not trustworthy — never auto-end a joiner's
    # surge from them. Joiners send surge_end / draw when they stop locally.
    if ctx.local:
        _tick_holster(ctx, pc, pawn, sprinting)
    elif state.stow_kind == "surge" and state.holstered:
        pass
    else:
        _tick_holster(ctx, pc, pawn, sprinting)
    boost = _boost_active(ctx)
    state_now = _state(ctx)
    # The host's holster flag can drop while the joiner is still surging. Their last
    # multiplier stays until they send 1.0, so the server pawn does not snap back to a walk.
    if (
        not boost
        and not ctx.local
        and state_now.peer_factor is not None
        and state_now.peer_factor > 1.001
    ):
        _write_surge_speed(ctx, pawn, state_now.peer_factor)
    else:
        _apply_speed_boost(ctx, pawn, boost)
    _publish_surge_speed(ctx, boost)
    if ctx.presentation:
        _update_tilt(ctx, dt, boost)
        hudfx.surge_state(
            boost and surge.indicator_option.value,
            surge.ramp(core.clock - state.surge_started),
        )


def _tick_holster(ctx: PlayerContext, pc, pawn, sprinting) -> None:
    state = _state(ctx)
    if state.holstered and not state.sprint_holstered and not state.mantle_holstered and not enabled_option.value:
        _log("Holster turned off while holstered, drawing the weapon.")
        _unholster(ctx, pawn)
        return
    if not (enabled_option.value or surge.enabled_option.value) and not state.holstered:
        return

    if state.holstered:
        if pawn.Weapon is None:
            state.seen_empty = True
        elif state.seen_empty:
            state.mantle_holstered = False
            _log("Weapon equipped while holstered, clearing holster state.")
            if state.sprint_holstered:
                state.sprint_suppressed = True
            state.holstered = False
            state.sprint_holstered = False
            state.stow.clear()
            return
        elif core.clock - state.holster_time > _HOLSTER_TIMEOUT:
            _log("Holster never took effect, clearing holster state.")
            state.mantle_holstered = False
            state.holstered = False
            state.sprint_holstered = False
            state.stow.clear()
            return

    _update_sprint_holster(ctx, pc, pawn, sprinting)


def _force_surge_start(ctx: PlayerContext) -> None:
    """Host path for a joiner who already passed the double-tap check locally.

    Never re-run the tap window on the listen host — remote last_tap/sprint edges are not reliable.
    """
    state = _state(ctx)
    pawn = ctx.pawn
    if pawn is None or core.unusable(pawn):
        return
    if not surge.enabled_option.value:
        return
    # "surge" means start. Ending is a separate message. Treating a second start as
    # "turn it off" made the next super sprint die on the listen host.
    if state.holstered:
        state.sprint_holstered = True
        state.sprint_suppressed = False
        state.stow_kind = "surge"
        _mark_surge_start(ctx)
        _apply_speed_boost(ctx, pawn, True)
        return
    if pawn.Weapon is not None:
        _holster(ctx, pawn)
    else:
        # Server pawn may already look empty while the joiner is mid-stow.
        state.holstered = True
        state.seen_empty = True
    state.sprint_holstered = True
    state.sprint_suppressed = False
    state.stow_kind = "surge"
    _mark_surge_start(ctx)
    _apply_speed_boost(ctx, pawn, True)


def _authority_input(ctx, payload):
    kind = payload.get("kind")
    pawn = ctx.pawn
    if pawn is None or core.unusable(pawn):
        return Reason.NO_PAWN, {}
    if kind == "surge":
        from . import slide

        if core.execute(ctx, slide.try_consume_sprint, ctx.controller, pawn):
            pass
        if not surge.enabled_option.value:
            return Reason.DISABLED, _snapshot(ctx)
        # Joiners: force-start. Host/local intents still use the tap logic via keybind path.
        if not ctx.local:
            core.execute(ctx, _force_surge_start, ctx)
            # Guarantee GroundSpeed lands on the same tick as the RPC (don't wait for PlayerTick).
            core.execute(ctx, _apply_speed_boost, ctx, pawn, _boost_active(ctx))
            try:
                core._apply_speed(ctx, pawn)
            except Exception:  # noqa: BLE001
                pass
        else:
            core.execute(ctx, _sprint_surge_logic)
        return Reason.OK, _snapshot(ctx)
    if kind == "surge_end":
        def end_surge():
            state = _state(ctx)
            if state.sprint_holstered:
                state.sprint_suppressed = True
            state.sprint_holstered = False
            if state.holstered:
                _unholster(ctx, pawn)
            _apply_speed_boost(ctx, pawn, False)

        core.execute(ctx, end_surge)
        return Reason.OK, _snapshot(ctx)
    if kind == "toggle":
        if not enabled_option.value and not _state(ctx).holstered:
            return Reason.DISABLED, _snapshot(ctx)
        core.execute(ctx, _holster_toggle_logic)
        return Reason.OK, _snapshot(ctx)
    if kind == "draw":
        def draw():
            _draw_now_for_fire(ctx, ctx.controller)

        core.execute(ctx, draw)
        return Reason.OK, _snapshot(ctx)
    return Reason.UNSUPPORTED, {}


def _authority_tick(ctx, frame) -> None:
    if ctx.local:
        return
    core.execute(ctx, _tick, ctx.controller, ctx.pawn, frame.dt)


def _authority_cancel(ctx, reason: str) -> None:
    def cancel():
        state = _state(ctx)
        if state.holstered:
            _unholster(ctx, ctx.pawn)
        else:
            _clear_state(ctx)
        _apply_speed_boost(ctx, ctx.pawn, False)

    core.execute(ctx, cancel)


def _snapshot(ctx) -> dict:
    state = _state(ctx)
    boost = _boost_active(ctx)
    return {
        "holstered": state.holstered,
        "stow_kind": state.stow_kind or "",
        "sprint_holstered": state.sprint_holstered,
        "surge_active": boost,
        "surge_elapsed": max(0.0, ctx.clock - state.surge_started) if boost else 0.0,
        "generation": ctx.pawn_generation,
    }


def surge_snapshot(ctx) -> dict:
    state = _state(ctx)
    boost = _boost_active(ctx)
    elapsed = max(0.0, ctx.clock - state.surge_started) if boost else 0.0
    return {
        "active": boost,
        "elapsed": elapsed,
        "ramp": surge.ramp(elapsed),
        "boost_pct": surge.boost(elapsed) if boost else 0.0,
    }


def _presentation(event: str, payload: dict) -> None:
    if event == "desync":
        hudfx.surge_state(False, 0.0)
        return
    state_payload = payload.get("state", payload)
    if not isinstance(state_payload, dict):
        return
    features = state_payload.get("features")
    holster_payload = features.get("holster") if isinstance(features, dict) else state_payload
    if not isinstance(holster_payload, dict):
        holster_payload = state_payload
    active = bool(holster_payload.get("surge_active", False))
    elapsed = float(holster_payload.get("surge_elapsed", 0.0))
    if active and surge.indicator_option.value:
        hudfx.surge_state(True, surge.ramp(elapsed))
    elif event in ("state", "accept", "end"):
        hudfx.surge_state(False, 0.0)


@hook("WillowGame.WillowPlayerController:PlayerWalking.PlayerMove", Type.PRE)
def _speed_before_move(obj, _args, _ret, _func) -> None:
    """GroundSpeed has to be the surged value before the engine builds this move."""
    ctx = REGISTRY.resolve_controller(obj)
    if ctx is None or not ctx.authority or not ctx.speed_multipliers:
        return
    pawn = ctx.pawn
    if pawn is None or core.unusable(pawn):
        return
    factor = ctx.speed_multipliers.get("surge")
    try:
        if factor is not None and factor > 1.001:
            core.execute(ctx, _write_surge_speed, ctx, pawn, factor)
        else:
            core.execute(ctx, core._apply_speed, ctx, pawn)
    except Exception:  # noqa: BLE001
        pass


def on_enable() -> None:
    for ctx in REGISTRY.contexts():
        state = _state(ctx)
        _clear_state(ctx)
        state.sprint_suppressed = False
        state.sprinting_now = None
        state.last_sprint_active = -100.0
        state.last_tap = -100.0
        state.surge_started = -100.0
        state.tilt_level = 0.0
    core.register(
        "holster",
        tick=_tick,
        events={"mantle_start": _on_mantle_start, "mantle_end": _on_mantle_end},
        priority=30,
    )
    authority.register_feature(
        "holster",
        authority.FeatureController(
            input=_authority_input,
            tick=_authority_tick,
            cancel=_authority_cancel,
            snapshot=_snapshot,
        ),
    )
    network.register_presentation("holster", _presentation)
    _hook_action_skill()


def on_disable() -> None:
    for ctx in REGISTRY.contexts():
        if ctx.authority:
            try:
                core.execute(ctx, _apply_speed_boost, ctx, ctx.pawn, False)
            except Exception:  # noqa: BLE001
                pass
            state = _state(ctx)
            if state.holstered and ctx.pawn is not None:
                try:
                    core.execute(ctx, _unholster, ctx, ctx.pawn)
                except Exception:  # noqa: BLE001
                    pass
            _authority_cancel(ctx, "mod disabled")
    authority.unregister_feature("holster")
    network.unregister_presentation("holster")
    _unhook_action_skill()
    core.unregister("holster")


OPTIONS = [
    enabled_option,
    *core.settings([holster_sprinting_option], "Fine-tune holstering."),
]
KEYBINDS = [_holster_toggle, _holster_toggle_pad, _sprint_surge_pressed, _sprint_surge_pressed_pad]
HOOKS = [_holster_block_auto_equip, _holster_on_fire, _holster_on_aim]