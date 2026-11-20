[← Home](../../README.md)

# Test

From the repository root:

```text
python -m pytest
python scripts/willow_harness.py
python scripts/dual_game_harness.py
```

`pythonpath` is `src` plus the repository root. The live package is `src/Modern_Movement`. Co-op authority contracts live in `tests/test_coop_host_authority.py` (dual-player strength and distance, the dash hold, and a joiner slide that keeps its coast after you release forward). `scripts/willow_harness.py` reads the Willow2 helpers installed in both games and checks this package calls them. `scripts/dual_game_harness.py` boots the package as Borderlands 2, with Slam loaded, and as The Pre-Sequel, with Slam left out.
