"""Prove listen-host authority paths mutate the joiner's server pawn.

These tests call the same handlers `coop_rpc` invokes on the host after a joiner `@host` RPC
(`_authority_start` / `host_apply_impulse` / `_force_surge_start`). They do not need live
Networking — they verify the host-side mutation contract Eternal/juso rely on.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from Modern_Movement.features import dash, double_jump, holster, mantle, slide, surge
from Modern_Movement.runtime import REGISTRY, ExecutionRole, PlayerContext, PlayerKey, TickFrame
from Modern_Movement import core, authority
from Modern_Movement.protocol import Reason


class _Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.X = float(x)
        self.Y = float(y)
        self.Z = float(z)


class _Pawn:
    def __init__(self, *, physics=2, ground=440.0, crouch=0.5, health=100.0):
        self.Physics = physics
        self.GroundSpeed = ground
        self.CrouchedPct = crouch
        self.Health = health
        self.JumpZ = 600.0
        self.AccelRate = 2048.0
        self.Velocity = _Vec()
        self.Acceleration = _Vec()
        self.Location = _Vec(100.0, 200.0, 50.0)
        self.Weapon = None
        self.InvManager = None
        self.bWantsToCrouch = False
        self.bIsCrouched = False
        self.Class = SimpleNamespace(Name="WillowPlayerPawn")
        self.Floor = _Vec(0.0, 0.0, 1.0)

    def ShouldCrouch(self, value):  # noqa: N802
        self.bWantsToCrouch = bool(value)
        self.bIsCrouched = bool(value)

    def UnCrouch(self):  # noqa: N802
        self.bWantsToCrouch = False
        self.bIsCrouched = False


class _PC:
    def __init__(self):
        self.Rotation = SimpleNamespace(Yaw=0)
        self.bDuck = 1
        self.WorldInfo = SimpleNamespace(WorldGravityZ=-1000.0, TimeSeconds=10.0)
        self.PlayerReplicationInfo = SimpleNamespace(PlayerID=7)
        self.Role = 3


def _remote(pawn, clock=10.0) -> PlayerContext:
    return PlayerContext(
        key=PlayerKey(1, 7),
        role=ExecutionRole.REMOTE_AUTHORITY,
        controller=_PC(),
        pawn=pawn,
        clock=clock,
        pawn_generation=1,
    )


@pytest.fixture(autouse=True)
def _enable_features(monkeypatch):
    monkeypatch.setattr(dash, "enabled_option", SimpleNamespace(value=True))
    monkeypatch.setattr(dash, "air_only_option", SimpleNamespace(value=False))
    monkeypatch.setattr(dash, "cooldown_slider", SimpleNamespace(value=0))
    monkeypatch.setattr(dash, "screen_option", SimpleNamespace(value=False))
    monkeypatch.setattr(dash, "audio_option", SimpleNamespace(value=False))
    monkeypatch.setattr(slide, "enabled_option", SimpleNamespace(value=True))
    monkeypatch.setattr(slide, "boost_slider", SimpleNamespace(value=0))
    monkeypatch.setattr(slide, "max_speed_slider", SimpleNamespace(value=300))
    monkeypatch.setattr(slide, "friction_slider", SimpleNamespace(value=0))
    monkeypatch.setattr(slide, "slope_slider", SimpleNamespace(value=0))
    monkeypatch.setattr(slide, "distance_slider", SimpleNamespace(value=100))
    monkeypatch.setattr(slide, "indicator_option", SimpleNamespace(value=False))
    monkeypatch.setattr(slide, "back_cancel_option", SimpleNamespace(value=False))
    monkeypatch.setattr(double_jump, "enabled_option", SimpleNamespace(value=True))
    monkeypatch.setattr(double_jump, "extra_jumps_slider", SimpleNamespace(value=1))
    monkeypatch.setattr(double_jump, "strength_slider", SimpleNamespace(value=100))
    monkeypatch.setattr(surge, "enabled_option", SimpleNamespace(value=True))
    monkeypatch.setattr(surge, "ramp_slider", SimpleNamespace(value=0.0))
    monkeypatch.setattr(mantle, "enabled_option", SimpleNamespace(value=True))
    core.busy = None
    dash._HOST_DASHES.clear()
    dash._CLIENT_DASH = None
    slide._HOST_SLIDES.clear()
    mantle._HOST_MANTLES.clear()
    yield
    core.busy = None
    dash._HOST_DASHES.clear()
    dash._CLIENT_DASH = None
    slide._HOST_SLIDES.clear()
    mantle._HOST_MANTLES.clear()


def test_call_host_refuses_stub_network_functions():
    from Modern_Movement import coop_rpc

    assert coop_rpc.call_host(coop_rpc.server_dash, 4000.0, 0.0, 0.0) is False


def test_host_dash_eternal_hold_writes_velocity_every_local_tick(monkeypatch):
    """Match Eternal: host hold is serviced from local PlayerTick, not remote feature tick."""
    pawn = _Pawn(physics=core.PHYS_FALLING)
    ctx = _remote(pawn)
    monkeypatch.setattr(
        core,
        "set_velocity",
        lambda p, x, y, z=None: (
            setattr(p.Velocity, "X", x),
            setattr(p.Velocity, "Y", y),
            setattr(p.Velocity, "Z", 0.0 if z is None else z),
        ),
    )

    dash.host_apply_dash(ctx, 4000.0, 0.0, 0.0)
    assert ctx.key.player_id in dash._HOST_DASHES

    dash._service_host_dashes(1.0 / 60.0)
    speed = math.hypot(pawn.Velocity.X, pawn.Velocity.Y)
    assert speed > 1000.0, f"host dash must drive Velocity (got {speed})"
    assert pawn.Velocity.Z == 0.0


def test_joiner_dash_local_predict_matches_host_duration(monkeypatch):
    """Live gap: host-only 0.15s dash dies before proxy replication — DJ dual-write required."""
    pawn = _Pawn(physics=core.PHYS_FALLING)
    monkeypatch.setattr(
        core,
        "set_velocity",
        lambda p, x, y, z=None: (
            setattr(p.Velocity, "X", x),
            setattr(p.Velocity, "Y", y),
            setattr(p.Velocity, "Z", 0.0 if z is None else z),
        ),
    )
    dash._CLIENT_DASH = dash._hold_dash(pawn, 4000.0, 0.0, dash._HOST_DASH_S)
    for _ in range(8):
        dash._service_client_dash(1.0 / 60.0)
        assert dash._CLIENT_DASH is not None
        assert math.hypot(pawn.Velocity.X, pawn.Velocity.Y) > 1000.0
    dash._service_client_dash(1.0)
    assert dash._CLIENT_DASH is None
    assert math.hypot(pawn.Velocity.X, pawn.Velocity.Y) == pytest.approx(200.0, abs=1.0)


def test_host_dash_survives_frozen_location(monkeypatch):
    """Live bug: joiner Location does not advance on host → stall must not kill Eternal hold."""
    pawn = _Pawn(physics=core.PHYS_FALLING)
    ctx = _remote(pawn)
    monkeypatch.setattr(
        core,
        "set_velocity",
        lambda p, x, y, z=None: (
            setattr(p.Velocity, "X", x),
            setattr(p.Velocity, "Y", y),
            setattr(p.Velocity, "Z", 0.0 if z is None else z),
        ),
    )
    dash.host_apply_dash(ctx, 4000.0, 0.0, 0.0)
    frozen = (pawn.Location.X, pawn.Location.Y)
    # Eternal hold is 0.15s; stay inside that window (stall must not end the dash).
    for i in range(8):
        dash._service_host_dashes(1.0 / 60.0)
        assert (pawn.Location.X, pawn.Location.Y) == frozen
        assert ctx.key.player_id in dash._HOST_DASHES, f"remote dash died early at tick {i}"
        assert math.hypot(pawn.Velocity.X, pawn.Velocity.Y) > 1000.0
    # Drain the remainder → soft stop ~200 u/s (Eternal).
    dash._service_host_dashes(1.0)
    assert ctx.key.player_id not in dash._HOST_DASHES
    assert math.hypot(pawn.Velocity.X, pawn.Velocity.Y) == pytest.approx(200.0, abs=1.0)


def test_host_mantle_replays_plan_without_location_stall(monkeypatch):
    """Live bug: joiner vault rubber-banded — host never owned the climb Velocity."""
    pawn = _Pawn(physics=core.PHYS_FALLING)
    pawn.Location = _Vec(0.0, 0.0, 0.0)
    ctx = _remote(pawn)
    monkeypatch.setattr(
        core,
        "set_velocity",
        lambda p, x, y, z=None: (
            setattr(p.Velocity, "X", x),
            setattr(p.Velocity, "Y", y),
            setattr(p.Velocity, "Z", 0.0 if z is None else z),
        ),
    )
    monkeypatch.setattr(core, "set_physics", lambda p, phys: setattr(p, "Physics", phys))
    plan = {
        "start": [0.0, 0.0, 0.0],
        "dir": [1.0, 0.0],
        "hdist": 80.0,
        "lip": 120.0,
        "target": [80.0, 0.0, 100.0],
        "T": 0.40,
        "h": [0.4, 1.0, 1.0, 1.0],
        "z": [200.0],
        "exit": 200.0,
        "v_in": [100.0, 0.0, 50.0],
        "top": 100.0,
        "drop": False,
        "handoff_u": 0.6,
        "clear": None,
        "narrow": False,
        "look": "test",
        "lift": 12.0,
    }
    mantle.host_apply_mantle(ctx, plan)
    assert ctx.key.player_id in mantle._HOST_MANTLES
    assert mantle._state(ctx).mantle is not None
    frozen = (pawn.Location.X, pawn.Location.Y, pawn.Location.Z)
    for i in range(10):
        mantle._service_host_mantles(1.0 / 60.0)
        assert (pawn.Location.X, pawn.Location.Y, pawn.Location.Z) == frozen
        assert mantle._state(ctx).mantle is not None, f"host mantle died at tick {i}"
        assert abs(pawn.Velocity.Z) + abs(pawn.Velocity.X) > 1.0


def test_host_slide_coasts_without_move_input():
    """Joiner released W: host still coasts the server pawn along the entry direction."""
    pawn = _Pawn(physics=core.PHYS_WALKING, crouch=0.5)
    pawn.Velocity = _Vec(0.0, 0.0, 0.0)
    pawn.Acceleration = _Vec(0.0, 0.0, 0.0)
    ctx = _remote(pawn)

    slide.host_enter_juso(ctx, 2.2, 80.0, 1.0, 0.0)
    assert pawn.CrouchedPct == pytest.approx(2.2)
    assert ctx.key.player_id in slide._HOST_SLIDES
    assert slide._HOST_SLIDES[ctx.key.player_id]["dir"] == (1.0, 0.0)
    # Enter records the slide; the per-tick coast is what survives a released key.
    assert pawn.Velocity.X == 0.0 and pawn.Velocity.Y == 0.0

    slide._service_host_slides(0.5)
    scale = slide._distance_scale(80.0)
    cp = 2.2 - (0.5 / scale) * slide._JUSO_DECAY
    assert pawn.CrouchedPct == pytest.approx(cp, abs=0.02)
    assert pawn.Velocity.X == pytest.approx(cp * pawn.GroundSpeed, abs=8.0)
    assert pawn.Velocity.Y == pytest.approx(0.0, abs=0.01)
    assert pawn.Acceleration.X == pytest.approx(pawn.AccelRate)
    assert pawn.Acceleration.Y == pytest.approx(0.0)


def test_dual_player_slide_distance_independent(monkeypatch):
    """Each joiner's Slide Distance (%) scales their own host decay, not the host menu."""
    monkeypatch.setattr(slide, "distance_slider", SimpleNamespace(value=40))
    a = _Pawn(physics=core.PHYS_WALKING, crouch=0.5)
    b = _Pawn(physics=core.PHYS_WALKING, crouch=0.5)
    ctx_a = PlayerContext(
        key=PlayerKey(1, 11),
        role=ExecutionRole.REMOTE_AUTHORITY,
        controller=_PC(),
        pawn=a,
        clock=10.0,
        pawn_generation=1,
    )
    ctx_b = PlayerContext(
        key=PlayerKey(1, 12),
        role=ExecutionRole.REMOTE_AUTHORITY,
        controller=_PC(),
        pawn=b,
        clock=10.0,
        pawn_generation=1,
    )
    slide.host_enter_juso(ctx_a, 2.2, 50.0)
    slide.host_enter_juso(ctx_b, 2.2, 140.0)
    assert slide._HOST_SLIDES[11]["distance"] == 50.0
    assert slide._HOST_SLIDES[12]["distance"] == 140.0

    slide._service_host_slides(0.5)
    # Lower distance → faster effective decay (dt/scale); higher distance → slower.
    assert a.CrouchedPct < b.CrouchedPct
    assert a.CrouchedPct == pytest.approx(
        2.2 - (0.5 / slide._distance_scale(50.0)) * slide._JUSO_DECAY, abs=0.03
    )
    assert b.CrouchedPct == pytest.approx(
        2.2 - (0.5 / slide._distance_scale(140.0)) * slide._JUSO_DECAY, abs=0.03
    )


