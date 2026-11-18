# Modern Movement 3.62.1

Borderlands: The Pre-Sequel movement package for the Willow2 SDK. Double Jump, Dash, Mantle, Slide, Holster, and Sprint Surge ship together in one `Modern_Movement.sdkmod`. This is the first published build of the TPS port (3.62.0 co-op foundation plus 3.62.1 HUD and per-player polish).

**Package:** `dist/Modern_Movement.sdkmod`  
**SHA-256:** `fcf51ffc93e385c309d62e76849e484c5595f7c72252e30aff813c06ff163b7b`

Install this exact file on every peer who wants the abilities. Confirm the hash against `dist/Modern_Movement.sdkmod.sha256` before enabling it.

## Highlights

- Listen host owns custom movement. Joiners send intents and keep their own option values.
- Jump Counter HUD is back (`mm_jump_chev`), off by default.
- Dash Ready Indicator defaults on, with its own Perfect Dodge Effect toggle.
- Camera and feel sliders are back under each feature's Settings.
- A joiner's Slide Distance and Double Jump strength / extra jumps follow that player, including over co-op.
- Native TPS Slam and Oz AirBoost stay in the game. Custom Slam is omitted from this package.

## Features

| Feature | What you get |
|---------|----------------|
| Double Jump | Mid-air boost, coyote time, optional jump-counter chevrons |
| Dash | Ground or air dash, ready pip, optional damage reduction and perfect-dodge burst |
| Mantle / Vault | Ledge climbs and low-obstacle vaults |
| Slide | Sprint-crouch slide; co-op mirrors with CrouchedPct only |
| Holster | Manual holster and sprint holster |
| Sprint Surge | Second sprint press for a speed boost that ramps up |

Players who do not install the mod can still join. Their movement stays vanilla.

## Changes in 3.62.1

### Added

- Double Jump Jump Counter (`mm_jump_chev`) with an On/Off toggle. Default is Off.
- Dash Perfect Dodge Effect toggle for the ECHO chevron burst.
- Per-player Slide Distance on the timed host slide path, sent in the RPC payload.
- Host double jump applies the requester's impulse and `max_jumps`.
- Repository docs (`docs/`), LICENSE, SECURITY, CONTRIBUTING, and `.gitignore`.

### Changed

- Mods-page description lists the six shipped features.
- Dash Ready Indicator defaults On.
- Camera and feel sliders are visible again under each feature's Settings. Temporary labels are gone.
- Sprint Surge Camera Tilt and Mantle camera/height options are visible again.
- Package allowlist includes the jump-counter textures.

### Fixed

- Joiner slide length followed the host Slide Distance slider. It now uses the requester's percent.
- Remote double jump applied the host's Extra Jumps and Strength. It now uses the requester's values.

## Included from 3.62.0

No earlier TPS build was tagged. This package includes that co-op foundation:

- Host-authoritative movement through `coop_rpc` (Networking 1.2). Clients send intents; the listen host is the custom-gameplay writer.
- TPS-only package. The mod stays inactive outside The Pre-Sequel.
- Controller Dash and Toggle Holster default to unbound, so they leave the TPS D-pad weapon slots alone.
- Custom Slam is excluded from the sdkmod allowlist. Slide jump, sprint, and off-cliff exits clear crouch so native Slam is left unarmed.

## Install

1. Remove or disable any older Modern Movement package (Borderlands 2 builds, loose folders, or a second copy).
2. Copy `Modern_Movement.sdkmod` into the Willow2 `sdk_mods` folder.
3. Enable the mod and check key bindings at the bottom of the mod options.
4. Restart the game after copying the file so hooks and keybinds load.

Full steps: [docs/INSTALL.md](../docs/INSTALL.md).

texloader is optional. Without a TPS-capable texloader fork, indicators draw as lines and gameplay is unchanged. Controller Dash and Toggle Holster start unbound; rebind them in the menu if you want them on a pad.

## Verification

Automated checks in this tree cover protocol, runtime, rules, gravity, input, the package allowlist, and dual-player co-op unit tests (`pytest`, 48 passed), plus a deterministic sdkmod build.

Two-player and four-player sessions in The Pre-Sequel remain **LIVE_REQUIRED**. Track them in [LIVE_VALIDATION.md](LIVE_VALIDATION.md) and [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md). In-game co-op movement is still awaiting that live proof.

## Rollback

Keep the supplied `Pre Sequel Port/Modern_Movement.sdkmod` archive unchanged as the known-good pre-co-op rollback artifact. Load either that archive or this co-op package in a session, not both.
