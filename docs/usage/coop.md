# Co-op

- Install and enable the same `Modern_Movement.sdkmod` on every peer who wants the abilities. Borderlands 2 peers also get Slam. Pre-Sequel peers keep native Oz slam.
- Peers without the mod join normally and stay vanilla.
- Listen host owns movement authority; joiners send intents through Networking when present.
- Each player keeps their own option values (strength, slide distance, indicators). The host menu does not force joiners.
- A joiner slide keeps its entry direction after you release forward. CrouchedPct times the length; Slide Speed (%) scales the coast. Joiner and host both re-apply that coast so the host correction does not stop you. Releasing crouch cancels that slide and tells the host to stand the body back up.
- Fast travel and level changes drop the old session and HELLO again. A loading screen with an empty player list does not kick joiners off the session.
