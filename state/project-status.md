# Project Status

## Active workstreams

### DM personality / behavior
Status: v0.1 captured and ready for scenario testing.

The current document defines identity, core appetites, pillar weighting, appetite resolution, inhibition rules, stakes telegraphing, NPC performance, visible DM presence, player relationship, character relationship, and self-evaluation.

### Technical DM runtime
Status: in development in a separate project conversation.

Action: migrate implementation into `runtime/` when the current technical branch/code is available. Preserve the separation between runtime machinery and personality/campaign data.

### Player-facing UX/UI
Status: active design.

Action: define explicit presentation contracts once technical message/event shapes are known.

### Maps and visual assets
Status: asset collection/indexing underway in another project conversation.

Action: add files/references and stable IDs to `assets/maps/index.json` and `assets/art/index.json`. Runtime should request assets by stable ID and semantic role, not by chat attachment position.

### Campaign content
Status: campaign-specific runtime concerns are being examined separately from the generic DM personality.

Action: establish a campaign manifest and through-line schema before importing large adventure/source collections.

## Next integration milestone

A playable vertical slice should prove this path:

source material -> current scene/state -> NPC/opposition execution -> personality arbitration -> adjudication -> player-facing response -> state update

with maps/assets retrieved by stable manifest IDs.
