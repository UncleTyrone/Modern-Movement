# `features/slam.py`

Borderlands 2 only. `game.is_bl2()` gates the tick. The Pre-Sequel does not register this feature, and Oz slam stays the game's own.

Hold crouch in the air. `_slam_kind` is a full slam once clearance reaches the jump-height requirement, and a pull once a shorter hop has peaked. A crouch held through a slide jump does not slam. The hold is the Willow2 InputKey event, with the keyboard as a fallback before that event has arrived. A jump with crouch up is left alone.

`server_slam_begin`, `server_slam_end`, and `server_slam_impact` are the host calls. The impact plays when you land. There is no sound on the way down. A full slam adds the small explosive crack. A pull plays the landing only. The crouch that started the slam does not become a slide.
