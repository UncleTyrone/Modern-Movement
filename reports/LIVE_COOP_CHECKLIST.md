# Live co-op verification checklist (joiners)

Automated tests prove the **host mutation contract**. This checklist is the remaining
gate for TPS listen-host + joiner with **Networking 1.2** and this mod installed on
**both** machines.

Build under test: `cc8b62c520dbdaaec47cfd99a74a995fb304afeb3c0cd168d4c3bc28d93b2705`


## Setup

1. Full restart of TPS on host and joiner (mod load at boot).
2. Confirm console/log once: `Networking 1.2 endpoints attached`.
3. Host starts a listen game; joiner joins. Both have Modern Movement enabled.

## Joiner checks (the player who joined)

| # | Action | Pass | Fail |
|---|--------|------|------|
| 1 | **Dash** (air or ground) | Moves the aimed distance; little/no snap-back | Rubber-band, no move, or HUD-only |
| 2 | **Double jump** | Clear second boost; lands normally | Nothing / Oz-only / delayed snap |
| 3 | **Slide** (sprint+crouch) | Faster than crouch-walk; ends ~1s flat | Crouch in place + HUD only |
| 4 | **Vault / Mantle** | Climbs onto the ledge; stays up | Rubber-band snap back to start |
| 5 | **Sprint Surge** | Noticeably faster while surging | Holster/HUD but same run speed |
| 6 | Host watches joiner | Host sees dash/slide/vault/surge | Host sees walk/crouch only |

## Host self-check

Host alone still has full dash / DJ / slide / surge (no regression).

## If anything fails

Note: ability, host/joiner, map, and whether log shows `mm.rpc.*` / `coop_rpc:` errors.
Do **not** claim co-op support until all five joiner rows pass.
