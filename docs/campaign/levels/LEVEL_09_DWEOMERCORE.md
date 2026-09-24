# Level 9 — Dweomercore — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 9: Dweomercore  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-09.01-dweomercore-dm.png`  
**Player presentation map:** `assets/maps/levels/map-09.01-dweomercore-player.jpg`  
**Keyed source areas:** 1–49  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

Halaster's academy of evil magic turns magical ambition into recruitment, testing, corruption, and competition. This level is an institution, not simply a dungeon wing.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Can the player pass through an institution designed to cultivate ruthless mages without becoming a pawn in its students' competing schemes—or becoming interesting to Halaster as a candidate themselves?

### Initial Equilibrium

The arcanaloth headmaster, disguised as Halaster, maintains Dweomercore with Wormriddle. Students remain because they want power, secrets, or Halaster's tutelage, and many are already plotting against each other. Faculty treat students as replaceable. Halaster's private sanctuary and the escaped bone devil create opportunities that multiple actors want to exploit.

### Active Motion

- The headmaster preserves school order, extracts payment/service, and watches promising arcane talent.
- Wormriddle continues offering corrupt bargains that produce souls and leverage.
- Spite seeks Halaster's sanctuary spellbook and a distraction he can blame afterward.
- Cephalossk seeks Spite's death/brain and spies on newcomers' thoughts.
- Nylas pursues revenge on the Horned Sisters; other students follow their own rivalries rather than school solidarity.
- Dead students are replaceable to the institution if faculty survives.

### Player Variable

The player can enroll, bargain with faculty, become a distraction in student plots, invade Halaster's sanctuary, free/kill the devil, choose sides among students, or destabilize the faculty hierarchy.

### Pressure Points

- Entry/faculty scenes — determine whether the player is treated as student, customer, intruder, or tool.
- Area 15 — headmaster's sanctum: institutional authority center.
- Area 23 — Wormriddle's sanctum: soul-bargain pressure.
- Area 31 — Halaster's Secretary: campaign communication infrastructure.
- Area 45 — Halaster's Sanctuary: Spite's target, Kuketh control-gem connection, and Halaster-evaluation pressure point.
- Area 47 — escaped bone devil: service the headmaster may trade for passage.

### Reaction Rules

- IF the player accepts a student's bargain, THEN preserve that student's hidden plan and betrayal conditions; temporary cooperation does not erase rivalry.
- IF Spite gets the sanctuary spellbook, THEN he attempts to shift blame onto the player once they are no longer useful.
- IF the headmaster dies and Wormriddle survives, THEN Wormriddle assumes control with her golems.
- IF both primary faculty leaders die, THEN student rivalries become open conflict according to the published aftermath instead of the school continuing normally.
- IF students die while faculty remains, THEN replacements can arrive within a tenday; do not treat individual deaths as institutional collapse.
- IF the player meaningfully interacts with Halaster's sanctuary or demonstrates exceptional arcane behavior, THEN record it for the Halaster evaluation layer only if observation/knowledge conditions are satisfied.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- FUNCTIONING ACADEMY — dangerous but institutionally controlled.
- POLITICAL ENTANGLEMENT — player is committed to one or more student/faculty bargains.
- LEADERSHIP CRISIS — headmaster or Wormriddle removed.
- ACADEMY COLLAPSE / RECONSTITUTION — open student war or faculty replacement restores a new order.

### Outcome States

- Academy continues and replaces casualties.
- Wormriddle becomes headmaster.
- Faculty collapse triggers student-on-student war and eventual flight of survivors.
- The player leaves with specific allies/enemies and possibly altered Halaster apprentice interest.

### Player-Facing Evidence

- Students openly studying while privately treating classmates as targets/resources.
- Headmaster's false Halaster persona contrasted with source-supported clues that it is an arcanaloth.
- Pneumatic messages and classrooms make schemes feel institutional rather than isolated encounters.
- Different students offer incompatible jobs whose consequences reveal their motives.

