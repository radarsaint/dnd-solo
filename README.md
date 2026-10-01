# D&D Solo Runtime

Canonical development repository for the D&D solo-DM project.

This repository separates the project into layers so campaign content, runtime behavior, player-facing presentation, assets, and test material can evolve independently without turning into one giant prompt or design document.

## In plain English

We are building Kitiara (DM Kit), an AI Dungeon Master with a recognizable personality and the judgment to run a solo campaign. The goal is a DM a player would eventually prefer to an experienced human DM. Kit should care about the story and the player, embody NPCs, run fair danger, enjoy surprises, and know when to speak or let the world carry the scene. The [plain-English project outline](docs/WHAT_WE_ARE_BUILDING.md) explains the goal, what is working, the first playtest's failures, and what comes next.

## Current state

The DM personality work now has a canonical live contract and a separate development pipeline:

- `docs/personality/dm-personality-core.md` — the compact project-wide answer to **who the DM is**. This is the live personality dependency that should be available to any chat or runtime surface.
- `docs/personality/dm-personality-development.md` — the workshop/test/promotion process used to improve that core. It is development guidance, not extra live personality instruction.
- `docs/personality/dm-personality-layer-v0.1.md` — the earlier long-form design exploration. Keep it as design history/reference; do not treat all 816 lines as the active personality prompt.

The technical runtime should integrate against the compact core rather than duplicating personality prose.

The [2026-09-30 character development](docs/personality/kit-character-development.md) connects Brendon's campaign craft and novel design decisions to Kit's tastes, emotional range, and voice. The candidate is wired into the core and existing prompts; its demonstrations and [transfer probes](tests/scenarios/modeled-personality-transfer.md) await live preference evaluation.

## Executable state/context prototype

`runtime/state_context.py` implements a small SQLite-backed prototype with atomic event batches, restartable snapshots, a player knowledge projection, fixed fixture topology, and bounded context assembly using the canonical personality core.

Run the automated checks from the repository root:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

See [the state/context prototype guide](docs/architecture/state-context-prototype.md) for the storage boundary. A [bounded area 6c play slice](docs/architecture/kit-06c-play-slice.md) runs Kit's private decision and player-facing performance with atomic persistence. A [reusable scene-discernment contract](docs/architecture/scene-discernment.md) selects the relevant player bid, story pressure, actor goal, and Kit reaction before performance. An assistant with access to this repository can host the room in chat without a separate model choice or API key. The staged path supports a separate decision and performance; an optional one-pass path uses fewer model/tool round trips for live play. The optional standalone `play` CLI uses a model ID and API key. Full D&D adjudication and demonstrated entertainment quality remain open work.

The first source-grounded test scene is [Level 1, area 6c — Uktarl's room](tests/scenarios/level-01-area-06c-uktarl.md). Its fixture exercises context and secrecy; six play probes examine whether Kit's event appraisal, chosen moves, and table performance make her personality felt. The [personality backend contract](docs/architecture/runtime/DM_PERSONALITY_BACKEND_CONTRACT.md#cognitive-agent-model-for-kit) records the research grounding for that agent cycle. Character onboarding showed promising engagement and adjudicative backbone alongside restraint and voice problems. The [first live room exchange](tests/playtests/2026-09-26-area-06c-nik.md) failed on speed and expressed personality. The [voice-spec branch test](tests/playtests/2026-09-29-area-06c-voice-spec-nik.md) found somewhat better dialogue, but an incoherent Kit quip and an invented high-card game that ignored the marked-deck cheating opportunity. The [project outline](docs/WHAT_WE_ARE_BUILDING.md) gives the plain-English goal and current scope.

The [claims-and-knowers live test](tests/playtests/2026-09-29-area-06c-claims-nik.md) ran a real card deal and caught cheating, but failed to make the room's purpose evident. NPC momentum, optional activity handling, description, equipment conditions, and chat latency remain quality failures.

The next phase follows an [expressed-performance pipeline](docs/architecture/expressed-performance-pipeline.md) and a [blind area 6c comparison packet](tests/scenarios/expressed-performance-v1.md). **Quality is the current gate**: compare player-facing exchanges on the same accepted situation, promote the behavior that makes Kit and her NPCs worth continuing with, then transfer it to another playable room. Record latency and remove obvious overhead, but do not shorten an earned moment to meet a timing target during this pass.

The [personality implementation audit](docs/personality/kit-personality-implementation.md) corrects a key gap: the core is written and loaded, but Kit's distinctive expressive behavior and longer-lived appetites/relationship dynamics are not yet built or validated. The next comparison tests **Kit's identity**, then NPC and scene performance. [Kit's expression gap](docs/architecture/kit-expression-gap.md) is the build guide for GPT: what the design assumed versus what the code did, the rule that every private decision needs a public carrier the performer receives and the validator can check, a worked example (`reply_to`, `scope`, `kit_focus`), and the next build steps.

## Repository map

- `docs/personality/` — canonical DM personality, development process, appetites, pillar biases, table presence, and personality design history.
- `docs/architecture/` — runtime boundaries, data flow, interfaces, and integration decisions.
- `docs/campaign/` — campaign-specific through-lines and authored concerns; campaign content stays separate from the generic DM runtime.
- `docs/decisions/` — short architecture decision records.
- `runtime/` — executable state/context prototype and future runtime implementation.
- `assets/maps/` — map manifest and eventually map files or stable external references.
- `assets/art/` — art manifest and eventually art files or stable external references.
- `tests/scenarios/` — table-situation tests used to validate DM behavior.
- `state/` — project status, migration notes, and workstream tracking.
- `scripts/` — indexing/validation utilities.

## Design rule

The DM is not implemented as a bag of witty lines. The personality core defines persistent wants, tastes, boundaries, pillar biases, and a vocal but calibrated table presence. Runtime behavior should emerge from those stable preferences interacting with the actual scene, campaign state, NPC motives, adjudication, and player behavior.

The personality core does **not** override source truth, rules, map geometry, hidden-information boundaries, NPC state, or campaign state.

## Immediate integration order

1. Load `dm-personality-core.md` as a stable project-wide dependency for DM-facing play and DM-behavior work.
2. Keep `dm-personality-development.md` outside ordinary live play; use it only when deliberately tuning/testing the personality.
3. Bring in the technical runtime without merging campaign-specific logic into the generic DM layer.
4. Index maps and visual assets through manifests with stable IDs.
5. Add campaign/runtime source ingestion behind explicit source manifests.
6. Build scenario tests for exploration, social play, combat, investigation, loot, downtime, shenanigans, and long-term through-line behavior.
7. Promote personality changes only after repeated failures are diagnosed and regression-tested.
