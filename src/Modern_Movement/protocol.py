"""Strict, bounded wire protocol for Modern Movement co-op."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 512
MAX_PAYLOAD_KEYS = 16
MAX_STRING = 96
MAX_PENDING = 4
MAX_RESULT_CACHE = 32


class Kind(str, Enum):
    HELLO = "hello"
    WELCOME = "welcome"
    READY = "ready"
    BIND = "bind"
    INTENT = "intent"
    ACCEPT = "accept"
    REJECT = "reject"
    END = "end"
    STATE = "state"
    SNAPSHOT_REQUEST = "snapshot_request"
    SNAPSHOT = "snapshot"
    HEARTBEAT = "heartbeat"
    LEAVE = "leave"
    ACK = "ack"


class Reason(str, Enum):
    OK = "ok"
    NOT_READY = "not_ready"
    BAD_PROTOCOL = "bad_protocol"
    BAD_MESSAGE = "bad_message"
    BAD_TOKEN = "bad_token"
    STALE_SESSION = "stale_session"
    STALE_PAWN = "stale_pawn"
    STALE_RULES = "stale_rules"
    STALE_SEQUENCE = "stale_sequence"
    SEQUENCE_GAP = "sequence_gap"
    RATE_LIMIT = "rate_limit"
    NO_PAWN = "no_pawn"
    NOT_AUTHORITY = "not_authority"
    DISABLED = "disabled"
    DEAD_OR_VEHICLE = "dead_or_vehicle"
    WRONG_PHYSICS = "wrong_physics"
    BUSY = "busy"
    COOLDOWN = "cooldown"
    INVALID_INPUT = "invalid_input"
    UNSUPPORTED = "unsupported"
    DESYNC = "desync"


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Envelope:
    kind: Kind
    sequence: int
    acknowledgement: int
    session: str
    peer: str
    pawn: int
    rules: int
    payload: dict[str, Any]
    version: int = PROTOCOL_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "v": self.version,
            "k": self.kind.value,
            "q": self.sequence,
            "a": self.acknowledgement,
            "s": self.session,
            "t": self.peer,
            "p": self.pawn,
            "r": self.rules,
            "d": self.payload,
        }


_TOP_KEYS = frozenset({"v", "k", "q", "a", "s", "t", "p", "r", "d"})


def _integer(value: Any, name: str, low: int = 0, high: int = 2**31 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ProtocolError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _string(value: Any, name: str, max_length: int = MAX_STRING) -> str:
    if not isinstance(value, str) or len(value) > max_length:
        raise ProtocolError(f"{name} must be a string no longer than {max_length}")
    if any(ord(char) < 0x20 or ord(char) > 0x7E for char in value):
        raise ProtocolError(f"{name} must contain printable ASCII only")
    return value


def _validate_json(value: Any, depth: int = 0) -> None:
    if depth > 4:
        raise ProtocolError("payload nesting is too deep")
    if value is None or isinstance(value, bool | str):
        if isinstance(value, str):
            _string(value, "payload string")
        return
    if isinstance(value, int):
        if not -(2**31) <= value <= 2**31 - 1:
            raise ProtocolError("payload integer is out of range")
        return
    if isinstance(value, float):
        if not math.isfinite(value) or abs(value) > 1_000_000.0:
            raise ProtocolError("payload float is invalid")
        return
    if isinstance(value, list):
        if len(value) > 16:
            raise ProtocolError("payload list is too long")
        for item in value:
            _validate_json(item, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_PAYLOAD_KEYS:
            raise ProtocolError("payload object has too many keys")
        for key, item in value.items():
            _string(key, "payload key", 32)
            _validate_json(item, depth + 1)
        return
    raise ProtocolError(f"unsupported payload value: {type(value).__name__}")


def encode(envelope: Envelope) -> str:
    _validate_envelope(envelope)
    raw = json.dumps(
        envelope.as_dict(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(raw.encode("ascii")) > MAX_FRAME_BYTES:
        raise ProtocolError("encoded frame exceeds the size limit")
    return raw


def decode(raw: str) -> Envelope:
    if not isinstance(raw, str):
        raise ProtocolError("frame must be text")
    if len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
        raise ProtocolError("frame exceeds the size limit")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("frame is not valid JSON") from exc
    if not isinstance(data, dict) or set(data) != _TOP_KEYS:
        raise ProtocolError("frame has an invalid top-level schema")
    try:
        kind = Kind(data["k"])
    except (TypeError, ValueError) as exc:
        raise ProtocolError("unknown message kind") from exc
    payload = data["d"]
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be an object")
    envelope = Envelope(
        version=_integer(data["v"], "version", 1, 255),
        kind=kind,
        sequence=_integer(data["q"], "sequence"),
        acknowledgement=_integer(data["a"], "acknowledgement"),
        session=_string(data["s"], "session"),
        peer=_string(data["t"], "peer"),
        pawn=_integer(data["p"], "pawn"),
        rules=_integer(data["r"], "rules"),
        payload=payload,
    )
    _validate_envelope(envelope)
    return envelope


def _validate_envelope(envelope: Envelope) -> None:
    if envelope.version != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    _integer(envelope.sequence, "sequence")
    _integer(envelope.acknowledgement, "acknowledgement")
    _string(envelope.session, "session")
    _string(envelope.peer, "peer")
    _integer(envelope.pawn, "pawn")
    _integer(envelope.rules, "rules")
    if not isinstance(envelope.payload, dict):
        raise ProtocolError("payload must be an object")
    _validate_json(envelope.payload)


def digest(payload: dict[str, Any]) -> str:
    _validate_json(payload)
    raw = json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("ascii")).hexdigest()[:16]


@dataclass
class SequenceWindow:
    expected: int = 1

    def classify(self, sequence: int) -> Reason:
        if sequence < self.expected:
            return Reason.STALE_SEQUENCE
        if sequence > self.expected:
            return Reason.SEQUENCE_GAP
        return Reason.OK

    def accept(self, sequence: int) -> None:
        if sequence != self.expected:
            raise ProtocolError(f"expected sequence {self.expected}, got {sequence}")
        self.expected += 1
