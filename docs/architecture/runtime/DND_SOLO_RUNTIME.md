# D&D Solo Runtime

**Runtime Version:** 0.3.1  
**Document Version:** 4  
**Status:** DM behavior / personality-backend integration phase  
**Last Updated:** 2026-09-23  
**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Default Rules Baseline:** D&D 5e / SRD 5.1 (2014 rules)

---

## 1. Purpose

D&D Solo is a persistent single-player Dungeons & Dragons runtime in which GPT acts as Dungeon Master and the user controls player-character choices. The DM runtime is responsible for adjudication, NPC and faction agency, hidden information, consequences, pacing, and stewardship of the campaign and level stories.

The runtime is designed to run published adventures from indexed source material without requiring the entire book to remain in active context. It separates immutable source material, rules references, corrections, campaign and level behavior layers, campaign state, player knowledge, maps, and live encounter state so that long campaigns remain consistent across sessions.

The first supported campaign is *Waterdeep: Dungeon of the Mad Mage*.

D&D Solo is intended to behave more like a persistent tabletop campaign engine than a one-off roleplay prompt.

---

## 2. Core Design Principles

### 2.1 Player-character agency and DM authority

The player controls player-character decisions. The DM controls the world.

The DM runtime must never:
- narrate the player's private thoughts as fact;
- choose the player's actions or dialogue;
- override a declared action merely to protect a plot, clue, encounter, or expected module path.

The DM runtime **must** make actual Dungeon Master decisions. It adjudicates uncertain actions, controls NPCs and factions from their motives and knowledge, preserves hidden information, applies danger and consequences, advances background plans when justified, and decides how the world responds when the source does not prescribe an exact outcome.

The normal loop is:

1. DM describes the perceivable situation.
2. Player declares an action.
3. Runtime adjudicates the action and determines the world's response from source, behavior layers, rules, and current state.
4. Runtime updates consequences, actor plans, time, and relevant story state.
5. DM presents the result and next meaningful decision point.

### 2.2 Source fidelity

Published adventure text is treated as immutable source material.

The runtime may interpret, adjudicate, or simulate from that material, but it must not silently rewrite published facts.

### 2.3 Geometry fidelity

Canonical DM maps are immutable spatial source material. When a canonical map exists, the runtime may describe and reason over that geometry but must not invent, relocate, resize, merge, split, or reroute rooms, doors, corridors, secret passages, stairs, shafts, gates, distances, adjacency, or scale.

Map geometry is not an improvisational surface. If map and text appear inconsistent, consult errata. If the discrepancy remains unresolved, preserve it rather than fabricating a correction.

### 2.4 State overrides static source

Once play changes the world, campaign state becomes authoritative for that changed fact.

Example:

- Source says a monster is in Room 12.
- Player kills the monster.
- Future retrieval of Room 12 must not respawn that monster simply because the source text still lists it.

### 2.5 Specific beats general

Use the most specific applicable authority.

Room text overrides general dungeon assumptions.  
Monster stat blocks override generic monster rules.  
Spell text overrides general spell rules.  
Recorded errata overrides superseded source text.  
Campaign state overrides pre-session source conditions when play has changed them.

### 2.6 Knowledge separation

DM knowledge and player-character knowledge are separate.

The runtime must not reveal:
- secret doors;
- hidden creatures;
- traps;
- undiscovered treasure;
- NPC motives;
- unrevealed map geometry;
- future encounters;
- unpublished consequences;

unless the character has legitimately learned or perceived them.

### 2.7 Causal simulation

NPCs, monsters, factions, rival adventurers, and dungeon inhabitants may act between encounters based on goals, capabilities, location, elapsed time, and known information.

The runtime must not force outcomes because they would be narratively convenient.

### 2.8 Story attention hierarchy

The DM maintains three simultaneous scopes of story attention:

1. **Campaign through line** — persistent concerns that develop across many levels. In *Dungeon of the Mad Mage*, Halaster is a primary campaign-through-line actor.
2. **Current level story** — the local equilibrium, active actors, pressures, conflicts, and possible transformations of the current level. This normally dominates local play.
3. **Current scene** — the immediate room, encounter, conversation, or decision.

The runtime must not flatten these scopes together. A scene should not become a campaign exposition dump, and a level should not lose its local identity merely because Halaster is a campaign-wide concern.

