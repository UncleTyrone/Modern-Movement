# Co-op

- Install and enable the same `Modern_Movement.sdkmod` on every peer who wants the abilities.
- Peers without the mod join normally and stay vanilla.
- Listen host owns movement authority; joiners send intents through Networking when present.
- Each player keeps their own option values (strength, slide distance, indicators). The host menu does not force joiners.
- Mid-slide network path uses CrouchedPct only — no joiner Velocity writes during a slide.
