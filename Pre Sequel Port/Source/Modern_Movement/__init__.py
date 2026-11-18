"""Modern Movement 3.62 — Borderlands: The Pre-Sequel

(Historical changelog below still mentions Borderlands 2; this package build is TPS-only.)

Gameplay features combined into one mod:
  - Double Jump:   press jump again in mid-air for an extra boost
  - Dash:          dash a fixed distance, forward or backward, on the ground or in the air
  - Holster:       put your weapon away (manually and while sprinting)
  - Sprint Surge:  press sprint again while sprinting for a speed boost
  - Mantle:        press jump near a ledge to pull yourself up onto it
  - Slide:         crouch while sprinting to slide

Layout
  core.py      shared PlayerTick hook, the single jump key, the "busy" flag, a small
               event bus and shared helpers
  tracing.py   line traces (wall / ledge detection) used by Mantle
  features/    one file per feature; each can be turned on or off from its own options
               group, and any of them can be removed by deleting its file and its
               line in _FEATURE_SPECS below

3.62.1 (TPS HUD + per-player polish)
  * Double Jump: Jump Counter restored (Off by default) — chevrons below-left of the crosshair show extra jumps left
  * Dash: Dash Ready Indicator defaults On; Perfect Dodge Effect toggle for the ECHO chevron burst
  * Every shipped indicator has its own On/Off; camera sliders back in each feature's Settings
  * Joiners keep their own Slide Distance and Double Jump Strength/Extra Jumps over host menus
  * Mods-page description matches the six shipped features (no omission language)

3.62.0 (TPS host-authoritative co-op)
  * Listen host owns all custom movement; clients send intents only
  * Same package required on every peer (Networking 1.2); readiness enforced before gameplay
  * Controller Dash and Toggle Holster default to unbound (avoid TPS D-pad weapon slots)
  * Custom Slam removed from the TPS deliverable; native Slam/Oz preserved
  * Slide jump/sprint/off-cliff exits clear crouch so native Slam is not auto-armed

3.61.2 (controller support — historical)
  * Every key has a controller twin; Jump / Mantle / Double Jump (A); Sprint Surge (left stick)
  * Holding jump to climb a ledge works with the controller jump button
  * Rebind controller keys in the menu as needed

3.61.1 (Borderlands: The Pre-Sequel support — historical baseline)
  * Ported to TPS; later 3.62 makes the package TPS-only fail-closed
  * Custom Slam skipped on TPS in favour of the native ground slam
  * Mantle/Vault: gravity is measured from your fall to time hops. Moon gravity is lower than Borderlands 2's,
    so on The Pre-Sequel readings down to 60 are accepted (300 before) instead of being thrown away
  * Sounds and effects that only exist in Borderlands 2 (the Longbow, Bee and Stalker sounds and the sand
    footstep switch) are skipped quietly if The Pre-Sequel doesn't have them, and logged once. They are
    cosmetic: the movement itself is unaffected

3.61
  New HUD feedback around the crosshair, in ECHO colours. texloader is recommended: the mod installs its
  images into texloader the first time it runs, and they load from the next game start (without
  texloader the effects are drawn from plain lines). Every indicator has its own On/Off toggle.
  * Dash: ECHO arrows around the crosshair show the direction you dash (replaces the game's shield-hit
    hexes, which could flash red like damage)
  * Dash: Dash Ready Indicator, a small hex below-right of the crosshair that fills while the dash cools
    down and pops when it's ready
  * Dash: Dash Damage Reduction (On). Damage you take while dashing, and just after, is reduced by 30%.
    A hit that lands within the Perfect Dash Window (ms) (default 150) of starting a dash is ignored
    completely, and ECHO chevrons burst out in all four directions. Damage you deal to yourself is
    never reduced
  * Double Jump: Jump Counter, chevrons below-left of the crosshair show the extra jumps you have left
  * Slam: Slam Indicator. Brackets below the crosshair show when you're high enough to slam, closing in
    the higher you are; they flash when the slam starts and a shockwave ripples out on impact, wider for
    a harder slam
  * Slide: Slide Indicator, a momentum bar below the crosshair that shrinks as the slide loses speed
    (how much a slide jump would carry); a slide jump makes it flash and lift away
  * Sprint Surge: the speed boost now starts at 30% and builds to 70% over Sprint Surge Speed Ramp Up
    (default 3 s), replacing Sprint Surge Speed Boost (%)
  * Sprint Surge: Sprint Surge Indicator. Arcs either side of the crosshair grow out from their middles
    when a surge starts, push outward as the boost builds, then pulse and sweep away at full boost. They
    flicker when an action skill is blocked (coming back for a moment if they've already gone)
  * The crouch icon stays hidden for 2 seconds after a slide or a slam, unless you press crouch again
  * Slam: fixed a crash when a slam killed an EXP Loader. The blast now goes off from your grenade at
    your feet (like a real grenade) instead of from you. It uses a plain explosive impact effect, where
    it could pick an elemental one before
  * Camera tilts now add to the view's roll instead of replacing it, so they combine with other mods
    that tilt the view
  * Slide: taking damage no longer ends a slide (a hit's push or flinch is ridden out)
  * Slam: Knockback Strength (1000) and Knockback Radius (600) are now fixed values and no longer in
    the menu

3.36
  * Dash: new Air Dash Only toggle in its Settings (off by default): on, dashes only work in the air
  * Double Jump: Only While Rising now defaults to Off

3.35
  * Slam: no more game crashes when a slam kills an enemy or sets off a barrel. The blast uses the
    game's own "cause radius damage" behavior with a full set of damage data (an explosive damage
    type and an impact definition for hit effects and sounds), dealt by your equipped grenade
  * Slam: Knockback Method removed (the blast is always used) and the Slam Knockback toggle removed:
    Slam Damage turns the blast (damage and knockback) on or off. Off: you just slam down
  * Slam: Slam Damage (%) (default 50) is a share of your equipped grenade's damage; no grenade = 1
  * Slam: new descriptions for Slam Damage, Slam Damage (%) and Slam Height Scaling
  * Slam: console lines turned off

3.34.1
  * Slam: Knockback Strength defaults to 1000

3.34
  * Slam: the Explosion knockback is locked in (Knockback Method removed)
  * Slam: new Slam Damage toggle (below Slam Knockback). Off: no damage, and the knockback is a plain
    push instead (which also leaves friendly NPCs and anyone behind a wall alone)
  * Slam: Slam Damage (%) is no longer temporary; new descriptions for it and Slam Height Scaling

3.33
  * Slam: Knockback Method now defaults to Explosion
  * Slam: the explosion deals your equipped grenade's damage (temporary Slam Damage (%) slider, default
    100, and scaled with height like the knockback). No grenade equipped, or its damage can't be read:
    1 damage. The console says where the grenade damage was read from

3.32
  * Slam knockback: friendly NPCs are left alone (the game's team, allegiance and team-number labels
    are checked), and so is anyone with a wall between them and where you landed
  * Slam: temporary Knockback Method toggle (Push / Explosion) to compare. Explosion asks the game for a
    small blast (1 damage) so its own rules decide who is hit; if the game refuses, Push is used
  * Temporary: a line per nearby character is printed in the console on each slam (what it is, its
    allegiance, and whether it was thrown or why not)

3.31.2
  * Slam: the minimum height is counted from where you left the ground, not from the ground below you.
    Walking or jumping off a ledge, you can slam straight away; a slide jump only needs to be clear of
    the ground. A plain jump on flat ground still has to reach Slam Min Height
  * Slam knockback: no longer knocks NPCs through walls or the floor. Pawns are pushed with the game's
    own AddVelocity, once; their movement mode is only switched to falling if they are plainly walking
    with world collision on (forcing it on pawns in special movement modes dropped them through the map)

3.31.1
  * Slam: every crouch press in the air now counts straight away. The crouch key itself is watched (read
    from your key bindings), not just the crouch state: with toggle crouch, a press in the air could
    switch crouch off (after jumping while crouched or out of a slide) and was missed

3.31
  * New defaults: Slide Distance 80%, Knockback Strength 800, Knockback Radius 600, Slam Height
    Scaling 40%. Dash stays on X
  * Slam Height Scaling description: "Slamming effects and knockback scale with height."

3.30
  * Slam: Slam Height Scaling (%) (default 100). The further you plunge, the harder it hits: a slam
    from 500 units up is normal, from lower it's softer (down to half), from higher it's stronger (up
    to 3x knockback strength, a wider radius and up to 2x the camera crunch). 0 = every slam the same

3.29
  * Slam: you come out of a slam standing (crouch, including toggle crouch, is switched off on impact)
  * Slam: Knockback Radius (450) is back in its Settings; Slam Press Window is fixed at 1500 ms
  * Slam: the knockback summary line is no longer printed in the console

3.28.1
  * Slam: temporary Slam Press Window (ms) slider (default 400) in its Settings

3.28
  * Slam: Slam Speed (2600), Slam Min Height (60%), Knockback Radius (450), Slam Camera Shake (100%) and
    Slam Camera Push (150%) are fixed values and no longer in the menu
  * Slam: a crouch press in the air keeps trying for 0.4 s, so pressing a little early (still too low,
    or during a dash) still slams; a dash is cut short by the slam
  * Knockback Strength description updated

3.27.3
  * Slam: the impact sound is fixed to Ak_Play_Exp_Elemental_Explosive_SM (Slam Impact Sound Variant 4);
    the slider is removed

3.27.2
  * Slam knockback: enemies' health can't be read in this game, so every enemy was skipped as "no
    health". Dead enemies are now recognised by the game's death flags instead

3.27.1
  * Slam knockback: enemies were not pushed. The likely cause: the engine's "player" flag can be set on
    enemy AI too, so enemies were skipped; now only real player controllers are skipped. The push uses the
    game's AddVelocity plus a direct velocity write, and is re-applied for a few ticks if the AI puts the
    enemy back on its feet. A summary line is printed in the console on each slam

3.27
  * New feature: Slam. Press crouch while high in the air (higher than a normal jump) to plunge straight
    down. Dive whoosh and a downward camera tip on the way down; a landing thud, a heavy impact layer and
    a camera crunch on impact; nearby enemies are knocked back (Slam Knockback). A jump, mantle or dash
    during the plunge ends it. Temporary tuning sliders are in its Settings
  * Mod description lists Slam

3.26
  * The Mantle page is renamed Mantle/Vault

3.25
  * Each feature is now its own clickable page in the menu (no "Options -" headers): its Enabled
    toggle and its Settings submenu are inside
  * Slide Distance now defaults to 40%

3.24
  * Every section now shows only its Enabled toggle (and Mantle's Vault toggle); all other options
    moved into that section's Settings submenu

3.23
  * Settings submenus: Double Jump (Only While Rising, Double Jump Strength), Sprint Surge (Sprint
    Surge Speed Boost) and Slide (new Slide Distance (%), default 100: 200 slides twice as far on
    flat ground)

3.22
  * Dash: the default key is now X (was Middle Mouse). Toggle Holster stays on Left Alt

3.21
  * Double Jump: Strength (100), Only While Rising (on) and Camera Push (50) are now fixed values and
    no longer in the menu. Extra Jumps is the last option in the section
  * Sprint Surge: Speed Boost (60) and Camera Tilt (80) are now fixed values and no longer in the menu
  * Options - Holster is renamed Options - Misc and is the last section, just above the key bindings

3.20
  * Double Jump: coyote jump. Walk or run off a ledge and press jump within 0.15 s: you get your normal
    jump, and the double jump is still available
  * Double Jump: Strength now sets height. 100% rises as high as a normal jump whether you are rising or
    falling, and 200% rises twice as high
  * Double Jump: your sideways speed bends toward the movement keys you hold, so you can change direction
    mid-air
  * Double Jump: Double Jump Camera Push (%) (default 50, temporary). The view nods up briefly, then eases
    back. Your aim returns exactly

3.19
  * Sprint Surge: press the Sprint Surge key again while surging to end it (the weapon is drawn and the
    boost stops; you keep sprinting without stowing again until the sprint ends)
  * Sprint Surge: Sprint Surge Camera Tilt (%) (default 50). The view leans forward while surging (3
    degrees at 100%) and eases back when it ends. Your aim moves with it and returns exactly

3.18.1
  * Dash section description: "Dash forwards, backwards, and side to side with a hotkey. Works on the
    ground or in the air."

3.18
  * Air Dash is now Dash: the section, its options and its key are named Dash (Dash Enabled, Dash
    Cooldown (s), Dash Audio Effect, Dash Cooldown Audio Effect, Dash Screen Effect)
  * Dash works on the ground and in the air (Ground Dash is part of it; the toggle is gone)
  * Air Dashes Available removed: the cooldown is the only limit on how often you can dash
  * Mantle description: "...by pressing or holding jump while airborne."

3.17
  * Mantle: Auto Mantle removed (and with it the automatic grab after an air dash); mantling is by
    pressing or holding jump. Section description updated to match
  * Mantle: Failed Mantle Boost fixed at 65% and removed from the menu
  * Slide: Slide Sound Variant (1), Slide Sound Rate (70%) and Slide Camera Push (80%) fixed and removed
    from the menu

3.16.6
  * Slide: the scrape always uses the sand / dirt version of the footstep, whatever you slide on (the
    footstep surface switch is set to sand before each scrape step; your real footsteps are unaffected)

3.16.5
  * Slide: a new scrape sound that plays on every map. It is made from your own footstep sound (always
    loaded, and it follows the floor: dirt, metal, snow...) repeated fast at the start of a slide and
    slowing as it runs out. Replaces the stalker scrape, which only played on maps with stalkers
  * Slide Sound Variant and Slide Sound Rate (%) (temporary): pick which footstep sound and how fast it
    repeats; the console lists the variants the first time you slide

3.16.4
  * Slide: Slide Camera Push (%) (default 50). The view tilts back while you slide, more the faster you go
    (3 degrees at 100%), and eases level as the slide slows or ends. Your aim moves with it and returns
    exactly

3.16.3
  * Mantle: Failed Mantle Boost (%) (default 25). When a climb is stopped partway up, you now let go into a
    normal fall with this share of your own jump as lift (never more than the climb was rising at).
    Before, you kept the climb's full upward speed, which could launch you far higher than a jump

3.16.2
  * Fixed: changing your movement state never worked. The game ignores SetPhysics from Python (tested),
    so the mod now writes the state directly (tested: works). This is why Ground Dash only glided: you
    never left walking, which caps your speed. A ground dash is now really an air dash a few units
    above the floor: same distance, speed and snap
  * Mantle / Vault: the climb runs in falling physics on purpose (what every climb really did before),
    and a vault now starts cleanly from the ground instead of relying on the game's own jump
  * A jump press during a climb is ignored (it could spend a double jump)

3.16.1
  * Ground Dash: now an air dash taken just above the floor. It starts with a tiny skim timed to land as
    the dash ends, so it has the same 800-unit distance, speed and snap as an air dash (gliding was
    capped by the game's flying speed). Touching the floor early (a bump, a slope) skims off again
  * Air Dash: Forward / Backward Dash Camera Push fixed at 80% and removed from the menu
  * Slide: holding forward barely steers the slide any more (25% of the steering rate); strafing still
    steers at the full rate

3.16
  * Air Dash: Ground Dash (off by default) lets the dash be used on the ground. A ground dash glides you
    along the floor (gentle slopes are fine; a step or wall ends it) and does not use up an air dash
  * Air Dash: Forward Dash Camera Push (%) and Backward Dash Camera Push (%) (default 50): the view nods
    down on a forward dash and up on a backward one, then eases back (3 degrees at 100%). Your aim
    moves with the view and returns exactly where your own mouse movement put it
  * Slide is back in the mod (Slide Enabled and Slide Audio Effect)

3.15
  * Mantle Indicator removed
  * Mantle: removed the Vault Max Height, Mantle Max Height, Mantle Look Angle, Vault Look Angle and
    Mantle Debug Log options; fixed at 160, 200, 60, 20 and off
  * Vault description ends with "(requires mantle)"

3.14.1
  * Mantle / Vault performance (stutter near obstacles): in the worst cases tested a ledge search used
    up to 169 traces in one frame; now at most 56 (20 on average, was 34), and never more than 120:
    - a wall seen by several look traces is measured once per search
    - the edge finder steps 20 units then refines (same ~1.3 unit precision, fewer traces)
    - the "look again from higher up" top check is capped and remembered per spot
    - a hard budget of 120 traces per search: past it, the search gives up for that frame
  * The indicator checks less: it reuses its last answer while you have not moved 8 units or turned
    3 degrees (refreshed at least every 0.6 s), and its checks share one trace weapon
  * The trace weapon is only created when a search actually traces (none for checks that end early)
  * Fixed: a surface taller than a small step at the landing spot raised the landing height instead of
    counting as an obstacle (a kerb right behind a ledge could be climbed into)

3.14
  * Mantle / Vault: rise, then hop. The climb is scripted only while rising straight up to just above the
    edge; there it hands you to the game's own physics with a computed hop (forward speed and a little
    lift) that lands you on the ledge about where the old climb ended. The game's collision then does
    the rest: small lips and steps are stepped up, props are slid around, and an invisible wall stops
    you like a normal jump would (no freezing at the top)
  * Vault over: the hop just clears the obstacle and lands you on the far side where the arc comes down
  * Narrow tops get a slow hop that lands almost in place
  * The hop uses gravity measured from how you actually fall (else the level's value)
  * The landing sound and shake play when you touch down

3.13.6
  * Mantle / Vault: body sweeps switched off. The line-trace room checks from 3.12.2 (headroom, nothing
    overhead, a clear way in, room to pass over and to land) are used again. Everything else since
    3.12.2 stays: the ground mantle preview, the attempt recorder, the hold-loop fix, landing on the
    highest surface under your footprint, and letting go early when a climb is held back

3.13.5
  * Mantle / Vault: body sweeps no longer switch themselves off. One look trace that seemed to hit your
    own body used to turn them off for the rest of the session; now just that trace is redone from
    outside your body (only if traces never get past your body, from the very start, are they off)
  * Mantle / Vault: when a climb is clearly being held back while you rise (your body has barely moved
    toward the ledge while the plan has you well on the way), it lets go at once as a normal jump,
    still going up, instead of floating to the top and dropping you
  * Mantle Debug Log: each climb is now recorded frame by frame (position, the velocity found, the
    velocity set, movement state) in its end record

3.13.4
  * Mantle / Vault: removed the blocked-spot memory (and the 1 s retry lock from 3.13.2). Every spot is
    always tried. Holding jump still won't re-climb until you let go after a climb ends

3.13.3
  * Mantle / Vault: the body sweep now uses a box as wide and as tall as your body (it was 85% wide and
    90% tall, and real climbs were getting stuck in that margin on bricks and lips). A box corner
    that already touches a wall at the start of a piece is checked again with a smaller box
  * Mantle / Vault: a higher arc (12 more units over the edge) is tried when the normal one would clip
    a small lip or raised brick, before the lower arc for tight gaps
  * Mantle / Vault: you land on the highest surface under your whole footprint (up to 24 higher than
    the spot itself), so a small step or lip next to the landing spot lifts you onto it instead of
    stopping you (while climbing you fly, and a flying body doesn't step up)
  * Mantle / Vault: spots where a climb got blocked (usually an invisible wall, which traces can't see)
    are remembered for 10 minutes: no indicator there, Auto Mantle and holding jump don't retry them,
    and a deliberate press only retries one every 5 s

3.13.2
  * Mantle Debug Log now also records every mantle / vault attempt in full (your position and view,
    every trace with where it hit, the edge and landing chosen or why it failed, and how each climb
    ended) to Modern_Movement_mantle_debug.txt in the SDK settings folder (the console says where)
  * Mantle: holding jump no longer loops in place. After a climb ends while you hold jump, holding
    does nothing until you let go, and a spot where a climb was blocked is not retried by holding
    jump or Auto Mantle for 1 s

3.13.1
  * Mantle Indicator: also shows on the ground when a ledge is too tall to vault but a jump and a
    press in the air would mantle it (allowing for your jump height, read from the game). One
    chevron = vault, two stacked chevrons = mantle
  * Mantle Debug Log: shows the jump height read from the game, once

3.13
  * Mantle / Vault: "check the move" with body sweeps. Before any climb or vault, a box about the size
    of your body is swept along the exact path it will take (tested in game: the trace weapon's
    Extent sweeps a box). If your body would hit anything on the way (a beam, an awning, a railing's
    top rail, something behind a thin ledge, a wide base), that path is not used and the next
    candidate is tried. This replaces the separate headroom, overhead, clear-way and room-to-land
    checks. In a tight gap a lower arc is tried before giving up
  * Body sweeps are used once look traces are known to ignore your body (the debug log's first line
    says "body sweeps ON"); otherwise the older checks are used as before

3.12.2
  * Vault over balustrades and barriers: the landing spot is placed past how far the obstacle reaches
    on the far side at several heights (its base is often wider than its top rail), instead of just
    past the top. Fixes "can't vault over: something right behind it"
  * Gaps between balusters: the edge finder looks 24 units deep (not 8) for a top rail above a gap, so
    a top rail set back from the base is found. Fixes "no room above the top" on balustrades

3.12.1
  * Vault over railings at a drop: when the ground on the far side is more than 120 below, the vault
    carries you over and releases you into a normal fall with your forward momentum, as long as there
    is ground within 600 below (never into a void)
  * Vault / Mantle: railings with gaps between the bars. When the face stops and starts again within
    36 units above, the edge finder keeps climbing to the real top (the lower edges are kept as
    fallbacks)

3.12
  * Vault over: thin obstacles you can't stand on (railings, barriers, low walls) are vaulted OVER. The
    vault measures how thick the top is, finds floor on the far side (at most 120 below your feet),
    checks there is room to pass over (nothing overhead such as a beam or doorframe) and to land,
    then carries you up, across and down the other side. Thick obstacles are still vaulted onto
  * Mantle Debug Log: a vault over says ", over"

3.11
  * Vault: consistent detection. Besides the look traces, a vault now also traces straight ahead the
    way you are facing (whatever your pitch) at a few heights up to Vault Max Height, reaching 50
    units past you plus 0.3 s of your speed. Low obstacles are found while you look at the horizon;
    before, they sat below every look trace unless you looked down at them
  * Vault: a jump the game starts a moment before the mod sees your press still counts as a vault
    (an air press within 0.2 s of leaving the ground)

3.10.10
  * Mantle / Air Dash: smoother dash into a mantle. The mantle now cancels the air dash before it reads
    your motion: your speed goes back to what it was before the dash, the dash's straight lock is
    skipped, and its camera shake and lean end in 0.1 s instead of fading over the climb. Before, the
    climb started from the dash's 4000 u/s, which lurched at the start and could fling you off the top
  * Mantle: the speed a climb blends from, and the momentum kept at the top, never exceed your run speed

3.10.9
  * Mantle: standing right against a wall. The hidden trace weapon now has your character as its
    owner (Instigator), which normally makes its traces ignore your body, so look traces can start
    from the middle of your body, well clear of the wall. If the game does not honour that, this
    is detected on the first press and traces start just outside your body as before. The debug
    log says which on the first check

3.10.8
  * Mantle: roofs that rise behind the edge. When the top check finds nothing (it started inside the
    roof, where the game often reports nothing), it tries again from higher up, as far as Mantle
    Max Height
  * Mantle: a new safety check traces from the open air above the edge to the landing spot, so a top
    found from inside something, or one with a raised part in the way, is never used

3.10.7
  * Mantle: roof trim and cornices. When the top check starts inside trim that sticks out over a wall,
    it steps up past it to find the real roof
  * Mantle Max Height (temporary, default 160): the tallest ledge you can mantle, above your feet

3.10.6
  * Mantle: a wall with something taller just behind it (a building, a back wall) is no longer read as
    one wall taller than 160. The edge finder measures where the wall face itself ends as well as
    how high things go behind it, and tries landing on the wall's own top. A new check makes sure
    there is room for your body past the landing spot
  * Mantle Look Angle (°) and Vault Look Angle (°) (temporary, default 20): how far below the crosshair
    mantles and vaults look for a ledge
  * Mantle Debug Log: shows the wall's edge and what is behind it ("edge at +120 (behind it: solid
    past +167)")

3.10.5
  * Mantle: rounded and sloped tops. The edge finder now checks as deep as you would stand (about 54
    units past the face), so a top that leans back is measured at its real top instead of where it
    first leans away. A sloped surface under your crosshair counts as a top, and a top that only
    flattens out further in gets one deeper landing try

3.10.4
  * Mantle: new edge finder. Short flat traces step up the wall face until they stop hitting, which
    measures exactly where the top edge is; the top check then starts just above that edge. Before,
    it traced down from 160 units above your feet, which started INSIDE thick or tall walls, where
    the game reports nothing ("nothing down to the minimum height")
  * Mantle Debug Log: shows the edge height ("edge at +N"), or how high a too-tall wall goes

3.10.3
  * Mantle: ledges under an overhang, awning or ceiling are found. The downward top check used to stop
    at the underside of whatever was above the ledge ("too steep, normal z=-1"); it now continues
    from just below it (the headroom check still rejects ledges with too little room)
  * Mantle: narrow ledges (wall tops about 25-40 units deep) are found by retrying closer to the edge
  * Mantle Debug Log: each failed trace now says how high it hit the wall, and what the top check
    found at each depth

3.10.2
  * Mantle: fixed ledge detection almost never working in 3.10.1. Look traces started inside your own
    body and never got out; they now start at eye height half a unit outside your body (close
    enough to still see a wall you are pressed against, which 3.10 missed)

3.10.1
  * Mantle: fixed mantles failing when standing right against a wall. Look traces started just outside
    your body, which is inside a wall you are pressed against; they now start at your eyes
  * Mantle: looking steeply up at a tall ledge right above you also traces at 30, 15 and 0 degrees
    above level, so the lip is still found

3.10
  * Mantle Indicator (on by default): a small chevron under the crosshair whenever pressing jump
    right now would mantle (in the air) or vault (on the ground)
  * Mantle: climbs along the way you are moving when you come in at an angle (up to about 53
    degrees off straight), instead of squaring up to the wall
  * Mantle: hold to mantle. Holding jump in the air keeps looking for a ledge, so you can jump,
    keep holding, and grab the ledge as soon as it is in reach. (Reads the game's held keys; if
    they can't be read, presses work as before. The debug log says which)

3.9
  * Mantle / Vault: look traces. A mantle only targets the ledge you are looking at: traces go out
    along the crosshair and 10 and 20 degrees below it, and the first one that lands on a ledge
    (its top or the wall under it) within 160 units wins. The forward probes are gone (no
    fallback while look traces are tested). Mantle Debug Log now also reports air presses, says
    which trace found the ledge, and gives each trace's reason when nothing is found

3.8.1
  * Vault: easier to trigger. It looks further ahead the faster you run (up to 170 units at run
    speed), along the way you are moving rather than only where the camera points. A press that
    is a little early keeps looking for 350 ms into the jump, and then also catches obstacles you
    have already partly risen past
  * Mantle Debug Log (temporary): prints one line to the console for every running jump, saying
    whether it vaulted and why not

3.8
  * Mantle: Vault (on by default). Press jump on the ground while moving into a low obstacle and you
    climb straight onto it, with no jump first. Vault Max Height (default 100) sets how tall; taller
    ledges still need a jump first

3.7.1
  * Mantle: the Mantle Camera Shake (30%) and Lower Weapon While Mantling (on) options are removed;
    both stay as fixed behaviour

3.7
  * Mantle: Lower Weapon While Mantling (on by default). The weapon is put away as you grab and drawn
    again at the end of the climb; firing or aiming draws it straight away. A weapon you had
    already holstered stays holstered
  * Mantle: the sound is split. The ladder step plays as you grab, the landing step at the top

3.6
  * Mantle: smoother climb. It follows a timed curve, and its length scales with the ledge height
    (0.4 s for the tallest). Your motion going in is blended into the climb (90 ms), and you keep
    60% of your forward momentum at the top. The camera dips as you grab, rises as you pull up
    and tilts slightly
  * Mantle: Mantle Enabled and Auto Mantle are on by default; Mantle Camera Shake defaults to 30%
  * Double Jump: Extra Jumps defaults to 1

3.5
  * Mantle: a sound on reaching the top (the landing footstep and ladder-climb step together;
    option: Mantle Audio Effect) and a short camera shake (Mantle Camera Shake (%), default 50)
  * Slide is parked: its file is kept in the mod but not loaded, so it has no menu entry, no
    settings and no cost. The notes below describe it for when it returns
  * New feature, Slide: crouch while sprinting (or land with crouch on while moving forward fast)
    to slide. It starts from your momentum plus a boost, slows with friction, speeds up downhill,
    can be steered a little, and ends when you slow to crouch speed, stand up, jump or hit
    something. Jumping at any point in a slide stands you up and launches you with the slide's
    current speed and direction (Slide Jump Momentum / Slide Jump Height sliders). Pressing
    crouch in the air within Slide Landing Window (ms) of touching down slides on landing.
    Pressing back during a slide cancels it (Back Cancels Slide). A light camera bob and tilt
    while sliding, fading as you slow (Slide Camera Shake (%), aim is not moved). Standing up or
    jumping out of a slide keeps its speed: top speed eases back to normal over Slide Momentum
    Carry (ms), and stopping cancels it
  * The pawn's GroundSpeed is now owned by core: Sprint Surge and the slide's momentum carry
    hand it multipliers, so they combine instead of fighting, and the game's own value is always
    put back
  * Slide: the Slide Cooldown slider is replaced by Sprint Before Next Slide (ms): after a slide
    you must sprint this long, unbroken, before the next one (default 500)
  * Defaults updated to the author's settings: Slide Boost 100%, Slide Landing Window 700 ms,
    Slide Camera Shake 20%
  * Slide is tuned: only Slide Enabled and Slide Audio Effect remain in the menu. Fixed at the
    author's values: Boost 100%, Friction 300, Slope Effect 200%, Steering 45 deg/s, Min Speed
    110%, Max Speed 350%, Slide From Landing on (700 ms window), Sprint Before Next Slide 200 ms,
    Back Cancels Slide on, Slide Jump Momentum 100% / Height 125%, Momentum Carry 1000 ms,
    Camera Shake 30%
  * Slide sound: the stalker's scraping step (Slide Audio Effect), loaded by the mod itself when
    the map doesn't have it
  * Slide: the HUD's crouch icon is hidden while sliding, and while crouch is on in the air (so a
    jump into a landing slide never shows it); it comes back otherwise
  * Sounds are looked up fresh every time they play instead of being kept: a sound from a map
    that was unloaded can no longer go silent, and a missing sound is retried after a few seconds
  * Camera effects: a camera shake and a lean toward the dash side on the air dash, and a
    camera shake on each double jump (fixed at tuned values: Air Dash shake 20%, lean 50%;
    Double Jump shake 50%). All camera effects (with the slide's shake) go through camera.py,
    which adds them together and takes them back out exactly; tilt never moves your aim
  * Defaults are now the author's settings (Extra Jumps 2, Air Dash Cooldown 2 s, Sprint Surge
    Speed Boost 75%, Mantle off, Slide Boost 80%, Slide Friction 300, Slope Effect 200%, Slide
    Cooldown 1000 ms, Slide Landing Window 500 ms; Air Dash on Middle Mouse, Toggle Holster on
    Left Alt) Sliders for boost, friction, slope effect, steering, minimum and
    maximum speed and cooldown, for tuning

3.4
  * Air Dash: the shield hex pattern flashes on the side of the screen you dash toward (left,
    right, top for forward, bottom for backward), using the game's own shield-hit indicator
    (option: Air Dash Screen Effect). It is now the air dash's only visual effect: the
    digistruct burst and its Air Dash Effect option are removed

3.3
  * Double Jump: a sound effect when you double jump (option: Double Jump Audio Effect)
  * Mantle: fixed a game crash. The hidden weapon used for ledge traces is now created and destroyed
    for each ledge search instead of being kept, because the game can delete it in between
  * Air Dash: only works while airborne (no dashing from the ground)
  * Air Dash: a digistruct effect (option: Air Dash Effect) held in front of you for the length of the
    air dash, then faded out
  * Air Dash: a teleport sound when the air dash starts (option: Air Dash Audio Effect)

3.9.1
  * Author is now Jinxxtt

3.9.0
  * Sprint Surge: action skills can't be used while a Sprint Surge is active

3.8.9
  * Removed the Log Dump section and its debug logging toggles

3.8.8
  * Sprint Surge is now its own options group (Sprint Surge Enabled + Speed Boost) and works
    independently of Holster Enabled

3.8.7
  * Consistent "Turn X on or off." enable descriptions; Active Sprint Surge key is now Sprint Surge;
    Mantle description no longer mentions a hotkey

3.8.6
  * Mantle: removed Max Height, Reach, Speed, Cooldown, Jump Buffer, From Ground and After Air Dash
    options (fixed at 160, 50, 1500, 300 ms, 250 ms, off; after-air-dash follows Auto Mantle);
    updated section and Auto Mantle descriptions

3.8.5
  * Mod description now lists Mantle

3.8.4
  * Updated the mod description

3.8.3
  * Double Jump: updated the section description and the Double Jump Strength and Only While
    Rising descriptions

3.8.2
  * Air Dash: updated the Omnidirectional Air Dash description

3.8.1
  * Air Dash: updated the section description

3.8.0
  * Air Dash: by default it now goes backward when you are holding back (forward otherwise);
    Omnidirectional Air Dash still allows any direction, including sideways

3.7.5
  * Air Dash: the movement-direction option is named Omnidirectional Air Dash

3.7.4
  * Air Dash: Air Dashes Available has an updated description

3.7.3
  * Air Dash: Air Dashes Per Normal Jump is renamed Air Dashes Available

3.7.2
  * Air Dash: Air Dash Cooldown (s) and Air Dashes Available have new descriptions (the latter is renamed)

3.7.1
  * Air Dash: the Air Dash Distance slider is removed and fixed at 800

3.7.0
  * Forward Dash is now Air Dash: the section, its options, its key, Mantle After Air Dash and all
    log text use the new name

3.6.7
  * Double Jump: the Peak Grace slider is removed and fixed at 150

3.6.6
  * Air Dash: the cooldown is now set in whole seconds (Air Dash Cooldown (s), default 1, 0 to 5)

3.6.5
  * Holster: fixed some state not resetting when the mod is enabled

3.6.4
  * Holster: added a Holster Enabled option at the top of the section that turns the whole section on or off

3.6.3
  * Holster: the Sprint Surge keybind is named Active Sprint Surge, Sprint Surge has an updated
    description, and Sprint Surge Speed Boost shows its (%) unit

3.6.2
  * Holster: simplified to four options: Holster While Sprinting (off by default), Sprint Surge, Sprint
    Surge Speed Boost, and the hotkey. The feature is always enabled. Fire / aim always draws the weapon
    straight away, and a holstered weapon is drawn again the moment the sprint ends

3.4.1
  * Air Dash: simplified. Ease-out, speed, exit momentum, post-air-dash lock and gravity hold sliders are
    removed and fixed at tuned values (speed 4000, no ease-out, full forward momentum, 100 ms lock,
    no gravity hold)

3.4.0
  * Air Dash: precise, straight air dashes. Only speed in the air dash direction carries out of one (no sideways
    drift), the path is held on the aimed line, and a short straight lock cancels sideways
    drift right after the air dash

3.3.3
  * Air Dash: fixed a backwards bounce after air dashing back the way you were moving. The velocity handed
    back at the end no longer includes any part that opposes the air dash or points into a wall

3.3.2
  * Holster: Sprint Surge (press sprint again while sprinting to holster the weapon and get a speed
    boost, scaled from GroundSpeed)
  * Mantle After Air Dash (air dash at a ledge out of reach and you climb it)
  * Line traces live in tracing.py; features talk through core events instead of
    importing each other

3.0.0 (refactor)
  * One PlayerTick hook for everything; one jump key shared by mantle and double jump
  * Holster no longer blocks other characters' weapon switching; ignores vehicles
  * Mantle: no more leaked trace weapons, jump buffering, smoother motion, multi-height
    ledge detection, ends in normal walking physics
  * Air Dash: hands back your pre-air-dash velocity, air dashes per jump, optional movement-input
    direction, optional air gravity hold
  * Double jump scales with the pawn's own jump strength and never slows you down
  * Every slider is a whole number (times are in milliseconds, strengths in percent)
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

from mods_base import build_mod

try:
    from mods_base import NestedOption as GroupedOption  # each feature is its own clickable page
except ImportError:
    try:
        from mods_base import GroupedOption
    except ImportError:  # older mods_base: fall back to a flat options list
        GroupedOption = None

from . import core as _core
from . import game as _game
from . import hudfx as _hudfx
from . import rules as _rules

__version__ = "3.62.1"
__author__ = "Jinxxtt"
__credits__ = "Original Modern Movement by Jinxxtt; TPS co-op authority port maintained in-tree."


def _log(message: str) -> None:
    print(f"[Modern Movement] {message}")


# Feature modules, in the order they appear in the options menu. Custom Slam is intentionally
# absent: TPS owns native Slam/Oz and the co-op package must not ship a competing implementation.
_FEATURE_SPECS = (
    ("Double Jump", "double_jump", "Perform an additional jump while airborne."),
    ("Dash", "dash", "Dash forwards, backwards, and side to side with a hotkey. Works on the ground or in the air."),
    ("Misc", "holster", "Holster your weapon by hotkey or automatically when sprinting."),
    ("Sprint Surge", "surge", "Press sprint again while sprinting to holster your weapon and receive a speed boost."),
    ("Mantle/Vault", "mantle", "Allows for mantling ledges and various obstacles by pressing or holding jump while airborne."),
    ("Slide", "slide", "Crouch while sprinting to slide. The more momentum you bring, the further you go."),
)

_FEATURES = []
_ENABLED_STACK: list[str] = []
_BLOCKED = False
_NETWORKING_OK = False

_log(f"game: {_game.current()}")

if not _game.supported():
    _BLOCKED = True
    _log(
        "refusing to load: this package is TPS-only and the running game was not detected as "
        "Borderlands: The Pre-Sequel"
    )

if not _BLOCKED:
    for _label, _module_name, _blurb in _FEATURE_SPECS:
        try:
            _FEATURES.append(
                (_label, _importlib.import_module(f".features.{_module_name}", __package__), _blurb)
            )
            _log(f"feature loaded: {_label}")
        except Exception as _e:
            _log(f"feature '{_label}' failed to load and was skipped: {_e!r}")


def _duplicate_install() -> bool:
    """True when another Modern Movement package is already present in the process."""
    hits = [
        name
        for name in _sys.modules
        if name != __name__
        and (
            name == "Modern Movement"
            or name.endswith(".Modern Movement")
            or name == "Modern_Movement"
            or name.endswith(".Modern_Movement")
        )
        and name.split(".")[-1] in {"Modern Movement", "Modern_Movement"}
    ]
    # The package itself and its submodules are expected; another top-level package is not.
    foreign = [
        name
        for name in hits
        if not name.startswith(f"{__package__}.") and name != __package__
    ]
    return bool(foreign)


def _on_enable() -> None:
    global _ENABLED_STACK
    if _BLOCKED:
        _log("enable blocked: unsupported game (TPS only)")
        return
    if _duplicate_install():
        _log(
            "enable blocked: another Modern Movement package is already loaded. "
            "Remove the older sdkmod/folder and restart before enabling this co-op build."
        )
        return
    if not _FEATURES:
        _log("enable blocked: no features loaded")
        return
    _ENABLED_STACK = []
    try:
        from . import network as _network

        _core.on_enable()
        _ENABLED_STACK.append("core")
        _hudfx.reset()
        _hudfx.install_textures()
        _ENABLED_STACK.append("hudfx")
        for _name, _feature, _desc in _FEATURES:
            _feature.on_enable()
            _ENABLED_STACK.append(_name)
        try:
            _network.set_rules(_rules.collect_live_rules())
            _ENABLED_STACK.append("network_rules")
        except Exception as net_exc:  # noqa: BLE001
            _log(f"network rules skipped ({net_exc!r}) — local movement still active")
        net_note = "with Networking" if _NETWORKING_OK else "local-only (Networking optional)"
        _log(f"enabled (own-pawn movement for every player who has the mod; {net_note})")
    except Exception as exc:  # noqa: BLE001
        _log(f"enable failed ({exc!r}); rolling back")
        _rollback_enable()


def _rollback_enable() -> None:
    from . import network as _network

    for name in reversed(_ENABLED_STACK):
        try:
            if name == "core":
                _core.on_disable()
            elif name == "hudfx":
                _hudfx.reset()
            elif name == "network_rules":
                _network.disable()
            else:
                for label, feature, _desc in _FEATURES:
                    if label == name:
                        feature.on_disable()
                        break
        except Exception as exc:  # noqa: BLE001
            _log(f"rollback {name} failed: {exc!r}")
    _ENABLED_STACK.clear()


def _on_disable() -> None:
    if not _ENABLED_STACK and _BLOCKED:
        return
    for _name, _feature, _desc in reversed(_FEATURES):
        try:
            _feature.on_disable()
        except Exception as e:
            _log(f"{_name}: on_disable failed: {e!r}")
    try:
        _hudfx.reset()
    except Exception as e:  # noqa: BLE001
        _log(f"hudfx reset failed: {e!r}")
    _core.on_disable()
    _ENABLED_STACK.clear()
    _log("disabled - game state restored")


def _group(name: str, children: list, description: str = ""):
    """A feature's own page in the menu (clickable entry), or the bare children if that isn't available."""
    if GroupedOption is None:
        return children
    last_error = None
    for build in (
        lambda: GroupedOption(name, children, description=description),
        lambda: GroupedOption(name, children),
    ):
        try:
            return [build()]
        except Exception as e:
            last_error = e
    _log(f"options group '{name}' unavailable ({last_error!r}) - showing its options directly")
    return children


# Misc is the last section in the menu (just above the key bindings).
_OPTIONS = []
for _name, _feature, _desc in sorted(_FEATURES, key=lambda f: f[0] == "Misc"):
    if _feature.OPTIONS:
        _OPTIONS.extend(_group(_name, list(_feature.OPTIONS), _desc))

# The shared jump key comes from core; each feature adds only its own keys.
_KEYBINDS = list(_core.KEYBINDS)
for _name, _feature, _desc in _FEATURES:
    _KEYBINDS.extend(_feature.KEYBINDS)

# HUD hooks are owned centrally so Dash load failure cannot drop PostRender.
_HOOKS = list(_core.HOOKS) + list(getattr(_hudfx, "HOOKS", []))
for _name, _feature, _desc in _FEATURES:
    for _hook in _feature.HOOKS:
        if _hook not in _HOOKS:
            _HOOKS.append(_hook)


_build_kwargs = dict(
    name="Modern Movement",
    author=__author__,
    version=__version__,
    description=(
        "Double Jump, Dash, Mantle, Slide, Holster, and Sprint Surge. "
        "Each module can be enabled or disabled. "
        "Make sure to check key bindings at the bottom!"
    ),
    options=_OPTIONS,
    hooks=_HOOKS,
    keybinds=_KEYBINDS,
    on_enable=_on_enable,
    on_disable=_on_disable,
)

try:
    from mods_base import Game as _Game

    _tps = getattr(_Game, "TPS", None)
    if _tps is not None:
        _build_kwargs["supported_games"] = _tps
except Exception:  # noqa: BLE001
    pass

try:
    from mods_base import CoopSupport as _CoopSupport

    # ClientSide: each peer who installed the mod runs it locally. Missing peers stay vanilla.
    _coop = getattr(_CoopSupport, "ClientSide", None) or getattr(_CoopSupport, "Optional", None)
    if _coop is not None:
        _build_kwargs["coop_support"] = _coop
except Exception:  # noqa: BLE001
    pass

_mod = build_mod(**_build_kwargs)

try:
    from . import network as _network

    _mod = _network.attach_mod(_mod)
    _NETWORKING_OK = bool(_network.networking_available())
    if _NETWORKING_OK:
        _log("Networking 1.2 endpoints attached")
    else:
        _log("Networking not present — each player still gets local movement/HUD")
except Exception as _attach_exc:  # noqa: BLE001
    # Never clear features or block enable: own-pawn movement must work without the wire.
    _log(f"network attach skipped ({_attach_exc!r}) — local movement still available")
