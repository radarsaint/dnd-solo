# Level 19 — Caverns of Ooze — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 19: Caverns of Ooze  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-19.01-caverns-of-ooze-dm.png`  
**Player presentation map:** `assets/maps/levels/map-19.01-caverns-of-ooze-player.jpg`  
**Keyed source areas:** 1–16  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

Halaster has turned powerful beings into a competitive game: a marid and dao race for Ezzat's phylactery while a stranded spelljamming crew and Ghaunadaur cult occupy the same bizarre caverns.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Which bound genie wins Halaster's contest for Ezzat's phylactery, and can the stranded Scavenger crew escape a completely separate Halaster-made captivity?

### Initial Equilibrium

Ichthyglug and Jarûk are bound by Halaster's bargain: whichever obtains Ezzat's phylactery wins freedom while the other remains trapped. They cannot harm each other directly or indirectly, so both recruit proxies. Urm is forced to mediate. Elsewhere, Captain N'ghathrod and the stranded Scavenger crew are trapped because Halaster stole the ship's spelljamming helm, while Ghaunadaur worshipers pursue ooze transformation.

### Active Motion

- Both genies seek adventurers capable of retrieving Ezzat's phylactery from Level 20 while remaining within Halaster's contest rules.
- Urm carries communications and looks for any improvement in his own forced position.
- N'ghathrod seeks brains and survival but can bargain when badly threatened; the Scavenger remains immobile without its helm.
- Ghaunadaur cultists continue their transformation/worship practices independent of the genie contest.

### Player Variable

The player can accept one or both genie bargains, refuse the contest, acquire the phylactery on Level 20, recover the Scavenger's helm from Level 23 later, bargain with N'ghathrod, or disrupt the cult.

### Pressure Points

- Area 1 — Ichthyglug's grotto: one side of the phylactery contract.
- Area 11 — Jarûk's caverns: competing contract and prize structure.
- Area 13 — Scavenger: stranded crew, N'ghathrod, and stolen-helm escape thread.
- Ghaunadaur shrine/ooze areas — independent transformation cult.
- Return visit with Ezzat's phylactery — delayed level payoff after Level 20.

### Reaction Rules

- IF the player gives Ezzat's phylactery to one genie, THEN that genie wins freedom and the other becomes the losing bound party/enemy; do not award both outcomes.
- IF a genie is freed before the other contest is otherwise resolved, THEN Halaster may later introduce an efreeti opponent for the remaining genie as the published aftermath suggests.
- IF N'ghathrod is reduced enough to surrender and a truce is accepted, THEN preserve its self-serving promise regarding the Scavenger; cooperation does not erase its desire to remove future rivals.
- IF the spelljamming helm is recovered from Level 23 and returned, THEN the Scavenger can become an active escape/ownership thread subject to the source's wish requirement.
- IF neither major thread is resolved, THEN the level changes little in the short term; avoid inventing a local war between unrelated groups.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- PARALLEL CAPTIVITIES — genie contest and Scavenger stranding coexist.
- CONTRACTED — player has accepted a genie or Scavenger-related obligation.
- PHYL ACTERY RETURN / HELM RETURN — delayed cross-level objective comes back to the level.
- FREED / STILL BOUND — one captivity changes while the other may remain completely unresolved.

### Outcome States

- Ichthyglug freed, Jarûk remains bound and hostile/resentful.
- Jarûk freed, Ichthyglug remains bound and hostile/resentful.
- Scavenger remains stranded under N'ghathrod's uneasy rule.
- Scavenger regains helm and becomes a campaign-scale transport asset/escape possibility.
- Cult persists or is destroyed largely independently of the other outcomes.

### Player-Facing Evidence

- The two genie courts offer competing versions of the same bargain, making the exclusivity discoverable.
- Urm's disgruntled mediation shows neither genie is freely cooperating with the arrangement.
- The enormous stranded ship and missing helm grooves make the Scavenger problem physically obvious.
- Ghaunadaur worship demonstrates yet another Halaster-influenced belief system without making it part of the genie plot.

## Actor Network

- Ichthyglug <-> Jarûk: competitors constrained from harming one another.
- Both genies -> adventurers: necessary proxies for Level 20.
- Urm -> both: coerced messenger with low loyalty.
- N'ghathrod -> crew/player: predatory captain capable of pragmatic surrender.
- Ghaunadaur cult -> ooze transformation: separate religious project.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Ichthyglug

**Motive:** Obtain Ezzat's phylactery first and win freedom from Halaster's bargain.  
**Plan if unopposed:** Use adventurers as legal proxies without directly harming the rival genie.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Jarûk

**Motive:** Obtain Ezzat's phylactery first and force the rival to remain bound.  
**Plan if unopposed:** Recruit and bargain with adventurers within Halaster's rules.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Urm

**Motive:** Survive forced service as go-between and improve his own miserable position.  
**Plan if unopposed:** Carry messages while looking for chances to escape obligations or inconvenience his masters.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Captain N’ghathrod

**Motive:** Survive, feed, and recover a viable future for himself and the stranded Scavenger if possible.  
**Plan if unopposed:** Prey on humanoids while seeking the means to restore the ship.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Ghaunadaur zealots

**Motive:** Pursue transformation and worship, believing their ooze state is divine blessing.  
**Plan if unopposed:** Serve the cult's practices and seek Halaster-enabled transformation.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Genie domains — competing bargains with same objective.
- Scavenger — evidence of Halaster collecting entire impossible situations.
- Ghaunadaur shrine/ooze transformation — Halaster reinforcing false divine interpretation.
- Return condition after Level 20 — phylactery payoff.

## Level State That Must Persist

- which genie has player's support
- genie freedom/binding
- Urm status
- Scavenger crew/captain/helm
- Ghaunadaur cult state
- Ezzat phylactery destination

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Ezzat and his phylactery are on Level 20.
- The Scavenger's spelljamming helm is on Level 23.
- This level demonstrates Halaster binding powerful beings into games and collections, feeding the campaign through-line.

## Halaster Through-Line

Strong revelation of Halaster as experimenter and binder. Save direct strategic relationship for Level 20.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

The winner of the phylactery contest is freed and the loser becomes a long-term enemy/remaining captive. Scavenger restoration can create a separate escape consequence.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.19`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/19-001.caverns-of-ooze.png`

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