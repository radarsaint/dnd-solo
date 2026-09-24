# Level 13 — Trobriand’s Graveyard — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 13: Trobriand’s Graveyard  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-13.01-trobriands-graveyard-dm.png`  
**Player presentation map:** `assets/maps/levels/map-13.01-trobriands-graveyard-player.jpg`  
**Keyed source areas:** 1–12  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

Trobriand's workshop, proving ground, and junkyard continues operating largely without him. Autonomous constructs, a control ring, scavenging hobgoblins, and the bore worm turn abandoned industry into an ecosystem.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Who controls Trobriand's autonomous industrial ecosystem: Zox with his control ring and Simulacrux project, Doomcrown's scavengers, or the constructs themselves?

### Initial Equilibrium

Trobriand is usually absent. Scaladar operate autonomously unless controlled by a ring. Zox has such a ring and is using the constructs to build the experimental Simulacrux. Hobgoblin raiders from Level 14 repeatedly steal scrap for the fire giants and now know the ring is the key to killing or controlling Zox's operation. The Bore Worm continues its programmed route regardless of politics.

### Active Motion

- Zox works toward completing the Simulacrux and uses controlled scaladar for protection/construction.
- Hobgoblin raiders return for scrap and try to kill Zox/take his ring.
- The Bore Worm continually traverses established routes and attacks obstructions, sometimes crossing into Levels 12 or 14.
- Uncontrolled scaladar follow their autonomous behavior; the myconid sovereign can eventually regrow the scorched fungal area if it survives.

### Player Variable

The player can protect/betray Zox, take or transfer the control ring, help/stop hobgoblin salvage, destroy constructs, alter the Simulacrux project, or follow the industrial links down to Arcturiadoom.

### Pressure Points

- Scaladar territory/control ring — determines whether constructs are environmental enemies or commanded resources.
- Zox's palace/worksite — motive center for the Simulacrux project.
- Area 11 — hobgoblin base camp: connection to Level 14's supply chain.
- Bore Worm routes — moving hazard whose position can matter across levels.
- Area 12 — myconid/fungus recovery branch.

### Reaction Rules

- IF Zox retains the ring and survives, THEN his construction project continues over months unless the player materially changes it.
- IF hobgoblins are defeated locally, THEN raids stop for roughly a tenday; after that Doomcrown sends more unless Level 14's command/supply structure has been broken.
- IF control of the ring changes, THEN immediately reevaluate which scaladar obey whom rather than treating ownership as ordinary treasure state.
- IF the Bore Worm is not destroyed, THEN keep it as a mobile level-crossing hazard; do not respawn it in a default room.
- IF the myconid sovereign survives, THEN fungal recovery is slow (years), not an instant scene reset.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- ACTIVE JUNKYARD — Zox, constructs, raiders, and Bore Worm all operating.
- CONTROL CONTEST — ring/Zox is under direct threat or has changed hands.
- SUPPLY LINE BROKEN / SECURED — Level 14 raiders either lose or retain access to scrap.
- LONG PROJECT — surviving Zox/Simulacrux or myconids continue changing the level over long time scales.

### Outcome States

- Zox remains and eventually completes or rebuilds the Simulacrux experiment.
- Hobgoblin raids continue until Doomcrown's Level 14 operation is stopped.
- Construct control fractures if the ring leaves Zox or is lost.
- Fungus slowly returns if the myconid sovereign survives.

### Player-Facing Evidence

- Fresh scrap removal and rust-monster tactics reveal organized raiding from below.
- The Bore Worm is heard before seen, establishing an industrial system that moves independently of rooms.
- Scaladar behavior visibly changes around the control ring.
- Zox's massive construction project makes his motive materially present.

## Actor Network

- Zox -> scaladar: controller/builder when ring remains in hand.
- Hobgoblins -> Zox: want him dead primarily to obtain the ring and scrap access.
- Hobgoblins -> Level 14 giants: supply chain.
- Trobriand -> whole level: absent designer whose machines continue functioning without supervision.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Zox Clammersham

**Motive:** Survive among the constructs and retain/control the ring that gives leverage over them.  
**Plan if unopposed:** Use knowledge and the control ring to preserve himself and his position.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Kurlog

**Motive:** Acquire scrap and useful construct technology for the hobgoblin/fire-giant interests below.  
**Plan if unopposed:** Raid opportunistically while avoiding destruction by Trobriand's machines.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Trobriand

**Motive:** Maintain his construct legacy and experiments, even though he normally remains near Halaster on Level 23.  
**Plan if unopposed:** His creations continue following their programmed or autonomous behavior; direct presence is exceptional.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Scaladar territory — autonomous workshop guardians.
- Bore Worm routes — moving industrial hazard that crosses level boundaries.
- Zox's position/control ring — social/mechanical leverage point.
- Hobgoblin base — connection to Arcturiadoom.

## Level State That Must Persist

- Zox/control ring status
- Scaladar control
- Bore Worm state/location
- hobgoblin salvage success
- damage to Trobriand's works

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Hobgoblin raiders answer to Doomcrown on Level 14.
- Bore Worm can cross into Levels 12 and 14.
- Trobriand himself is a Level 23 payoff actor; damage to his work can become a later callback.

## Halaster Through-Line

Revelation through an apprentice's legacy. Avoid a Halaster cameo unless another established condition demands one.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Control of constructs and salvage routes can materially affect Level 14 and later Trobriand callbacks.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.13`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/13-001.trobriands-graveyard.png`

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