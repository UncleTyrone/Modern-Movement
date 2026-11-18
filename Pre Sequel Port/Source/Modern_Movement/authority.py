"""Host-only action routing and authoritative state digests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import diagnostics
from .protocol import Reason, digest
from .runtime import PlayerContext, TickFrame


StartHandler = Callable[[PlayerContext, dict[str, Any]], tuple[Reason, dict[str, Any]]]
InputHandler = Callable[[PlayerContext, dict[str, Any]], tuple[Reason, dict[str, Any]]]
TickHandler = Callable[[PlayerContext, TickFrame], None]
CancelHandler = Callable[[PlayerContext, str], None]
SnapshotHandler = Callable[[PlayerContext], dict[str, Any]]


@dataclass
class FeatureController:
    start: StartHandler | None = None
    input: InputHandler | None = None
    tick: TickHandler | None = None
    cancel: CancelHandler | None = None
    snapshot: SnapshotHandler | None = None


@dataclass
class AuthorityState:
    next_action_id: int = 1
    phase_revision: int = 0
    last_digest: str = ""
    last_digest_at: float = -100.0
    feature_actions: dict[str, int] = field(default_factory=dict)


_features: dict[str, FeatureController] = {}
_send: Callable[[PlayerContext, str, dict[str, Any]], None] | None = None
DIGEST_INTERVAL = 0.25


def set_sender(sender: Callable[[PlayerContext, str, dict[str, Any]], None]) -> None:
    global _send
    _send = sender


def register_feature(name: str, controller: FeatureController) -> None:
    _features[name] = controller


def unregister_feature(name: str) -> None:
    _features.pop(name, None)


def state(ctx: PlayerContext) -> AuthorityState:
    return ctx.state("authority", AuthorityState)


def allocate_action(ctx: PlayerContext, feature: str) -> int:
    ctx.require_authority("action allocation")
    runtime = state(ctx)
    action_id = runtime.next_action_id
    runtime.next_action_id += 1
    runtime.phase_revision += 1
    runtime.feature_actions[feature] = action_id
    ctx.action_revision += 1
    return action_id


def end_action(ctx: PlayerContext, feature: str, reason: str) -> None:
    ctx.require_authority("action end")
    runtime = state(ctx)
    action_id = runtime.feature_actions.pop(feature, None)
    runtime.phase_revision += 1
    ctx.action_revision += 1
    if action_id is not None:
        send(ctx, "end", {"feature": feature, "action": action_id, "reason": reason})


def dispatch_intent(
    ctx: PlayerContext,
    feature: str,
    operation: str,
    payload: dict[str, Any],
) -> tuple[Reason, dict[str, Any]]:
    if not ctx.authority:
        return Reason.NOT_AUTHORITY, {}
    controller = _features.get(feature)
    if controller is None:
        return Reason.UNSUPPORTED, {}
    handler = controller.start if operation == "start" else controller.input
    if handler is None:
        return Reason.UNSUPPORTED, {}
    try:
        reason, response = handler(ctx, payload)
    except PermissionError:
        return Reason.NOT_AUTHORITY, {}
    except Exception as exc:  # noqa: BLE001
        diagnostics.event(
            "mm.authority.error",
            player=ctx.key.player_id,
            feature=feature,
            operation=operation,
            error=repr(exc),
        )
        return Reason.BAD_MESSAGE, {}
    diagnostics.event(
        "mm.authority.intent",
        player=ctx.key.player_id,
        feature=feature,
        operation=operation,
        result=reason.value,
    )
    return reason, response


def tick(ctx: PlayerContext, frame: TickFrame) -> None:
    if not ctx.authority:
        return
    for name, controller in tuple(_features.items()):
        if controller.tick is None:
            continue
        try:
            controller.tick(ctx, frame)
        except Exception as exc:  # noqa: BLE001
            diagnostics.event(
                "mm.authority.tick_error",
                player=ctx.key.player_id,
                feature=name,
                error=repr(exc),
            )
            if controller.cancel is not None:
                try:
                    controller.cancel(ctx, "authority_error")
                except Exception:
                    pass
    runtime = state(ctx)
    if frame.now - runtime.last_digest_at >= DIGEST_INTERVAL:
        payload = snapshot(ctx)
        current = digest(payload)
        if current != runtime.last_digest or runtime.feature_actions:
            send(ctx, "state", payload)
            runtime.last_digest = current
        runtime.last_digest_at = frame.now


def snapshot(ctx: PlayerContext) -> dict[str, Any]:
    runtime = state(ctx)
    features: dict[str, Any] = {}
    for name, controller in _features.items():
        if controller.snapshot is None:
            continue
        try:
            features[name] = controller.snapshot(ctx)
        except Exception:
            features[name] = {"error": True}
    return {
        "pawn": ctx.pawn_generation,
        "busy": ctx.busy or "",
        "action_revision": ctx.action_revision,
        "phase_revision": runtime.phase_revision,
        "actions": dict(runtime.feature_actions),
        "features": features,
    }


def cancel_all(ctx: PlayerContext, reason: str) -> None:
    if not ctx.authority:
        return
    for name, controller in tuple(_features.items()):
        if controller.cancel is not None:
            try:
                controller.cancel(ctx, reason)
            except Exception:
                pass
    runtime = state(ctx)
    for feature in tuple(runtime.feature_actions):
        end_action(ctx, feature, reason)


def send(ctx: PlayerContext, kind: str, payload: dict[str, Any]) -> None:
    if _send is not None:
        _send(ctx, kind, payload)
