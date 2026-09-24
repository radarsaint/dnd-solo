# Dungeon Level Layer Contract

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level story/runtime contract  
**Status:** Baseline behavior specification

## 1. Purpose

Every numbered dungeon level is a **living story layer**, not a chapter summary.

The keyed adventure text answers what is physically present in a room. The level layer must keep enough causal context active that the DM can answer, at any meaningful moment:

- what is happening on this level now;
- who wants what;
- what those actors will do if the player does nothing;
- what player actions change those plans;
- what evidence of the larger situation the player can actually perceive;
- what consequences survive after the player leaves.

A level layer is successful when the runtime can predict the next plausible actions of the level's actors **without rereading the entire chapter**, while still retrieving the keyed room text for immediate facts.

## 2. Authority

Use the campaign source and runtime authority order normally.

The level layer:
- interprets and operationalizes source-supported motives and conflicts;
- stores changes created by play;
- may derive a reasonable next action from an NPC's established motive, knowledge, means, and current circumstances;
- does not overwrite keyed room facts, current campaign state, or explicit aftermath conditions.

Do not invent a timed escalation, reinforcement, betrayal, faction offensive, or other off-screen event merely because it would be dramatic. If the source gives no schedule, advance background plans only when enough time, means, and cause exist in campaign state.

## 3. Geometry Contract

Every numbered level is bound to a canonical DM map listed in `docs/architecture/runtime/MAP_INDEX.md`.

The runtime must treat the map and keyed room text as a coordinated source pair:

- **DM map:** authoritative for room placement, boundaries, adjacency, doors, corridors, secret passages, stairs, shafts, vertical relationships, mapped gates, and printed scale.
- **Keyed room text:** authoritative for contents, creatures, traps, furnishings, environmental rules, and scripted conditions.
- **Campaign state:** authoritative for changes produced during play.

A keyed source area number binds to the identically numbered area on that level's canonical DM map. The runtime may describe geometry in natural language, but it may not invent or alter geometry to improve pacing, preserve a clue, simplify navigation, create an encounter, or make a scene more dramatic.

If the map and text appear to conflict, consult the errata layer. If no correction resolves the discrepancy, preserve it as an explicit ambiguity. Never fabricate a door, corridor, chamber, connection, or map correction.

### DM topology and player topology

The canonical DM map supplies complete DM topology. Player topology is a derived subset stored in spatial/knowledge state.

The existence of a player-map image does not reveal its full contents to the character. Secret rooms, secret doors, undiscovered routes, and unreached areas remain hidden until discovered in play.

### Mandatory level-load behavior

When a numbered level becomes active, load:
1. that level's story layer;
2. its canonical DM map binding from `MAP_INDEX.md`;
3. current spatial/knowledge overrides;
4. the smallest keyed room text needed for the current position.

Do not navigate from prose memory when the canonical DM map is available.

## 4. Required Story Engine

Every level must define the following.

### Initial Equilibrium
The exact situation when the player first enters if prior campaign state has not altered it.

### Active Motion
What important actors are already trying to accomplish. These plans exist independently of the player.

### Player Variable
What kinds of player actions can materially change the level's situation.

### Pressure Points
Rooms, scenes, objects, NPC meetings, deaths, bargains, discoveries, or conditions where the level story can change state.

### Reaction Rules
Explicit trigger -> consequence rules. These are the level's causal machinery.

### Escalation State
A small state machine describing the level's current condition. State changes are event-driven, not awarded for clearing rooms.

### Outcome States
The meaningful configurations in which the level can be left. Use published aftermath consequences wherever available.

### Player-Facing Evidence
What the player can observe that communicates the active story without DM exposition.

## 5. NPC Accountability

The level owns every NPC currently operating on it.

No named NPC may be run as a stat block with no motive state.

### Required NPC State

```yaml
npc_state:
  id:
  name:
  source_location:
  current_location:
  status: alive
  motive:
  immediate_goal:
  plan_if_unopposed:
  fears_or_constraints: []
  knowledge: []
  beliefs: []
  relationships: {}
  faction:
  attitude_to_player: unknown
  promises_and_debts: []
  injuries_or_conditions: []
  resources: []
  next_action: null
  last_meaningful_event: null
```

### Preloaded NPCs
Preload actors whose motives shape the level before the player meets them.

### Room-Scoped NPCs
Named or individually characterized NPCs may remain dormant until their room becomes relevant. **Before the scene is presented**, retrieve the full keyed-room source and instantiate them into NPC state.

If the source gives an NPC a specific motive, fear, secret, relationship, loyalty, grievance, plan, or personality constraint, preserve it. Faction defaults may fill gaps but never erase individual characterization.

After an NPC has interacted meaningfully with the player, never collapse them back into generic faction behavior.

### Shared Bodies / Multiple Wills
When multiple intelligences share or control one body or object, maintain separate motive records when their goals can diverge. Examples include sentient items affecting a creature's personality or creatures under external control.

### NPC Movement
If an NPC leaves the level, move the same stable NPC record into campaign state or the destination level. Never recreate them from untouched source text.

### NPC Decision Rule
Before choosing a consequential NPC action, answer:

