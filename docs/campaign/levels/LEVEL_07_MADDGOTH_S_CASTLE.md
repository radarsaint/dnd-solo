# Level 7 — Maddgoth’s Castle — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 7: Maddgoth’s Castle  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-07.01-maddgoths-castle-dm.png`  
**Player presentation map:** `assets/maps/levels/map-07.01-maddgoths-castle-player.jpg`  
**Keyed source areas:** 1–47  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

A contained wizard-murder mystery inside a miniature castle whose owner is initially absent. The tension is that the party is exploring the home of a serial killer who may return.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Who controls Maddgoth's miniature castle while its serial-killer owner is away, and can any alliance here survive the stone giants' engineered inability to remember it?

### Initial Equilibrium

Memory-damaged stone giants occupy the outer caverns and regard humanoid intruders as vermin. Otto secretly torments them with illusions while occupying Maddgoth's castle. Maddgoth's homunculus continues serving its absent master. A slaad inside the castle represents a separate takeover risk. Maddgoth is absent at first.

### Active Motion

- Otto continues invisible pranks against the giants and seeks a way to remove the homunculus permanently.
- The giants respond to perceived intrusions but lose memories older than roughly eight hours because of Halaster's alteration.
- The homunculus preserves Maddgoth's interests inside the castle.
- If given the opportunity, the slaad seeks control/security while waiting for Maddgoth and its control gem.
- Maddgoth may return after the characters leave and restore his murder-house operation.

### Player Variable

The player can earn temporary giant trust, expose Otto, aid Otto against the homunculus, release or empower the slaad, loot the castle, or leave evidence that changes Maddgoth's return.

### Pressure Points

- Outer giant caverns — memory curse and Otto's invisible interference.
- Castle approach / shrinking effect — transition into Maddgoth's private scale-controlled domain.
- Otto's relationship with the homunculus — key local alliance choice.
- Area 33 — slaad: potential castle succession threat.
- Maddgoth's study/suite/armory — evidence that the absent owner lures and murders wizards.

### Reaction Rules

- IF the player proves Otto caused the giant disturbances, THEN giant hostility can ease temporarily, but the benefit degrades as memories fade.
- IF the player removes/traps Maddgoth's homunculus for Otto, THEN Otto permits use of the castle under his terms.
- IF the slaad drives off the player and remains free enough to act, THEN it makes the castle its home and competes with Otto.
- IF all stone giants die, THEN Halaster may repopulate the vacated caverns with a new dangerous population after appropriate elapsed time.
- IF the player materially disturbs or loots the castle, THEN Maddgoth's later return must respond to the actual state left behind; he can restore defenses and bring reinforcements if challenged.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- DIVIDED DOMAIN — giants outside, Otto/homunculus inside, Maddgoth absent.
- TEMPORARY ALLIANCE — player has earned short-lived giant or Otto cooperation.
- CASTLE SUCCESSION — Otto, slaad, or returning Maddgoth is becoming dominant inside.
- OWNER RETURN — Maddgoth reasserts the serial-killer lair after the player's departure.

### Outcome States

- Little lasting change among surviving giants because the memory curse erases history.
- Otto controls the castle with the homunculus removed.
- The slaad establishes itself and contests Otto.
- Maddgoth returns, repairs the castle, and resumes luring wizard victims.
- Outer caverns are repopulated if the giant family is wiped out.

### Player-Facing Evidence

- Giants accuse newcomers of recent events they cannot coherently remember.
- False passages and altered-looking tunnels reveal an unseen illusionist before Otto is known.
- The miniature castle and trophy spaces reveal an owner with highly specific predatory interests.
- Return visits show giants genuinely failing to recognize the player.

## Actor Network

- Otto -> giants: prankster tormentor, not conqueror.
- Giants -> humanoids: perceived infestation; trust is possible but ephemeral.
- Otto -> homunculus: wants it permanently removed.
- Homunculus -> Maddgoth: persistent loyalty.
- Slaad -> castle: potential opportunistic occupier.
- Maddgoth -> visiting mages: future murder victims.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Maddgoth

**Motive:** Lure wizards to the castle, murder them, and keep arcane trophies.  
**Plan if unopposed:** Return according to source conditions and treat capable spellcasters as potential victims.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Otto

**Motive:** Keep the castle as a lair and indulge his own games and mischief while Maddgoth is away.  
**Plan if unopposed:** Manipulate visitors through play, deception, and self-preservation.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Maddgoth's Homunculus

**Motive:** Protect Maddgoth's property and interests in his absence.  
**Plan if unopposed:** Observe intruders and respond according to its bond and source instructions.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Gravillok and Speleosa

**Motive:** Protect their stone-giant family and caverns from what they perceive as humanoid infestation.  
**Plan if unopposed:** Respond defensively to intrusions and Otto's unexplained magical harassment, then lose older memories because of Halaster's curse.  
**Runtime:** Maintain family casualties and current eight-hour memory window separately; they cannot act on facts they have already forgotten.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Approach through the stone giant caverns — establish scale and separation.
- The castle interior — investigation of a killer's private domain.
- Otto's Game — NPC-driven interaction with its own agenda.
- Maddgoth's possible return — condition-driven escalation.

## Level State That Must Persist

- Maddgoth present/absent
- Otto relationship
- Homunculus status
- Wizard trophies/records discovered
- Castle defenses altered

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Maddgoth carries a horned ring relevant to Undermountain's transport restrictions.
- The level's memory curse is a direct Halaster intervention and should remain recognizable as such.

## Halaster Through-Line

No required live Halaster contact. The floor is allowed to be Maddgoth's story.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

If Maddgoth returns, his response must reflect what the player changed. Survivors retain memory and plans; do not reset the castle.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.07`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/07-001.maddgoths-castle.png`

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