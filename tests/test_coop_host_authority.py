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
from Modern_Movement import core, authority, game
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
    monkeypatch.setattr(slide, "speed_slider", SimpleNamespace(value=100))
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
    slide._HOST_JUMPS.clear()
    mantle._HOST_MANTLES.clear()
    yield
    core.busy = None
    dash._HOST_DASHES.clear()
    dash._CLIENT_DASH = None
    slide._HOST_SLIDES.clear()
    slide._HOST_JUMPS.clear()
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


def test_host_dash_hold_returns_to_falling_without_rewriting_z(monkeypatch):
    """Touching the ground mid-hold must not clamp the burst. Z stays whatever it was."""
    pawn = _Pawn(physics=core.PHYS_FALLING)
    pawn.Velocity.Z = 40.0
    ctx = _remote(pawn)

    def _write(p, x, y, z=None):
        p.Velocity.X = float(x)
        p.Velocity.Y = float(y)
        if z is not None:
            p.Velocity.Z = float(z)

    monkeypatch.setattr(core, "set_velocity", _write)
    dash.host_apply_dash(ctx, 4000.0, 0.0, 0.0)
    pawn.Physics = core.PHYS_WALKING
    pawn.Velocity.Z = 40.0
    dash._service_host_dashes(1.0 / 60.0)
    assert pawn.Physics == core.PHYS_FALLING
    assert pawn.Velocity.Z == pytest.approx(40.0)
    assert pawn.Velocity.X > 1000.0


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


