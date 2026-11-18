from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SentMessage:
    channel: str
    target: Any
    payload: str


@dataclass
class FakeTransport:
    sent: list[SentMessage] = field(default_factory=list)

    def targeted(self, target: Any, payload: str) -> None:
        self.sent.append(SentMessage("targeted", target, payload))

    def broadcast(self, payload: str) -> None:
        self.sent.append(SentMessage("broadcast", None, payload))

    def clear(self) -> None:
        self.sent.clear()