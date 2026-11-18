# API overview

Package root: `Pre Sequel Port/Source/Modern_Movement`.

Bootstrap lives in `__init__.py` (`build_mod`, feature group wiring, enable/disable). Shared tick/input lives in `core.py`. Host/client roles are in `runtime.py` + `authority.py`. Wire protocol helpers are `network.py`, `coop_rpc.py`, `protocol.py`, `rules.py`.

Presentation: `hudfx.py` (PostRender), `camera.py`, `fx.py`. Features under `features/` register through `core.register` and optional `authority` / `network` presentation hooks.
