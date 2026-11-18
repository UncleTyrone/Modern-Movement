"""Optional wire helpers for Modern Movement.

Local own-pawn movement does not need Networking. When Networking 1.2 is present the
HELLO/INTENT endpoints still register; when it is missing, stubs keep imports alive so
Dash/Slide/Double Jump still load for every player who enabled the mod.
"""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable

from mods_base import ENGINE, get_pc
from unrealsdk import logging

from . import authority, diagnostics
from .protocol import (
    MAX_PENDING,
    MAX_RESULT_CACHE,
    Envelope,
    Kind,
    ProtocolError,
    Reason,
    SequenceWindow,
    decode,
    digest,
    encode,
)
from .rules import EMPTY_RULES, Ruleset
from .runtime import PlayerContext, REGISTRY, TickFrame

_NETWORKING_AVAILABLE = False
try:
    from networking import add_network_functions
    from networking.decorators import host, targeted

    _NETWORKING_AVAILABLE = True
except Exception:  # noqa: BLE001

    def add_network_functions(mod, network_functions=None):  # noqa: ANN001
        return mod

    class _StubEndpoint:
        def string_message(self, fn=None):  # noqa: ANN001
            def wrap(target):
                return target

            return wrap if fn is None else wrap(fn)

        def json_message(self, fn=None):  # noqa: ANN001
            def wrap(target):
                return target

            return wrap if fn is None else wrap(fn)

        def message(self, fn=None):  # noqa: ANN001
            def wrap(target):
                return target

            return wrap if fn is None else wrap(fn)

        def __call__(self, fn):  # noqa: ANN001
            return fn

    host = _StubEndpoint()
    targeted = _StubEndpoint()


C2H_IDENTIFIER = "ModernMovement:C2H"
H2C_IDENTIFIER = "ModernMovement:H2C"
HELLO_INTERVAL = 1.0
HEARTBEAT_INTERVAL = 5.0
RETRY_DELAYS = (0.5, 1.0, 2.0)
RATE_PER_SECOND = 12.0
RATE_BURST = 16.0


@dataclass
class PendingFrame:
    envelope: Envelope
    raw: str
    sent_at: float
    retry: int = 0


@dataclass
class Peer:
    player_id: int
    token: str
    receive: SequenceWindow = field(default_factory=SequenceWindow)
    send_sequence: int = 1
    acknowledgement: int = 0
    ready: bool = False
    pawn_token: int = 0
    rules_hash: str = ""
    results: OrderedDict[int, str] = field(default_factory=OrderedDict)
    tokens: float = RATE_BURST
    token_at: float = field(default_factory=time.monotonic)
    last_seen: float = 0.0

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(RATE_BURST, self.tokens + (now - self.token_at) * RATE_PER_SECOND)
        self.token_at = now
        if self.tokens < 1.0:
            return False
        self.tokens -= 1.0
        return True

    def cache(self, sequence: int, raw: str) -> None:
        self.results[sequence] = raw
        self.results.move_to_end(sequence)
        while len(self.results) > MAX_RESULT_CACHE:
            self.results.popitem(last=False)


@dataclass
class Client:
    session: str = ""
    token: str = ""
    pawn_token: int = 0
    send_sequence: int = 1
    receive: SequenceWindow = field(default_factory=SequenceWindow)
    acknowledgement: int = 0
    pending: OrderedDict[int, PendingFrame] = field(default_factory=OrderedDict)
    ready: bool = False
    desync_safe: bool = True
    last_hello: float = -100.0
    last_heartbeat: float = -100.0
    host_player_id: int | None = None
    mirror: dict[str, Any] = field(default_factory=dict)
    mirror_digest: str = ""


_session = ""
_host_peers: dict[int, Peer] = {}
_client = Client()
_rules = EMPTY_RULES
_presentation_handlers: dict[str, Callable[[str, dict[str, Any]], None]] = {}
_enabled = False


