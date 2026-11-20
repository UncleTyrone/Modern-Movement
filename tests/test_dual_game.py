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
    pc = SimpleNamespace(
        bDuck=0,
        Pawn=pawn,
        PlayerInput=SimpleNamespace(PressedKeys=[], Bindings=[]),
        PlayerReplicationInfo=SimpleNamespace(PlayerID=4),
    )
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


def test_slam_landing_does_not_become_a_slide(monkeypatch):
    """The crouch that started the slam plays the landing. It does not turn into a slide."""
    from Modern_Movement.features import slide
    from Modern_Movement.runtime import REGISTRY

    monkeypatch.setattr(game, "_cached", "BL2")
    monkeypatch.setattr(slam, "_crouch_key_down", lambda _pc: True)
    ctx = _ctx()
    observed = REGISTRY.observe(ctx.controller, ctx.role, 10.0, ctx.pawn)
    try:
        def run():
            slam._start(observed.controller, observed.pawn)
            slam._impact(observed.controller, observed.pawn)

        core.execute(observed, run)
        assert slam._slam is None
        assert slide._state(observed).slide is None
        assert slide._state(observed).slam_hold is False
        assert observed.pawn.Velocity.X == pytest.approx(0.0)
    finally:
        REGISTRY.retire(observed, "test")
        slam._SLAM_CARRY = None


def test_slide_bar_follows_the_slide_clock():
    from Modern_Movement.features import slide

    assert slide._slide_fill(0.0, 1.0, 900.0, 900.0, 200.0) == pytest.approx(1.0)
    assert slide._slide_fill(0.5, 1.0, 900.0, 900.0, 200.0) == pytest.approx(0.5)
    assert slide._slide_fill(1.0, 1.0, 900.0, 900.0, 200.0) == pytest.approx(0.0)
    assert slide._slide_fill(0.2, 1.0, 200.0, 900.0, 200.0) == pytest.approx(0.0)


def test_physical_crouch_hold_counts_when_the_game_omits_the_key():
    assert slam._vk_for("c") == 0x43
    assert slam._vk_for("LeftControl") == 0xA2
    assert slam._combine_key(True, False, False) is True
    assert slam._combine_key(False, False, False) is False
    assert slam._combine_key(None, None, True) is True
    assert slam._combine_key(None, None, None) is None


def test_sprint_press_after_release_ends_the_slide():
    from Modern_Movement.features import slide

    active = {"fresh_until": -1.0}
    assert slide._sprint_press_is_cancel(active, True, True) is False
    active["sprint_released"] = True
    assert slide._sprint_press_is_cancel(active, True, True) is True
    assert slide._sprint_press_is_cancel(active, True, False) is False
    assert slide._sprint_press_is_cancel({"fresh_until": slide.core.clock + 5.0, "sprint_released": True}, True, True) is False
    assert slide._sprint_press_is_cancel(active, False, None) is True


def test_slam_hold_is_only_the_crouch_key():
    slam._hold_latch = True
    assert slam._slam_hold(None, True, False) is False
    assert slam._hold_latch is False
    assert slam._slam_hold(None, True, None) is False
    assert slam._slam_hold(None, False, True) is True


def test_a_crouch_on_the_ground_is_not_high_enough_to_slam():
    slam._takeoff_feet = 100.0
    assert slam._clear_of_last_ground(110.0) is False
    assert slam._clear_of_last_ground(100.0) is False
    assert slam._clear_of_last_ground(100.0 + slam._SLAM_FLOOR) is True
    assert slam._clear_of_last_ground(100.0 - slam._SLAM_FLOOR) is True
    slam._takeoff_feet = None
    assert slam._clear_of_last_ground(400.0) is False


def test_landing_camera_stays_out_of_the_floor():
    assert slam._impact_eye(-1.0, 2.0) >= -slam._HIT_EYE_LIMIT
    assert slam._impact_eye(1.0, 2.0) <= slam._HIT_EYE_LIMIT
    assert slam._HIT_DIP == 0.0


def test_a_crouch_dip_is_not_the_end_of_a_slide():
    from Modern_Movement.features import slide

    assert slide._falling_is_crouch_dip(0.0, True) is True
    assert slide._falling_is_crouch_dip(-40.0, True) is True
    assert slide._falling_is_crouch_dip(800.0, True) is False
    assert slide._falling_is_crouch_dip(0.0, False) is False


def test_a_crouch_dip_on_the_ground_still_counts_as_ground():
    from types import SimpleNamespace

    from Modern_Movement.features import slide

    pawn = SimpleNamespace(Velocity=SimpleNamespace(Z=0.0))
    state = SimpleNamespace(prev_phys=slide.core.PHYS_WALKING, slide=None)
    assert slide._crouch_blip_on_ground(state, pawn, slide.core.PHYS_FALLING) is True
    pawn.Velocity.Z = 700.0
    assert slide._crouch_blip_on_ground(state, pawn, slide.core.PHYS_FALLING) is False
    assert slide._crouch_blip_on_ground(state, pawn, slide.core.PHYS_WALKING) is False


def test_short_hop_pulls_and_full_height_slams():
    assert slam._slam_kind(30.0, 300.0, -400.0) is None
    assert slam._slam_kind(80.0, 300.0, 500.0) is None
    assert slam._slam_kind(80.0, 300.0, -50.0) is None
    assert slam._slam_kind(140.0, 300.0, 200.0) == "pull"
    assert slam._slam_kind(300.0, 300.0, 400.0) == "full"
    assert slam._slam_kind(900.0, 300.0, -800.0) == "full"


def test_chain_landing_rejects_a_tap_and_accepts_a_real_jump():
    from Modern_Movement.features import slide

    previous = slide.core.clock
    try:
        slide.core.clock = 20.0
        assert slide._chain_air_ok({"at": 20.0}) is False
        assert slide._chain_air_ok({"at": 20.0 - slide._CHAIN_MIN_AIR + 0.05}) is False
        assert slide._chain_air_ok({"at": 20.0 - slide._CHAIN_MIN_AIR - 0.01}) is True
    finally:
        slide.core.clock = previous


def test_slide_jump_hold_blocks_slam_press():
    """The crouch held through a slide jump is not a new slam press."""
    from Modern_Movement.features import slide
    from Modern_Movement.runtime import REGISTRY
    from unrealsdk.hooks import Block

    ctx = _ctx()
    ctx.pawn.Physics = core.PHYS_FALLING
    observed = REGISTRY.observe(ctx.controller, ctx.role, 10.0, ctx.pawn)
    try:
        slide._state(observed).chain = {"dir": (1.0, 0.0), "speed": 800.0}
        assert slide._pre_duck_pressed(ctx.controller, None, None, None) is Block
        assert slide._state(observed).slam_bank is None
    finally:
        REGISTRY.retire(observed, "test")


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
