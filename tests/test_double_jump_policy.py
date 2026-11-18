from __future__ import annotations

from Modern_Movement.features import double_jump
from Modern_Movement.runtime import ExecutionRole, PlayerContext, PlayerKey


class _Vel:
    def __init__(self, z: float = 0.0):
        self.X = 0.0
        self.Y = 0.0
        self.Z = z


class _Pawn:
    Physics = 2
    Health = 100
    JumpZ = 600.0
    GroundSpeed = 440.0
    Acceleration = _Vel()
    Class = type("C", (), {"Name": "WillowPlayerPawn"})()

    def __init__(self):
        self.Velocity = _Vel(100.0)


def test_air_press_applies_without_oz_reservation(monkeypatch):
    """First airborne press must spend a mod double jump (no Oz deferral)."""
    pawn = _Pawn()
    ctx = PlayerContext(
        key=PlayerKey(1, 1),
        role=ExecutionRole.LOCAL_HOST,
        controller=object(),
        pawn=pawn,
    )
    monkeypatch.setattr(double_jump.core, "current_context", lambda: ctx)
    monkeypatch.setattr(double_jump.core, "clock", 10.0)
    monkeypatch.setattr(double_jump.core, "base_jump", lambda _p: 600.0)
    monkeypatch.setattr(double_jump.enabled_option, "value", True)
    monkeypatch.setattr(double_jump.extra_jumps_slider, "value", 1)
    monkeypatch.setattr(double_jump.strength_slider, "value", 100)
    monkeypatch.setattr(double_jump.only_rising_option, "value", False)
    monkeypatch.setattr(double_jump.sound_option, "value", False)

    state = double_jump._state_for(ctx)
    state.left_by_jump = True
    state.jumps_used = 0

    assert double_jump._on_air_press(ctx.controller, pawn) is True
    assert state.jumps_used == 1
    assert pawn.Velocity.Z > 0.0


def test_double_jump_allows_near_jump_speed(monkeypatch):
    """Rising at almost JumpZ used to refuse the boost (vz >= target); allow a small margin."""
    pawn = _Pawn()
    pawn.Velocity.Z = 600.0
    ctx = PlayerContext(
        key=PlayerKey(1, 2),
        role=ExecutionRole.LOCAL_HOST,
        controller=object(),
        pawn=pawn,
    )
    monkeypatch.setattr(double_jump.core, "current_context", lambda: ctx)
    monkeypatch.setattr(double_jump.core, "clock", 10.0)
    monkeypatch.setattr(double_jump.core, "base_jump", lambda _p: 600.0)
    monkeypatch.setattr(double_jump.enabled_option, "value", True)
    monkeypatch.setattr(double_jump.extra_jumps_slider, "value", 1)
    monkeypatch.setattr(double_jump.strength_slider, "value", 100)
    monkeypatch.setattr(double_jump.only_rising_option, "value", False)
    monkeypatch.setattr(double_jump.sound_option, "value", False)
    state = double_jump._state_for(ctx)
    state.left_by_jump = True
    state.jumps_used = 0
    assert double_jump._on_air_press(ctx.controller, pawn) is True


def test_double_jump_has_no_oz_reserved_field():
    assert not hasattr(double_jump.DoubleJumpState(), "oz_reserved")


def test_jump_logic_activates_context(monkeypatch):
    """Keybind path must execute air handlers with an active context (else DJ is a no-op)."""
    from Modern_Movement import core

    pawn = _Pawn()
    ctx = PlayerContext(
        key=PlayerKey(1, 1),
        role=ExecutionRole.LOCAL_HOST,
        controller=object(),
        pawn=pawn,
        clock=10.0,
    )
    calls = []

    def fake_air(pc, p):
        calls.append(core.current_context() is ctx)
        p.Velocity.Z = 500.0
        return True

    monkeypatch.setattr(core, "local_context", lambda: ctx)
    monkeypatch.setattr(core, "_air_handlers", [("double_jump", fake_air)])
    monkeypatch.setattr(core, "_ground_handlers", [])
    monkeypatch.setattr(core, "_slide_owns_jump", lambda *_a: False)
    monkeypatch.setattr(core, "_last_ground_press", -100.0)
    monkeypatch.setattr(core, "_last_jump_edge", -100.0)
    core.busy = None
    core.clock = 10.0

    core._jump_logic()
    assert calls == [True]
    assert pawn.Velocity.Z == 500.0
