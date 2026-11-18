# Willow2 authoritative networking research

## Verified Networking 1.2 behavior

Sources:

- https://github.com/bl-sdk/willow2-mod-manager/blob/master/src/networking/__init__.py
- https://github.com/bl-sdk/willow2-mod-manager/blob/master/src/networking/decorators.py
- https://github.com/bl-sdk/willow2-mod-manager/blob/master/src/networking/transmission.py
- https://github.com/bl-sdk/willow2-mod-manager/blob/master/src/networking/message_queue.py
- https://github.com/bl-sdk/willow2-mod-manager/blob/master/src/networking/registration.py

Facts:

- `host`, `targeted`, and `broadcast` support empty, string, and JSON messages.
- The sender exposed during a callback is the sender’s PlayerReplicationInfo.
- On the listen host, `sender.Owner` is the sender’s server-side PlayerController.
- The host can see every PlayerController; a client normally sees only itself.
- Transport uses reliable `ServerSpeech` and `ClientMessage`.
- Delivery is documented as ordered/reliable under normal load, but engine bandwidth saturation
  can silently drop messages.
- The library has no application acknowledgement, retry, queue bound, or published safe payload.
- The global queue currently sends one item per `Engine.PlayerController:PlayerTick` callback.
- Targeted messages store PlayerID and resolve the current PRI again at send time.
- Default network identifiers use Python module and qualified function names.
- Registration is one callback per identifier; a collision replaces the previous callback.

## Strict authority policy (locked to Eternal / juso source)

Checked against:

- https://github.com/juso40/bl2sdk-mods/blob/main/bl2eternal/mechanics/dashing.py
- https://github.com/juso40/bl2sdk-mods/blob/main/sliding/__init__.py

### Dash (Eternal)

- Joiner: FX/HUD only + `@host` (no local Velocity write — rubber-bands).
- Host: `PLAYER_DASH_DATA`-style `_HOST_DASHES`; write full `Velocity` Vector every local tick
  for ~0.15s; soft stop ~200 u/s + Z=-10.
- We send world dash velocity in the RPC (Eternal reads host-side Acceleration instead).

### Slide (juso)

- Joiner + host: **CrouchedPct only** (enter ≈2.2, exit 0.5). **No mid-slide Velocity.**
- Host: `_HOST_SLIDES` + decay ~0.7/s (+ slope terms); serviced once per local frame.
- Joiner predicts the same CrouchedPct decay locally; `@host` enter/exit mirrors host pawn.
- PlayerMove re-asserts CrouchedPct while a slide is active (juso).

### Double jump / surge

- DJ: joiner predicts + `@host` impulse; host re-asserts Velocity briefly.
- Surge: `@host` force-start / `surge_end`; no per-frame speed RPCs (1 msg/tick queue).

## Automated verification

`tests/test_coop_host_authority.py` covers host dash hold, frozen-location dash survival,
juso CrouchedPct-only slide, DJ hold, surge GroundSpeed, and joiner timed slide (no Velocity).

Live join checklist: `reports/LIVE_COOP_CHECKLIST.md`. Diff notes: `reports/COOP_MOD_DIFF.md`.
