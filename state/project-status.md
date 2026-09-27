# Project Status

## Active workstreams

### DM personality / behavior
Status: canonical core and area 6c personality protocol captured. The character-onboarding test and a short area 6c room test have been reviewed; a multi-turn preference test is still pending.

The current document defines identity, core appetites, pillar weighting, appetite resolution, inhibition rules, stakes telegraphing, NPC performance, visible DM presence, player relationship, character relationship, and self-evaluation.

The onboarding test found that Kit engaged with a player-created character motive and could stand by a ruling, then reconsider it when explicitly invited. It also found unsolicited advice, rushing ahead of the player's current task, a weak campaign opening, and generic banter. The next behavior pass should focus on interaction-state detection, restraint, a distinct table voice, and a causal handoff into play. See `docs/WHAT_WE_ARE_BUILDING.md` for the plain-English overview.

The [Nik room test](../tests/playtests/2026-09-26-area-06c-nik.md) failed more directly: an 81-second wait produced a basic room opening and a flat toll exchange. The player described Kit as mechanically aware but still “an it, not a she,” then noted the dealer had no appreciable voice change, longer improvised invitation, or readable story promise. An Insight ruling was given in chat without being saved to the backend. The next live pass must test expressed personality and persistence while measuring end-to-end speed.

### Technical DM runtime
Status: SQLite source/state backend and a bounded area 6c Kit play loop implemented on `kit-area-06c-testbed`.

The play loop separates source-grounded room adjudication, a private Kit decision, and public performance. It persists world changes, a Kit episode, and the transcript atomically. In a tool-enabled chat, the staged `prepare`, `decide`, and `finish` path runs without a separate API key. An optional `prepare --one-pass` and `complete` path reduces model/tool round trips for live chat, with weaker causal evidence; it has not yet been timed in a live test. A [reusable scene-discernment step](../docs/architecture/scene-discernment.md) makes Kit select how the player's current bid, eligible story pressure, a live actor's established aim, and her own appraisal connect. Area 6c then supplies one actor card and a saved scene entry as performance inputs. These are structural changes, not a demonstrated improvement in play. Full rules, combat, NPC belief updates, and measured entertainment quality remain open.

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

The current slice uses the area 6c fixture and a map reference. It does not load maps/assets from manifest IDs or execute tactical opposition. First test the onboarding failures and multi-turn room behavior with a real character. Compare player-facing runs, memory ablations, and eventually experienced human DMs before claiming that Kit's personality succeeds.
