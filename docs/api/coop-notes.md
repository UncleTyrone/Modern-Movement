# Co-op notes

Package **3.62.0** (shipped Pre-Sequel baseline is 3.61.2).

- A joining client is `LOCAL_REQUESTER` when `NetMode` is 3, even if `Role` is Authority. That client sends `coop_rpc.call_host`. The listen host (`NetMode` 2) stays `LOCAL_HOST`.
- Prefer `coop_rpc.call_host(fn, *args)` from requesters. `sender` is the caller's PlayerReplicationInfo. If `Owner.Pawn` is empty, the host walks `PawnList` for that PlayerID before it gives up.
- Dash: Eternal-style host Velocity hold in `_HOST_DASHES` + local predict.
- Slide: `server_slide_enter(crouched_pct, distance_percent, dir_x, dir_y, speed_percent)`. CrouchedPct decay is per `player_id`. Joiner and host coast Velocity along that direction after forward is released. Releasing crouch sends `server_slide_exit`. A slide jump sends `server_slide_jump(vx, vy, vz)` so the host holds the launch. Slide cancel (`state.chain`, the `DuckPressed` block) and a sprint-jump crouch landing (`state.air_slide`) run on the owning client. The landing slide is a normal `server_slide_enter`, aimed where that player is facing. The host does not replay that keyboard on the joiner pawn.
- Slam (Borderlands 2): `server_slam_begin` / `server_slam_end` / `server_slam_impact`. The Pre-Sequel does not arm these.
- Double Jump: host applies requester `(vx,vy,vz)` and `max_jumps`; do not re-read host strength.
- Mantle: host replays climb plan; do not replace host replay tables.
- Networking optional: without it, each installed peer still runs local movement/HUD.
