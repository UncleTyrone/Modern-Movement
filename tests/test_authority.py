from __future__ import annotations

import Modern_Movement.authority as authority
from Modern_Movement.protocol import Reason
from Modern_Movement.runtime import ExecutionRole, PlayerContext, PlayerKey, TickFrame


def _ctx(role: ExecutionRole = ExecutionRole.LOCAL_HOST) -> PlayerContext:
    key = PlayerKey(0, 1)
    return PlayerContext(key=key, role=role, controller=object())


def test_dispatch_requires_authority():
    authority.register_feature(
        "dash",
        authority.FeatureController(
            start=lambda ctx, payload: (Reason.OK, {"ok": True}),
        ),
    )
    host = _ctx(ExecutionRole.LOCAL_HOST)
    client = _ctx(ExecutionRole.LOCAL_REQUESTER)
    remote = _ctx(ExecutionRole.REMOTE_AUTHORITY)
    # Host, joining clients, and host-side remote contexts may all dispatch.
    assert authority.dispatch_intent(host, "dash", "start", {}) == (Reason.OK, {"ok": True})
    assert authority.dispatch_intent(client, "dash", "start", {}) == (Reason.OK, {"ok": True})
    assert authority.dispatch_intent(remote, "dash", "start", {}) == (Reason.OK, {"ok": True})


def test_dispatch_unknown_feature():
    host = _ctx()
    assert authority.dispatch_intent(host, "nope", "start", {}) == (Reason.UNSUPPORTED, {})


def test_snapshot_and_digest_emit_on_tick(monkeypatch):
    sent: list[tuple[str, dict]] = []

    def sender(ctx, kind, payload):  # noqa: ANN001
        sent.append((kind, payload))

    authority.set_sender(sender)
    authority.register_feature(
        "jump",
        authority.FeatureController(snapshot=lambda ctx: {"count": 1}),
    )
    ctx = _ctx()
    authority.allocate_action(ctx, "jump")
    frame = TickFrame(now=1.0, dt=0.016, phys_at_start=0, world_epoch=0)
    authority.tick(ctx, frame)
    assert sent and sent[0][0] == "state"
    assert sent[0][1]["features"]["jump"]["count"] == 1
    sent.clear()
    frame = TickFrame(now=1.1, dt=0.016, phys_at_start=0, world_epoch=0)
    authority.tick(ctx, frame)
    assert not sent
    frame = TickFrame(now=1.35, dt=0.016, phys_at_start=0, world_epoch=0)
    authority.tick(ctx, frame)
    assert sent and sent[-1][0] == "state"