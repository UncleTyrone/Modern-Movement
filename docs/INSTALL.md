# Install Modern Movement

Version **3.62.0**. The same `Modern_Movement.sdkmod` runs in Borderlands 2 and Borderlands: The Pre-Sequel.

## What you need

Install [Willow2 Mod Manager v3.8 (Slammer)](https://github.com/bl-sdk/willow2-mod-manager/releases/tag/v3.8) in each game before this mod. PythonSDK is required. These are the pieces this mod calls:

| Piece | Version | What this mod uses it for |
|-------|---------|---------------------------|
| Game | Borderlands 2, The Pre-Sequel | Slam loads only in Borderlands 2. The Pre-Sequel keeps Oz slam. |
| Base (`mods_base`) | 1.12 | Options, keybinds, hooks, `get_pc`, `ENGINE` |
| Networking | 1.2 | Host messages for dash, slide, jump, mantle, surge, and slam |
| Keybinds | 1.2 | Crouch hold and release follow the same InputKey event |
| UI Utils | 1.5 | A short HUD note if a required helper did not load |
| Texture loaders | Inside this package | Borderlands 2 uses texloader 1.2. The Pre-Sequel uses the 1.1.9 fork. A separate texloader install is not required. |

If a texloader is already installed, that copy is used. If an image cannot be created, that indicator draws with lines. Movement does not wait on it.

## Install the package

1. Build `dist/Modern_Movement.sdkmod`, or take a copy whose SHA-256 matches `dist/Modern_Movement.sdkmod.sha256`.
2. Copy **only** `Modern_Movement.sdkmod` into both folders:
   - `D:\SteamLibrary\steamapps\common\Borderlands 2\sdk_mods`
   - `D:\SteamLibrary\steamapps\common\BorderlandsPreSequel\sdk_mods`
3. Leave `Modern_Movement.sdkmod.sha256` and `Modern_Movement.manifest.json` in `dist`. Do not copy them into a game folder.
4. Enable **Modern Movement** in the mod menu.
5. Open the key bindings at the bottom of the mod options. Controller Dash and Toggle Holster start unbound.
6. Restart the game so the hooks and keybinds load.

A build from this tree copies the package into both of those folders and leaves every other file there alone, including `Modern_Movement.log.txt`.

## One copy only

The package name is `Modern_Movement`. Before you enable it:

- Disable or remove any older Modern Movement package, loose folder, or second menu entry.
- If the mod menu shows two Modern Movement entries, keep this file and remove the other.
- Do not enable `archive/pre-sequel-3.61.2.sdkmod` in the same session as a newly built package. That file is the frozen 3.61.2 baseline, kept in the repository. It is not the install file.

## Co-op

1. Each player who wants the moves installs and enables this same file.
2. Players without the mod can join. Their movement stays the game's own.
3. Restart after copying the file.
4. After you play, `Modern_Movement.log.txt` is written next to the sdkmod. Each machine has its own log.

## Check a build

From the repository root:

```text
python -m pytest
python scripts/build_sdkmod.py
python scripts/verify_sdkmod.py --build-first --rebuild
python scripts/willow_harness.py
```

`willow_harness.py` reads the Willow2 helpers installed in both games and checks this package calls them. Compare the printed SHA-256 with `dist/Modern_Movement.sdkmod.sha256` on every machine.

## Remove it

1. Disable Modern Movement in the mod menu.
2. Delete `Modern_Movement.sdkmod` from each game's `sdk_mods` folder.
3. The frozen packages stay in `archive/`. They are the rollback copies, not a second install.
