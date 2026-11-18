from __future__ import annotations

import pytest

from Modern_Movement.protocol import (
    MAX_FRAME_BYTES,
    Envelope,
    Kind,
    ProtocolError,
    Reason,
    SequenceWindow,
    decode,
    digest,
    encode,
)


def _sample(**payload):
    return Envelope(
        kind=Kind.INTENT,
        sequence=1,
        acknowledgement=0,
        session="sess",
        peer="peer-a",
        pawn=42,
        rules=7,
        payload=payload or {"feature": "dash", "op": "start"},
    )


def test_encode_decode_roundtrip():
    env = _sample()
    raw = encode(env)
    restored = decode(raw)
    assert restored == env


def test_frame_size_bound():
    big = "x" * (MAX_FRAME_BYTES - 80)
    env = _sample(note=big)
    with pytest.raises(ProtocolError):
        encode(env)


def test_decode_rejects_extra_keys():
    raw = encode(_sample())
    broken = raw.replace('"feature"', '"extra","feature"', 1)
    with pytest.raises(ProtocolError):
        decode(broken)


def test_sequence_window():
    window = SequenceWindow(expected=3)
    assert window.classify(2) is Reason.STALE_SEQUENCE
    assert window.classify(5) is Reason.SEQUENCE_GAP
    assert window.classify(3) is Reason.OK
    window.accept(3)
    assert window.expected == 4


def test_digest_stable():
    payload = {"b": 2, "a": 1, "nested": {"z": 1}}
    first = digest(payload)
    second = digest({"a": 1, "b": 2, "nested": {"z": 1}})
    assert first == second