# Level 22 — Shadowdusk Hold — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 22: Shadowdusk Hold  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-22.01-shadowdusk-hold-dm.png`  
**Player presentation map:** `assets/maps/levels/map-22.01-shadowdusk-hold-player.jpg`  
**Keyed source areas:** 1–41  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

An exiled Waterdavian noble house has become a Far Realm dynasty. Dezmyr and Zalthar want restoration and conquest; Halaster sees them as potential puppets for ruling Waterdeep.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Can the player dismantle a Far-Realm-corrupted noble dynasty before it returns to Waterdeep—and how much of Halaster's Shadow Lord plan survives the level?

### Initial Equilibrium

The Shadowdusks maintain a subterranean imitation of their lost noble house. Dezmyr and Zalthar are death-knight twins devoted to each other and obsessed with restoring the family to power in Waterdeep. Other family members pursue arcane/Far Realm interests within the hold. Halaster encourages the dynasty because he wants to rule Waterdeep through them.

### Active Motion

- The twins preserve family military power and prepare for eventual return/conquest rather than merely defending a dungeon floor.
- Living Shadowdusks continue occult research and contact with Far Realm entities.
- Killed humanoid family members can return as will-o'-wisps unless the source-defined precautions are taken.
- If threatened badly enough, surviving leaders seek allies among other Undermountain powers or the Far Realm.

### Player Variable

The player can investigate family history, kill or bargain with family members, prevent undead return, destroy the twins, disrupt Far Realm assets, help the dynasty, or enter Halaster's final gate at Area 35.

### Pressure Points

- Family-history rooms/frescoes — establish continuity from Waterdeep nobility to the present hold.
- Arcane/Far Realm sanctums — show the family's active source of power/corruption.
- Dezmyr and Zalthar's domains — leadership and twin-bond payoff.
- Area 39 — dracolich phylactery: major local persistence object.
- Area 35 — Eyes of Stone / gate to Level 23: final Halaster threshold.

### Reaction Rules

- IF a humanoid Shadowdusk dies without the source precautions, THEN schedule its will-o'-wisp return rather than marking the NPC permanently removed.
- IF Dezmyr/Zalthar are destroyed, THEN remember death-knight reformation; if they return to a ruined family, they add the player to their vendetta.
- IF the twins return after family destruction, THEN they seek surviving Auvryndar/Freth, Seadeeps illithids, Vanrakdoom cultists, or Far Realm entities as allies depending on which still exist in campaign state.
- IF the player materially helps the family's Waterdeep plan, THEN record it as support for Halaster's Shadow Lord preoccupation rather than only local friendliness.
- IF Area 35 is opened/used, THEN trigger the final Halaster threshold state and preserve all sacrifice/resource consequences entering Level 23.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- DYNASTY INTACT — family hierarchy and Far Realm program functioning.
- HOLD BREACHED — player has killed/converted key family members or exposed critical assets.
- SUCCESSION CRISIS — one/both twins or major occult infrastructure removed.
- VENGEFUL REMNANT / COLLAPSE — reformed death knights seek external allies or the dynasty is unable to execute its Waterdeep plan.

### Outcome States

- Shadowdusks remain viable for a future Waterdeep return, supporting Halaster's Shadow Lord plan.
- Family shattered but twins later reform and seek alliances/revenge.
- Far Realm connections become the remnant's primary source of reinforcements.
- Player opens the route to Level 23 with a clearly recorded campaign relationship state.

### Player-Facing Evidence

- Inverted family heraldry, noble rooms, and inherited records keep the enemy recognizably Waterdavian.
- Family members speak/act in terms of lineage and restoration, not generic cult conquest.
- Repeated unnatural returns and Far Realm manifestations demonstrate that killing individuals may not solve the institution.
- Halaster's support should be inferable through opportunities/resources and the final gate, not constant cameos.

## Actor Network

- Dezmyr <-> Zalthar: unusually strong mutual devotion; leadership functions as a pair.
- Twins -> Waterdeep: long-term conquest/restoration objective.
- Halaster -> Shadowdusks: cultivates them as future puppets for the Shadow Lord plan.
- Living occultists -> Far Realm: source of knowledge/reinforcements and corruption.
- Player -> dynasty: potential destroyer, enabler, or personal future enemy.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Dezmyr Shadowdusk

**Motive:** Restore the Shadowdusk family to power and seize influence over Waterdeep alongside Zalthar.  
**Plan if unopposed:** Protect the hold, preserve family power, and seek allies if threatened.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Zalthar Shadowdusk

**Motive:** Restore the family and conquer with Dezmyr; devotion to the twin bond is central.  
**Plan if unopposed:** Act in concert with Dezmyr and pursue vengeance against those who destroy the family.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Melissara Shadowdusk

**Motive:** Advance the family's arcane/Far Realm interests and survive internal politics.  
**Plan if unopposed:** Use knowledge and position in service of the house unless personal source motives override.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Berlain Shadowdusk

**Motive:** Preserve personal position within the corrupted family structure.  
**Plan if unopposed:** Follow source-specific relationships and react to changes in leadership.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Family-history spaces and frescoes — make the hold feel inherited, not generic aberration dungeon.
- Death-knight leadership — active political ambition.
- Far Realm contacts/shrines — source of corruption and power.
- Area 35 gate/sacrifice threshold — final Halaster threshold into Level 23.

## Level State That Must Persist

- Dezmyr/Zalthar status
- family population and will-o'-wisp returns
- Far Realm alliances
- Halaster Shadow Lord plan helped/harmed
- gate to Level 23 opened

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Skrianna on Level 9 and emissaries on Level 12 establish earlier Shadowdusk reach.
- Runestone expedition on Level 20 can alter what resources/knowledge the family has here.
- Xindulus may arrive from Level 21 if alive.
- Area 35 directly gates Level 23 and triggers the final through-line threshold.

## Halaster Through-Line

Final-threshold milestone. The player's handling of the Shadowdusks directly touches one of Halaster's possible campaign goals. By the Level 23 gate, Halaster knows they are coming.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Death knights can return. If the family is shattered, surviving twins seek new Undermountain/Far Realm allies and specifically add the player to their vendetta.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.22`  
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