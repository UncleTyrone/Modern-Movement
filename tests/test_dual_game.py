"""Borderlands 2 gets custom slam. The Pre-Sequel does not."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Modern_Movement import coop_rpc, core, game, gravity
from Modern_Movement.features import slam
from Modern_Movement.runtime import ExecutionRole, PlayerContext, PlayerKey


class _Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.X = float(x)
        self.Y = float(y)
        self.Z = float(z)


def _ctx(role=ExecutionRole.LOCAL_STANDALONE):
    pawn = SimpleNamespace(
        Physics=core.PHYS_FALLING,
        Velocity=_Vec(200.0, 0.0, 40.0),
        Location=_Vec(0.0, 0.0, 900.0),
        Health=100.0,
        JumpZ=630.0,
        Class=SimpleNamespace(Name="WillowPlayerPawn"),
    )
    pc = SimpleNamespace(bDuck=0, Pawn=pawn, PlayerInput=SimpleNamespace(PressedKeys=[], Bindings=[]))
    return PlayerContext(
        key=PlayerKey(1, 4),
        role=role,
        controller=pc,
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )


@pytest.fixture(autouse=True)
def _restore_slam(monkeypatch):
    monkeypatch.setattr(game, "_cached", "TPS")
    slam.on_disable()
    slam._HOST_SLAMS.clear()
    yield
    slam.on_disable()
    slam._HOST_SLAMS.clear()
    monkeypatch.setattr(game, "_cached", None)


def test_detects_both_supported_games(monkeypatch):
    mods_base = __import__("mods_base")

    def current(name):
        monkeypatch.setattr(game, "_cached", None)
        monkeypatch.setattr(mods_base.Game, "get_current", staticmethod(lambda: SimpleNamespace(name=name)))
        return game.current()

    assert current("BL2") == "BL2"
    assert current("Borderlands2") == "BL2"
    assert current("TPS") == "TPS"
    assert current("Pre-Sequel") == "TPS"
    assert current("AODK") == "AODK"
    monkeypatch.setattr(game, "_cached", "BL2")
    assert game.supported() is True
    assert game.is_bl2() is True
    monkeypatch.setattr(game, "_cached", "TPS")
    assert game.supported() is True
    assert game.is_tps() is True
    monkeypatch.setattr(game, "_cached", "UNSUPPORTED")
    assert game.supported() is False


def test_slam_enables_only_on_bl2(monkeypatch):
    monkeypatch.setattr(game, "_cached", "TPS")
    slam.on_enable()
    assert "slam" not in core._entries

    monkeypatch.setattr(game, "_cached", "BL2")
    slam.on_enable()
    assert "slam" in core._entries
    slam.on_disable()
    assert "slam" not in core._entries


def test_bl2_slam_dives(monkeypatch):
    monkeypatch.setattr(game, "_cached", "BL2")
    slam.on_enable()
    ctx = _ctx()

    def start():
        slam._start(ctx.controller, ctx.pawn)

    core.execute(ctx, start)
    assert slam._slam is not None
    assert ctx.pawn.Velocity.Z == pytest.approx(-float(slam.speed_slider.value))
    assert ctx.pawn.Velocity.X == pytest.approx(200.0 * slam._HORIZONTAL_KEEP)


def test_host_slam_hold_matches_dive():
    ctx = _ctx(ExecutionRole.REMOTE_AUTHORITY)
    slam.host_begin_slam(ctx, 30.0, 0.0, -100.0)
    slam._service_host_slams(1.0 / 60.0)
    assert ctx.pawn.Velocity.Z == pytest.approx(-float(slam.speed_slider.value))
    assert ctx.key.player_id in slam._HOST_SLAMS
    slam.host_end_slam(ctx)
    assert ctx.key.player_id not in slam._HOST_SLAMS
    assert ctx.pawn.Velocity.X == pytest.approx(0.0)


def test_tps_rpc_does_not_arm_slam(monkeypatch):
    ctx = _ctx(ExecutionRole.REMOTE_AUTHORITY)
    monkeypatch.setattr(game, "_cached", "TPS")
    assert coop_rpc._slam_allowed(ctx) is False
    monkeypatch.setattr(coop_rpc, "_sender_pc", lambda _fn: ctx.controller)
    monkeypatch.setattr(coop_rpc, "_host_context", lambda _pc: ctx)
    coop_rpc.server_slam_begin(10.0, 0.0, -2600.0)
    assert slam._HOST_SLAMS == {}
    monkeypatch.setattr(game, "_cached", "BL2")
    assert coop_rpc._slam_allowed(ctx) is True
    coop_rpc.server_slam_begin(10.0, 0.0, -2600.0)
    assert ctx.key.player_id in slam._HOST_SLAMS


def test_bl2_gravity_floor_matches_original(monkeypatch):
    monkeypatch.setattr(game, "_cached", "BL2")
    assert gravity.measured_bounds()[0] == 300.0
