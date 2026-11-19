# Modern Movement 3.62.0 (Borderlands 2 and The Pre-Sequel)

Double Jump, Dash, Mantle, Slide, Holster, and Sprint Surge, with host-authoritative co-op. Borderlands 2 also gets Slam.

## Install

See [docs/INSTALL.md](docs/INSTALL.md). Short version:

1. Take `dist/Modern_Movement.sdkmod` (verify SHA-256 in `dist/Modern_Movement.sdkmod.sha256`).
2. Copy it into the game's `sdk_mods` folder (Borderlands 2 or The Pre-Sequel).
3. Enable the mod; check key bindings at the bottom of the mod options.

## Features

| Feature | Summary |
|---------|---------|
| Double Jump | Mid-air boost with optional jump-counter HUD |
| Dash | Ground/air dash with ready pip and perfect-dodge feedback |
| Mantle / Vault | Jump-to-ledge climbs and low obstacle vaults |
| Slide | Sprint-crouch slides. Hold crouch through a real slide jump to slide on landing. On co-op, releasing forward keeps the coast |
| Holster | Manual + sprint holster |
| Sprint Surge | Second sprint press for a ramping speed boost |
| Slam | Borderlands 2 only. Crouch in the air to slam. The Pre-Sequel uses native Oz slam |

## Co-op

Each peer who installs the mod runs their own options. The listen host owns movement authority; joiners send intents. Players without the mod stay vanilla. Details: [docs/usage/coop.md](docs/usage/coop.md).

## Develop

```text
python -m pytest
python scripts/build_sdkmod.py
```

Docs index: [docs/index.md](docs/index.md). Release steps: [docs/development/releasing.md](docs/development/releasing.md).

## License

MIT — see [LICENSE](LICENSE).