def test_sprint_speed_counts_as_running_into_a_vault():
    """A sprint leaves acceleration at zero. Speed toward the camera still vaults."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Acceleration = _Vec(0.0, 0.0, 0.0)
    pawn.Velocity = _Vec(800.0, 0.0, 0.0)
    pc = _PC()
    assert mantle._moving_into_wall(pc, pawn) is True
    pawn.Velocity = _Vec(0.0, 0.0, 0.0)
    assert mantle._moving_into_wall(pc, pawn) is False


def test_ledge_hit_keeps_its_place_when_the_trace_names_a_material():
    """A wall hit is location, normal, and a material name. The climb only needs the first two."""
    from Modern_Movement import tracing

    hit = ((10.0, 0.0, 80.0), (0.0, 1.0, 0.0), "Concrete")
    (hx, hy, hz), (nx, ny, nz) = tracing.pair(hit)
    assert (hx, hy, hz) == (10.0, 0.0, 80.0)
    assert (nx, ny, nz) == (0.0, 1.0, 0.0)


def test_remote_slide_tick_does_not_start_or_block_crouch():
    """The host must not run slide-cancel input on a joiner. That ate their crouch and dash."""
    from Modern_Movement.features import slam

    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(900.0, 0.0, 0.0)
    pawn.bIsSprinting = True
    pc = _PC()
    pc.bDuck = 1
    ctx = REGISTRY.observe(pc, ExecutionRole.REMOTE_AUTHORITY, 10.0, pawn)
    saved_keys = slam._crouch_keys
    saved_at = slam._keys_at
    try:
        slam._crouch_keys = ("LeftControl",)
        slam._keys_at = 10.0
        state = slide._state(ctx)
        state.chain = {"dir": (1.0, 0.0), "speed": 800.0, "at": 0.0}
        state.suppress_crouch_until_release = True
        assert slide._pre_duck_pressed(pc, None, None, None) is None
        frame = TickFrame(now=10.0, dt=1.0 / 60.0, phys_at_start=core.PHYS_WALKING, world_epoch=0)
        slide._authority_tick(ctx, frame)
        assert state.slide is None
        assert core.busy is None
        assert slam._crouch_keys == ("LeftControl",)
        slide.host_enter_juso(ctx, 2.2, 100.0, 1.0, 0.0)
        slide._authority_tick(ctx, frame)
        assert ctx.key.player_id in slide._HOST_SLIDES
    finally:
        slam._crouch_keys = saved_keys
        slam._keys_at = saved_at
        REGISTRY.retire(ctx, "test")


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
    assert pawn.Acceleration.X == pytest.approx(slide._COAST_PUSH)
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


def test_holstered_shift_starts_surge_like_gun_out():
    """A second sprint press must boost while the gun is already away."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Weapon = None
    ctx = PlayerContext(
        key=PlayerKey(1, 31),
        role=ExecutionRole.LOCAL_HOST,
        controller=_PC(),
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    state = holster._state(ctx)
    state.holstered = True
    state.sprint_holstered = False
    state.stow_kind = None
    state.sprinting_now = True

    core.execute(ctx, holster._sprint_surge_logic)
    assert state.stow_kind == "surge"
    assert holster._boost_active(ctx) is True
    core.execute(ctx, holster._apply_speed_boost, ctx, pawn, True)
    core._apply_speed(ctx, pawn)
    assert pawn.GroundSpeed > 440.0


def test_bl2_first_shift_does_not_start_a_surge(monkeypatch):
    """Borderlands 2: the first Shift press is a normal sprint. The next one, while sprinting, surges."""
    monkeypatch.setattr(game, "is_bl2", lambda: True)
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Weapon = None
    ctx = PlayerContext(
        key=PlayerKey(1, 33),
        role=ExecutionRole.LOCAL_HOST,
        controller=_PC(),
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    state = holster._state(ctx)
    state.sprinting_now = False
    state.last_sprint_active = -100.0
    state.last_tap = -100.0
    core.execute(ctx, holster._sprint_surge_logic)
    assert state.stow_kind != "surge"
    state.sprinting_now = True
    ctx.clock = 11.0
    core.execute(ctx, holster._sprint_surge_logic)
    assert state.stow_kind == "surge"
    assert holster._boost_active(ctx) is True


def test_surge_key_starts_again_after_the_last_one():
    """The surge key starts a surge. Standing still does not throw the press away."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Weapon = None
    ctx = PlayerContext(
        key=PlayerKey(1, 32),
        role=ExecutionRole.LOCAL_HOST,
        controller=_PC(),
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    state = holster._state(ctx)
    state.holstered = True
    state.sprinting_now = False
    state.last_sprint_active = -100.0
    state.last_tap = -100.0

    core.execute(ctx, holster._sprint_surge_logic)
    assert state.stow_kind == "surge"
    assert holster._boost_active(ctx) is True
    ctx.clock = 11.0
    core.execute(ctx, holster._sprint_surge_logic)
    assert holster._boost_active(ctx) is False
    ctx.clock = 12.0
    core.execute(ctx, holster._sprint_surge_logic)
    assert holster._boost_active(ctx) is True


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


def test_second_surge_stays_on_when_the_host_is_asked_again():
    """A joiner's next super sprint is a start. The host must not treat that message as turn-off."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Weapon = object()
    pawn.InvManager = SimpleNamespace(SetCurrentWeapon=lambda *_a: None, SwitchToBestWeapon=lambda: None)
    ctx = _remote(pawn)
    holster._authority_input(ctx, {"kind": "surge"})
    first = pawn.GroundSpeed
    assert first > 440.0
    holster._authority_input(ctx, {"kind": "surge"})
    assert holster._boost_active(ctx) is True
    assert pawn.GroundSpeed > 440.0
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


def test_joiner_surge_factor_stays_on_the_host_pawn():
    """The host writes the joiner's multiplier. The host's own ramp of 3 seconds does not replace it."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    ctx = _remote(pawn)
    previous = surge.ramp_slider.value
    surge.ramp_slider.value = 3.0
    try:
        holster.apply_peer_factor(ctx, 1.7)
        assert pawn.GroundSpeed == pytest.approx(440.0 * 1.7, abs=0.6)
        pawn.GroundSpeed = 440.0
        core.execute(ctx, holster._tick, ctx.controller, pawn, 0.05)
        core._apply_speed(ctx, pawn)
        assert holster._state(ctx).peer_factor == pytest.approx(1.7)
        assert pawn.GroundSpeed == pytest.approx(440.0 * 1.7, abs=0.6)
        assert pawn.Velocity.X == pytest.approx(0.0, abs=0.1)
    finally:
        surge.ramp_slider.value = previous


def test_surge_scales_the_run_they_already_have():
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Velocity = _Vec(440.0, 0.0, 0.0)
    ctx = _remote(pawn)
    holster.apply_peer_factor(ctx, 1.5)
    assert pawn.GroundSpeed == pytest.approx(660.0, abs=1.0)
    assert pawn.Velocity.X == pytest.approx(660.0, abs=1.0)
    assert pawn.Velocity.Z == pytest.approx(0.0, abs=0.1)
    holster.apply_peer_factor(ctx, 1.5)
    assert pawn.Velocity.X == pytest.approx(660.0, abs=1.0)


def test_ending_the_surge_puts_the_run_back():
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    ctx = _remote(pawn)
    holster.apply_peer_factor(ctx, 1.5)
    assert pawn.GroundSpeed > 440.0
    holster.apply_peer_factor(ctx, 1.0)
    assert holster._state(ctx).peer_factor is None
    assert pawn.GroundSpeed == pytest.approx(440.0, abs=0.6)


def test_host_tick_keeps_the_joiners_boost_and_their_velocity():
    """The host refreshes GroundSpeed. It does not push the joiner faster than that boost."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Velocity = _Vec(440.0, 0.0, 0.0)
    pc = _PC()
    pc.PlayerReplicationInfo = SimpleNamespace(PlayerID=44)
    ctx = REGISTRY.observe(pc, ExecutionRole.REMOTE_AUTHORITY, 10.0, pawn)
    assert ctx is not None
    try:
        holster._state(ctx).peer_factor = 1.5
        holster._service_host_surges()
        assert pawn.GroundSpeed == pytest.approx(660.0, abs=1.0)
        assert pawn.Velocity.X == pytest.approx(660.0, abs=1.0)
    finally:
        REGISTRY.retire(ctx, "test")


def test_surge_multiplies_a_sprint_ground_speed_once():
    """A sprint GroundSpeed is the base. A later boosted sample must not stack."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=800.0)
    pawn.Velocity = _Vec(700.0, 0.0, 0.0)
    ctx = _remote(pawn)
    holster.apply_peer_factor(ctx, 1.5)
    assert pawn.GroundSpeed == pytest.approx(1200.0, abs=1.0)
    assert pawn.Velocity.X == pytest.approx(1050.0, abs=1.0)
    pawn.GroundSpeed = 2000.0
    holster.apply_peer_factor(ctx, 1.5)
    assert pawn.GroundSpeed == pytest.approx(1200.0, abs=1.0)
    assert pawn.Velocity.X == pytest.approx(1050.0, abs=1.0)


def test_a_sprint_keeps_its_velocity_under_surge():
    """Surge raises GroundSpeed. It does not launch the sprint they already have."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Velocity = _Vec(700.0, 0.0, 0.0)
    pc = _PC()
    pc.PlayerReplicationInfo = SimpleNamespace(PlayerID=48)
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_HOST, 10.0, pawn)
    assert ctx is not None
    try:
        holster._state(ctx).surge_started = 10.0
        factor = core.execute(ctx, holster._speed_multiplier, ctx, pawn)
        assert factor == pytest.approx(1.7, abs=0.05)
        core.execute(ctx, holster._apply_speed_boost, ctx, pawn, True)
        assert pawn.GroundSpeed == pytest.approx(440.0 * 1.7, abs=1.0)
        assert pawn.Velocity.X == pytest.approx(700.0 * 1.7, abs=1.0)
    finally:
        REGISTRY.retire(ctx, "test")


def test_an_absolute_speed_does_not_launch_the_joiner():
    """An old message that carried uu/s is capped at the same boost. Velocity is not touched."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Velocity = _Vec(700.0, 0.0, 0.0)
    ctx = _remote(pawn)
    holster.apply_peer_factor(ctx, 1100.0)
    assert holster._state(ctx).peer_factor == pytest.approx(1.7)
    assert pawn.GroundSpeed == pytest.approx(440.0 * 1.7, abs=1.0)
    assert pawn.Velocity.X == pytest.approx(700.0 * 1.7, abs=1.0)
    pawn.GroundSpeed = 2000.0
    holster.apply_peer_factor(ctx, 1100.0)
    assert pawn.GroundSpeed == pytest.approx(440.0 * 1.7, abs=1.0)
    assert pawn.Velocity.X == pytest.approx(700.0 * 1.7, abs=1.0)


def test_a_look_direction_does_not_launch_a_surge():
    """No run means no surge launch. Pushing along the crosshair was the jump teleport."""
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=440.0)
    pawn.Velocity = _Vec(0.0, 0.0, 0.0)
    pawn.Acceleration = _Vec(800.0, 0.0, 0.0)
    ctx = _remote(pawn)
    holster.apply_peer_factor(ctx, 1.5)
    assert pawn.Velocity.X == pytest.approx(0.0, abs=1.0)


def test_a_jump_does_not_take_the_surge_speed():
    pawn = _Pawn(physics=core.PHYS_FALLING, ground=440.0)
    pawn.Velocity = _Vec(80.0, 0.0, 400.0)
    pawn.Acceleration = _Vec(800.0, 0.0, 0.0)
    ctx = _remote(pawn)
    holster.apply_peer_factor(ctx, 900.0)
    assert pawn.Velocity.X == pytest.approx(80.0, abs=1.0)
    assert pawn.Velocity.Z == pytest.approx(400.0, abs=1.0)


def test_uncrouch_during_slide_jump_keeps_the_landing(monkeypatch):
    """Standing up at the jump is not a crouch release. The key still has to be down."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.JumpZ = 600.0
    pc = _PC()
    pc.PlayerReplicationInfo = SimpleNamespace(PlayerID=45)
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_REQUESTER, 10.0, pawn)
    assert ctx is not None
    monkeypatch.setattr(slide, "_crouch_held", lambda _pc: True)
    monkeypatch.setattr("Modern_Movement.coop_rpc.call_host", lambda *_a, **_k: False)
    real_end = slide._end

    def ending(pawn, reason, pc=None):
        real_end(pawn, reason, pc)
        slide._pre_duck_released(pc, None, None, None)

    monkeypatch.setattr(slide, "_end", ending)
    try:
        def arm():
            state = slide._state()
            state.crouch_down = True
            state.slide = {
                "dir": (1.0, 0.0),
                "speed": 800.0,
                "entry": 800.0,
                "start": 800.0,
                "timed": False,
            }
            slide._ground_jump(pc, pawn)

        core.execute(ctx, arm)
        state = slide._state(ctx)
        assert state.crouch_down is True
        assert state.chain is not None
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_slide_cancel_waits_out_a_short_touch_then_lands(monkeypatch):
    """Touching ground before the jump has been airborne does not throw away the landing slide."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(900.0, 0.0, 0.0)
    pc = _PC()
    pc.bDuck = 0
    pc.PlayerReplicationInfo = SimpleNamespace(PlayerID=46)
    monkeypatch.setattr(slide, "_crouch_held", lambda _pc: True)
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_REQUESTER, 10.0, pawn)
    assert ctx is not None
    try:
        state = slide._state(ctx)
        state.crouch_down = True
        state.chain_hold = True
        state.chain_was_air = True
        state.prev_phys = core.PHYS_WALKING
        state.chain = {"dir": (1.0, 0.0), "speed": 800.0, "at": 10.0}
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert state.slide is None
        assert state.chain is not None
        state.chain["at"] = 9.0
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert state.slide is not None
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_a_chained_slide_does_not_keep_the_tilted_gun():
    """The level pose stays the rest pose. A gun already leaned over is not saved as normal."""
    mesh = SimpleNamespace(
        RotOrigin=SimpleNamespace(Pitch=900, Yaw=-350, Roll=-7800),
        Origin=SimpleNamespace(X=28.0, Y=-18.0, Z=-188.0),
    )
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Arms = SimpleNamespace(SkeletalMesh=mesh)
    pc = _PC()
    pc.Pawn = pawn
    pc.PlayerReplicationInfo = SimpleNamespace(PlayerID=47)
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 10.0, pawn)
    assert ctx is not None
    try:
        core.execute(ctx, slide._begin_slide_pose, pc, pawn)
        arms = slide._state(ctx).arms
        assert arms is not None
        assert arms["rest"]["roll"] == 0.0
        assert arms["rest"]["pitch"] == 0.0
        core.execute(ctx, slide._end_slide_pose, pc, pawn)
        assert slide._state(ctx).arms is None
        core.execute(ctx, slide._tick_slide_pose, pc, 0.1)
        assert slide._state(ctx).arms is None
        mesh.RotOrigin.Pitch = 900
        mesh.RotOrigin.Roll = -7800
        slide._state(ctx).slide = None
        core.execute(ctx, slide._settle_arms, pc)
        assert abs(float(mesh.RotOrigin.Roll)) < 1.0
        assert abs(float(mesh.RotOrigin.Pitch)) < 1.0
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


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
    assert pawn.Acceleration.X == pytest.approx(slide._COAST_PUSH)
    assert pawn.Acceleration.Y == pytest.approx(0.0)


def test_host_slide_speed_scales_coast_not_duration():
    """Slide Speed (%) speeds the coast up. Distance still owns how fast CrouchedPct decays."""
    pawn = _Pawn(physics=core.PHYS_WALKING, crouch=0.5)
    ctx = _remote(pawn)
    slide.host_enter_juso(ctx, 2.2, 100.0, 1.0, 0.0, 150.0)
    slide._service_host_slides(0.5)
    cp = 2.2 - 0.5 * slide._JUSO_DECAY
    assert pawn.CrouchedPct == pytest.approx(cp * 1.5, abs=0.05)
    assert pawn.Velocity.X == pytest.approx(cp * pawn.GroundSpeed * 1.5, abs=12.0)


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
        assert pawn.Acceleration.Y == pytest.approx(slide._COAST_PUSH)
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


def test_host_slide_jump_holds_launch_without_freezing_z(monkeypatch):
    """A joiner slide jump must stay on the server pawn. Rising Z is left alone."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    ctx = _remote(pawn)

    def _write(p, x, y, z=None):
        p.Velocity.X = float(x)
        p.Velocity.Y = float(y)
        if z is not None:
            p.Velocity.Z = float(z)

    monkeypatch.setattr(core, "set_velocity", _write)
    slide.host_enter_juso(ctx, 2.2, 100.0, 1.0, 0.0)
    slide.host_apply_slide_jump(ctx, 800.0, 0.0, 600.0)
    assert ctx.key.player_id not in slide._HOST_SLIDES
    assert ctx.key.player_id in slide._HOST_JUMPS
    assert pawn.Physics == core.PHYS_FALLING
    assert pawn.bWantsToCrouch is False
    assert pawn.Velocity.X == pytest.approx(800.0)
    assert pawn.Velocity.Z == pytest.approx(600.0)
    pawn.Velocity.Z = 420.0
    slide._service_host_jumps(1.0 / 60.0)
    assert pawn.Velocity.Z == pytest.approx(420.0)
    assert pawn.Velocity.X == pytest.approx(800.0)
    pawn.Physics = core.PHYS_WALKING
    pawn.Velocity.Z = 0.0
    slide._service_host_jumps(1.0 / 60.0)
    assert pawn.Physics == core.PHYS_FALLING
    assert pawn.Velocity.Z == pytest.approx(600.0)


