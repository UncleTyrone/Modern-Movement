# Modern Movement codebase map

Forensic baseline of the supplied TPS 3.61.2 source before co-op work. The BL2 original remains
under `Original/Source/Modern Movement`. The **live working tree** is
`Pre Sequel Port/Source/Modern_Movement` at **3.62.2** (host-authoritative co-op).

## Co-op status (working tree — supersedes baseline notes below)

- TPS-only fail-closed (`game.supported()`); custom Slam excluded from package allowlist.
- Network slides (3.62.2): CrouchedPct decay plus entry-direction Velocity coast on the joiner and the host. Releasing forward must not stop the slide.
- Modules: `runtime`, `protocol`, `network`, `rules`, `authority`, `input_state`, `gravity`, `diagnostics`.
- Each machine writes its local pawn (Willow client simulation). Remote host contexts are observe-only.
- Jump order: Slide first → Mantle → Double Jump (airborne DoJump blocked so Oz glide does not eat the press).
- Controller Dash/Holster defaults are unbound (`None`); Surge keeps left-stick.
- Enable is transactional; Networking attach failure refuses enable; coop support is optional (peers without the mod do not lock out the host).

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
