"""Surface effects: dust, wind streaks, and a slam ring.

Cosmetic only. Each machine spawns the particles it can see, on its own copy of
that pawn, so a listen host and every joiner draw the same trail without a new
replication channel. A missing particle is skipped. Movement is never affected.
"""

from __future__ import annotations

import math

from mods_base import BoolOption

from .. import core, tracing

enabled_option = BoolOption(
    "Surface Effects",
    True,
    "On",
    "Off",
    description="Dust and wind while you slide, sprint, or dash, and a ring when you slam. Each game uses its own effects. Other players with the mod see them too.",
)

# Slide puffs stay on the ground. Air bursts sit a little higher and read as wind.
_KIND_ORDER = ("water", "snow", "metal", "wood", "grass", "stone", "dirt")
_KIND_WORDS = {
    "water": ("water", "puddle", "liquid", "wet"),
    "snow": ("snow", "ice", "frost"),
    "metal": ("metal", "steel", "grate", "iron"),
    "wood": ("wood", "plank", "timber"),
    "grass": ("grass", "foliage", "moss", "leaves"),
    "stone": ("stone", "concrete", "rock", "tile", "brick", "asphalt"),
    "dirt": ("dirt", "sand", "mud", "gravel", "earth", "dust", "ground"),
}
_SWITCH = {
    "dirt": "Aks_Global_Switches.Ground_Textures.AkSwitch_PM_Sand",
    "grass": "Aks_Global_Switches.Ground_Textures.AkSwitch_PM_Grass",
    "stone": "Aks_Global_Switches.Ground_Textures.AkSwitch_PM_Stone",
    "metal": "Aks_Global_Switches.Ground_Textures.AkSwitch_PM_Metal",
    "wood": "Aks_Global_Switches.Ground_Textures.AkSwitch_PM_Wood",
    "water": "Aks_Global_Switches.Ground_Textures.AkSwitch_PM_Water",
    "snow": "Aks_Global_Switches.Ground_Textures.AkSwitch_PM_Snow",
}
# Soft tints if the spawned system honours RColor. Air stays cool, never hot.
_COLOR = {
    "dirt": (1.15, 0.86, 0.52),
    "grass": (0.55, 1.05, 0.42),
    "stone": (0.82, 0.84, 0.88),
    "metal": (1.35, 1.55, 1.85),
    "wood": (1.05, 0.68, 0.32),
    "water": (0.35, 0.85, 1.35),
    "snow": (1.55, 1.75, 1.95),
    "air": (0.62, 0.92, 1.45),
}
# Always-loaded Borderlands particle systems (BLCM ParticleSystem list). The old
# guessed paths were not in the game, so every spawn returned nothing.
_CANDIDATES = {
    "dirt": (
        "FX_VEH_Shared.Particles.Part_VEHDirtKickupFX",
        "FX_ENV_Dust.Particles.Dynamic.Part_GenericGroundImpactFX",
        "FX_CREA_Skag.Particles.Shared.Part_Skag_FeetDustFX",
        "FX_ENV_Smoke.Particles.Part_SkagFootStepFX",
        "FX_ENV_Dust.Particles.Part_AmbientDustFX",
    ),
    "metal": (
        "FX_BulletImpacts_Metal.Particles.Part_Impact_Metal_SmallCalFX",
        "FX_env_sparks.Particles.Part_SparkShowerGenericFX",
    ),
    "water": (
        "FX_ENV_Water.Particles.Part_Water_Step_SplashFX",
        "FX_BulletImpacts_Water.Particles.Part_Impact_Water_ReduxFX",
        "FX_VEH_Shared.Particles.Part_VEH_WaterKickupFX",
    ),
    "snow": (
        "FX_ENV_InteractiveObjects.Particles.SnowChest.Part_IcePuffGenericFX",
        "FX_VEH_Shared.Particles.Part_Snow_Kickup_ClaptrapFX",
    ),
    "wood": ("FX_BulletImpacts_Wood.Particles.Impact_Wood_LargeCal_PartFX",),
    "stone": ("FX_BulletImpacts_Rock.Particles.Part_Impact_Rock_LargeCalFX",),
    "grass": (
        "FX_VEH_Shared.Particles.Part_VEHGrassKickupFX",
        "FX_BulletImpacts_Vegetation.Particles.Part_Impact_Grass_LargeCalFX",
        "FX_CREA_Skag.Particles.Shared.Part_Skag_FeetDustFX",
    ),
    "air": (
        "FX_ENV_Smoke.Particles.Part_WhispySmokeFX",
        "FX_ENV_InteractiveObjects.Particles.SnowChest.Part_SnowChest_AirFX",
        "FX_ENV_Dust.Particles.Part_AmbientDustFX",
    ),
    "sprint": (
        "FX_ENV_Smoke.Particles.Part_WhispySmokeFX",
        "FX_ENV_Dust.Particles.Part_AmbientDustFX",
        "FX_ENV_InteractiveObjects.Particles.SnowChest.Part_SnowChest_AirFX",
    ),
    "ring": (
        "FX_CHAR_Shared_Shield.Particles.Novas.Part_Explosive_Nova_Shield_ExplosionFX",
        "FX_ENV_Dust.Particles.Dynamic.Part_GenericGroundImpactFX",
        "FX_ENV_Dust.Particles.Part_AmbientDustFX",
    ),
}
# PhysX copies that ship with The Pre-Sequel. The names are on the always-loaded list.
_TPS_EXTRA = {
    "air": (
        "FX_ENV_Smoke.Particles.Part_WhispySmokeFX",
    ),
    "sprint": (
        "FX_ENV_Smoke.Particles.Part_WhispySmokeFX",
    ),
    "ring": (
        "FX_ENV_Dust_Px.Particles.Dynamic.Part_GenericGroundImpact_PxFX",
        "FX_CHAR_Shared_Shield.Particles.Novas.Part_Explosive_Nova_Shield_ExplosionFX",
    ),
    "dirt": (
        "FX_ENV_Dust_Px.Particles.Dynamic.Part_GenericGroundImpact_PxFX",
        "FX_VEH_Shared.Particles.Part_VEHDirtKickupFX",
    ),
}
_loaded_packages: set[str] = set()
_FALLBACK = (
    "FX_ENV_Dust.Particles.Dynamic.Part_GenericGroundImpactFX",
    "FX_ENV_Dust.Particles.Part_AmbientDustFX",
    "FX_CREA_Skag.Particles.Shared.Part_Skag_FeetDustFX",
)
_resolved: dict[str, object] = {}
_slots: dict[int, dict] = {}


