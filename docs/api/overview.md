[← Home](../../README.md)

# API overview

Package version **3.62.0** (`Modern_Movement.__version__`), the next minor after the shipped Pre-Sequel baseline 3.61.2. Pre-release work stays on 3.62.0.

Package root: `src/Modern_Movement`. Slam (`features/slam.py`) loads when `game.is_bl2()` is true. Host slam writes are `server_slam_begin`, `server_slam_end`, and `server_slam_impact`. The original Borderlands 2 source is `archive/borderlands-2/Modern_Movement`. The frozen packages are `archive/borderlands-2.sdkmod` and `archive/pre-sequel-3.61.2.sdkmod`.

Bootstrap lives in `__init__.py` (`build_mod`, feature group wiring, enable/disable). It expects Willow2 v3.8 Slammer: Base 1.12, Networking 1.2, Keybinds 1.2, UI Utils 1.5. Shared tick/input lives in `core.py`, including the InputKey hook the keybinds module uses. Host/client roles are in `runtime.py` + `core._role_for`. A client (`NetMode` 3) is a requester even when `Role` is Authority. Slide cancel and a sprint-jump crouch landing stay on the owning client; the host coast for a joiner slide is `_HOST_SLIDES`, not the local crouch machine. Wire protocol helpers are `network.py` (`add_network_functions`), `coop_rpc.py` (`@host`), `protocol.py`, `rules.py`.

Presentation: `hudfx.py` (PostRender), `camera.py`, `fx.py`. Features under `features/` register through `core.register` and optional `authority` / `network` presentation hooks.
