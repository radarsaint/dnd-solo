# Level 2 — Arcane Chambers — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 2: Arcane Chambers  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-02.01-arcane-chambers-dm.png`  
**Player presentation map:** `assets/maps/levels/map-02.01-arcane-chambers-player.jpg`  
**Keyed source areas:** 1–25  
**Binding:** source keyed area number ↔ the same numbered area on the canonical DM map.

Runtime geometry rules for this level:

1. Load the canonical DM map whenever movement, adjacency, line of travel, room dimensions, doors, corridors, secret passages, vertical links, or map scale can affect resolution.
2. The DM map is authoritative for **spatial geometry**. The keyed room text is authoritative for **room contents, creatures, traps, objects, rules, and scripted conditions**. Current campaign state overrides either when play has physically changed the space.
3. Do not invent, smooth over, relocate, resize, merge, split, or reroute rooms, doors, corridors, passages, stairs, shafts, gates, or other mapped connections. There is no improvisational geometry.
4. Use the scale/legend printed on this map. Do not assume one universal grid scale across Undermountain.
5. Secret geometry exists in DM topology but remains absent from player-known topology until discovered. The player-map asset is presentation material, not permission to reveal secrets.
6. If source text and map geometry appear inconsistent, consult the errata/correction layer. If no correction resolves it, preserve the ambiguity and do not invent a geometric fix.

## What This Level Is About

A contested inhabited level layered over the abandoned laboratories of Halaster's apprentices. The Rustbone bazaar wants to survive; Xanathar wants to suppress and plunder it; Rizzeryl and the wererats exploit the conflict; the ruins show what magical experimentation in Undermountain does to people.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Does the Arcane Chambers remain a functioning goblin market, become Xanathar-controlled territory, or fracture under competing opportunists and magical remnants?

### Initial Equilibrium

The Rustbone bazaar is functioning under Yek, but many goblins resent his human transformation. Xanathar holds two outposts and wants the market suppressed and the level stripped. Rizzeryl and his wererats secretly work against Xanathar. The surviving Fine Fellows are scattered through the level while old apprentice experiments remain active.

### Active Motion

- Yek keeps the bazaar operating and resists attempts to reverse the transformation he likes.
- Shunn seeks the stolen stone key and the wererat hideout; Nadia maintains the southern guild position.
- Rizzeryl uses the wererats and any useful adventurers to weaken both Xanathar outposts while hiding his deeper allegiances.
- Copper, Midna, and Rex each pursue survival according to their own selfish priorities; Halleth pursues them if present.
- Magical remnants continue acting according to their bindings and altered natures rather than faction politics.

### Player Variable

The player can alter Yek's status, protect or destabilize the bazaar, side with/against either Xanathar post, expose Rizzeryl, transfer the stone key, and resolve the Fine Fellows vengeance chain.

### Pressure Points

- Area 1 — Goblin Bazaar: market stability and Yek's transformation dispute.
- Areas 9 and 20 — Xanathar outposts: the organized pressure on the level.
- Area 14 — Rizzeryl's base: hidden third-party strategy and the stolen key.
- Areas 11 and 13 — Midna/Rex and Halleth's vengeance consequences.
- Area 13 — Mutated Apprentices: living evidence of failed magical study.
- Area 25 — Creature Storage: Halaster's collector infrastructure.
- Area 3 — Halaster Puppet: automated authorship signal, not proof of live observation.

### Reaction Rules

- IF Yek loses the circlet and returns to goblin form, THEN update his authority and the tribe's resentment from the source outcome rather than preserving the old human-boss equilibrium.
- IF a Xanathar outpost falls, THEN its patrol/control pressure disappears locally and the other actors may exploit that opening.
- IF both Xanathar outposts fall while the Rustbones survive, THEN the goblins expand their territory and patrols after sufficient time.
- IF the Rustbones are weakened but survive, THEN they harden the bazaar perimeter with traps and trained giant rats as described by the aftermath.
- IF Rizzeryl obtains what he wants from the player, THEN keep his Zhentarim/House Auvryndar loyalties and future usefulness separate from any temporary friendliness.
- IF Halleth encounters a surviving betrayer, THEN vengeance overrides convenience until that specific grievance is resolved.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- CONTESTED MARKET — bazaar, Xanathar posts, and Rizzeryl all remain active.
- GUILD PRESSURE BROKEN — one or both Xanathar posts are gone; bazaar/wererats gain room.
- BAZAAR DESTABILIZED — Yek/tribe or market defenses have been materially changed.
- NEW LOCAL ORDER — surviving actors have expanded, fortified, or abandoned positions after elapsed time.

