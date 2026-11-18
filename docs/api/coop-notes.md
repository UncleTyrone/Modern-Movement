# Co-op notes

- Prefer `coop_rpc.call_host(fn, *args)` from requesters; handlers resolve `sender.Owner` pawn.
- Dash: Eternal-style host Velocity hold in `_HOST_DASHES` + local predict.
- Slide: `server_slide_enter(crouched_pct, distance_percent, dir_x, dir_y)`. CrouchedPct decay is per `player_id`. Joiner and host coast Velocity along that direction after forward is released.
- Double Jump: host applies requester `(vx,vy,vz)` and `max_jumps`; do not re-read host strength.
- Mantle: host replays climb plan; do not replace host replay tables.
- Networking optional: without it, each installed peer still runs local movement/HUD.
