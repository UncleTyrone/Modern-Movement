# `coop_rpc.py`

Host RPC surface (`server_dash`, `server_double_jump`, `server_slide_enter(pct, distance, dir_x, dir_y)` / exit, mantle, surge). Identifiers are stable `ModernMovement:*` strings. `call_host` no-ops safely when Networking stubs are present. Slide enter carries the entry direction so the host coast matches the joiner.
