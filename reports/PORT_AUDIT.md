# Modern Movement supplied-source audit

## Immutable inputs
- Original archive: `archive/borderlands-2.sdkmod`
  - SHA-256: `d9431034750f6a8739841220a60a8da391f5a20772eb3affb3fedb4c8774278e`
  - 34 files; extraction was hash-verified before implementation edits.
- Pre-Sequel 3.61.2 archive: `archive/pre-sequel-3.61.2.sdkmod`
  - SHA-256: `4f7c1fbeda6bc75e1d624123e323f109e716fc0d3b0ca2026939aee1919a2429`
  - 35 files; extraction was hash-verified before implementation edits.

Both archives pass CRC, path traversal, duplicate-member, encryption, symlink, and case-collision checks.

## Normalized payload comparison
- Identical entries: 31
- Changed entries: 5
- Added entries: 1
- Removed entries: 0

Changed:
- `__init__.py`
- `core.py`
- `features/dash.py`
- `features/holster.py`
- `features/mantle.py`

Added by the port:
- `game.py`

## Semantic summary
- `__init__.py`: TPS detection, native-Slam exclusion, controller changelog, supported-game metadata.
- `core.py`: shared keyboard/controller jump wrappers and held-key checks.
- `features/dash.py`: D-pad Right controller default.
- `features/holster.py`: D-pad Down holster and left-stick Surge defaults.
- `features/mantle.py`: lower TPS gravity-sample floor.
- `game.py`: added cached BL2/TPS detection and the custom-Slam override.

No changed file adds networking, authority, per-player state, peer negotiation, or reconciliation.

## Confirmed TPS regression
The port reuses the BL2 Slide source unchanged. Slide holds native crouch state, has no explicit
sprint-exit transition, and does not clear crouch when it leaves the ground. TPS can therefore
interpret the retained crouch as native Slam. The co-op implementation must fix jump-out,
sprint-out, and off-cliff behavior before release.

## Scope
The supplied TPS 3.61.2 source is the implementation baseline. The separately published BL2 4.04
release is intentionally not merged into this work.
