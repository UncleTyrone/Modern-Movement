# Modern Movement docs

Version **3.62.0**. One package, `src/Modern_Movement`, runs in Borderlands 2 and The Pre-Sequel on PythonSDK Willow2 v3.8 (Slammer). Slam loads only in Borderlands 2.

## Start here

- [Install](INSTALL.md)
- [Usage overview](usage/overview.md)
- [Co-op](usage/coop.md)
- [HUD indicators](usage/hud.md)
- [Controller](usage/controller.md)

## Features

- [Double Jump](usage/double-jump.md)
- [Dash](usage/dash.md)
- [Mantle / Vault](usage/mantle.md)
- [Slide](usage/slide.md)
- [Holster](usage/holster.md)
- [Sprint Surge](usage/surge.md)
- Slam is Borderlands 2 only. The Pre-Sequel keeps native Oz slam. Hold crouch in the air: a high jump slams, and a short hop pulls you down after it peaks.

## Repository

| Path | Role |
|------|------|
| `src/Modern_Movement` | Live package. This is what `scripts/build_sdkmod.py` packs. |
| `archive/borderlands-2/Modern_Movement` | Original Borderlands 2 source, kept. |
| `archive/borderlands-2.sdkmod` | Frozen original package. |
| `archive/pre-sequel-3.61.2.sdkmod` | Frozen Pre-Sequel 3.61.2 package. |
| `dist/Modern_Movement.sdkmod` | The file you copy into `sdk_mods`. |

## API

- [Overview](api/overview.md)
- [Public surface](api/public-surface.md)
- [Options](api/options.md)
- [Co-op notes](api/coop-notes.md)
- [Contracts](api/contracts.md)
- Modules: [authority](api/authority.md) · [camera](api/camera.md) · [coop_rpc](api/coop_rpc.md) · [core](api/core.md) · [diagnostics](api/diagnostics.md) · [fx](api/fx.md) · [game](api/game.md) · [gravity](api/gravity.md) · [hudfx](api/hudfx.md) · [input_state](api/input_state.md) · [network](api/network.md) · [protocol](api/protocol.md) · [rules](api/rules.md) · [runtime](api/runtime.md) · [tracing](api/tracing.md)
- Features: [dash](api/features-dash.md) · [double jump](api/features-double_jump.md) · [holster](api/features-holster.md) · [mantle](api/features-mantle.md) · [slam](api/features-slam.md) · [slide](api/features-slide.md) · [surface](api/features-surfacefx.md) · [surge](api/features-surge.md)

## Development

- [Architecture](development/architecture.md)
- [Build](development/build.md)
- [Test](development/test.md)
- [Releasing](development/releasing.md)