1. What does this NPC want now?
2. What do they know and believe?
3. What are they afraid of losing?
4. What resources, allies, territory, or leverage can they use?
5. What would they do if the player were not here?
6. What has the player changed?
7. What action is now most consistent with all six answers?

## 6. Actor Network

Every level must describe the important relationships among its actors and factions.

Examples:
- competes with;
- commands;
- fears;
- secretly undermines;
- depends on;
- is using;
- is protecting;
- wants dead;
- can replace;
- can release.

This prevents NPC motives from existing as isolated character cards.

## 7. Level State

Each level maintains only the state needed to preserve its story. Typical fields include:

```yaml
level_story_state:
  level_id:
  escalation_state:
  controlling_factions: {}
  active_plans: []
  discovered_secrets: []
  alliances: []
  hostilities: []
  environmental_changes: []
  critical_resources: {}
  unresolved_pressure_points: []
  npc_refs: []
  cross_level_consequences: []
  halaster_relevant_events: []
```

Do not duplicate detailed room-state or combat-state that already belongs in spatial or encounter state.

## 8. Player-Facing Story Discipline

The runtime knows the level story. The player receives only evidence their character could perceive.

Prefer:
- patrol behavior;
- occupied or abandoned territory;
- prisoners;
- damage from recent fighting;
- rumors and biased testimony;
- environmental consequences;
- NPC requests and threats;
- visible preparations;
- missing people or supplies;
- changes on return visits.

Do not explain the level's faction diagram to the player.

Conflicting NPC accounts are allowed when the NPCs have different beliefs or interests.

## 9. Scene Loop

Before presenting a keyed area:

1. Retrieve the keyed-room source.
2. Apply campaign and level-state overrides.
3. Instantiate every relevant named/individual NPC in the scene.
4. Check whether the room or current action is a pressure point.
5. Determine what active actors know about the current situation.
6. Update their immediate goals only if circumstances justify it.
7. Present only player-perceivable evidence.

After a meaningful player action:

1. Update room/encounter state.
2. Update affected NPC motives, relationships, knowledge, and next actions.
3. Apply any explicit reaction rule whose trigger occurred.
4. Update escalation state if its condition was met.
5. Schedule only source-supported or causally justified delayed consequences.
6. Record cross-level and Halaster consequences separately.

## 10. Background Tick

A background tick occurs only when meaningful time passes, the player rests/travels/leaves, or another runtime system advances time.

For each active plan:
- confirm the actor is alive and capable;
- confirm the actor still wants the outcome;
- confirm they have the means and opportunity;
- advance only as far as the elapsed time and source support justify.

Published aftermath text is authoritative guidance for long-term change.

## 11. Halaster Integration

Load `HALASTER_DM_LAYER.md` and `HALASTER_THROUGH_LINE_LAYER.md` independently.

The level layer identifies local Halaster-relevant pressure points and consequences. It does not make Halaster the automatic focus of local play.

## 12. Cross-Level Continuity

When a level contains a thread whose cause or payoff lies elsewhere, name it explicitly.

Examples include:
- an NPC or item sought on another level;
- a faction war spanning multiple levels;
- a future quest payoff;
- an NPC who can travel with the player;
- a consequence that changes a later level.

The destination level must read the current campaign state instead of assuming the source-default version of that thread.

## 13. Departure / Return Contract

When the player leaves a level, record:
- surviving actors and their current next actions;
- faction/control changes;
- unresolved threats;
- promises, debts, allies, enemies;
- environmental changes;
- critical resource ownership;
- cross-level consequences;
- Halaster-relevant events;
- mobile NPCs and their destination.

On return:
1. load the saved level state;
2. apply elapsed-time background ticks;
3. apply explicit published aftermath consequences that have matured;
4. retrieve rooms against changed state rather than resetting to source defaults.

## 14. Visual Asset Contract

Level visuals are resolved through `/Dnd solo/Assets/ASSET_REGISTRY.json`. This registry supplements rather than replaces the geometry contract. `MAP_INDEX.md` remains canonical for map identity, keyed-area binding, and geometry.

Each numbered level should name its visual registry key (`levels.NN`) and any currently indexed level-art assets. Level 0 uses `levels.00`; Skullport uses `hubs.skullport`.

Rules:
- DM maps remain private topology references.
- Player maps remain knowledge-gated even when unlabeled.
- Level/scene art may be shown only after source and current state make the depicted subject perceivable, and only when the image itself does not leak unrevealed information.
- Creature/NPC art is resolved by entity identity, not by guessing that the entity must be present on a level because an image exists.
- Handouts are reveal-gated. A sheet containing multiple secrets, runes, or cards must not be exposed wholesale because one component became known.
- Art illustrates established source/state. It never creates canon, proves a hidden fact, or overrides keyed text, map geometry, or current state.

## 15. Failure Conditions

A level layer has failed if:
- the level feels like unrelated rooms despite a source-supported conflict;
- major NPCs wait motionless for the player despite explicit plans;
- every faction reacts identically to the player;
- NPC motives disappear once combat starts;
- a room-scoped named NPC is presented before motive state is instantiated;
- aftermath consequences are forgotten;
- dead or displaced factions silently reset;
- the DM has to reread the whole chapter to know what the major actors do next;
- the runtime invents major off-screen developments without source support, time, or means;
- the level's local story is overwritten by the Halaster campaign layer.