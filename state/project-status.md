# Project Status

## Active workstreams

### DM personality / behavior
Status: v0.1 captured and ready for scenario testing.

The current document defines identity, core appetites, pillar weighting, appetite resolution, inhibition rules, stakes telegraphing, NPC performance, visible DM presence, player relationship, character relationship, and self-evaluation.

### Personality backend interface
Status: alpha contract represented in-repo.

`docs/architecture/runtime/DM_PERSONALITY_BACKEND_CONTRACT.md` defines the bounded `dm_context` packet the personality consumes. The backend supplies truth/state/evidence; personality selects emphasis among valid possibilities.

Required persistent support includes separate player-model, player-character pattern, and recent-rhythm state.

### Technical DM runtime
Status: architecture documented; persistence/implementation remains in development.

The current runtime specification is in `docs/architecture/runtime/DND_SOLO_RUNTIME.md`. The next implementation work is concrete save schemas, state persistence, event-ledger storage, revealed-topology persistence, and executable context assembly.

### Player-facing UX/UI
Status: active design.

Action: integrate presentation contracts against the runtime's eventual event/message shapes.

### Maps and visual assets
Status: asset collection/indexing is active in another project conversation.

The runtime-side geometry contract is already documented. `docs/architecture/runtime/MAP_INDEX.md` binds levels to canonical DM/player maps and room numbering. Canonical DM geometry is fixed; runtime narration may not invent or reroute mapped space.

The asset workstream should continue populating `assets/maps/index.json` with stable IDs and repository paths.

### Campaign content
Status: first campaign backend is represented in-repo.

Added:
- Halaster behavior layer;
- Halaster campaign through-line layer;
- shared level-story-engine contract;
- game setup layer;
- Skullport hub layer;
- all 23 numbered *Dungeon of the Mad Mage* level layers.

Each level owns its active NPC motives, story equilibrium, active motion, pressure points, reaction rules, escalation state, outcomes, player-facing evidence, cross-level consequences, and canonical map binding.

## Next integration milestone

A playable vertical slice should prove this path:

source + canonical map + persistent state
-> level/NPC/opposition execution
-> dm_context assembly
-> personality arbitration
-> adjudication/presentation
-> state + event/rhythm update

The first vertical slice should use a real keyed room and its level story engine rather than a synthetic demo scene.