def _log(message: str) -> None:
    logging.info(f"[Modern Movement] network: {message}")


def set_rules(rules: Ruleset) -> None:
    global _rules
    _rules = rules


def rules() -> Ruleset:
    return _rules


def register_presentation(feature: str, callback: Callable[[str, dict[str, Any]], None]) -> None:
    _presentation_handlers[feature] = callback


def unregister_presentation(feature: str) -> None:
    _presentation_handlers.pop(feature, None)


def _pid(pri: Any) -> int | None:
    try:
        return int(pri.PlayerID)
    except Exception:
        return None


def _party_leader(pri: Any) -> bool:
    try:
        return bool(pri.bIsPartyLeader)
    except Exception:
        return False


def _accept_host_sender(pri: Any) -> bool:
    """Listen-host PRI is not always flagged bIsPartyLeader in TPS; clients still need WELCOME."""
    if _party_leader(pri):
        return True
    if not _is_client():
        return False
    pid = _pid(pri)
    known = _client.host_player_id
    # First targeted frame from the session host, or the same host we already bound.
    return pid is not None and (known is None or known == pid)


def _local_pri() -> Any:
    pc = get_pc(possibly_loading=True)
    return getattr(pc, "PlayerReplicationInfo", None) if pc is not None else None


def _is_client() -> bool:
    try:
        return int(ENGINE.GetCurrentWorldInfo().NetMode) == 3
    except Exception:
        return False


def _is_standalone() -> bool:
    try:
        return int(ENGINE.GetCurrentWorldInfo().NetMode) == 0
    except Exception:
        return True


def _world_now() -> float:
    try:
        return float(ENGINE.GetCurrentWorldInfo().TimeSeconds)
    except Exception:
        return time.monotonic()


def _new_session() -> None:
    global _session
    _session = secrets.token_hex(8)
    _host_peers.clear()


def _host_peer(pri: Any) -> Peer | None:
    pid = _pid(pri)
    if pid is None:
        return None
    peer = _host_peers.get(pid)
    if peer is None:
        peer = Peer(player_id=pid, token=secrets.token_hex(8))
        _host_peers[pid] = peer
    return peer


def _envelope(
    kind: Kind,
    sequence: int,
    acknowledgement: int,
    payload: dict[str, Any],
    *,
    session: str = "",
    peer: str = "",
    pawn: int = 0,
    rules_revision: int = 0,
) -> Envelope:
    return Envelope(
        kind=kind,
        sequence=sequence,
        acknowledgement=acknowledgement,
        session=session,
        peer=peer,
        pawn=pawn,
        rules=rules_revision,
        payload=payload,
    )


