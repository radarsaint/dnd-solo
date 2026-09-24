# Level 1 — Dungeon Level — DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Level-specific DM behavior  
**Source scope:** Level 1: Dungeon Level  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, `MAP_INDEX.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Geometry Binding

**Canonical DM map:** `assets/maps/levels/map-01.01-dungeon-level-dm.png`  
**Player presentation map:** `assets/maps/levels/map-01.01-dungeon-level-player.jpg`  
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

The player's first contact with Undermountain as a living, inhabited ecosystem. The immediate conflict is exploitation of newcomers: the Undertakers prey on adventurers while Xanathar forces try to control access to deeper levels.

The runtime should keep this concern active while individual keyed rooms supply immediate facts and encounters.

## Story Engine

### Player-Facing Story Question

Who controls the upper dungeon's traffic and exploitation of new arrivals after the player disturbs the balance?

### Initial Equilibrium

The Undertakers extort newcomers from areas 6–8 while three Xanathar watch posts restrict descent and suppress some predators. Uktarl and Harria are secretly trying to remove each other. Xanathar is preparing to infiltrate or absorb the bandit gang.

### Active Motion

- Uktarl and Harria continue competing for sole control while both profit from the vampire fraud.
- Xanathar forces test Undertaker defenses, seek an opening against the flesh golem, and ultimately want an Undertaker leader captured for intellect-devourer replacement.
- Predators continue ranging outside occupied territory but are partially constrained by the organized factions.
- New adventuring parties continue arriving from the Yawning Portal regardless of the player's choices.

### Player Variable

The player can expose or exploit the Undertaker fraud, back one leader, destroy the flesh golem, attack either faction, aid Halleth, or simply open territory by killing its occupants.

### Pressure Points

- Area 1 — Entry Well: establishes the steady arrival route and Undertaker surveillance of newcomers.
- Areas 6–8 — Undertaker territory: extortion, false-vampire performance, and Uktarl/Harria leadership fracture.
- Areas 23, 28, and 39 — Xanathar watch posts: organized effort to control movement deeper into Undermountain.
- Area 37 — Map Room: activates Halleth's vengeance thread toward the Fine Fellows on Level 2.
- Area 29 — Eye See You!: campaign-level Halaster observation pressure point.
- Area 27 — Hidden Demiplane: automated Halaster simulacrum; information opportunity, not live Halaster contact.

### Reaction Rules

- IF the Undertakers cannot extort or defeat the player, THEN they prefer to redirect the player toward Xanathar forces rather than fight to annihilation.
- IF one Undertaker leader is removed and the other survives, THEN the survivor attempts to consolidate the gang and its territory.
- IF the flesh golem is removed, THEN Xanathar's fear-based restraint against the Undertakers is reduced; future guild pressure can increase when time and means permit.
- IF the Undertakers are eliminated while Xanathar remains, THEN guild operatives can occupy former bandit territory as described by the aftermath.
- IF Xanathar's outposts are destroyed, THEN grells, gricks, and other predators begin expanding into the resulting security vacuum.
- IF Halleth gains a viable route toward a surviving Fine Fellow, THEN his next action remains pursuit of vengeance rather than generic companionship.

### Escalation State

The escalation state is **event-driven**. Do not advance it because the player cleared a percentage of rooms.

- CONTESTED — Undertakers and Xanathar both retain meaningful control.
- SHIFTED — one faction has been materially weakened and the other has room to expand.
- VACUUM — both organized powers are crippled; predators and independent adventurers gain relative freedom.
- REPOPULATED — after sufficient elapsed time, surviving factions/predators/new adventurers have visibly adapted to the changed level.

### Outcome States

- Undertaker control persists, possibly under one surviving leader.
- Xanathar expands into former Undertaker territory.
- Xanathar is removed and predators expand.
- Both powers are broken and the level becomes an unstable corridor used by predators and rival adventurers.

### Player-Facing Evidence

- Undertaker spies watching the Entry Well and their theatrical vampire disguises.
- Separated watch posts, patrol behavior, and goblinoids discussing orders rather than behaving as isolated monsters.
- Signs of creatures avoiding occupied territory and later expanding into emptied rooms.
- New adventurers descending from above, showing that the level never becomes a sealed cleared zone.

## Actor Network

- Uktarl <-> Harria: former lovers and internal rivals; each benefits from the other's removal.
- Undertakers -> newcomers: prey and revenue source.
- Xanathar -> Undertakers: target for infiltration/control, temporarily checked by Harria's flesh golem.
- Organized factions -> predators: their presence indirectly limits predator expansion.

The network is a decision aid, not player-facing exposition. NPC testimony may be biased or incomplete.

## NPC Accountability

This level owns every NPC currently operating here. The actors below preload because their motives shape the level before the player meets them. Any other named NPC in a keyed room must be instantiated from that room's source **before** the scene is run, using the full NPC state required by `LEVEL_LAYER_CONTRACT.md`. Once instantiated, that NPC persists.

### Uktarl Krannoc

**Motive:** Take sole control of the Undertakers by eliminating Harria while continuing to profit from adventurers.  
**Plan if unopposed:** Probe newcomers for money or usefulness; maneuver others against Harria.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Harria Valashtar

**Motive:** Eliminate Uktarl and take control of the Undertakers; use her flesh golem as leverage.  
**Plan if unopposed:** Consolidate the gang around herself and exploit anyone she can.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Halleth Garke

**Motive:** Avenge his murder by the Fine Fellows of Daggerford.  
**Plan if unopposed:** Track surviving former companions across Levels 1–2 until vengeance is complete.  
**Runtime:** Track current location/status, what this NPC knows, relationships, attitude to the player, promises/debts, and any changes to the plan caused by play.

### Room-scoped NPC audit

Before presenting any keyed area on this level:

1. Retrieve the full keyed-room source.
2. Identify every named or individually characterized NPC present or able to enter the scene.
3. Instantiate their motive state before choosing dialogue or action.
4. If the source gives no individual motive, inherit the relevant faction/role motive plus self-preservation and immediate situational needs.
5. Never collapse a named NPC back into generic faction behavior after they have acquired history with the player.

## Story Anchor Rooms / Scenes

- Area 1: Entry Well — arrival and first proof that the dungeon is occupied.
- Areas 6–8 — Undertakers' territory and leadership feud.
- Areas 23, 28, 39 — Xanathar watch posts; show organized control rather than random monsters.
- Area 27: Hidden Demiplane — Halaster simulacrum; automated through-line contact.
- Area 29: Eye See You! — primary first Halaster observation beat.
- Area 37: Map Room — Halleth/Fine Fellows thread.

## Level State That Must Persist

- Undertakers leadership and survival
- Xanathar watch-post strength
- Predator pressure after factions are removed
- Halleth vengeance status
- Halaster first-observation status

- current story-engine escalation state
- active actor next-actions that can continue off-screen
- unresolved pressure points and delayed consequences

## Cross-Level Continuity

- Halleth and the Fine Fellows continue onto Level 2.
- The defective shield guardian's amulet is on Level 4.
- Xanathar pressure connects directly to Levels 2–3 and Skullport.
- Halaster first-observation state feeds the campaign through-line.

## Halaster Through-Line

First sighting only. Establish that the dungeon can watch. No personalized villain relationship yet.

Use the exact contact/observation scheduling rules in `HALASTER_THROUGH_LINE_LAYER.md`; this paragraph only explains this level's function in that larger line.

## Departure / Aftermath

Removing the Undertakers opens their territory to other forces. Removing Xanathar makes the floor temporarily safer from the guild but frees predators to expand. New adventurers continue entering from the Yawning Portal.

At departure, write surviving NPCs' next plans. If an NPC follows the player, moves to another level, or becomes campaign-significant, move the same stable NPC record rather than creating a new copy.

## Visual Asset Binding

**Asset registry key:** `levels.01`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/01-001.monster.png`

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