# Architecture

```text
__init__.py  → build_mod, feature groups, hooks
core.py      → tick bus, jump key, busy, helpers
authority.py → host FeatureControllers
network.py   → Networking attach + presentation
coop_rpc.py  → @host handlers
features/*   → gameplay + OPTIONS
hudfx.py     → PostRender indicators
runtime.py   → PlayerContext roles
```

Version **3.62.0**, the next minor after the shipped Pre-Sequel package 3.61.2. Pre-release edits stay on 3.62.0.

Co-op model: requester predicts locally where needed, host mutates the sender pawn, presentation peers draw HUD/VFX only. Copy-first peers: Original MM HUD/options, juso slide length (CrouchedPct decay) plus an entry-direction coast, Eternal dash hold. Slam follows the same host-write pattern on Borderlands 2 and stays disabled on The Pre-Sequel.