### Outcome States

- Rustbones expand after Xanathar's removal.
- Rustbones survive but become more defensive and trap-heavy.
- Xanathar secures more of the level if its enemies are removed.
- Rizzeryl/wererats survive as a hidden influence even when public control changes.
- Fine Fellows vengeance resolves partially or completely and changes who can travel onward.

### Player-Facing Evidence

- A functioning bazaar with watchers, prices, internal gossip, and goblins uncomfortable with their human-looking boss.
- Different equipment and discipline at the two Xanathar posts.
- Evidence of covert wererat operations rather than a declared third army.
- Mutated apprentices, bound outsiders, and stored specimens showing the level's older laboratory history.

## Actor Network

- Rustbones <-> Xanathar: market survival versus suppression/plunder.
- Rustbones <-> Yek: loyalty strained by his transformation.
- Rizzeryl/wererats -> Xanathar: covert enemies using deniable violence and adventurers.
- Halleth -> Copper/Midna/Rex: personal revenge independent of faction politics.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Yek

**Motive:** Keep control of the Rustbone tribe and preserve the human form granted by the circlet.  
**Plan if unopposed:** Run the bazaar, resist Xanathar, and resist attempts to reverse his transformation.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Shunn “Spider Eyes” Shurreth

**Motive:** Secure the northern Xanathar position and recover the stolen stone key.  
**Plan if unopposed:** Use coercion, capture, and bargains to locate the wererats/key.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Nadia the Unbent

**Motive:** Hold the southern Xanathar outpost and advance guild control.  
**Plan if unopposed:** Defend the post and suppress threats to guild operations.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Rizzeryl

**Motive:** Undermine Xanathar for both House Auvryndar and the Zhentarim while preserving his hidden position.  
**Plan if unopposed:** Use wererats and adventurers against the guild; trade the stone key if necessary.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Copper Stormforge

**Motive:** Survive and enrich himself; gold comes before loyalty.  
**Plan if unopposed:** Escape captivity and pursue profit.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Midna Tauberth

**Motive:** Survive independently and avoid dependence on others.  
**Plan if unopposed:** Use the servants and shelter she controls; resist Halleth if he arrives.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Rex the Hammer

**Motive:** Survive, find fortune, and dominate companions.  
**Plan if unopposed:** Attach himself to useful adventurers, then increasingly try to control them.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Area 1: Goblin Bazaar — living settlement and Yek's transformation conflict.
- Area 3: Halaster Puppet — automated Halaster presence, not live contact.
- Areas 9 and 20 — Xanathar outposts.
- Area 11 — Midna/Halleth consequence.
- Area 13: Mutated Apprentices — early evidence of the cost of magical obsession.
- Area 14: Rizzeryl's base — three-way faction play.
- Area 25: Creature Storage — Halaster as collector.

## Level State That Must Persist

- Bazaar stability
- Yek transformation/status
- Xanathar north/south outposts
- Rizzeryl/wererat alliance and stone key
- Fine Fellows/Halleth vengeance outcomes

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Rizzeryl's stone key opens a gate linking Levels 6 and 8.
- Halleth's thread originates on Level 1 and can resolve here.
- House Auvryndar and Xanathar politics continue on Level 3.
- The level's failed-apprentice material feeds the Halaster/apprentice campaign story.

## Halaster Through-Line

Teach authorship and collector behavior through remnants. No required direct contact.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Surviving goblins fortify and expand if Xanathar is weakened. Faction changes should alter patrols and future access.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.02`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/02-001.arcane-chambers.png`
- Level art: `/Dnd solo/Assets/Art/Levels/02-002.wall-carvings.png`

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