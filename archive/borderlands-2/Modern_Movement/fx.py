"""Air dash effects: the screen-edge hex flash and sounds.

Everything here is best-effort and cosmetic: if something can't be found or played it is
skipped (and logged once) and the air dash itself is never affected.
"""

import unrealsdk
from unrealsdk import logging

# The sound played once as an air dash starts: the Longbow grenade's teleport-out.
SOUND = "Ake_Wep_Grenades.Grenade_Classes.Ak_Play_Wep_Grenade_Longbow_Teleport_Out"

_SOUND_RETRY_S = 10.0
_sound_retry: dict = {}    # name -> time.monotonic() before which a missing sound isn't searched again
_warned: set = set()


def _warn_once(key, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        logging.warning(message)


def play_sound(pc, pawn, name: str = SOUND) -> None:
    """Play a sound once (the air dash sound unless another event name is given). Never raises.

    The sound is looked up by its path every time (a cheap name lookup) and never kept between
    plays: sounds that belong to a map are unloaded when you travel, and a kept one would go
    silent (or worse). If it isn't loaded, its bundle is loaded; if it still can't be found it
    is tried again after a few seconds rather than given up on."""
    import time
    now = time.monotonic()
    if now < _sound_retry.get(name, 0.0):
        return
    try:
        event = _find_event(name)
        if event is None:
            try:
                unrealsdk.load_package(name.split(".", 1)[0])
            except Exception:  # noqa: BLE001
                pass
            event = _find_event(name)
        if event is None:
            _sound_retry[name] = now + _SOUND_RETRY_S
            _warn_once(("sound", name), f"[Modern Movement] sound not found, skipped: {name}")
            return
        _sound_retry.pop(name, None)
        try:
            pawn.PlayAkEvent(event)
        except Exception:  # noqa: BLE001
            pc.PlayAkEvent(event)  # the pawn can't play it: ask the controller
    except Exception as e:  # noqa: BLE001
        _warn_once(("sound-play", name), f"[Modern Movement] could not play {name}: {e!r}")


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
