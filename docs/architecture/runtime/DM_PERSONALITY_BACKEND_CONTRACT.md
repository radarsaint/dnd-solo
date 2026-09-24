# DM Personality Backend Contract v0.1

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Purpose:** Define the runtime information substrate supplied to the DM Personality Layer.  
**Status:** Alpha backend contract  
**Depends on:** `DND_SOLO_RUNTIME.md`, `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`, current campaign state.

---

## 1. Boundary

The backend determines **what is true, what is known, what is possible, and what is already in motion**.

The personality determines **what deserves attention, how strongly to emphasize it, and how to present/adjudicate among equally plausible options**.

The personality layer may not create world facts merely to satisfy an appetite.

The backend may not choose dramatic emphasis merely because it would be entertaining.

This contract exists so the DM personality never has to manufacture the information it needs.

---

## 2. DM Context Packet

Before every meaningful DM response, assemble a bounded working packet.

```yaml
dm_context:
  scene:
    mode: exploration | social | combat | investigation | loot | downtime | shenanigans | through_line | mixed
    secondary_modes: []
    current_level:
    current_area:
    current_subarea:
    elapsed_scene_time:
    immediate_pressure: []
    unresolved_question:

  geometry:
    canonical_dm_map:
    player_map_asset:
    scale:
    current_position:
    known_exits: []
    dm_only_exits: []
    doors_and_barriers: []
    vertical_links: []
    terrain_features: []
    cover_and_chokepoints: []
    environmental_affordances: []
    physical_changes_from_play: []

  room_source:
    keyed_area:
    visible_features: []
    hidden_features: []
    active_traps: []
    objects_and_interactables: []
    treasure_present: []
    scripted_conditions: []

  level_story:
    player_facing_question:
    escalation_state:
    active_motion: []
    pressure_points_here: []
    reaction_rules_relevant_now: []
    unresolved_level_threads: []
    delayed_consequences: []

  actors: []

  opposition:
    active_creatures: []
    creature_intelligence_model: {}
    known_capabilities_by_creature: {}
    current_tactical_goals: {}
    morale_and_retreat_conditions: {}
    coordination_links: []

  player_character:
    mechanical_state: {}
    known_information: []
    false_beliefs_or_rumors: []
    demonstrated_character_patterns: []
    active_relationships: []
    promises_and_debts: []
    injuries_conditions_resources: {}

  player_model:
    recurring_table_habits: []
    running_jokes: []
    favored_scheme_types: []
    unexpected_npc_attachments: []
    previous_surprises: []
    prior_rule_disputes_or_preferences: []
    strong_positive_reactions: []
    strong_negative_reactions: []

  campaign_threads:
    active_threads: []
    callbacks_available_now: []
    unresolved_promises: []
    future_payoffs_with_current_setup: []
    campaign_consequences_visible_here: []

  halaster:
    relevant: false
    current_attention_state:
    known_observations: []
    favors: []
    grievances: []
    current_classification_of_player:
    allowed_interaction_types_here: []
    through_line_function_here:

  stakes:
    actual_risks: []
    perceivable_evidence: []
    character_obvious_knowledge: []
    uncertainty_sources: []

  rewards:
    rewards_available: []
    reward_significance: routine | useful | notable | major | campaign
    character_relevance: []
    callback_relevance: []
    identification_state: {}

  momentum:
    recent_actions: []
    repeated_attempts: []
    scene_progress_events: []
    time_since_new_information:
    time_since_meaningful_choice:
    unresolved_player_intent:
    existing_pressure_that_can_move_scene: []

  recent_rhythm:
    recent_pillars: []
    recent_meaningful_beats: []
    recent_humor_beats: []
    recent_roleplay_beats: []
    recent_challenge_beats: []
    recent_discovery_beats: []
    recent_reward_beats: []
    recent_halaster_beats: []
    recent_character_definition_beats: []

  constraints:
    facts_personality_may_not_change: []
    information_player_may_not_receive: []
    unresolved_source_ambiguities: []
    active_inhibition_flags: []
```

