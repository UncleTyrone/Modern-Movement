# Co-op vs Eternal / juso (verified 2026-11-17)

Sources:

- https://github.com/juso40/bl2sdk-mods/blob/main/bl2eternal/mechanics/dashing.py
- https://github.com/juso40/bl2sdk-mods/blob/main/sliding/__init__.py
- https://github.com/bl-sdk/willow2-mod-manager/blob/master/src/networking/decorators.py
- https://github.com/bl-sdk/willow2-mod-manager/blob/master/src/networking/message_queue.py

## What is proven in code (not live)

| Claim | Evidence |
|-------|----------|
| `@host` RPC path works in this mod | Live: DJ / surge / holster already succeed on joiner |
| Host Velocity writes stick when re-asserted | Live: DJ host hold; unit: `test_host_dash_*` |
| Eternal host dash = timed full-Vector hold ~0.15s + soft stop 200 | Source + our `_HOST_DASHES` |
| juso slide = CrouchedPct 2.2→0.5, decay 0.7/s, no mid-slide Velocity | Source + our timed/`_HOST_SLIDES` |
| Networking queues **1 msg/tick** | message_queue.py `MAX_MESSAGES_PER_TICK = 1` |

## Critical correction (why “100% Eternal dash” was wrong for us)

Eternal joiner writes **no** local Velocity. That can work on LAN with their coroutine stack.

Our live stack already proved the opposite for DJ: **local predict + identical host hold**.

A host-only 0.15s dash often finishes before autonomous-proxy replication arrives → joiner feels **nothing**.

Locked dash contract for Modern Movement:

1. Joiner: local Velocity hold for 0.15s (same vector) + ground skim out of walking clamp  
2. Host: `_HOST_DASHES` Eternal hold on `sender.Owner.Pawn`  
3. Soft stop 200 u/s + Z=-10 on both sides  

## Slide contract

1. Joiner + host: CrouchedPct only (juso)  
2. Latch `bDuck=1` while sliding (juso `can_slide` requires it)  
3. Host `_HOST_SLIDES` decay once per local tick (not doubled with PlayerMove)  

## What still requires a live join

No offline test can prove replication timing under real TPS listen-host load. Checklist: `LIVE_COOP_CHECKLIST.md`.
