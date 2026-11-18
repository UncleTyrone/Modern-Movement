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

### Slide (juso length, local coast)

- juso itself is CrouchedPct only and `can_slide` fails when Acceleration is zero, so releasing forward ends the slide.
- This package keeps juso's CrouchedPct decay (enter ≈2.25, exit 0.5, host `_HOST_SLIDES` once per local frame, per-player distance scale) and adds the local slide's coast.
- `server_slide_enter` carries `dir_x` / `dir_y`. Joiner and host re-apply that Velocity and Acceleration every tick and again after PlayerMove, so a released forward key does not brake the slide.
- A CrouchedPct-only path is not allowed. Unpaired client Velocity writes still rubber-band; the host must coast the same vector.

### Double jump / surge

- DJ: joiner predicts + `@host` impulse; host re-asserts Velocity briefly.
- Surge: `@host` force-start / `surge_end`; no per-frame speed RPCs (1 msg/tick queue).

## Automated verification

`tests/test_coop_host_authority.py` covers host dash hold, frozen-location dash survival,
joiner slide coast after forward is released, host replay restore, DJ hold, and surge GroundSpeed.

Live join checklist: `reports/LIVE_COOP_CHECKLIST.md`. Diff notes: `reports/COOP_MOD_DIFF.md`.