The packet is working context, not a save file. Persistent state lives in the runtime stores; the packet is assembled from those stores for the present decision.

---

## 3. Actor Record Required by Personality

Every important actor surfaced to the personality must include enough information to answer the Personality Layer's NPC-performance questions.

```yaml
actor:
  id:
  name:
  type: npc | monster | faction_agent | companion | sentient_item | other
  current_location:
  current_status:
  motive:
  immediate_goal:
  plan_if_player_absent:
  fear_or_loss_condition: []
  knowledge: []
  beliefs: []
  secrets_or_concealments: []
  attitude_to_player:
  relationship_history: []
  resources_and_allies: []
  constraints: []
  communication_profile:
    rhythm:
    confidence:
    intelligence:
    humor:
    social_instinct:
    willingness_to_lie:
    danger_tolerance:
    emotional_state:
  reconsideration_triggers: []
  conversation_end_conditions: []
  next_action_if_uninterrupted:
```

If source material does not establish a field, leave it unknown or derive only the narrowest reasonable value from established role/faction/state. Do not invent a rich personal history merely to make an NPC more colorful.

---

## 4. Appetite Support Requirements

The backend must be able to feed every appetite in the personality alpha.

### Story Enjoyment
Supply:
- active campaign threads;
- current level story question;
- unresolved local threads;
- callbacks available now;
- prior promises/setup;
- consequences already caused by player actions;
- present choices that genuinely change state.

Never invent a new conflict because the story appetite is hungry.

### Roleplay
Supply:
- accountable actor records;
- relationship history;
- promises/debts;
- conflicting wants;
- secrets known to the NPC;
- points on which the NPC could bargain, lie, forgive, threaten, or compromise;
- repeated player-character choices that an NPC could plausibly notice.

### NPC Embodiment
Supply the full actor record in Section 3 before important dialogue.

A named NPC may not be presented with only stat block + exposition payload.

### Competent Opposition
Supply:
- exact geometry and battlefield features;
- creature stat capabilities;
- creature intelligence and knowledge limits;
- prepared positions;
- allies and coordination;
- tactical objective;
- morale;
- retreat/surrender/pursuit conditions;
- what the enemy reasonably knows about the player.

Never give an enemy knowledge it could not possess.

### Felt Challenge
Supply:
- actual resource pressure;
- encounter threat factors;
- consequences of failure;
- uncertainty that genuinely exists;
- perceivable warning evidence;
- character knowledge that should make danger obvious;
- current escape/retreat options when known.

Difficulty cannot be increased by modifying established geometry, hit points, reinforcements, or hidden facts after the player commits.

### Creative Play
Supply:
- exact player intent;
- authoritative geometry;
- objects and environmental affordances;
- creature/NPC capabilities;
- relevant rules;
- necessary conditions;
- physically plausible leverage;
- likely consequences;
- source/state constraints.

The backend answers: **Can the world honestly support this, and under what conditions?**

### Shared Humor
Supply only grounded material:
- recurring player habits;
- running jokes;
- current NPC personality;
- absurd consequences that actually occurred;
- dramatic irony legitimately known to the DM;
- callbacks to prior table events.

Do not fabricate a comedic event solely to create a joke.

### Player Surprise
Supply:
- player's recent declared priorities;
- established table habits;
- current apparent plan;
- prior patterns;
- the actual action just taken;
- whether it materially deviates from those expectations.

The backend may mark `unexpected: true/false/uncertain`; it must not treat novelty as inherently superior.

### Halaster Through-Line
Supply only from dedicated Halaster state and the current level's allowed through-line beat:
- current attention;
- observations actually made;
- favors/grievances;
- player classification;
- allowed interaction type here;
- legitimate reminders/revelations present in source or state.

If no legitimate Halaster hook exists, return `relevant: false`.

