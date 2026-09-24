# Game Setup Layer — Descent into Undermountain

**Campaign:** Waterdeep: Dungeon of the Mad Mage  
**Layer Type:** Campaign setup / surface anchor  
**Source scope:** Undermountain Overview, Yawning Portal, Adventure Hooks, Undermountain Secrets, Dungeon Features  
**Depends on:** `DND_SOLO_RUNTIME.md`, `HALASTER_DM_LAYER.md`, `HALASTER_THROUGH_LINE_LAYER.md`

## Setup Story

The campaign begins with a deliberate descent from Waterdeep into a place that has swallowed adventurers for centuries.

The setup must establish:
- the Yawning Portal as the recurring surface anchor;
- Undermountain as a known but poorly understood place with a reputation, economy, and history;
- a concrete reason for this player character to descend;
- at least one external relationship that can matter when the character returns;
- the fact that Halaster is a real figure behind the dungeon without front-loading his full story;
- Jhesiyra as hidden campaign state, not player-facing exposition.

Do not rush through setup as a character-sheet preamble. The descent should mean something to the player before the first room.

## Required Setup State

```yaml
campaign_setup:
  player_reason_for_descent:
  accepted_starting_quests: []
  declined_starting_quests: []
  surface_contacts: {}
  yawning_portal_relationship:
  known_undermountain_rumors: []
  halaster_current_preoccupation:
  jhesiyra_hidden_state: active
  first_descent_complete: false
```

## NPC Accountability

### Durnan
**Motive:** Keep the Yawning Portal functioning and remain the hard-practical gatekeeper to Undermountain.  
**Immediate goal:** Run the winch, charge the toll, assess who is going down, and continue the tavern culture built around the dungeon.  
**Knowledge:** Deep personal experience with Undermountain; suspects serious dangers such as the later telepathic threat.  
**Constraint:** He does not become the player's quest nanny. He lets people choose to descend.  
**Persistent use:** Durnan is a recurring witness to who leaves, who returns, and how the player changes.

### Obaya Uday
**Motive:** Acquire valuable magic items and spellbooks for Wakanga O'tamu.  
**Immediate goal:** Establish a profitable relationship with adventurers capable of returning alive.  
**Plan if unopposed:** Buy qualifying items until her procurement target is met, then return to Chult.  
**Player relationship:** Transactional but potentially reliable; her stated prices are not a haggling minigame.

### Mattrim "Threestrings" Mereg
**Motive:** Maintain his Harper cover while supporting Harper interests.  
**Immediate goal:** Get payment safely to Cal'al Claddani in Skullport.  
**Plan if unopposed:** Continue using the Yawning Portal to cultivate information and contacts.  
**Constraint:** His apparent tavern-musician identity is cover.

### Esvele Rosznar
**Motive:** Protect the Rosznar family from further disgrace and learn what happened to her brother Kressando.  
**Immediate goal:** Get the player to look for Kressando without publicly exposing the family's problem.  
**Plan if unopposed:** Continue discreet investigation and damage control.  
**Persistent consequence:** The player's handling of Kressando's fate affects a real surface relationship.

### Volothamp Geddarm
**Motive:** Curiosity, stories, reputation, and interest in Undermountain lore.  
**Immediate goal:** Encourage the Throne of the Coronal lead and remain connected to interesting discoveries.  
**Use:** Volo can connect later quest-givers but must not become a universal exposition device.

### Future quest-givers
Instantiate when prerequisites are met:
- **Joroth Brighthelm:** recover the Eye of the Spider to strengthen Waterdeep/Mirabar interests.
- **Jalester Silvermane:** obtain a Runestone fragment for Laeral while concealing her private need.
- **Lady Wylynd Moonstar / Helion Moonstar:** resolve the family debt surrounding Glyster/Umbraxakar.
- **Durnan:** identify and end the telepathic threat from Seadeeps if hostile.

### Jhesiyra Kestellharp — hidden persistent NPC
**Motive:** Keep viable adventurers alive long enough to defeat Halaster, then seize control of Undermountain.  
**Immediate goal:** Remain undetected by Halaster and use her limited control of gates/warnings selectively.  
**Constraint:** She cannot become a conversational guide. Her communication and intervention remain source-limited.  
**State location:** Campaign layer, not a normal room NPC.

## Setup Scenes

### Yawning Portal arrival
Give the player enough interaction to establish Durnan, the well, the culture around expeditions, and available hooks.

### Hook selection
Present hooks through NPCs with motives, not as a quest-board dump. The player may accept none, some, or all.

### Rumors and secrets
Use the source procedure. Reliable secrets and tavern stories are information with provenance; do not collapse rumor into fact.

### The descent
The winch ride is the threshold between surface play and Undermountain. Once the character reaches Level 1 Area 1, hand control to the Level 1 layer.

## Setup Completion

Before the first Level 1 scene:
- player state is loaded;
- personal reason for descent is known;
- accepted hooks are recorded;
- setup NPC relationships exist;
- Halaster has a current preoccupation;
- Halaster attention remains 0 unless the campaign has a source-supported reason otherwise;
- Jhesiyra exists only in hidden state.

## Visual Asset Binding

**Asset registry key:** `levels.00`  
**Registry:** `/Dnd solo/Assets/ASSET_REGISTRY.json`

- Level art: `/Dnd solo/Assets/Art/Levels/00-001.yawning-portal.png`
- Canonical map: none indexed for Level 0 / game setup

Use the Yawning Portal art only when that location is legitimately in scene. Art illustrates source/state and does not establish hidden facts. Map geometry begins with Level 1 and is resolved through `MAP_INDEX.md`.
