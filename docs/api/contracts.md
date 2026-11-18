# Contracts

Hard locks (do not break in PRs):

1. Network slides coast. Joiner and host both re-apply entry-direction `Velocity` after movement keys are released. CrouchedPct only times the slide. Do not return to a CrouchedPct-only path.
2. No `Mesh.Translation` dips for third-person slide pose.
3. No custom Slam feature in the TPS package.
4. Keep `_HOST_DASHES`, `_HOST_SLIDES`, and mantle host replay as the authority tables.
5. Mods-page description lists shipped features only — no “left out” language.

See also `reports/NETWORK_RESEARCH.md` and `reports/COOP_MOD_DIFF.md`.
