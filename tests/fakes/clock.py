from __future__ import annotations


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, dt: float) -> float:
        self._now += float(dt)
        return self._now