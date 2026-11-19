"""Host RPCs for Willow co-op (Eternal dash hold, slide coast, double jump, surge, mantle, BL2 slam).

Joiners predict locally and call @host. The listen host writes the same values on
sender.Owner.Pawn. A client-only Velocity write rubber-bands; a host-only write often
lands after the move is already over, so dash, double jump, and slide coast on both sides.
"""

from __future__ import annotations

from typing import Any

from unrealsdk import logging

from . import authority, core, diagnostics
from .protocol import Reason
from .runtime import ExecutionRole, REGISTRY

_NETWORKING = False
try:
    from networking.decorators import host

    _NETWORKING = True
except Exception:  # noqa: BLE001

    class _Stub:
        def json_message(self, fn=None):  # noqa: ANN001
            def wrap(target):
                return target

            return wrap if fn is None else wrap(fn)

        def message(self, fn=None):  # noqa: ANN001
            def wrap(target):
                return target

            return wrap if fn is None else wrap(fn)

    host = _Stub()


def _log(msg: str) -> None:
    logging.info(f"[Modern Movement] coop_rpc: {msg}")


def _sender_pc(fn) -> Any:
    try:
        return fn.sender.Owner
    except Exception:
        return None


def _host_context(pc) -> Any:
    if pc is None:
        return None
    ctx = REGISTRY.resolve_controller(pc)
    if ctx is not None:
        return ctx
    try:
        pawn = pc.Pawn
    except Exception:
        pawn = None
    try:
        now = float(pc.WorldInfo.TimeSeconds)
    except Exception:
        now = 0.0
    return REGISTRY.observe(pc, ExecutionRole.REMOTE_AUTHORITY, now, pawn)


@host.json_message
def server_dash(dx: float, dy: float, vz: float = 0.0) -> None:
    """Eternal-style: host writes a full Velocity vector on sender.Owner every dash tick."""
    pc = _sender_pc(server_dash)
    ctx = _host_context(pc)
    if ctx is None or ctx.pawn is None:
        diagnostics.event("mm.rpc.dash", result="no_pawn")
        return
    from .features import dash

    try:
        dash.host_apply_dash(ctx, float(dx), float(dy), float(vz))
        diagnostics.event("mm.rpc.dash", result="ok", player=ctx.key.player_id)
    except Exception as exc:  # noqa: BLE001
        diagnostics.event("mm.rpc.dash", result=repr(exc))


@host.json_message
def server_double_jump(vz: float, vx: float, vy: float, max_jumps: int = 1) -> None:
    """Host owns the impulse; re-assert for a few ticks like Eternal dash (one write loses to moves)."""
    pc = _sender_pc(server_double_jump)
    ctx = _host_context(pc)
    if ctx is None or ctx.pawn is None:
        diagnostics.event("mm.rpc.double_jump", result="no_pawn")
        return
    from .features import double_jump

    try:
        double_jump.host_apply_impulse(
            ctx, float(vx), float(vy), float(vz), max_jumps=int(max_jumps)
        )
        diagnostics.event("mm.rpc.double_jump", result="ok", player=ctx.key.player_id)
    except Exception as exc:  # noqa: BLE001
        diagnostics.event("mm.rpc.double_jump", result=repr(exc))


@host.json_message
def server_slide_enter(
    crouched_pct: float,
    distance_percent: float = 80.0,
    dir_x: float = 0.0,
    dir_y: float = 0.0,
    speed_percent: float = 100.0,
) -> None:
    """Host raises CrouchedPct and coasts the joiner along their entry direction.

    CrouchedPct alone stops the slide when the joiner releases forward. The host
    re-applies the same vector the joiner coasts locally, so the correction matches.
    """
    pc = _sender_pc(server_slide_enter)
    ctx = _host_context(pc)
    if ctx is None or ctx.pawn is None:
        diagnostics.event("mm.rpc.slide_enter", result="no_pawn")
        return
    from .features import slide

    try:
        slide.host_enter_juso(
            ctx,
            float(crouched_pct),
            float(distance_percent),
            float(dir_x),
            float(dir_y),
            float(speed_percent),
        )
        diagnostics.event("mm.rpc.slide_enter", result="ok", player=ctx.key.player_id)
    except Exception as exc:  # noqa: BLE001
        diagnostics.event("mm.rpc.slide_enter", result=repr(exc))


@host.message
def server_slide_exit() -> None:
    """juso-exact: restore CrouchedPct default on sender.Owner.Pawn."""
    pc = _sender_pc(server_slide_exit)
    ctx = _host_context(pc)
    if ctx is None:
        return
    from .features import slide

    slide.host_exit_juso(ctx)


@host.json_message
def server_slide_jump(vx: float, vy: float, vz: float) -> None:
    """Host holds the joiner's slide-jump launch so the server does not pull them down."""
    pc = _sender_pc(server_slide_jump)
    ctx = _host_context(pc)
    if ctx is None or ctx.pawn is None:
        diagnostics.event("mm.rpc.slide_jump", result="no_pawn")
        return
    from .features import slide

    try:
        slide.host_apply_slide_jump(ctx, float(vx), float(vy), float(vz))
        diagnostics.event("mm.rpc.slide_jump", result="ok", player=ctx.key.player_id)
    except Exception as exc:  # noqa: BLE001
        diagnostics.event("mm.rpc.slide_jump", result=repr(exc))


