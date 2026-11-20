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


def test_willow_input_key_holds_and_releases():
    from Modern_Movement import input_state

    input_state.reset_willow_keys()
    assert input_state.willow_held(("c",)) is None
    input_state.note_willow_key("C", 0)
    assert input_state.willow_held(("c",)) is True
    input_state.note_willow_key("C", 2)
    assert input_state.willow_held(("c",)) is True
    input_state.note_willow_key("C", 1)
    assert input_state.willow_held(("c",)) is False
    input_state.note_willow_key("LeftControl", "IE_Pressed")
    assert input_state.willow_held(("leftcontrol",)) is True
    input_state.note_willow_key("LeftControl", "IE_Released")
    assert input_state.willow_held(("leftcontrol",)) is False
    input_state.reset_willow_keys()
    assert input_state.willow_held(("c",)) is None


def test_crouch_suppression_until_release():
    tracker = InputTracker()
    tracker.edge(InputBit.CROUCH, True, frame=1)
    tracker.suppress_crouch_until_release()
    assert not tracker.allow_crouch(fresh_press=False)
    assert tracker.allow_crouch(fresh_press=True)
    tracker.edge(InputBit.CROUCH, False, frame=2)
    assert tracker.allow_crouch(fresh_press=False)