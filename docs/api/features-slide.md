# `features/slide.py`

Sprint-crouch slides. Network path: CrouchedPct decay plus `_coast_slide` on the entry direction (`host_enter_juso(..., distance_percent, dir_x, dir_y)`). `_distance_scale` lengths the decay. Host service and PlayerMove post both re-apply the coast. Slide indicator HUD. No Mesh.Z dips.
