# SWEEP_CHECKLIST (Phase B — frozen)

Implement all items in Phase S in one pass. No mid-sweep scope adds.

## B.1 Product / in-game

- [x] Mods-page description Original voice (no slam/omission language)
- [x] Top docstring lists six features
- [x] Jump counter HUD + `counter_option` (default Off) + `mm_jump_chev` in `_IMAGES` + PostRender
- [x] Dash pip default On
- [x] Perfect Dodge Effect BoolOption
- [x] Every shipped indicator has On/Off
- [x] Strip `Temporary:`; expose DJ/slide/mantle/dash/surge camera sliders in Settings
- [x] Joiner slide distance on timed/juso path (RPC + host dict)
- [x] Host REMOTE_AUTHORITY DJ uses impulse payload; track jumps per player_id without host strength
- [x] Regression tests: dual strength / dual slide distance
- [x] Phase R REJECT stays out

## B.2 Repository

- [x] `.gitignore`
- [x] `README.md`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`
- [x] `docs/` index, install, usage/*, api/*, development/*
- [x] Release process in docs/development/releasing.md

## B.3 Ship

- [x] Full pytest
- [x] Rebuild sdkmod; CHANGELOG SHA
- [x] Local git init + one commit (no push)
