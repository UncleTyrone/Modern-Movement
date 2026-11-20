# Modern Movement codebase map

Forensic baseline of the supplied TPS 3.61.2 source before co-op work. The BL2 original remains
under `archive/borderlands-2/Modern_Movement`. The **live working tree** is
`src/Modern_Movement` at **3.62.0** (the next minor after the shipped Pre-Sequel package 3.61.2 in `archive/pre-sequel-3.61.2.sdkmod`).

## Co-op status (working tree — supersedes baseline notes below)

- Borderlands 2 and The Pre-Sequel (`game.supported()`). Custom Slam loads on Borderlands 2 and stays out of the Pre-Sequel feature list.
- Network slides (3.62.0): CrouchedPct decay plus entry-direction Velocity coast on the joiner and the host. Releasing forward keeps the coast. Releasing crouch cancels the joiner slide. A slide jump keeps `state.chain` only while the crouch key reads down. A release clears `crouch_down` and the chain. A PressedKeys miss does not, because that list omits a held crouch key. The pose-based landing slide stays blocked after that jump. Landing calls `offer_landing` only after `_CHAIN_MIN_AIR` (0.40s). A joining client is `LOCAL_REQUESTER` from `NetMode` 3. Host RPCs resolve an empty `Owner.Pawn` through `PawnList`. That held crouch can still slam once the jump is high enough. A step cannot. A new in-air crouch press still slams, and a held crouch through the impact slides out via `slam_bank`. A sprint jump with no prior slide, already at Min Slide Speed, saves `state.slide_jump` from `_note_sprint_jump` the same way a slide cancel does. Holding crouch in the air arms `state.chain` through `_update_chain_hold`, and the landing waits for `_CHAIN_MIN_AIR`. A release clears it. Both games. A jump that is too slow to slide does not save that link. A press during an active slide is blocked, and a slide that just ended does not start another one in the air. `offer_landing` aims every landing slide along `core.facing`, stores that direction in the slide, and keeps it alive for `_LAND_GRACE` so the old momentum cannot stall or back-cancel it. An unreadable key does not. The host coast is `_HOST_SLIDES`. A joiner slide jump is `server_slide_jump`, held in `_HOST_JUMPS` for `_LAUNCH_HOLD`. A sustained downhill (`drop_run` > 0.12s) lengthens the slide and keeps its speed. Every slide is fresh for `_LAND_GRACE`, so the sprint already held does not end it, and a slide ending does not block the next crouch. The key-up of the press that started the slide is ignored for 0.05s in both games. A sprint press ends the slide only after that sprint key has come up (`sprint_released`), so the leftover slide time is not a lock. Crouch hold and slam read the physical key when PressedKeys omits it. A surge key press starts the boost when one is not already running. A joiner's surge is the same 1.30–1.70 GroundSpeed boost, taken once from the GroundSpeed already on the pawn, sprint included. Velocity is not rewritten. Borderlands 2 starts that surge only on a second sprint press, and both games end a slide when the crouch key comes up. The Pre-Sequel uses that same let-go. A landing slide after a slide jump happens only while the key is down. A slide jump latches crouch before the uncrouch, and a short ground touch does not drop that chain. The gun's rest pose is the level pose. `diagnostics.py` appends `Modern_Movement.log.txt` beside the installed sdkmod while the mod is enabled. `_authority_tick` does not run the crouch-key machine on a joiner pawn, and `DuckPressed` is blocked only for the local player. A dash hold that is walking again is set back to falling without rewriting Z. `core.downed` is the Fight For Your Life flag (`bIsInjured`, `IsInjured`, or the controller `Injured` state). Dash and double jump refuse it, including a down that starts while falling, and `DoJump` is blocked for that pawn.
- HUD PNGs load from the package through the vendored texloader for that game (`native/bl2` is 1.2, `native/tps` is the 1.1.9 fork plus `texcompat.py`). An installed texloader is preferred so two native modules are not loaded.
- Borderlands 2 slam: `_slam_kind` is a full slam once clearance reaches the jump-height requirement (at least `_FULL_FLOOR`), and a pull once clearance is at least `_SLAM_FLOOR` and upward speed is no longer a launch (`vz <= _COMMIT_VZ`). A missed trace is not a slam. A slide that simply leaves the ground is not a slam. The feet also have to leave the last walking height by `_SLAM_FLOOR`, so a crouch on the ground is a slide. The landing camera uses `_impact_eye` and does not drop EyeHeight through the floor. A high slide jump can slam. `_slam_hold` is true only when the crouch key reads down on that tick, and a short air buffer lets the dive start without holding through the whole rise. `slam_hold` is cleared every slide tick, so a slam does not block the next slide. One upward frame does not cancel the dive. A crouch dip in the first moments of a slide stays on the floor instead of ending the slide and starting another. Dash, double jump, and slide spawn the same ground dust. The slam ring is that dust plus a darkened nova. Dash, sprint, slide, and slam spawn an Emitter in the world from per-game lists in `surfacefx.py`. A dash plays the Longbow teleport whoosh. On The Pre-Sequel it tries the Oz air boost first, and a double jump tries that same boost. Super sprint does not. A slide does not. It repeats `Ake_Fs_Player` footsteps only. A slam plays the impact only. The slide bar is `_slide_fill` (time left on the cap, or speed if that runs out first) and it reaches empty when the slide ends. A full slam plays `Ak_Play_Fs_Land` and `Ak_Play_Exp_Elemental_Explosive_SM`. The Pre-Sequel uses `Ak_Play_Cork_FX_Slam` and the Oz air boost.
- Modules: `runtime`, `protocol`, `network`, `rules`, `authority`, `input_state`, `gravity`, `diagnostics`.
- Each machine writes its local pawn (Willow client simulation). Remote host contexts are observe-only.
- Jump order: Slide first → Mantle → Double Jump (airborne DoJump blocked so Oz glide does not eat the press).
- Controller Dash/Holster defaults are unbound (`None`); Surge keeps left-stick.
- Enable registers with Willow2 v3.8 Slammer: Base 1.12, Networking 1.2, Keybinds 1.2, UI Utils 1.5. Movement RPCs use `add_network_functions`. Crouch hold uses the keybinds InputKey event. Peers without the mod stay vanilla and do not lock the host.