def test_host_double_jump_hold_rewrites_velocity():
    pawn = _Pawn(physics=core.PHYS_FALLING)
    pawn.Velocity = _Vec(10.0, 0.0, -50.0)
    ctx = _remote(pawn, clock=5.0)

    double_jump.host_apply_impulse(ctx, 100.0, 0.0, 600.0)
    assert pawn.Velocity.Z == 600.0

    # Simulate a move packet clobbering the impulse, then host tick must restore it.
    pawn.Velocity.Z = -20.0
    ctx.clock = 5.05
    double_jump._authority_tick(
        ctx, TickFrame(now=5.05, dt=0.05, phys_at_start=2, world_epoch=1)
    )
    assert pawn.Velocity.Z == 600.0
    assert pawn.Velocity.X == 100.0


def test_dual_player_double_jump_strength_independent(monkeypatch):
    """Requester impulse + max_jumps stick per player_id; host strength slider is ignored."""
    monkeypatch.setattr(double_jump, "strength_slider", SimpleNamespace(value=50))
    monkeypatch.setattr(double_jump, "extra_jumps_slider", SimpleNamespace(value=1))
    a = _Pawn(physics=core.PHYS_FALLING)
    b = _Pawn(physics=core.PHYS_FALLING)
    ctx_a = PlayerContext(
        key=PlayerKey(1, 21),
        role=ExecutionRole.REMOTE_AUTHORITY,
        controller=_PC(),
        pawn=a,
        clock=5.0,
        pawn_generation=1,
    )
    ctx_b = PlayerContext(
        key=PlayerKey(1, 22),
        role=ExecutionRole.REMOTE_AUTHORITY,
        controller=_PC(),
        pawn=b,
        clock=5.0,
        pawn_generation=1,
    )
    double_jump.host_apply_impulse(ctx_a, 50.0, 0.0, 400.0, max_jumps=1)
    double_jump.host_apply_impulse(ctx_b, 80.0, 0.0, 800.0, max_jumps=3)
    assert a.Velocity.Z == 400.0
    assert b.Velocity.Z == 800.0
    assert double_jump._state_for(ctx_a).max_jumps == 1
    assert double_jump._state_for(ctx_b).max_jumps == 3
    assert double_jump._state_for(ctx_a).jumps_used == 1
    assert double_jump._state_for(ctx_b).jumps_used == 1


