# Co-op notes

Package **3.62.0** (shipped Pre-Sequel baseline is 3.61.2).

- Prefer `coop_rpc.call_host(fn, *args)` from requesters; handlers resolve `sender.Owner` pawn.
- Dash: Eternal-style host Velocity hold in `_HOST_DASHES` + local predict.
- Slide: `server_slide_enter(crouched_pct, distance_percent, dir_x, dir_y, speed_percent)`. CrouchedPct decay is per `player_id`. Joiner and host coast Velocity along that direction after forward is released. Releasing crouch sends `server_slide_exit`.
- Slam (Borderlands 2): `server_slam_begin` / `server_slam_end` / `server_slam_impact`. The Pre-Sequel does not arm these.
- Double Jump: host applies requester `(vx,vy,vz)` and `max_jumps`; do not re-read host strength.
- Mantle: host replays climb plan; do not replace host replay tables.
- Networking optional: without it, each installed peer still runs local movement/HUD.
