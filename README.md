# D&D Solo Runtime

Canonical development repository for the D&D solo-DM project.

This repository separates the project into layers so campaign content, runtime behavior, player-facing presentation, assets, and test material can evolve independently without turning into one giant prompt or design document.

## Current state

The behavioral/personality layer has a testable v0.1 specification. The technical runtime is being developed separately and should integrate against the contracts documented here rather than duplicating personality prose.

## Repository map

- `docs/personality/` — DM personality, appetites, priorities, inhibition rules, table presence.
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

The DM is not implemented as a bag of witty lines. The personality layer defines persistent desires and conflicts; behavior should emerge from choosing which appetite leads a response under the current pillar of play.

## Immediate integration order

1. Preserve the personality layer as a versioned behavioral contract.
2. Bring in the technical runtime without merging campaign-specific logic into the generic DM layer.
3. Index maps and visual assets through manifests with stable IDs.
4. Add campaign/runtime source ingestion behind explicit source manifests.
5. Build scenario tests for exploration, social play, combat, investigation, loot, downtime, shenanigans, and long-term through-line behavior.
6. Only then tune personality based on observed failures in playtests.
