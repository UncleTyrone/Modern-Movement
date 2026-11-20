# `hudfx.py`

PostRender ECHO HUD: dash arrows, ready pip, perfect-dodge burst, jump counter (`jump_state` / `mm_jump_chev`), slide bar, surge arcs. The draw prefers `WillowHUD:PostRender` so the marks sit on top of the game HUD. Textures load through the vendored texloader for the current game (`textures_load.py`, `native/bl2`, `native/tps`). An already installed texloader is used instead. A failed image draw falls back to lines. Slam indicators run only when Borderlands 2 loaded Slam.
