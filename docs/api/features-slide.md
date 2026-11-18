# `features/slide.py`

Sprint-crouch slides. Network path: CrouchedPct decay plus `_coast_slide` on the entry direction (`host_enter_juso(..., distance_percent, dir_x, dir_y, speed_percent)`). `_distance_scale` lengths the decay. `_speed_scale` multiplies coast speed only (default 120). Host service and PlayerMove post both re-apply the coast. The owning client ends the slide on crouch release (`stood up` → `server_slide_exit`); the host copy does not cancel from a missing `bDuck`. `release_player` drops holds on respawn or travel. Slide indicator HUD. No Mesh.Z dips.
