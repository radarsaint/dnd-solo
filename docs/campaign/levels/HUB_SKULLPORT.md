# Skullport — Hub DM Layer

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Dungeon settlement / recurring hub  
**Source scope:** Skullport  
**Depends on:** `LEVEL_LAYER_CONTRACT.md`, campaign state

## What Skullport Is About

Skullport is the dungeon's damaged civilization layer: a hidden settlement under Xanathar's sway where adventurers can resupply, gather information, make contacts, and become entangled in criminal power.

It is not a safe-room reset. People live here under coercion, protection rackets, scarcity, and old magical remnants. The town should feel politically different depending on what the player has done on Levels 1–3.

## NPC Accountability

Skullport owns every NPC currently living or operating here. Named shopkeepers, agents, prisoners, informants, and faction members must receive persistent motive state when their location becomes relevant.

### Sundeth
**Motive:** Maintain Xanathar's military control of Skull Island and its approaches.  
**Plan if unopposed:** Keep the fortress garrison disciplined, defend access, and enforce guild power through overwhelming force.  
**Runtime:** Track fortress strength, alert state, losses, prisoners, and whether Sundeth knows the player's reputation.

### Cal'al Claddani
**Motive:** Keep the Flagon and the Dragon functioning while surviving Skullport's power structure; honor the relationship that led her to shelter and heal a Harper agent.  
**Plan if unopposed:** Continue operating discreetly and avoid drawing unnecessary Xanathar attention.  
**Persistent hook:** Recipient of Threestrings' payment; can anchor the Harper relationship in Skullport.

### Hlool
**Motive:** Immediate survival and food.  
**Plan if unopposed:** Remain near the river and scavenge.  
**Runtime:** If helped, Hlool's gratitude has a concrete source-defined response rather than generic friendliness.

### Droon Stonedark
**Motive:** Protect his own interests and keep dangerous information about Clan Ironeye from outsiders.  
**Plan if unopposed:** Deny useful knowledge and continue business under Skullport conditions.

### Gharz Stonedark
**Motive:** Run the Worm's Gullet under Xanathar's imposed order with little concern for patrons beyond profit/control.  
**Plan if unopposed:** Keep the restaurant operating through kobold labor and whatever ingredients are available.

### Room-scoped NPC audit
Before any named Skullport NPC enters play, retrieve the full keyed location and instantiate the standard NPC motive record. This is especially important for shopkeepers and service NPCs: they are people with survival incentives, loyalties, prices, fears, and knowledge, not vending interfaces.

## Faction / Population State

Track:
- Xanathar control of Skull Island;
- visible Xanathar pressure in town;
- condition of businesses and supply;
- Harper access / Dalagor's Fortress if established;
- relationships created by Level 3 outcomes;
- the thirteen flameskulls as ancient, unstable claimants to the town's identity;
- routes to Waterdeep, Level 3, and deeper Undermountain known to the player.

## Story Anchor Scenes

- Arrival from Level 3 / River Sargauth — transition from wilderness-war to settlement.
- Skull Island — visible military power of Xanathar.
- The Flagon and the Dragon — payoff for the Harper debt and possible recurring contact.
- Shops and inns — resource play with people who have motives and constraints.
- Flameskull encounters — old Skullport beneath current Xanathar rule.
- Clan Ironeye inquiries — cross-level bridge to Level 6.
- Return visits — NPCs should remember transactions, threats, favors, and reputation.

## Halaster Through-Line

No forced Halaster appearance. Skullport demonstrates that whole societies exist inside the ecosystem under his dungeon without him micromanaging them.

## Visual Asset Binding

**Asset registry key:** `hubs.skullport`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

Skullport's three canonical DM/player map pairs are resolved through `docs/architecture/runtime/MAP_INDEX.md`:
- Skull Island (`24.01`)
- Lower and Middle Levels (`24.02`)
- Upper Level (`24.03`)

No Skullport-specific scene art is indexed yet. DM maps remain private geometry references; player maps remain knowledge-gated. Future Skullport art should be added under `hubs.skullport.art` rather than treated as source evidence.

## Departure / Return State

Skullport is a recurring hub. Never reset it to its printed starting state on return.

Record:
- merchants/contacts alive and disposition;
- faction violence;
- prices or shortages materially changed by events;
- outstanding debts/favors;
- discovered routes;
- Xanathar awareness of the player;
- NPCs who left Skullport for another level or the surface.