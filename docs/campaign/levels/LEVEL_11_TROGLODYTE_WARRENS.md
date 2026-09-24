# Level 11 — Troglodyte Warrens — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 11: Troglodyte Warrens  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-11.01-troglodyte-warrens-dm.jpg`  
**Player presentation map:** `assets/maps/levels/map-11.01-troglodyte-warrens-player.jpg`  
**Keyed source areas:** 1–17  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

The drow conflict spills into a population that both houses want to enslave. Free troglodytes, captured troglodytes, mutated trolls, and a dominant behir create a battlefield where unlikely alliances are rational.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Can any local population survive the drow proxy war and apex predators, and which side gains the corridor between the Auvryndar and Freth strongholds?

### Initial Equilibrium

Auvryndar and Freth forces are fighting through the warrens while capturing troglodytes as slaves. A free troglodyte clan still holds territory. Mutated trolls prey on everyone except the behir, and the magically enhanced behir acts as the uncontested apex predator.

### Active Motion

- Both drow houses continue sending forces while their strongholds on Levels 10 and 12 remain capable.
- Captured troglodytes seek escape; the free clan defends itself and may trade secrets for decisive help.
- Trolls continue predation while avoiding the behir.
- The behir roams/hunts and keeps troll and troglodyte populations in check.

### Player Variable

The player can free prisoners, ally with the free clan, cripple one or both drow houses locally, kill/avoid the behir, neutralize trolls, or alter the broader war by actions on Levels 10 and 12.

### Pressure Points

- Area 2 — captured troglodytes: immediate alliance/slavery pressure point.
- Area 7 — strongest free troglodyte clan: local sovereignty and information exchange.
- Areas 8–14 — shifting Auvryndar/Freth front line and contested caves.
- Area 11 — mutation source for trolls.
- Area 17 — behir lair/payoff after repeated environmental foreshadowing.

### Reaction Rules

- IF the player frees troglodytes and harms their captors, THEN survivors can treat the player as useful allies until later dominance changes their incentives.
- IF a drow stronghold remains intact on its home level, THEN that house can continue replacing local forces; do not treat one cleared outpost as the end of the war.
- IF the behir is killed, THEN remove its population-control pressure and allow drow/troglodyte/troll actors to respond according to surviving strength.
- IF the behir, trolls, and both drow houses are crippled, THEN troglodytes grow in strength and numbers; once dominant, they eventually become hostile to outsiders regardless of old truces.
- IF drow kill the behir, THEN they remove its treasure to their stronghold as described by the aftermath.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- MULTI-SIDED BATTLEFIELD — drow war plus free/captive troglodytes and predators.
- ALLIANCE WINDOW — player cooperation has temporarily empowered a local side.
- PREDATOR/F ACTION SHIFT — behir, trolls, or one drow house has been removed from the balance.
- NEW DOMINANT POPULATION — surviving drow or troglodytes have enough space to impose a new order.

### Outcome States

- Auvryndar or Freth continues controlling part of the corridor.
- Troglodytes regain the warrens and later become broadly hostile from strength.
- Predators remain the main limiting force if political factions are broken but monsters survive.
- The level remains a replenished drow battlefield while either house's home stronghold survives.

### Player-Facing Evidence

- Prisoners and slave-taking reveal that the drow war is being fought through the local population.
- Different drow insignia and contested positions communicate a front line.
- Blue scales, ceiling claw marks, lightning/thunder, and missing creatures foreshadow the behir before the lair.
- Mutated troll bodies/effects point back to the rune-covered cavern.

## Actor Network

- Auvryndar <-> Freth: regional drow war.
- Both drow houses -> troglodytes: labor/slave resource and territorial obstacle.
- Free troglodytes -> both houses: enemies; adventurers can become temporary liberators.
- Behir -> everyone: apex predator with no faction loyalty.
- Trolls -> troglodytes/drow/adventurers: opportunistic predation, checked by behir.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Free troglodyte leaders

**Motive:** Keep the last free clan alive and resist enslavement by either drow house.  
**Plan if unopposed:** Trade information or treasure for meaningful help against oppressors.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### House Auvryndar commanders

**Motive:** Hold and expand their side of the warrens while denying House Freth.  
**Plan if unopposed:** Capture troglodytes and use them as labor/forces.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### House Freth commanders

**Motive:** Break Auvryndar control and secure the warrens for their own expansion.  
**Plan if unopposed:** Contest chokepoints and enslave local populations.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Enhanced behir

**Motive:** Maintain dominance as an apex predator and terrorize all factions.  
**Plan if unopposed:** Attack vulnerable targets and preserve its lair.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Captured troglodytes — immediate moral/political leverage.
- Free clan territory — possible alliance center.
- Auvryndar/Freth front line — moving conflict, not static rooms.
- Behir lair — independent threat neither drow side controls.

## Level State That Must Persist

- Auvryndar vs Freth balance
- Free/captured troglodyte population
- Troll pressure
- Behir status
- alliances made by player

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Auvryndar viability depends on Level 10; Freth viability depends on Level 12.
- The gith/illithid campaign does not yet own this level; preserve the drow/troglodyte story as primary.

## Halaster Through-Line

No required contact. The level demonstrates downstream consequences of conflicts begun on other floors.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Survivors reposition according to faction outcomes. Any liberated population needs a plausible next plan rather than disappearing from state.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.11`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/11-001.troglodyte-warrens.png`

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