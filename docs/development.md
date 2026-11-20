[← Home](../README.md)

# Development

The live tree is `src/Modern_Movement`. Version 3.62.0 until this package ships. The original Borderlands 2 source sits in `archive/borderlands-2/Modern_Movement` and is not the build. `archive/borderlands-2.sdkmod` and `archive/pre-sequel-3.61.2.sdkmod` are frozen. Do not overwrite them and do not edit anything under `archive/`.

```text
src/Modern_Movement/
  __init__.py      build_mod, feature groups, Willow2 check
  core.py          tick bus, jump key, busy, InputKey
  runtime.py       who this player is
  authority.py     host feature controllers
  network.py       Networking 1.2
  coop_rpc.py      host messages
  features/        the moves
  hudfx.py         the marks around the crosshair
  fx.py            sounds
```

A requester predicts, the host writes that player's pawn, and everyone else only draws. Slide length is the crouch-percent decay plus a coast along the direction they entered. Dash is a short host velocity hold. Slam is the same idea on Borderlands 2 and is not registered on The Pre-Sequel.

Willow2 v3.8 is the helper set: `mods_base`, Networking 1.2, Keybinds 1.2, and UI Utils 1.5. Python on this machine for tests is 3.10. The game's PythonSDK is 3.14, so do not import the Willow2 zips from the test run. `scripts/willow_harness.py` reads those zips instead.

## Build and test

From the repository root:

```text
python -m pytest
python scripts/build_sdkmod.py
python scripts/verify_sdkmod.py --build-first
python scripts/triple_check.py
python scripts/willow_harness.py
python scripts/dual_game_harness.py
```

`pythonpath` is `src` plus the repository root. The allowlist is `build/package-allowlist.json`. A new `.py` under the package has to be on that list or `scripts/audit_sources.py` fails. The build writes `dist/Modern_Movement.sdkmod`, the `.sha256` sidecar, and `dist/Modern_Movement.manifest.json`. It does not touch the two archive packages.

After a build, copy only the sdkmod into both games:

- `D:\SteamLibrary\steamapps\common\Borderlands 2\sdk_mods`
- `D:\SteamLibrary\steamapps\common\BorderlandsPreSequel\sdk_mods`

Leave the hash file and the manifest in `dist`. Leave every other file in those folders alone, including `Modern_Movement.log.txt`.

`tests/test_coop_host_authority.py` covers the host writes. `dual_game_harness.py` boots the package as Borderlands 2, with slam, and as The Pre-Sequel, without it. Tests that need a slope set `slide.slope_slider.value` themselves. The autouse fixture turns slope and the surge ramp to 0.

## Releasing

The changelog section for this work is `3.62.0` in `CHANGELOG.md`. Open 3.62.1 only after 3.62.0 has actually shipped. Say what the player does, what they get, and which game it is. Borderlands 2 slam and Pre-Sequel Oz slam stay separate.

When the behavior changes, update `CHANGELOG.md`, `reports/RELEASE_NOTES.md`, and this set of pages in the same turn. After a rebuild, put the new SHA-256 in the release notes and in `reports/LIVE_COOP_CHECKLIST.md`. The home page is `README.md`. Play, API, and development are the three pages under `docs/`.

The usual release is: tests, build, copy the sdkmod into both games, commit locally once it has been played and it works. Do not push unless asked. The publisher then tags a GitHub Release and attaches `dist/Modern_Movement.sdkmod` and the `.sha256` file. Paste the hash into the release notes.

Nexus paste text for the two game pages is `docs/nexus-borderlands-2.md` and `docs/nexus-pre-sequel.md`.

The installed games were compared file by file in `reports/WILLOW2_DIFF.md`. The PythonSDK and the Willow2 helpers match. Startup, WillowGame, the Wwise banks, PhysX, and Oz content do not. Sound and particle calls stay try-lists per game.

## Commits

Do not commit while a change is still being tried. After it has been played and it works, one commit. The message says why. The changelog is already in that commit. Do not stack commits titled only with the version number. Do not force-push `main` or `master` unless that was asked for.

`CONTRIBUTING.md`, `SECURITY.md`, and `CHANGELOG.md` stay at the repository root. Historical audits in `reports/LINE_AUDIT.md` and `reports/PEER_MOD_RESEARCH.md` stay as the record of that pass.
