"""Slam: press crouch high in the air to drive straight down into the ground.

  * Press crouch while airborne and above the ground (60% of a normal jump's height): you stop
    drifting and plunge straight down. A press keeps trying for 1.5 s, so pressing a moment early
    (still too low, or mid-dash) still slams. Crouching just before you land does not.
  * Hitting the ground: an impact sound, a camera crunch, and (with Slam Damage) a blast from the
    game itself (like an explosion): enemies within "Knockback Radius" take a share of your
    equipped grenade's damage and are thrown. Walls block it and friendly NPCs are not hit. You come
    out of it standing.
  * Grabbing a ledge (mantle), dashing or landing in water ends the slam.
  * Slam Indicator: landing brackets below the crosshair while you're high enough to slam (closer
    together the harder it would hit), and a flat shockwave on impact (hudfx.py).

The height check is one line trace straight down (tracing.py), only when crouch is pressed in
the air. Only numbers are kept between ticks, never game objects.
"""

from __future__ import annotations

import math

from mods_base import BoolOption, SliderOption
from unrealsdk import logging

from .. import camera, core, fx, hudfx, tracing

enabled_option = BoolOption(
    "Slam Enabled", True, "On", "Off",
    description="Press crouch while high in the air to slam into the ground.",
)
indicator_option = BoolOption(
    "Slam Indicator", True, "On", "Off",
    description="Brackets below the crosshair show when you're high enough to slam, closing in the higher you are, "
                "and a shockwave shows on impact.",
)
audio_option = BoolOption("Slam Audio Effect", True, "On", "Off", description="Adds sound effects to the slam.")

damage_slider = SliderOption(
    "Slam Damage (%)", value=50, min_value=0, max_value=300, step=10, is_integer=True,
    description="Percentage of your equipped grenade's damage your slam will deal.",
)
damage_option = BoolOption(
    "Slam Damage", True, "On", "Off",
    description="Enemies near where you land are dealt a percentage of your equipped grenade's damage.",
)
scaling_slider = SliderOption(
    "Slam Height Scaling (%)", value=40, min_value=0, max_value=200, step=10, is_integer=True,
    description="Percentage that slamming camera effects, knockback, and damage scale with height.",
)


class _Fixed:
    """A locked-in tuning value (read like a slider's .value, not in the menu)."""

    def __init__(self, value):
        self.value = value


speed_slider = _Fixed(2600)        # Slam Speed, units/s
knock_strength_slider = _Fixed(1000)  # Knockback Strength: how hard nearby enemies are thrown
knock_radius_slider = _Fixed(600)     # Knockback Radius: how far from where you land enemies are thrown
min_height_slider = _Fixed(60)     # Slam Min Height, % of a normal jump's height
window_slider = _Fixed(1500)       # Slam Press Window, ms
shake_slider = _Fixed(100)         # Slam Camera Shake, %
push_slider = _Fixed(150)          # Slam Camera Push, %

_DEBUG = False            # True: what each slam's blast used, in the console
_FALLBACK_GRAVITY = 1050.0
_HORIZONTAL_KEEP = 0.12   # share of your sideways speed kept when the slam starts
_MAX_TIME = 6.0           # safety net, seconds
_RECHECK = 0.05           # while it waits: one height check per this long

# Sounds: the dive reuses the dash whoosh; the impact is the landing thud plus a heavy layer.
_DIVE_SOUND = fx.SOUND
_THUD = ("Ak_Play_Fs_Land",)
_IMPACT = "Ak_Play_Exp_Elemental_Explosive_SM"   # the heavy layer (was Slam Impact Sound Variant 4)

# Camera
_PUSH = 4.0               # degrees the view tips down at 100% while plunging
_PUSH_IN = 0.10
_PUSH_OUT = 0.22
_DIVE_EYE = 0.6           # rumble while plunging at 100%, units
_HIT_EYE = 5.0            # impact bob at 100%, units
_HIT_ROLL = 2.0           # impact tilt at 100%, degrees
_HIT_DIP = 14.0           # the eye drops this far on impact (a knee bend) and comes back
_HIT_RISE = 0.03
_HIT_FALL = 0.45

_prev_crouch = False
_next_check = -100.0
_buffer_until = -100.0
_slam: dict | None = None    # {"t0", "t"} while plunging
_hit: dict | None = None     # {"t0", "t"} while the impact shake runs
_push_out: dict | None = None  # {"t0", "from"} while the view eases back after impact


