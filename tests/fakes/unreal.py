from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeVector:
    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0


@dataclass
class FakePRI:
    PlayerID: int = 1
    bIsPartyLeader: bool = False


@dataclass
class FakePawn:
    _id: int
    Velocity: FakeVector = field(default_factory=FakeVector)
    Physics: int = 1
    Health: float = 100.0
    bWantsToCrouch: bool = False
    bIsCrouched: bool = False
    bIsSprinting: bool = False
    GroundSpeed: float = 500.0

    def _get_address(self) -> int:
        return self._id


@dataclass
class FakeController:
    _id: int
    Role: int = 3
    PlayerReplicationInfo: FakePRI = field(default_factory=FakePRI)
    Pawn: FakePawn | None = None
    bDuck: bool = False
    WorldInfo: Any = None

    def _get_address(self) -> int:
        return self._id

    def IsLocalPlayerController(self) -> bool:
        return self.Role == 3

    def PathName(self, obj: Any) -> str:  # noqa: N802
        return f"Fake.{type(obj).__name__}.{getattr(obj, '_id', id(obj))}"


@dataclass
class FakeWorld:
    _id: int = 1
    NetMode: int = 1

    def _get_address(self) -> int:
        return self._id


def bind_controller(pc: FakeController, pawn: FakePawn | None = None) -> FakeController:
    pc.Pawn = pawn
    if pawn is not None:
        pawn.Physics = pawn.Physics
    pc.WorldInfo = FakeWorld()
    return pc