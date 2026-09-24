# Level 4 — Twisted Caverns — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 4: Twisted Caverns  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-04.01-twisted-caverns-dm.png`  
**Player presentation map:** `assets/maps/levels/map-04.01-twisted-caverns-player.jpg`  
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

An ecological and political struggle centered on Illuun the aboleth, displaced kuo-toa, poisoned waters, and House Auvryndar waiting to exploit the winner.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Does Illuun convert the entire cavern ecosystem into a slave domain, do the displaced kuo-toa reclaim it, or does House Auvryndar inherit the winner's territory?

### Initial Equilibrium

Illuun controls the lake and has displaced the kuo-toa, whose food supply is collapsing because the aboleth has tainted the water. Noolgaloop is trying to create a new god capable of defeating Illuun. House Auvryndar deliberately waits for the struggle to weaken one side before intervening.

### Active Motion

- Illuun sends servants to capture new slaves and extends contamination from the lake.
- Noolgaloop continues constructing and investing faith in the improvised god while the kuo-toa try to survive.
- Auvryndar avoids committing heavily until it can exploit a weakened winner.
- Other Underdark inhabitants adapt to the shrinking safe ecosystem.

### Player Variable

The player can destroy or bargain with Illuun, aid or manipulate the kuo-toa's religious project, weaken Auvryndar, or change access to the lake and river.

### Pressure Points

- Areas 16+ — lake/grotto: Illuun's center of control and the poisoned ecosystem.
- Areas 20–21 — kuo-toa refuge and Noolgaloop's response to displacement.
- Areas 11–12 — Auvryndar outpost waiting on the conflict.
- Area 16a — Bulba-Slopp: a separate Halaster-created belief experiment that reveals how he seeds bizarre social systems.

### Reaction Rules

- IF Illuun dies and enough kuo-toa survive, THEN they reclaim the grotto; afterward Auvryndar begins attacking them when time and forces permit.
- IF Illuun survives without effective opposition, THEN it progressively enslaves/kills the remaining kuo-toa and expands its thrall network.
- IF Illuun remains dominant long enough, THEN its slime destroys the fungi and the level's food ecology as described by the aftermath.
- IF the drow inherit the grotto, THEN they enslave surviving troglodytes and convert useful areas to their own production.
- IF the player becomes valuable to Noolgaloop or Illuun, THEN roleplay that relationship through the actor's actual objective rather than generic gratitude.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- DISPLACEMENT — Illuun ascendant, kuo-toa refugees, drow waiting.
- DECISION — the player has materially altered one side's ability to survive.
- SUCCESSION — Illuun or kuo-toa control the lake and Auvryndar chooses whether to attack.
- ECOLOGICAL TRANSFORMATION — enslavement, drow occupation, or ecosystem collapse becomes the new normal.

### Outcome States

- Kuo-toa reclaim the lake briefly before renewed drow pressure.
- Illuun dominates and the ecosystem degrades under aboleth slime.
- Auvryndar eventually seizes the weakened grotto.
- A more unstable mixed state persists if all major powers survive but are damaged.

### Player-Facing Evidence

- Dead fish and declining food before the player ever meets Illuun.
- Displaced kuo-toa building a desperate god from scavenged material.
- Enslaved troglodytes and servants moving between the lake and outer caverns.
- Drow behaving like observers and opportunists rather than primary attackers.

## Actor Network

- Illuun -> kuo-toa: displacement, starvation, enslavement.
- Noolgaloop -> Illuun: religiously mediated counterattack.
- Auvryndar -> both: wait for attrition, then seize the result.
- Illuun -> ecosystem: domination damages the resource base everyone depends on.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Illuun

**Motive:** Dominate the level, expand its slave network, and ultimately extend control toward Undermountain and Waterdeep.  
**Plan if unopposed:** Use chuuls and enslaved creatures to capture more subjects while remaining protected in its lake.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Darribeth Meltimer

**Motive:** Survive the caverns and find a way out of her isolated predicament.  
**Plan if unopposed:** Seek useful allies while managing her own instability.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Melith Auvryndar

**Motive:** Preserve House Auvryndar's position and wait for the aboleth/kuo-toa struggle to create an opening.  
**Plan if unopposed:** Avoid unnecessary losses and exploit the eventual winner.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Thirza Helviiryn

**Motive:** Support the drow position and protect access to House Auvryndar's interests.  
**Plan if unopposed:** Act with the drow contingent rather than start a separate war.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Noolgaloop

**Motive:** Save the displaced kuo-toa by creating a new god powerful enough to destroy Illuun.  
**Plan if unopposed:** Continue assembling the idol and invest the tribe's hope/resources in bringing it to life.  
**Runtime:** Track what components/help the player supplies, what Noolgaloop believes about the idol's progress, and whether the kuo-toa still have a population to protect.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Area 16 and surrounding lake — Illuun's center of control.
- Kuo-toa refuge — displaced population seeking survival.
- Drow outpost — opportunists waiting on the conflict.
- Area 16a: Bulba-Slopp — Halaster-created belief experiment/revelation.

## Level State That Must Persist

- Illuun survival and slave network
- Kuo-toa population/disposition
- Water contamination
- Auvryndar posture
- Control of river routes

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Auvryndar's posture depends on surviving leadership from Levels 3 and later feeds Level 10.
- The River of the Depths continues to Wyllowwood on Level 5.
- The defective shield guardian's amulet connected to Level 1 is found in Illuun's broader area.

## Halaster Through-Line

Revelation rather than contact: show that Halaster can seed bizarre social/ecological experiments and let them develop.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Record who controls the lake and river, whether displaced populations return, and whether Auvryndar gains an opening.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.04`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/04-001.twisted-caverns.png`
- Level art: `/Dnd solo/Assets/Art/Levels/04-002.fungi-and-snails.png`

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