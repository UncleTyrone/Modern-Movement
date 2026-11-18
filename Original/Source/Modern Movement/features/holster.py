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
  (H, fire or aim). A weapon put away by Holster While Sprinting is upgraded to a Sprint Surge (boost on)
  if you tap sprint. Weapons stowed with H never get the boost.
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

from mods_base import BoolOption, hook, keybind
from unrealsdk import logging
from unrealsdk import find_class
from unrealsdk.hooks import Block, Type, add_hook, remove_hook

from .. import camera, core, hudfx
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

_holstered = False
_stored_weapon = None
_holster_time = 0.0
_seen_empty = False  # the weapon slot has gone empty since we holstered

# True only when the current holster was caused by sprinting (not by the H key).
_sprint_holstered = False
# How the current sprint-holster happened: "sprinting" (Holster While Sprinting) or "surge" (Sprint Surge, gets the
# speed boost). None for H-key holsters.
_stow_kind = None
_sprinting_now = None      # last frame's sprint flag (None = can't be detected)
_last_sprint_active = -100.0
_last_tap = -100.0         # game-clock time of the previous sprint-key press
_sprint_suppressed = False  # you drew the weapon by hand mid-sprint: don't holster-while-sprinting again until it ends

# If the weapon slot never empties after holstering, assume the holster failed after this long.
_TAP_WINDOW = 0.25  # seconds: how soon a second tap of sprint still counts as 'sprint again'
_HOLSTER_TIMEOUT = 1.5
# Seconds between attempts to find a sprint flag when none has worked.
_SPRINT_RETRY = 2.0

_SPRINT_FLAG_NAMES = ["bIsSprinting", "bSprinting", "bSprintActive", "bSprintingMode"]
_SPRINT_FUNC_NAMES = ["IsSprinting"]
_sprint_sources: list = []  # list of (owner_name, member_name, is_call)
_sprint_source_ok = None
_sprint_scanned = False
_sprint_warned = False
_next_sprint_probe = 0.0

# (The Sprint Surge speed boost is a GroundSpeed multiplier applied by core.set_speed_mult.)


def _log(msg: str) -> None:
    if _DEBUG:
        logging.info(f"[Holster] {msg}")


# ---------------------------------------------------------------------------------------------
# Sprint detection
# ---------------------------------------------------------------------------------------------


def _scan_for_sprint_fields(pawn, pc) -> None:
    """Look for any property with 'sprint' in its name and add it as a candidate source."""
    for owner_name, owner in (("pawn", pawn), ("pc", pc)):
        if owner is None:
            continue
        try:
            for field in owner.Class._fields():
                name = str(field.Name)
                if "sprint" not in name.lower():
                    continue
                _log(f"Found sprint-related field on {owner_name}: {name}")
                if (owner_name, name, False) not in _sprint_sources:
                    _sprint_sources.append((owner_name, name, False))
        except Exception as e:  # noqa: BLE001
            _log(f"Could not scan {owner_name} class fields: {e!r}")


def _build_sprint_sources(pawn, pc) -> None:
    global _sprint_scanned
    if _sprint_scanned:
        return
    _sprint_scanned = True
    for owner_name in ("pawn", "pc"):
        for name in _SPRINT_FLAG_NAMES:
            _sprint_sources.append((owner_name, name, False))
        for name in _SPRINT_FUNC_NAMES:
            _sprint_sources.append((owner_name, name, True))
    _scan_for_sprint_fields(pawn, pc)


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


def _is_sprinting(pc, pawn):
    """True/False if we can tell, None if no sprint source works (retried every few seconds)."""
    global _sprint_source_ok, _sprint_warned, _next_sprint_probe

    if _sprint_source_ok is not None:
        return _read_source(_sprint_source_ok, pawn, pc)

    if core.clock < _next_sprint_probe:
        return None
    _build_sprint_sources(pawn, pc)
    for src in _sprint_sources:
        value = _read_source(src, pawn, pc)
        if value is not None:
            _sprint_source_ok = src
            _log(f"Using {src[0]}.{src[1]}{'()' if src[2] else ''} to detect sprinting.")
            return value

    _next_sprint_probe = core.clock + _SPRINT_RETRY
    if not _sprint_warned:
        _sprint_warned = True
        logging.warning(
            "[Holster] Could not find a way to detect sprinting, so Sprint Surge falls back to a double tap of the key."
        )
    return None


# ---------------------------------------------------------------------------------------------
# Holster / unholster
# ---------------------------------------------------------------------------------------------


