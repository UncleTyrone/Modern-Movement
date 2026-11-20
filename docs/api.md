[← Home](../README.md)

# API

Package `Modern_Movement` version 3.62.0, loaded from `src/Modern_Movement`. That is the next minor after the shipped Pre-Sequel package 3.61.2. Pre-release work stays on 3.62.0. `__version__` and the handshake field `package` both say `3.62.0`.

`build_mod` is what the mod manager calls. `__init__.py` wires the feature groups and checks Willow2 v3.8 on enable: Base 1.12, Networking 1.2, Keybinds 1.2, UI Utils 1.5. If Networking did not import, local movement still runs and a short HUD note says so. A player without this mod stays on the game's own movement. The mod does not require every player to have it.

## Where things live

`core.py` is the tick bus, the jump key, the busy flag, and the InputKey hook that Keybinds 1.2 uses. Crouch hold and release come from that event, with the keyboard as a fallback. PressedKeys dropping a held key is not treated as a release. `runtime.py` names the role. A listen host is `LOCAL_HOST`. A client (`NetMode` 3) is `LOCAL_REQUESTER` even when `Role` says Authority. `authority.py` is the host-side feature controller. `network.py` attaches Networking 1.2. `coop_rpc.py` is the `@host` messages. `protocol.py` and `rules.py` are the handshake and the option snapshot. `input_state.py` remembers the Willow key. `game.py` is `is_bl2()` and `is_tps()`. Outside a game both are false.

`hudfx.py` draws on PostRender. `camera.py` mixes the view pushes. `fx.py` plays AkEvents and gives up quietly when one is missing. `features/surfacefx.py` spawns an Emitter in the world for dust, wind, and the slam ring, using `Part_SparkShowerGeneric` and `Part_Explosive_Nova_Shield_Explosion`. The Pre-Sequel tries the `_Px` versions of those first. The emitter pool is the fallback. `diagnostics.py` appends `Modern_Movement.log.txt` beside the installed sdkmod. `tracing.py` is the ledge trace. It uses one hidden weapon for a search and then throws that weapon away. `gravity.py` keeps the original 300 floor on Borderlands 2 and accepts moon gravity down to 60 on The Pre-Sequel.

The calls meant for tests and other tools are `core.register`, `authority.register_feature`, `network.register_presentation`, the `coop_rpc.server_*` handlers, the `hudfx` indicator helpers, and the `host_apply_*` / `host_enter_juso` / `host_begin_slam` writers. Everything else is internal.

## Co-op messages

A requester predicts locally and calls `coop_rpc.call_host`. The host writes the sender's pawn. If `Owner.Pawn` is empty, the host walks `PawnList` by PlayerID. Presentation peers draw the HUD and the effects. They do not run the other player's keyboard.

| Message | Id | What the host writes |
|---------|----|----------------------|
| `server_dash` | `ModernMovement:Dash` | A short velocity hold in `_HOST_DASHES`. Vertical speed is left alone. |
| `server_double_jump` | `ModernMovement:DoubleJump` | The requester's velocity and max jumps. The host does not re-read its own strength slider. |
| `server_slide_enter` | `ModernMovement:SlideEnter` | CrouchedPct plus the entry direction and speed. Both sides keep coasting after forward is released. |
| `server_slide_exit` | `ModernMovement:SlideExit` | Stands that body back up. |
| `server_slide_jump` | `ModernMovement:SlideJump` | Holds the launch in `_HOST_JUMPS`. Once they are rising, later ticks write horizontal speed only. |
| `server_speed_mult` | `ModernMovement:Speed` | GroundSpeed times 1.30 to 1.70, taken once from the run already on the pawn, sprint included. `1.0` clears it. Velocity is not written. |
| `server_holster` | `ModernMovement:Holster` | Weapon holster state. |
| `server_mantle_start` / `server_mantle_end` | `ModernMovement:MantleStart` / `MantleEnd` | Replays the climb plan. Do not replace the host tables. |
| `server_slam_begin` / `server_slam_end` / `server_slam_impact` | `ModernMovement:SlamBegin` / `SlamEnd` / `SlamImpact` | Borderlands 2 only. A barely-downward begin is a full slam at 2600. A real pull is kept. |

HELLO and INTENT stay on `network.py` as string messages. Slide cancel and the sprint-jump landing run on the owning client. The host does not replay that keyboard. A walking frame before the jump has been airborne for 0.40 seconds does not drop the chain.

## Features

Slide (`features/slide.py`) holds crouch to start and a key-up to stop, in both games, after 0.05 seconds of grace. A slide jump stores `state.slide_jump`. `state.chain` stays armed only while the crouch key reads down. A missed read is `None` and does not arm a chain or clear one that a real hold started. Landing calls `offer_landing` only after `_CHAIN_MIN_AIR`. The landing aims along `core.facing`. `DuckPressed` is blocked on the owning client while a chain is set, so the game's own crouch does not eat the hold. Borderlands 2 slam still reads the key, so a high slide jump can slam. The host coast is `_HOST_SLIDES`.

Slam (`features/slam.py`) registers only when `game.is_bl2()` is true. `_slam_kind` is a full slam once clearance reaches the jump-height requirement, and at least 170 units. A pull starts once clearance is at least 120 and upward speed is no longer a launch. A missed ground trace is not a slam. A slide that simply leaves the ground is not a slam. A press in the air sticks for a short moment. Landing clears it. The impact plays `Ak_Play_Fs_Land`, and a full slam also plays `Ak_Play_Exp_Elemental_Explosive_SM`. There is no dive whoosh.

Dash plays the Longbow teleport whoosh. On The Pre-Sequel, `dash_paths()` tries `Ak_Play_Cork_FX_AirBoost_Boost` first. Double jump uses `jump_paths()`, which tries that same Oz boost on The Pre-Sequel and otherwise a footstep jump. `play_first` stops at the first event the game actually has. Super sprint does not play the whoosh. A slide repeats footstep scrapes. The Pre-Sequel's hard landing can play `Ak_Play_Cork_FX_Slam` plus the footstep land. Those events are looked up in the game that is running. The package does not contain the sound banks.

Surface effects are cosmetic. A missing particle is skipped. Sprint Surge multiplies GroundSpeed from +30% to +70%. The ramp slider is seconds to climb. Borderlands 2 starts it on the second sprint press. Mantle and holster follow the same host-write pattern as the other moves.

The original Borderlands 2 source is `archive/borderlands-2/Modern_Movement`. The frozen packages are `archive/borderlands-2.sdkmod` and `archive/pre-sequel-3.61.2.sdkmod`. Do not edit those.
