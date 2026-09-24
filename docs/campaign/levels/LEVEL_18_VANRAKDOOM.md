# Level 18 — Vanrakdoom — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 18: Vanrakdoom  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-18.01-vanrakdoom-dm.png`  
**Player presentation map:** `assets/maps/levels/map-18.01-vanrakdoom-player.jpg`  
**Keyed source areas:** 1–33  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

A long Waterdavian tragedy calcified into a Shar cult stronghold. The level is about loss, corruption, and whether Glyster/Umbraxakar can be freed from what Vanrak and Shar made of him.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Can the player end a centuries-old cycle of Shar-driven loss by destroying Keresta and restoring Glyster, or will they simply kill another victim of the level's despair?

### Initial Equilibrium

Keresta rules the surviving cult of Shar and plans future attacks on Waterdeep's temples. Umbraxakar is Glyster, a bronze dragon whose despair and Shar corruption keep part of Vanrakdoom in the Shadowfell. His memories are anchored throughout the level and provide the means to understand and potentially reverse his condition.

### Active Motion

- Keresta sustains the vampire/cult network, recruits or converts promising acolytes, and plans strikes against Lathander/Selûne worship in Waterdeep.
- Umbraxakar remains in despair, defends the domain, and unconsciously deepens the Shadowfell condition through that despair.
- Cultists perform rituals that anchor Umbraxakar's memories and strengthen the domain's shadow condition.
- Prisoners/survivors such as Portia remain subject to Keresta's feeding/charm until freed.

### Player Variable

The player can learn the history through visions, gather emotionally significant items, attempt the three-success redemption sequence, kill Umbraxakar, destroy Keresta, free prisoners, or leave one pillar of the cult intact.

### Pressure Points

- Umbraxakar visions throughout the level — required evidence for redemption logic, not decorative flashbacks.
- Cult ritual chambers — show active attempts to anchor more of the level in shadow.
- Area 25 — Prisoner of Darkness: Portia and the failed prior Moonstar expedition.
- Area 26/31 — Keresta leadership/tomb loop: vampire persistence must be handled correctly.
- Area 32 — Umbraxakar's Lair: redemption or destruction payoff.
- Four emotionally significant gifts — resources for the source-defined redemption checks.

### Reaction Rules

- IF the player presents an emotionally significant gift with appropriate appeal and succeeds on three qualifying checks before failing too often, THEN Umbraxakar's despair ends and he becomes Glyster again.
- IF Glyster is restored, THEN his undead servants vanish, Shadowfell-shifted areas return to the Material Plane, and he offers active help/escape goals.
- IF Umbraxakar dies, THEN the Shadowfell displacement also ends, but no redeemed dragon ally exists.
- IF Keresta is destroyed, THEN her regional fog/vermin effects fade and surviving cultists/vampire spawn disperse over time.
- IF Keresta survives a defeat and can reach her sarcophagus, THEN preserve the vampire recovery loop; do not mark her dead prematurely.
- IF cult rituals remain active and Umbraxakar remains despairing, THEN their project to tether memories/expand shadow influence remains live.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- CULT DOMINANCE — Keresta active, Umbraxakar corrupted, shadow rituals continuing.
- MEMORY RECOVERY — player has enough visions/gifts to understand a redemption path.
- DRAGON DECISION — redemption attempt or lethal confrontation underway.
- CURSE BROKEN / CULT COLLAPSE — Glyster restored or Umbraxakar killed, with Keresta separately alive/dead.

### Outcome States

- Glyster restored and becomes a powerful ally seeking escape from Undermountain.
- Umbraxakar killed; shadow condition ends but tragedy is resolved only by death.
- Keresta destroyed; cult disperses and Waterdeep receives later consequences/reward.
- Keresta survives and continues using the domain even if the dragon's state changes.

### Player-Facing Evidence

- Repeated involuntary visions let the player reconstruct Glyster/Vanrak history in fragments.
- Color/light loss and Shadowfell geography physically embody Umbraxakar's despair.
- Cultists actively manipulating memory-anchors show the present-day antagonist is exploiting the dragon's grief.
- Portia provides a mortal failed-expedition perspective rather than authoritative puzzle instructions.

## Actor Network

- Keresta -> Umbraxakar: exploits/maintains Shar's corruption for cult power.
- Umbraxakar/Glyster -> Vanrak memory: grief attachment driving the curse.
- Moonstar interests -> Glyster: family obligation to restore or end his suffering.
- Player -> dragon: can become executioner, redeemer, or failed interloper.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Keresta Delvingstone

**Motive:** Preserve the cult of Shar and its hold over Vanrakdoom.  
**Plan if unopposed:** Use vampire power and cult infrastructure to eliminate threats.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Umbraxakar / Glyster

**Motive:** Exist under Shar's corruption while the buried history of Glyster makes redemption possible.  
**Plan if unopposed:** Defend the lair and cult-linked domain unless the conditions for breaking Shar's hold are met.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Helion Moonstar

**Motive:** Carry House Moonstar's request and family responsibility without becoming the protagonist of the dungeon level.  
**Plan if unopposed:** Support the attempt to save Glyster or, failing that, end his suffering.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Portia Dzuth

**Motive:** Survive captivity and see the mission to restore Glyster completed despite trauma and distorted time perception.  
**Plan if freed:** Stay with rescuers until safe or until Keresta's charm causes a source-supported betrayal.  
**Runtime:** Track charm state, trauma, trust, and whether she has reached safety.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Vanrak/Moonstar history — must inform the level's meaning.
- Keresta's cult network — active present threat.
- Umbraxakar's lair — emotional and quest payoff.
- Moonstar quest conditions — connect Waterdeep consequences to dungeon action.

## Level State That Must Persist

- Keresta/cult survival
- Umbraxakar corruption/redemption/death
- Moonstar quest outcome
- Shar influence and vampire survivors

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- The Save the Dragon quest originates in Waterdeep campaign setup.
- Glyster can become a mobile campaign NPC for deeper levels if restored.
- Halaster permits the Shadowfell anomaly because it interests him and can later restock the level after its current story ends.

## Halaster Through-Line

Halaster is background here; the level belongs to the Moonstar/Shar tragedy. Record any relevant consequence for the broader dungeon but do not hijack the story.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Destroying Keresta disperses remaining cultists. Glyster/Umbraxakar's outcome must persist as a major surface relationship consequence.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.18`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/18-001.vanrakdoom.png`

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