_mantle_holstered = False  # we put the weapon away for a mantle: draw it again when the mantle ends


def _on_mantle_start(lower_weapon=False, **_) -> None:
    """Mantle started: put the weapon away for the climb (unless it is already away)."""
    global _mantle_holstered
    if not lower_weapon or _holstered:
        return
    pawn = core.get_pc_pawn()[1]
    if pawn is None or core.unusable(pawn) or pawn.Weapon is None:
        return
    _holster(pawn)
    if _holstered:
        _mantle_holstered = True
        _log("Mantling, holstering.")


def _on_mantle_end(**_) -> None:
    """Mantle ended (on top or not): draw the weapon we put away for it."""
    global _mantle_holstered
    if not _mantle_holstered:
        return
    _mantle_holstered = False
    if _holstered:
        _log("Mantle ended, drawing weapon.")
        _unholster(core.get_pc_pawn()[1])


def _clear_state() -> None:
    global _holstered, _stored_weapon, _sprint_holstered, _seen_empty
    global _stow_kind, _mantle_holstered
    _mantle_holstered = False
    _holstered = False
    _stored_weapon = None
    _stow_kind = None
    _sprint_holstered = False
    _seen_empty = False


def _holster(pawn) -> None:
    global _holstered, _stored_weapon, _holster_time, _seen_empty, _stow_kind

    if pawn is None or core.unusable(pawn) or pawn.Weapon is None or pawn.InvManager is None:
        _log("Nothing to holster.")
        return

    _stored_weapon = pawn.Weapon
    _holstered = True
    _stow_kind = None  # Sprint Surge sets "surge" afterwards
    _seen_empty = False
    _holster_time = core.clock
    _log(f"Holstering {_stored_weapon}")
    pawn.InvManager.SetCurrentWeapon(None, False)


def _weapon_still_ours(pawn, weapon) -> bool:
    """False only when we can tell the weapon was dropped / sold / destroyed while holstered."""
    try:
        if bool(weapon.bDeleteMe):
            return False
        owner = weapon.Owner
        if owner is None or owner != pawn:
            return False
    except Exception:  # noqa: BLE001
        pass  # can't tell: assume it's fine
    return True


def _unholster(pawn) -> None:
    global _holstered, _seen_empty, _mantle_holstered

    _mantle_holstered = False
    _holstered = False  # first, so our own SwitchToBestWeapon below isn't blocked
    _seen_empty = False
    if pawn is None or pawn.InvManager is None:
        return

    weapon = _stored_weapon
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


@keybind("Toggle Holster", "LeftAlt")
def _holster_toggle() -> None:
    global _sprint_holstered, _sprint_suppressed

    _pc, pawn = core.get_pc_pawn()
    if pawn is None or core.unusable(pawn):
        return

    if _holstered:
        if _sprint_holstered:
            _sprint_suppressed = True  # drawn by hand mid-sprint: leave it out until the sprint ends
        _sprint_holstered = False
        _unholster(pawn)
    elif enabled_option.value:
        _sprint_holstered = False
        _holster(pawn)


@hook("Engine.InventoryManager:SwitchToBestWeapon")
def _holster_block_auto_equip(obj, *_args):
    """Stop the game pulling a weapon back out while YOU are holstered (and only you)."""
    if not _holstered:
        return None
    try:
        _pc, pawn = core.get_pc_pawn()
        if pawn is not None and obj == pawn.InvManager:
            return Block
    except Exception:  # noqa: BLE001
        pass
    return None


@keybind("Sprint Surge", "LeftShift")
def _sprint_surge_pressed() -> None:
    """Sprint key pressed: if that is a "sprint again", stow the weapon (with the speed boost)."""
    global _last_tap, _sprint_holstered, _stow_kind, _sprint_suppressed

    now = core.clock
    previous_tap = _last_tap
    _last_tap = now

    if not surge.enabled_option.value:
        return
    _pc, pawn = core.get_pc_pawn()
    if pawn is None or core.unusable(pawn):
        return

    # Already surging: this press takes you back out (draw the weapon, boost off).
    if _boost_active() and now - _surge_started > _SURGE_EXIT_GUARD:
        _log("Sprint Surge pressed again while surging: ending the surge.")
        _sprint_holstered = False
        _sprint_suppressed = True  # still sprinting: don't stow again until the sprint ends
        _unholster(pawn)
        return

    window = _TAP_WINDOW
    if _sprinting_now is None:
        # Can't read the sprint state: fall back to a plain double tap of the key.
        again = now - previous_tap <= window
    else:
        # Sprinting right now (toggle-style sprint), or a sprint that only just ended (hold-style).
        again = _sprinting_now or (now - _last_sprint_active) <= window
    if not again:
        return

    if _holstered:
        if _sprint_holstered and _stow_kind == "sprinting":
            _stow_kind = "surge"  # put away by Holster While Sprinting: turn the speed boost on
            _mark_surge_start()
            _log("Sprint pressed again while holstered by sprinting: Sprint Surge on (boost).")
        return  # an H-key holster (or an existing Sprint Surge) is left alone

    if pawn.Weapon is None:
        return
    _log("Sprint pressed again: stowing weapon.")
    _holster(pawn)
    if _holstered:
        _sprint_holstered = True
        _stow_kind = "surge"
        _mark_surge_start()


