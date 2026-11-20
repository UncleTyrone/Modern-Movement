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
- Other players' dash, slide, and jump reach the listen host again. The host was dropping every one of those messages because the joiner's pawn was missing on their controller, so only a local weapon holster showed up.
- A slide jump lands in another slide only while the crouch key is still down. Letting go before landing does not slide, and the crouched pose from the slide does not count as holding the key.
- Sprint, jump, and hold crouch: you slide when you land or slam, even if you never slid before that jump. The crouch key has to be down when you hit the ground. Letting go does not slide.
- A landing slide goes the way you are facing when you touch down, and it stays down. Turning around no longer cancels it or slides you backward. You keep the speed you had.
- Slide cancel works again while crouch is held. The game's pressed-key list was reporting that held button as up, so the landing slide never started. Releasing crouch still cancels it.
- Pressing crouch while you are already sliding does not start another slide. Leaving the ground no longer starts a slide in the air, and the gun returns upright when the slide ends.
- Crouch while sprinting starts another slide after the last one. The sprint already held was ending the slide and then blocking the next press.
- The super sprint key starts another surge after the last one. A later press was only treated as turn-off.
- Running at a low obstacle and pressing jump vaults onto it. The ledge check was crashing as soon as it found a wall.
- Dash arrows, the slide bar, the ready pip, and the surge arcs draw on the HUD again. They were being painted on a canvas the game covered.
- Sliding down a ramp or a run of stairs keeps the slide's speed for that longer run. The extra time was slowing down to a crouch walk.
- Other players get the super sprint speed, not only the arcs. Their Sprint Surge Speed Ramp Up is the climb the host writes onto them, from +30% to +70%. 10 on that slider is ten seconds to full speed, not ten times speed. The host rewrites that speed on its own tick.
- Other players slide cancel while they hold crouch. Standing up at the jump was read as letting go, so the landing slide only happened sometimes.
- The gun comes back up when you are not sliding. A chain of slides was saving the tilted gun as the normal pose, and the settle-back was painting that lean on again.
- A joiner's slide jump no longer sends a second "stand up" after the launch, which was pulling the landing slide back down.
- Other players' double sprint is faster than the sprint they already had. The boost was being added to a walk, and a normal sprint is already faster than that, so the host put them back on a normal run. The host now keeps writing their surged run after the game moves them.
- Sprint surge adds 30% to 70% of walk speed on top of a sprint. Multiplying the sprint, and writing that into GroundSpeed, was launching people. A jump keeps the game's jump. The surge no longer throws you along the crosshair.
- Other players surge at the same boost you do. The host was also pushing their velocity, so they ran ahead of you, stuttered, and then got pulled back to where the run started.
- Sprint surge multiplies the run you already have, sprint included, from +30% to +70%. Pinning that to a walk had turned the surge off, including for the host. The bonus is taken once, so it does not stack, and it does not throw you along the crosshair.
- Borderlands 2: the first sprint press only sprints. Super sprint starts when you press sprint again while that sprint is already going.
- Borderlands 2: hold crouch to slide and let go to stop. A tap no longer runs the whole slide, and you do not have to sprint until you are faster than the sprint itself. The Pre-Sequel hold is unchanged.
- Borderlands 2: hold crouch in the air and you slam down as soon as you are off the ground, including a short hop. You do not have to reach the top of a jump first. A crouch held through a slide jump still lands in a slide.
- Dashing leaves wind, sprinting leaves a light streak, and a slam lands in a circle of dust. Borderlands 2 and The Pre-Sequel each use that game's effects. A missing effect is skipped.
- Sliding starts with a whoosh and keeps a footstep scrape until you stand up. A dash is a whoosh, a double jump is a jump, a slam dives with a whoosh and lands with an explosion and a footstep. The Pre-Sequel uses its Oz slam and air-boost sounds for those.
- HUD images load from this package. Borderlands 2 uses its texloader, and The Pre-Sequel uses its own. A separate texloader install is not required.
- The slide bar follows the slide. It shrinks across the coast and is gone when the slide ends, in both games. The next slide can start as soon as that one ends.
- Borderlands 2: hold crouch while you are moving and jumping. A high jump slams. A short hop, once it has peaked, pulls you down. The slam plays a hard landing, and that crouch does not turn into a slide.
- A dash plays a whoosh. The beep is only the ready tone when the cooldown finishes.
- A slide is only the ground scrape. The high whoosh on slide start is gone. A slam plays the impact only, with no sound on the way down.
- Borderlands 2: hold crouch to slide and let go to stop. Letting go ends it, including a short hold. A second press is not the cancel. The same hold slams from a high jump and pulls a short hop down after it peaks. A jump with crouch up is left alone.
- Press sprint again after you let go of sprint and the slide ends then. The time that slide had left is not a wait before the next one. The sprint you were already holding does not end it.
- Willow2 Mod Manager v3.8 (Slammer) is required: Base 1.12, Networking 1.2, Keybinds 1.2, and UI Utils 1.5. Dash, slide, jump, mantle, surge, and slam travel on the Networking host endpoints. Crouch hold and release use the same InputKey event the keybinds module uses.
- The live package is `src/Modern_Movement`. The original Borderlands 2 source is `archive/borderlands-2/Modern_Movement`. The frozen packages are `archive/borderlands-2.sdkmod` and `archive/pre-sequel-3.61.2.sdkmod`. Install `dist/Modern_Movement.sdkmod`.
- The installed copy in each game's `sdk_mods` folder is `Modern_Movement.sdkmod` only. The hash file and the manifest stay in `dist`.

## [3.61.2] — shipped Pre-Sequel baseline

Controller twins for the mod keys, including Jump / Mantle / Double Jump on A and Sprint Surge on the left stick. Custom Slam stays off in favor of native Oz slam. This is the archive in `archive/pre-sequel-3.61.2.sdkmod`.
