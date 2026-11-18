from __future__ import annotations

import math

from Modern_Movement.gravity import (
    DEFAULT_GRAVITY,
    GravityState,
    ballistic_vertical_speed,
    clearance_vertical_speed,
)


def test_gravity_median_after_samples():
    state = GravityState()
    vz = 0.0
    for _ in range(16):
        state.observe(vz, 0.1, falling=True, signature="moon")
        vz -= 100.0 * 0.1
    assert len(state.samples) >= 12
    measured = state.value(None)
    assert math.isclose(measured, 100.0, rel_tol=1e-6)


def test_bl2_gravity_floor_is_original(monkeypatch):
    from Modern_Movement import game, gravity

    monkeypatch.setattr(game, "_cached", "BL2")
    assert gravity.measured_bounds() == (300.0, gravity.MAX_GRAVITY)
    monkeypatch.setattr(game, "_cached", "TPS")
    assert gravity.measured_bounds()[0] == 60.0


def test_gravity_fallback_default():
    state = GravityState()
    assert state.value(None) == DEFAULT_GRAVITY


def test_ballistic_helpers():
    vz = ballistic_vertical_speed(delta_z=100.0, flight_time=1.0, gravity=1000.0)
    assert vz > 0
    assert math.isclose(clearance_vertical_speed(2.0, 100.0), math.sqrt(400.0))