"""Joining clients must get full local movement without host intents or Networking."""

from __future__ import annotations

from Modern_Movement.features import double_jump
from Modern_Movement.runtime import ExecutionRole, PlayerContext, PlayerKey


class _Vel:
    def __init__(self, z: float = 0.0):
        self.X = 0.0
        self.Y = 0.0
        self.Z = z


class _Pawn:
    Physics = 2  # falling
    Health = 100
    JumpZ = 600.0
    GroundSpeed = 440.0
    Acceleration = _Vel()
    Class = type("C", (), {"Name": "WillowPlayerPawn"})()

    def __init__(self):
        self.Velocity = _Vel(50.0)


def test_requester_role_is_local_authority():
    role = ExecutionRole.LOCAL_REQUESTER
    assert role.local and role.authority and role.presentation


def test_requester_double_jump_writes_velocity(monkeypatch):
    pawn = _Pawn()
    ctx = PlayerContext(
        key=PlayerKey(1, 7),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=object(),
        pawn=pawn,
        clock=5.0,
    )
    monkeypatch.setattr(double_jump.core, "current_context", lambda: ctx)
    monkeypatch.setattr(double_jump.core, "clock", 5.0)
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
    assert pawn.Velocity.Z > 50.0


def test_jump_logic_works_for_requester(monkeypatch):
    from Modern_Movement import core

    pawn = _Pawn()
    ctx = PlayerContext(
        key=PlayerKey(1, 8),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=object(),
        pawn=pawn,
        clock=20.0,
    )
    seen = []

    def fake_air(pc, p):
        seen.append(core.current_context().role)
        p.Velocity.Z = 700.0
        return True

    monkeypatch.setattr(core, "local_context", lambda: ctx)
    monkeypatch.setattr(core, "_air_handlers", [("double_jump", fake_air)])
    monkeypatch.setattr(core, "_ground_handlers", [])
    monkeypatch.setattr(core, "_slide_owns_jump", lambda *_a: False)
    monkeypatch.setattr(core, "_last_ground_press", -100.0)
    monkeypatch.setattr(core, "_last_jump_edge", -100.0)
    core.busy = None
    core.clock = 20.0

    core._jump_logic()
    assert seen == [ExecutionRole.LOCAL_REQUESTER]
    assert pawn.Velocity.Z == 700.0


def test_network_module_loads_without_blocking_ready():
    from Modern_Movement import network

    assert network.ready() is True
    assert network.all_peers_ready() is True
