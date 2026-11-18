from __future__ import annotations

from Modern_Movement.input_state import InputBit, InputTracker


def test_input_edges_and_dedup():
    tracker = InputTracker()
    first = tracker.edge(InputBit.JUMP, True, frame=1)
    assert first.pressed == InputBit.JUMP
    dup = tracker.edge(InputBit.JUMP, True, frame=1)
    assert dup.pressed == InputBit(0)
    release = tracker.edge(InputBit.JUMP, False, frame=1)
    assert release.released == InputBit.JUMP


def test_crouch_suppression_until_release():
    tracker = InputTracker()
    tracker.edge(InputBit.CROUCH, True, frame=1)
    tracker.suppress_crouch_until_release()
    assert not tracker.allow_crouch(fresh_press=False)
    assert tracker.allow_crouch(fresh_press=True)
    tracker.edge(InputBit.CROUCH, False, frame=2)
    assert tracker.allow_crouch(fresh_press=False)