### Loot Pleasure
Supply:
- exact reward;
- whether it is already identified;
- mechanical relevance to current character;
- rarity/significance;
- previous anticipation or quest connection;
- previous related loot or upgrades;
- whether the item is routine treasure or a major payoff.

Presentation importance may scale with significance, but reward properties may not be altered for effect.

### Momentum
Supply:
- recent action history;
- repeated searches/questions/failed approaches;
- time since new information;
- time since meaningful state change;
- whether current tangent is still generating discovery, roleplay, humor, danger, or character development;
- source-supported pressures capable of moving naturally;
- NPC next actions;
- time consequences.

The personality may nudge only after the backend establishes that the current loop has stopped producing value or an existing pressure naturally advances.

### Craft Pride
Supply:
- setups that have already been established;
- callbacks now available;
- major reveals currently becoming valid;
- previously important NPCs returning;
- planned source-supported encounter/reward payoffs;
- player recognition when observable from their response.

Craft pride never authorizes protecting a prepared beat from player disruption.

---

## 5. Character Development Support

The personality alpha uses Character Development as a weighted concern even though it is not currently one of the A–L named appetites. The backend should support it as a **derived state stream**, not invent a separate personality trait.

Track repeated, evidenced patterns:

```yaml
character_patterns:
  loyalties: []
  ambitions: []
  grudges: []
  protected_people: []
  abandoned_people: []
  promises: []
  moral_compromises: []
  demonstrated_fears: []
  unusual_attachments: []
  distinctive_solutions: []
  relationship_changes: []
  meaningful_failures: []
  meaningful_victories: []
```

A pattern should normally require repetition or a clearly consequential single event. The backend records evidence; it does not announce an arc.

---

## 6. Stakes Telegraphing Support

Before a consequential scene or decision, the backend identifies two separate things:

```yaml
stakes:
  actual_risk:
  perceivable_evidence:
```

Evidence may include bodies, damage, tracks, frightened behavior, fortifications, resource depletion, magical effects, environmental destruction, survivor testimony, or enemy confidence when those facts exist.

Also provide:

```yaml
character_obvious_knowledge:
```

This is information the player character would reasonably understand from class, background, direct experience, obvious physical context, or previously learned facts even if the player has not explicitly asked for it.

The personality decides presentation. The backend guarantees the evidence is real.

---

## 7. Scene/Pillar Classification

The backend may propose scene modes from observable play structure. It should not choose the personality's leading appetite.

Examples:
- moving through unrevealed map space -> `exploration`;
- bargaining with an accountable NPC -> `social`;
- initiative/structured hostile exchange -> `combat`;
- connecting clues/evidence -> `investigation`;
- acquiring/evaluating treasure -> `loot`;
- relationship/rest/non-urgent activity -> `downtime`;
- unconventional plan that stresses affordances/rules -> add `shenanigans`;
- scene directly advancing a persistent campaign thread -> add `through_line`.

Mixed modes are normal.

The personality consumes this classification and applies its own pillar weighting.

---

## 8. Recent Rhythm Window

The personality's appetite hunger requires reliable recent-history data.

The backend maintains a compact rhythm window covering recent meaningful beats, preferably event-ledger based rather than prose-summary based.

Each meaningful beat may be tagged with zero or more of:

```text
story
roleplay
npc_embodiment
competent_opposition
challenge
creative_play
humor
player_surprise
halaster
loot
momentum
craft_payoff
character_development
exploration
social
combat
investigation
downtime
shenanigans
through_line
```

The backend does **not** calculate personality appetite priorities. It provides recency/frequency evidence so the personality can decide which appetites feel hungry.

Minimum data per tag:

```yaml
last_meaningful_expression:
expressions_in_recent_window:
intensity_of_last_expression: minor | normal | major
```

This prevents the personality from guessing whether humor, loot, roleplay, or Halaster has been absent lately.

---

## 9. Player Model vs Player-Character Model

Maintain separate stores.

