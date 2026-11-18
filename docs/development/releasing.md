# Releasing

Maintainer prepares a local commit; the publisher creates the GitHub Release.

1. Bump `Modern_Movement.__version__` and add a Keep a Changelog section in `CHANGELOG.md`.
2. Run `python -m pytest`.
3. Run `python scripts/build_sdkmod.py` and confirm `dist/Modern_Movement.sdkmod.sha256`.
4. Commit locally (do not push unless asked).
5. Publisher: push, tag, create a GitHub Release, and **attach** `dist/Modern_Movement.sdkmod` plus the `.sha256` sidecar.
6. Paste the SHA-256 into the release notes so peers can verify downloads.
