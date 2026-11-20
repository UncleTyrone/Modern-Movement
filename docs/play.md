[← Home](../README.md)

# Playing Modern Movement

Version 3.62.0. One file, `Modern_Movement.sdkmod`, runs in Borderlands 2 and in Borderlands: The Pre-Sequel. Double jump, dash, mantle, slide, surface effects, holster, and sprint surge load in both. Slam loads in Borderlands 2. The Pre-Sequel keeps its own Oz slam.

You need [Willow2 Mod Manager v3.8, Slammer](https://github.com/bl-sdk/willow2-mod-manager/releases/tag/v3.8) in each game. That is the PythonSDK package. It brings Base 1.12, Networking 1.2, Keybinds 1.2, and UI Utils 1.5. The HUD images ship inside this mod. If a texloader is already installed, that copy is used. If an image cannot be created, that mark draws with lines. Movement does not wait on it.

## Install

1. Install Willow2 v3.8 in the game you are playing.
2. Copy `Modern_Movement.sdkmod` into that game's `sdk_mods` folder. Leave the `.sha256` file and the manifest wherever you built them. Do not copy those two into the game folder.
3. Enable **Modern Movement**. Check the key bindings at the bottom of the mod options. Controller Dash and Toggle Holster start unbound so they do not take the D-pad weapon slots.
4. Restart the game.

If the menu shows two Modern Movement entries, keep this file and remove the other. Do not also enable the frozen 3.61.2 package from `archive/`.

To remove it, disable it in the menu and delete `Modern_Movement.sdkmod` from `sdk_mods`.

## How the moves feel

Hold crouch while you are sprinting, then let go. The slide stops, including a short hold. You do not press crouch a second time. That is the same in both games. Press sprint again after you have let go of sprint and the slide ends then. The time that slide had left is not a wait, and the sprint you were already holding does not end it.

Jump out of a slide and you keep that speed. You slide again on landing only if crouch is still held, and only after the jump has been in the air for a moment. Letting go before you land does not slide. The crouched body left over from the slide is not a hold. The landing slide goes the way you are facing. Sprint, jump, and hold crouch, with no slide before the jump, and you also slide when you land. Pressing crouch again during a slide does not start a second one. The gun comes back up when the slide ends.

On Borderlands 2, hold crouch in the air. A high jump slams, even if you are still moving and even after a slide jump. A shorter hop pulls you down once you are clearly off the ground. A step, a bump, a crouch on the ground, or the start of a slide does not. The crouch that starts a slide does not cancel it and start another. You do not have to clamp crouch until the top of the jump. A press in the air sticks for a moment. Letting go before you are high enough cancels it. The slam plays when you land, and the camera stays in your body instead of dropping through the floor. You can slide again right away. The Pre-Sequel does not use this slam. Oz slam stays the game's.

Dash on the ground or in the air. The cooldown is the limit unless you turn on air-only. Mantle grabs a ledge in the air. Vault hops a low obstacle while you are running. Holster puts the gun away on a key, or while you sprint. Sprint Surge is the next sprint press while you are already sprinting. Speed climbs from +30% to +70% of the run you already have. On the ramp slider, 10 is ten seconds to full speed, not ten times speed. In Borderlands 2 the first sprint press only sprints. The surge starts on the press after that.

## What you hear and see

A slide is footsteps on the ground for the whole slide. There is no whoosh when it starts. Super sprint keeps the game's sprinting sounds. A dash plays a whoosh. The beep is only the ready tone when the cooldown finishes. In The Pre-Sequel the dash tries the Oz air boost first, and a double jump tries that same boost. Those sounds are already in that game. They are not copied into this file. A Borderlands 2 slam plays the landing, and a full slam adds a short crack. There is no sound on the way down.

Dust follows a slide. A dash and a double jump kick up that same dust. A slam lands in a darker ring of it, with the dust around the ring. If an effect is missing, that one is skipped.

The marks around the crosshair are optional. Dash arrows, the ready pip, the perfect-dodge burst, the slide bar, and the surge arcs start on. The jump counter starts off. Slam brackets are Borderlands 2 only. The slide bar shrinks across the slide and is gone when it ends. Each mark has its own switch under that feature's Settings.

Jump, mantle, and double jump share the jump button. On a controller that is A. Sprint Surge defaults to the left stick click. Rebind Dash and Toggle Holster if you want them on the pad.

## Playing with other people

Everyone who wants the moves installs and enables this same file. The listen host writes the movement. Joiners send dash, slide, jump, mantle, surge, and slam through Networking 1.2. Each player keeps their own settings. A player without the mod stays on normal movement and does not block the others.

A joiner slide keeps going after you release forward. Letting go of crouch ends it. Fast travel starts the session again. A loading screen with an empty player list does not kick people off.

After you play, `Modern_Movement.log.txt` is written next to the sdkmod. Each machine has its own log.
