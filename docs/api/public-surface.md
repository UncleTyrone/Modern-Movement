# Public surface

Intended entry points for tooling and tests:

| Symbol | Module | Role |
|--------|--------|------|
| `build_mod` | `__init__` (via pyproject entry) | Mod manager load |
| `core.register` / `unregister` | `core` | Feature tick/input hooks |
| `authority.register_feature` | `authority` | Host-side controllers |
| `network.register_presentation` | `network` | Client presentation mirrors |
| `coop_rpc.server_*` | `coop_rpc` | `@host` RPC handlers |
| `hudfx.jump_state` / dash/slide/surge helpers | `hudfx` | Indicator state |
| `host_apply_*` / `host_enter_juso` / `host_begin_slam` | feature modules | Host mutation used by RPCs |
| `__version__` | `__init__` | `3.62.0` until this package ships. Handshake field `package` matches it |

Everything else is internal; prefer tests against host helpers over private tick loops.