_SURGE_EXIT_GUARD = 0.3  # seconds after a surge starts before another press can end it (no bounce)
_surge_started = -100.0
_TILT = 3.0              # Sprint Surge camera tilt (view leans forward) at 100%, degrees
_TILT_RISE = 0.25        # seconds to lean in as a surge starts...
_TILT_FALL = 0.30        # ...and to come back level when it ends
_tilt_level = 0.0


def _mark_surge_start() -> None:
    global _surge_started
    _surge_started = core.clock


def _update_tilt(dt, active: bool) -> None:
    """Lean the view forward while surging (eased in and out). Your aim moves with it and returns."""
    global _tilt_level
    if active:
        _tilt_level = min(1.0, _tilt_level + dt / _TILT_RISE)
    else:
        _tilt_level = max(0.0, _tilt_level - dt / _TILT_FALL)
    amount = surge.tilt_slider.value / 100.0
    if _tilt_level > 0.0 and amount > 0.0:
        e = _tilt_level * _tilt_level * (3.0 - 2.0 * _tilt_level)
        camera.request("surge", pitch=-_TILT * amount * e)


def _apply_speed_boost(pawn, active: bool) -> None:
    """Sprint Surge speed boost on / off. The boost is a GroundSpeed multiplier handed to core,
    which owns GroundSpeed for every feature (so the slide's momentum carry can't fight it)."""
    if pawn is None or not active:
        core.set_speed_mult("surge", None)
        return
    core.set_speed_mult("surge", 1.0 + surge.boost(core.clock - _surge_started) / 100.0)


def _boost_active() -> bool:
    """The boost follows the stow itself: on while a Sprint Surge is in effect, off the moment it is drawn.

    (Because it is tied to the stow and not the raw sprint flag, it also rides out the redraw
    delay, so a one-frame flicker in the sprint state can't make the speed stutter.)
    """
    return bool(_holstered and _stow_kind == "surge" and surge.enabled_option.value)


def _draw_now_for_fire(obj) -> None:
    """Fire / aim pressed while holstered by sprinting, Sprint Surge or a mantle: draw right away."""
    global _sprint_holstered, _sprint_suppressed
    if not (_holstered and (_sprint_holstered or _mantle_holstered)):
        return
    pc, pawn = core.get_pc_pawn()
    try:
        if pc is None or obj != pc:
            return
    except Exception:  # noqa: BLE001
        return
    _log("Fire/aim pressed while holstered, drawing.")
    if _sprint_holstered:
        _sprint_suppressed = True
    _sprint_holstered = False
    _unholster(pawn)


# NOTE: these two paths are standard UE3 controller functions. If a build of the game routes
# fire / aim through different functions the hooks simply never fire and the feature does nothing.
@hook("Engine.PlayerController:StartFire")
def _holster_on_fire(obj, *_args) -> None:
    _draw_now_for_fire(obj)


@hook("Engine.PlayerController:StartAltFire")
def _holster_on_aim(obj, *_args) -> None:
    _draw_now_for_fire(obj)


# Action skills can't be used during a Sprint Surge (Axton's turret, for one, never appears with the weapon
# stowed). The game's action skill button goes through a controller function; these are the likely
# names. Any that doesn't exist is simply never called. On enable we also log every action-skill
# related function we can see on the controller, so the right one is easy to spot.
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


def _surge_blocks_skill(obj, *_args):
    try:
        if not (_holstered and _stow_kind == "surge" and surge.enabled_option.value):
            return None
        pc, _pawn = core.get_pc_pawn()
        if pc is not None and obj == pc:
            _log("Action skill blocked during Sprint Surge.")
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


