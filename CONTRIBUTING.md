[← Home](README.md)

# Contributing

## Before you change movement

1. Read `docs/development.md` and `reports/NETWORK_RESEARCH.md`. The live code is `src/Modern_Movement`. The original Borderlands 2 source is `archive/borderlands-2/Modern_Movement`.
2. Respect co-op locks: network slides coast on both sides (do not drop the joiner or host Velocity re-apply), no `Mesh.Translation` dips, no custom Slam rewrite, keep `_HOST_DASHES` / `_HOST_SLIDES` / mantle host replay.
3. Prefer the original Borderlands 2 source, juso Sliding, and Eternal dash when a behavior is being matched. Do not edit the files in `archive/`.

## Dev loop

```text
python -m pytest
python scripts/build_sdkmod.py
python scripts/verify_sdkmod.py --build-first
```

## Commits

Do not commit while a change is still being tried. After you have tested it and said it works, the next step is one commit. The message says why the change exists, and `CHANGELOG.md` is already updated in that commit. Do not stack commits that are titled only with the version number. Do not push, and do not force-push `main` or `master`, unless you ask for that.

## Pull requests

- Keep changes focused; do not mix unrelated HUD polish with authority rewrites.
- Keep gameplay notes in the unreleased `CHANGELOG.md` section. The working version stays **3.62.0**, the next minor after the shipped Pre-Sequel package 3.61.2, until that package is actually released. Do not open 3.62.1 for pre-release edits.
- Rebuild `dist/Modern_Movement.sdkmod` and refresh the `.sha256` sidecar before asking for review.
- Do not force-push `main` / `master`.

## Docs

The player guide is `docs/play.md`. The API notes are `docs/api.md`. The build and release notes are `docs/development.md`. `README.md` is the only index. Each of those pages links back to it.