def _log(msg: str) -> None:
    logging.info(f"[Modern Movement] Slam: {msg}")


def _flag(obj, name) -> bool:
    try:
        return bool(getattr(obj, name))
    except Exception:  # noqa: BLE001
        return False


def _crouching(pc, pawn) -> bool:
    return _flag(pawn, "bWantsToCrouch") or _flag(pawn, "bIsCrouched") or _flag(pc, "bDuck")


# The crouch KEY itself is watched too (the keys bound to crouch, read from the game's bindings),
# so every press counts at once. The crouch state alone misses presses: with toggle crouch a press
# in the air can switch crouch OFF (if you jumped while crouched), which looked like no press.
_KEYS_REFRESH = 5.0
_crouch_keys: tuple = ()
_keys_at = -100.0
_prev_key = False


def _find_crouch_keys(pc) -> tuple:
    """Keys bound to crouch (names only), following one level of named commands (GBA_...)."""
    try:
        binds = [(str(b.Name), str(b.Command)) for b in pc.PlayerInput.Bindings]
    except Exception:  # noqa: BLE001
        return ()
    words = ("duck", "crouch")
    targets = {n for n, c in binds if any(w in c.lower() for w in words)}
    keys = set()
    for n, c in binds:
        if n in targets and not n.upper().startswith("GBA_"):
            keys.add(n)                                 # a key bound straight to crouch
        if c.strip() in targets:
            keys.add(n)                                 # a key bound to a crouch command
    return tuple(sorted(k for k in keys if not k.upper().startswith("GBA_")))


def _crouch_key_down(pc):
    """True / False for the crouch key, or None if it can't be read."""
    global _crouch_keys, _keys_at
    if core.clock - _keys_at >= _KEYS_REFRESH or core.clock < _keys_at:
        _crouch_keys = _find_crouch_keys(pc)
        _keys_at = core.clock
    if not _crouch_keys:
        return None
    try:
        held = {str(k) for k in pc.PlayerInput.PressedKeys}
    except Exception:  # noqa: BLE001
        return None
    return any(k in held for k in _crouch_keys)


def _gravity(pc) -> float:
    try:
        g = abs(float(pc.WorldInfo.WorldGravityZ))
        if g >= 100.0:
            return g
    except Exception:  # noqa: BLE001
        pass
    return _FALLBACK_GRAVITY


def _min_height(pc, pawn) -> float:
    """How far above the ground your feet must be: a share of a normal jump's height."""
    jump = core.base_jump(pawn)
    return jump * jump / (2.0 * _gravity(pc)) * min_height_slider.value / 100.0


_EASY_MIN = 40.0          # units of clearance always needed (so a slam is never a step down)
_takeoff_feet: float | None = None   # feet height when you were last on the ground
_slide_jump_at = -100.0              # clock time of the last slide jump
_easy = False                        # left the ground with a slide jump: only _EASY_MIN needed


def _on_slide_jump(**_kw) -> None:
    global _slide_jump_at, _easy
    _slide_jump_at = core.clock
    _easy = True


_PROBE_MAX = 1600.0      # how far down the indicator looks to judge how hard a slam would hit


def _probe(pc, pawn):
    """One trace straight down from your feet: (high enough to slam, clearance, clearance needed).

    Slam Min Height is counted from where you left the ground, not from the ground below you:
    off a ledge (jumping or walking) the ground below is already far enough down, so the slam
    works straight away. A plain jump on flat ground still has to reach the min height, and a
    slide jump only needs to be clear of the ground."""
    need = _min_height(pc, pawn)
    try:
        x, y, z = core.position(pawn)
        _radius, half = tracing.body(pawn)
        feet = z - half
        reach = max(need, _PROBE_MAX)
        with tracing.session(pawn, 3):
            hit = tracing.trace(pawn, (x, y, feet - 2.0), (x, y, feet - 2.0 - reach))
    except Exception as e:  # noqa: BLE001
        _log(f"height check failed ({e!r}): not slamming")
        return False, 0.0, need
    if _easy:
        required = _EASY_MIN
    else:
        drop = 0.0 if (_takeoff_feet is None or hit is None) else max(0.0, _takeoff_feet - hit[0][2])
        required = max(_EASY_MIN, need - drop)
    clearance = reach + 2.0 if hit is None else feet - hit[0][2]
    return clearance >= required, clearance, required


