# Peer mod research (Phase R)

Sources cloned under `reports/peer_sources/` on 2026-11-18. Catalog JSON under `reports/WILLOW2_*.json` used only as indexes.

## 1. Inventory

| Slug / mod | URL / path | Files read | Decision |
|------------|------------|------------|----------|
| Original Modern Movement 3.61 | `archive/borderlands-2/Modern_Movement/` | All `.py` + textures | **COPY** HUD/options |
| Port Modern Movement 3.62.0 | `src/Modern_Movement/` | All `.py` | Working tree, next minor after shipped 3.61.2 |
| juso Sliding | `peer_sources/bl2sdk-mods/sliding/__init__.py` | Full | **COPY** CrouchedPct + FP arms; no Mesh dip |
| BL2 Eternal dash | `peer_sources/bl2sdk-mods/bl2eternal/mechanics/dashing.py` | Full | **KEEP** host Velocity hold (already) |
| Eternal glorykill | `.../glorykill.py` | Skim | **REJECT** |
| tweens | `peer_sources/bl2sdk-mods/tweens/` | tween.py, easing.py | **ADAPT** (we lerp manually) |
| Movement Tech | `peer_sources/willow2-sdk-mods/movement_tech/` | `__init__.py`, uemath, ucaching | **ADAPT** NestedOption/per-PlayerID; **REJECT** grapple |
| Movement Overhaul | `peer_sources/bl2-movement-overhaul/src/movement_overhaul/` | options.py, hud.py, __init__.py, legacy/* skim | **ADAPT** option IA; **REJECT** stamina-dash networking |
| willow2 Networking | `peer_sources/willow2-mod-manager/src/networking/` | All 6 modules | **KEEP** contracts |
| Movement DB (8) | willow2-mod-db + sources above | Pages + sources | See Tier 2 |
| UI/HUD peers | willow2-mod-db UI category | Pages + prior sweep | Pattern notes only |
| Libs (coroutines, canvaslib, texloader, …) | DB + installed sdk_mods | Metadata | Dependencies only |
| Nexus MM 4.04 | nexusmods.com/borderlands2/mods/706 | Changelog/features | Prefer Original code |
| Local TPS sdk_mods | `D:\SteamLibrary\...\sdk_mods` | Listing | Modern_Movement + manager deps only |

### Tier 2 movement (all 8)

| Mod | COPY/ADAPT/REJECT |
|-----|-------------------|
| bl2eternal | KEEP authority model |
| movementtech | ADAPT options; REJECT grapple |
| sliding | COPY feel/visual model |
| bl2speed | REJECT (Surge covers) |
| sprintadjuster | ADAPT air-control idea later only |
| sprintsetandforget | REJECT (conflicts Surge/holster) |
| tpsstylebhop | **REJECT** (native TPS) |
| speedometer | ADAPT optional debug HUD later; not in this sweep |

### Tier 3 UI — reusable patterns

PostRender + BoolOption On/Off + position/size sliders: Action Skill Timer, Shield Recharge Timer, ComboCounter, Farm/Run Counter, Bossbar, speedometer, NoCrosshair+CanvasLIB. **We already have ECHO texloader HUD** — copy Original jump/pip toggles, not rewrite into CanvasLIB.

Camera/viewmodel: Better Third Person, CVM, Photo Mode, SimpleZoom — **do not integrate**; FP arms already juso-style.

texloader: KEEP dependency path.

### Tier 4 libs

networking, tweens, uemath, coroutines, canvaslib, ue-timers, command-extensions, tracelib, keybinds/controllerbinds, audiocontrol, akeventplayer — reference only; no new hard deps this sweep.

### Tier 5

Nexus 4.04 confirms jump counter, dash pip, perfect dodge FX, slide jump indicator. **Copy from Original 3.61** (in-tree). Slide “boosted jump indicator” = our existing slide momentum bar.

Local sdk_mods: no other movement peers installed.

---

## 2. Copy matrix (into Port)

| Pattern | From | Into |
|---------|------|------|
| `jump_state` / `_draw_jumps` / `mm_jump_chev` | Original `hudfx.py` + textures | Port `hudfx.py` `_IMAGES` + PostRender |
| `counter_option` + tick wire | Original `double_jump.py` | Port `double_jump.py` (presentation only) |
| Dash pip default On | Original `dash.py` | Port `pip_option` |
| Mods description short list | Original `__init__.py` | Port `build_mod` description (no Slam name) |
| CrouchedPct slide / no Mesh.Z | juso Sliding | Keep Port (already); never re-add Mesh dip |
| Host dash Velocity hold | Eternal | Keep `_HOST_DASHES` |
| Nested Settings IA | Movement Overhaul `options.py` | Group Audio/Indicators/Camera in feature OPTIONS |
| Per-PlayerID state | Movement Tech `PLAYERS` | Reinforce Port `runtime` + host dicts |

---

## 3. Reject list

- Custom slam / glory kills / grapple / Mario / stamina-charge dash rewrite  
- Mesh.Translation body posing  
- Joiner mid-slide Velocity  
- Forcing host ruleset onto client menu widgets  
- TPS Style Bunny Hop  
- Sprint Set-and-Forget (Surge conflict)  
- Movement Overhaul networking (untested co-op)

---

## 4. Option catalog (add this sweep)

- Jump Counter On/Off (Original)  
- Perfect Dodge Effect On/Off (new BoolOption; dodge damage stays under existing dodge option)  
- Dash Ready Indicator default On  
- Strip `Temporary:` from descriptions; expose DJ/slide/mantle camera sliders already in code if they drive `camera.request`  
- Slide Distance must affect timed/juso path (per-player)

---

## 5. HUD catalog

| Indicator | Asset | Toggle |
|-----------|-------|--------|
| Dash arrows | mm_dash_* | screen_option |
| Dash pip | mm_pip_* | pip_option (On) |
| Perfect burst | drawn | perfect_fx_option (new) |
| Jump chevrons | mm_jump_chev | counter_option |
| Slide bar | mm_slide_* | indicator_option |
| Surge arcs | mm_surge_arc | surge.indicator_option |
| Slam | mm_slam_* | **do not ship** |

---

## 6. Co-op catalog

| Peer | Pattern | Ours |
|------|---------|------|
| Eternal | `@host` + host Velocity loop | `server_dash` + `_HOST_DASHES` |
| juso | CrouchedPct enter/exit + host decay | `server_slide_enter(pct, distance, dir)` + `_HOST_SLIDES` coast. juso stops at zero Acceleration; we keep the entry-direction speed |
| Movement Tech | `@host` slam; local options | DJ/slide must use **requester payload**, not host menu |
| Networking | 1 msg/tick ServerSpeech | Keep; no per-frame speed spam |

**Resolved:** Per-player feel = local options + RPC carries numbers. Do **not** apply `network.rules()` onto joiner menus. Host remote ticks must not re-read host `strength_slider` / `extra_jumps_slider` / `distance_slider` for remote pawns.

---

## 7. Open questions — resolved

| Q | Answer |
|---|--------|
| Restore slam HUD? | No — native TPS Slam |
| Force host options on joiners? | No — contradicts per-player requirement |
| Adopt MO stamina dash? | No — breaks Eternal contract |
| Slide distance on co-op? | Yes — bake into timed decay/cap via enter payload |
| Perfect dodge toggle? | Yes — presentation BoolOption |
