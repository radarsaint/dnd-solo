# Visual Asset Integration

This document records the visual-asset integration completed in the ChatGPT project and translates it into repository terms.

## Architectural decision

Maps and ordinary artwork are related presentation resources, but they are not one authority system.

- `assets/maps/index.json` owns stable map identity and the DM/player map pairing used by the runtime.
- `assets/art/index.json` owns level/scene art and entity-reference art.
- `assets/handouts/index.json` owns reveal-gated handout sheets.
- published adventure text owns room contents, creatures, traps, objects, scripted conditions, and keyed facts.
- current runtime state owns changes caused by play.

Do not collapse those responsibilities together.

## What the project pass established

The completed project-library pass:

1. sorted canonical map files into numbered-level and Skullport collections;
2. preserved separate DM and player variants;
3. indexed one DM/player pair for every numbered level, Levels 1–23;
4. indexed three additional DM/player pairs for Skullport;
5. separated level/scene art from creature/NPC reference art;
6. separated handout/deck sheets from ordinary illustrations;
7. normalized obvious filename typos at the persistent destination without altering image content;
8. established stable reveal rules so uploaded art cannot leak hidden information;
9. bound each numbered level to a stable visual key in the project runtime;
10. identified the reveal/render pipeline as the next unfinished visual-system task.

## Repository layout

```text
assets/
├── maps/
│   ├── index.json
│   ├── levels/
│   └── skullport/
├── art/
│   ├── index.json
│   ├── levels/
│   └── creatures/
└── handouts/
    └── index.json
```

The manifests are the durable representation of the indexing work. Binary asset migration may happen independently, but it must preserve the stable IDs, roles, DM/player distinction, and repo-relative paths defined here.

## Current indexed inventory

- 52 map files: 23 numbered-level DM/player pairs plus 3 Skullport DM/player pairs.
- 25 level/scene art files.
- 8 creature/NPC reference-art files.
- 2 handout/deck sheets.
- Level-specific scene art for Levels 20–23 is still pending additional uploads; their canonical map bindings are already complete.

## Map authority

### DM map

The DM map is private runtime topology and is authoritative for original spatial geometry:

- room placement;
- boundaries;
- adjacency;
- corridors;
- doors;
- secret passages;
- stairs;
- shafts;
- mapped gates;
- vertical relationships;
- printed scale.

When a canonical DM map exists, the runtime must not improvise a replacement layout.

### Player map

The player map is a presentation base, not the player's knowledge ledger.

An unlabeled player map can still contain unreached rooms or hidden geometry. Therefore player-map presentation must be gated by current knowledge/spatial state.

The eventual map renderer should derive visible topology from the player's reveal graph rather than simply displaying the complete player-map image.

## Division of factual authority

When visual assets, adventure source, and live state interact:

- **DM map:** original geometry.
- **Keyed adventure text:** room contents, creatures, traps, objects, encounter rules, scripted conditions.
- **Current campaign/spatial state:** physical changes produced by play.
- **Campaign/level behavior layer:** why the scene matters, active plans, reactions, consequences.
- **Visual manifests:** asset identity, path, semantic role, and reveal policy.

Artwork never creates canon by itself.

## Runtime resolution

For a location:

1. identify the level or hub from runtime state;
2. resolve its canonical map entry from `assets/maps/index.json`;
3. use the DM map for private geometry;
4. use the keyed source text for the contents of the active keyed area;
5. apply recorded spatial/campaign changes;
6. present only player-known topology.

For scene or level art:

1. resolve the current level;
2. inspect `assets/art/index.json`;
3. determine whether the depicted subject is legitimately perceivable;
4. reject any image that would reveal hidden information.

For creature/NPC art:

1. establish identity from source/state;
2. resolve the entity ID;
3. reveal only after legitimate encounter or knowledge.

For handouts:

1. establish the exact source/state reveal trigger;
2. determine whether one component or the entire sheet was earned;
3. reveal only the earned information.

## Extending the system

### New level art

Add the binary under `assets/art/levels/`, append a stable entry to `assets/art/index.json`, and preserve reveal gating.

### New creature/NPC art

Add the binary under `assets/art/creatures/`, assign a stable entity ID, and index it by identity rather than presumed level.

### New handouts

Add the binary under `assets/handouts/`, define its reveal rule, and state whether the asset is atomic or a composite sheet.

### New or replacement maps

Map changes require more care because geometry is authoritative. Add or replace the DM/player pair under `assets/maps/`, verify level/region identity, and update `assets/maps/index.json` without silently changing current campaign state.

## Do not redo this work

Future runtime work should assume these decisions are already made unless a source file proves otherwise:

- map variants are DM/player paired;
- all Levels 1–23 and all three Skullport regions have deterministic map identities;
- art is separated into level-scene and entity-reference roles;
- handouts have their own reveal-gated manifest;
- player maps are knowledge-gated;
- artwork is subordinate to source and current state;
- a second independent visual registry should not be created.

The next visual-system problem is presentation: masking/cropping player maps to known topology and extracting individual cards/runes from composite sheets without leaking unrevealed information.
