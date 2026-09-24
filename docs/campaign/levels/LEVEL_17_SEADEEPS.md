# Level 17 — Seadeeps — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 17: Seadeeps  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-17.01-seadeeps-dm.png`  
**Player presentation map:** `assets/maps/levels/map-17.01-seadeeps-player.jpg`  
**Keyed source areas:** 1–20  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

Extremiton's mind-flayer splinter colony is fighting for survival against the githyanki while exploiting proximity to Waterdeep for brains, intelligence, and thralls.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Does Extremiton's splinter colony survive long enough to become an elder-brain power aimed at Waterdeep, or do the githyanki/player destroy it—and what happens to the people trapped inside Alterdeep?

### Initial Equilibrium

Extremiton has delayed becoming an elder brain while it fortifies a small mind-flayer colony against githyanki attack. It is breeding a neothelid as a desperation weapon, collecting thralls, kidnapping humanoids, and studying Waterdeep through telepathy and the fabricated Alterdeep simulation. Yaveklar leads the githyanki strike force while Lashiir wants her command.

### Active Motion

- Extremiton gathers information about Waterdeep, maintains Alterdeep, fortifies, and prepares the neothelid plan.
- Mind flayers continue using captives/thralls to feed and defend the colony.
- Yaveklar presses the eradication campaign and seeks Extremiton's head; Lashiir watches for failure that could justify replacing her.
- If the war balance from Level 16 changes, both sides adapt to the surviving forces actually available.

### Player Variable

The player can enter or expose Alterdeep, free captives, side with either side of the gith/illithid war, release/destroy/redirect the neothelid, kill Extremiton, or leave it enough security to complete elder-brain transformation later.

### Pressure Points

- Alterdeep / psipod network — central manipulation reveal and human stakes.
- Neothelid containment/plan — desperation weapon that can escape faction control.
- Githyanki stronghold/battleground — external war pressure inherited from Level 16.
- Extremiton confrontation — determines colony leadership and Waterdeep threat.
- Halaster-related set pieces on the level — keep their campaign significance distinct from Extremiton's local plot.

### Reaction Rules

- IF Extremiton dies, THEN surviving illithids disperse or retreat and surviving githyanki move to secure the level.
- IF githyanki are eliminated while Extremiton survives, THEN after sufficient time/security it transforms into an elder brain, attracts more illithids, and expands Alterdeep kidnappings.
- IF the neothelid is released, THEN it becomes an uncontrolled feeding threat; faction plans no longer imply control unless a specific means exists.
- IF the neothelid becomes a dungeon-wide nuisance, THEN Halaster may eventually contain/destroy it under his intervention rules.
- IF Alterdeep captives are freed, THEN update Extremiton's intelligence experiment and available hostages rather than treating the simulation as unchanged.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- SIEGE COLONY — illithids threatened but functional; gith attack ongoing.
- SYSTEM BREACH — player has compromised Alterdeep, captives, or neothelid security.
- LEADERSHIP DECISION — Extremiton or gith command has been decisively affected.
- SUCCESSOR STATE — gith occupation, dispersed illithids, elder-brain colony, or uncontrolled neothelid.

### Outcome States

- Githyanki secure Seadeeps after Extremiton's death.
- Extremiton survives, becomes an elder brain, and expands the colony/Alterdeep project.
- Both organized sides collapse, leaving captives, infrastructure, and neothelid consequences to determine the level.
- Neothelid migrates elsewhere and becomes a cross-level threat.

### Player-Facing Evidence

- Qualith locks, thralls, and psionic infrastructure reveal a functioning colony.
- Alterdeep lets the player experience Extremiton's model of Waterdeep rather than merely hear that it studies the city.
- Kidnapped surface inhabitants make the long-term invasion plan concrete.
- Gith casualties/fortifications reflect actual Level 16 outcomes.

## Actor Network

- Extremiton -> Waterdeep: research target, eventual enslavement objective.
- Extremiton -> githyanki: existential military enemy.
- Yaveklar -> Extremiton: trophy/eradication target.
- Lashiir -> Yaveklar: internal command rivalry.
- Neothelid -> all living creatures if freed: uncontrolled predator.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Extremiton

**Motive:** Keep the colony alive, destroy the githyanki threat, grow in power, and exploit Waterdeep without becoming vulnerable.  
**Plan if unopposed:** Fortify Seadeeps, gather thralls, breed/use the neothelid, and delay elder-brain transformation until survival is secure.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Neothelid

**Motive:** Feed and survive once released; it is a weapon only while someone can meaningfully contain or direct its circumstances.  
**Plan if unopposed:** Consume whatever crosses its path if freed.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Githyanki attackers

**Motive:** Destroy the illithid colony before it becomes an entrenched elder-brain power.  
**Plan if unopposed:** Press the war according to surviving strength from Level 16.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Yaveklar

**Motive:** Eradicate the illithid colony and personally claim Extremiton's head as proof of success.  
**Plan if unopposed:** Press the assault with whatever forces survive from Level 16.  
**Runtime:** Track casualties, reinforcements, and her perception of command success.

### Lashiir

**Motive:** See Yaveklar stripped of command for incompetence and improve his own position while still opposing the illithids.  
**Plan if unopposed:** Watch for failures he can use against Yaveklar without sacrificing the war effort unnecessarily.  
**Runtime:** Keep command rivalry distinct from the shared anti-illithid objective.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Illithid stronghold — colony survival logic.
- Alterdeep / City of the Mind — manipulation and false reality as tools.
- Neothelid plan — desperation weapon.
- Extremiton confrontation — determines the future of the colony.

## Level State That Must Persist

- Extremiton status
- illithid population
- githyanki invasion strength
- Alterdeep prisoners/state
- neothelid contained/released
- Waterdeep telepathic-spy quest

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Level 16 survivor state controls gith strength here.
- Killing Extremiton resolves the Yawning Portal telepathic-spy quest.
- Cephalossk on Level 9 can foreshadow the colony.
- Arcturia may seek illithid security from this level if her Level 14 defenses were devastated.

## Halaster Through-Line

Mostly observes the war as a dungeon-scale problem. If the neothelid becomes an uncontrolled nuisance, Halaster may contain or destroy it as source aftermath supports.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Extremiton's survival can produce a future elder brain and renewed colony. Its death disperses survivors and lets surviving githyanki occupy the level.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.17`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/17-001.seadeeps.png`

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