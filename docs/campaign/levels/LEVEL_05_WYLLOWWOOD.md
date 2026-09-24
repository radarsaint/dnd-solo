# Level 5 — Wyllowwood — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 5: Wyllowwood  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-05.01-wyllowwood-dm.png`  
**Player presentation map:** `assets/maps/levels/map-05.01-wyllowwood-player.jpg`  
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

A convincing artificial wilderness that is both sanctuary and prison. Wyllow protects a real ecosystem created by Halaster while carrying centuries of grief, guilt, and dependence.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Does the player remain a tolerated guest in Wyllow's controlled ecosystem, become a threat the whole forest mobilizes against, or break one of the relationships that holds Wyllowwood together?

### Initial Equilibrium

Wyllow rules a functioning artificial wilderness and tolerates travelers who do not harm it. Her forest spies report violations. Tearulai's personality currently suppresses Valdemar's evil and makes the dragon a stable part of Wyllowwood. The werebats accept Wyllow's authority. Vool is exiled. Crissann's spirit wants revenge on Wyllow.

### Active Motion

- Wyllow patrols or receives reports and preserves the ecosystem rather than seeking outsiders by default.
- Mobar and the werebats prey on permitted targets while avoiding Wyllow's protected animals and dragon.
- Vool hunts alone, then tries to turn useful outsiders against Wyllow if cornered.
- Crissann's spirit seeks an agent willing to take the wand of fireballs and attack Wyllow.
- Tearulai/Valdemar guards the platform and gate under Wyllow's current permission structure.

### Player Variable

The player can obey or violate the forest rules, accept Crissann's revenge framing, believe Vool, gain Wyllow's trust, remove Tearulai, kill Wyllow, or use the crystal bulb that summons Halaster.

### Pressure Points

- Area 2 — Forest: the warning signs and spy network convert ordinary player behavior into Wyllow's attitude state.
- Area 2d — Old Grave: Crissann offers a weapon and a revenge agenda.
- Area 6 — Wyllow's Tower: primary negotiation and safe-passage scene.
- Area 6g — crystal bulb: optional first physical Halaster meeting if used.
- Area 9 — Dragon's Platform: Tearulai/Valdemar fork and controlled gate access.
- Areas 12–17 — werebat society and Vool's exile create a second account of Wyllow's rule.

### Reaction Rules

- IF the player chops trees, starts destructive fires, kills protected animals, or commits similar harm, THEN forest spies report it and Wyllow shifts toward eradication; she can mobilize the dragon, werebats, and awakened trees according to source capability.
- IF the player remains harmless and treats with Wyllow, THEN she can grant safe passage; IF they also remove the cloakers north of her tower, THEN she can reveal gate/passages as specified by the source.
- IF the player accepts Crissann's revenge plan, THEN Crissann guides them toward Wyllow; IF Wyllow is defeated, THEN Crissann's spirit turns on the party in despair.
- IF Tearulai is forcibly removed from Valdemar, THEN maintain separate minds: Tearulai becomes a sentient item with its own goal to return to Myth Drannor, while Valdemar's evil personality returns and Wyllow becomes his mortal enemy.
- IF Wyllow dies, THEN after days the werebats loot the tower and set the calendar stone to perpetual night; vegetation and animal populations then decline over time.
- IF Wyllow survives but evil Valdemar survives separated from Tearulai, THEN Wyllow begins directing newly arrived adventurers against the dragon.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- EQUILIBRIUM — Wyllow's ecosystem and political hierarchy function.
- SCRUTINY — the player's behavior has caused Wyllow or another actor to actively judge/manipulate them.
- RUPTURE — Wyllow is hostile, Valdemar/Tearulai are separated, or the werebat balance has broken.
- TRANSFORMED WOOD — Wyllow is dead or a new predator/defender relationship now determines the ecosystem.

### Outcome States

- Wyllow remains ruler and the ecosystem stays stable.
- Wyllow survives but now wages a local war against restored-evil Valdemar.
- Wyllow dies; werebats impose perpetual night and the ecosystem collapses unless checked.
- Tearulai remains with or leaves with a wielder, creating a persistent sentient-item thread beyond the level.

### Player-Facing Evidence

