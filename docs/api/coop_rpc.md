[← Home](../../README.md)

# `coop_rpc.py`

Package **3.62.0**. Host RPC surface: `server_dash`, `server_double_jump`, `server_slide_enter(pct, distance, dir_x, dir_y, speed_percent)` / `server_slide_exit` / `server_slide_jump(vx, vy, vz)`, mantle, surge, and Borderlands 2 slam (`server_slam_begin`, `server_slam_end`, `server_slam_impact`). Identifiers are stable `ModernMovement:*` strings. `call_host` no-ops safely when Networking stubs are present. Slide enter carries the entry direction and Slide Speed so the host coast matches the joiner. Slam RPCs run only when `game.is_bl2()` is true.
