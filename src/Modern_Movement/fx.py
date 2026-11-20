"""Air dash effects: the screen-edge hex flash and sounds.

Everything here is best-effort and cosmetic: if something can't be found or played it is
skipped (and logged once) and the air dash itself is never affected.
"""

import unrealsdk
from unrealsdk import logging

# The dash whoosh. The melee swing's short path never resolved in game, so a dash
# only played the ready beep. This is the grenade teleport the original dash used,
# and that full path (package, group, event) is one the game will load.
SOUND = "Ake_Wep_Grenades.Grenade_Classes.Ak_Play_Wep_Grenade_Longbow_Teleport_Out"

# The Pre-Sequel tries its Oz air-boost first, then the same whoosh.
WHOOSH = (SOUND,)
WHOOSH_TPS = (
    "Ake_Cork_FX_Global.Ak_Play_Cork_FX_AirBoost_Boost",
    SOUND,
)
JUMP = (
    "Ake_Fs_Player.Ak_Play_Fs_Jump",
    "Ake_Fol_Player.Ak_Play_Foley_Armor_Jump",
)
LAND = (
    "Ake_Fs_Player.Ak_Play_Fs_Land",
    "Ake_Fol_Player.Ak_Play_Foley_Armor_Land",
)
LADDER = ("Ake_Fs_Player.Ak_Play_Fs_Ladder",)
# The scrape is a real footstep, repeated for the whole slide. The old stalker
# step is not in either game's banks.
SCRAPE = (
    "Ake_Fs_Player.Ak_Play_Fs_Run",
    "Ake_Fs_Player.Ak_Play_Fs_Walk",
    "Ake_Fol_Player.Ak_Play_Foley_Armor",
    "Ake_Cork_Fs_Player.Ak_Play_Fs_Run",
)
SLAM_DIVE = WHOOSH
# A footstep on concrete. The medium explosion and the gib were the mushy layer.
SLAM_HIT = ("Ake_Fs_Player.Ak_Play_Fs_Land",)
SLAM_HIT_TPS = (
    "Ake_Cork_FX_Global.Ak_Play_Cork_FX_Slam",
    "Ake_Fs_Player.Ak_Play_Fs_Land",
)
# Sharp crack played by short name, the way the original slam found it.
SLAM_CRACK = "Ak_Play_Exp_Elemental_Explosive_SM"

_SOUND_RETRY_S = 10.0
_sound_retry: dict = {}    # name -> time.monotonic() before which a missing sound isn't searched again
_warned: set = set()


