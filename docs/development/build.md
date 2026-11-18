# Build

Deterministic package builder:

```text
python scripts/build_sdkmod.py
```

Writes `dist/Modern_Movement.sdkmod` and `dist/Modern_Movement.sdkmod.sha256` from `build/package-allowlist.json`. Never overwrites the protected archives under `Original/` or `Pre Sequel Port/`.

Verify:

```text
python scripts/verify_sdkmod.py --build-first
```
