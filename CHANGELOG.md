# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.62.2] — 2026-11-18

### Fixed

- Joiner slides stopped as soon as forward was released. CrouchedPct only raises the crouch speed cap, so the game braked with no movement input. Joiner and host now keep the entry-direction coast, the same as a local slide.

## [3.62.1] — 2026-11-18

### Added

- Double Jump Jump Counter HUD (`mm_jump_chev`) with On/Off toggle (defaults Off).
- Dash Perfect Dodge Effect toggle for the ECHO chevron burst.
- Per-player Slide Distance on the timed/juso host path via RPC payload.
- Host double-jump applies requester impulse and `max_jumps` without host menu strength.
- Repository docs tree (`docs/`), LICENSE, SECURITY, CONTRIBUTING, and `.gitignore`.

### Changed

- Mods-page description lists the six shipped features in Original voice.
- Dash Ready Indicator defaults On.
- Camera / feel sliders re-exposed under each feature's Settings (no Temporary labels).
- Sprint Surge Camera Tilt and Mantle camera/height options visible again.
- Package allowlist includes jump-counter textures.

### Fixed

- Joiner slide length ignored host `distance_slider` instead of the requester percent.
- Remote double-jump authority leaked host Extra Jumps / Strength onto joiners.

## [3.62.0] — 2026-11-18

### Added

- Host-authoritative TPS co-op path (`coop_rpc`, Networking 1.2).
- Eternal-style host dash hold and juso CrouchedPct-only network slides.

### Changed

- TPS-only package; custom Slam omitted in favour of native Slam/Oz.
