# Level 8 — Slitherswamp — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 8: Slitherswamp  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-08.01-slitherswamp-dm.png`  
**Player presentation map:** `assets/maps/levels/map-08.01-slitherswamp-player.jpg`  
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

A swamp war built on domination. Spirit nagas control thralls; the Blacktongue bullywugs serve a death slaad; remnants of yuan-ti history and Dweomercore agents complicate the struggle.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Which coercive regime survives Slitherswamp, and can the player break any of the control systems instead of merely replacing one tyrant with another?

### Initial Equilibrium

The Ssethian Scourges dominate thralls through a rod of rulership and want the Blacktongues removed. The Blacktongues are themselves ruled by Kuketh, a death slaad forced into kingship because Halaster holds its control gem on Level 9. Karstis observes for Dweomercore and benefits from weakened local factions. Yoastal's ghost and yuan-ti remnants complicate both sides.

### Active Motion

- The nagas reassert magical control over thralls each dawn and seek agents willing to remove Kuketh/Blacktongues.
- Kuketh vents its hatred of Halaster's control onto the bullywugs while remaining constrained by the missing control gem.
- Blacktongues defend their territory and domesticated monsters under coercive leadership.
- Karstis watches for opportunities to thin factions or claim strategic ground for Dweomercore.

### Player Variable

The player can serve or betray the nagas, free Kuketh by affecting its control gem, empower the Blacktongues, kill the rejuvenating nagas, interact with Yoastal, or give Dweomercore an opening.

### Pressure Points

- Areas 15–16 — naga domain and recurring thrall-control system.
- Areas 20–23 — Blacktongue domain and Kuketh's coerced kingship.
- Areas 7–8 — Karstis's observation post and Dweomercore pressure.
- Area 9 — yuan-ti ghost/legacy pressure.
- Kuketh's control gem — physically on Level 9, making this level's ruler dependent on a cross-level object.

### Reaction Rules

- IF Kuketh's control gem is destroyed or restored to Kuketh, THEN Kuketh abandons the bullywugs; IF Torbit survives, he can become ruler afterward.
- IF Kuketh leaves and the Scourges remain, THEN their ability to capture/enslave the new Blacktongue leadership remains a future threat.
- IF the Ssethian Scourges are killed, THEN Yoastal is freed from the relevant curse and Blacktongues can overrun the naga caves, with Karstis/Dweomercore also positioned to exploit them.
- IF the nagas die, THEN remember Rejuvenation: their defeat is temporary unless the game establishes a permanent solution.
- IF the Blacktongues are destroyed and yuan-ti abominations do not take the temple, THEN the source allows the temple to become a safer rest location.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- COERCED STALEMATE — naga thralls versus bullywugs under a coerced slaad king.
- CONTROL BROKEN — Kuketh's gem or the naga rod-system has been materially disrupted.
- SUCCESSION — Blacktongues, Scourges, or Dweomercore occupies newly available territory.
- RETURNING THREAT — rejuvenated nagas or another surviving power reasserts itself after elapsed time.

### Outcome States

- Kuketh leaves and Torbit leads until stronger powers intervene.
- Nagas dominate the Blacktongues through enthrallment.
- Blacktongues overrun naga caves after the Scourges fall, potentially competing with Dweomercore.
- The temple becomes a viable refuge if both local threats are removed.

### Player-Facing Evidence

- Thralls repeating obedient behavior despite signs of fear/resistance.
- Blacktongues living under a ruler they visibly fear rather than revere.
- Karstis avoiding commitment while watching other factions lose people.
- Ancient yuan-ti structures show that every current ruler is occupying somebody else's ruin.

## Actor Network

- Scourges -> thralls: repeated magical domination.
- Scourges -> Kuketh/Blacktongues: rival regime they want destroyed.
- Halaster -> Kuketh: control through the gem on Level 9.
- Kuketh -> Blacktongues: abusive coerced ruler.
- Karstis/Dweomercore -> all factions: observers who profit from attrition.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Excrutha

**Motive:** Maintain naga dominance, control thralls, and remove the Blacktongue obstacle.  
**Plan if unopposed:** Seek allies when useful while preserving magical control over servants.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Serakath

**Motive:** Share the Ssethian Scourges' goal of restoring dominance and destroying rivals.  
**Plan if unopposed:** Coordinate with Excrutha and exploit creatures willing to serve.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Kuketh

**Motive:** Maintain rule over the Blacktongues and survive the naga conflict.  
**Plan if unopposed:** Use the bullywug tribe as power base and resist outside control.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Yoastal

**Motive:** Pursue the unresolved yuan-ti/Slitherswamp grievance tied to her ghostly state.  
**Plan if unopposed:** Use intruders when they can advance the source-defined vengeance or release condition.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Karstis

**Motive:** Advance Dweomercore interests while surviving a level dominated by stronger factions.  
**Plan if unopposed:** Observe and exploit the conflict rather than die for it.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Torbit

**Motive:** Preserve the Blacktongue tribe and his own survival under Kuketh's brutal rule.  
**Plan if unopposed:** Remain subordinate while Kuketh controls the tribe; if Kuketh leaves or dies and Torbit survives, assume leadership.  
**Runtime:** Leadership succession matters because the Scourges can later enthrall him.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Naga lairs and daily thrall-control procedure.
- Blacktongue territory and death-slaad leadership.
- Yuan-ti temple/history locations.
- Dweomercore hideout/observers.

## Level State That Must Persist

- Naga survival/rejuvenation
- Thrall control and liberated thralls
- Blacktongue leadership
- Yoastal curse/state
- Dweomercore presence

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Kuketh's control gem is in Halaster's sanctuary on Level 9.
- The stone key from Level 2 connects to a gate involving Level 8.
- Karstis foreshadows Dweomercore and may carry knowledge forward.

## Halaster Through-Line

Primarily inheritance: Halaster replaced one defeated order with another and allows the conflict to continue.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Nagas can return through Rejuvenation. Any faction victory must account for that unless the campaign changes the condition.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.08`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/08-001.slitherswamp.png`

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