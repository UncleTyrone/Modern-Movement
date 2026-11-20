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


# Willow2 keybinds watch WillowUIInteraction:InputKey. The same event is the hold and the
# release. PressedKeys drops a crouch key that is still held, so this set is the SDK read.
_willow_down: set[str] = set()
_willow_seen = False


def _willow_event_code(event: Any) -> int | None:
    """UE3 EInputEvent: Pressed 0, Released 1, Repeat 2. Names win when the value is an enum."""
    try:
        text = str(getattr(event, "name", None) or getattr(event, "Name", None) or event).lower()
    except Exception:  # noqa: BLE001
        text = ""
    if "released" in text:
        return 1
    if "repeat" in text:
        return 2
    if "double" in text:
        return 3
    if "pressed" in text:
        return 0
    try:
        return int(event)
    except Exception:  # noqa: BLE001
        return None


def note_willow_key(key: Any, event: Any) -> None:
    """Record one SDK input event. Pressed and Repeat count as down. Released clears the key."""
    global _willow_seen
    _willow_seen = True
    token = str(key).strip().strip("'\"").lower()
    if token.startswith("name'") and token.endswith("'"):
        token = token[5:-1].strip().lower()
    code = _willow_event_code(event)
    if code == 1:
        _willow_down.discard(token)
    elif code in (0, 2):
        _willow_down.add(token)


def willow_held(names) -> bool | None:
    """True when one of these keys is down in the SDK input stream, False when it is up.

    None until InputKey has run, so a cold start can still use the game's key list.
    """
    if not _willow_seen:
        return None
    wanted = {str(name).strip().lower() for name in names}
    if not wanted:
        return None
    return any(name in _willow_down for name in wanted)


def reset_willow_keys() -> None:
    global _willow_seen
    _willow_down.clear()
    _willow_seen = False


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