def _high_enough(pc, pawn) -> bool:
    return _probe(pc, pawn)[0]


def _drop_strength(drop: float) -> float:
    """0 .. 1: where a fall of `drop` units sits in the slam's strength range."""
    lo, hi = _POWER_RANGE
    m = min(max(drop / _POWER_REF, lo), hi)
    return (m - lo) / (hi - lo)


_INDICATOR_EVERY = 0.05
_indicator_at = -100.0


def _update_indicator(pc, pawn) -> None:
    """Show the landing brackets while a slam is possible (one trace every _INDICATOR_EVERY)."""
    global _indicator_at
    if (not indicator_option.value or core.phys != core.PHYS_FALLING
            or core.busy not in (None, "dash") or core.unusable(pawn)):
        hudfx.slam_hide()
        return
    if core.clock - _indicator_at < _INDICATOR_EVERY and core.clock >= _indicator_at:
        return
    _indicator_at = core.clock
    ok, clearance, _required = _probe(pc, pawn)
    if ok:
        hudfx.slam_ready(_drop_strength(clearance))
    else:
        hudfx.slam_hide()


# ---- slam ---------------------------------------------------------------------------------


def _start(pc, pawn) -> None:
    global _slam, _push_out
    core.begin("slam")
    try:
        pawn.Velocity.X = float(pawn.Velocity.X) * _HORIZONTAL_KEEP
        pawn.Velocity.Y = float(pawn.Velocity.Y) * _HORIZONTAL_KEEP
        pawn.Velocity.Z = -float(speed_slider.value)
    except Exception:  # noqa: BLE001
        pass
    try:
        z0 = core.position(pawn)[2]
    except Exception:  # noqa: BLE001
        z0 = None
    _slam = {"t0": core.clock, "t": 0.0, "z0": z0}
    _push_out = None
    if indicator_option.value:
        hudfx.slam_go()
    if audio_option.value:
        fx.play_sound(pc, pawn, _DIVE_SOUND)


def _stop(push_from: float = 0.0) -> None:
    """End the plunge (the view eases back from where it was tipped)."""
    global _slam, _push_out
    if _slam is not None and push_from > 0.0:
        _push_out = {"t0": core.clock, "from": push_from}
    _slam = None
    core.end("slam")


def _cancel() -> None:
    """Another action (mantle, dash) took over."""
    _stop(_dive_push())
    hudfx.slam_hide()


def _dive_push() -> float:
    if _slam is None:
        return 0.0
    e = min(1.0, (core.clock - _slam["t0"]) / _PUSH_IN)
    e = e * e * (3.0 - 2.0 * e)
    return -_PUSH * push_slider.value / 100.0 * e


_STAND_TICKS = 4   # ticks the crouch is switched off after impact (in case the game re-applies it)
_stand = 0


def _stand_up(pc, pawn) -> None:
    """Turn crouch off (the toggle too) so you come out of the slam standing."""
    try:
        pc.bDuck = 0
    except Exception:  # noqa: BLE001
        try:
            pc.bDuck = False
        except Exception:  # noqa: BLE001
            pass
    for call in (lambda: pawn.ShouldCrouch(False), lambda: pawn.UnCrouch()):
        try:
            call()
        except Exception:  # noqa: BLE001
            pass


_POWER_REF = 500.0       # a slam from this far up hits at the normal strength (units fallen)
_POWER_RANGE = (0.5, 3.0)  # the drop counts from half as hard to three times as hard (at 100%)
_POWER_CAMERA_MAX = 2.0  # the camera crunch grows at most this much


def _power(pawn) -> float:
    """How hard this slam hits: 1 = normal; more when it fell further (Slam Height Scaling)."""
    try:
        z0 = _slam["z0"] if _slam is not None else None
        drop = max(0.0, z0 - core.position(pawn)[2]) if z0 is not None else _POWER_REF
    except Exception:  # noqa: BLE001
        drop = _POWER_REF
    lo, hi = _POWER_RANGE
    m = min(max(drop / _POWER_REF, lo), hi)
    return max(0.25, 1.0 + (m - 1.0) * scaling_slider.value / 100.0)


