# LINE_AUDIT — Port vs Original (Phase 0)

**Port:** `Pre Sequel Port/Source/Modern_Movement`  
**Original:** `Original/Source/Modern Movement`  
**Date:** 2026-11-18

Severity: `BLOCKER` / `FIX_NOW` / `POLISH` / `WONTFIX`

## Findings

| Sev | Location | Issue |
|-----|----------|-------|
| BLOCKER | `hudfx.py:758-760` | `jump_state` no-op stub |
| BLOCKER | `hudfx.py:92-100` | `_IMAGES` omits `mm_jump_chev` |
| FIX_NOW | `double_jump.py:384+` | `counter_option` removed; no `hudfx.jump_state` call |
| FIX_NOW | `dash.py:82-88` | `pip_option` default Off (Original On) |
| FIX_NOW | `dash.py` | Perfect dodge VFX has no BoolOption |
| BLOCKER | `slide.py` timed path | `distance_slider` ignored on juso/timed slides |
| BLOCKER | `double_jump.py` host paths | `REMOTE_AUTHORITY` uses host `extra_jumps_slider` / `strength_slider` |
| POLISH | `__init__.py:884-889` | Apologetic description mentions slam omitted |
| POLISH | slide/mantle/DJ options | `Temporary:` prefixes |
| POLISH | dash/DJ/slide/mantle/surge | Camera sliders exist but hidden from OPTIONS |
| WONTFIX | slam feature | Intentionally omitted for TPS |
| FIX_NOW | `hudfx.py` slam draw | Dead path; keep uninstalled textures; leave draw inert |
| POLISH | slide arms | No Mesh.Translation (good); keep |

## Module index (Port)

See peer research + explore audit: 23 modules — `__init__`, core, runtime, authority, network, coop_rpc, rules, protocol, input_state, diagnostics, game, gravity, tracing, camera, fx, hudfx, features/{double_jump,dash,holster,surge,mantle,slide,__init__}.

## FIX_NOW for sweep

1. Restore jump HUD from Original  
2. Pip default On; perfect FX option  
3. Description Original voice  
4. Strip Temporary; expose camera sliders in Settings  
5. Timed slide respects requester distance %  
6. Host DJ/slide remote paths use payload / per-player state, not host menu globals  
