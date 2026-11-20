[← Home](../README.md)

# Willow2, Borderlands 2, and The Pre-Sequel

Both games are Willow2. The PythonSDK, the Slammer helpers, and the way a mod hooks a pawn are the same bytes on this machine. The games diverge in the cooked packages, the Wwise banks, PhysX, gravity, and Oz. That split is what Modern Movement has to follow. Calling a Pre-Sequel sound or particle from Borderlands 2 does not work, because those objects are not in Borderlands 2's packages. Copying the bank file across does not create them.

This pass walked every file in both installs, compared paths and sizes, and hashed the SDK, the executables and DLLs under `Binaries\Win32`, every `.ini`, and the shared engine packages small enough to hash in full. Cooked level packages were compared by name and size. The shared engine packages are stored as one LZO chunk (`0x20000` blocks). Decompressing them yields a normal package, version 832, licensee 46, in both games. The format is the same. The name tables are not. Level packages were not decompressed one by one. A movement name was also searched as raw bytes across every `.upk` in both cooked folders, so a name that never appears there is not sitting in a map package either.

Installs compared:

- `D:\SteamLibrary\steamapps\common\Borderlands 2` — 14,110 files, 26,549,115,304 bytes. Steam app id 49520.
- `D:\SteamLibrary\steamapps\common\BorderlandsPreSequel` — 11,662 files, 22,553,366,206 bytes. Steam app id 261640.

Shared relative paths: 1,519. Same size: 936. Different size: 583. Only in Borderlands 2: 12,591, mostly `DLC` (9,622) and `WillowGame` (2,949), and the extra languages (`.esn`, `.fra`, `.ita`, `.deu`, `.jpn`). Only in The Pre-Sequel: 10,143, mostly `WillowGame` (6,337) and `DLC` (3,215), plus `pandoras_leftovers` (25 files) and a `Binaries` tree that is 352 files larger. The hash appendix is `reports/willow2_game_diff.json`.

## The SDK is one Willow2

These files hashed identical in both games. Same length, same SHA-256.

| Piece | What it is |
| --- | --- |
| `Binaries\Win32\Plugins\python314.dll` and `python314.zip` | CPython 3.14. The game's Python, not the 3.10 used to run tests. |
| `pyunrealsdk.dll`, `unrealsdk.dll`, `unrealsdk.toml` | The SDK loader. `unrealsdk.log` differs only because it is a runtime log. |
| `sdk_mods\mods_base.sdkmod` | Base 1.12. Options, hooks, `get_pc`, `ENGINE`. |
| `sdk_mods\networking.sdkmod` | Networking 1.2. `@host`, one message per player tick. |
| `sdk_mods\keybinds.sdkmod` | Keybinds 1.2. `WillowGame.WillowUIInteraction:InputKey`. |
| `sdk_mods\ui_utils.sdkmod` | UI Utils 1.5. |
| `sdk_mods\willow2_mod_menu.sdkmod`, `console_mod_menu.sdkmod`, `legacy_compat.sdkmod`, `save_options.sdkmod` | The menu and the option store. |
| `sdk_mods\__main__.py` and `sdk_mods\.stubs` | The loader and the type stubs. |

`Modern_Movement.sdkmod` was also identical, because this tree copies one build into both folders.

The `.pyc` files under other mods are 7 bytes larger on The Pre-Sequel. `BorderlandsPreSequel` is 7 characters longer than `Borderlands 2`. That is the path baked into the compiled file, not a second copy of the source. The `.sdkmod` payloads of the helpers did not change.

So a hook, a host message, an option, and `PlayAkEvent` are written once. `game.is_bl2()` / `game.is_tps()` is not a fork of the SDK. It is a fork of content the SDK then looks up.

## The engine packages are not the same bytes

`WillowGame\CookedPCConsole` has 935 files in Borderlands 2 and 840 in The Pre-Sequel. Only 45 names exist in both. 12 of those are the same size. 33 are not. The ones this mod actually stands on:

| Package | Borderlands 2 | The Pre-Sequel |
| --- | --- | --- |
| `Startup.upk` | 17,800,929 | 21,359,341 |
| `WillowGame.upk` | 4,104,253 | 4,732,034 |
| `Engine.upk` | 1,573,828 | 1,686,424 |
| `Core.upk` | 63,165 | 63,825 |
| `IpDrv.upk` | 61,975 | 69,084 |
| `AkAudio.upk` | 10,781 | 18,708 |
| `Startup_LOC_INT.upk` | 2,407,939 | 85,172 |
| `GfxUI.upk` | 38,444 | 45,207 |

