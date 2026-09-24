# Visual Asset Migration Status

**Date:** 2026-09-23  
**Source:** D&D Solo ChatGPT project Library integration pass

The project's visual indexing work is now represented in this repository by:

- `assets/maps/index.json`
- `assets/art/index.json`
- `assets/handouts/index.json`
- `docs/architecture/visual-asset-integration.md`
- `docs/decisions/0002-map-and-visual-authority.md`

## Indexed inventory

- 52 map files.
- 25 level/scene art files.
- 8 creature/NPC reference files.
- 2 composite handout sheets.

The manifests preserve the stable IDs, canonical DM/player distinction, repo-relative destinations, and reveal rules established in the project.

## Binary migration

The repository manifests are authoritative for where the indexed binaries belong. If the actual image files are not yet present on the branch being integrated, migrate them into the exact paths named in the manifests rather than renaming or reclassifying them independently.

Levels 20–23 currently have canonical map entries but no level-specific scene-art entries. This is intentional until additional files are supplied.

## Next implementation task

Build the player-facing reveal/render pipeline:

- derive visible topology from player knowledge;
- mask/crop player maps instead of exposing full undiscovered layouts;
- expose only earned components from composite rune/secret sheets;
- keep DM maps completely private.
