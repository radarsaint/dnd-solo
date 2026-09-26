# Project Status

## Active workstreams

### DM personality / behavior
Status: canonical core and area 6c personality protocol captured; live model evaluation is still pending.

The current document defines identity, core appetites, pillar weighting, appetite resolution, inhibition rules, stakes telegraphing, NPC performance, visible DM presence, player relationship, character relationship, and self-evaluation.

### Technical DM runtime
Status: SQLite source/state backend and a bounded area 6c Kit play loop implemented on `kit-area-06c-testbed`.

The play loop separates source-grounded room adjudication, a private Kit decision, and a public performance call. It persists world changes, a Kit episode, and the transcript atomically. See `docs/architecture/kit-06c-play-slice.md`. Full rules, combat, and measured entertainment quality remain open.

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

A live playtest should now probe this path:

source material -> current scene/state -> bounded adjudication -> Kit event appraisal and move -> player-facing performance -> validated state update

The current slice uses the area 6c fixture and a map reference. It does not load maps/assets from manifest IDs or execute tactical opposition. Compare player-facing runs, memory ablations, and eventually experienced human DMs before claiming that Kit's personality succeeds.