def classify(material_name: str) -> str:
    """Map a physical-material name onto a surface kind. Unknown ground is dirt."""
    text = (material_name or "").lower()
    for kind in _KIND_ORDER:
        if any(word in text for word in _KIND_WORDS[kind]):
            return kind
    return "dirt"


def switch_path(kind: str) -> str:
    """Wwise ground switch for this surface. Dirt/sand is the fallback."""
    return _SWITCH.get(kind, _SWITCH["dirt"])


def _slot(pawn) -> dict:
    key = id(pawn)
    slot = _slots.get(key)
    if slot is None:
        if len(_slots) > 64:
            _slots.clear()
        slot = {"puff": -100.0, "air": -100.0, "kind": "dirt", "kind_until": -100.0}
        _slots[key] = slot
    return slot


def _base_name(pawn) -> str:
    """Ground the pawn is standing on, without a weapon trace.

    A trace spawns a hidden weapon. Doing that on the slide tick is a hitch.
    """
    try:
        base = pawn.Base
    except Exception:  # noqa: BLE001
        return ""
    if base is None:
        return ""
    parts: list[str] = []
    for attr in ("Name",):
        try:
            parts.append(str(getattr(base, attr)))
        except Exception:  # noqa: BLE001
            pass
    try:
        parts.append(str(base.Class.Name))
    except Exception:  # noqa: BLE001
        pass
    try:
        mesh = getattr(base, "StaticMeshComponent", None) or getattr(base, "Mesh", None)
        parts.append(str(mesh.PhysMaterialOverride.Name))
    except Exception:  # noqa: BLE001
        pass
    return " ".join(parts)


