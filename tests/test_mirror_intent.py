from __future__ import annotations

from Modern_Movement import network
from Modern_Movement.protocol import Reason
from Modern_Movement.runtime import ExecutionRole, PlayerContext, PlayerKey


def test_send_intent_mirrors_for_requester(monkeypatch):
    mirrored = []

    ctx = PlayerContext(
        key=PlayerKey(1, 3),
        role=ExecutionRole.LOCAL_REQUESTER,
        controller=object(),
    )

    monkeypatch.setattr(network.REGISTRY, "resolve_controller", lambda _pc: ctx)
    monkeypatch.setattr(network, "get_pc", lambda *a, **k: object())
    monkeypatch.setattr(
        network.authority,
        "dispatch_intent",
        lambda *_a, **_k: (Reason.OK, {"local": True}),
    )
    monkeypatch.setattr(network, "mirror_intent", lambda *a: mirrored.append(a))

    reason, payload = network.send_intent("dash", "start", {"direction": "forward"})
    assert reason == Reason.OK
    assert payload == {"local": True}
    assert mirrored == [("dash", "start", {"direction": "forward"})]


def test_send_intent_host_does_not_mirror(monkeypatch):
    mirrored = []
    ctx = PlayerContext(
        key=PlayerKey(1, 1),
        role=ExecutionRole.LOCAL_HOST,
        controller=object(),
    )
    monkeypatch.setattr(network.REGISTRY, "resolve_controller", lambda _pc: ctx)
    monkeypatch.setattr(network, "get_pc", lambda *a, **k: object())
    monkeypatch.setattr(
        network.authority,
        "dispatch_intent",
        lambda *_a, **_k: (Reason.OK, {"host": True}),
    )
    monkeypatch.setattr(network, "mirror_intent", lambda *a: mirrored.append(a))

    reason, payload = network.send_intent("dash", "start", {"direction": "forward"})
    assert reason == Reason.OK
    assert payload == {"host": True}
    assert mirrored == []
