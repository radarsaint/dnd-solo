# Level 10 — Muiral’s Gauntlet — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 10: Muiral’s Gauntlet  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-10.01-muirals-gauntlet-dm.png`  
**Player presentation map:** `assets/maps/levels/map-10.01-muirals-gauntlet-player.jpg`  
**Keyed source areas:** 1–30  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

One of Halaster's transformed apprentices is trying to hold a decaying hunting domain while House Auvryndar returns to reclaim it as a permanent Lolth stronghold.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Does Muiral keep his decaying hunting domain, does Vlonwelv turn it into a permanent Auvryndar fortress, or does the player cripple the house badly enough to shift the wider drow war toward Freth?

### Initial Equilibrium

Muiral controls portions of the old drow level through personal predation but cannot defeat the returning House Auvryndar force alone. Vlonwelv controls the southern stronghold, is rebuilding Lolth's presence, uses Gorzil's troglodytes, and wants outsiders to kill Muiral for her. House Auvryndar also uses this level as a staging ground against House Freth.

### Active Motion

- Muiral hunts intruders and drow throughout his territory, relying on familiarity and terror rather than diplomacy.
- Vlonwelv expands fortifications and treats capable adventurers cordially only as long as they can be turned against Muiral or other enemies.
- Gorzil's troglodytes support Auvryndar while pursuing their own survival and predation.
- House Auvryndar continues using the level as a base for raids toward Freth-held territory.

### Player Variable

The player can take Vlonwelv's bargain, side with Muiral only indirectly by attacking drow, kill either leader, expose weakness to House Freth, or recover cross-level quest material such as Falkir's Fist evidence.

### Pressure Points

- Muiral's roaming encounter zones — his location is variable and he is an active hunter rather than a stationary boss.
- Area 4 — Muiral's Laboratory: history and transformation evidence.
- Areas 25–28 — Auvryndar halls/temple/apartments: organized occupation and Vlonwelv's political center.
- Area 8 — Fate of Falkir's Fist: surface quest continuity.
- Troglodyte-controlled areas — show the alliance structure beneath Auvryndar rule.

### Reaction Rules

- IF the player accepts Vlonwelv's hospitality, THEN she remains cordial only while they appear useful/compliant; her demand to kill Muiral remains the strategic purpose of the relationship.
- IF Muiral survives and Auvryndar is routed, THEN he animates dead drow/troglodytes and repopulates the level with undead defenders.
- IF Vlonwelv survives, THEN Auvryndar continues gaining footholds elsewhere in Undermountain.
- IF Vlonwelv dies, THEN allied houses withdraw support from Auvryndar and House Freth gains strategic advantage; after securing Level 11, Freth can push into this level.
- IF prior player cooperation with Auvryndar or Freth is known, THEN use that history in negotiations rather than resetting drow attitudes at the room door.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- TWO-SIDED OCCUPATION — Muiral predator territory versus Vlonwelv fortress.
- PROXY WAR — player is being used against one side or has openly chosen enemies.
- LOCAL VICTORY — Muiral or Auvryndar has been decisively weakened.
- REGIONAL SHIFT — the result changes House Auvryndar/Freth strength on Levels 11–12.

### Outcome States

- Muiral reclaims the level with undead servants.
- Vlonwelv consolidates Auvryndar's fortress and broader expansion.
- Vlonwelv's death throws Auvryndar alliances into disorder and opens a Freth advance.
- Both sides are crippled, leaving territory contested by later drow forces and surviving local creatures.

### Player-Facing Evidence

- Physical contrast between Muiral's neglected rooms and actively restored drow territory.
- Vlonwelv's hospitality paired with coercive demands.
- Signs of a roaming scorpion-bodied hunter rather than a boss waiting in one chamber.
- Troglodytes operating as subordinates/allies reveal the drow's occupation model.

## Actor Network

- Muiral -> Auvryndar: existential territorial enemy.
- Vlonwelv -> Muiral: problem best outsourced to capable adventurers.
- Vlonwelv -> House Freth: wider strategic rival.
- Gorzil -> Vlonwelv: subordinate ally whose gang benefits from the occupation.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Muiral the Misshapen

**Motive:** Keep control of his remaining domain and repel the returning drow.  
**Plan if unopposed:** Hunt intruders and drow aggressively; use familiarity with the level.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Vlonwelv Auvryndar

**Motive:** Establish durable House Auvryndar control and rebuild a Lolth-centered stronghold.  
**Plan if unopposed:** Use drow forces and troglodyte allies to eliminate Muiral and secure territory.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Gorzil

**Motive:** Advance his gang's position by serving Vlonwelv and preying on enemies.  
**Plan if unopposed:** Follow the alliance while preserving his own authority and survival.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Muiral's roaming/hunting zones — persistent predator with motive.
- Auvryndar halls and Spider Queen's Temple — organized reclamation.
- Muiral's Laboratory — evidence of his transformation and history.

## Level State That Must Persist

- Muiral alive/location
- Auvryndar territorial control
- Vlonwelv status
- Gorzil/troglodyte alliance
- Halaster reaction to Muiral outcome

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- House Auvryndar state from Levels 3–4 should affect its confidence/resources here.
- House Freth pressure continues through Levels 11–12.
- Falkir's Fist links back to a surface quest.
- Muiral is a living Halaster-apprentice consequence relevant to the campaign through-line.

## Halaster Through-Line

Apprentice consequence milestone. Muiral's fate is eligible for deliberate Halaster observation/callback; do not force a physical appearance.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Whichever side survives consolidates. Muiral's death or survival must remain in Halaster/apprentice history.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.10`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/10-001.muirals-gauntlet.png`
- Level art: `/Dnd solo/Assets/Art/Levels/10-002.scarabs.png`
- Level art: `/Dnd solo/Assets/Art/Levels/10-003.spider.png`

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