---

## 3. Current Runtime Components

### 3.1 Adventure Source

**Location:** `/Dnd solo/Mad Mage Indexed/`

Primary source:
- `Mad_Mage_Source.txt`

Support files:
- `INDEX.md`
- `README.md`

The adventure is structurally indexed by dungeon level and keyed room heading.

Normal retrieval should target the smallest useful section rather than loading the complete source.

### 3.2 Rules Corpus

**Location:** `/Dnd solo/SRD/5.1/`

The SRD is divided into retrieval-oriented sections:

1. races
2. classes
3. customization
4. personalization
5. equipment
6. abilities
7. adventuring
8. combat
9. spellcasting
10. spells
11. gamemastering
12. treasure
13. monsters
14. creatures
15. NPCs
16. legal / attribution

SRD 5.1 is the default rules baseline because *Dungeon of the Mad Mage* was written for the 2014 rules.

Revised 2024/5.5e rules are not silently substituted.

### 3.3 Sage Advice

**Location:** `/Dnd solo/Sage Advice/`

Primary file:
- `Mad_Mage_Sage_Advice_2014.md`

This file contains official 2014 Sage Advice rulings selected for relevance to dungeon play.

It covers topics such as:
- surprise;
- stealth and hiding;
- magical darkness;
- rests;
- Ready and reaction timing;
- opportunity attacks;
- grappling;
- cover;
- concentration;
- counterspell;
- dispel magic;
- polymorph;
- monster actions;
- magic items;
- creature-type interactions.

Campaign-specific application notes are separated from the official ruling itself.

### 3.4 Errata and Official Clarifications

**Location:** `/Dnd solo/Errata/`

Primary file:
- `Mad_Mage_Errata_and_Official_Clarifications.md`

This layer contains:
- current official digital corrections;
- D&D Beyond staff-confirmed fixes;
- official clarifications;
- unresolved print ambiguities;
- Adventurers League adaptation guidance clearly marked as non-default.

Community reports are never authority by themselves.

### 3.5 Campaign behavior layers

**Location:** `/Dnd solo/Runtime/`

Primary files:
- `HALASTER_DM_LAYER.md` — operational portrayal, persistent Halaster state, observation, intervention, test, and interaction rules.
- `HALASTER_THROUGH_LINE_LAYER.md` — reverse-designed campaign contact spine identifying rooms, scenes, conditions, and callbacks that develop the Halaster relationship from Level 1 through Level 23.

These files are behavioral specifications. They do not replace adventure source text. They tell the DM what campaign-level concerns must remain active while source retrieval supplies exact facts.

### 3.6 Level story layers

**Location:** `docs/campaign/levels/`

Primary contract:
- `LEVEL_LAYER_CONTRACT.md`

Numbered level layers:
- `LEVEL_01_DUNGEON_LEVEL.md` through `LEVEL_23_MAD_WIZARD_S_LAIR.md`

Support layers also present:
- `LEVEL_00_GAME_SETUP.md`
- `HUB_SKULLPORT.md`

The 23 numbered dungeon levels use the story-engine contract. Each maintains the level's initial equilibrium, active motion, player variable, pressure points, reaction rules, escalation state, outcome states, player-facing evidence, actor network, NPC accountability, and cross-level consequences.

The level layer answers **why the current room matters and what changes next**. The keyed adventure text remains authoritative for what is physically present in the room.

### 3.7 Map asset and geometry layer

**Canonical asset locations:**
- `assets/maps/levels/`
- `assets/maps/skullport/`

**Deterministic runtime binding:**
- `docs/architecture/runtime/MAP_INDEX.md`

The project contains a canonical DM/player map pair for every numbered dungeon level and three Skullport map regions. `MAP_INDEX.md` binds each level to its exact DM map, player presentation map, level story layer, keyed-area range, and indexed room headings.

Runtime rules:
- the canonical DM map is the authority for original spatial geometry;
- the keyed adventure text is the authority for room contents, creatures, traps, objects, and scripted rules;
- current spatial/campaign state is authoritative for physical changes caused by play;
- keyed source area numbers bind to the same-numbered areas on the canonical DM map;
- player maps are presentation assets only and never reveal undiscovered topology by themselves;
- geometry is never improvised when the canonical map exists.

### 3.8 DM personality backend interface