def _impact(pc, pawn) -> None:
    global _hit, _stand
    _stand = _STAND_TICKS
    _stand_up(pc, pawn)
    power = _power(pawn)
    try:
        z0 = _slam["z0"] if _slam is not None else None
        fell = max(0.0, z0 - core.position(pawn)[2]) if z0 is not None else _POWER_REF
    except Exception:  # noqa: BLE001
        fell = _POWER_REF
    if indicator_option.value:
        hudfx.slam_impact(_drop_strength(fell))
    else:
        hudfx.slam_hide()
    push = _dive_push()
    _stop(push)
    _hit = {"t0": core.clock, "t": 0.0, "p": power}
    core.emit("slam_impact")        # the slide module keeps the crouch icon hidden for a moment
    try:
        pawn.Velocity.X = 0.0
        pawn.Velocity.Y = 0.0
    except Exception:  # noqa: BLE001
        pass
    if audio_option.value:
        _impact_sound(pc, pawn)
    # The game's own blast does both the damage and the knockback. Slam Damage off = no blast at all:
    # you just slam down.
    if damage_option.value:
        _blast(pc, pawn, power, knock_strength_slider.value > 0)


def _impact_sound(pc, pawn) -> None:
    fx.play_named(pc, pawn, _THUD + (_IMPACT,))


def _obj_name(obj) -> str:
    try:
        return str(obj.Name) if obj is not None else ""
    except Exception:  # noqa: BLE001
        return ""


# The blast must use the game's own damage type class. The engine's base DamageType made the game
# crash (it reads the game's extra damage-type data, e.g. hit sounds, which the base class lacks)
# once the blast did real damage. If no game class is found the slam pushes instead.
_DAMAGE_TYPE_CLASSES = ("WillowDamageType",)
_dtype_name: str | None = None   # the class name that was found (a name, never the object)


def _damage_type():
    global _dtype_name
    from unrealsdk import find_class
    for name in ((_dtype_name,) if _dtype_name else _DAMAGE_TYPE_CLASSES):
        try:
            cls = find_class(name)
        except Exception:  # noqa: BLE001
            cls = None
        if cls is not None:
            _dtype_name = name
            return cls
    return None


_BLAST_MASS = 100.0   # the game divides a blast's momentum by the target's mass (about this much)


# Damage data for the blast: an explosive damage type and a matching impact definition, looked
# up by path or by searching the loaded data (names only are kept, never the objects).
_DTDEF_PATHS = ("GD_Explosive.DamageType.DmgType_Explosive_Impact",)
_IMPACT_CLASSES = ("WillowExplosionImpactDefinition", "WillowImpactDefinition")
_IMPACT_PREFER = ("grenade", "explosive")
_IMPACT_ELEMENTS = ("corros", "acid", "incend", "fire", "burn", "shock", "electr", "slag", "cryo",
                    "frost", "nova")
_impact_path: str | None = None


def _damage_data():
    """(damage type definition, impact definition), or None for any that can't be found."""
    global _impact_path
    import unrealsdk
    dtdef = None
    for path in _DTDEF_PATHS:
        try:
            dtdef = unrealsdk.find_object("WillowDamageTypeDefinition", path)
        except Exception:  # noqa: BLE001
            dtdef = None
        if dtdef is not None:
            break
    impact = None
    if _impact_path is not None:
        for cls in _IMPACT_CLASSES:
            try:
                impact = unrealsdk.find_object(cls, _impact_path)
            except Exception:  # noqa: BLE001
                impact = None
            if impact is not None:
                break
    if impact is None:
        found = []
        for cls in _IMPACT_CLASSES:
            try:
                for o in unrealsdk.find_all(cls, exact=False):
                    path = o._path_name()
                    if "Default__" not in path:
                        found.append((cls, path))
            except Exception:  # noqa: BLE001
                continue
        def rank(item):
            # a plain explosive impact, matching the plain explosive damage type: one for an element
            # (corrosive, fire, shock, slag, ice) is used only if there is nothing else
            low = item[1].lower().rsplit(".", 1)[-1]
            elemental = any(w in low for w in _IMPACT_ELEMENTS)
            return (elemental, -sum(w in low for w in _IMPACT_PREFER), len(low))
        for cls, path in sorted(found, key=rank):
            try:
                impact = unrealsdk.find_object(cls, path)
            except Exception:  # noqa: BLE001
                impact = None
            if impact is not None:
                _impact_path = path
                break
    return dtdef, impact


