# Modern Movement (Borderlands: The Pre-Sequel)

Double Jump, Dash, Mantle, Slide, Holster, and Sprint Surge — one Willow2 SDK package with host-authoritative co-op.

## Install

See [docs/INSTALL.md](docs/INSTALL.md). Short version:

1. Take `dist/Modern_Movement.sdkmod` (verify SHA-256 in `dist/Modern_Movement.sdkmod.sha256`).
2. Copy it into your Willow2 `sdk_mods` folder.
3. Enable the mod; check key bindings at the bottom of the mod options.

## Features

| Feature | Summary |
|---------|---------|
| Double Jump | Mid-air boost with optional jump-counter HUD |
| Dash | Ground/air dash with ready pip and perfect-dodge feedback |
| Mantle / Vault | Jump-to-ledge climbs and low obstacle vaults |
| Slide | Sprint-crouch slides. On co-op, releasing forward keeps the coast |
| Holster | Manual + sprint holster |
| Sprint Surge | Second sprint press for a ramping speed boost |

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