@host.string_message
def _from_peer(raw: str) -> None:
    sender = _from_peer.sender
    try:
        message = decode(raw)
    except ProtocolError as exc:
        diagnostics.event("mm.net.drop", direction="c2h", reason=str(exc))
        return
    if message.kind == Kind.HELLO:
        _handle_hello(sender, message)
        return
    peer = _host_peer(sender)
    if peer is None or not peer.allow():
        return
    peer.last_seen = time.monotonic()
    if message.session != _session or message.peer != peer.token:
        _send_host_reject(sender, peer, message.sequence, Reason.BAD_TOKEN)
        return
    # READY / HEARTBEAT / SNAPSHOT must not die on a stale pawn generation from travel.
    classification = peer.receive.classify(message.sequence)
    if classification == Reason.STALE_SEQUENCE:
        cached = peer.results.get(message.sequence)
        if cached is not None:
            _to_peer(sender, cached)
        return
    if classification != Reason.OK:
        _send_host_reject(sender, peer, message.sequence, classification)
        return
    peer.receive.accept(message.sequence)
    peer.acknowledgement = message.sequence

    if message.kind == Kind.READY:
        # Host rules always win; never leave the peer unready over a hash mismatch.
        peer.ready = True
        ctx = _context_for_sender(sender)
        peer.pawn_token = ctx.pawn_generation if ctx is not None else 0
        _send_to_peer(
            sender,
            peer,
            Kind.BIND,
            {"ready": True, "rules_hash": _rules.hash},
            request_sequence=message.sequence,
        )
        return
    if message.kind == Kind.HEARTBEAT:
        return
    if message.kind == Kind.SNAPSHOT_REQUEST:
        ctx = _context_for_sender(sender)
        if ctx is not None:
            peer.pawn_token = ctx.pawn_generation
            _send_to_peer(
                sender,
                peer,
                Kind.SNAPSHOT,
                authority.snapshot(ctx),
                request_sequence=message.sequence,
            )
        return
    if message.kind == Kind.LEAVE:
        peer.ready = False
        return
    # Only this peer must have finished HELLO/WELCOME. Missing mods on other players
    # must never freeze the host or ready peers.
    if message.kind != Kind.INTENT or not peer.ready:
        _send_host_reject(sender, peer, message.sequence, Reason.NOT_READY)
        return
    # Host gameplay rules are authoritative; client revision is not a kill switch.
    ctx = _context_for_sender(sender)
    if ctx is None or ctx.pawn is None:
        _send_host_reject(sender, peer, message.sequence, Reason.NO_PAWN)
        return
    peer.pawn_token = ctx.pawn_generation
    feature = message.payload.get("feature")
    operation = message.payload.get("operation")
    data = message.payload.get("data")
    if not isinstance(feature, str) or not isinstance(operation, str) or not isinstance(data, dict):
        _send_host_reject(sender, peer, message.sequence, Reason.BAD_MESSAGE)
        return
    reason, response = authority.dispatch_intent(ctx, feature, operation, data)
    kind = Kind.ACCEPT if reason == Reason.OK else Kind.REJECT
    response = {
        "request": message.sequence,
        "feature": feature,
        "operation": operation,
        "reason": reason.value,
        "state": response,
    }
    _send_to_peer(sender, peer, kind, response, request_sequence=message.sequence)


@targeted.string_message
def _from_host(raw: str) -> None:
    sender = _from_host.sender
    if not _accept_host_sender(sender):
        diagnostics.event("mm.net.drop", direction="h2c", reason="sender_not_host")
        return
    try:
        message = decode(raw)
    except ProtocolError as exc:
        diagnostics.event("mm.net.drop", direction="h2c", reason=str(exc))
        return
    _client.host_player_id = _pid(sender)
    if message.kind == Kind.WELCOME:
        _handle_welcome(message)
        return
    if message.session != _client.session or message.peer != _client.token:
        _enter_desync("token_mismatch")
        return
    classification = _client.receive.classify(message.sequence)
    if classification == Reason.STALE_SEQUENCE:
        return
    if classification != Reason.OK:
        _enter_desync("sequence_gap")
        return
    _client.receive.accept(message.sequence)
    _client.acknowledgement = message.sequence
    request = message.payload.get("request")
    if isinstance(request, int):
        _client.pending.pop(request, None)

    if message.kind == Kind.BIND:
        _client.pawn_token = message.pawn
        # BIND is confirmation only; WELCOME already marked this client ready to send intents.
        _client.ready = True
        _client.desync_safe = False
    elif message.kind in (Kind.STATE, Kind.SNAPSHOT):
        state_payload = message.payload.get("state", message.payload)
        if not isinstance(state_payload, dict):
            _enter_desync("bad_snapshot")
            return
        _client.mirror = state_payload
        _client.mirror_digest = digest(state_payload)
        _client.desync_safe = False
        if isinstance(state_payload.get("pawn"), int):
            _client.pawn_token = int(state_payload["pawn"])
        _dispatch_presentation("state", state_payload)
    elif message.kind == Kind.ACCEPT:
        state_payload = message.payload.get("state")
        if isinstance(state_payload, dict) and isinstance(state_payload.get("pawn"), int):
            _client.pawn_token = int(state_payload["pawn"])
        _dispatch_result("accept", message.payload)
    elif message.kind == Kind.REJECT:
        reason = message.payload.get("reason")
        if reason in (Reason.STALE_PAWN.value, Reason.STALE_RULES.value, Reason.BAD_TOKEN.value):
            # Force a fresh HELLO rather than sitting forever in DESYNC_SAFE.
            _client.session = ""
            _client.ready = False
            _client.desync_safe = True
        _dispatch_result("reject", message.payload)
    elif message.kind == Kind.END:
        _dispatch_result("end", message.payload)


