# Modern Movement installation

## Install

1. Build or obtain `dist/Modern_Movement.sdkmod` and confirm the SHA-256 in `dist/Modern_Movement.sdkmod.sha256`.
2. Copy that file into the game's mods folder (`sdk_mods/Modern_Movement.sdkmod`) for Borderlands 2 or The Pre-Sequel.
3. Friends without the mod can still join; their movement stays vanilla. Anyone who has the mod keeps their own abilities.

## Remove duplicate packages

The TPS port uses the canonical root name `Modern_Movement`. Before enabling:

- Remove or disable any older **Modern Movement** package (BL2 builds, duplicate menus, or a second copy in another folder).
- If the mod manager shows two Modern Movement entries, uninstall the older one and keep only this `Modern_Movement.sdkmod`.
- Do not mix the supplied `Pre Sequel Port/Modern_Movement.sdkmod` baseline archive with a newly built co-op package in the same session.

## Dependencies

| Component | Requirement |
|-----------|-------------|
| Game | Borderlands 2 and Borderlands: The Pre-Sequel. Slam loads only in Borderlands 2 |
| Networking | Optional (1.2+). Movement/HUD work without it; each player runs the mod locally. |
| mods_base | Version compatible with your mod manager build |
| texloader | Optional TPS-capable fork for PNG HUD textures |

### texloader fallback

When a known TPS-capable texloader fork is **not** detected, the mod skips external texture installation, logs once, and uses the existing line-drawn HUD indicators. Gameplay is unaffected.

## Co-op setup

1. Every player who wants the abilities installs **and enables** the same `Modern_Movement.sdkmod`.
2. Players without the mod join fine and stay vanilla.
3. Restart the game after copying the sdkmod so hooks/keybinds load.
4. After a session, `Modern_Movement.log.txt` sits in the same folder as the sdkmod. Each player gets their own file. Send both when a joiner's dash or slide does nothing.

## Verification before play

From the repository root (developers):

```text
python -m pytest
python scripts/build_sdkmod.py
python scripts/verify_sdkmod.py --build-first --rebuild
```

Compare the printed SHA-256 with the sidecar on every peer.

## Uninstall / rollback

1. Disable Modern Movement in the mod manager on all peers.
2. Remove `Modern_Movement.sdkmod` from each mods folder.
3. Retain the prior known-good archive (supplied `Pre Sequel Port/Modern_Movement.sdkmod` or last release hash) for rollback testing.