- Explicit warning signs, animal behavior, and tracks establish that the forest is watched and governed.
- Wyllow's calm reception of harmless visitors contrasts with rapid coordinated retaliation against harm.
- Crissann and Vool offer self-interested, hostile narratives about Wyllow rather than objective exposition.
- The sword visibly embedded in Valdemar's skull is an immediate clue that dragon identity is unstable.

## Actor Network

- Wyllow -> ecosystem: sovereign protector and source of retaliation.
- Mobar/werebats -> Wyllow: subordinate predators; Mobar's infatuation strengthens obedience.
- Vool -> Wyllow/werebats: exiled destabilizer seeking leverage through outsiders.
- Crissann -> Wyllow: revenge-seeking dead former companion.
- Tearulai -> Valdemar: currently suppresses/reshapes the dragon's personality.
- Valdemar (if freed from Tearulai) -> Wyllow: mortal enemy.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Wyllow

**Motive:** Protect Wyllowwood and its peaceful denizens while remaining bound by her guilt and long dependence on the dungeon.  
**Plan if unopposed:** Tolerate harmless travelers; mobilize the forest, dragon, and werebats against threats.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Valdemar

**Motive:** Preserve his lair and treasure under the personality currently imposed by Tearulai; if the sword is removed, resume his lawful-evil green-dragon nature and destroy Wyllow if possible.  
**Plan if unopposed:** While Tearulai remains lodged in his skull, coexist with Wyllow and enforce her permission around the platform/gate. If separated, treat Wyllow as a mortal enemy.  
**Runtime:** Track dragon body/status separately from Tearulai's sentient-item state; removal of the sword is a hard personality-state transition.

### Vool

**Motive:** Survive exile and find companionship or leverage.  
**Plan if unopposed:** Offer guidance and try to turn outsiders against Wyllow to improve his own position.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Mobar

**Motive:** Win Wyllow's favor and maintain control of the werebat tribe.  
**Plan if unopposed:** Obey Wyllow, bring her gifts, and prey on outsiders when permitted.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Crissann (will-o'-wisp)

**Motive:** Avenge the betrayal and death bound up with Wyllow; recruit outsiders to kill her.  
**Plan if unopposed:** Remain at the grave and seek a willing avenger; if Wyllow is actually defeated, despair overrides the alliance and Crissann turns on the killers.  
**Runtime:** Track whether the wand was taken, whether the player accepted/refused the revenge framing, and Wyllow's status.

### Halastree

**Motive:** Serve Wyllow as her polite usher and defend her tower/order.  
**Plan if unopposed:** Receive visitors according to Wyllow's rules and help route peaceful guests into the social encounter rather than combat.  
**Runtime:** Treat Halastree as an accountable awakened NPC, not furniture; track knowledge of visitor conduct reported to Wyllow.

### Tearulai (sentient sword)

**Motive:** Seek beauty, gems, worthy companionship, and ultimately return to the forests around Myth Drannor.  
**Plan if unopposed:** While lodged in Valdemar, continue dominating the dragon's personality; if removed and attuned, pursue its own preferences and attempt to leave Undermountain when the opportunity exists.  
**Runtime:** Maintain a separate motive record from Valdemar whenever separation is possible.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- The forest itself — maintain ecology and the false-surface effect.
- Wyllow's Tower — relationship center of the level.
- Area 6g crystal bulb — optional player-triggered first meeting with the real Halaster.
- Werebat settlement and Vool's refuge — local social conflict.

## Level State That Must Persist

- Wyllow attitude to player
- Forest damage/protection
- Tearulai/Valdemar status
- Werebat tribe and Vool
- Crystal bulb used or unused

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Tearulai can become a persistent sentient-item NPC if removed.
- Wyllowwood gates and passages connect to Levels 2, 6, and 7.
- The crystal bulb is the optional Level 5 Halaster meeting in the campaign through-line.

## Halaster Through-Line

Optional first physical meeting only if the player uses the source-provided bulb. Wyllow herself is a major revelation about Halaster's possessive control.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

The forest persists if its caretakers survive. Damage to Wyllowwood and Wyllow's fate should remain important because this is one of Halaster's long-running creations.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.05`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/05-001.wyllowwood.png`

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