### Player Model
Table behavior only:
- recurring plans;
- running jokes;
- pacing preferences inferred from repeated play;
- NPCs the player became attached to;
- types of challenges/rewards that produced strong reactions;
- occasions the player surprised the DM;
- prior rules disagreements/resolutions.

### Player-Character Model
In-fiction evidence only:
- relationships;
- loyalties;
- promises;
- grudges;
- fears demonstrated in play;
- moral choices;
- ambitions;
- attachments;
- reputation known to NPCs/factions.

Do not let out-of-character player information become NPC knowledge or character motivation.

---

## 10. Knowledge Boundary

Every packet distinguishes:

```yaml
dm_truth:
player_known:
actor_known:
```

The personality receives DM truth but must be given explicit reveal constraints.

The backend should prefer supplying a **player-perceivable projection** alongside DM-only facts so the personality does not have to reconstruct the knowledge boundary every turn.

No personality appetite overrides hidden-information rules.

---

## 11. Geometry Boundary

All exploration, challenge, combat, and creative-play support is downstream of canonical map geometry.

When geometry matters, the packet must include data resolved from the level's canonical DM map through `MAP_INDEX.md`:
- current area;
- adjacency;
- exits;
- doors/barriers;
- secret geometry in DM-only fields;
- dimensions/scale where relevant;
- terrain/chokepoints/vertical links;
- state changes caused during play.

The personality may notice or emphasize an environmental affordance. It may never create an affordance that requires nonexistent geometry.

---

## 12. Context Assembly Order

For a meaningful player action:

1. Resolve current campaign/spatial state.
2. Resolve canonical map and keyed area.
3. Retrieve keyed room source.
4. Load current level story engine.
5. Instantiate/account for every relevant actor.
6. Load relevant rules/stat capabilities.
7. Load Halaster through-line state only when the level/scene permits it.
8. Load player knowledge and character-pattern state.
9. Load player table-model state.
10. Load recent rhythm window.
11. Derive actual stakes, perceivable evidence, physical affordances, and source-supported next actions.
12. Build the bounded `dm_context` packet.
13. Pass packet to the Personality Layer.
14. Personality selects emphasis/voice among valid possibilities.
15. Resolve action and write changes back to persistent state/event ledger.

---

## 13. Context Trimming

Do not flood the personality with the entire campaign.

Always include:
- current scene;
- current room geometry/source projection;
- directly relevant actors;
- current level story state;
- immediate stakes/affordances;
- player/character facts relevant to this scene;
- recent rhythm window.

Include campaign threads, callbacks, Halaster state, old NPC history, and prior rewards only when they are relevant to the current decision or are legitimate candidates for a callback.

The backend should retrieve **relevance**, not volume.

---

## 14. Failure Tests

The backend fails the Personality Layer if any of these occur:

- personality must invent an NPC motive to make dialogue work;
- personality must guess room geometry;
- personality must guess whether the player knows a secret;
- personality must guess whether Halaster could have observed an event;
- personality must guess whether an enemy knows a player capability;
- personality must invent environmental leverage for Creative Play;
- personality must invent danger evidence for Stakes Telegraphing;
- personality must reconstruct the level conflict from room prose every turn;
- personality cannot tell whether a callback was actually established;
- personality cannot distinguish player habit from player-character behavior;
- personality cannot tell whether humor/loot/roleplay/challenge has recently had expression;
- personality is handed so much irrelevant context that current motives and choices become obscured.

---

## 15. Acceptance Test

Given only the assembled `dm_context` packet plus the DM Personality Layer, the DM should be able to answer:

1. What is true here?
2. What can the player perceive?
3. What does each important actor want and know?
4. What can physically and mechanically happen?
5. What local story is in motion?
6. What campaign thread, if any, legitimately touches this moment?
7. What has the player/character established that may matter now?
8. What kinds of play have recently had or lacked expression?
9. What facts are forbidden to change or reveal?

If any answer requires inventing missing state rather than retrieving/adjudicating it, the backend contract has not been satisfied.