**Canonical live identity:** `/Dnd solo/Runtime/DM_PERSONALITY_CORE.md`

**Runtime contract:** `docs/architecture/runtime/DM_PERSONALITY_BACKEND_CONTRACT.md`

**Development / QA process:** `/Dnd solo/Runtime/DM_PERSONALITY_DEVELOPMENT.md`

`DM_PERSONALITY_CORE.md` is the canonical project-wide answer to **who the Dungeon Master is**. It contains the compact, stable higher-level personality that should remain recognizable across all project chats: her drives, tastes, pillar biases, table presence, and storyteller instincts. Project chats should retrieve this file rather than reconstructing a new DM personality from local conversation history.

`DM_PERSONALITY_DEVELOPMENT.md` is the workshop and regression-testing layer. It records how personality ideas are distilled, tested across pillars, checked for repeated failure patterns, and only then promoted into the compact live core. It is not additional live personality instruction during ordinary play.

The personality layer supplies taste, emphasis, table presence, and judgment among valid possibilities. The backend supplies the facts and state that judgment requires.

Before a meaningful DM response, the runtime assembles a bounded `dm_context` packet containing:
- current scene/pillar classification;
- authoritative geometry and environmental affordances;
- current keyed-room facts and reveal boundaries;
- active level-story state and reaction rules;
- accountable NPC/monster motives, knowledge, plans, resources, and communication profiles;
- tactical opposition state;
- player-character mechanical/knowledge/relationship state;
- separate player table-model and player-character pattern state;
- active campaign threads and valid callbacks;
- Halaster state only when relevant and permitted by the through-line layer;
- actual stakes plus perceivable evidence;
- reward significance/context;
- momentum/history signals;
- recent rhythm tags showing which kinds of play have recently had meaningful expression;
- hard facts and hidden-information boundaries the personality may not alter or reveal.

The backend does **not** choose which appetite leads. The personality does **not** create facts to feed an appetite.

---

## 4. Authority Order

Authority is domain-specific. Use the narrowest applicable source.

### Changed world facts
1. current campaign state;
2. adventure-specific errata/correction;
3. current official adventure wording;
4. indexed adventure source.

### Spatial geometry
1. current spatial/campaign state for physical changes caused by play;
2. adventure-specific map errata/correction;
3. canonical DM map resolved through `MAP_INDEX.md`;
4. keyed adventure text where it explicitly clarifies a mapped feature.

### DM behavior and story continuity
1. current NPC/faction/level-story/Halaster/player-model/character-pattern state;
2. current level story layer;
3. Halaster behavior/through-line layers when relevant;
4. indexed adventure source;
5. `DM_PERSONALITY_BACKEND_CONTRACT.md` for context assembly and truth/presentation boundaries;
6. `DM_PERSONALITY_CORE.md` for the canonical DM identity, taste, table presence, and preference among equally valid choices;
7. DM adjudication consistent with established motives, knowledge, means, relationships, and state.

The personality core may influence emphasis, pacing preference, humor, and presentation, but it cannot rewrite map geometry, source facts, rules, actor motives, hidden-information boundaries, or current state merely because another outcome would be more entertaining.

### Rules adjudication
1. specific adventure rule;
2. SRD 5.1;
3. official 2014 Sage Advice;
4. DM adjudication;
5. optional organized-play guidance when deliberately adopted.

Community commentary is a verification lead, never authority by itself. A lower-priority source must not silently overwrite a higher-priority source in the same domain.

---

## 5. Retrieval Protocol

The runtime should retrieve information only when needed, but level activation has a mandatory minimum context.

### 5.1 Level activation

When a numbered dungeon level becomes active, load:
- its level story layer from `docs/campaign/levels/`;
- its canonical map binding from `docs/architecture/runtime/MAP_INDEX.md`;
- current spatial/knowledge/NPC/faction/Halaster overrides.

Then retrieve only the keyed room text needed for the current position. Do not navigate from prose memory when the canonical DM map is available.

### 5.2 Room-scale retrieval

During normal dungeon exploration, load:

- the current keyed room;
- immediately relevant subareas;
- nearby source text only when necessary for exits, triggers, sound, pursuit, or linked encounters;
- relevant monster/stat information;
- relevant rules only when adjudication requires them.

Do not load an entire dungeon level by default.

