# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The last shipped Pre-Sequel package is **3.61.2**. The next minor is **3.62.0**. Everything since 3.61.2 stays on 3.62.0 until that package is released.

## [3.62.0] — 2026-11-18

### Added

- Host-authoritative co-op through `coop_rpc` and Networking 1.2. The listen host writes custom movement. Joiners send intents and keep their own option values. Peers without the mod stay vanilla.
- One package for Borderlands 2 and Borderlands: The Pre-Sequel. Borderlands 2 loads custom Slam, including the indicator, the landing blast, and a host dive so a joiner's plunge is written on the server pawn. The Pre-Sequel keeps native Oz slam.
- Double Jump Jump Counter HUD (`mm_jump_chev`), off by default, and a Dash Perfect Dodge Effect toggle.
- Per-player Slide Distance and Double Jump strength / extra jumps. The host menu does not override the joiner.
- Slide Speed (%) beside Slide Distance. Default 120. Distance still sets how long a slide lasts. Speed sets how fast it moves.
- Repository docs under `docs/`, plus LICENSE, SECURITY, CONTRIBUTING, and `.gitignore`.

### Changed

- Dash Ready Indicator defaults on. Camera and feel sliders sit under each feature's Settings.
- Controller Dash and Toggle Holster start unbound so they do not take the D-pad weapon slots. Rebind them in the menu if you want them.
- Gravity samples keep the original 300 floor on Borderlands 2 and accept moon gravity down to 60 on The Pre-Sequel.
- The package allowlist ships the jump-counter textures and the Borderlands 2 slam textures.

### Fixed

- Joiner slides keep their entry-direction coast after forward is released. The joiner and the host both re-apply that speed, including after PlayerMove.
- Releasing crouch cancels a joiner slide and tells the host to stand that body back up. The host copy waits for that exit, because it does not see the joiner's crouch key.
- Fast travel and level changes re-handshake co-op. An empty loading roster does not drop peers, and a world change or a broken token sends a fresh HELLO. Slide, dash, mantle, and slam holds from the old pawn are dropped.
- Joiner slide length uses that player's Slide Distance. Remote double jump uses the requester's strength and extra jumps.
- Joiner slide meters drain on a timer. Height noise no longer freezes the bar, refills it, stretches the slide, or leaves the fast crouch cap on after it ends.
- Joiner ground dashes leave walking with the same skim as a local dash, so standing still and dashing forward works. Air-only stays an option.
- Sprint Surge starts from a second sprint press while the weapon is already holstered, the same as with the gun out.
- Joiner dashes use the same cooldown as a local dash. The ready hex fills while it waits, and another dash does not start until that wait is over.
- Slides last about three quarters as long. They lose speed on that shorter clock, so the slowdown starts earlier.
- Sliding kicks up the ground you are on (dust, sparks, splash, snow). An air dash and a double jump leave a cool wind burst. Each machine draws those trails locally, including on other players.
- Slides no longer stutter. The coast pushes with a small acceleration instead of the full run acceleration, and the crouch speed cap matches the slide so the engine cannot lunge and snap back.
- Joiner dashes keep their vertical speed. The hold no longer stamps a fixed Z every tick or a downward yank at the end, which was the rubber-band.
- Surface effects use the game's own dust, impact, and smoke systems. A slide does not scan every particle or spawn a trace weapon, which was hitching the coast.
- Holding crouch through a slide jump lands in another slide, so a sprint-slide-jump can keep going. That held key is no longer a slam. A new crouch press in the air still slams, and holding crouch through the impact slides out of it.
- A slide cancel has to stay in the air for a moment. Jumping and touching ground again immediately no longer starts another slide, so the chain cannot be tapped as fast as the button allows.
- Other players can move again. The host was running the slide-cancel keyboard on each joiner's server pawn, which blocked their crouch and cancelled their dash. Slide cancel stays on the player who is holding crouch. The host still coasts their slide from the slide message.
- A joiner dash that touches the ground during the short hold is put back into falling, so the burst is not cut down to run speed. Vertical speed is still left alone.
- A joiner slide jump stays in the air. The host holds the same launch the joiner used, so the jump is no longer pulled back to the ground. Once they are rising, vertical speed is left to gravity.
- Sliding down a ramp or a run of stairs lasts longer. A single height bump does not.
- The game writes `Modern_Movement.log.txt` in the same folder as the installed mod. It records enable, handshake, dash and slide starts, and refused moves, so two players can compare sessions.
- Other players get dash, slide, and jump, not only the weapon holster. A joining client was treated as the host because the game reports Role Authority, so movement never reached the listen host. Weapon changes still showed up because the game replicates those itself.
- A slide jump lands in another slide only while crouch is held. Releasing crouch before landing, or a crouch pose left over from the slide, does not start another slide.

## [3.61.2] — shipped Pre-Sequel baseline

Controller twins for the mod keys, including Jump / Mantle / Double Jump on A and Sprint Surge on the left stick. Custom Slam stays off in favor of native Oz slam. This is the archive in `Pre Sequel Port/Modern_Movement.sdkmod`.
