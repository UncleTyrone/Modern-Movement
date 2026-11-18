from __future__ import annotations

from Modern_Movement.features.slide import SlideCrouchLease, SlideState
from Modern_Movement.protocol import Reason
from Modern_Movement.runtime import ExecutionRole, PlayerContext, PlayerKey


class _Pawn:
    Physics = 2  # falling
    Health = 100
    Class = type("C", (), {"Name": "WillowPlayerPawn"})()
    Velocity = type("V", (), {"X": 0.0, "Y": 0.0, "Z": 100.0})()
    JumpZ = 600.0


def test_mantle_air_fallback_calls_double_jump(monkeypatch):
    from Modern_Movement.features import double_jump, mantle

    calls = []

    def fake_air(pc, pawn):
        calls.append("mantle")
        return False

    def fake_dj(ctx, payload):
        calls.append(("dj", payload.get("kind")))
        return Reason.OK, {"jumps_used": 0}

    monkeypatch.setattr(mantle, "_on_air_press", fake_air)
    monkeypatch.setattr(double_jump, "_authority_input", fake_dj)
    monkeypatch.setattr(
        "Modern_Movement.features.mantle.network.all_peers_ready",
        lambda: True,
        raising=False,
    )

    ctx = PlayerContext(
        key=PlayerKey(1, 1),
        role=ExecutionRole.LOCAL_HOST,
        controller=object(),
        pawn=_Pawn(),
    )
    reason, _ = mantle._authority_input(ctx, {"kind": "jump", "fallback": "double_jump"})
    assert reason == Reason.OK
    assert calls == ["mantle", ("dj", "jump")]


def test_slide_crouch_lease_defaults():
    state = SlideState()
    assert isinstance(state.crouch_lease, SlideCrouchLease)
    assert state.crouch_pressed_while_airborne is False
