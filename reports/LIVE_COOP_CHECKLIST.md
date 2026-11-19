# Live co-op verification checklist (joiners)

Automated tests prove the **host mutation contract**. This checklist is the remaining
gate for a listen-host and a joiner on **3.62.0** with **Networking 1.2** and this mod installed on
**both** machines. The same file is the Borderlands 2 package.

Build under test: `cdbcbf3b51ca09de434fae10678fc3f03708c4f40949b3ab48177858757b2e33`

The same file is the Borderlands 2 build. On Borderlands 2 it also loads Slam. On The Pre-Sequel it does not.


## Setup

1. Full restart of TPS on host and joiner (mod load at boot).
2. Confirm console/log once: `Networking 1.2 endpoints attached`.
3. Host starts a listen game; joiner joins. Both have Modern Movement enabled.

## Joiner checks (the player who joined)

| # | Action | Pass | Fail |
|---|--------|------|------|
| 1 | **Dash** (air or ground) | Moves the aimed distance; little/no snap-back | Rubber-band, no move, or HUD-only |
| 2 | **Double jump** | Clear second boost; lands normally | Nothing / Oz-only / delayed snap |
| 3 | **Slide** (sprint+crouch, release forward, then release crouch) | Coasts without holding forward; releasing crouch cancels it | Stops when forward is released, or crouch release does nothing and it only times out |
| 4 | **Vault / Mantle** | Climbs onto the ledge; stays up | Rubber-band snap back to start |
| 5 | **Sprint Surge** | Noticeably faster while surging | Holster/HUD but same run speed |
| 6 | Host watches joiner | Host sees dash/slide/vault/surge | Host sees walk/crouch only |
| 7 | **Fast travel** (everyone), then slide and dash again | Joiner movement still works after the load | Joiner abilities dead until restart |

## Host self-check

Host alone still has full dash / DJ / slide / surge (no regression).

## If anything fails

Note: ability, host/joiner, map, and whether log shows `mm.rpc.*` / `coop_rpc:` errors.
Do **not** claim co-op support until all five joiner rows pass.
