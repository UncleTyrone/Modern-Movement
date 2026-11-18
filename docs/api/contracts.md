# Contracts

Hard locks (do not break in PRs):

1. Network slides coast. Joiner and host both re-apply entry-direction `Velocity` after movement keys are released. CrouchedPct only times the slide. Do not return to a CrouchedPct-only path.
2. No `Mesh.Translation` dips for third-person slide pose.
3. Custom Slam arms only when `game.is_bl2()` is true. The Pre-Sequel keeps native Oz slam, so the Slam feature must stay out of the TPS feature list.
4. Keep `_HOST_DASHES`, `_HOST_SLIDES`, and mantle host replay as the authority tables.
5. Mods-page description lists shipped features only — no “left out” language.

See also `reports/NETWORK_RESEARCH.md` and `reports/COOP_MOD_DIFF.md`.