def test_host_surge_force_start_raises_groundspeed():
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    ctx = _remote(pawn)
    authority.register_feature(
        "holster",
        authority.FeatureController(input=holster._authority_input, tick=holster._authority_tick),
    )

    reason, snap = holster._authority_input(ctx, {"kind": "surge"})
    assert reason == Reason.OK
    assert snap["surge_active"] is True
    assert pawn.GroundSpeed > 440.0, f"host surge must raise GroundSpeed (got {pawn.GroundSpeed})"


def test_host_surge_end_restores_groundspeed():
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    ctx = _remote(pawn)
    holster._authority_input(ctx, {"kind": "surge"})
    boosted = pawn.GroundSpeed
    assert boosted > 440.0

    holster._authority_input(ctx, {"kind": "surge_end"})
    # Apply once more like the remote tick would.
    core.execute(ctx, holster._apply_speed_boost, ctx, pawn, False)
    core._apply_speed(ctx, pawn)
    assert pawn.GroundSpeed == pytest.approx(440.0, abs=0.6)


def test_requester_slide_coasts_when_forward_released(monkeypatch):
    """Releasing W zeroes Acceleration. The joiner slide must keep its entry speed."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(500.0, 0.0, 0.0)
    pawn.bWantsToCrouch = True
    ctx = PlayerContext(
        key=PlayerKey(1, 8),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=_PC(),
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    monkeypatch.setattr(slide.core, "current_context", lambda: ctx)
    monkeypatch.setattr(slide.core, "phys", core.PHYS_WALKING)
    monkeypatch.setattr(slide.core, "busy", "slide")
    monkeypatch.setattr(slide.core, "clock", 10.0)

    def start():
        slide._start(ctx.controller, pawn, "test")

    core.execute(ctx, start)
    assert slide._state(ctx).slide is not None
    assert slide._state(ctx).slide["timed"] is True
    assert pawn.CrouchedPct >= slide._JUSO_SLIDE_PCT

    # Engine walking brake after the movement key comes up.
    pawn.Velocity = _Vec(0.0, 0.0, 0.0)
    pawn.Acceleration = _Vec(0.0, 0.0, 0.0)

    def run():
        slide._run(ctx.controller, pawn, 1.0 / 60.0)

    core.execute(ctx, run)
    assert slide._state(ctx).slide is not None
    assert pawn.CrouchedPct > 0.5
    assert pawn.Velocity.X > 400.0
    assert pawn.Velocity.Y == pytest.approx(0.0, abs=0.01)
    assert pawn.Acceleration.X == pytest.approx(pawn.AccelRate)
    assert pawn.Acceleration.Y == pytest.approx(0.0)


def test_host_replayed_move_restores_slide_after_brake():
    """Server PlayerMove of a released key must not be the correction that stops the joiner."""
    pawn = _Pawn(physics=core.PHYS_WALKING, crouch=0.5)
    pc = _PC()
    ctx = REGISTRY.observe(pc, ExecutionRole.REMOTE_AUTHORITY, 10.0, pawn)
    try:
        slide.host_enter_juso(ctx, 2.2, 90.0, 0.0, 1.0)
        pawn.Velocity = _Vec(0.0, 0.0, 0.0)
        pawn.Acceleration = _Vec(0.0, 0.0, 0.0)
        pawn.CrouchedPct = 0.5
        slide._post_player_move(pc, None, None, None)
        assert pawn.CrouchedPct == pytest.approx(2.2)
        assert pawn.Velocity.Y == pytest.approx(2.2 * pawn.GroundSpeed, abs=1.0)
        assert pawn.Velocity.X == pytest.approx(0.0, abs=0.01)
        assert pawn.Acceleration.Y == pytest.approx(pawn.AccelRate)
    finally:
        REGISTRY.retire(ctx, "test")


def test_host_slide_survives_without_bduck():
    """juso host dict does not depend on joiner bDuck replication."""
    pawn = _Pawn(physics=core.PHYS_WALKING, crouch=0.5)
    pc = _PC()
    pc.bDuck = 0
    pawn.bWantsToCrouch = False
    pawn.bIsCrouched = False
    ctx = PlayerContext(
        key=PlayerKey(1, 9),
        role=ExecutionRole.REMOTE_AUTHORITY,
        controller=pc,
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    slide.host_enter_juso(ctx, 2.2)
    for i in range(10):
        slide._service_host_slides(1.0 / 60.0)
        assert ctx.key.player_id in slide._HOST_SLIDES, f"host slide died at tick {i}"
        assert pawn.CrouchedPct > 0.5


def test_requester_slide_uses_timed_path(monkeypatch):
    """Joiners must not use location-stall — that was the 1ms slide then stuck crouch."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(700.0, 0.0, 0.0)
    pawn.bWantsToCrouch = True
    ctx = PlayerContext(
        key=PlayerKey(1, 11),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=_PC(),
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    monkeypatch.setattr(slide.core, "phys", core.PHYS_WALKING)
    monkeypatch.setattr(slide.core, "clock", 10.0)

    def start():
        slide._start(ctx.controller, pawn, "test")

    core.execute(ctx, start)
    assert slide._state(ctx).slide["timed"] is True
    frozen = (pawn.Location.X, pawn.Location.Y)
    for i in range(10):
        core.execute(ctx, slide._run, ctx.controller, pawn, 1.0 / 60.0)
        assert (pawn.Location.X, pawn.Location.Y) == frozen
        assert slide._state(ctx).slide is not None, f"joiner slide died at tick {i}"


def test_slide_end_always_uncrouches():
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.bWantsToCrouch = True
    pawn.bIsCrouched = True
    ctx = _remote(pawn)
    state = slide._state(ctx)
    state.slide = {
        "dir": (1.0, 0.0),
        "speed": 900.0,
        "start": 900.0,
        "entry": 700.0,
        "elapsed": 0.0,
        "last": (0.0, 0.0),
        "commanded": 0.0,
        "stalled": 0,
        "timed": True,
        "cp": 2.2,
    }
    state.crouch_owned = True

    def end():
        slide._end(pawn, "slowed", ctx.controller)

    core.execute(ctx, end)
    assert pawn.bWantsToCrouch is False
    assert pawn.bIsCrouched is False
