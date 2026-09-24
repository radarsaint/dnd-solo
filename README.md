# D&D Solo Runtime

Canonical development repository for the D&D solo-DM project.

This repository separates the project into layers so campaign content, runtime behavior, player-facing presentation, assets, and test material can evolve independently without turning into one giant prompt or design document.

## Current state

The behavioral/personality layer has a testable v0.1 specification.

The backend architecture now also includes:
- a personality-backend `dm_context` contract;
- Halaster behavior and campaign through-line layers;
- a causal story-engine contract for dungeon levels;
- all 23 *Dungeon of the Mad Mage* level layers;
- fixed-geometry map bindings and room-number coordination;
- runtime architecture through the 0.3.0 backend milestone.

Technical persistence and executable runtime code remain under development.

## Repository map

- `docs/personality/` — DM personality, appetites, priorities, inhibition rules, table presence.
- `docs/architecture/` — runtime boundaries, data flow, interfaces, map/geometry contracts, and integration decisions.
- `docs/architecture/runtime/` — detailed runtime specification, personality-backend contract, map registry, and runtime change records.
- `docs/campaign/` — campaign-specific through-lines and authored concerns.
- `docs/campaign/levels/` — shared level contract plus game setup, Skullport, and the 23 numbered Mad Mage story-engine layers.
- `docs/decisions/` — short architecture decision records.
- `runtime/` — implementation code once the technical runtime is brought into this repo.
- `assets/maps/` — map manifest and canonical map assets/stable references.
- `assets/art/` — art manifest and art files/stable references.
- `tests/scenarios/` — table-situation tests used to validate DM behavior.
- `state/` — project status, migration notes, and workstream tracking.
- `scripts/` — indexing/validation utilities.

## Design rule

The DM is not implemented as a bag of witty lines. The personality layer defines persistent desires and conflicts; behavior emerges from choosing which appetite leads a response under the current pillar of play.

The backend does the other half of that job: it supplies the personality with reliable current truth, NPC motives, campaign/level motion, geometry, stakes, affordances, callbacks, and player/character history without manufacturing drama.

## Runtime boundary

Backend:

`source + map + state -> valid possibilities -> dm_context`

Personality:

`dm_context -> emphasis / table presence / preference among valid possibilities`

Then:

`adjudication + presentation -> persistent state update`

## Immediate integration order

1. Keep personality and backend contracts separately versioned.
2. Bring concrete runtime/state implementation into `runtime/`.
3. Finish stable map/art manifests and repository asset paths.
4. Implement save/event/revealed-topology persistence.
5. Build a real Mad Mage vertical slice using one level story engine, canonical DM map, keyed room source, NPC state, and personality arbitration.
6. Add scenario tests across exploration, social play, combat, investigation, loot, downtime, shenanigans, and long-term through-line behavior.