_from_peer.network_identifier = C2H_IDENTIFIER
_from_host.network_identifier = H2C_IDENTIFIER
NETWORK_FUNCTIONS = [_from_peer, _from_host]


def _handle_hello(sender: Any, message: Envelope) -> None:
    if _is_client():
        return
    peer = _host_peer(sender)
    if peer is None:
        return
    # Welcome immediately authorizes intents so clients are not soft-locked waiting on BIND.
    peer.ready = True
    peer.receive = SequenceWindow(expected=message.sequence + 1)
    peer.acknowledgement = message.sequence
    peer.rules_hash = str(message.payload.get("rules_hash", ""))
    ctx = _context_for_sender(sender)
    peer.pawn_token = ctx.pawn_generation if ctx is not None else 0
    _send_to_peer(
        sender,
        peer,
        Kind.WELCOME,
        {
            "protocol": 1,
            "rules": _rules.payload(),
            "rules_hash": _rules.hash,
            "package": "3.62.2",
        },
        request_sequence=message.sequence,
    )


def _handle_welcome(message: Envelope) -> None:
    global _rules
    try:
        remote_rules = Ruleset.from_payload(message.payload["rules"])
    except (KeyError, TypeError, ValueError):
        # Adopt session anyway; host still validates intents. Stale option mirrors must not
        # freeze the joining client with zero abilities.
        diagnostics.event("mm.net.welcome_rules", result="adopt_failed")
        remote_rules = _rules
    else:
        if message.payload.get("rules_hash") == remote_rules.hash:
            _rules = remote_rules
        else:
            diagnostics.event("mm.net.welcome_rules", result="hash_mismatch_ignored")
            _rules = remote_rules
    _client.session = message.session
    _client.token = message.peer
    _client.pawn_token = message.pawn
    _client.receive = SequenceWindow(expected=message.sequence + 1)
    _client.acknowledgement = message.sequence
    # Ready as soon as the host welcomes us — waiting on BIND left clients soft-locked.
    _client.ready = True
    _client.desync_safe = False
    _send_client(Kind.READY, {"rules_hash": _rules.hash})


def _context_for_sender(pri: Any) -> PlayerContext | None:
    """Resolve the server-side controller for a wire sender, creating a context if needed."""
    try:
        pc = pri.Owner
    except Exception:
        return None
    if pc is None:
        return None
    ctx = REGISTRY.resolve_controller(pc)
    if ctx is not None:
        return ctx
    try:
        pawn = pc.Pawn
    except Exception:
        pawn = None
    from .runtime import ExecutionRole

    # On the listen host, remote owners are always treated as authority targets.
    return REGISTRY.observe(pc, ExecutionRole.REMOTE_AUTHORITY, _world_now(), pawn)


def _send_to_peer(
    pri: Any,
    peer: Peer,
    kind: Kind,
    payload: dict[str, Any],
    *,
    request_sequence: int = 0,
) -> None:
    message = _envelope(
        kind,
        peer.send_sequence,
        peer.acknowledgement,
        {"request": request_sequence, **payload},
        session=_session,
        peer=peer.token,
        pawn=peer.pawn_token,
        rules_revision=_rules.revision,
    )
    peer.send_sequence += 1
    raw = encode(message)
    if request_sequence:
        peer.cache(request_sequence, raw)
    _to_peer(pri, raw)