`Startup.upk` is the always-loaded package. There is no loose `FX_*.upk`. Effects and AkEvents are names inside `Startup.upk` or `WillowGame.upk`. After decompression the name counts are:

| Package | Borderlands 2 names | The Pre-Sequel names | Uncompressed bytes |
| --- | --- | --- | --- |
| `Startup.upk` | 28,576 | 24,194 | 60,134,127 vs 79,041,276 |
| `WillowGame.upk` | 33,675 | 38,014 | 13,054,200 vs 15,631,774 |
| `Engine.upk` | 21,113 | 21,519 | 5,878,264 vs 6,321,400 |
| `AkAudio.upk` | 254 | 840 | 39,503 vs 63,008 |
| `Core.upk` | 865 | 872 | 234,397 vs 236,177 |

Both headers are version 832, licensee 46. A hook that exists on one game exists on the other. `WillowPlayerPawn`, `DoJump`, `DuckPressed`, and `PlayAkEvent` are in both `WillowGame.upk` name tables (`PlayAkEvent` and `DoJump` are also in both `Engine.upk` tables). `WorldGravityZ` is in both `Engine.upk` tables.

Level packages are per game. Borderlands 2 has `sanctuary_fx.upk`, `caverns_audio.upk`, and the rest of its maps. The Pre-Sequel has `moonsurface_fx.upk`, `laser_fx.upk`, `innercore_fx.upk`. None of those names are a movement effect. Do not reference them.

PhysX is a real binary fork, not just a bigger file. `PhysXCore.dll` is 4,318,208 bytes in Borderlands 2 and 4,029,440 in The Pre-Sequel. `PhysXCooking.dll` and `PhysXExtensions.dll` differ. `NxCharacter.dll` and `PhysXLoader.dll` are the same size and still hash different. A `_Px` particle can be a real name and still draw nothing on the other game's PhysX build. The names that exist are below. `FX_ENV_Dust_Px` is not one of them.

## Config that changes movement

`DefaultInput.ini` had no movement-line difference in this diff. Crouch, jump, and sprint bindings are the same idea in both games.

`DefaultGame.ini`:

- Both set `bCrouchToggle=true`. The crouched pose stays down after a tap in both games. A pose is not a key-up. That is why hold and release go through InputKey and the keyboard, on both games, and not through `bIsCrouched`.
- Borderlands 2 sets `DefaultGravityZ=-500`.
- The Pre-Sequel comments that line out (`2K_AUS:pboutot - Gravity`) and sets `bResetCameraOnSlam=true`.

Runtime gravity is `WorldInfo.WorldGravityZ`, which is not this default. Moon levels go far below 500. `gravity.py` keeps a 300 floor on Borderlands 2 and a 60 floor on The Pre-Sequel. That split stays.

`DefaultEngine.ini` on The Pre-Sequel cooks extra packages the Borderlands 2 list does not have, including `GD_Co_SpaceSlam` and a run of `GD_Cork_*` packages. Those are The Pre-Sequel's slam and Oz content. They are not Borderlands 2 objects.

`DefaultUI.ini` on The Pre-Sequel has a debug command, `Spawn Oz Kit`, and camera commands Borderlands 2's file does not. Nothing in our HUD should call those.

## Sounds

Wwise banks are not in the same place.

- Borderlands 2: `CookedPCConsole\Audio_Banks.pck` (320,565,120 bytes) and `CookedPCConsole\English(US)\Audio_Banks.pck` (11,822,307).
- The Pre-Sequel: `CookedPCConsole\Audio\Audio_Banks.pck` (282,252,800) and `CookedPCConsole\Audio\English(US)\Audio_Banks.pck` (10,832,138).

The banks hashed as different files because they are different files. Event names inside them are Wwise ids, not `Ak_Play_*` text. `PlayAkEvent` needs an `AkEvent` object from the Unreal package. That object is created when that game cooks its startup and audio packages. Copying `Audio_Banks.pck` into the other game does not add `Ake_Cork_FX_Global.Ak_Play_Cork_FX_AirBoost_Boost` to Borderlands 2, and it does not make a Borderlands 2 event appear in The Pre-Sequel.