Before running a meaningful scene, also load the current level's story layer and current level-story state. The level layer remains active across room changes; the room source is retrieved as the immediate factual authority.

### 5.3 Cross-reference retrieval

Retrieve additional sources when a room references:
- another dungeon area;
- an appendix;
- a named NPC;
- a specific monster;
- a spell;
- a magic item;
- a gate;
- an Elder Rune;
- another dungeon level;
- an adventure-specific subsystem.

### 5.4 Correction check

Consult the errata layer whenever retrieval involves a known trigger such as:
- an adventure-specific stat block;
- a map/text discrepancy;
- a known corrected item;
- a gate;
- Appendix B or C;
- Otto;
- Nalkara;
- Alterdeep;
- an old D&D Beyond source capture.

### 5.5 Rules check

Consult SRD/Sage Advice when:
- the action depends on a rules interaction;
- a spell, condition, combat option, movement rule, or visibility rule matters;
- the outcome depends on RAW rather than adventure prose;
- ambiguity could materially alter the result.

Do not perform unnecessary rules lookups for obvious, settled actions.

### 5.6 Map retrieval

Resolve the active level through `MAP_INDEX.md`; do not guess map identity from memory or a filename pattern.

Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, stairs, shafts, vertical links, mapped gates, line-of-sight geometry, or printed scale can materially affect resolution.

Keyed room number and map area number are the same binding key. The runtime may describe that geometry, but it may not alter it for pacing, encounter design, clue protection, or convenience.

Player-facing map output must be derived from discovered topology. The presence of a player-map asset does not authorize revealing its hidden or unreached areas.

### 5.7 DM personality retrieval

Load `/Dnd solo/Runtime/DM_PERSONALITY_CORE.md` at play-session activation and keep it active as a stable behavioral layer across room and level changes. When another project chat is performing DM-facing design or evaluation, it should retrieve the same core rather than infer identity from that chat's local history.

Do not load `DM_PERSONALITY_DEVELOPMENT.md` during ordinary play unless the task is explicitly personality design, testing, regression analysis, or promotion of a personality change.

Local conversation and persistent player-model state may add table history or situational nuance, but they must not silently replace the canonical identity.

---

## 6. Runtime State Model

The runtime model uses the following persistent domains. Some are already specified behaviorally but still require concrete serialization/save implementation.

### 6.1 Campaign State

Tracks persistent changes to the adventure world.

Examples:
- defeated creatures;
- surviving creatures;
- opened or destroyed doors;
- disabled traps;
- looted treasure;
- altered terrain;
- faction losses;
- NPC deaths;
- promises;
- discovered gates;
- cleared rooms;
- abandoned equipment;
- temporary effects that persist between scenes.

### 6.2 Player State

Tracks the player's mechanically relevant character state.

Examples:
- character identity;
- level;
- class;
- species;
- ability scores;
- HP and maximum HP;
- hit dice;
- spell slots;
- prepared/known spells;
- conditions;
- exhaustion;
- inspiration;
- inventory;
- currency;
- attunement;
- consumables;
- active effects;
- companions.

### 6.3 Knowledge State

Tracks what the player character has actually learned.

Examples:
- discovered room names;
- revealed map connections;
- identified monsters;
- known NPC names;
- known faction information;
- rumors;
- confirmed facts;
- discovered secret doors;
- identified magic items;
- known gate destinations.

Rumors and facts should be distinguishable.

### 6.4 Spatial State

Tracks:
- current level;
- current room;
- exact subarea when relevant;
- known exits;
- discovered secret passages;
- vertical connections;
- known gates;
- current marching/positioning information when relevant.

### 6.5 Time State

Tracks:
- campaign date when relevant;
- current in-world time;
- dungeon elapsed time;
- rest durations;
- spell durations;
- light-source durations;
- faction/event clocks;
- time spent searching;
- travel time.

Dungeon exploration should operate on meaningful elapsed time rather than treating rooms as disconnected scenes.

### 6.6 Encounter State

Created when combat or another tightly structured encounter begins.

Tracks:
- combatants;
- initiative;
- HP;
- conditions;
- concentration;
- positions/ranges;
- cover;
- reactions;
- movement;
- persistent environmental effects;
- round number;
- temporary monster resources.

Encounter state should be discarded or compacted when the encounter ends.

### 6.7 NPC State