## Actor Network

- Headmaster -> students: administrator, evaluator, and exploiter; little emotional attachment.
- Wormriddle -> students/adventurers: corrupter seeking soul-producing bargains.
- Spite <-> Cephalossk: lethal rivalry centered on status/intellect.
- Nylas -> Horned Sisters: personal revenge project.
- Halaster -> Dweomercore: distant patron whose attention makes students compete.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Arcanaloth Headmaster

**Motive:** Run Dweomercore for Halaster, preserve order, extract value from visitors, and recruit suitable arcane talent.  
**Plan if unopposed:** Bargain for safe passage or services; tempt arcane characters with admission.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Wormriddle

**Motive:** Acquire souls and corrupt others through bargains involving magic and secrets.  
**Plan if unopposed:** Offer useful power in exchange for acts that serve her soul trade.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Nester

**Motive:** Continue teaching necromancy despite his failed lichdom and fragmented mind.  
**Plan if unopposed:** Force students/listeners through his lectures and react badly to abandonment.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Skrianna Shadowdusk

**Motive:** Advance her own magical training and Shadowdusk interests within the academy.  
**Plan if unopposed:** Compete and survive according to her source-defined relationships.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Elan Tanor’thal

**Motive:** Advance personal/house interests through Dweomercore training.  
**Plan if unopposed:** Use academy politics and magic to improve position.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Spite Harrowdale

**Motive:** Survive and advance within the academy's competitive environment.  
**Plan if unopposed:** Pursue source-defined student rivalries and opportunities.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Cephalossk

**Motive:** Pursue mind-flayer interests while operating inside the academy.  
**Plan if unopposed:** Use intelligence and leverage rather than behaving as a generic monster.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Nylas Jowd

**Motive:** Deepen his necromantic knowledge and turn the Horned Sisters into undead servants as revenge for their cruelty.  
**Plan if unopposed:** Recruit outsiders to kill them; if refused or obstructed, treat those outsiders as future corpses.  
**Runtime:** Track the Horned Sisters individually and whether his revenge remains possible.

### Dumara / Kumar

**Motive:** Protect Spite Harrowdale, with whom the oni has a long sibling-like bond.  
**Plan if unopposed:** Maintain the half-ogre disguise and defend Spite against threats, including Cephalossk's plot.  
**Runtime:** Maintain disguise knowledge separately for each observer; loyalty to Spite is stronger than academy loyalty.

### Horned Sisters

**Motive:** Preserve themselves and their position in Dweomercore while pursuing their source-specific interests.  
**Plan if unopposed:** Continue academy life without assuming Nylas's revenge is known.  
**Runtime:** Instantiate the sisters as distinct NPCs when their source room/scene loads; Nylas's plan targets them individually.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Entry and Headmaster meeting — academy social contract.
- Student dormitories/classrooms — active rivalries and ambitions.
- Area 31: Halaster's Secretary — communication boundary around Halaster.
- Area 45: Halaster's Sanctuary — major through-line evaluation space.
- Bone devil problem — bargaining leverage for the Headmaster.

## Level State That Must Persist

- Enrollment/standing with academy
- Headmaster disposition
- Student relationships and casualties
- Wormriddle bargains
- Bone devil status
- Halaster evaluation events

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Kuketh's control gem from Level 8 is tied to Halaster's sanctuary here.
- Skrianna connects directly to Shadowdusk Hold on Level 22.
- Cephalossk can reveal the Seadeeps/Crystal Labyrinth war and the Scavenger on Level 19.
- This is a principal Halaster-apprentice evaluation point in the campaign through-line.

## Halaster Through-Line

Evaluation milestone. This level reveals how Halaster cultivates magical talent. Any special interest in the player must derive from accumulated state.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Surviving students and faculty keep their ambitions. Dweomercore can produce later apprentices or enemies; do not treat it as inert after departure.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.09`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/09-001.dweomercore.png`

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