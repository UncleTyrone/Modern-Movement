"""Player-scoped runtime identity and lifecycle for authoritative co-op movement.

This module deliberately has no dependency on mods_base or unrealsdk so it can be tested in a
normal Python interpreter. Unreal objects are owned only by a live PlayerContext and are discarded
whenever the world, controller, or pawn generation changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


AUTHORITY_ROLE = 3


class ExecutionRole(str, Enum):
    LOCAL_STANDALONE = "local_standalone"
    LOCAL_HOST = "local_host"
    LOCAL_REQUESTER = "local_requester"
    REMOTE_AUTHORITY = "remote_authority"

    @property
    def authority(self) -> bool:
        # Hybrid co-op: joining clients write locally for feel/HUD, and the listen host also
        # writes the matching server-side pawn (REMOTE_AUTHORITY) so moves are not rubber-banded.
        return self in (
            self.LOCAL_STANDALONE,
            self.LOCAL_HOST,
            self.LOCAL_REQUESTER,
            self.REMOTE_AUTHORITY,
        )

    @property
    def local(self) -> bool:
        return self in (self.LOCAL_STANDALONE, self.LOCAL_HOST, self.LOCAL_REQUESTER)

    @property
    def presentation(self) -> bool:
        return self.local


@dataclass(frozen=True)
class PlayerKey:
    world_epoch: int
    player_id: int


@dataclass(frozen=True)
class PawnKey:
    player: PlayerKey
    generation: int


@dataclass
class TickFrame:
    now: float
    dt: float
    phys_at_start: int
    world_epoch: int


@dataclass
class NumericLease:
    """Compare-and-swap ownership of one numeric Unreal property."""

    pawn_key: PawnKey | None = None
    base: float | None = None
    written: float | None = None

    def clear(self) -> None:
        self.pawn_key = None
        self.base = None
        self.written = None

    def adopt(self, pawn_key: PawnKey, current: float) -> None:
        if self.pawn_key != pawn_key or self.written is None or abs(current - self.written) > 0.5:
            self.pawn_key = pawn_key
            self.base = current
            self.written = None

    def can_restore(self, pawn_key: PawnKey, current: float, tolerance: float = 0.5) -> bool:
        return (
            self.pawn_key == pawn_key
            and self.base is not None
            and self.written is not None
            and abs(current - self.written) <= tolerance
        )


@dataclass
class PlayerContext:
    key: PlayerKey
    role: ExecutionRole
    controller: Any
    peer_token: str = ""
    clock: float = 0.0
    pawn_generation: int = 0
    pawn: Any = None
    pawn_identity: int | str | None = None
    busy: str | None = None
    last_ground_press: float = -100.0
    speed_multipliers: dict[str, float] = field(default_factory=dict)
    ground_speed: NumericLease = field(default_factory=NumericLease)
    feature_state: dict[str, Any] = field(default_factory=dict)
    warned: set[str] = field(default_factory=set)
    input_state: Any = None
    action_revision: int = 0
    detached: bool = False

    @property
    def pawn_key(self) -> PawnKey | None:
        if self.pawn is None:
            return None
        return PawnKey(self.key, self.pawn_generation)

    @property
    def authority(self) -> bool:
        return self.role.authority

    @property
    def local(self) -> bool:
        return self.role.local

    @property
    def presentation(self) -> bool:
        return self.role.presentation

    def state(self, name: str, factory: Callable[[], Any]) -> Any:
        if name not in self.feature_state:
            self.feature_state[name] = factory()
        return self.feature_state[name]

    def require_authority(self, operation: str) -> None:
        if not self.authority:
            raise PermissionError(f"{operation} requires host authority ({self.role.value})")


def object_identity(obj: Any) -> int | str | None:
    if obj is None:
        return None
    try:
        return int(obj._get_address())
    except Exception:
        pass
    try:
        return str(obj.PathName(obj))
    except Exception:
        return id(obj)


def player_id(pc: Any) -> int | None:
    try:
        return int(pc.PlayerReplicationInfo.PlayerID)
    except Exception:
        return None


def is_authority(pc: Any) -> bool:
    try:
        return int(pc.Role) == AUTHORITY_ROLE
    except Exception:
        return False


class ContextRegistry:
    def __init__(self) -> None:
        self.world_epoch = 0
        self._world_identity: int | str | None = None
        self._contexts: dict[PlayerKey, PlayerContext] = {}
        self._by_controller: dict[int | str, PlayerContext] = {}
        self._by_pawn: dict[int | str, PlayerContext] = {}
        self._detach_callbacks: list[Callable[[PlayerContext, Any, str], None]] = []

    def add_detach_callback(self, callback: Callable[[PlayerContext, Any, str], None]) -> None:
        if callback not in self._detach_callbacks:
            self._detach_callbacks.append(callback)

    def observe_world(self, world: Any) -> bool:
        identity = object_identity(world)
        if identity == self._world_identity:
            return False
        if self._world_identity is not None:
            self.clear("world_changed")
        self._world_identity = identity
        self.world_epoch += 1
        return True

    def observe(
        self,
        pc: Any,
        role: ExecutionRole,
        now: float,
        pawn: Any = None,
    ) -> PlayerContext | None:
        pid = player_id(pc)
        if pid is None:
            return None
        key = PlayerKey(self.world_epoch, pid)
        ctx = self._contexts.get(key)
        controller_identity = object_identity(pc)
        if ctx is None:
            ctx = PlayerContext(key=key, role=role, controller=pc, clock=now)
            self._contexts[key] = ctx
        else:
            old_controller_identity = object_identity(ctx.controller)
            if old_controller_identity != controller_identity:
                self._by_controller.pop(old_controller_identity, None)
                self._detach_pawn(ctx, "controller_replaced")
                ctx.controller = pc
            ctx.role = role
            ctx.clock = now
            ctx.detached = False
        self._by_controller[controller_identity] = ctx

        if pawn is None:
            try:
                pawn = pc.Pawn
            except Exception:
                pawn = None
        identity = object_identity(pawn)
        if identity != ctx.pawn_identity:
            self._detach_pawn(ctx, "pawn_replaced")
            ctx.pawn_generation += 1
            ctx.pawn = pawn
            ctx.pawn_identity = identity
            ctx.busy = None
            ctx.last_ground_press = -100.0
            ctx.feature_state.clear()
            ctx.speed_multipliers.clear()
            ctx.ground_speed.clear()
            if identity is not None:
                self._by_pawn[identity] = ctx
        return ctx

    def resolve_controller(self, pc: Any) -> PlayerContext | None:
        return self._by_controller.get(object_identity(pc))

    def resolve_pawn(self, pawn: Any) -> PlayerContext | None:
        return self._by_pawn.get(object_identity(pawn))

    def contexts(self) -> tuple[PlayerContext, ...]:
        return tuple(self._contexts.values())

    def retire_missing(self, player_ids: set[int]) -> None:
        for key, ctx in list(self._contexts.items()):
            if key.player_id not in player_ids:
                self.retire(ctx, "player_left")

    def retire(self, ctx: PlayerContext, reason: str) -> None:
        self._detach_pawn(ctx, reason)
        self._by_controller.pop(object_identity(ctx.controller), None)
        self._contexts.pop(ctx.key, None)
        ctx.detached = True

    def clear(self, reason: str) -> None:
        for ctx in list(self._contexts.values()):
            self.retire(ctx, reason)
        self._contexts.clear()
        self._by_controller.clear()
        self._by_pawn.clear()

    def _detach_pawn(self, ctx: PlayerContext, reason: str) -> None:
        pawn = ctx.pawn
        if pawn is not None:
            for callback in tuple(self._detach_callbacks):
                try:
                    callback(ctx, pawn, reason)
                except Exception:
                    pass
        self._by_pawn.pop(ctx.pawn_identity, None)
        ctx.pawn = None
        ctx.pawn_identity = None
        ctx.busy = None
        ctx.speed_multipliers.clear()
        ctx.ground_speed.clear()
        ctx.feature_state.clear()


REGISTRY = ContextRegistry()
