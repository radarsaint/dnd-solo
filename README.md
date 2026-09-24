# D&D Solo Runtime

Canonical development repository for the D&D solo-DM project.

This repository separates the project into layers so campaign content, runtime behavior, player-facing presentation, assets, and test material can evolve independently without turning into one giant prompt or design document.

## Current state

The DM personality work now has a canonical live contract and a separate development pipeline:

- `docs/personality/dm-personality-core.md` — the compact project-wide answer to **who the DM is**. This is the live personality dependency that should be available to any chat or runtime surface.
- `docs/personality/dm-personality-development.md` — the workshop/test/promotion process used to improve that core. It is development guidance, not extra live personality instruction.
- `docs/personality/dm-personality-layer-v0.1.md` — the earlier long-form design exploration. Keep it as design history/reference; do not treat all 816 lines as the active personality prompt.

The technical runtime should integrate against the compact core rather than duplicating personality prose.

## Repository map

- `docs/personality/` — canonical DM personality, development process, appetites, pillar biases, table presence, and personality design history.
- `docs/architecture/` — runtime boundaries, data flow, interfaces, and integration decisions.
- `docs/campaign/` — campaign-specific through-lines and authored concerns; campaign content stays separate from the generic DM runtime.
- `docs/decisions/` — short architecture decision records.
- `runtime/` — implementation code once the technical runtime is brought into this repo.
- `assets/maps/` — map manifest and eventually map files or stable external references.
- `assets/art/` — art manifest and eventually art files or stable external references.
- `tests/scenarios/` — table-situation tests used to validate DM behavior.
- `state/` — project status, migration notes, and workstream tracking.
- `scripts/` — indexing/validation utilities.

## Design rule

The DM is not implemented as a bag of witty lines. The personality core defines persistent wants, tastes, boundaries, pillar biases, and selective table presence. Runtime behavior should emerge from those stable preferences interacting with the actual scene, campaign state, NPC motives, adjudication, and player behavior.

The personality core does **not** override source truth, rules, map geometry, hidden-information boundaries, NPC state, or campaign state.

## Immediate integration order

1. Load `dm-personality-core.md` as a stable project-wide dependency for DM-facing play and DM-behavior work.
2. Keep `dm-personality-development.md` outside ordinary live play; use it only when deliberately tuning/testing the personality.
3. Bring in the technical runtime without merging campaign-specific logic into the generic DM layer.
4. Index maps and visual assets through manifests with stable IDs.
5. Add campaign/runtime source ingestion behind explicit source manifests.
6. Build scenario tests for exploration, social play, combat, investigation, loot, downtime, shenanigans, and long-term through-line behavior.
7. Promote personality changes only after repeated failures are diagnosed and regression-tested.
