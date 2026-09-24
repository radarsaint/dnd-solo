# Visual Asset Migration Status

**Date:** 2026-09-23  
**Source:** D&D Solo ChatGPT project Library integration pass

The project's visual indexing work is represented in this repository by:

- `assets/maps/index.json`
- `assets/art/index.json`
- `assets/handouts/index.json`
- `docs/architecture/visual-asset-integration.md`
- `docs/decisions/0002-map-and-visual-authority.md`
- `docs/decisions/0003-private-binary-assets.md`
- `scripts/import_visual_assets.py`

## Indexed inventory

- 52 map files.
- 25 level/scene art files.
- 8 creature/NPC reference files.
- 2 composite handout sheets.
- **87 binary visual assets total.**

The manifests preserve the stable IDs, canonical DM/player distinction, repo-relative destinations, and reveal rules established in the project.

## Private binary pack

Binary migration is complete into the private project asset pack:

- Project Library path: `/Dnd solo/Private Asset Packs/dnd-solo-private-visual-assets.zip`
- Size: approximately 235 MiB
- ZIP SHA-256: `d9cc62b2fba15c73b575a0903c6eb7866152ea3db9e99a31c0777263ca77b9ff`
- Contains all 87 currently indexed image files.
- Contains `SHA256SUMS.txt` with a per-file digest.

The repository is public, so the licensed source binaries are intentionally not published in Git. Instead, `scripts/import_visual_assets.py` verifies and hydrates them into the exact manifest paths for local/runtime use. Those paths are gitignored.

Levels 20–23 currently have canonical map entries but no level-specific scene-art entries. This remains intentional until additional art is supplied.

## Next implementation task

Build the player-facing reveal/render pipeline:

- derive visible topology from player knowledge;
- mask/crop player maps instead of exposing full undiscovered layouts;
- expose only earned components from composite rune/secret sheets;
- keep DM maps completely private.
