# Level 23 — Mad Wizard’s Lair — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 23: Mad Wizard’s Lair  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-23.01-mad-wizards-lair-dm.png`  
**Player presentation map:** `assets/maps/levels/map-23.01-mad-wizards-lair-player.jpg`  
**Keyed source areas:** 1–36  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

The payoff layer. Halaster, Arcturia, and Trobriand are no longer distant history; the player enters the private center of the system they have spent the campaign learning.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

What does Halaster ultimately believe the player has become inside his dungeon, and does the accumulated campaign relationship end in recruitment, dismissal, bargain, rivalry, death, or a struggle over Undermountain itself?

### Initial Equilibrium

The player has reached Halaster's private level. Arcturia and Trobriand remain part of his inner circle according to their surviving campaign state. Halaster has an accumulated player model, favors, grievances, apprentice interest, and current preoccupation. Jhesiyra is still hidden in the dungeon and intends to exploit any window created by Halaster's defeat.

### Active Motion

- Halaster watches the final approach and acts according to the dedicated Halaster behavior/through-line layers rather than a generic boss script.
- Arcturia reacts to the permanent state of her Level 14 phylactery and any known attacks on her work.
- Trobriand reacts to the player's history with his constructs and pursues his own post-flesh construct obsession.
- Jhesiyra remains covert until her source-supported warning/opportunity; she is pursuing control of Undermountain, not altruistic liberation.

### Player Variable

The player can negotiate with or oppose the surviving apprentices, recover campaign objects such as the Scavenger helm, receive Jhesiyra's warning, pass Halaster's Nalkara test, and then resolve the relationship built across the campaign.

### Pressure Points

- Areas 1–21 — private dungeon: Halaster/apprentice machinery should call back to prior discoveries rather than feel like a fresh unrelated gauntlet.
- Area 13 — Trobriand confrontation/payoff if active.
- Area 17 — Arcturia court/payoff, modified by phylactery state.
- Area 29 — Apprentice Portraits: historical context at the center of the apprentice through-line.
- Area 30 — Scrying Room: reinforces that observation was a real campaign capability.
- Area 32 — Jhesiyra's Warning: hidden counterplot becomes explicit at the threshold.
- Area 33 — Mad Mage Showdown: Nalkara test followed by relationship payoff.
- Scavenger helm repository — delayed Level 19 escape payoff.

### Reaction Rules

- IF Arcturia's phylactery was destroyed on Level 14, THEN she attacks on sight as the source states; otherwise do not invent that grievance.
- IF the player has materially helped Halaster's current goal, THEN his post-Nalkara response can be warm/rewarding/dismissive according to source; IF they hindered it, THEN hostility is justified.
- IF Halaster speaks after Nalkara, THEN reference at least three campaign events he actually knows, using the finale context rather than generic praise.
- IF Halaster dies in Undermountain, THEN apply rejuvenation and the conclusion state: gates deactivate and he normally reforms in 1d10 days unless Jhesiyra successfully seizes control.
- IF Jhesiyra attempts takeover, THEN treat success as a campaign-state decision grounded in surviving apprentices, dungeon control, and the ending—not an automatic happy ending.
- IF the Scavenger helm leaves with the player, THEN update Level 19's ship thread for a possible return.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- FINAL APPROACH — apprentice/private-dungeon consequences being cashed out.
- AUDIENCE — Halaster has recognized the player as a major actor and the Nalkara test/showdown logic is active.
- RELATIONSHIP RESOLUTION — bargain, recruitment, dismissal, rivalry, or combat determined by accumulated state.
- SUCCESSION — Halaster remains, rejuvenates, or Jhesiyra contests control of Undermountain.

### Outcome States

- Halaster survives and the player leaves under a bargain/dismissal/recruitment outcome.
- Halaster dies and later reforms, hardening Undermountain against future challengers.
- Jhesiyra successfully takes control and becomes the new dungeon master/power, with her own instability unresolved.
- Jhesiyra fails and Halaster resumes control after rejuvenation.
- Surviving Arcturia/Trobriand remain future powers if not resolved.

### Player-Facing Evidence

- Private rooms and apprentice spaces visibly reuse names, creations, and systems encountered on earlier floors.
- Halaster's dialogue uses actual observed player history rather than exposition about things the player already knows.
- Arcturia/Trobriand recognize consequences from their own earlier levels when they have a source-supported way to know them.
- Jhesiyra's revelation reframes earlier gate behavior without rewriting what the player previously experienced.

## Actor Network

- Halaster -> player: accumulated campaign relationship, defined by state rather than alignment shorthand.
- Halaster -> Arcturia/Trobriand: useful apprentices he is willing to torment or sacrifice depending on preoccupation.
- Arcturia/Trobriand -> player: personal reactions based on phylactery/construct history.
- Jhesiyra -> player: covert instrument for removing Halaster so she can seize the dungeon.
- Jhesiyra -> surviving apprentices: future threats to her control if Halaster falls.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Halaster Blackcloak

**Motive:** Resolve his current preoccupation and his accumulated relationship with the player while preserving control of Undermountain.  
**Plan if unopposed:** Use the full `HALASTER_DM_LAYER` and through-line state; test, bargain, reward, dismiss, recruit, or attack according to actual history.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Arcturia

**Motive:** Preserve herself and her work; react personally if her phylactery was destroyed on Level 14.  
**Plan if unopposed:** Attack on sight if source condition is met; otherwise act from current loyalty, interest, and survival.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Trobriand

**Motive:** Continue his construct obsession and post-flesh existence while remaining part of Halaster's inner circle.  
**Plan if unopposed:** Protect his interests and respond to what the player did to his creations on Level 13.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Nalkara

**Motive:** Repay the favor she owes Halaster by serving as his test/enforcer in the showdown.  
**Plan if unopposed:** Fight the player when summoned according to the source encounter.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Jhesiyra Kestellharp

**Motive:** Use the player to remove Halaster, then seize control of Undermountain before Halaster can return.  
**Plan if unopposed:** Remain concealed until the source-supported warning/opportunity near the finale; exploit any post-Halaster power vacuum.  
**Runtime:** Load her persistent campaign record rather than creating a new Level 23 copy; her goals survive Halaster's defeat and may conflict with surviving apprentices.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Areas 1–21 — gauntlet through Halaster's private dungeon and apprentice machinery.
- Area 29: Apprentice Portraits — accumulated history made visible.
- Area 32: Jhesiyra's Warning — hidden counterplot reaches threshold.
- Area 33: Mad Mage Showdown — campaign relationship payoff.
- Conclusion — Halaster rejuvenation versus Jhesiyra's attempted seizure of Undermountain.

## Level State That Must Persist

- Halaster finale context
- Arcturia phylactery consequence
- Trobriand callbacks
- Nalkara outcome
- Halaster alive/dead/dismissed/allied
- Jhesiyra takeover attempt
- gate network state

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Arcturia state comes from Level 14; Trobriand state comes from Level 13.
- Scavenger helm pays off Level 19.
- All Halaster observation/contact milestones feed Area 33 finale context.
- Conclusion changes the entire dungeon's gate state and ownership question.

## Halaster Through-Line

Full payoff. He must reference actual known campaign events and respond to the player's history, not deliver generic boss dialogue.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

If Halaster dies, gates fail and he normally reforms in 1d10 days unless Jhesiyra successfully seizes control. The campaign outcome depends on accumulated state rather than assuming a single canonical ending.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.23`  
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