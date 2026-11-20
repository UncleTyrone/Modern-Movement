[b][size=6]Modern Movement[/size][/b]

[b][size=5]Summary[/size][/b]
Modern Movement adds a double jump, a dash, mantling, a hold-to-slide, weapon holster, and a sprint surge to Borderlands: The Pre-Sequel. Oz slam stays the game's own slam. This build does not replace it.

This is the 3.62.0 package. It is the same file used for Borderlands 2. Slide works the same way in both games: hold crouch, let go to stop, and a landing slide only happens if you are still holding crouch.

[url=https://github.com/UncleTyrone/Modern-Movement]Source, changelog, and the file hash are on GitHub[/url]

[b][size=5]Requirements[/size][/b]
[list]
[*][url=https://github.com/bl-sdk/willow2-mod-manager/releases/tag/v3.8]Willow2 Mod Manager v3.8 (Slammer)[/url]. PythonSDK is required.[/*]
[*]Base 1.12, Networking 1.2, Keybinds 1.2, and UI Utils 1.5 come with that install.[/*]
[*]You do not install texloader yourself. The HUD images are in this package.[/*]
[/list]

[b][size=5]What's new in 3.62.0[/size][/b]
[list]
[*]Hold crouch to slide and let go to stop, the same as Borderlands 2. A slide jump does not force another slide when you land.[/*]
[*]Double jump and dash try the Oz air boost that is already in this game.[/*]
[*]Oz slam is left alone.[/*]
[*]Sprint Surge climbs from +30% to +70% of the run you already have. It can start on the surge key even if you were not already sprinting.[/*]
[*]Dust, wind, and a ring on a hard landing. A missing effect is skipped.[/*]
[*]A slide is footsteps only. Super sprint keeps the game's sprinting sounds. The beep is only the dash ready tone.[/*]
[/list]

[b][size=5]Installation[/size][/b]
[list=1]
[*]Install Willow2 v3.8 first.[/*]
[*]Copy [b]Modern_Movement.sdkmod[/b] into [b]BorderlandsPreSequel/sdk_mods[/b].[/*]
[*]Do not copy the .sha256 file or the manifest into that folder.[/*]
[*]Enable Modern Movement. Check the key bindings at the bottom of the options. Controller Dash and Toggle Holster start unbound so they do not take the D-pad weapon slots.[/*]
[*]Restart the game.[/*]
[/list]
If the menu shows two Modern Movement entries, keep this file and remove the other. Do not also enable an older 3.61.2 copy.

[b][size=5]How it plays[/size][/b]

[b][size=4]Slide[/size][/b]
[list]
[*]Hold crouch while sprinting. Let go and the slide stops.[/*]
[*]Jump out of it and you keep the speed. You slide again on landing only if crouch is still down, and only after the jump has been in the air for a moment.[/*]
[*]Press sprint again after you have let go of sprint and the slide ends then. The leftover time is not a wait.[/*]
[/list]

[b][size=4]Oz[/size][/b]
[list]
[*]Oz slam is the game's slam. This mod does not add a second one.[/*]
[*]A double jump tries the Oz air boost, then a normal jump sound if that boost is missing.[/*]
[*]A dash tries the Oz air boost first, then the whoosh.[/*]
[*]Those sounds are played from the game. They are not bundled in the mod file.[/*]
[/list]

[b][size=4]Dash, mantle, holster, surge[/size][/b]
[list]
[*]Dash on the ground or in the air. The cooldown is the limit unless you turn on air-only.[/*]
[*]Mantle grabs a ledge. Vault hops a low obstacle while you run.[/*]
[*]Holster on a key, or while you sprint.[/*]
[*]Sprint Surge adds +30% to +70% on the run you already have. On the ramp slider, 10 is ten seconds to full speed, not ten times speed.[/*]
[/list]

[b][size=5]Co-op[/size][/b]
Everyone who wants the moves installs this same file. The listen host writes the movement. Someone without the mod stays on normal movement and does not block the others. Each player keeps their own settings. Moon gravity down to 60 is accepted here. Borderlands 2 still uses its original floor.

[b][size=5]Compatibility[/size][/b]
Borderlands: The Pre-Sequel with Willow2 Mod Manager v3.8. The log is [b]Modern_Movement.log.txt[/b] next to the sdkmod.
