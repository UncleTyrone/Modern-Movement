# API overview

Package version **3.62.0** (`Modern_Movement.__version__`), the next minor after the shipped Pre-Sequel baseline 3.61.2. Pre-release work stays on 3.62.0.

Package root: `Pre Sequel Port/Source/Modern_Movement`. Slam (`features/slam.py`) loads when `game.is_bl2()` is true. Host slam writes are `server_slam_begin`, `server_slam_end`, and `server_slam_impact`.

Bootstrap lives in `__init__.py` (`build_mod`, feature group wiring, enable/disable). Shared tick/input lives in `core.py`. Host/client roles are in `runtime.py` + `core._role_for`. A client (`NetMode` 3) is a requester even when `Role` is Authority. Slide cancel and a sprint-jump crouch landing stay on the owning client; the host coast for a joiner slide is `_HOST_SLIDES`, not the local crouch machine. Wire protocol helpers are `network.py`, `coop_rpc.py`, `protocol.py`, `rules.py`.

Presentation: `hudfx.py` (PostRender), `camera.py`, `fx.py`. Features under `features/` register through `core.register` and optional `authority` / `network` presentation hooks.
