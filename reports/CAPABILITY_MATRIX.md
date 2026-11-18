# TPS capability matrix

Status values:

- `PROVEN_SOURCE`: established from official Networking source or local static analysis.
- `PROVEN_COMPARABLE`: demonstrated by a current public Willow2 mod, still requiring local TPS test.
- `SIMULATED`: covered by the fake runtime/network harness.
- `LIVE_REQUIRED`: cannot be established without TPS host/client runtime evidence.
- `BLOCKED`: failed live authority proof; the feature must remain unavailable off-host.

## Transport and identity

- Sender PRI attribution: `PROVEN_SOURCE`
- `sender.Owner` on listen host: `PROVEN_SOURCE`
- Host sees all controllers, clients see themselves: `PROVEN_SOURCE`
- Ordered reliable delivery under normal bandwidth: `PROVEN_SOURCE`
- Silent loss under saturation: `PROVEN_SOURCE`
- Safe payload/rate boundary: `LIVE_REQUIRED`
- Join/leave/travel PlayerID behavior: `LIVE_REQUIRED`

## Authoritative property control

- Host remote Velocity write: `PROVEN_COMPARABLE`, `LIVE_REQUIRED`
- Host remote Physics write: `LIVE_REQUIRED`
- Host remote Acceleration write: `LIVE_REQUIRED`
- Host remote GroundSpeed write: `LIVE_REQUIRED`
- Host remote CrouchedPct/crouch write: `PROVEN_COMPARABLE`, `LIVE_REQUIRED`
- Host remote weapon stow/restore: `LIVE_REQUIRED`
- Native server movement fallback names/behavior: `LIVE_REQUIRED`

## Inputs and native TPS mechanics

- Jump input can be blocked without duplicate native action: `LIVE_REQUIRED`
- Sprint input can exit Slide and start exactly one sprint: `LIVE_REQUIRED`
- Crouch input can start Slide without arming native Slam: `LIVE_REQUIRED`
- Slide off cliff can suppress retained crouch until release: `LIVE_REQUIRED`
- Fresh crouch after suppression still invokes native Slam: `LIVE_REQUIRED`
- Native Oz boost consumed-state signal: `LIVE_REQUIRED`
- Native Slam active/queued-state signal: `LIVE_REQUIRED`

## Damage and tracing

- Listen-host TakeDamage hook for remote pawn: `LIVE_REQUIRED`
- Damage block/replay exactly once: `LIVE_REQUIRED`
- Remote controller trace-weapon spawn: `LIVE_REQUIRED`
- Host controller spawn with remote pawn instigator: `LIVE_REQUIRED`
- Four-player trace scheduling budget: `SIMULATED` after harness implementation, then `LIVE_REQUIRED`

## Implementation status (code complete, live proof pending)

- Per-player runtime contexts, host authority dispatch, and two-endpoint protocol: `SIMULATED`
- Double Jump / Dash / Slide / Holster / Surge / Mantle host controllers: `SIMULATED`
- Requester jump fan-out (Slide → Mantle → Double Jump fall-through): `SIMULATED`
- Trace weapons spawn from session controller (not only `get_pc()`): `SIMULATED`
- Co-op all-peers-ready gate on host feature ticks and intent dispatch: `SIMULATED`
- Slide air-jump first refusal + BeginSprint PRE + airborne-crouch landing guard: `SIMULATED`
- SlideCrouchLease generation binding + input_state suppress mirror: `SIMULATED`
- AST static policy (`scripts/static_policy.py`) bans feature `get_pc()`: `SIMULATED`
- Slide first-refusal jump/sprint + crouch suppress after off-cliff/jump: `SIMULATED` (live TPS still required)
- Double jump owns airborne DoJump (Oz glide deferred/blocked while extra jumps remain): `SIMULATED`
- Custom Slam removed from release allowlist; slam textures not installed: `PROVEN_SOURCE`
- Joiner slide coast after forward is released (same vector on joiner and host): `SIMULATED`, `LIVE_REQUIRED`
- Package TPS-only fail-closed game detection + Networking attach: `PROVEN_SOURCE`

## Release rule

An item marked `LIVE_REQUIRED` may not be represented as proven in release documentation. If a
movement property is `BLOCKED`, use a proven native server function or leave the affected feature
disabled for remote clients. Client-authoritative movement is not an allowed fallback.
