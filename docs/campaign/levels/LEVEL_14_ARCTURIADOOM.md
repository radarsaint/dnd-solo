# Level 14 — Arcturiadoom — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 14: Arcturiadoom  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-14.01-arcturiadoom-dm.png`  
**Player presentation map:** `assets/maps/levels/map-14.01-arcturiadoom-player.jpg`  
**Keyed source areas:** 1–41  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

Arcturia's private domain has become a giant/hobgoblin industrial project. Fire giants are building a construct for Halaster in exchange for a lost giant rune, while Arcturia's experiments and phylactery make the level part of the endgame.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Does the fire-giant bargain with Halaster produce Mecha-Halaster, does the player break the industrial project, and what does the player do with Arcturia's phylactery before eventually facing her?

### Initial Equilibrium

Emberosa's fire giants and Doomcrown's Death's Head Phalanx control most of the level while building Mecha-Halaster in exchange for a giant rune Halaster possesses. House Freth mages infiltrate for powerful magic. Arcturia is usually absent but the level remains her retreat, laboratory, trap network, and phylactery site.

### Active Motion

- Emberosa's force continues construction and resource gathering.
- Doomcrown's hobgoblins patrol, protect the project, and send raiders to Level 13 for metal.
- Freth infiltrators avoid unnecessary battle and try to turn outsiders against the giants/hobgoblins.
- Arcturia periodically returns over longer time scales to study, reset/alter polymorph traps, and respond to major damage to her domain.

### Player Variable

The player can stop or aid the giant project, kill Doomcrown, exploit Freth infiltrators, discover/destroy Arcturia's phylactery, release experiments, or leave the industrial system intact.

### Pressure Points

- Area 15 — Mecha-Halaster assembly: physical expression of Emberosa/Halaster bargain.
- Areas 32–36 — Death's Head command/barracks/training: Doomcrown's military center.
- Arcturia's laboratories/experiments and polymorph traps — her continuing authorship despite absence.
- Arcturia's phylactery location — irreversible Level 23 consequence if destroyed.
- Freth infiltration scenes — opportunity to connect this level to the drow war without making it the primary story.

### Reaction Rules

- IF Emberosa/giants are defeated, THEN Mecha-Halaster construction stalls but is not permanently cancelled; Halaster can eventually find replacement metalsmiths.
- IF Doomcrown's command structure survives, THEN raiding pressure on Level 13 can resume; IF he is removed, update that supply line there.
- IF Arcturia's phylactery is destroyed, THEN set a permanent campaign flag that causes her Level 23 hostility; never reset it when this level reloads.
- IF Arcturia's defenses are badly damaged and she later returns, THEN she can seek illithid security from Level 17 or bribe surviving dragons to cover routes as the aftermath allows.
- IF Freth infiltrators survive with useful intelligence, THEN move that information into House Freth campaign state rather than forgetting them at departure.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- INDUSTRIAL OCCUPATION — giants/hobgoblins control production under Arcturia's absent ownership.
- SABOTAGE / INFILTRATION — player or Freth is materially disrupting the project/defenses.
- PROJECT STALLED / SECURED — giant production has stopped or become protected enough to continue.
- ARCTURIA RESPONSE — phylactery/defense changes have become personal to the absent lich and feed Level 23.

### Outcome States

- Mecha-Halaster project continues toward completion.
- Project stalls until Halaster recruits replacement smiths.
- Arcturia's domain becomes more heavily defended after a damaging incursion.
- Arcturia enters Level 23 with or without phylactery protection based on player action.

### Player-Facing Evidence

- Regular hobgoblin patrols and scrap flow show an operating factory rather than static guard rooms.
- The enormous incomplete construct makes Halaster's bargain visible without exposition.
- Polymorph traps and laboratories show Arcturia's specific transmutation obsession.
- Freth agents behave as spies/opportunists, contrasting with the openly militarized occupiers.

## Actor Network

- Emberosa -> Halaster: contractual labor for the promised giant rune.
- Doomcrown -> Emberosa/project: ideological/military support and scrap acquisition.
- Freth -> occupiers: infiltrators looking for magic and leverage.
- Arcturia -> level: absent owner whose immortality and experiments remain embedded here.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Emberosa

**Motive:** Obtain the lost giant rune and elevate fire giants in the ordning.  
**Plan if unopposed:** Complete Halaster's requested construct using giant forging skill.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Doomcrown

**Motive:** Lead the Death's Head Phalanx effectively and establish a legacy separate from his father Azrok.  
**Plan if unopposed:** Support the giant project and maintain hobgoblin discipline.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Arcturia

**Motive:** Preserve her immortality, work, and status among Halaster's surviving apprentices.  
**Plan if unopposed:** Normally remain tied to Level 23, but her phylactery and experiments make player actions here personal later.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Vanar Freth

**Motive:** Advance House Freth interests through infiltration without needlessly fighting adventurers.  
**Plan if unopposed:** Exploit the industrial conflict and survive.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Construct assembly area — concrete bargain between Halaster and giants.
- Arcturia's laboratories/experiments — reveal her methods.
- Arcturia's phylactery — major endgame consequence.
- Doomcrown/Death's Head areas — cross-level Azrok family connection.

## Level State That Must Persist

- construct progress/destruction
- Emberosa/rune bargain
- Doomcrown survival
- Arcturia phylactery status
- drow infiltration

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Doomcrown is Azrok's estranged son from Level 3.
- Hobgoblin salvage pressure reaches Level 13.
- Arcturia can seek support from mind flayers on Level 17.
- Arcturia's phylactery directly controls her Level 23 state.

## Halaster Through-Line

Strong indirect through-line. Destruction/preservation of the phylactery and the giant project become callback-grade events.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Carry phylactery status directly into Level 23. Carry Doomcrown outcome back into the Azrok family story if relevant.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.14`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/14-001.arcturiadoom.png`

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