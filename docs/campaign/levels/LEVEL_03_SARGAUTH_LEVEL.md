# Level 3 — Sargauth Level — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 3: Sargauth Level  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-03.01-sargauth-level-dm.png`  
**Player presentation map:** `assets/maps/levels/map-03.01-sargauth-level-player.jpg`  
**Keyed source areas:** 1–23  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

Stromkuhldur is on the edge of war. House Auvryndar presses into the Legion of Azrok while Xanathar and Halaster benefit from escalation. The level is also the gateway to Skullport.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Which power survives the crisis in Stromkuhldur, and does the player expose, repair, or exploit the hidden weakness that made the crisis possible?

### Initial Equilibrium

House Auvryndar has seized eastern Stromkuhldur after Azrok lost the dagger that concealed his blindness. Lurkana is trying to recover it and preserve his legitimacy. Ulquess and Xanathar agents are covertly worsening morale from inside Azrok's court. Halaster and Xanathar both benefit from the drow/goblinoid conflict continuing.

### Active Motion

- Auvryndar consolidates its gains and looks for the next opening.
- Lurkana searches for capable outsiders to retrieve the dagger; Azrok tries to preserve command despite vulnerability.
- Ulquess's intellect-devourer network continues spreading knowledge of Azrok's blindness and weakening confidence.
- The sea-hag faction remains hostile to the drow and can become part of the anti-Auvryndar balance.
- Skullport remains an external source of Xanathar pressure and deserters.

### Player Variable

The player can return Azrok's dagger, expose or aid the infiltration, destroy either major faction, enter Skullport, or turn one faction's fear of the other into leverage.

### Pressure Points

- House Auvryndar territory / Area 20 — source of the territorial offensive and spider-incubator horror.
- Area 21 — Azrok's Hold: political center, blindness secret, Lurkana's side quest, and Xanathar infiltration.
- Area 21 random encounter — Halaster scrying eye when the through-line trigger is satisfied.
- River Sargauth and Area 23 — routes into Skullport and outside influence.
- Retrieve Azrok's Dagger — cross-level pressure point whose physical payoff lies on Level 6.

### Reaction Rules

- IF the dagger returns to Azrok, THEN his practical ability to perceive and his symbolic authority recover; update troop confidence and the leverage enemies gained from his blindness.
- IF the player publicly exposes the blindness before the dagger is restored, THEN increase internal political instability only among actors who learn and care about it.
- IF Auvryndar is defeated while Azrok's legion survives, THEN the legion reclaims and fortifies areas 18–20.
- IF Azrok's legion is destroyed while Auvryndar survives, THEN the drow secure the rest of Stromkuhldur.
- IF both are destroyed, THEN Skullport explorers begin treating the ruins as open territory.
- IF Azrok's network remains penetrated long enough for Xanathar's plan to mature, THEN the aftermath allows the guild to convert the legion into a bulwark against the drow. Do not jump to this result without elapsed time and surviving infiltrators.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- CRISIS — drow gains, Azrok weakness, and covert Xanathar pressure coexist.
- LEGION RECOVERY — Azrok/Lurkana regain capability and territory.
- AUVRYNDAR ASCENDANT — the legion collapses and drow control expands.
- XANATHAR CAPTURE / OPEN RUINS — either covert guild control matures or both local powers are removed.

### Outcome States

- Azrok holds and fortifies more of Stromkuhldur.
- Auvryndar controls Stromkuhldur.
- Xanathar subverts the surviving legion over time.
- Both major factions fall and Skullport explorers fill the vacuum.

### Player-Facing Evidence

- Rumors and visible hesitation around Azrok despite his old reputation.
- Drow occupation of previously goblinoid ruins and spider experimentation.
- Goblins quietly repeating damaging information they should not all independently know.
- Deserters and traffic toward Skullport showing external pressure.

## Actor Network

- Auvryndar -> Azrok: territorial predator exploiting visible weakness.
- Lurkana -> Azrok: protector, captain, and keeper of his secret.
- Ulquess/Xanathar -> Azrok: covert destabilization before eventual capture.
- Halaster/sea hags -> Auvryndar: separate pressure encouraging conflict rather than stable rule.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### T’rissa Auvryndar

**Motive:** Expand House Auvryndar's control of Stromkuhldur and advance Lolth's interests, including her spider-incubator experiments.  
**Plan if unopposed:** Pressure Azrok's territory and exploit weakness.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Azrok

**Motive:** Preserve his rule, legion, and reputation despite losing the dagger that allowed him to conceal his blindness.  
**Plan if unopposed:** Hold western Stromkuhldur and prevent enemies from discovering how vulnerable he is.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Lurkana

**Motive:** Protect Azrok, preserve the legion, and recover the dagger of blindsight.  
**Plan if unopposed:** Recruit capable outsiders discreetly and contain the truth of Azrok's blindness.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Ulquess

**Motive:** Advance Xanathar's influence by weakening Azrok from inside his court.  
**Plan if unopposed:** Use intellect devourers and information warfare to undermine the legion.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- House Auvryndar territory — spider hatchery and territorial aggression.
- Area 21: Azrok's Hold — political center of the level.
- Retrieve Azrok's Dagger side quest — cross-level consequence reaching Level 6.
- River Sargauth / routes to Skullport — transition from dungeon to settlement.
- Area 21 random scrying eye — deliberate Halaster observation milestone when triggered.

## Level State That Must Persist

- Auvryndar vs Azrok territorial balance
- Azrok dagger/secret status
- Xanathar infiltration of Azrok's court
- Sea hag disposition
- Skullport routes discovered
- Halaster deliberate-observation state

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Azrok's dagger is with Skella Ironeye on Level 6.
- Azrok's son Doomcrown appears on Level 14.
- Skullport is directly connected and can alter the local balance.
- House Auvryndar continues through Levels 4 and 10; Xanathar pressure continues through Skullport.

## Halaster Through-Line

The player can become specifically worth checking on if they alter the faction war. Use the source-supported eye; keep it silent.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Whichever major faction survives expands. Xanathar continues infiltrating Azrok if the legion remains. A power vacuum invites Skullport explorers if both sides fall.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.03`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/03-001.sargauth-level.png`

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