# Level 6 — Lost Level — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 6: Lost Level  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-06.01-lost-level-dm.png`  
**Player presentation map:** `assets/maps/levels/map-06.01-lost-level-player.jpg`  
**Keyed source areas:** 1–48  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

A sealed Melairkyn religious complex has been rediscovered and is being stripped for loot. The level pits historical/sacred value against raiders who see abandoned wealth.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Will the Lost Level remain a protected remnant of Melairkyn history, be stripped by Clan Ironeye, or become a demon-infested ruin after its deepest safeguards are broken?

### Initial Equilibrium

Clan Ironeye has newly entered an isolated Dumathoin temple complex and is already looting it, but traps and monsters have reduced their confidence. Skella wants profit and beauty more than historical preservation and is willing to bargain. The true tomb of King Melair and dangerous bound demons remain deeper in the complex.

### Active Motion

- Skella's surviving duergar continue methodically looting rooms and looking for access beyond the temple defenses.
- The allied cloakers treat the opened level as a prospective hunting ground.
- If undisturbed long enough, the raiders can eventually locate and plunder King Melair's tomb before leaving for the Underdark.
- Bound guardians and demons remain inert until their source conditions are disturbed.

### Player Variable

The player can bargain with Skella, reclaim Azrok's dagger, protect or assist the looting, open sacred barriers, release demons, or reach King Melair's true tomb first.

### Pressure Points

- Area 15 — Temple of Dumathoin: Skella, the main duergar force, Azrok's dagger, and the truce opportunity.
- Area 16 — Heart of the Mountain: sacred center unlocked by a dwarf king's hand.
- Area 29 — King Melair's Lost Tomb: heritage payoff and demon-release catastrophe branch.
- Melairkyn relic rooms — evidence that the duergar are stripping a historical site rather than merely scavenging generic treasure.

### Reaction Rules

- IF the player accepts Skella's bargain and does not cross her, THEN her lawful nature makes the agreement durable until circumstances genuinely change.
- IF the player takes or negotiates for the dagger of blindsight, THEN update the Level 3 Azrok/Lurkana thread immediately; possession of the dagger is not just loot state.
- IF the duergar remain alive and unopposed across meaningful elapsed time, THEN advance their looting toward King Melair's tomb and eventual departure as the aftermath permits.
- IF the glabrezu or other tomb demons are released, THEN they become the dominant active threat and hunt treasure seekers rather than remaining a room encounter.
- IF the player preserves significant relics or denies them to Skella, THEN Skella's attitude and plan should change according to the bargain and her actual losses.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- PLUNDER IN PROGRESS — Ironeye is damaged but actively looting.
- RACE FOR THE CORE — player and duergar both have credible access to sacred interior/tomb material.
- HERITAGE SECURED / STOLEN — one side has effectively controlled the major relic outcome.
- DEMON BREACH — released fiends supersede treasure politics as the level's primary danger.

### Outcome States

- Clan Ironeye escapes with major Melairkyn treasures.
- The player preserves/reclaims the tomb and its key relics.
- Skella survives under a negotiated settlement and leaves with limited plunder.
- Released demons dominate the Lost Level and make future expeditions substantially more dangerous.

### Player-Facing Evidence

- Ransacked chambers and missing display pieces show an active looting trail.
- Skella's forces are visibly depleted and cautious after losses to the temple's defenses.
- Dwarven art and inscriptions repeatedly frame rooms as sacred/historical rather than disposable treasure containers.
- The hidden tomb and sealed barriers communicate that something important was meant to remain secret.

## Actor Network

- Skella/Ironeye -> Melairkyn complex: extraction target, not heritage.
- Skella -> player: potential contractual partner until betrayed or obstructed.
- Cloakers -> level inhabitants: future prey; temporary allies of the raiders.
- Bound demons -> everyone: catastrophic threat if released.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Skella Ironeye

**Motive:** Plunder the level profitably while keeping her depleted band alive; she also genuinely values artistry and beauty.  
**Plan if unopposed:** Negotiate when useful, continue looting when safe, and honor bargains unless betrayed.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Mornhyld Crystalmantle

**Motive:** Protect or embody the surviving Melairkyn legacy associated with the level's sacred history.  
**Plan if unopposed:** Respond according to the source scene and the treatment of the dwarven complex.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Temple of Dumathoin and sacred spaces — the level's historical identity.
- King Melair's Lost Tomb — central Melairkyn legacy.
- Clan Ironeye's route and loot trail — active intrusion.
- Cross-level dagger connection from Azrok's Hold.

## Level State That Must Persist

- Clan Ironeye strength and loot
- Sacred sites disturbed or preserved
- Azrok's dagger recovered or moved
- Melairkyn discoveries
- routes opened by umber hulks

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Skella carries Azrok's dagger from Level 3.
- King Melair's crystal crown activates gates on later/other levels.
- The level's historical material deepens the Melairkyn substrate beneath Halaster's dungeon.

## Halaster Through-Line

Mostly absent. The level reveals what existed before Halaster and what his dungeon has swallowed.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Record whether raiders escape with relics, whether the tomb is disturbed, and how the recovered history changes later understanding of Undermountain.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.06`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/06-001.lost-level.png`

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