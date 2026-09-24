# Level 12 — Maze Level — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 12: Maze Level  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-12.01-maze-level-dm.jpg`  
**Player presentation map:** `assets/maps/levels/map-12.01-maze-level-player.jpg`  
**Keyed source areas:** 1–19  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

House Freth seeks to convert a stalemated war with minotaurs into conquest by faking divine authority. The key tension is Drivvin's plan to pass a controlled goristro off as Baphomet.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Does Drivvin successfully turn religious fraud into House Freth's military victory, or does the player break the deception before a goristro and the minotaurs are weaponized against the levels above?

### Initial Equilibrium

Freth and the minotaurs are in a battered truce. Erelal wants minotaur submission so she can use them to secure Level 11. Drivvin plans to fake an appearance of Baphomet with a controlled goristro but knows his ritual is inadequate. Shadowdusk emissaries secretly press him to accept Halaster's apprenticeship in exchange for the missing magical solution. Maku continues trying to attract Baphomet through sacrifice.

### Active Motion

- Erelal pressures Drivvin while cultivating the Shadowdusk visitors and watching Auvryndar.
- Tendra Nightblade and Maleen Shadowdusk quietly steer Drivvin toward Halaster's offer rather than a genuine Shadowdusk/Freth alliance.
- Drivvin searches for a way to complete the ritual without exposing his inadequacy.
- Maku and the minotaurs maintain devotion to Baphomet and accumulate evidence/sacrifices they believe can produce divine contact.

### Player Variable

The player can expose the fake-alliance/apprenticeship offer, kill or aid Drivvin, influence Erelal, exploit Maku's belief, destroy Freth leadership, or let enough time pass for Halaster's promised solution to mature.

### Pressure Points

- Areas 7–8 — minotaur caves/shrine: faith and the carrion site the future goristro plan exploits.
- Areas 18–19 — Spiderwatch Keep: Freth command center, emissaries, and ritual politics.
- Drivvin interactions — whether he accepts Halaster's apprenticeship is a campaign-level pressure point.
- Any scene revealing prior Auvryndar collaboration — changes Freth's initial willingness to bargain.

### Reaction Rules

- IF Drivvin survives unresolved and accepts Halaster's offer, THEN after 30 days Halaster helps bind the goristro; Drivvin releases it at the minotaur shrine and uses their belief to redirect them toward Level 11.
- IF Erelal survives, THEN the later birth of Amalica increases perceived Lolth favor and attracts houses formerly aligned with Auvryndar, as the aftermath specifies.
- IF Erelal and Drivvin both die, THEN Freth allies desert and the weakened house retreats into the fortress while seeking reinforcements.
- IF Vlonwelv remains powerful on Level 10 while Freth leadership collapses, THEN her side can exploit the opening before distant reinforcements arrive.
- IF the player reveals the planned Baphomet deception to minotaurs who can understand/believe it, THEN update their willingness to obey Freth rather than automatically following the future goristro.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- ARMED TRUCE — Freth/minotaurs exhausted, ritual scheme incomplete.
- APPRENTICESHIP DECISION — Drivvin's dependence on Halaster becomes explicit or is severed.
- GORISTRO COUP / FRETH COLLAPSE — the deception succeeds or leadership is broken.
- REGIONAL OFFENSIVE — minotaurs/Freth move toward Level 11 or Auvryndar exploits the collapse.

### Outcome States

- Freth gains minotaur shock troops through the fake-Baphomet goristro.
- Freth survives under Erelal with growing political support even without the goristro resolution.
- Freth collapses into a besieged remnant after both leaders die.
- Minotaurs remain independent if Freth cannot make the religious deception credible.

### Player-Facing Evidence

- An exhausted front with a suspicious pause in open fighting.
- Freth court behavior toward Shadowdusk 'emissaries' looks unusually flattering and cautious.
- Drivvin's ritual preparations coexist with signs he lacks a crucial solution.
- Maku's corpse-gathering and Baphomet devotion make the future deception legible before it occurs.

## Actor Network

- Erelal -> Drivvin: political pressure and sibling authority.
- Drivvin -> minotaurs: intends to control them through religious fraud.
- Shadowdusk emissaries/Halaster -> Drivvin: apprenticeship offer in exchange for solving the ritual.
- Maku/minotaurs -> Baphomet: sincere devotion that makes them exploitable.
- Freth <-> Auvryndar: wider drow war extending into Levels 10–11.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Erelal Freth

**Motive:** Secure House Freth's dominance, subjugate the minotaurs, and use them to expand into the Troglodyte Warrens.  
**Plan if unopposed:** Pressure Drivvin to produce the ritual and turn religious obedience into military control.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Drivvin Freth

**Motive:** Complete the goristro deception and prove his value to Erelal while hiding that his ritual knowledge is inadequate.  
**Plan if unopposed:** Seek missing knowledge or outside help without admitting weakness.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Minotaur leadership

**Motive:** Preserve the tribe after heavy losses and interpret signs through their devotion to Baphomet.  
**Plan if unopposed:** Resist Freth unless convinced that divine authority demands submission.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Maku

**Motive:** Win Baphomet's favor and preserve the minotaurs through sincere devotion to the Horned King.  
**Plan if unopposed:** Continue gathering sacrifice/carrion and interpreting events through Baphomet worship, making the tribe vulnerable to Drivvin's planned deception.  
**Runtime:** Track what Maku believes about any apparent divine sign; belief, not factual truth, drives his decisions.

### Tendra Nightblade and Maleen Shadowdusk

**Motive:** Fulfill Halaster's order by steering Drivvin into accepting apprenticeship while disguising the mission as alliance diplomacy.  
**Plan if unopposed:** Maintain Erelal's hospitality, privately press Drivvin toward Halaster's offer, and avoid exposing Shadowdusk's lack of genuine alliance interest.  
**Runtime:** Track separately if one dies/defects; their secret objective overrides the public diplomatic role.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Maze hazards — environment controlled by magical effects and traps.
- Spiderwatch Keep — Freth command center.
- Drivvin's ritual preparations — deception engine for the level.
- Minotaur territory/shrine — belief is politically actionable.

## Level State That Must Persist

- Freth/minotaur ceasefire or war
- Drivvin ritual progress
- Goristro summoned/control status
- Freth leadership survival
- minotaur allegiance

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Drivvin can become a Halaster apprentice if left alive/unresolved.
- Tendra/Maleen connect the level to Shadowdusk Hold (Level 22).
- Outcome directly changes the war on Level 11 and relative strength against Level 10 Auvryndar.

## Halaster Through-Line

Potential apprentice pipeline. Drivvin becomes relevant to later Halaster decisions if his capability and survival warrant it.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Record whether House Freth gains minotaur forces and whether Drivvin emerges stronger, exposed, dead, or available for Halaster's later use.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.12`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/12-001.maze-level.png`

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