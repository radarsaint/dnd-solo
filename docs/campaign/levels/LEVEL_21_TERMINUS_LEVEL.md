# Level 21 — Terminus Level — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 21: Terminus Level  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-21.01-terminus-level-dm.png`  
**Player presentation map:** `assets/maps/levels/map-21.01-terminus-level-player.jpg`  
**Keyed source areas:** 1–24  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

Halaster's dumping ground for failed experiments has acquired a corrupted judge. Fazrian came to cleanse evil and became addicted to punishment, while duergar and yugoloths use his court for their own advantage.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Can the player break Fazrian's corrupted system of judgment, and who controls the Deep Mines when the fallen angel's authority is gone?

### Initial Equilibrium

Fazrian rules through lethal moral judgment after being corrupted by its own crusade against Halaster's horrors. Yugoloths flatter and exploit the fallen angel. Valtagar's exiled duergar nominally serve Fazrian while plotting to overthrow it and regain the mines. Halaster continues dumping failed monsters into the level.

### Active Motion

- Fazrian summons/judges intruders and kills those it considers selfish or unworthy.
- Valtagar seeks allies and means to remove Fazrian, while his duergar remain loyal to him rather than the planetar.
- Aximus, Exekarus, Raxxus, and Xindulus stay with the arrangement only while it serves their welfare/profit.
- Halaster's stray experiments continue appearing over time, preserving environmental instability even if local rulers change.

### Player Variable

The player can submit to/argue against Fazrian's judgment, show it that it became what it hated, ally with Valtagar, buy/recruit yugoloths, kill Fazrian, or leave the current court intact.

### Pressure Points

- Duergar patrols — deliver strangers toward Valtagar and establish his surviving command network.
- Area 15 — Valtagar's quarters: coup alliance center.
- Area 23 — Fazrian's Court: social/moral resolution can matter as much as combat.
- Regional effects — blood, roses/sulfur, unholy choir physically communicate Fazrian's corruption.
- Halaster scrying-eye pressure point from the through-line after Level 20 choices.

### Reaction Rules

- IF the player can make Fazrian recognize that it has become what it sought to destroy, THEN the source permits self-destruction/redemptive sacrifice; do not force combat if that condition is achieved.
- IF Fazrian dies, THEN duergar regain control and Valtagar fortifies while planning eventual return to Gracklstugh.
- IF Fazrian falls, THEN surviving yugoloths choose next affiliations individually: Aximus/Exekarus lean duergar, Raxxus prefers the adventurers, Xindulus may move to Shadowdusk Hold.
- IF a more profitable credible offer appears before Fazrian falls, THEN yugoloth loyalty may shift; calculate this individually rather than as one faction switch.
- IF the player returns later, THEN new failed experiments may have been dumped here by Halaster even if prior monsters were cleared.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- CORRUPT COURT — Fazrian supreme; duergar/yugoloths maneuver beneath it.
- COUP / JUDGMENT — player is entangled in Fazrian's moral test or Valtagar's overthrow plan.
- FALLEN ANGEL RESOLVED — Fazrian redeemed through self-sacrifice or killed.
- DUERGAR SUCCESSION — Valtagar fortifies; surviving outsiders redistribute.

### Outcome States

- Fazrian remains judge and the court persists.
- Fazrian dies/redeems itself; Valtagar retakes and fortifies the mines.
- Raxxus may become a mobile companion; Xindulus may enter Level 22.
- Halaster continues seeding the level with failed experiments indefinitely.

### Player-Facing Evidence

- Regional effects make the angel's corruption perceptible before meeting it.
- Duergar describe the latest monsters as Halaster's continuing dumps, proving the level is still being supplied.
- Valtagar's patrol orders to bring adventurers alive reveal that he wants tools/allies, not random corpses.
- Yugoloths visibly hedge and negotiate rather than display sincere religious loyalty.

## Actor Network

- Fazrian -> intruders: subjects for moral judgment/execution.
- Valtagar -> Fazrian: outward vassal, inward usurper.
- Duergar -> Valtagar: genuine loyalty.
- Yugoloths -> Fazrian/Valtagar/player: transactional allegiance.
- Halaster -> level: continuing source of discarded experiments, independent of local politics.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Fazrian

**Motive:** Judge and destroy those it deems unworthy, while a surviving mote of goodness makes self-recognition possible.  
**Plan if unopposed:** Hold court, demand moral accounting, and execute the condemned.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Valtagar Steelshadow

**Motive:** Preserve and strengthen duergar control while positioning himself for eventual return to Gracklstugh.  
**Plan if unopposed:** Use Fazrian's order when convenient and fortify if the planetar falls.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Aximus

**Motive:** Profit from and influence Fazrian's court while serving yugoloth self-interest.  
**Plan if unopposed:** Prefer useful alliances and survival over loyalty.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Exekarus

**Motive:** Exploit the court and preserve yugoloth advantage.  
**Plan if unopposed:** Align with power that best serves self-interest.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Raxxus

**Motive:** Survive and seek a better opportunity than remaining trapped under the local hierarchy.  
**Plan if unopposed:** May prefer accompanying capable adventurers to staying.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Xindulus

**Motive:** Secure influence and future alliances if the current order collapses.  
**Plan if unopposed:** Seek another power center, including Shadowdusk Hold, if necessary.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Failed-experiment zones — why this level exists.
- Fazrian's Court — moral/social boss scene, not only combat.
- Duergar mining/fortification areas — mundane power under supernatural rule.
- Area 20a scrying eye — silent Halaster reassessment after Ezzat choice.

## Level State That Must Persist

- Fazrian corruption/redemption/death
- duergar control
- yugoloth loyalties/movement
- failed experiments released/contained
- Halaster reassessment

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Xindulus can move into Shadowdusk Hold on Level 22.
- Halaster observation here should reflect the player's Ezzat/Runestone decision from Level 20.

## Halaster Through-Line

Silent reassessment milestone. His interest should reflect the Level 20 choice; no need to interrupt Fazrian's story.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

If Fazrian falls, Valtagar fortifies. Surviving yugoloths choose new patrons or destinations based on self-interest.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.21`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: none indexed yet

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