# Releasing

Maintainer prepares a local commit; the publisher creates the GitHub Release.

1. The unreleased line is `3.62.0`, the next minor after the shipped Pre-Sequel package `3.61.2`. Record the work in that `CHANGELOG.md` section, in `reports/RELEASE_NOTES.md`, and in the usage and API docs for every feature the change touches. Open 3.62.1 only when 3.62.0 itself has shipped.
2. Run `python -m pytest`.
3. Run `python scripts/build_sdkmod.py` and confirm `dist/Modern_Movement.sdkmod.sha256`.
4. Commit locally (do not push unless asked).
5. Publisher: push, tag, create a GitHub Release, and **attach** `dist/Modern_Movement.sdkmod` plus the `.sha256` sidecar.
6. Paste the SHA-256 into the release notes so peers can verify downloads.
