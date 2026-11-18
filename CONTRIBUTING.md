# Contributing

## Before you change movement

1. Read `docs/development/architecture.md` and `reports/NETWORK_RESEARCH.md`.
2. Respect co-op locks: network slides coast on both sides (do not drop the joiner or host Velocity re-apply), no `Mesh.Translation` dips, no custom Slam rewrite, keep `_HOST_DASHES` / `_HOST_SLIDES` / mantle host replay.
3. Prefer copy-first from Original MM, juso Sliding/Eternal dash, and Movement Overhaul option/HUD patterns.

## Dev loop

```text
python -m pytest
python scripts/build_sdkmod.py
python scripts/verify_sdkmod.py --build-first
```

## Pull requests

- Keep changes focused; do not mix unrelated HUD polish with authority rewrites.
- Update `CHANGELOG.md` (Keep a Changelog) and bump `__version__` when shipping gameplay.
- Rebuild `dist/Modern_Movement.sdkmod` and refresh the `.sha256` sidecar before asking for review.
- Do not force-push `main` / `master`.

## Docs

API pages live under `docs/api/`. Usage pages under `docs/usage/`. Keep module pages sorted by name.