## Bootstrap (baseline 3.61.2 archive)

- `__init__.py`
  - Builds the mod and aggregates options, keybinds, hooks, and lifecycle callbacks.
  - Feature order: Double Jump, Dash, Holster, Surge, Mantle, Slide, Slam.
  - TPS skips custom Slam before import.
  - Enable order is core then feature order; disable currently uses the same order.
- `game.py`
  - Cached BL2/TPS detection in the **archive** baseline (working tree is TPS-only fail-closed).

## Shared services

- `core.py`
  - One PlayerTick hook and shared jump key.
  - Feature registry, synchronous event bus, exclusive `busy` action, speed multiplier ledger.
  - Tick order: Dash 10, Mantle 15, Double Jump 20, Slide 20, Holster 30.
  - Ground jump order: Mantle, Double Jump, Slide.
  - Air jump order: Mantle then Double Jump, first consumer wins.
  - Local-only guard discards every controller except `get_pc()`.
- `camera.py`
  - Aggregates named eye/roll/pitch requests and writes one local pawn/controller.
- `tracing.py`
  - Spawns one hidden WillowWeapon for line/box traces.
  - Global session depth, pawn, weapon, budget, memo, recorder, and self-hit state.
- `fx.py`
  - Sound and AkSwitch lookup, HUD-movie helpers, and clip alpha.
- `hudfx.py`
  - Dash, cooldown, dodge, jump, Slam, Slide, and Surge drawing.
  - Global effect state and one selected PostRender source.

## Features

- `features/double_jump.py`
  - Coyote jump, configurable extra jumps, directional redirect, counter, camera, and sound.
  - Directly writes pawn velocity.
- `features/dash.py`
  - Cardinal fixed-distance dash, stall detection, ground skim, exit lock, cooldown, HUD, sound.
  - Dynamic TakeDamage hook implements dodge/perfect-dodge by blocking and replaying damage.
  - Directly writes velocity, acceleration, and physics.
- `features/holster.py`
  - Manual/sprint/mantle holster, weapon restore, fire/aim handling, action-skill blocking.
  - Owns Sprint Surge runtime and contributes a GroundSpeed multiplier.
- `features/surge.py`
  - Options and the 30% to 70% boost curve; runtime lives in Holster.
- `features/mantle.py`
  - Buffered/held ledge search, rail/overhang/narrow-top handling, Hermite path, ballistic handoff.
  - Up to 120 logical traces per search; direct velocity/acceleration/physics writes.
- `features/slide.py`
  - Sprint-crouch and landing starts, steering, slope/friction, crouch-speed lease, carry, slide jump.
  - Direct velocity/acceleration/crouch/physics writes.
  - TPS regression: retained crouch can arm native Slam; sprint and jump lack deterministic ownership.
- `features/slam.py` (removed from TPS co-op source; native Slam only)
  - BL2 custom plunge, indicator, grenade-scaled blast, knockback, and camera effects.
  - Skipped on TPS but still packaged in the supplied port.
- `features/__init__.py`
  - Interface documentation; incorrectly claims features do not import each other.

## Events and coupling

- `mantle_start` and `mantle_end` drive Holster.
- `player_hit` lets Slide tolerate hit flinch; it is emitted by Dash’s damage hook.
- `slide_jump` drives custom Slam’s easy-height path.
- `slam_impact` hides Slide’s crouch icon.
- `dash_end` currently has no listener.
- HUD hooks and texture installation are exported through Dash, coupling every HUD feature to Dash.

## Mutable singleton state

Every gameplay module stores action state globally. Important examples:

- Core clock, physics snapshot, busy owner, jump guard, vehicle cache, speed ledger.
- Double Jump count and air/coyote history.
- Dash action, cooldown, exit lock, camera, pip, and global damage recursion guard.
- Holster weapon UObject, sprint source, stow cause, Surge timing, and camera tilt.
- Mantle action, buffers, gravity samples, trace mode, held state, recorder.
- Slide action, crouch lease, input history, carry, launch hold, camera, HUD, sound.
- Camera/HUD presentation and trace session state.

These globals are the primary blocker to host simulation for multiple remote players.

## Authoritative mutations

- Movement: `Velocity`, `Acceleration`, `Physics`, `DoJump`, `ShouldCrouch`, `UnCrouch`.
- Speed: `GroundSpeed`, `CrouchedPct`.
- Inventory: `SetCurrentWeapon`, `SwitchToBestWeapon`.
- Damage: `TakeDamage` replay; custom Slam radius damage.
- Presentation: `EyeHeight`, controller rotation, viewport Canvas, Flash clip opacity, audio.

The refactor must gate the first four groups to host/standalone authority and the presentation
group to the local owning view.

## Assets

Ten PNG/TOML pairs provide Dash, jump, cooldown, Slam, Slide, and Surge HUD textures. The original
loose tree contains an unused `mm_slide_streak` pair. Stock texloader is BL2-only; TPS must use the
line fallback unless a compatible fork is positively identified.
