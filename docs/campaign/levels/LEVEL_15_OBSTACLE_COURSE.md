# Level 15 — Obstacle Course — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 15: Obstacle Course  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-15.01-obstacle-course-dm.png`  
**Player presentation map:** `assets/maps/levels/map-15.01-obstacle-course-player.jpg`  
**Keyed source areas:** 1–40  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

A deliberately maintained deathtrap jointly tolerated by Halaster and Netherskull. The level openly treats intruders as contestants while githzerai hide inside it for a mission that points toward Seadeeps.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Can the player survive a dungeon deliberately operated as a lethal spectacle while discovering the githzerai mission hidden inside it?

### Initial Equilibrium

Netherskull rules the level under an old agreement that lets Halaster maintain and modify the obstacle course. The trap network actively splits and harms intruders, accompanied by Halaster-themed commentary. Yrlakka's four githzerai hide from both Netherskull and Halaster while waiting on the githyanki–mind flayer war and searching for missing Ezria.

### Active Motion

- Netherskull continues hunting/terrorizing intruders from a position of lair dominance.
- The course's traps continue functioning and Halaster maintains them over time; triggered teleportation can split the party.
- Yrlakka's band remains concealed, seeks Ezria, and waits for a chance to assist against the mind flayers without exposing itself prematurely.
- Lava children/mephits hold their warm territory and can be manipulated into violence by the mephits.

### Player Variable

The player can disable/bypass traps, find and cooperate with the githzerai, recover information about Ezria, kill Netherskull, or interact with the play-by-play in ways that become Halaster callback material.

### Pressure Points

- Trap network / teleport traps — systemic encounter pressure and party-splitting behavior.
- Area 24 — githzerai retreat: Yrlakka's mission, Ezria, and the next campaign conflict.
- Area 39 — Netherskull's Sanctum: level-ruler payoff.
- Halaster's Play-by-Play — source-supported campaign recognition beat; keep live/automated knowledge consistent with the Halaster layer.

### Reaction Rules

- IF teleport traps split characters, THEN run parallel scenes fairly; do not use separation to make off-screen player choices.
- IF the player earns Yrlakka's trust, THEN his next priorities remain finding Ezria and influencing the gith conflict toward reunification, not generic dungeon companionship.
- IF Netherskull dies, THEN its regional effects end immediately; Halaster does not instantly replace it but eventually seeds beholders to select a successor death tyrant.
- IF the githzerai reunite with Ezria and the mind-flayer colony is resolved, THEN they leave rather than treating the Obstacle Course as a permanent base.
- IF player behavior during commentary is notable and Halaster actually knows it under the through-line rules, THEN add concise callback evidence rather than turning every stunt into relationship escalation.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- ACTIVE COURSE — Netherskull + traps + commentary functioning.
- HIDDEN ALLIANCE — githzerai thread discovered while ruler remains active.
- RULER REMOVED — Netherskull dead; traps persist but regional tyranny ends.
- SUCCESSOR CYCLE — long-term Halaster replacement process begins if enough time passes.

### Outcome States

- Netherskull remains lord and the course continues unchanged.
- Netherskull dies; Halaster later engineers a beholder succession contest.
- Githzerai leave after their cross-level mission succeeds or fails decisively.
- The course remains a Halaster-maintained hazard even when its current ruler is gone.

### Player-Facing Evidence

- Taunting commentary and reset/maintained traps reveal deliberate operation.
- Evidence of old dwarven engineering overlaid with newer Halaster modifications.
- The githzerai's concealment and caution contrast with the level's theatrical surface.
- Recurring signs of Netherskull's lair influence build toward its sanctum.

## Actor Network

- Halaster <-> Netherskull: negotiated coexistence; Halaster maintains the attraction, Netherskull rules it.
- Netherskull -> all intruders: prey/targets.
- Yrlakka -> Ezria: rescue concern.
- Yrlakka -> githyanki/mind flayers: wants cooperation against illithids to support eventual gith reunification.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Netherskull

**Motive:** Remain undisputed lord of the level and destroy intruders while allowing Halaster to keep modifying the traps.  
**Plan if unopposed:** Use lair knowledge and the obstacle course to kill or dominate challengers.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Githzerai zerths

**Motive:** Remain hidden long enough to reunite with their missing comrade and ensure destruction of the mind-flayer colony on Level 17.  
**Plan if unopposed:** Avoid Netherskull/Halaster attention, gather information, and move when mission conditions allow.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Yrlakka

**Motive:** Find Ezria and use cooperation against mind flayers to demonstrate that githyanki and githzerai can reunify.  
**Plan if unopposed:** Keep the band hidden, wait on the Seadeeps war, and move when there is a credible opportunity to recover Ezria or aid against illithids.  
**Runtime:** Preserve his Sha'sal Khou agenda; he is not simply an anti-mind-flayer quest giver.

### Ezria

**Motive:** Prove capability and gather intelligence on githyanki defenses; survive capture.  
**Plan if unopposed:** His current plan depends on actual captive/location state on Level 16.  
**Runtime:** Use one persistent NPC record across Levels 15–16.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Halaster's Play-by-Play — autonomous/remote theatrical pressure; preserve source distinction about whether live.
- Trap sequence — the level itself is an antagonist system.
- Netherskull's Sanctum/Chasm — ruler payoff.
- Githzerai refuge — launches the gith/illithid campaign thread.

## Level State That Must Persist

- Netherskull status
- announcer active/silenced
- githzerai survivors/mission
- major traps altered
- Halaster recognition of player's performance

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Ezria is tied to Level 16.
- Yrlakka's mission points directly to the Level 16–17 war.
- This level is a major Halaster recognition/contact milestone in the through-line.

## Halaster Through-Line

Recognized-subject milestone. The dungeon can openly acknowledge performance here, but Halaster still should not become a constant physical host.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

If Netherskull falls, the obstacle course's political center changes even if many traps remain. Githzerai mission state carries into Levels 16–17.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.15`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/15-001.obstacle-course.png`
- Level art: `/Dnd solo/Assets/Art/Levels/15-002.netherskulls-sanctum.png`

Maps remain bound through `docs/architecture/runtime/MAP_INDEX.md`; this section governs non-map visual lookup. Level art is player-facing only after source/state make the depicted subject legitimately perceivable and the image does not leak unrevealed information. Creature/NPC art is resolved separately by entity identity.

## Level Runtime Procedure

Before each meaningful scene on this level:

1. Load the current `escalation_state`, surviving actor states, and cross-level overrides.
2. Retrieve the keyed room source before presenting room-specific facts.
3. Instantiate every named or individually characterized NPC who can participate.
4. Check this file's pressure points and reaction rules against the player's current action.
5. Choose NPC actions from motive + knowledge + means + relationships, including what they would do without the player.
6. Present only player-perceivable evidence of the larger level story.
7. After the action resolves, update actor plans and the smallest necessary level-story state.

On a rest, long travel interval, departure, or return, run a background tick using the source-supported Active Motion and published aftermath. Never invent elapsed-time outcomes without the means and time required.

## Runtime Check

Before advancing play, the DM should be able to answer:

- What is the current story-engine state and what event put it there?
- Which NPCs are acting even if the player does nothing, and what is each one doing next?
- What does each active NPC want, know, fear losing, and have the means to do?
- Which reaction rules fired because of the player's last meaningful action?
- If time advances now, what source-supported background motion can actually occur before the player returns?