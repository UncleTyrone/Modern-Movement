"""Normalized local input edges and TPS Slide ownership."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag
from typing import Any


class InputBit(IntFlag):
    JUMP = 1
    CROUCH = 2
    SPRINT = 4
    DASH = 8
    HOLSTER = 16


@dataclass
class InputSnapshot:
    held: InputBit = InputBit(0)
    changed: InputBit = InputBit(0)
    pressed: InputBit = InputBit(0)
    released: InputBit = InputBit(0)
    frame: int = 0


@dataclass
class InputTracker:
    held: InputBit = InputBit(0)
    frame: int = 0
    _seen: set[tuple[int, int, bool]] = field(default_factory=set)
    crouch_suppressed_until_release: bool = False

    def begin_frame(self, frame: int) -> None:
        if frame != self.frame:
            self.frame = frame
            self._seen.clear()

    def edge(self, bit: InputBit, down: bool, frame: int) -> InputSnapshot:
        self.begin_frame(frame)
        token = (frame, int(bit), down)
        if token in self._seen:
            return InputSnapshot(held=self.held, frame=frame)
        self._seen.add(token)

        was_down = bool(self.held & bit)
        if down:
            self.held |= bit
        else:
            self.held &= ~bit
            if bit == InputBit.CROUCH:
                self.crouch_suppressed_until_release = False
        changed = bit if was_down != down else InputBit(0)
        return InputSnapshot(
            held=self.held,
            changed=changed,
            pressed=bit if changed and down else InputBit(0),
            released=bit if changed and not down else InputBit(0),
            frame=frame,
        )

    def suppress_crouch_until_release(self) -> None:
        if self.held & InputBit.CROUCH:
            self.crouch_suppressed_until_release = True

    def allow_crouch(self, fresh_press: bool) -> bool:
        return not self.crouch_suppressed_until_release or fresh_press


def pressed_keys(pc: Any) -> set[str] | None:
    try:
        return {str(key) for key in pc.PlayerInput.PressedKeys}
    except Exception:
        return None


def binding_conflicts(pc: Any, mod_keys: dict[str, str | None]) -> dict[str, list[str]]:
    """Best-effort native binding collision report."""
    native: dict[str, list[str]] = {}
    try:
        bindings = pc.PlayerInput.Bindings
    except Exception:
        return {}
    for binding in bindings:
        try:
            key = str(binding.Name)
            command = str(binding.Command)
        except Exception:
            continue
        native.setdefault(key, []).append(command)
    return {
        name: native[key]
        for name, key in mod_keys.items()
        if key is not None and key in native and native[key]
    }