def kind_for(pc, pawn) -> str:
    """Surface under the pawn. Cached so a slide does not re-read the floor every puff."""
    del pc  # the floor read does not need the controller
    slot = _slot(pawn)
    now = core.clock
    if now < slot["kind_until"]:
        return slot["kind"]
    kind = classify(_base_name(pawn))
    slot["kind"] = kind
    slot["kind_until"] = now + 0.35
    return kind


def _paths_for(kind: str) -> list[str]:
    from .. import game

    paths: list[str] = []
    if game.is_tps():
        paths.extend(_TPS_EXTRA.get(kind, ()))
    paths.extend(_CANDIDATES.get(kind, ()))
    if kind not in ("dirt", "air", "sprint", "ring"):
        paths.extend(_CANDIDATES["dirt"])
    paths.extend(_FALLBACK)
    return paths


def _find_system(path: str):
    """Load that effect's package once, then look it up. A missing path is skipped."""
    import unrealsdk

    package = path.split(".", 1)[0]
    if package and package not in _loaded_packages:
        _loaded_packages.add(package)
        try:
            unrealsdk.load_package(package)
        except Exception:  # noqa: BLE001
            pass
    try:
        return unrealsdk.find_object("ParticleSystem", path)
    except Exception:  # noqa: BLE001
        return None


def _system(kind: str):
    """One particle for this kind, from this game's list. Never scans the whole catalog."""
    cached = _resolved.get(kind)
    if cached is not None:
        return cached
    seen: set[str] = set()
    for path in _paths_for(kind):
        if not path or path in seen:
            continue
        seen.add(path)
        system = _find_system(path)
        if system is not None:
            _resolved[kind] = system
            return system
    return None


def _pool(pawn):
    try:
        pool = pawn.WorldInfo.MyEmitterPool
        if pool is not None:
            return pool
    except Exception:  # noqa: BLE001
        pass
    try:
        from mods_base import ENGINE

        return ENGINE.GetCurrentWorldInfo().MyEmitterPool
    except Exception:  # noqa: BLE001
        return None


def _rotator():
    import unrealsdk

    try:
        return unrealsdk.make_struct("Rotator", Pitch=0, Yaw=0, Roll=0)
    except Exception:  # noqa: BLE001
        return unrealsdk.make_struct("Core.Object.Rotator", True, Pitch=0, Yaw=0, Roll=0)


def _emit(pawn, kind: str, loc: tuple[float, float, float], scale: float) -> None:
    system = _system(kind)
    if system is None or pawn is None:
        return
    pool = _pool(pawn)
    if pool is None:
        return
    # SpawnEmitter wants a template, a location, and a rotator. A missing rotator
    # makes this SDK reject the call, which is why a found particle still showed nothing.
    vec = tracing.make_vec(*loc)
    rot = _rotator()
    comp = None
    try:
        comp = pool.SpawnEmitter(system, vec, rot)
    except Exception:  # noqa: BLE001
        try:
            comp = pool.SpawnEmitter(EmitterTemplate=system, SpawnLocation=vec, SpawnRotation=rot)
        except Exception:  # noqa: BLE001
            try:
                comp = pool.SpawnEmitter(system, vec)
            except Exception:  # noqa: BLE001
                return
    if comp is None:
        return
    try:
        comp.ActivateSystem()
    except Exception:  # noqa: BLE001
        pass
    try:
        comp.SetScale(max(0.85, float(scale)))
    except Exception:  # noqa: BLE001
        pass
    color = _COLOR.get(kind, _COLOR["dirt"])
    tint = tracing.make_vec(*color)
    for param in ("RColor", "Color", "Tint"):
        try:
            comp.SetVectorParameter(param, tint)
        except Exception:  # noqa: BLE001
            pass


