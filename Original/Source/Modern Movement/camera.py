"""Shared camera effects: shake and lean, from any feature.

Features never touch the camera themselves. Each asks for offsets by name every tick it wants
them (request), and core applies the sum once per tick (apply), after every feature has run:

  eye   - eye-height offset in units (bob). Added as a change from what was applied last tick,
          so the game's own eye-height easing (crouching, landing) keeps working.
  roll  - view tilt in degrees, added on top of the view's own roll. Roll never changes where you aim.
  pitch - a brief nod in degrees (+ = up). Pitch IS your aim in this game, so it is added as a
          change from what was applied last tick (your own mouse movement is kept) and taken out
          exactly when the request stops: your aim ends where it would have been.

When nothing is requested any more, every offset is taken back out exactly. Only numbers are
kept between ticks, never game objects.
"""

from __future__ import annotations

import math

_requests: dict = {}    # name -> (eye, roll, pitch), cleared after each apply
_eye_applied = 0.0
_roll_applied = False
_roll_written = None    # the roll value written last tick, and how much of it is ours
_roll_added = 0
_pawn_name = ""
_pitch_applied = 0      # pitch offset currently applied, in rotation units (65536 = 360 degrees)


def request(name: str, eye: float = 0.0, roll: float = 0.0, pitch: float = 0.0) -> None:
    """Ask for these offsets this tick (call every tick while the effect runs)."""
    _requests[name] = (eye, roll, pitch)


def wave(t: float) -> tuple[float, float]:
    """(bob, tilt) in -1..1: two mixed frequencies each, so a shake feels like texture,
    not a metronome."""
    bob = math.sin(t * 2.0 * math.pi * 9.0) * 0.7 + math.sin(t * 2.0 * math.pi * 13.7 + 1.3) * 0.3
    tilt = math.sin(t * 2.0 * math.pi * 5.3 + 0.4) * 0.6 + math.sin(t * 2.0 * math.pi * 11.1) * 0.4
    return bob, tilt


def apply(pc, pawn) -> None:
    """Once per tick (core): apply the sum of this tick's requests, or take offsets out."""
    global _eye_applied, _roll_applied, _pitch_applied, _roll_written, _roll_added
    eye = sum(r[0] for r in _requests.values())
    roll = sum(r[1] for r in _requests.values())
    pitch = sum(r[2] for r in _requests.values())
    _requests.clear()

    if pawn is not None and (eye or _eye_applied):
        try:
            pawn.EyeHeight = float(pawn.EyeHeight) + (eye - _eye_applied)
            _eye_applied = eye
        except Exception:  # noqa: BLE001
            _eye_applied = 0.0
    if pc is not None and (pitch or _pitch_applied):
        try:
            want = int(round(pitch * 65536.0 / 360.0))
            if want != _pitch_applied:
                pc.Rotation.Pitch = (int(pc.Rotation.Pitch) + (want - _pitch_applied)) & 0xFFFF
                _pitch_applied = want
        except Exception:  # noqa: BLE001
            _pitch_applied = 0
    global _pawn_name
    name = str(pawn)
    if name != _pawn_name:              # a new map or respawn resets the view: nothing of ours is in it
        _pawn_name = name
        _roll_added = 0
    if pc is not None and (roll or _roll_applied):
        # added on top of the view's roll (so it combines with other mods that tilt the view): the
        # roll added last tick is taken out first
        try:
            current = int(pc.Rotation.Roll) & 0xFFFF
            base = (current - _roll_added) & 0xFFFF   # our part comes out; other mods' parts stay
            want = int(round(roll * 65536.0 / 360.0))
            new = (base + want) & 0xFFFF
            if new != current:
                pc.Rotation.Roll = new
            _roll_written, _roll_added = new, want
            _roll_applied = bool(want)
        except Exception:  # noqa: BLE001
            _roll_applied = False
            _roll_written, _roll_added = None, 0


def reset(pc=None, pawn=None) -> None:
    """Take every offset out now (mod disabled)."""
    _requests.clear()
    apply(pc, pawn)