def _causer(pawn):
    """What the blast is dealt by: your equipped grenade, else your gun, else you."""
    nade = _equipped_grenade(pawn)
    if nade is not None:
        return nade, f"grenade {_obj_name(nade)}"
    try:
        gun = pawn.Weapon
        if gun is not None:
            return gun, f"weapon {_obj_name(gun)}"
    except Exception:  # noqa: BLE001
        pass
    return pawn, "you (no grenade or weapon)"


def _grenade_at_feet(pawn):
    """Your equipped grenade's projectile, spawned at your feet (the way a thrown grenade is), or None."""
    nade = _equipped_grenade(pawn)
    if nade is None:
        return None
    pdef = nade.GetProjectileDefinition()
    x, y, z = core.position(pawn)
    _radius, half = tracing.body(pawn)
    proj = nade.SpawnProjectile(ProjectileDef=pdef, SpawnLocation=tracing.make_vec(x, y, z - half + 20.0),
                                bSpawnWithNoCollisionFail=True)
    if _DEBUG:
        _log(f"blast source: {_obj_name(proj) or 'nothing'} from {_obj_name(pdef) or 'no projectile'}")
    return proj


def _blast_call(pawn, radius, damage, momentum, dtype, dtdef, impact, causer) -> None:
    """The blast is set off by your grenade, spawned at your feet for the moment and removed straight
    after, the way a real grenade's explosion comes from the grenade and not from you. Set off by you,
    an enemy that explodes the moment it dies (EXP Loaders) hit you with its own explosion while yours
    was still going, which crashed the game. The blast doesn't push or hurt you."""
    try:
        proj = _grenade_at_feet(pawn)
    except Exception as e:  # noqa: BLE001
        _log(f"could not place the grenade for the blast ({e!r}): blasting from you")
        proj = None
    if proj is not None:
        try:
            proj.bCauseRadiusDamageToInstigator = False      # the blast leaves you alone...
        except Exception:  # noqa: BLE001
            pass
        try:
            vel = (float(pawn.Velocity.X), float(pawn.Velocity.Y), float(pawn.Velocity.Z))
        except Exception:  # noqa: BLE001
            vel = None
        try:
            proj.Behavior_CauseRadiusDamage(
                Radius=radius, DamageAmount=damage, bFullDamage=False, Momentum=momentum,
                DamageType=dtype, DamageTypeDefinition=dtdef, ImpactDefinition=impact,
                bCanDamageFriendlies=False, Offset=tracing.make_vec(0.0, 0.0, 0.0),
                DamageCauser=proj, bSkipTraceTest=False,
            )
        finally:
            try:
                proj.DisableProjectile()
            except Exception:  # noqa: BLE001
                pass
            proj.Destroy()
            if vel is not None:                              # ...and any push it gave you is undone
                try:
                    pawn.Velocity = tracing.make_vec(*vel)
                except Exception:  # noqa: BLE001
                    pass
        return
    # no grenade equipped: the blast comes from you
    pawn.Behavior_CauseRadiusDamage(
        Radius=radius, DamageAmount=damage, bFullDamage=False, Momentum=momentum,
        DamageType=dtype, DamageTypeDefinition=dtdef, ImpactDefinition=impact,
        bCanDamageFriendlies=False, Offset=tracing.make_vec(0.0, 0.0, 0.0),
        DamageCauser=causer, bSkipTraceTest=False,
    )


def _blast(pc, pawn, power, knock: bool = True) -> bool:
    """Knockback through the game's own radius damage (like an explosion): walls block it and the
    game's own rules decide who is affected. True if the game accepted it."""
    try:
        dtype = _damage_type()
        if dtype is None:
            if _DEBUG:
                _log("knockback: no game damage type found: no blast")
            return False
        x, y, z = core.position(pawn)
        radius = float(knock_radius_slider.value) * math.sqrt(power)
        momentum = float(knock_strength_slider.value) * power * _BLAST_MASS if knock else 0.0
        damage = _slam_damage(pawn, power)
        causer, how = _causer(pawn)
        dtdef, impact = _damage_data()
        if _DEBUG:
            _log(f"blast from: {how}; damage type {_obj_name(dtdef) or 'none'}; impact {_obj_name(impact) or 'none'}")
        # The game's own "cause radius damage" behavior (what game scripts use), given a full set of
        # damage data: the damage type definition (element) and the impact definition (hit effects
        # and sounds). Without them a kill left the game looking up data that wasn't there.
        if dtdef is not None and impact is not None:
            _blast_call(pawn, radius, damage, momentum, dtype, dtdef, impact, causer)
        else:
            _log("blast: the game's damage data wasn't found: no blast")
            return False
    except Exception as e:  # noqa: BLE001
        _log(f"knockback: the game refused the blast ({type(e).__name__}: {e})")
        return False
    if _DEBUG:
        _log(f"knockback: blast sent ({damage:.0f} damage at the centre)")
    return True