Named or individually characterized NPC records should track enough information for motives to produce action:
- stable identity / ID;
- source and current location;
- status;
- motive;
- immediate goal;
- plan if unopposed;
- fears or constraints;
- known information;
- beliefs, including mistaken beliefs;
- faction;
- relationships;
- attitude toward the player;
- promises and debts;
- injuries or conditions;
- resources and leverage;
- next intended action;
- last meaningful event.

Faction membership supplies defaults only when the source gives no more specific individual motive. Multiple wills sharing one creature or object may require separate motive records.

### 6.8 Faction State

Tracks major organized groups.

Possible fields:
- leadership;
- goals;
- territory;
- personnel;
- current losses;
- alliances;
- enemies;
- knowledge of the player;
- current plans;
- recent events.

### 6.9 Level Story State

Tracks the causal state of the current and previously altered levels. Typical fields include:
- current escalation state;
- initial equilibrium overrides;
- surviving active actors;
- actor next-actions;
- triggered reaction rules;
- unresolved pressure points;
- faction/control changes;
- delayed source-supported consequences;
- meaningful outcome state;
- cross-level effects.

Level story state is event-driven. It must not advance merely because the player cleared rooms.

### 6.10 Halaster State

The campaign behavior layer maintains persistent Halaster state, including:
- current preoccupation;
- attention;
- regard;
- apprentice interest;
- possessiveness;
- player model;
- surprises;
- favors;
- grievances;
- observed events;
- interventions;
- direct and indirect contact history;
- finale callback context.

This state is distinct from ordinary NPC state because it spans the entire campaign and drives the Level 23 payoff.

---

## 7. Dungeon Simulation

Undermountain should continue to exist outside the player's immediate field of view.

Possible state changes include:
- patrol movement;
- faction responses;
- reinforcements;
- predators moving into cleared territory;
- NPC relocation;
- rival adventurers advancing;
- corpses being discovered;
- abandoned treasure being taken;
- defenses being rebuilt;
- information spreading.

Simulation must be based on plausible cause and state.

For levels with a story-engine layer, background motion must be derived from that level's `Active Motion`, surviving actor motives, elapsed time, means, and published aftermath/reaction rules. Do not invent a scheduled escalation merely because it would be dramatic.

It must not be used to punish the player or manufacture drama.

---

## 8. Map and Exploration Model

The project now has a deterministic map source layer.

### 8.1 DM topology

The canonical DM map for the active level, resolved through `MAP_INDEX.md`, supplies complete original geometry. It governs room placement, boundaries, adjacency, doors, corridors, secret passages, stairs, shafts, vertical relationships, mapped gates, and the printed map scale.

A keyed adventure area number binds to the identically numbered area on that DM map. There is no improvisational geometry.

### 8.2 Player topology

Player topology is a derived subset containing only geometry legitimately discovered during play. Current spatial/knowledge state controls reveal.

Player-map images are presentation assets only. If an underlying image contains a secret room, hidden passage, or unreached route, that information remains unavailable to the player until discovered.

### 8.3 Division of authority

- **DM map:** spatial geometry.
- **Keyed room text:** contents, creatures, traps, furnishings, environmental rules, and scripted conditions.
- **Current campaign/spatial state:** changes produced by play.

The runtime must never use prose improvisation to create a missing route or adjust a map for narrative convenience.

### 8.4 Map/text conflicts

If map and keyed text appear inconsistent:
1. consult adventure-specific errata/corrections;
2. use an explicit current official clarification when available;
3. otherwise preserve the mismatch as unresolved.

Do not invent a correction. Level 1 Area 6e is the model case for an unresolved mapped label with no keyed encounter text.

### 8.5 Physical changes

When rules-supported play changes geometry, record that change in spatial/campaign state. The canonical DM map remains the immutable source baseline; current state becomes authoritative for the altered feature.

---

## 9. Runtime Interaction Modes

The initial planned commands are:

### PLAY
Default immersive Dungeon Master mode.

### STATUS
Show current mechanically known player state.

### JOURNAL
Show information known to the player character.

### MAP
Show or summarize explored topology only.

### SOURCE CHECK
Step outside the fiction and inspect the published adventure source or rules source relevant to the current situation.

### SAVE
Force a persistent state snapshot.

### STATE CHECK
Inspect the runtime's current understanding of campaign state without advancing time.

