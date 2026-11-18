# LIVE TPS validation checklist

Items marked **LIVE_REQUIRED** in [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md) cannot be marked proven until this checklist passes in the actual game with matched build hashes on every peer.

Automated code integration against the plan is complete (contexts, authority, protocol, Slide/Oz/Mantle/Dash/Holster paths, packaging). **G1 live capability lab and G4–G6 in-game matrices remain open** until two/four TPS instances validate them.

## Prerequisites

- Same `dist/Modern_Movement.sdkmod` SHA-256 on host and every client (see `dist/Modern_Movement.sdkmod.sha256`).
- Remove any older duplicate Modern Movement package from all peers before testing.
- Networking **1.2+** enabled; peers without the mod do not gate host abilities.
- Optional TPS-capable texloader fork installed on all peers, or confirm line-drawn HUD fallback after one-time log.

## Release gates (from plan)

| Gate | Requirement |
|------|-------------|
| G0 | Source provenance: manifests, allowlist, and audit reports pass. |
| G1 | Capability lab evidence for remote mutation, damage, trace, input, and transport. |
| G2 | Standalone TPS behavior matches supplied port; no stale state after lifecycle events. |
| G3 | Protocol/authority: hostile traffic fails closed; simulated four-player isolation; zero requester writes. |
| G4 | Two-player TPS matrix below passes with native Oz/Slam intact. |
| G5 | Four-player TPS matrix below passes including soak. |
| G6 | Two deterministic builds match; installation verified on every peer; rollback archive retained. |

## Two-player gate

Record build hash, map, role/slot, input device, Oz/native-Slam state, RTT/loss, structured logs, and video timestamp per scenario.

- [ ] Same build/hash on host and client, then **role reversal**
- [ ] Keyboard and controller combinations, including rebound/conflicting controls
- [ ] Every feature alone and every supported cancellation combination
- [ ] Hold/toggle crouch: Slide + jump → one rising slide jump, no native downward Slam, no immediate re-crouch
- [ ] Slide + sprint → clean exit into one sprint, no stutter, no same-press Sprint Surge, momentum carry preserved
- [ ] Slide off cliff while crouch held → ordinary fall, no instant native Slam; release then air-crouch → native TPS Slam works
- [ ] Repeat three Slide regressions at 50 / 150 / 300 ms RTT with roles reversed and controller (A / left stick)
- [ ] Atmospheric and vacuum/moon-gravity locations
- [ ] Oz equipped/absent, oxygen full/empty, native boost available/consumed
- [ ] Native Slam from multiple heights: no custom HUD/blast/duplicate dive/accidental landing slide
- [ ] Dash dodge vs enemy, self, environmental, DOT, splash, lethal, and FFYL damage
- [ ] Simultaneous actions; death/Second Wind/respawn; vehicle; fast travel; level transition; save/quit/rejoin; disconnect/rejoin; mod disable/re-enable
- [ ] 50 / 150 / 300 ms shaped RTT and controlled loss

## Four-player gate

- [ ] All players same feature simultaneously, then four different features
- [ ] All mantle same obstacle (trace scheduling stress)
- [ ] Damage all players in one frame; independent dodge state
- [ ] One dies, one changes weapon while holstered, one disconnects/travels, one continues an action
- [ ] Join-in-progress and reconnect with reused slots
- [ ] Thirty-minute soak across at least two map transitions
- [ ] No growing state maps, retained trace weapons, duplicate hooks, queue growth, runaway logs, or cross-player speed/weapon/camera/HUD bleed

## Authoritative synchronization evidence

- [ ] Every client intent correlates with one host accept/reject and one host action ID when accepted
- [ ] Host action digests and client mirror digests match; token/phase/rules mismatch enters DESYNC_SAFE and recovers from snapshot without client gameplay writes
- [ ] Instrumentation shows **no requester client authoritative property writes**
- [ ] After action end, all peers observe host pawn within native replication tolerance; no cooldown/action disagreement
- [ ] Under H2C loss, host movement stays correct; next digest/snapshot repairs presentation only

## Immediate rollback blockers

Stop release if any of these occur:

- Crash, hang, or unbounded trace/network work
- Cross-player cooldown, busy, velocity, physics, speed, weapon, damage, camera, or HUD corruption
- Damage reduction applied zero or multiple times
- Slide/jump/sprint/off-cliff unintentionally arming native TPS Slam
- Unrestored speed, crouch, weapon, camera, or trace resource after lifecycle cleanup
- Broken native TPS Oz boost or Slam
- Archive/source mismatch, duplicate hooks after reload, or non-deterministic release bytes