# ---- damage from your grenade ------------------------------------------------------------
# Each way of reading it is tried in turn (in game it is the GrenadeDamage value); none = 1 damage.
_GRENADE_DAMAGE_CALLS = ("GetDamage", "GetGrenadeDamage", "GetCardDamage", "GetBaseDamage")
_GRENADE_DAMAGE_ATTRS = (
    "D_Attributes.GrenadeMod.GrenadeDamage",
    "D_Attributes.GrenadeMod.GrenadeMod_Damage",
    "D_Attributes.Projectile.ProjectileDamage",
)
_last_grenade_note = ""


def _items(pawn):
    """Your equipped items (shield, grenade, class mod, relic): the inventory's item chain."""
    try:
        item = pawn.InvManager.ItemChain
    except Exception:  # noqa: BLE001
        return
    for _ in range(32):
        if item is None:
            return
        yield item
        try:
            item = item.Inventory
        except Exception:  # noqa: BLE001
            return


def _equipped_grenade(pawn):
    for item in _items(pawn):
        try:
            if "Grenade" in str(item.Class.Name):
                return item
        except Exception:  # noqa: BLE001
            continue
    return None


def _number(v):
    if isinstance(v, (tuple, list)):
        v = v[0] if v else None
    try:
        n = float(v)
    except Exception:  # noqa: BLE001
        return None
    return n if n > 0.0 and math.isfinite(n) else None


def _grenade_damage(pawn):
    """(damage, how) for your equipped grenade, or (None, why not)."""
    nade = _equipped_grenade(pawn)
    if nade is None:
        return None, "no grenade equipped"
    for name in _GRENADE_DAMAGE_CALLS:
        try:
            n = _number(getattr(nade, name)())
            if n is not None:
                return n, f"{name}()"
        except Exception:  # noqa: BLE001
            continue
    try:
        import unrealsdk
        for path in _GRENADE_DAMAGE_ATTRS:
            try:
                attr = unrealsdk.find_object("AttributeDefinition", path)
            except Exception:  # noqa: BLE001
                attr = None
            if attr is None:
                continue
            try:
                n = _number(attr.GetValue(nade))
                if n is not None:
                    return n, path.rsplit(".", 1)[-1]
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return None, f"damage unreadable on {_obj_name(nade)}"


def _slam_damage(pawn, power) -> float:
    """Your grenade's damage (x Slam Damage, x height scaling), or 1 if there is none."""
    global _last_grenade_note
    base, how = _grenade_damage(pawn)
    note = f"grenade damage: {base:.0f} ({how})" if base is not None else f"grenade damage: none ({how}): 1 damage"
    if _DEBUG and note != _last_grenade_note:
        _log(note)
        _last_grenade_note = note
    if base is None or not damage_option.value:
        return 1.0
    return max(1.0, base * damage_slider.value / 100.0 * power)


# ---- per tick -----------------------------------------------------------------------------


def _update_camera(dt) -> None:
    global _hit, _push_out
    if _slam is not None:
        _slam["t"] += dt
        pitch = _dive_push()
        bob, _tilt = camera.wave(_slam["t"])
        camera.request("slam_dive", eye=bob * _DIVE_EYE * shake_slider.value / 100.0, pitch=pitch)
    elif _push_out is not None:
        f = (core.clock - _push_out["t0"]) / _PUSH_OUT
        if f >= 1.0:
            _push_out = None
        else:
            camera.request("slam_dive", pitch=_push_out["from"] * (1.0 - f * f * (3.0 - 2.0 * f)))
    if _hit is not None:
        age = core.clock - _hit["t0"]
        if age >= _HIT_RISE + _HIT_FALL:
            _hit = None
            return
        if age < _HIT_RISE:
            e = age / _HIT_RISE
        else:
            f = (age - _HIT_RISE) / _HIT_FALL
            e = 1.0 - f * f * (3.0 - 2.0 * f)
        _hit["t"] += dt
        amount = shake_slider.value / 100.0 * e * min(_hit.get("p", 1.0), _POWER_CAMERA_MAX)
        if amount > 0.0:
            bob, tilt = camera.wave(_hit["t"])
            camera.request(
                "slam_hit",
                eye=(bob * _HIT_EYE - _HIT_DIP) * amount,
                roll=tilt * _HIT_ROLL * amount,
            )