def _warn_once(key, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        logging.warning(message)


def dash_paths() -> tuple[str, ...]:
    """Whoosh for a dash. The Pre-Sequel prefers the Oz air-boost. Super sprint stays silent."""
    from . import game

    return WHOOSH_TPS if game.is_tps() else WHOOSH


def jump_paths() -> tuple[str, ...]:
    return JUMP


def land_paths() -> tuple[str, ...]:
    return LAND


def scrape_paths() -> tuple[str, ...]:
    return SCRAPE


def slam_hit_paths() -> tuple[str, ...]:
    from . import game

    return SLAM_HIT_TPS if game.is_tps() else SLAM_HIT


def play_first(pc, pawn, paths) -> None:
    """Play the first event in the list that this game actually has."""
    for path in paths:
        if _play_one(pc, pawn, path):
            return


def play_all(pc, pawn, paths) -> None:
    """Play every event in the list that this game has. Missing ones are skipped."""
    for path in paths:
        _play_one(pc, pawn, path)


def _resolve_event(name: str):
    """Look up one event. A full path is loaded if it is not already in memory.

    The object is not kept. A map travel unloads it, and a kept one goes silent.
    A miss waits a few seconds before it is tried again.
    """
    import time

    now = time.monotonic()
    if now < _sound_retry.get(name, 0.0):
        return None
    event = _find_event(name)
    short = name.rsplit(".", 1)[-1]
    if event is None and "." in name:
        try:
            unrealsdk.load_package(name.split(".", 1)[0])
        except Exception:  # noqa: BLE001
            pass
        event = _find_event(name)
    if event is None and short != name:
        event = _find_event(short)
    if event is None:
        event = _find_loaded(short)
    if event is None:
        _sound_retry[name] = now + _SOUND_RETRY_S
        _warn_once(("sound", name), f"[Modern Movement] sound not found, skipped: {name}")
        return None
    _sound_retry.pop(name, None)
    return event


def _find_loaded(short: str):
    """Match a short event name against sounds already in memory. One scan, then a wait."""
    import time

    cached = _named_paths.get(short)
    if cached:
        return _find_event(cached)
    now = time.monotonic()
    if now < _sound_retry.get(("catalog",), 0.0):
        return None
    _sound_retry[("catalog",)] = now + _SOUND_RETRY_S
    try:
        for obj in unrealsdk.find_all("AkEvent", exact=False):
            try:
                _named_paths.setdefault(str(obj.Name), obj._path_name())
            except Exception:  # noqa: BLE001
                continue
    except Exception as e:  # noqa: BLE001
        _warn_once(("named-scan",), f"[Modern Movement] could not search sounds: {e!r}")
        return None
    path = _named_paths.get(short)
    if not path:
        return None
    return _find_event(path)


def _play_one(pc, pawn, name: str) -> bool:
    """True when the event was found and handed to the pawn or the controller."""
    event = _resolve_event(name)
    if event is None or (pawn is None and pc is None):
        return False
    try:
        try:
            if pawn is not None:
                pawn.PlayAkEvent(event)
            else:
                pc.PlayAkEvent(event)
        except Exception:  # noqa: BLE001
            pc.PlayAkEvent(event)
        return True
    except Exception as e:  # noqa: BLE001
        _warn_once(("sound-play", name), f"[Modern Movement] could not play {name}: {e!r}")
        return False


def play_sound(pc, pawn, name: str = SOUND) -> None:
    """Play one event by its full path. Never raises. A missing event is skipped."""
    _play_one(pc, pawn, name)


_named_paths: dict = {}    # sound name -> its full path (a string), found once


def play_named(pc, pawn, names) -> None:
    """Play sounds by name (e.g. "Ak_Play_Fs_Land"), all at once. Each name's full path is found
    once by searching the loaded sounds and kept as a string; the sound itself is looked up fresh
    every play. Never raises."""
    import time
    now = time.monotonic()
    missing = [n for n in names if n not in _named_paths and now >= _sound_retry.get(n, 0.0)]
    if missing:
        try:
            want = set(missing)
            for o in unrealsdk.find_all("AkEvent", exact=False):
                try:
                    if o.Name in want:
                        _named_paths[o.Name] = o._path_name()
                except Exception:  # noqa: BLE001
                    continue
        except Exception as e:  # noqa: BLE001
            _warn_once(("named-scan",), f"[Modern Movement] could not search sounds: {e!r}")
        for n in missing:
            if n not in _named_paths:
                _sound_retry[n] = now + _SOUND_RETRY_S
                _warn_once(("sound", n), f"[Modern Movement] sound not found, skipped: {n}")
    for n in names:
        path = _named_paths.get(n)
        if path is None:
            continue
        event = _find_event(path)
        if event is None:
            _named_paths.pop(n, None)          # unloaded since: search again next time
            continue
        try:
            try:
                pawn.PlayAkEvent(event)
            except Exception:  # noqa: BLE001
                pc.PlayAkEvent(event)
        except Exception as e:  # noqa: BLE001
            _warn_once(("sound-play", n), f"[Modern Movement] could not play {n}: {e!r}")


def set_switch(pawn, path: str) -> None:
    """Set a sound switch on the pawn (e.g. the footstep surface) before playing a sound. The switch is
    looked up fresh each time (never kept). Never raises."""
    try:
        sw = unrealsdk.find_object("AkSwitch", path)
    except Exception:  # noqa: BLE001
        sw = None
    if sw is None:
        _warn_once(("switch", path), f"[Modern Movement] sound switch not found, skipped: {path}")
        return
    try:
        pawn.SetAkSwitchObject(sw)
    except Exception as e:  # noqa: BLE001
        _warn_once(("switch-set", path), f"[Modern Movement] could not set sound switch {path}: {e!r}")


_event_names = None   # names of the sound events loaded when first asked (strings only)


def event_names(refresh: bool = False):
    """Names of all loaded sound events (searched once; refresh=True searches again). Never raises."""
    global _event_names
    if _event_names is None or refresh:
        names = set()
        try:
            for o in unrealsdk.find_all("AkEvent", exact=False):
                try:
                    names.add(str(o.Name))
                    _named_paths.setdefault(str(o.Name), o._path_name())
                except Exception:  # noqa: BLE001
                    continue
        except Exception as e:  # noqa: BLE001
            _warn_once(("names",), f"[Modern Movement] could not list sounds: {e!r}")
        _event_names = sorted(names)
    return _event_names


def _find_event(name: str):
    try:
        return unrealsdk.find_object("AkEvent", name)
    except Exception:  # noqa: BLE001
        return None


def hex_flash(pc, direction) -> None:
    """Flash the game's blue shield-hit hex pattern on the screen edge the air dash goes
    toward (left dash: left edge, forward: top, back: bottom). It is the game's own
    directional shield-hit indicator, fed a world direction as if the shield had been
    hit from that side. Never raises."""
    try:
        d = pc.SummedDamageDirection
        d.X = direction[0] * 100.0
        d.Y = direction[1] * 100.0
        d.Z = 0.0
        pc.SummedDamageOnlyAffectedShield = True   # blue hex (shield), not red (health)
        pc.bHUDDamageIndicatorAdded = True          # the game shows it on its next update
    except Exception as e:  # noqa: BLE001
        _warn_once("hex", f"[Dash] could not show the screen effect: {e!r}")


# ---- HUD clips (the game's Flash HUD) -----------------------------------------------------
_hud_field = None   # name of myHUD's property holding the HUD movie (a string, found once)


def hud_movie(pc):
    """The game's HUD movie right now, or None (looked up fresh every call, never kept)."""
    global _hud_field
    try:
        hud = pc.myHUD
        if hud is None:
            return None
        if _hud_field is None:
            _hud_field = "HUDMovie"
            try:
                for f in hud.Class._fields():
                    cls = getattr(f, "PropertyClass", None)
                    if f.Class.Name == "ObjectProperty" and cls is not None and cls.Name == "WillowHUDGFxMovie":
                        _hud_field = f.Name
                        break
            except Exception:  # noqa: BLE001
                pass
        movie = getattr(hud, _hud_field, None)
        return movie if movie is not None and movie.bMovieIsOpen else None
    except Exception:  # noqa: BLE001
        return None


def clip_alpha(pc, path: str):
    """A HUD clip's _alpha (0-100), or None if it can't be read."""
    movie = hud_movie(pc)
    if movie is None:
        return None
    try:
        return float(movie.GetVariableNumber(path + "._alpha"))
    except Exception:  # noqa: BLE001
        return None


def set_clip_alpha(pc, path: str, alpha: float) -> None:
    """Set a HUD clip's _alpha (0-100). Never raises."""
    movie = hud_movie(pc)
    if movie is None:
        return
    try:
        movie.SetVariableNumber(path + "._alpha", float(alpha))
    except Exception as e:  # noqa: BLE001
        _warn_once(("alpha", path), f"[Modern Movement] could not change {path}: {e!r}")
