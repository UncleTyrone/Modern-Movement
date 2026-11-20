# Architecture

The live package is `src/Modern_Movement`. Version **3.62.0**, the next minor after the shipped Pre-Sequel package 3.61.2. Pre-release edits stay on 3.62.0.

```text
src/Modern_Movement/
  __init__.py     build_mod, feature groups, Willow2 version check
  core.py         tick bus, jump key, busy, InputKey hold
  authority.py    host FeatureControllers
  network.py      Networking 1.2 attach and presentation
  coop_rpc.py     @host handlers
  features/       gameplay and OPTIONS
  hudfx.py        PostRender indicators
  runtime.py      PlayerContext roles
```

Frozen originals live in `archive/`. Builds write `dist/Modern_Movement.sdkmod` and do not replace those files.

Co-op model: a requester predicts locally where needed, the host mutates the sender pawn, and presentation peers draw HUD and effects only. Slide length follows the crouch-percent decay plus an entry-direction coast. Dash uses a short host velocity hold. Slam follows the same host-write pattern on Borderlands 2 and stays off on The Pre-Sequel.

Willow2 v3.8 supplies the helpers: `mods_base` (`get_pc`, `ENGINE`, hooks, keybinds, options), Networking 1.2 (`@host`, `@targeted`, `add_network_functions`), Keybinds 1.2 (the InputKey event), and UI Utils 1.5.