def _feet(pawn, back: float = 28.0) -> tuple[float, float, float]:
    x, y, z = core.position(pawn)
    _radius, half = tracing.body(pawn)
    try:
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
    except Exception:  # noqa: BLE001
        vx, vy = 0.0, 0.0
    speed = math.hypot(vx, vy)
    if speed > 1.0 and back:
        x -= vx / speed * back
        y -= vy / speed * back
    return (x, y, z - half + 10.0)


def puff(pawn, kind: str, strength: float) -> None:
    """One ground puff. Rate-limited per pawn so a slide and the observer do not double up."""
    if not enabled_option.value or pawn is None:
        return
    strength = max(0.15, min(1.0, float(strength)))
    slot = _slot(pawn)
    now = core.clock
    if now < slot["puff"]:
        return
    slot["puff"] = now + 0.12 + 0.1 * (1.0 - strength)
    origin = _feet(pawn, 36.0 * strength)
    _emit(pawn, kind, origin, 1.0 + 0.35 * strength)
    if strength > 0.65:
        side = _feet(pawn, 18.0)
        _emit(pawn, kind, (side[0], side[1], side[2] + 8.0), 0.9)


def slide(pc, pawn, strength: float) -> str:
    """Match the scrape to the ground and kick up that surface."""
    kind = kind_for(pc, pawn) if pc is not None else "dirt"
    puff(pawn, kind, strength)
    return kind


def sprint_wind(pc, pawn) -> None:
    """A light streak behind a sprint. Smaller and slower than a dash burst."""
    del pc
    if not enabled_option.value or pawn is None:
        return
    slot = _slot(pawn)
    now = core.clock
    if now < slot.get("sprint", -100.0):
        return
    slot["sprint"] = now + 0.16
    try:
        vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
    except Exception:  # noqa: BLE001
        return
    if math.hypot(vx, vy) < 280.0:
        return
    origin = _feet(pawn, 48.0)
    _emit(pawn, "sprint", (origin[0], origin[1], origin[2] + 18.0), 0.55)
    _emit(pawn, "sprint", (origin[0], origin[1], origin[2] + 42.0), 0.4)


def slam_ring(pawn, strength: float = 1.0) -> None:
    """A circle of ground dust where a slam lands, plus one impact in the middle."""
    if not enabled_option.value or pawn is None:
        return
    slot = _slot(pawn)
    now = core.clock
    if now < slot.get("ring", -100.0):
        return
    slot["ring"] = now + 0.35
    strength = max(0.25, min(1.0, float(strength)))
    center = _feet(pawn, 0.0)
    _emit(pawn, "ring", (center[0], center[1], center[2] + 6.0), 1.6 + 0.8 * strength)
    radius = 70.0 + 110.0 * strength
    for step in range(8):
        ang = step * math.tau / 8.0
        _emit(
            pawn,
            "dirt",
            (center[0] + math.cos(ang) * radius, center[1] + math.sin(ang) * radius, center[2] + 4.0),
            0.85 + 0.25 * strength,
        )


def _note_landing(pc, pawn) -> None:
    """The Pre-Sequel's own slam does not call us. A hard landing still gets the ring."""
    slot = _slot(pawn)
    try:
        vz = float(pawn.Velocity.Z)
    except Exception:  # noqa: BLE001
        vz = 0.0
    if core.phys == core.PHYS_FALLING:
        slot["fall_z"] = min(float(slot.get("fall_z", 0.0)), vz)
        return
    fell = float(slot.get("fall_z", 0.0))
    slot["fall_z"] = 0.0
    if core.phys == core.PHYS_WALKING and fell < -1200.0:
        slam_ring(pawn, min(1.0, abs(fell) / 1800.0))
        try:
            from .. import fx, game

            if game.is_tps():
                fx.play_all(pc, pawn, fx.slam_hit_paths())
        except Exception:  # noqa: BLE001
            pass


