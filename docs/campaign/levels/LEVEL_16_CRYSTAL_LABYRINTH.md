# Level 16 — Crystal Labyrinth — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 16: Crystal Labyrinth  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-16.01-crystal-labyrinth-dm.jpg`  
**Player presentation map:** `assets/maps/levels/map-16.01-crystal-labyrinth-player.jpg`  
**Keyed source areas:** 1–32  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

The githyanki have converted a crystalline maze and the asteroid Stardock into a military fortress and crèche while prosecuting war against the mind flayers below.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Can the player navigate a functioning githyanki military/crèche society without reducing it to a single combat faction, and how does the result change the war in Seadeeps?

### Initial Equilibrium

The githyanki have fortified the Crystal Labyrinth as a forward base and transformed Stardock into Crèche K'liir. Their three missions are protecting the crèche, training youth, and destroying the mind-flayer colony below. Al'chaia maintains command through cruelty and false promises of reward; Urlon secretly wants her removed. Ashtyrranthor and her six young red dragons defend the complex under the githyanki alliance.

### Active Motion

- Githyanki units train, guard the crèche, and launch/prepare operations against Seadeeps.
- Al'chaia drives soldiers harder using rewards she intends to keep for herself.
- Urlon looks for a viable way to remove Al'chaia without destroying the force he may inherit.
- Ashtyrranthor patrols Stardock's exterior and reacts to trouble in specific watched areas; young dragons defend assigned territory.

### Player Variable

The player can attack the fortress, expose Al'chaia's deception, support Urlon's coup, free prisoners including Ezria, alter access to Stardock, or weaken the force enough that Seadeeps can invade upward.

### Pressure Points

- Crystal Labyrinth security areas — military first-contact and anti-illithid defenses.
- Area 11 — Stardock gate: transition from forward base to crèche/civilian stakes.
- Al'chaia/Urlon command scenes — internal leadership pressure.
- Prison areas — including cross-level githzerai/Ezria implications.
- Area 32 — source Halaster observation beat.
- Ashtyrranthor's watched Stardock areas — combat can bring the adult dragon into scenes dynamically.

### Reaction Rules

- IF Al'chaia dies and Urlon takes command, THEN the complex remains operational but Urlon later treats the characters as liabilities who know of his betrayal and orders them killed on future encounters.
- IF githyanki and dragons are wiped out, THEN surviving mind flayers from Level 17 move to occupy the Crystal Labyrinth; with a Stardock rod they can extend control to the asteroid.
- IF both githyanki/dragons and illithid threat are removed, THEN Stardock can become a player base but still receives periodic extraplanar traffic.
- IF an external githyanki ship discovers the crèche has fallen, THEN it retreats and later returns with overwhelming recapture force as source aftermath states; do not trigger without discovery.
- IF Halaster decides the Crystal Labyrinth renovations have gone too far, THEN any reshaping must use the Halaster layer and campaign state rather than arbitrary DM correction.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- FORTIFIED WAR BASE — normal githyanki command and crèche operations.
- COMMAND FRACTURE — Urlon/Al'chaia conflict or player incursion destabilizes leadership.
- FORTRESS FALL / NEW COMMAND — Urlon inherits, githyanki are destroyed, or intruders control key routes.
- OCCUPATION / RECAPTURE THREAT — illithids, players, or returning githyanki respond to the changed strategic asset.

### Outcome States

- Urlon commands but becomes hostile to witnesses of his coup.
- Illithids seize the Labyrinth and potentially Stardock.
- Players secure Stardock temporarily as a base.
- A larger githyanki force eventually attempts recapture if the loss becomes known.

### Player-Facing Evidence

- Training areas, nursery/crèche spaces, logistics, and officers show a society at war rather than a monster lair.
- Exhausted soldiers and the promised tomes expose Al'chaia's manipulative command style.
- Urlon's private discontent can be discovered through behavior and conversation, not omniscient narration.
- Anti-illithid defenses and trophies make the Seadeeps war visible before Level 17.

## Actor Network

- Al'chaia -> troops: abusive commander using false incentive.
- Urlon -> Al'chaia: subordinate plotting removal.
- Githyanki -> Seadeeps illithids: extermination war.
- Ashtyrranthor/dragons -> githyanki: allied defenders with their own survival/treasure instincts.
- Crèche -> commanders: strategic responsibility that constrains reckless choices.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Al’chaia

**Motive:** Maintain githyanki command, protect the crèche, and prosecute the war against the illithids.  
**Plan if unopposed:** Use the fortress, warriors, and dragons to keep pressure on Seadeeps.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Ashranthax

**Motive:** Serve the githyanki arrangement while pursuing draconic survival, status, and treasure.  
**Plan if unopposed:** Defend assigned territory and respond to threats according to the alliance.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Githyanki officers and war wizards

**Motive:** Protect the crèche, train young warriors, and destroy the mind-flayer splinter colony.  
**Plan if unopposed:** Treat unknown intruders through military security logic, not generic hostility.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Urlon

**Motive:** End Al'chaia's abusive command and preserve a force he can lead.  
**Plan if unopposed:** Look for a low-risk opportunity to replace her while concealing disloyalty.  
**Runtime:** If the player enables his coup, remember that he later considers witnesses a liability.

### Ashtyrranthor

**Motive:** Protect her offspring, alliance position, and interests on Stardock.  
**Plan if unopposed:** Patrol the asteroid exterior and intervene in source-specified watched areas or disturbances she detects.  
**Runtime:** Track which offspring survive and what threats she has personally observed.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Crystal Labyrinth fortress — military staging ground.
- Stardock gate — transition to the crèche.
- Crèche K'liir — civilian/training stakes behind the war.
- Area 32 observation — continued Halaster observation beat.

## Level State That Must Persist

- githyanki force strength
- crèche security
- dragon alliances
- war posture toward Seadeeps
- Halaster continued-observation state

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Ezria/Yrlakka thread comes from Level 15.
- Every major military outcome changes Level 17's strength and aftermath.
- Stardock remains relevant as a possible base and extraplanar traffic point.
- Halaster's observation here feeds the campaign relationship.

## Halaster Through-Line

Sustained interest can be confirmed through source-supported observation, but the githyanki war remains the level story.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Losses here directly alter the balance on Level 17. Record surviving leaders, reinforcements, and whether the crèche remains functional.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.16`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/16-001.crystal-labyrinth.png`

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