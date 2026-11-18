# Modern Movement 3.62.0

Next minor after the shipped Pre-Sequel package 3.61.2. The same file runs in Borderlands 2 and Borderlands: The Pre-Sequel. Double Jump, Dash, Mantle, Slide, Holster, and Sprint Surge ship in both games. Borderlands 2 also gets Slam. The Pre-Sequel keeps native Oz slam. Pre-release work stays on 3.62.0.

**Package:** `dist/Modern_Movement.sdkmod`  
**SHA-256:** `ec3927d7f0a25eb3c51b1537276a3d49c6658a1c3c2f257fdd2041bb3ffa62fc`

Install this exact file on every peer who wants the abilities, in that game's `sdk_mods` folder. Confirm the hash against `dist/Modern_Movement.sdkmod.sha256` before enabling it. Use the same file on Borderlands 2 and on The Pre-Sequel.

## Highlights

- The same package loads in Borderlands 2 and The Pre-Sequel. Borderlands 2 includes Slam. The Pre-Sequel leaves Oz slam alone.
- Releasing crouch cancels a joiner slide. The slide ends when crouch is released.
- Fast travel re-handshakes co-op. Joiners come back with movement instead of a dead session.
- Slide Speed (%) sits next to Slide Distance. Default is 120, so slides are a little faster. Distance still sets how long they last.
- Joiner slides keep going after you release forward. Crouch starts the slide; you do not have to hold the movement key.
- Listen host owns custom movement. Joiners send intents and keep their own option values.
- Jump Counter HUD (`mm_jump_chev`) defaults off. Dash Ready Indicator defaults on.
- On The Pre-Sequel, native Slam and Oz AirBoost stay in the game. Custom Slam stays off there.

## Features

| Feature | What you get |
|---------|----------------|
| Double Jump | Mid-air boost, coyote time, optional jump-counter chevrons |
| Dash | Ground or air dash, ready pip, optional damage reduction and perfect-dodge burst |
| Mantle / Vault | Ledge climbs and low-obstacle vaults |
| Slide | Sprint-crouch slide. Speed and distance are separate. Releasing forward keeps the coast |
| Surface | Dust, sparks, splash, and snow from the ground you slide on, plus a cool wind burst in the air |
| Holster | Manual holster and sprint holster |
| Sprint Surge | Second sprint press for a speed boost that ramps up |
| Slam | Borderlands 2. Crouch in the air to dive, with a landing blast and indicator |

Players who do not install the mod can still join. Their movement stays vanilla.

## Changes since 3.61.2

These notes are the whole 3.62.0 delta from the shipped 3.61.2 package.

### Added

- Host-authoritative co-op. The listen host writes custom movement. Joiners send intents and keep their own option values.
- Borderlands 2 and The Pre-Sequel both load this package. Slam is included on Borderlands 2, with the indicator and a host dive so a joiner's plunge is written on the server pawn. The Pre-Sequel keeps native Oz slam.
- Slide Speed (%) beside Slide Distance. Default 120. 100 is the previous coast.
- Jump Counter HUD, off by default, and a Dash Perfect Dodge Effect toggle.
- Per-player Slide Distance and Double Jump strength / extra jumps.

### Changed

- Dash Ready Indicator defaults on. Camera and feel sliders are under each feature's Settings.
- Controller Dash and Toggle Holster start unbound. Gravity samples use a 300 floor on Borderlands 2 and accept moon gravity down to 60 on The Pre-Sequel.

### Fixed

- Joiner slides keep the entry-direction coast after forward is released. `server_slide_enter` sends that direction with the crouched percent, Slide Distance, and Slide Speed. The joiner and the host re-apply the speed, including after PlayerMove.
- Releasing crouch cancels a joiner slide and tells the host to stand that body back up. The host copy waits for the exit.
- Fast travel and level changes send a fresh HELLO. An empty loading roster does not drop peers. Slide, dash, mantle, and slam holds from the old pawn are dropped.
- Joiner slide meters drain steadily and clear when the slide ends. A noisy height no longer freezes, refills, or jitters the bar, and it no longer leaves them sliding afterward.
- Joiner dashes work from a standstill on the ground. The dash leaves walking instead of requiring them to already be in the air.
- Sprint Surge starts when you press sprint again while already holstered, the same as with the gun out.
- Joiner dashes wait out the dash cooldown. The ready hex fills during that wait, and mashing dash does not fire another one early.
- Slides are about three quarters as long, and they start losing speed earlier instead of holding full speed until the end.
- Slides kick up the surface you are on, and an air dash leaves a cool wind burst. Other players running the mod see those effects on your body.
- Slides no longer stutter. The coast uses a small push, and the crouch cap is the slide speed, so walking physics cannot lunge ahead and get snapped back.
- Joiner dashes keep the fall they already have. The host hold no longer rewrites Z every tick.
- Surface dust uses particles the game already has loaded. The slide coast does not stop to search the particle list or fire a trace.
- Holding crouch through a slide jump slides again on landing, once the jump has actually been in the air. A hop that touches down immediately does not start another slide. A new crouch press in the air still slams, and holding crouch through that slam slides away when you land.

## Install

1. Remove or disable any older Modern Movement package (Borderlands 2 builds, loose folders, or a second copy).
2. Copy `Modern_Movement.sdkmod` into the game's `sdk_mods` folder (Borderlands 2 or The Pre-Sequel).
3. Enable the mod and check key bindings at the bottom of the mod options.
4. Restart the game after copying the file so hooks and keybinds load.

Full steps: [docs/INSTALL.md](../docs/INSTALL.md).

texloader is optional. Without a TPS-capable texloader fork, indicators draw as lines and gameplay is unchanged. Controller Dash and Toggle Holster start unbound; rebind them in the menu if you want them on a pad.

## Verification

Automated checks in this tree cover protocol, runtime, rules, gravity, input, the package allowlist, travel recovery, dual-player co-op unit tests, and a dual-game boot harness (`pytest`, 64 passed), plus a deterministic sdkmod build. The harness boots the package as Borderlands 2 (Slam loaded) and as The Pre-Sequel (Slam not loaded) and reads every shipped source line.

Releasing forward on a joiner slide is covered by those unit tests and remains **LIVE_REQUIRED** in a real two-player session. Track that in [LIVE_VALIDATION.md](LIVE_VALIDATION.md) and [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md).

## Rollback

Keep the supplied `Pre Sequel Port/Modern_Movement.sdkmod` archive unchanged as the known-good pre-co-op rollback artifact. Load either that archive or this co-op package in a session, not both.
