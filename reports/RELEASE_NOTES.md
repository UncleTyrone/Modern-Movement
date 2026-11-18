# Modern Movement 3.62.2

Borderlands: The Pre-Sequel movement package for the Willow2 SDK. Double Jump, Dash, Mantle, Slide, Holster, and Sprint Surge ship together in one `Modern_Movement.sdkmod`.

**Package:** `dist/Modern_Movement.sdkmod`  
**SHA-256:** `c97876c29b893a226f48948b2cc619562084f7705a2ec01df2bdc123e8b1ed0a`

Install this exact file on every peer who wants the abilities. Confirm the hash against `dist/Modern_Movement.sdkmod.sha256` before enabling it. A 3.62.1 package will not coast joiner slides.

## Highlights

- Joiner slides keep going after you release forward. Crouch starts the slide; you do not have to hold the movement key.
- Listen host owns custom movement. Joiners send intents and keep their own option values.
- Jump Counter HUD (`mm_jump_chev`) defaults off. Dash Ready Indicator defaults on.
- Native TPS Slam and Oz AirBoost stay in the game. Custom Slam is omitted from this package.

## Features

| Feature | What you get |
|---------|----------------|
| Double Jump | Mid-air boost, coyote time, optional jump-counter chevrons |
| Dash | Ground or air dash, ready pip, optional damage reduction and perfect-dodge burst |
| Mantle / Vault | Ledge climbs and low-obstacle vaults |
| Slide | Sprint-crouch slide. On co-op, releasing forward keeps the entry-direction coast |
| Holster | Manual holster and sprint holster |
| Sprint Surge | Second sprint press for a speed boost that ramps up |

Players who do not install the mod can still join. Their movement stays vanilla.

## Changes in 3.62.2

### Fixed

- Joiner slides stopped as soon as forward was released. CrouchedPct only raises the engine crouch-speed cap, so the game braked with no movement input. The joiner and the host now re-apply the entry-direction speed, including after PlayerMove, the same way a local slide coasts.
- `server_slide_enter` sends that entry direction with the crouched percent and Slide Distance.

## Included from 3.62.1

- Jump Counter HUD, off by default, and a Dash Perfect Dodge Effect toggle.
- Per-player Slide Distance and Double Jump strength / extra jumps. The host menu does not override the joiner.
- Camera and feel sliders are back under each feature's Settings.
- Dash Ready Indicator defaults on.

## Included from 3.62.0

- Host-authoritative movement through `coop_rpc` (Networking 1.2). Clients send intents; the listen host writes custom movement.
- TPS-only package. Controller Dash and Toggle Holster start unbound.
- Custom Slam is excluded. Slide exits clear crouch so native Slam is left unarmed.

## Install

1. Remove or disable any older Modern Movement package (Borderlands 2 builds, loose folders, or a second copy).
2. Copy `Modern_Movement.sdkmod` into the Willow2 `sdk_mods` folder.
3. Enable the mod and check key bindings at the bottom of the mod options.
4. Restart the game after copying the file so hooks and keybinds load.

Full steps: [docs/INSTALL.md](../docs/INSTALL.md).

texloader is optional. Without a TPS-capable texloader fork, indicators draw as lines and gameplay is unchanged. Controller Dash and Toggle Holster start unbound; rebind them in the menu if you want them on a pad.

## Verification

Automated checks in this tree cover protocol, runtime, rules, gravity, input, the package allowlist, and dual-player co-op unit tests (`pytest`, 49 passed), plus a deterministic sdkmod build.

Releasing forward on a joiner slide is covered by those unit tests and remains **LIVE_REQUIRED** in a real two-player session. Track that in [LIVE_VALIDATION.md](LIVE_VALIDATION.md) and [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md).

## Rollback

Keep the supplied `Pre Sequel Port/Modern_Movement.sdkmod` archive unchanged as the known-good pre-co-op rollback artifact. Load either that archive or this co-op package in a session, not both.