def _tick(pc, pawn, dt) -> None:
    global _prev_crouch, _next_check, _buffer_until, _stand
    _update_camera(dt)
    global _takeoff_feet, _easy
    if pawn is not None and core.phys == core.PHYS_WALKING:
        try:
            _takeoff_feet = core.position(pawn)[2] - tracing.body(pawn)[1]
        except Exception:  # noqa: BLE001
            pass
        if core.clock - _slide_jump_at > 0.25:
            _easy = False
    if _stand > 0:
        _stand -= 1
        if pawn is not None:
            _stand_up(pc, pawn)
    if pawn is None:
        _prev_crouch = False
        if _slam is not None:
            _stop()
        hudfx.slam_hide()
        return

    global _prev_key
    crouch = _crouching(pc, pawn)
    pressed = crouch and not _prev_crouch
    _prev_crouch = crouch
    key = _crouch_key_down(pc)
    if key is not None:
        pressed = pressed or (key and not _prev_key)
        _prev_key = key

    if _slam is not None:
        if core.busy != "slam":
            _stop(_dive_push())          # something else took over without cancelling us
        elif core.phys == core.PHYS_FALLING:
            if float(pawn.Velocity.Z) > -0.5 * float(speed_slider.value):
                _stop(_dive_push())          # a double jump (or something else) sent you up: let it
                return
            if core.clock - _slam["t0"] > _MAX_TIME:
                _stop(_dive_push())
                return
            try:
                pawn.Velocity.X = float(pawn.Velocity.X) * 0.9
                pawn.Velocity.Y = float(pawn.Velocity.Y) * 0.9
                pawn.Velocity.Z = min(float(pawn.Velocity.Z), -float(speed_slider.value))
            except Exception:  # noqa: BLE001
                pass
        elif core.phys == core.PHYS_WALKING:
            _impact(pc, pawn)
        else:
            _stop(_dive_push())          # water, ladder, vehicle...
        return

    if not enabled_option.value:
        hudfx.slam_hide()
        return
    _update_indicator(pc, pawn)
    if pressed and core.phys == core.PHYS_FALLING:
        _buffer_until = core.clock + window_slider.value / 1000.0  # keeps trying for a moment: no need to time it exactly
        _next_check = -100.0
    if core.clock > _buffer_until:
        return
    if core.phys != core.PHYS_FALLING:
        _buffer_until = -100.0                    # landed (or swimming...) first: forget the press
        return
    if core.busy not in (None, "dash") or core.unusable(pawn):
        return                                    # a dash is cut short by the slam; a mantle is not
    if core.clock < _next_check:
        return
    if _high_enough(pc, pawn):
        _buffer_until = -100.0
        _start(pc, pawn)
    else:
        _next_check = core.clock + _RECHECK


def on_enable() -> None:
    global _keys_at, _prev_key, _takeoff_feet, _slide_jump_at, _easy
    global _prev_crouch, _next_check, _slam, _hit, _push_out, _stand
    _prev_crouch = False
    _next_check = -100.0
    _buffer_until = -100.0
    _stand = 0
    _keys_at = -100.0
    _prev_key = False
    _takeoff_feet, _slide_jump_at, _easy = None, -100.0, False
    _slam = None
    _hit = None
    _push_out = None
    core.register("slam", tick=_tick, cancel=_cancel, priority=45, events={"slide_jump": _on_slide_jump})


def on_disable() -> None:
    global _slam
    hudfx.slam_hide()
    if _slam is not None:
        _stop()
    _slam = None
    core.unregister("slam")


OPTIONS = [
    enabled_option,
    *core.settings(
        [
            audio_option,
            indicator_option,
            damage_option,
            damage_slider,
            scaling_slider,
        ],
        "Fine-tune the slam.",
    ),
]
KEYBINDS = []
HOOKS = []
