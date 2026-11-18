"""Per-pawn gravity observation for TPS low-gravity movement."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import isfinite, sqrt

DEFAULT_GRAVITY = 1050.0
MAX_GRAVITY = 6000.0
TRUSTED_SAMPLES = 12
KEPT_SAMPLES = 60
# This package is TPS-only; accept moon/low-gravity samples down to 60 (BL2 used 300).
_TPS_MEASURED_MIN = 60.0


def measured_bounds() -> tuple[float, float]:
    """Valid range for gravity inferred from falling (jump pads / landings are outside this)."""
    return _TPS_MEASURED_MIN, MAX_GRAVITY


def world_gravity_z(pc) -> float | None:
    try:
        if pc is None:
            return None
        raw = float(pc.WorldInfo.WorldGravityZ)
        if not isfinite(raw):
            return None
        return raw
    except Exception:  # noqa: BLE001
        return None


@dataclass
class GravityState:
    signature: str = ""
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=KEPT_SAMPLES))
    previous_vz: float | None = None

    def reset(self, signature: str = "") -> None:
        """Drop samples when the pawn identity changes."""
        self.signature = signature
        self.samples.clear()
        self.previous_vz = None

    def invalidate(self) -> None:
        self.samples.clear()
        self.previous_vz = None

    def observe(self, vz: float, dt: float, falling: bool, signature: str = "") -> None:
        if signature != self.signature:
            self.reset(signature)
        if not falling or dt <= 0.0 or not isfinite(vz):
            self.previous_vz = None
            return
        if self.previous_vz is not None:
            measured = -(vz - self.previous_vz) / dt
            low, high = measured_bounds()
            if low <= measured <= high and isfinite(measured):
                self.samples.append(measured)
        self.previous_vz = vz

    def value(self, world_gravity: float | None) -> float:
        if len(self.samples) >= TRUSTED_SAMPLES:
            values = sorted(self.samples)
            middle = len(values) // 2
            if len(values) % 2:
                return values[middle]
            return 0.5 * (values[middle - 1] + values[middle])
        if world_gravity is not None:
            direct = abs(float(world_gravity))
            if isfinite(direct) and 0.0 < direct <= MAX_GRAVITY:
                return direct
        return DEFAULT_GRAVITY


def gravity_for(pc, state: GravityState) -> float:
    """Gravity for gameplay math on this pawn."""
    return state.value(world_gravity_z(pc))


def ballistic_vertical_speed(delta_z: float, flight_time: float, gravity: float) -> float:
    if flight_time <= 0.0:
        return 0.0
    gravity = max(0.0, gravity)
    return delta_z / flight_time + 0.5 * gravity * flight_time


def clearance_vertical_speed(clearance: float, gravity: float) -> float:
    if clearance <= 0.0 or gravity <= 0.0:
        return 0.0
    return sqrt(2.0 * gravity * clearance)