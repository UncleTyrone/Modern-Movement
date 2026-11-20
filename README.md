# Modern Movement 3.62.0

One package for Borderlands 2 and Borderlands: The Pre-Sequel. You get a double jump, a dash, mantle, a slide you hold and let go of, holster, and a sprint surge in both games. Borderlands 2 also gets a slam. The Pre-Sequel keeps Oz slam.

PythonSDK is required. Install [Willow2 Mod Manager v3.8, Slammer](https://github.com/bl-sdk/willow2-mod-manager/releases/tag/v3.8) first. That brings Base 1.12, Networking 1.2, Keybinds 1.2, and UI Utils 1.5.

Copy `dist/Modern_Movement.sdkmod` into each game's `sdk_mods` folder and restart. Leave the `.sha256` file and the manifest in `dist`. Enable **Modern Movement** and check the key bindings at the bottom of the options. Controller Dash and Toggle Holster start unbound.

Hold crouch while sprinting, then let go. That stops the slide in both games. Hold crouch through a slide jump and you slide again on landing, after the jump has been in the air for a moment. Let go and you do not. In Borderlands 2, hold crouch in the air for a slam once you are high enough. A short hop pulls you down. A step does not. Sprint Surge is the next sprint press while you are already sprinting, from +30% to +70% of that run. In Borderlands 2 the first sprint press only sprints.

Everyone who wants the moves installs the same file. The listen host writes the movement. A player without the mod stays on normal movement.

The package that builds is `src/Modern_Movement`. The original Borderlands 2 source and the frozen 3.61.2 Pre-Sequel package stay in [archive/](archive/README.md). Do not overwrite those.

```text
python -m pytest
python scripts/build_sdkmod.py
python scripts/willow_harness.py
```

## Pages

- [Play](docs/play.md) covers install, the moves, the HUD, the controller, and co-op.
- [API](docs/api.md) covers the package, the host messages, and how the features fit together.
- [Development](docs/development.md) covers the tree, the build, tests, and how a release goes out.

Nexus paste text: [Borderlands 2](docs/nexus-borderlands-2.md) and [The Pre-Sequel](docs/nexus-pre-sequel.md).

[Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [License](LICENSE)