def test_requester_slide_jump_sends_launch(monkeypatch):
    """The joiner tells the host the slide-jump vector. A local-only launch rubber-bands."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.JumpZ = 600.0
    pc = _PC()
    ctx = PlayerContext(
        key=PlayerKey(1, 31),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=pc,
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    calls = []
    monkeypatch.setattr(slide, "jump_momentum_slider", SimpleNamespace(value=100))
    monkeypatch.setattr(slide, "jump_height_slider", SimpleNamespace(value=100))
    monkeypatch.setattr(slide.core, "phys", core.PHYS_WALKING)
    monkeypatch.setattr(slide.core, "clock", 10.0)
    monkeypatch.setattr(
        "Modern_Movement.coop_rpc.call_host",
        lambda fn, *args: calls.append((getattr(fn, "__name__", ""), args)),
    )

    def _write(p, x, y, z=None):
        p.Velocity.X = float(x)
        p.Velocity.Y = float(y)
        if z is not None:
            p.Velocity.Z = float(z)

    monkeypatch.setattr(core, "set_velocity", _write)

    def arm():
        slide._state().slide = {
            "dir": (1.0, 0.0),
            "speed": 800.0,
            "entry": 800.0,
            "start": 800.0,
            "timed": False,
        }
        slide._ground_jump(pc, pawn)

    core.execute(ctx, arm)
    jumps = [item for item in calls if item[0] == "server_slide_jump"]
    assert jumps
    assert jumps[0][1][0] == pytest.approx(800.0)
    assert jumps[0][1][1] == pytest.approx(0.0)
    assert jumps[0][1][2] == pytest.approx(600.0)
    assert any(item[0] == "server_slide_exit" for item in calls)


def test_requester_slide_ends_when_crouch_released(monkeypatch):
    """Releasing crouch cancels a joiner slide. It must not only run out on the timer."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(700.0, 0.0, 0.0)
    pawn.bWantsToCrouch = True
    pc = _PC()
    ctx = PlayerContext(
        key=PlayerKey(1, 12),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=pc,
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    monkeypatch.setattr(slide.core, "phys", core.PHYS_WALKING)
    monkeypatch.setattr(slide.core, "clock", 10.0)
    exits = []
    monkeypatch.setattr(
        "Modern_Movement.coop_rpc.call_host",
        lambda fn: exits.append(getattr(fn, "__name__", "exit")),
    )
    monkeypatch.setattr("Modern_Movement.coop_rpc.is_requester", lambda _ctx: True)

    def start():
        slide._start(ctx.controller, pawn, "test")

    core.execute(ctx, start)
    assert slide._state(ctx).slide is not None
    # The server crouch flag can drop before the host applies the slide. That is not a release.
    pc.bDuck = 0
    pawn.bWantsToCrouch = False
    pawn.bIsCrouched = False
    core.execute(ctx, slide._run, ctx.controller, pawn, 1.0 / 60.0)
    assert slide._state(ctx).slide is not None
    assert exits == []

    def release():
        slide._state().crouch_down = False
        slide._run(ctx.controller, pawn, 1.0 / 60.0)

    core.execute(ctx, release)
    assert slide._state(ctx).slide is None
    assert exits == ["server_slide_exit"]


def test_host_slide_ignores_missing_crouch(monkeypatch):
    """The host copy does not see joiner bDuck, so a clear crouch flag must not cancel it."""
    pawn = _Pawn(physics=core.PHYS_WALKING, crouch=2.2)
    pawn.Velocity = _Vec(700.0, 0.0, 0.0)
    pc = _PC()
    pc.bDuck = 0
    pawn.bWantsToCrouch = False
    pawn.bIsCrouched = False
    ctx = PlayerContext(
        key=PlayerKey(1, 13),
        role=ExecutionRole.REMOTE_AUTHORITY,
        controller=pc,
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    monkeypatch.setattr(slide.core, "phys", core.PHYS_WALKING)
    monkeypatch.setattr(slide.core, "clock", 10.0)
    slide.host_enter_juso(ctx, 2.2, 80.0, 1.0, 0.0)
    state = slide._state(ctx)
    state.slide = {
        "dir": (1.0, 0.0),
        "speed": 900.0,
        "start": 900.0,
        "entry": 700.0,
        "elapsed": 0.1,
        "last": (0.0, 0.0),
        "commanded": 0.0,
        "stalled": 0,
        "timed": True,
        "cp": 2.2,
        "old_z": 50.0,
        "distance": 80.0,
        "speed_percent": 100.0,
    }
    core.execute(ctx, slide._run, pc, pawn, 1.0 / 60.0)
    assert state.slide is not None
    assert ctx.key.player_id in slide._HOST_SLIDES


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
    assert pawn.CrouchedPct == pytest.approx(slide._JUSO_CROUCH_PCT)


def test_joiner_slide_meter_ignores_height_noise():
    """A single dropping sample used to refill CrouchedPct. One spike still only drains."""
    cp = 2.25
    for _ in range(30):
        nxt = slide._decay_juso_pct(cp, -4.0, 1.0 / 60.0)
        assert nxt < cp
        cp = nxt
    climbed = slide._decay_juso_pct(2.25, 40.0, 1.0 / 60.0)
    flat = slide._decay_juso_pct(2.25, 0.0, 1.0 / 60.0)
    assert climbed < flat < 2.25


def test_sustained_drop_stretches_the_slide_meter():
    """A ramp or a run of stairs slows the drain and opens the long cap. One spike does not."""
    store = {}
    for _ in range(10):
        run = slide._track_drop(store, -6.0, 1.0 / 60.0)
    assert run > 0.12
    flat = slide._decay_juso_pct(2.25, 0.0, 1.0 / 60.0)
    down = slide._decay_juso_pct(2.25, -6.0, 1.0 / 60.0, run)
    assert down > flat
    assert down < 2.25
    noise = {}
    for _ in range(10):
        slide._track_drop(noise, -1.0, 1.0 / 60.0)
        slide._track_drop(noise, 1.0, 1.0 / 60.0)
    assert noise["drop_run"] < 0.12


def test_slide_meter_never_refills_and_clears():
    from Modern_Movement import hudfx

    hudfx.slide_end()
    hudfx.slide_momentum(1.0)
    hudfx.slide_momentum(0.4)
    hudfx.slide_momentum(0.9)
    assert hudfx._slide_hud["v"] == pytest.approx(0.4)
    hudfx.slide_end()
    assert hudfx._slide_hud["on"] is False
    assert hudfx._slide_hud["v"] == pytest.approx(0.0)


def test_joiner_ground_dash_leaves_walking(monkeypatch):
    """A standing joiner dash must leave the ground. Walking was eating the burst."""
    dash._CLIENT_DASH = None
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Acceleration = _Vec(0.0, 0.0, 0.0)
    pc = _PC()
    ctx = PlayerContext(
        key=PlayerKey(1, 21),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=pc,
        pawn=pawn,
        clock=10.0,
        pawn_generation=1,
    )
    sent = []
    def _write(p, x, y, z=None):
        p.Velocity.X = float(x)
        p.Velocity.Y = float(y)
        p.Velocity.Z = float(p.Velocity.Z if z is None else z)

    monkeypatch.setattr(dash.core, "local_context", lambda: ctx)
    monkeypatch.setattr(dash.core, "set_velocity", _write)
    monkeypatch.setattr(dash.hudfx, "dash_arrows", lambda *_a, **_k: None)
    monkeypatch.setattr(dash.fx, "play_sound", lambda *_a, **_k: None)
    monkeypatch.setattr("Modern_Movement.coop_rpc.is_requester", lambda _ctx: True)
    monkeypatch.setattr(
        "Modern_Movement.coop_rpc.call_host",
        lambda fn, *args: sent.append((getattr(fn, "__name__", ""), args)),
    )
    dash._dash_request()
    assert pawn.Physics == core.PHYS_FALLING
    assert pawn.Velocity.X > 1000.0
    assert pawn.Velocity.Z > 0.0
    assert dash._CLIENT_DASH is not None
    assert dash._CLIENT_DASH["vz"] > 0.0
    assert sent and sent[0][0] == "server_dash"
    assert sent[0][1][2] > 0.0
    dash.host_apply_dash(ctx, *sent[0][1])
    assert pawn.Physics == core.PHYS_FALLING
    dash._service_host_dashes(1.0 / 60.0)
    assert pawn.Velocity.Z > 0.0


def test_joiner_dash_cooldown_fills_ready_hex(monkeypatch):
    """A joiner dash waits out the cooldown and the ready hex fills during that wait."""
    from Modern_Movement import hudfx

    dash._CLIENT_DASH = None
    dash.cooldown_slider.value = 2
    hudfx.pip_clear()
    pawn = _Pawn(physics=core.PHYS_FALLING)
    pc = _PC()
    ctx = PlayerContext(
        key=PlayerKey(1, 23),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=pc,
        pawn=pawn,
        clock=20.0,
        pawn_generation=1,
    )
    sent = []
    previous_clock = core.clock
    core.clock = 20.0
    monkeypatch.setattr(dash.core, "local_context", lambda: ctx)
    monkeypatch.setattr(dash.hudfx, "dash_arrows", lambda *_a, **_k: None)
    monkeypatch.setattr(dash.fx, "play_sound", lambda *_a, **_k: None)
    monkeypatch.setattr("Modern_Movement.coop_rpc.is_requester", lambda _ctx: True)
    monkeypatch.setattr(
        "Modern_Movement.coop_rpc.call_host",
        lambda fn, *args: sent.append(getattr(fn, "__name__", "")),
    )
    try:
        dash._dash_request()
        assert sent == ["server_dash"]
        dash._dash_request()
        assert sent == ["server_dash"]

        ctx.clock = 20.2
        core.execute(ctx, dash._service_client_dash, 1.0)
        assert dash._CLIENT_DASH is None
        assert dash._state(ctx).last_end == pytest.approx(20.2)

        core.clock = 21.0
        dash._dash_request()
        assert sent == ["server_dash"]

        ctx.clock = 21.0
        core.execute(ctx, dash._update_pip)
        assert hudfx._pip is not None
        assert hudfx._pip["p"] == pytest.approx((21.0 - 20.2) / 2.0, abs=0.02)

        dash._presentation("state", {"active": False, "cooldown_left": 0.0})
        assert hudfx._pip is not None
        assert "p" in hudfx._pip

        core.clock = 22.3
        dash._dash_request()
        assert sent == ["server_dash", "server_dash"]
    finally:
        core.clock = previous_clock
        dash._CLIENT_DASH = None
        hudfx.pip_clear()


def test_joining_client_with_authority_role_is_a_requester():
    """Willow clients report Role Authority. They still have to send movement to the listen host."""
    world = SimpleNamespace(NetMode=3)
    pc = SimpleNamespace(Role=3, WorldInfo=world)
    assert core._role_for(pc, pc) == ExecutionRole.LOCAL_REQUESTER

    host_world = SimpleNamespace(NetMode=2)
    host = SimpleNamespace(Role=3, WorldInfo=host_world)
    assert core._role_for(host, host) == ExecutionRole.LOCAL_HOST

    alone = SimpleNamespace(Role=3, WorldInfo=SimpleNamespace(NetMode=0))
    assert core._role_for(alone, alone) == ExecutionRole.LOCAL_STANDALONE


def test_bl2_lets_go_of_crouch_to_stop_sliding(monkeypatch):
    """Borderlands 2 keeps the crouch pose after a tap. Letting go of the key stops the slide."""
    monkeypatch.setattr(game, "is_bl2", lambda: True)
    monkeypatch.setattr(slide, "_crouch_held", lambda _pc: False)
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.bWantsToCrouch = True
    pawn.bIsCrouched = True
    pc = _PC()
    pc.bDuck = 1
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_HOST, 10.0, pawn)
    assert ctx is not None
    try:
        state = slide._state(ctx)
        state.slide = {
            "dir": (1.0, 0.0),
            "speed": 700.0,
            "entry": 500.0,
            "fresh_until": -1.0,
            "stick": False,
        }
        state.crouch_down = True
        state.ignore_release_until = 0.0
        state.hit_at = -100.0
        core.execute(ctx, slide._run, pc, pawn, 0.05)
        assert state.slide is None
    finally:
        REGISTRY.retire(ctx, "test")


def test_bl2_slide_does_not_wait_for_a_sprint_ground_speed():
    state = slide.SlideState()
    pawn = _Pawn(physics=core.PHYS_WALKING, ground=900.0)
    assert slide._bl2_slide_ready(state, pawn, False, 200.0) is False
    assert slide._bl2_slide_ready(state, pawn, True, 200.0) is True
    assert slide._bl2_slide_ready(state, pawn, False, 600.0) is True


def test_slide_jump_chains_only_while_crouch_is_held(monkeypatch):
    """A crouch release cancels the landing slide. The slide pose is not a hold."""
    state = slide.SlideState()
    previous = core.clock
    core.clock = 10.0
    try:
        monkeypatch.setattr(slide, "_crouch_held", lambda _pc: False)
        state.crouch_down = True
        assert slide._wants_chain(state, None) is False
        slide._remember_slide_jump(state, True, 1.0, 0.0, 800.0)
        assert state.chain is not None
        slide._update_chain_hold(state, False)
        assert state.chain is None
        assert state.chain_hold is False
        assert state.crouch_down is False

        monkeypatch.setattr(slide, "_crouch_held", lambda _pc: None)
        state.crouch_down = True
        state.chain_hold = True
        slide._remember_slide_jump(state, True, 1.0, 0.0, 800.0)
        slide._update_chain_hold(state, None)
        assert state.chain is not None
        assert slide._wants_chain(state, None) is False

        monkeypatch.setattr(slide, "_crouch_held", lambda _pc: True)
        assert slide._wants_chain(state, None) is True
        slide._update_chain_hold(state, True)
        assert state.chain is not None
        assert state.crouch_down is True
    finally:
        core.clock = previous


def test_sprint_jump_held_crouch_slides_on_landing(monkeypatch):
    """Sprint, jump, hold crouch, land: slide. No slide before the jump, and the landing option stays off."""
    pawn = _Pawn(physics=core.PHYS_FALLING)
    pawn.Velocity = _Vec(900.0, 0.0, 400.0)
    pc = _PC()
    pc.bDuck = 0
    held = {"down": True}
    monkeypatch.setattr(slide, "_crouch_held", lambda _pc: held["down"])
    monkeypatch.setattr(slide, "landing_option", SimpleNamespace(value=False))
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 10.0, pawn)
    try:
        slide._state(ctx).air_pressed = True
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert slide._state(ctx).air_slide is not None
        assert slide._state(ctx).slide is None
        assert slide._state(ctx).slide_jump is None
        pawn.Physics = core.PHYS_WALKING
        pawn.bWantsToCrouch = False
        pawn.bIsCrouched = False
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert slide._state(ctx).slide is not None
        pawn.bWantsToCrouch = False
        pawn.bIsCrouched = False
        pc.bDuck = 0
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert slide._state(ctx).slide is not None
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_landing_slide_follows_facing_not_the_old_slide(monkeypatch):
    """Turning around in the air slides the way you are looking, and the old momentum does not cancel it."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(0.0, 0.0, 40.0)
    pawn.Acceleration = _Vec(2000.0, 0.0, 0.0)
    pc = _PC()
    pc.Rotation.Yaw = 32768
    monkeypatch.setattr(slide, "_crouch_held", lambda _pc: True)
    monkeypatch.setattr(slide, "back_cancel_option", SimpleNamespace(value=True))
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 12.0, pawn)
    try:
        started = core.execute(ctx, slide.offer_landing, pc, pawn, 1.0, 0.0, 900.0, "slide cancel")
        assert started is True
        direction = slide._state(ctx).slide["dir"]
        assert direction[0] < -0.9
        assert abs(direction[1]) < 0.1
        assert pawn.Velocity.X < -100.0
        assert pawn.Velocity.Z <= 0.0
        for _ in range(5):
            pawn.Location.X += 40.0
            pawn.Physics = core.PHYS_FALLING
            pawn.Acceleration = _Vec(2000.0, 0.0, 0.0)
            core.execute(ctx, slide._run, pc, pawn, 1.0 / 60.0)
            assert slide._state(ctx).slide is not None
            assert slide._state(ctx).slide["dir"][0] < -0.9
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_air_crouch_does_not_slide_when_the_key_is_up(monkeypatch):
    """Letting go before a sprint jump lands does not slide. A slide jump stays on its own chain."""
    pawn = _Pawn(physics=core.PHYS_FALLING)
    pawn.Velocity = _Vec(900.0, 0.0, 400.0)
    pc = _PC()
    pc.bDuck = 0
    held = {"down": True}
    monkeypatch.setattr(slide, "_crouch_held", lambda _pc: held["down"])
    monkeypatch.setattr(slide, "landing_option", SimpleNamespace(value=False))
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 10.0, pawn)
    try:
        slide._state(ctx).air_pressed = True
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert slide._state(ctx).air_slide is not None
        held["down"] = False
        slide._state(ctx).crouch_down = False
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert slide._state(ctx).air_slide is None
        pawn.Physics = core.PHYS_WALKING
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert slide._state(ctx).slide is None

        pawn.Physics = core.PHYS_WALKING
        state = slide._state(ctx)
        state.prev_phys = core.PHYS_FALLING
        state.slide_jump = {"dir": (1.0, 0.0), "speed": 800.0, "at": 0.0}
        state.air_slide = {"dir": (1.0, 0.0), "speed": 900.0}
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert state.slide is None
        assert state.air_slide is None
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_slide_cancel_lands_only_while_the_key_is_down(monkeypatch):
    """Letting go before landing does not slide. Holding crouch still does."""
    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(900.0, 0.0, 0.0)
    pawn.bWantsToCrouch = False
    pawn.bIsCrouched = False
    pc = _PC()
    pc.bDuck = 0
    held = {"down": False}
    monkeypatch.setattr(slide, "_crouch_held", lambda _pc: held["down"])
    monkeypatch.setattr(slide, "landing_option", SimpleNamespace(value=False))
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 10.0, pawn)
    try:
        state = slide._state(ctx)
        state.crouch_down = True
        state.slide_jump = {"dir": (1.0, 0.0), "speed": 800.0, "at": 9.0}
        state.chain = {"dir": (1.0, 0.0), "speed": 800.0, "at": 9.0}
        state.chain_hold = True
        state.chain_was_air = True
        state.prev_phys = core.PHYS_FALLING
        state.prev_crouch = True
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert slide._state(ctx).slide is None
        held["down"] = True
        state = slide._state(ctx)
        state.crouch_down = True
        state.slide_jump = {"dir": (1.0, 0.0), "speed": 800.0, "at": 9.0}
        state.chain = {"dir": (1.0, 0.0), "speed": 800.0, "at": 9.0}
        state.chain_hold = True
        state.chain_was_air = True
        state.prev_phys = core.PHYS_FALLING
        state.slide = None
        core.execute(ctx, slide._tick, pc, pawn, 1.0 / 60.0)
        assert slide._state(ctx).slide is not None
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_pressing_crouch_during_a_slide_does_not_start_another():
    """A second crouch press while sliding is ignored. The gun tilt belongs to one slide."""
    from unrealsdk.hooks import Block

    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(900.0, 0.0, 0.0)
    pc = _PC()
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 10.0, pawn)
    try:
        core.execute(ctx, slide._start, pc, pawn, "crouch while sprinting")
        assert slide._state(ctx).slide is not None
        assert slide._pre_duck_pressed(pc, None, None, None) is Block
        assert slide._state(ctx).slide is not None
        core.execute(ctx, slide._start, pc, pawn, "crouch while sprinting")
        assert slide._state(ctx).slide["entry"] != 0.0
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_a_finished_slide_does_not_block_the_next_press():
    """Letting go, then pressing crouch again, starts another slide. A later press is never swallowed."""

    pawn = _Pawn(physics=core.PHYS_WALKING)
    pawn.Velocity = _Vec(900.0, 0.0, 0.0)
    pc = _PC()
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 10.0, pawn)
    try:
        core.execute(ctx, slide._start, pc, pawn, "crouch while sprinting")
        state = slide._state(ctx)
        state.crouch_down = False
        core.execute(ctx, slide._end, pawn, "timed out", pc)
        assert state.slide is None
        assert state.suppress_crouch_until_release is False
        assert slide._pre_duck_pressed(pc, None, None, None) is None
        assert state.crouch_down is True

        core.execute(ctx, slide._start, pc, pawn, "crouch while sprinting")
        core.execute(ctx, slide._end, pawn, "timed out", pc)
        assert state.suppress_crouch_until_release is False
        assert slide._pre_duck_pressed(pc, None, None, None) is None
        assert state.suppress_crouch_until_release is False
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_downhill_keeps_slide_speed():
    """A ramp stretches the slide and keeps it fast. Flat ground over the same time bleeds off."""

    def coast(drop: float) -> float:
        pawn = _Pawn(physics=core.PHYS_WALKING)
        pawn.Velocity = _Vec(900.0, 0.0, 0.0)
        pc = _PC()
        slide.slope_slider.value = 250
        ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 10.0, pawn)
        try:
            core.execute(ctx, slide._start, pc, pawn, "crouch while sprinting")
            for _ in range(40):
                pawn.Location.X += 40.0
                pawn.Location.Z -= drop
                core.execute(ctx, slide._run, pc, pawn, 1.0 / 60.0)
            state = slide._state(ctx)
            assert state.slide is not None
            return float(state.slide["speed"])
        finally:
            REGISTRY.retire(ctx, "test")
            core.busy = None

    assert coast(8.0) > coast(0.0) + 200.0


def test_air_slide_does_not_start_while_still_falling(monkeypatch):
    """Leaving a slide in the air does not immediately start another one."""
    pawn = _Pawn(physics=core.PHYS_FALLING)
    pawn.Velocity = _Vec(900.0, 0.0, -200.0)
    pc = _PC()
    monkeypatch.setattr(slide, "_crouch_held", lambda _pc: True)
    ctx = REGISTRY.observe(pc, ExecutionRole.LOCAL_STANDALONE, 10.0, pawn)
    try:
        state = slide._state(ctx)
        state.crouch_down = True
        state.air_slide = {"dir": (1.0, 0.0), "speed": 900.0}
        state.suppress_crouch_until_release = True
        core.execute(ctx, slide._air_crouch_landing, state, pc, pawn)
        assert state.slide is None
    finally:
        REGISTRY.retire(ctx, "test")
        core.busy = None


def test_crouch_key_reads_down_and_up(monkeypatch):
    from Modern_Movement.features import slam

    monkeypatch.setattr(game, "_cached", "UNSUPPORTED")
    binding = SimpleNamespace(Name="C", Command="Duck")
    pc = SimpleNamespace(PlayerInput=SimpleNamespace(Bindings=[binding], PressedKeys=["C"]))
    saved = (slam._crouch_keys, slam._keys_at)
    slam._crouch_keys = ()
    slam._keys_at = -100.0
    try:
        assert slam._crouch_key_down(pc) is True
        pc.PlayerInput.PressedKeys = []
        assert slam._crouch_key_down(pc) is False
        pc.PlayerInput.Bindings = []
        slam._crouch_keys = ()
        assert slam._crouch_key_down(pc) is None
        pc.PlayerInput.Bindings = [binding]
        pc.PlayerInput.PressedKeys = [SimpleNamespace(Name="C")]
        assert slam._crouch_key_down(pc) is True
    finally:
        slam._crouch_keys, slam._keys_at = saved


def test_host_rpc_finds_pawn_when_controller_pawn_is_empty(monkeypatch):
    """Listen-host Controller.Pawn is often empty. The world pawn list still has them."""
    from Modern_Movement import coop_rpc

    pawn = _Pawn(physics=core.PHYS_WALKING)
    pc = _PC()
    pc.PlayerReplicationInfo = SimpleNamespace(PlayerID=9)
    pri = SimpleNamespace(PlayerID=9, Owner=pc)
    fn = SimpleNamespace(sender=pri)
    pawn.Controller = pc
    monkeypatch.setattr(coop_rpc, "_walk_pawns", lambda pid: pawn if pid == 9 else None)
    assert coop_rpc._sender_pc(fn) is pc
    ctx = coop_rpc._host_context(pc)
    try:
        assert ctx is not None
        assert ctx.pawn is pawn
        assert ctx.key.player_id == 9
    finally:
        if ctx is not None:
            REGISTRY.retire(ctx, "test")