The decompressed name tables, checked against every cooked `.upk`, say which of those events are real objects.

In both games, in `Startup.upk` unless noted:

- `Ak_Play_Wep_Grenade_Longbow_Teleport_Out` and the package name `Ake_Wep_Grenades`. The dash whoosh is a shared event.
- `Ak_Play_Exp_Elemental_Explosive_SM`. The full-slam crack is a shared event, not a Borderlands 2 exclusive.
- `Ak_Play_Foley_Armor`, `Ak_Play_Foley_Armor_Jump`, `Ak_Play_Foley_Armor_Land`, `Ak_Play_Fs_Ladder`, and the package names `Ake_Fs_Player`, `Ake_Fol_Player`, `Ake_UI`.
- `Ak_Play_Fs_Jump`, `Ak_Play_Fs_Land`, `Ak_Play_Fs_Run`, and `Ak_Play_Fs_Walk` are in both `WillowGame.upk` tables. The Pre-Sequel also has the jump, land, run, and walk names in `Startup.upk`. Borderlands 2 does not. They still resolve there because `WillowGame` is loaded. `GlobalPersistentCookerData.upk` carries the same strings in both installs.

The Pre-Sequel `Startup.upk` has these names. No Borderlands 2 `.upk` contains them:

- `Ake_Cork_FX_Global`, `Ak_Play_Cork_FX_AirBoost_Boost`, `Ak_Play_Cork_FX_AirBoost_End`, `Ak_Play_Cork_FX_AirBoost_Slam_Booster`
- `Ak_Play_Cork_FX_Slam`, plus `_Corrosive`, `_Fart`, `_Ice`, `_Incendiary`, `_Shock`
- `Ake_Cork_Fs_Player`
- `AirBoost`, `OzAirBoostDefinition`, `GetOzKit`, `GD_Co_SpaceSlam`

`Ak_Play_UI_Shield_Impact_The_Bee_Res` is the reverse. It is in Borderlands 2 `Startup.upk` and in no Pre-Sequel file. The dash-ready beep is silent on The Pre-Sequel until it uses a name that game has, such as `Ak_Play_Cork_UI_BadAssMedal` or `Ak_Play_UI_World_Discovery_Prompt`. Those are names only. They have not been heard in a session.

`WillowGame.upk` on The Pre-Sequel also has the native functions `DoAirBoost`, `BeginAirBoost`, `EndAirBoost`, `CanAirBoost`, `DoSlam`, `CanSlam`, `CancelSlam`, `ShouldSlam`, `bWantsToSlam`, `bResetCameraOnSlam`, `PlayerSlamRequiredDistance`, and `SlamStartHeight`. Borderlands 2's `WillowGame.upk` does not. That is the code fork. Custom slam stays off on The Pre-Sequel because the pawn already has `DoSlam`.

| Moment | Borderlands 2 | The Pre-Sequel |
| --- | --- | --- |
| Dash whoosh | Longbow teleport | Oz air boost, then Longbow. The air-boost name is in that game's `Startup.upk` and in no Borderlands 2 file |
| Dash ready beep | Bee shield UI event | That event is absent. A Cork UI name is the candidate |
| Double jump | `Ak_Play_Fs_Jump` from `WillowGame.upk` | Oz air boost first, then the same footstep |
| Slide | `Ak_Play_Fs_Run` / walk / foley | Same, and `Ake_Cork_Fs_Player` exists only here |
| Slam | `Ak_Play_Fs_Land`, and `Ak_Play_Exp_Elemental_Explosive_SM` on a full slam | Do not register custom slam. `DoSlam` is native. A hard landing can call `Ak_Play_Cork_FX_Slam` |
| Super sprint | No extra event | No extra event |

`fx.play_first` stops at the first event that resolves. There is no second sound bank inside the sdkmod.

## Particles

`features/surfacefx.py` spawns an `Emitter` in the world and falls back to the emitter pool. Both games have that Engine path. The template names in the source do not.

Every candidate the mod uses ends in `FX` (`Part_GenericGroundImpactFX`, `Part_WhispySmokeFX`, `Part_VEHDirtKickupFX`, `Part_Explosive_Nova_Shield_ExplosionFX`, and the rest). Those exact strings are absent from both `Startup.upk` and `WillowGame.upk` name tables, and from the bytes of every cooked `.upk` in both installs. `find_object` cannot return them. A short-name catalog cannot match them either. That is a sufficient explanation for no particles in either game. It is not a spawn-signature problem until a name that exists is requested.

