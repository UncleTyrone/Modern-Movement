# Modern Movement 3.62.0

One package for Borderlands 2 and Borderlands: The Pre-Sequel. Double jump, dash, mantle, slide, holster, and sprint surge run in both games. Borderlands 2 also gets slam. The Pre-Sequel keeps its own Oz slam.

PythonSDK is required: [Willow2 Mod Manager v3.8, Slammer](https://github.com/bl-sdk/willow2-mod-manager/releases/tag/v3.8).

## Install

Full steps are in [docs/INSTALL.md](docs/INSTALL.md).

1. Install Willow2 v3.8 in both games. That brings Base 1.12, Networking 1.2, Keybinds 1.2, and UI Utils 1.5.
2. Copy `dist/Modern_Movement.sdkmod` into each game's `sdk_mods` folder. Leave the `.sha256` file and the manifest in `dist`.
3. Enable **Modern Movement** and check the key bindings at the bottom of the mod options.
4. Restart the game after copying the file.

## What you get

| Feature | Where | What it does |
|---------|--------|----------------|
| Double Jump | Both | Another jump in the air. The counter can stay off. |
| Dash | Both | Ground or air dash, a ready mark, and an optional perfect dodge. |
| Mantle / Vault | Both | Climb a ledge in the air, or hop a low obstacle on the ground. |
| Slide | Both | Hold crouch while sprinting. Let go and the slide stops. Hold crouch through a jump and you slide again on landing. |
| Surface | Both | Dust, wind, and a slam ring. Missing effects are skipped. |
| Holster | Both | Put the gun away on a key, or while sprinting. |
| Sprint Surge | Both | Press sprint again while already sprinting. Speed climbs from +30% to +70% of the run you already have. Borderlands 2 does not start this on the first sprint press. |
| Slam | Borderlands 2 | Hold crouch in the air. A high jump slams. A short hop pulls you down after it peaks. |

A slide is the ground scrape only. A slam plays its impact when you land. Super sprint keeps the game's own sprinting sounds. A dash plays a whoosh. The beep is only the ready tone.

## Co-op

Every player who wants the moves installs and enables the same file. The listen host writes the movement. Joiners send the same dash, slide, jump, mantle, surge, and slam through Networking 1.2. A player without the mod stays on normal movement and does not block the others.

Details: [docs/usage/coop.md](docs/usage/coop.md).

## Repository

| Path | What it is |
|------|------------|
| `src/Modern_Movement` | The package that builds. Version 3.62.0. |
| `archive/borderlands-2/` | The original Borderlands 2 source, kept as it was, under `Modern_Movement`. |
| `archive/borderlands-2.sdkmod` | The frozen original package. Do not overwrite it. |
| `archive/pre-sequel-3.61.2.sdkmod` | The shipped Pre-Sequel 3.61.2 package. Do not overwrite it. |
| `dist/Modern_Movement.sdkmod` | The package you install. |
| `docs/` | Install, usage, and API. |

## Develop

```text
python -m pytest
python scripts/build_sdkmod.py
python scripts/willow_harness.py
```

Docs: [docs/index.md](docs/index.md). Release steps: [docs/development/releasing.md](docs/development/releasing.md).

## License

MIT. See [LICENSE](LICENSE).