def air(pc, pawn, dx: float = 0.0, dy: float = 0.0, scale: float = 1.0) -> None:
    """A short cool wind burst. dx, dy are the burst direction on the ground plane."""
    if not enabled_option.value or pawn is None:
        return
    slot = _slot(pawn)
    now = core.clock
    if now < slot["air"]:
        return
    slot["air"] = now + 0.28
    x, y, z = core.position(pawn)
    _radius, half = tracing.body(pawn)
    mag = math.hypot(dx, dy)
    if mag > 1e-3:
        dx, dy = dx / mag, dy / mag
    else:
        try:
            vx, vy = float(pawn.Velocity.X), float(pawn.Velocity.Y)
            mag = math.hypot(vx, vy)
            if mag > 1.0:
                dx, dy = vx / mag, vy / mag
        except Exception:  # noqa: BLE001
            dx, dy = 1.0, 0.0
    chest = (x - dx * 20.0, y - dy * 20.0, z - half * 0.15)
    wake = (x - dx * 70.0, y - dy * 70.0, z - half * 0.35)
    amount = max(0.35, min(1.0, float(scale)))
    _emit(pawn, "air", chest, 1.05 * amount)
    _emit(pawn, "air", wake, 0.9 * amount)


def _speed(pawn) -> float:
    try:
        return math.hypot(float(pawn.Velocity.X), float(pawn.Velocity.Y))
    except Exception:  # noqa: BLE001
        return 0.0


def _crouched(pawn) -> bool:
    try:
        if float(pawn.CrouchedPct) > 1.0:
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return bool(pawn.bIsCrouched) or bool(pawn.bWantsToCrouch)
    except Exception:  # noqa: BLE001
        return False


def _others(local_pawn):
    try:
        pris = list(local_pawn.WorldInfo.GRI.PRIArray)
    except Exception:  # noqa: BLE001
        return
    for pri in pris:
        pawn = None
        try:
            pawn = pri.Pawn
        except Exception:  # noqa: BLE001
            pawn = None
        if pawn is None:
            try:
                pawn = pri.Owner.Pawn
            except Exception:  # noqa: BLE001
                pawn = None
        if pawn is None or pawn is local_pawn:
            continue
        yield pawn


def _observe(pc, local_pawn) -> None:
    """Draw trails on pawns this machine does not simulate itself.

    The listen host already puffs while it ticks a joiner slide. A joiner does not
    tick the host, so this pass is what lets them see the host's dust and dash wind.
    """
    for pawn in _others(local_pawn):
        speed = _speed(pawn)
        if _crouched(pawn) and speed > 450.0:
            slide(pc, pawn, min(1.0, speed / 900.0))
            continue
        if speed > 2500.0:
            try:
                air(pc, pawn, float(pawn.Velocity.X), float(pawn.Velocity.Y), 0.85)
            except Exception:  # noqa: BLE001
                pass


def _tick(pc, pawn, _dt) -> None:
    if not enabled_option.value or pawn is None or core.unusable(pawn):
        return
    ctx = core.current_context()
    if ctx is None or not ctx.local:
        return
    _note_landing(pc, pawn)
    try:
        from . import holster

        sprinting = holster.is_sprinting(pc, pawn, ctx)
    except Exception:  # noqa: BLE001
        sprinting = None
    if sprinting and not _crouched(pawn) and core.busy not in ("slide", "slam", "dash", "mantle"):
        sprint_wind(pc, pawn)
    _observe(pc, pawn)


def on_enable() -> None:
    _slots.clear()
    _resolved.clear()
    core.register("surfacefx", tick=_tick, priority=80)


def on_disable() -> None:
    core.unregister("surfacefx")
    _slots.clear()


OPTIONS = [enabled_option]
KEYBINDS: list = []
HOOKS: list = []