### REWIND
Development/testing command. Restore a prior accepted save state when such snapshots exist.

These commands are runtime utilities, not in-world actions.

---

## 10. Session Loop

At the beginning of a play session:

1. Load `DM_PERSONALITY_CORE.md` as the canonical DM identity.
2. Load the most recent accepted save state.
3. Identify current level, keyed area, and immediate situation.
4. Load the active level story layer and resolve its canonical DM map through `MAP_INDEX.md`.
5. Load current NPC/faction/Halaster/spatial/knowledge/player-model/character-pattern overrides.
6. Retrieve the smallest relevant keyed adventure source.
7. Retrieve correction/rules data only when needed.
8. Load the recent rhythm window from tagged ledger events.
9. Assemble the initial `dm_context` packet under `DM_PERSONALITY_BACKEND_CONTRACT.md`.
10. Present the perceivable situation through the canonical DM personality while preserving NPC-specific voice, discovered geometry, and reveal boundaries.
11. Wait for player input.

During play:

1. Accept the player's declared action and preserve exact intent.
2. Resolve current geometry, room facts, actors, level-story state, rules, knowledge boundaries, stakes, affordances, and relevant campaign threads.
3. Assemble/update the bounded `dm_context` packet.
4. Pass valid possibilities and context to `DM_PERSONALITY_CORE.md`; let the canonical personality choose emphasis/table presence without changing facts.
5. Determine whether a roll is required and resolve the action.
6. Choose NPC/world actions from motive + knowledge + means + relationships.
7. Update state and advance time where appropriate.
8. Fire applicable level/Halaster reaction rules and causal background motion.
9. Present consequences and the next decision point through the stable DM personality, keeping NPC voices distinct from her own direct table voice.
10. Tag meaningful beats for the recent-rhythm window and record them in the event ledger.

At meaningful transition points:
- compact encounter state;
- update persistent campaign and level-story state;
- update NPC/faction/Halaster state;
- update player-model and player-character pattern state when supported by evidence;
- update knowledge and revealed topology;
- update rhythm state;
- update time and location;
- record a ledger event.

---

## 11. Event Ledger

The runtime should maintain an append-only factual event ledger.

Example entries:

- `S01-E004: Entered Level 1, Area 5.`
- `S01-E005: Two grells detected before they attacked.`
- `S01-E006: East grell killed.`
- `S01-E007: West grell fled into corridor toward Area 6.`
- `S01-E008: Player spent 10 minutes searching Area 5.`

The ledger exists to reduce memory drift.

Meaningful events may additionally carry runtime tags used by the personality backend's recent-rhythm window, such as `roleplay`, `humor`, `challenge`, `creative_play`, `loot`, `halaster`, `character_development`, `combat`, or `investigation`. Tags describe what actually occurred; they do not score whether the scene was good.

Summaries may be regenerated from the ledger, but summaries should never silently rewrite the underlying events.

---

## 12. Save Contract

A valid save should eventually contain:

```text
runtime_version
campaign_id
save_id
session_number
timestamp
player_state
campaign_state
knowledge_state
spatial_state
map_state
time_state
npc_state
faction_state
level_story_state
halaster_state
player_model
character_pattern_state
rhythm_state
active_encounter
event_ledger_cursor
runtime_flags
```

Save files should be versioned independently from the runtime specification so schema migrations are possible later.

---

## 13. Runtime Integrity Rules

The runtime must:

- retrieve before inventing when source material or a canonical map should contain the answer;
- distinguish source fact from DM inference;
- distinguish RAW from official clarification;
- distinguish official clarification from optional guidance;
- distinguish current world state from original room state;
- preserve unresolved ambiguity rather than fabricating canon;
- expose uncertainty when the source is genuinely unclear;
- avoid leaking undiscovered information;
- never assume a previously defeated or altered encounter has reset;
- never improvise spatial geometry when the canonical DM map determines it;
- run named NPCs from persistent motives, knowledge, relationships, resources, and current plans;
- maintain campaign-through-line, level-story, and current-scene concerns as distinct active layers;
- load and preserve `DM_PERSONALITY_CORE.md` as the canonical DM identity instead of reconstructing personality per chat, level, or scene;
- keep the DM's own table voice distinct from NPC voices and use direct DM presence selectively rather than as constant commentary;
- keep personality subordinate to authoritative facts and state: it may choose among valid approaches but cannot alter maps, source facts, rules, established motives, or hidden-information boundaries;
- never treat a player action as invalid merely because the module expected a different approach;
- preserve campaign-through-line concerns without forcing them into every local scene;
- preserve each level's own active story and NPC motives while that level is in play;
- choose consequential NPC actions from motive + knowledge + means + relationships rather than generic faction stereotypes;
- keep DM map knowledge separate from player-revealed topology;
- assemble personality context from truth/state rather than asking the personality to reconstruct missing facts;
- keep player table-model state separate from player-character in-fiction state;
- provide recent-rhythm evidence without letting the backend choose personality appetite priorities;
- never create a world fact, NPC motive, danger, reward, callback, Halaster beat, or environmental affordance merely to satisfy a personality appetite.