def _to_peer(pri: Any, raw: str) -> None:
    _from_host(pri, raw)
    diagnostics.count("mm.net.tx.h2c")


def _send_host_reject(pri: Any, peer: Peer, request: int, reason: Reason) -> None:
    _send_to_peer(
        pri,
        peer,
        Kind.REJECT,
        {"reason": reason.value, "feature": "", "operation": "", "state": {}},
        request_sequence=request,
    )


def _send_client(kind: Kind, payload: dict[str, Any]) -> int | None:
    if len(_client.pending) >= MAX_PENDING and kind == Kind.INTENT:
        return None
    sequence = _client.send_sequence
    _client.send_sequence += 1
    message = _envelope(
        kind,
        sequence,
        _client.acknowledgement,
        payload,
        session=_client.session,
        peer=_client.token,
        pawn=_client.pawn_token,
        rules_revision=_rules.revision,
    )
    raw = encode(message)
    _from_peer(raw)
    diagnostics.count("mm.net.tx.c2h")
    if kind in (Kind.INTENT, Kind.READY, Kind.SNAPSHOT_REQUEST):
        _client.pending[sequence] = PendingFrame(message, raw, time.monotonic())
    return sequence


def mirror_intent(feature: str, operation: str, data: dict[str, Any]) -> None:
    """Wire-only client → host mirror. Caller already applied the action locally."""
    if not _NETWORKING_AVAILABLE or not _enabled or not _is_client():
        return
    try:
        _send_client(
            Kind.INTENT,
            {"feature": feature, "operation": operation, "data": data},
        )
    except Exception:  # noqa: BLE001
        pass


def send_intent(feature: str, operation: str, data: dict[str, Any]) -> tuple[Reason, dict[str, Any]]:
    """Apply locally, and when this is a joining client also mirror to the listen host."""
    from .runtime import ExecutionRole

    ctx = REGISTRY.resolve_controller(get_pc(possibly_loading=True))
    if ctx is None:
        return Reason.NO_PAWN, {}
    if ctx.role in (ExecutionRole.LOCAL_STANDALONE, ExecutionRole.LOCAL_HOST):
        return authority.dispatch_intent(ctx, feature, operation, data)
    if ctx.role == ExecutionRole.LOCAL_REQUESTER:
        # Local write = HUD + immediate feel; host mirror = server pawn matches (no rubber-band).
        reason, response = authority.dispatch_intent(ctx, feature, operation, data)
        mirror_intent(feature, operation, data)
        return reason, response
    return Reason.NOT_AUTHORITY, {}


def _dispatch_result(event: str, payload: dict[str, Any]) -> None:
    feature = payload.get("feature")
    state_payload = payload.get("state")
    if isinstance(feature, str) and isinstance(state_payload, dict):
        callback = _presentation_handlers.get(feature)
        if callback is not None:
            try:
                callback(event, payload)
            except Exception:
                pass


def _dispatch_presentation(event: str, payload: dict[str, Any]) -> None:
    features = payload.get("features")
    if not isinstance(features, dict):
        return
    for feature, state_payload in features.items():
        callback = _presentation_handlers.get(feature)
        if callback is not None and isinstance(state_payload, dict):
            try:
                callback(event, state_payload)
            except Exception:
                pass


def _enter_desync(reason: str) -> None:
    _client.desync_safe = True
    _client.ready = False
    _dispatch_presentation("desync", {})
    diagnostics.event("mm.net.desync", reason=reason)
    if _client.session:
        try:
            _send_client(Kind.SNAPSHOT_REQUEST, {"reason": reason})
        except Exception:
            pass


def _hello(now: float) -> None:
    if now - _client.last_hello < HELLO_INTERVAL:
        return
    _client.last_hello = now
    message = _envelope(
        Kind.HELLO,
        _client.send_sequence,
        _client.acknowledgement,
        {
            "protocol_min": 1,
            "protocol_max": 1,
            "package": "3.62.2",
            "game": "TPS",
            "rules_hash": _rules.hash,
            "boot": secrets.token_hex(4),
        },
    )
    _client.send_sequence += 1
    _from_peer(encode(message))