@host.json_message
def server_speed_mult(mult: float) -> None:
    """Host writes GroundSpeed multiplier for surge on the sender's server pawn."""
    pc = _sender_pc(server_speed_mult)
    ctx = _host_context(pc)
    if ctx is None or ctx.pawn is None:
        return
    value = max(0.05, float(mult))

    def apply() -> None:
        if value <= 1.001:
            core.set_speed_mult("surge", None, ctx)
        else:
            core.set_speed_mult("surge", value, ctx)

    try:
        core.execute(ctx, apply)
    except Exception as exc:  # noqa: BLE001
        diagnostics.event("mm.rpc.speed", result=repr(exc))


@host.json_message
def server_holster(kind: str) -> None:
    pc = _sender_pc(server_holster)
    ctx = _host_context(pc)
    if ctx is None:
        return
    from .features import holster

    reason, _ = holster._authority_input(ctx, {"kind": kind})
    diagnostics.event("mm.rpc.holster", result=reason.value if isinstance(reason, Reason) else str(reason))


@host.json_message
def server_mantle_start(plan: dict) -> None:
    """Host replays the joiner's climb plan on sender.Owner.Pawn (Location stall ignored)."""
    pc = _sender_pc(server_mantle_start)
    ctx = _host_context(pc)
    if ctx is None or ctx.pawn is None:
        diagnostics.event("mm.rpc.mantle_start", result="no_pawn")
        return
    from .features import mantle

    try:
        mantle.host_apply_mantle(ctx, plan if isinstance(plan, dict) else {})
        diagnostics.event("mm.rpc.mantle_start", result="ok", player=ctx.key.player_id)
    except Exception as exc:  # noqa: BLE001
        diagnostics.event("mm.rpc.mantle_start", result=repr(exc))


@host.message
def server_mantle_end() -> None:
    """Joiner ended early — drop the host-side climb hold."""
    pc = _sender_pc(server_mantle_end)
    ctx = _host_context(pc)
    if ctx is None:
        return
    from .features import mantle

    mantle.host_end_mantle(ctx)


def _slam_allowed(ctx) -> bool:
    from . import game

    return game.is_bl2() and ctx is not None


@host.json_message
def server_slam_begin(vx: float, vy: float, vz: float) -> None:
    """BL2: host writes the joiner's slam dive until they land."""
    pc = _sender_pc(server_slam_begin)
    ctx = _host_context(pc)
    if not _slam_allowed(ctx):
        return
    from .features import slam

    slam.host_begin_slam(ctx, float(vx), float(vy), float(vz))


@host.message
def server_slam_end() -> None:
    """BL2: joiner cancelled the slam before impact."""
    pc = _sender_pc(server_slam_end)
    ctx = _host_context(pc)
    if not _slam_allowed(ctx):
        return
    from .features import slam

    slam.host_end_slam(ctx)


@host.json_message
def server_slam_impact(power: float) -> None:
    """BL2: host stops the dive and runs the landing blast once."""
    pc = _sender_pc(server_slam_impact)
    ctx = _host_context(pc)
    if not _slam_allowed(ctx):
        return
    from .features import slam

    slam.host_impact_slam(ctx, float(power))


def call_host(fn, *args) -> bool:
    """Invoke a @host RPC; returns False if Networking cannot deliver.

    Refuses bare stub callables (no `_encode_message`) so tests/missing Networking cannot
    silently "succeed" by running the host handler locally without a sender.
    """
    if not _NETWORKING:
        _log(f"skip {getattr(fn, '__name__', fn)} — Networking missing")
        diagnostics.event("mm.rpc.no_networking", interval=2.0, fn=getattr(fn, "__name__", "?"))
        return False
    if not hasattr(fn, "_encode_message"):
        _log(f"skip {getattr(fn, '__name__', fn)} — not a live NetworkFunction")
        diagnostics.event("mm.rpc.not_network_function", fn=getattr(fn, "__name__", "?"))
        return False
    name = getattr(fn, "__name__", "?")
    try:
        fn(*args)
        diagnostics.event("mm.rpc", fn=name, ok=True)
        return True
    except Exception as exc:  # noqa: BLE001
        _log(f"{name} failed: {exc!r}")
        diagnostics.event("mm.rpc.call_failed", fn=name, error=repr(exc))
        return False


def is_requester(ctx) -> bool:
    return ctx is not None and ctx.role == ExecutionRole.LOCAL_REQUESTER


# Stable identifiers (module path changes would break wire compatibility).
server_dash.network_identifier = "ModernMovement:Dash"
server_double_jump.network_identifier = "ModernMovement:DoubleJump"
server_slide_enter.network_identifier = "ModernMovement:SlideEnter"
server_slide_exit.network_identifier = "ModernMovement:SlideExit"
server_slide_jump.network_identifier = "ModernMovement:SlideJump"
server_speed_mult.network_identifier = "ModernMovement:Speed"
server_holster.network_identifier = "ModernMovement:Holster"
server_mantle_start.network_identifier = "ModernMovement:MantleStart"
server_mantle_end.network_identifier = "ModernMovement:MantleEnd"
server_slam_begin.network_identifier = "ModernMovement:SlamBegin"
server_slam_end.network_identifier = "ModernMovement:SlamEnd"
server_slam_impact.network_identifier = "ModernMovement:SlamImpact"

NETWORK_FUNCTIONS = [
    server_dash,
    server_double_jump,
    server_slide_enter,
    server_slide_exit,
    server_slide_jump,
    server_speed_mult,
    server_holster,
    server_mantle_start,
    server_mantle_end,
    server_slam_begin,
    server_slam_end,
    server_slam_impact,
]
