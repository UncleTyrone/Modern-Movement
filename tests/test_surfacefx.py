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
    surfacefx._slots.clear()
