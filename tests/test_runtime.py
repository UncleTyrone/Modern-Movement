from __future__ import annotations

from Modern_Movement.runtime import (
    ContextRegistry,
    ExecutionRole,
    NumericLease,
    PawnKey,
    PlayerKey,
)

from tests.fakes.unreal import FakeController, FakePawn, FakePRI, bind_controller


def test_numeric_lease_adopt_and_restore():
    lease = NumericLease()
    key = PawnKey(PlayerKey(1, 9), 2)
    lease.adopt(key, 400.0)
    lease.written = 450.0
    assert lease.can_restore(key, 450.0)
    assert not lease.can_restore(key, 200.0)


def test_registry_pawn_replacement_increments_generation():
    reg = ContextRegistry()
    world = object()
    reg.observe_world(world)
    pawn_a = FakePawn(_id=10)
    pawn_b = FakePawn(_id=11)
    pc = bind_controller(FakeController(_id=1, PlayerReplicationInfo=FakePRI(PlayerID=5)))
    ctx = reg.observe(pc, ExecutionRole.LOCAL_HOST, 0.0, pawn_a)
    assert ctx is not None
    first_gen = ctx.pawn_generation
    reg.observe(pc, ExecutionRole.LOCAL_HOST, 0.1, pawn_b)
    assert ctx.pawn_generation == first_gen + 1
    assert ctx.ground_speed.base is None


def test_execution_role_flags():
    host = ExecutionRole.LOCAL_HOST
    requester = ExecutionRole.LOCAL_REQUESTER
    remote = ExecutionRole.REMOTE_AUTHORITY
    assert host.authority and host.presentation
    # Clients write locally; host also writes REMOTE_AUTHORITY so mirrored moves stick.
    assert requester.local and requester.authority and requester.presentation
    assert remote.authority and not remote.local