def _update_sprint_holster(pc, pawn, sprinting) -> None:
    """Holster While Sprinting; draw a sprint-holstered weapon again as soon as the sprint ends."""
    global _sprint_holstered, _sprint_suppressed, _stow_kind

    sprinting_ok = bool(enabled_option.value and holster_sprinting_option.value)
    surge_ok = bool(surge.enabled_option.value)
    if _sprint_holstered and not (sprinting_ok if _stow_kind == "sprinting" else surge_ok):
        _sprint_holstered = False  # the option that stowed it was switched off
        _unholster(pawn)
    if sprinting is None:
        return

    if sprinting:
        if sprinting_ok and not _holstered and not _sprint_suppressed and pawn.Weapon is not None:
            _log("Sprinting, holstering.")
            _holster(pawn)
            if _holstered:
                _sprint_holstered = True
                _stow_kind = "sprinting"
        return

    # Not sprinting.
    _sprint_suppressed = False
    if _sprint_holstered:
        _log("Sprint ended, drawing weapon.")
        _sprint_holstered = False
        _unholster(pawn)


def _tick(pc, pawn, dt) -> None:
    global _sprint_suppressed, _sprinting_now, _last_sprint_active

    if pawn is None or core.unusable(pawn):
        if _holstered or _sprint_holstered:
            _clear_state()  # died, loading, or climbed into a vehicle: nothing to restore
        _sprinting_now = None
        _apply_speed_boost(pawn if pawn is not None and not core.unusable(pawn) else None, False)
        _update_tilt(dt, False)
        hudfx.surge_state(False, 0.0)
        return

    sprinting = _is_sprinting(pc, pawn)
    _sprinting_now = sprinting
    if sprinting:
        _last_sprint_active = core.clock

    _tick_holster(pc, pawn, sprinting)
    _apply_speed_boost(pawn, _boost_active())
    _update_tilt(dt, _boost_active())
    hudfx.surge_state(_boost_active() and surge.indicator_option.value,
                      surge.ramp(core.clock - _surge_started))


def _tick_holster(pc, pawn, sprinting) -> None:
    global _holstered, _sprint_holstered, _sprint_suppressed, _seen_empty, _mantle_holstered

    if _holstered and not _sprint_holstered and not _mantle_holstered and not enabled_option.value:
        _log("Holster turned off while holstered, drawing the weapon.")
        _unholster(pawn)  # also clears the holster state
        return
    if not (enabled_option.value or surge.enabled_option.value) and not _holstered:
        return

    if _holstered:
        if pawn.Weapon is None:
            _seen_empty = True
        elif _seen_empty:
            _mantle_holstered = False
            # The slot emptied (our holster worked) and now something is equipped: the player did it.
            _log("Weapon equipped while holstered, clearing holster state.")
            if _sprint_holstered:
                _sprint_suppressed = True  # don't instantly re-holster the weapon they just chose
            _holstered = False
            _sprint_holstered = False
            return
        elif core.clock - _holster_time > _HOLSTER_TIMEOUT:
            _log("Holster never took effect, clearing holster state.")
            _mantle_holstered = False
            _holstered = False
            _sprint_holstered = False
            return

    _update_sprint_holster(pc, pawn, sprinting)


def on_enable() -> None:
    global _sprint_suppressed, _sprinting_now, _last_sprint_active, _last_tap
    _clear_state()
    _sprint_suppressed = False
    _sprinting_now = None
    _last_sprint_active = -100.0
    _last_tap = -100.0
    core.register(
        "holster",
        tick=_tick,
        events={"mantle_start": _on_mantle_start, "mantle_end": _on_mantle_end},
        priority=30,
    )
    _hook_action_skill()


def on_disable() -> None:
    """Draw the weapon again, and give back normal speed, if the mod is switched off."""
    try:
        _apply_speed_boost(core.get_pc_pawn()[1], False)
    except Exception:  # noqa: BLE001
        pass
    if _holstered:
        try:
            _unholster(core.get_pc_pawn()[1])
        except Exception:  # noqa: BLE001
            pass
    _clear_state()
    _unhook_action_skill()
    core.unregister("holster")


OPTIONS = [
    enabled_option,
    *core.settings([holster_sprinting_option], "Fine-tune holstering."),
]
KEYBINDS = [_holster_toggle, _sprint_surge_pressed]
HOOKS = [_holster_block_auto_equip, _holster_on_fire, _holster_on_aim]