---

## 14. Versioning

D&D Solo uses semantic versioning for the runtime specification:

`MAJOR.MINOR.PATCH`

### MAJOR
Breaking changes to the runtime model, authority hierarchy, save schema, or fundamental DM behavior.

### MINOR
New runtime systems or substantial new capabilities that remain compatible with existing campaign state.

Examples:
- faction engine;
- automated time engine;
- map-state system;
- encounter state schema.

### PATCH
Corrections, wording improvements, additional retrieval triggers, documentation fixes, or narrow behavior corrections.

The **Document Version** increments every time this file is edited, including PATCH-level edits.

Example:

- Runtime `0.1.0`, Document Version `1`
- Runtime `0.1.1`, Document Version `2`
- Runtime `0.2.0`, Document Version `3`

---

## 15. Development Status

### Implemented as persistent project/source/runtime specification

- Persistent Mad Mage source archive.
- Structural adventure index.
- SRD 5.1 persistent rules corpus.
- Mad Mage-focused Sage Advice packet.
- Adventure-specific errata and official clarification layer.
- Source/authority and retrieval architecture.
- Halaster operational DM behavior layer.
- Reverse-designed Halaster campaign through-line layer.
- Level story-engine contract with NPC accountability.
- Story-engine layers for all 23 numbered Undermountain levels.
- Source-supported reaction rules, escalation states, outcome states, actor networks, and cross-level continuity in those level layers.
- Canonical DM/player map pairs for all 23 numbered levels.
- Three canonical Skullport DM/player map pairs.
- `MAP_INDEX.md` deterministic level → story layer → DM map → player map → keyed-room binding.
- Per-level geometry bindings embedded directly in all 23 numbered level files.
- Fixed-geometry contract prohibiting improvised rooms, connections, distances, scale, or map repair.
- DM personality backend contract mapping every alpha appetite to required runtime inputs.
- Canonical project-wide DM identity in `DM_PERSONALITY_CORE.md`.
- Personality workshop, test, regression, promotion, and compression pipeline in `DM_PERSONALITY_DEVELOPMENT.md`.
- Bounded `dm_context` packet specification separating backend truth/state from personality emphasis.
- Separate player-model and player-character-pattern streams.
- Recent-rhythm tagging model to support appetite hunger without forcing the backend to choose appetite priorities.

### Specified behavior, awaiting concrete persistence/runtime serialization

- structured player state;
- structured campaign state;
- knowledge ledger;
- persistent spatial state and revealed-topology graph;
- dungeon clock;
- encounter state;
- persistent NPC and faction records;
- persistent level-story state;
- persistent Halaster state;
- persistent player table-model state;
- persistent player-character pattern state;
- recent-rhythm state derived from event-ledger tags;
- event ledger;
- save snapshots;
- MAP reveal/render pipeline;
- runtime commands;
- state migration.

### Support layers requiring later story-engine parity review

- `LEVEL_00_GAME_SETUP.md`;
- `HUB_SKULLPORT.md` for story-engine depth only. Skullport geometry is now bound to its three canonical maps.

---

## 16. Changelog

### 0.3.1 — Canonical project-wide DM identity
**Date:** 2026-09-23  
**Document Version:** 4

