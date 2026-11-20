"""Surface kind and cosmetic calls. Spawning particles is best-effort and must not raise."""

from types import SimpleNamespace

from Modern_Movement.features import surfacefx


def test_surface_kinds_follow_the_ground_name():
    assert surfacefx.classify("PM_Metal_Grate") == "metal"
    assert surfacefx.classify("PhysMat_Water_Puddle") == "water"
    assert surfacefx.classify("PM_Snow") == "snow"
    assert surfacefx.classify("PM_Wood_Plank") == "wood"
    assert surfacefx.classify("PM_Grass") == "grass"
    assert surfacefx.classify("PM_Concrete") == "stone"
    assert surfacefx.classify("PM_Sand") == "dirt"
    assert surfacefx.classify("") == "dirt"
    assert "Metal" in surfacefx.switch_path("metal")
    assert "Water" in surfacefx.switch_path("water")
    assert "Sand" in surfacefx.switch_path("unknown")


def test_slide_and_air_effects_never_raise():
    pawn = SimpleNamespace(
        Location=SimpleNamespace(X=0.0, Y=0.0, Z=100.0),
        Velocity=SimpleNamespace(X=800.0, Y=0.0, Z=0.0),
        WorldInfo=None,
        Rotation=None,
    )
    pc = SimpleNamespace()
    surfacefx._slots.clear()
    surfacefx._resolved.clear()
    assert surfacefx.slide(pc, pawn, 1.0) == "dirt"
    surfacefx.air(pc, pawn, 1.0, 0.0, 1.0)
    surfacefx.puff(pawn, "metal", 0.4)
    surfacefx.sprint_wind(pc, pawn)
    surfacefx.slam_ring(pawn, 0.8)
    surfacefx.burst(pc, pawn, 1.0, 0.0, 4)
    names = " ".join(
        surfacefx._paths_for("air") + surfacefx._paths_for("sprint") + surfacefx._paths_for("ring") + surfacefx._paths_for("dirt")
    )
    assert "Part_Skag_FeetDust" in names
    assert "Part_SparkShowerGeneric" not in names
    assert "Part_Explosive_Nova_Shield_Explosion" in names
    assert "GroundImpactFX" not in names
    assert "Moon" not in names
    from Modern_Movement import fx

    assert any("Fs_Run" in path for path in fx.scrape_paths())
    assert any("Fs_Land" in path for path in fx.slam_hit_paths())
    assert all("Gib" not in path and "Explosive_MED" not in path for path in fx.slam_hit_paths())
    assert fx.SLAM_CRACK.endswith("Explosive_SM")
    assert any("Longbow_Teleport_Out" in path for path in fx.dash_paths())
    from pathlib import Path

    from Modern_Movement import textures_load

    native = Path(textures_load.__file__).resolve().parent / "native"
    assert (native / "bl2" / "_texloader.pyd").is_file()
    assert (native / "tps" / "_texloader.pyd").is_file()
    textures_load.load_packaged(("mm_dash_side",))
    surfacefx._slots.clear()
