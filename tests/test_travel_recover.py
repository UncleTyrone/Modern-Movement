"""Fast travel must not leave joiners on a dead session or an old slide hold."""

from __future__ import annotations

from types import SimpleNamespace

from Modern_Movement import network
from Modern_Movement.features import slide
from Modern_Movement.runtime import ExecutionRole, PlayerContext, PlayerKey


class _Pawn:
    def __init__(self):
        self.CrouchedPct = 0.5
        self.GroundSpeed = 440.0
        self.Location = SimpleNamespace(X=0.0, Y=0.0, Z=10.0)
        self.Velocity = SimpleNamespace(X=0.0, Y=0.0, Z=0.0)
        self.Acceleration = SimpleNamespace(X=0.0, Y=0.0, Z=0.0)
        self.AccelRate = 2048.0

    def ShouldCrouch(self, _value):  # noqa: N802
        return None


def test_empty_roster_does_not_drop_peers(monkeypatch):
    network._host_peers.clear()
    network._peer_missing_since.clear()
    network._host_peers[4] = network.Peer(player_id=4, token="keep")
    world = SimpleNamespace(GRI=SimpleNamespace(PRIArray=[]))
    monkeypatch.setattr(network, "ENGINE", SimpleNamespace(GetCurrentWorldInfo=lambda: world))
    network._poll_roster()
    assert 4 in network._host_peers
    assert network._host_peers[4].token == "keep"


def test_world_change_clears_session_and_slide_hold():
    pawn = _Pawn()
    ctx = PlayerContext(
        key=PlayerKey(1, 9),
        role=ExecutionRole.REMOTE_AUTHORITY,
        controller=SimpleNamespace(),
        pawn=pawn,
        clock=1.0,
        pawn_generation=1,
    )
    slide.host_enter_juso(ctx, 2.2, 100.0, 1.0, 0.0, 120.0)
    assert 9 in slide._HOST_SLIDES

    network._client.session = "old-session"
    network._client.ready = True
    network._client.last_hello = 99999.0
    old_session = network._session
    network.on_world_changed()

    assert network._client.session == ""
    assert network._client.ready is False
    assert network._client.last_hello < 0.0
    assert network._session and network._session != old_session
    assert slide._HOST_SLIDES == {}


def test_rewound_clock_still_sends_hello(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(network, "_from_peer", lambda raw: sent.append(raw))
    network._reset_client_handshake()
    network._client.last_hello = 8000.0
    network._hello(0.2)
    assert sent
    assert network._client.last_hello == 0.2