def _retry(now: float) -> None:
    for sequence, pending in list(_client.pending.items()):
        delay = RETRY_DELAYS[min(pending.retry, len(RETRY_DELAYS) - 1)]
        if now - pending.sent_at < delay:
            continue
        if pending.retry >= len(RETRY_DELAYS):
            _client.pending.pop(sequence, None)
            _enter_desync("request_timeout")
            return
        _from_peer(pending.raw)
        pending.sent_at = now
        pending.retry += 1


def tick(ctx: PlayerContext, frame: TickFrame) -> None:
    if not _enabled or not ctx.local:
        return
    # Without Networking 1.2 there is no wire — local movement/HUD do not need this path.
    if not _NETWORKING_AVAILABLE:
        return
    if not _is_client():
        if not _session:
            _new_session()
        _poll_roster()
        # Refresh host rules from live options so revision changes cancel mismatched clients.
        try:
            from . import rules as rules_mod

            live = rules_mod.collect_live_rules(revision=max(1, _rules.revision))
            if live.hash != _rules.hash:
                set_rules(live.with_revision(_rules.revision + 1))
                diagnostics.event("mm.rules.revised", revision=_rules.revision)
        except Exception:  # noqa: BLE001
            pass
        return
    if not _client.session:
        _hello(frame.now)
    else:
        _retry(time.monotonic())
        if frame.now - _client.last_heartbeat >= HEARTBEAT_INTERVAL:
            _client.last_heartbeat = frame.now
            _send_client(Kind.HEARTBEAT, {})


def _poll_roster() -> None:
    try:
        pris = list(ENGINE.GetCurrentWorldInfo().GRI.PRIArray)
    except Exception:
        return
    local = _local_pri()
    active: set[int] = set()
    for pri in pris:
        pid = _pid(pri)
        if pid is None or pri == local:
            continue
        active.add(pid)
    for pid in list(_host_peers):
        if pid not in active:
            _host_peers.pop(pid, None)


def all_peers_ready() -> bool:
    """Deprecated compatibility shim: never blocks gameplay for missing peer mods."""
    return True


def ready() -> bool:
    """Local own-pawn movement never waits on handshake (Willow client simulation)."""
    return True


def _send_authority(ctx: PlayerContext, kind: str, payload: dict[str, Any]) -> None:
    if ctx.local:
        _dispatch_presentation(kind, payload)
        return
    pri = getattr(ctx.controller, "PlayerReplicationInfo", None)
    peer = _host_peers.get(ctx.key.player_id)
    if pri is None or peer is None or not peer.ready:
        return
    mapped = {"state": Kind.STATE, "end": Kind.END}.get(kind, Kind.STATE)
    _send_to_peer(pri, peer, mapped, {"state": payload})


def enable() -> None:
    global _enabled
    _enabled = True
    _new_session()
    authority.set_sender(_send_authority)


def disable() -> None:
    global _enabled
    if _enabled and _is_client() and _client.session:
        try:
            _send_client(Kind.LEAVE, {})
        except Exception:
            pass
    _enabled = False
    _host_peers.clear()
    _client.pending.clear()
    _client.ready = False
    _client.desync_safe = True


def networking_available() -> bool:
    return _NETWORKING_AVAILABLE


def attach_mod(mod):
    if not _NETWORKING_AVAILABLE:
        _log("Networking 1.2 not found — local movement only (no wire endpoints)")
        return mod
    try:
        from . import coop_rpc

        funcs = list(NETWORK_FUNCTIONS) + list(coop_rpc.NETWORK_FUNCTIONS)
        return add_network_functions(mod, network_functions=funcs)
    except Exception as exc:  # noqa: BLE001
        _log(f"network attach failed ({exc!r}) — local movement only")
        return mod
