# Modern Movement 3.62.1 — TPS polish release notes

## Package

- Artifact: `dist/Modern_Movement.sdkmod`
- SHA-256: `fcf51ffc93e385c309d62e76849e484c5595f7c72252e30aff813c06ff163b7b` (also in `dist/Modern_Movement.sdkmod.sha256`)
- Scope: Borderlands: The Pre-Sequel only
- Policy: listen host is the sole custom-gameplay writer; clients send intents and render host-confirmed presentation
- Native TPS Slam and Oz AirBoost are preserved; custom Slam is excluded from the sdkmod allowlist

## Highlights

- Jump Counter HUD restored (Off by default) with `mm_jump_chev`
- Dash Ready Indicator defaults On; Perfect Dodge Effect toggle
- Per-player Slide Distance and Double Jump strength/extra jumps over co-op
- Camera/feel Settings re-exposed; Temporary labels stripped
- Full docs/repo scaffold for publish

## Install

See [`docs/INSTALL.md`](../docs/INSTALL.md). Every peer should use this exact package hash. Remove any older Modern Movement folder/sdkmod first.

## Automated verification completed

- Protocol / runtime / rules / gravity / input / allowlist / dual-player co-op unit tests (`pytest` — 48 passed)
- Deterministic sdkmod build + verify

## Live validation

Two-player and four-player TPS gates remain **LIVE_REQUIRED**. Track progress in [`LIVE_VALIDATION.md`](LIVE_VALIDATION.md) and [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

## Rollback

Retain the supplied `Pre Sequel Port/Modern_Movement.sdkmod` archive unchanged as the known-good pre-co-op rollback artifact.
