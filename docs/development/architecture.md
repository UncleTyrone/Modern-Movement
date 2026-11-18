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

Co-op model: requester predicts locally where needed, host mutates the sender pawn, presentation peers draw HUD/VFX only. Copy-first peers: Original MM HUD/options, juso slide, Eternal dash hold.
