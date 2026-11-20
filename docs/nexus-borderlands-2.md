[b][size=6]Modern Movement[/size][/b]

[b][size=5]Summary[/size][/b]
Modern Movement adds a double jump, a dash, mantling, a hold-to-slide, weapon holster, and a sprint surge on top of Borderlands 2. Hold crouch in the air and a high jump slams. A shorter hop pulls you down once you are clearly off the ground. A slide on the ground stays a slide.

This is the 3.62.0 package. It is the same file used for The Pre-Sequel. Slam in this build is the Borderlands 2 slam. The Pre-Sequel page keeps Oz slam.

[url=https://github.com/UncleTyrone/Modern-Movement]Source, changelog, and the file hash are on GitHub[/url]

[b][size=5]Requirements[/size][/b]
[list]
[*][url=https://github.com/bl-sdk/willow2-mod-manager/releases/tag/v3.8]Willow2 Mod Manager v3.8 (Slammer)[/url]. PythonSDK is required.[/*]
[*]Base 1.12, Networking 1.2, Keybinds 1.2, and UI Utils 1.5 come with that install.[/*]
[*]You do not install texloader yourself. The HUD images are in this package.[/*]
[/list]

[b][size=5]What's new in 3.62.0[/size][/b]
[list]
[*]Hold crouch to slide and let go to stop, including a short hold.[/*]
[*]A slide jump lands in another slide only while crouch is still held.[/*]
[*]Slam needs real height. A high jump slams while you are moving, including after a slide jump. A step does not.[/*]
[*]You do not have to hold crouch until the top of the jump.[/*]
[*]Sprint Surge starts on the second sprint press, from +30% to +70% of the run you already have.[/*]
[*]Dust, wind, and a slam ring. A missing effect is skipped.[/*]
[*]A slide is footsteps only. Super sprint keeps the game's sprinting sounds. A dash plays a whoosh. The beep is only the ready tone.[/*]
[/list]

[b][size=5]Installation[/size][/b]
[list=1]
[*]Install Willow2 v3.8 first.[/*]
[*]Copy [b]Modern_Movement.sdkmod[/b] into [b]Borderlands 2/sdk_mods[/b].[/*]
[*]Do not copy the .sha256 file or the manifest into that folder.[/*]
[*]Enable Modern Movement. Check the key bindings at the bottom of the options. Controller Dash and Toggle Holster start unbound.[/*]
[*]Restart the game.[/*]
[/list]
If the menu shows two Modern Movement entries, keep this file and remove the other.

[b][size=5]How it plays[/size][/b]

[b][size=4]Slide[/size][/b]
[list]
[*]Hold crouch while sprinting. Let go and the slide stops.[/*]
[*]Jump out of it and you keep the speed. You slide again on landing only if crouch is still down, and only after the jump has been in the air for a moment.[/*]
[*]Press sprint again after you have let go of sprint and the slide ends then. The leftover time is not a wait.[/*]
[/list]

[b][size=4]Slam[/size][/b]
[list]
[*]Hold crouch in the air. A high jump slams even if you are still moving.[/*]
[*]A shorter hop pulls you down once you are clearly off the ground.[/*]
[*]The sound is the landing. A full slam adds a short crack. There is no whoosh on the way down.[/*]
[/list]

[b][size=4]Dash, mantle, holster, surge[/size][/b]
[list]
[*]Dash on the ground or in the air. The cooldown is the limit unless you turn on air-only.[/*]
[*]Mantle grabs a ledge. Vault hops a low obstacle while you run.[/*]
[*]Holster on a key, or while you sprint.[/*]
[*]Sprint Surge is the next sprint press while you are already sprinting. On the ramp slider, 10 is ten seconds to full speed, not ten times speed.[/*]
[/list]

[b][size=5]Co-op[/size][/b]
Everyone who wants the moves installs this same file. The listen host writes the movement. Someone without the mod stays on normal movement and does not block the others. Each player keeps their own settings.

[b][size=5]Compatibility[/size][/b]
Borderlands 2 with Willow2 Mod Manager v3.8. The log is [b]Modern_Movement.log.txt[/b] next to the sdkmod.