The package name `FX_ENV_Dust` is in both `Startup.upk` tables. `FX_ENV_Dust_Px` is not in either name table. It shows up once, in Borderlands 2 `GuidCache.upk` only, as a cache string. It is not a Pre-Sequel-only system.

Names that do exist, shared by both `Startup.upk` tables, and close to what the effects are for:

- Slam ring: `Part_Explosive_Nova_Shield_Explosion`. The Pre-Sequel also has `Part_Explosive_Nova_Shield_Explosion_Px`.
- Sparks: `Part_SparkShowerGeneric`. The Pre-Sequel also has `Part_SparkShowerGeneric_Px`.
- A hard surface hit: `Part_Impact_Metal_LargeCal`, also in both `WillowGame.upk` tables.

Borderlands 2 `WillowGame.upk` alone has `Part_Skag_FeetDust`. The Pre-Sequel list has no feet-dust name. Ground dust of the wiki's `Part_GenericGroundImpact` / `Part_AmbientDust` / `Part_WhispySmoke` family is not cooked into either of these installs under those names. The full shared and one-game lists of impact-like `Part_` names are in `reports/willow2_particles.txt`.

`surfacefx.py` now asks for `Part_Explosive_Nova_Shield_Explosion`, `Part_SparkShowerGeneric`, and `Part_Impact_Metal_LargeCal`. The Pre-Sequel list tries the `_Px` twins first. A miss stays a skip. Movement does not wait on it.

## Where this package already branches

These are the forks that match the games. They are not SDK forks.

| Branch | Why it exists |
| --- | --- |
| `game.is_bl2()` before slam is registered | The Pre-Sequel has Oz slam and `bResetCameraOnSlam`. A second slam fights it. |
| `coop_rpc` slam messages no-op unless `is_bl2()` | The host must not write a dive the client game does not have. |
| `gravity.measured_bounds` | Moon gravity is legal on The Pre-Sequel. Borderlands 2 keeps the 300 floor. |
| `fx.dash_paths`, `jump_paths`, `slam_hit_paths` | Event objects differ. Try the local one, then a shared fallback. |
| `surfacefx._TPS_EXTRA` | The `_Px` names that exist (`Part_Explosive_Nova_Shield_Explosion_Px`, `Part_SparkShowerGeneric_Px`) are Pre-Sequel startup names. The current candidate strings, with a trailing `FX`, exist in neither game. |
| `textures_load` picks `native/bl2` or `native/tps` | The texloader builds differ. The Python SDK does not. |
| `holster` second-sprint gate on Borderlands 2 | Our rule, not a missing engine function. The first Shift press only sprints. The Pre-Sequel can start surge on the surge key. |
| Slide key-up on both games | Both default `bCrouchToggle=true`. The old "Pre-Sequel cannot see a release" path was our latch, not a different InputKey. |

Shared on purpose, because the SDK matches: tick order, `Networking 1.2`, InputKey press and release, host pawn writes, slide coast, dash hold, mantle replay, HUD draw, and "a missing effect is skipped".

## What not to do with this

Do not copy `Audio_Banks.pck`, `Startup.upk`, or a loose sound out of The Pre-Sequel into the sdkmod or into Borderlands 2's cooked folder. The banks are that game's audio, the packages are different bytes, and a copied bank does not register AkEvents in the other game.

Do not point both games at one particle list, and do not keep the current list. The shared names are `Part_Explosive_Nova_Shield_Explosion`, `Part_SparkShowerGeneric`, and `Part_Impact_Metal_LargeCal`. The `_Px` twins are Pre-Sequel only. The `...FX` strings in the source are in neither name table.

Do not treat a missing name in one decompressed table as a missing class until `WillowGame.upk` and `Engine.upk` have been checked too. `Ak_Play_Fs_Jump` is not in Borderlands 2's `Startup.upk`. It is in `WillowGame.upk`, which is why the footstep still has a name to resolve. `DoSlam` and `DoAirBoost` were checked the same way. They are Pre-Sequel `WillowGame` names and they are not in the Borderlands 2 package.
