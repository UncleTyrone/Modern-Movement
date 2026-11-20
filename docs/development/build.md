# Build

From the repository root:

```text
python scripts/build_sdkmod.py
```

The script packs `src/Modern_Movement` using `build/package-allowlist.json`. It writes:

- `dist/Modern_Movement.sdkmod`
- `dist/Modern_Movement.sdkmod.sha256`
- `dist/Modern_Movement.manifest.json`

It does not overwrite `archive/borderlands-2.sdkmod` or `archive/pre-sequel-3.61.2.sdkmod`.

After a build, copy only `dist/Modern_Movement.sdkmod` into both games' `sdk_mods` folders. Leave the hash file and the manifest in `dist`.

Verify:

```text
python scripts/verify_sdkmod.py --build-first
python scripts/triple_check.py
```
