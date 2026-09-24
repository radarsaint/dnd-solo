# Level 20 — Runestone Caverns — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 20: Runestone Caverns  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-20.01-runestone-caverns-dm.png`  
**Player presentation map:** `assets/maps/levels/map-20.01-runestone-caverns-player.jpg`  
**Keyed source areas:** 1–23  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

The campaign's clearest strategic choice involving Halaster before the finale. Ezzat wants to destroy and replace him; Halaster wants Ezzat removed; the Runestone and Stonecloaks make their rivalry physical.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Does the player become Halaster's instrument against Ezzat, Ezzat's ally against Halaster, or a third party who damages both systems—and what does that choice do to the Runestone?

### Initial Equilibrium

Ezzat occupies the stalagmite tower behind wards that keep Halaster's Stonecloaks out. The Stonecloaks worship Halaster and the Runestone but cannot solve the lich problem. Ezzat wants to destroy Halaster and seize Undermountain, while his obsession increasingly mirrors Halaster's. A Shadowdusk expedition also seeks Runestone fragments.

### Active Motion

- Ezzat protects his tower/phylactery and looks for useful agents against Halaster.
- Stonecloaks guard/worship the Runestone and resent Ezzat but remain blocked by his wards.
- Shadowdusk agents collect fragments and seek leverage for their family.
- Halaster has a direct strategic interest in Ezzat's removal and can use the Runestone as a communication vector under the through-line rules.

### Player Variable

The player can ally with Ezzat, destroy him, locate/transfer his phylactery, damage the Runestone, kill/steal Haungharassk, deal with the Stonecloaks, or bring Shadowdusk interests into the conflict.

### Pressure Points

- Area 10 — Mad Mage's Puzzle: automated Halaster authorship/player-model input.
- Area 14 — Runestone: required strategic Halaster remote-contact opportunity in the through-line.
- Areas 15–23 — Ezzat's tower: rival wizard ideology and phylactery protection.
- Area 23 — Ezzat's phylactery: Level 19 genie-contest object.
- Shadowdusk expedition encounter — links the level to the family on Level 22.
- Haungharassk — Halaster possessiveness trigger disproportionate to ordinary tactical value.

### Reaction Rules

- IF the player destroys Ezzat and secures his phylactery, THEN record Halaster favor and make the phylactery available for the mutually exclusive Level 19 genie reward.
- IF the player allies with Ezzat, THEN record Halaster enmity and preserve Ezzat's actual goal of replacing Halaster; alliance does not make him a benign resistance leader.
- IF the Runestone is damaged/destroyed, THEN update Stonecloak function/worship consequences and Halaster grievance according to the through-line layer; do not treat it as ordinary scenery damage.
- IF Haungharassk is killed/stolen, THEN create the source-supported personal Halaster grievance/interest state.
- IF Shadowdusk agents survive with fragments, THEN move that resource/knowledge into Level 22 state.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- STALEMATE — Ezzat protected; Stonecloaks blocked; Halaster wants a proxy.
- COURTED — Halaster and/or Ezzat has directly tried to define the player's role.
- CHOICE MADE — player materially supports or harms one side.
- POWER VACUUM / ALLIANCE — Ezzat dead, allied, or Runestone system transformed.

### Outcome States

- Ezzat destroyed and Halaster pleased.
- Ezzat survives as player ally/enemy and continues seeking Undermountain control.
- Runestone/Stonecloak system is damaged enough to create a new Halaster response.
- Phylactery leaves the level for one of the Level 19 genies.
- Shadowdusks leave with or without Runestone fragments.

### Player-Facing Evidence

- Stonecloaks' worship and inability to enter the tower make the stalemate visible.
- Ezzat's defenses and rhetoric reveal he is becoming psychologically similar to the enemy he hates.
- Shadowdusk fragment-hunting shows other factions already recognize the Runestone's value.
- Halaster's Runestone communication should reference actual prior history, making the campaign relationship concrete.

## Actor Network

- Ezzat -> Halaster: rival seeking total replacement/control.
- Halaster -> Ezzat: wants proxy destruction because direct construct assault failed.
- Stonecloaks -> Halaster/Runestone: worshipful defenders.
- Shadowdusks -> Runestone: strategic resource collectors.
- Player -> both wizards: potential proxy, ally, enemy, or destabilizer.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Ezzat

**Motive:** Destroy Halaster and usurp control of Undermountain, even as his obsession makes him increasingly resemble his enemy.  
**Plan if unopposed:** Recruit capable adventurers, protect his phylactery, and undermine Halaster.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Stonecloaks

**Motive:** Serve and worship Halaster and protect the Runestone while resenting Ezzat's protected tower.  
**Plan if unopposed:** Obey their Halaster-centered purpose but remain blocked by Ezzat's wards.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Haungharassk

**Motive:** Survive as Halaster's prized giant snail; its importance comes from Halaster's attachment rather than political agency.  
**Plan if unopposed:** Follow its creature behavior; its death or theft is a major Halaster grievance trigger.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Akarrth Shadowdusk

**Motive:** Acquire Runestone fragments for Shadowdusk interests while surviving his own unstable alliance network.  
**Plan if unopposed:** Gather fragments and exploit temporary alliances, including with adventurers, until paranoia/instability breaks them.  
**Runtime:** If he leaves with fragments, move that resource into Level 22 campaign state.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Area 10: Mad Mage's Puzzle — automated evidence/player-model input.
- Area 14: Runestone — required remote Halaster strategic contact.
- Ezzat's tower — rival worldview and alliance choice.
- Ezzat's phylactery — connects back to Level 19.
- Haungharassk — unusual object of Halaster's possessiveness.

## Level State That Must Persist

- Ezzat alliance/hostility/death
- phylactery status
- Runestone intact/damaged/destroyed
- Stonecloak status
- Haungharassk status
- Halaster favor/enmity

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Ezzat's phylactery pays off the genie contest on Level 19.
- Shadowdusk expedition links forward to Level 22.
- Halaster relationship state here is one of the major late-campaign through-line pivots.

## Halaster Through-Line

Investment milestone. The Runestone supports a direct remote conversation about Ezzat and the player's accumulated history. This decision should materially shape Halaster's later regard.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Removing Ezzat pleases Halaster and opens the tower to a new apprentice. Destroying the Runestone provokes a major response. Haungharassk's fate can create a personal grievance.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.20`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: none indexed yet

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