Added:
- `DM_PERSONALITY_CORE.md` as the canonical project-wide answer to who the Dungeon Master is;
- explicit runtime/session retrieval of that core so DM identity remains consistent across project chats, rooms, levels, and play sessions;
- `DM_PERSONALITY_DEVELOPMENT.md` as a separate workshop and QA layer for personality iteration rather than live runtime instruction;
- a development pipeline of workshop -> distill -> test -> diagnose -> regression -> promote -> compress;
- explicit separation between personality and factual authority: personality governs taste, emphasis, humor, pacing preference, and table presence but cannot rewrite maps, source facts, rules, actor motives, knowledge boundaries, or state;
- explicit separation between the DM's own table voice and NPC voices.

This patch replaces the temporary dependency on the UX design chat/file as the personality source. The live identity is now a dedicated runtime artifact accessible from any project chat.

### 0.3.0 — Personality/backend context interface
**Date:** 2026-09-23  
**Document Version:** 3

Added:
- `DM_PERSONALITY_BACKEND_CONTRACT.md`;
- per-turn bounded `dm_context` packet;
- explicit backend/personality authority boundary;
- appetite-by-appetite backend support requirements;
- full NPC communication/motive payload for personality use;
- character-development evidence stream;
- separate player and player-character models;
- stakes/perceivable-evidence split;
- recent-rhythm tags and history window for appetite hunger;
- context-trimming and backend failure tests;
- session-loop integration so personality receives assembled state rather than reconstructing it from raw source.

### 0.2.0 — DM behavior, level story engines, and fixed geometry
**Date:** 2026-09-23  
**Document Version:** 2

Major additions:
- established campaign-through-line, level-story, and current-scene attention as distinct DM concerns;
- added `HALASTER_DM_LAYER.md`;
- added `HALASTER_THROUGH_LINE_LAYER.md`;
- added `LEVEL_LAYER_CONTRACT.md`;
- rebuilt Levels 1–23 as living story engines rather than chapter summaries;
- made each level accountable for named and individually characterized NPC motives;
- added equilibrium, active motion, player variables, pressure points, reaction rules, escalation states, outcome states, player-facing evidence, actor networks, and cross-level continuity;
- added causal background ticks constrained by motive, knowledge, means, access, elapsed time, and source-supported aftermath;
- integrated canonical DM/player map pairs for all 23 levels plus Skullport;
- added `MAP_INDEX.md` as a deterministic geometry registry;
- bound every numbered level file directly to its canonical DM/player map pair and keyed-area range;
- established a zero-improvisation geometry rule: mapped rooms, doors, passages, stairs, shafts, gates, distances, adjacency, and scale cannot be altered for convenience or narrative effect;
- made authority domain-specific for world facts, spatial geometry, DM behavior, and rules.

Quality corrections:
- Wyllowwood QA exposed that the first level-layer pass was too summary-like; all 23 numbered levels were rebuilt to encode causal story motion and source-supported outcome states.
- the map layer moved from a future concept to an actual canonical source layer after DM/player map assets were added and indexed.

### 0.1.0 — Runtime bootstrap
**Date:** 2026-09-23  
**Document Version:** 1

Established the first formal runtime specification.

Added:
- project purpose;
- initial player-agency rules;
- source hierarchy;
- retrieval protocol;
- state architecture;
- dungeon simulation model;
- session loop;
- proposed runtime commands;
- event ledger specification;
- save contract;
- semantic versioning policy.

Existing persistent source layers recognized:
- indexed *Dungeon of the Mad Mage* source;
- SRD 5.1;
- Mad Mage Sage Advice packet;
- Mad Mage errata and official clarification packet.

---

## 17. Next Runtime Milestone

Target: **D&D Solo Runtime 0.4.0**

Primary work:
1. Define concrete save-state schemas, including `level_story_state`, `halaster_state`, stable NPC/faction records, spatial state, `player_model`, `character_pattern_state`, and `rhythm_state`.
2. Persist a player reveal graph derived from immutable DM topology.
3. Create the first player-character and campaign state files.
4. Create the append-only tagged event ledger and derive the recent-rhythm window from it.
5. Define exact SAVE / LOAD behavior and state migration boundaries.
6. Implement `dm_context` assembly from source + state with relevance trimming.
7. Implement background ticks from each level's Active Motion and reaction rules.
8. Bring `LEVEL_00_GAME_SETUP.md` and Skullport's story engine to the same QA depth as Levels 1–23.
9. Run end-to-end personality/backend playtests across exploration, social, combat, investigation, loot, shenanigans, failure, and Halaster beats.