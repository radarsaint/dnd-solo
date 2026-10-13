# Project Status

**Updated:** 2026-10-07  
**Executable state audited against:** `main @ e3a5e9908357441051df24dac8086d8d4c7f26f5`

For fast current orientation, read [`PROJECT_CONTROL.md`](../PROJECT_CONTROL.md). For cross-AI work, read [`COORDINATION.md`](../COORDINATION.md).

## Current runtime

The runtime is no longer accurately described as a bounded Area 6c prototype.

Current `main` provides a chat-hosted SQLite runtime with:

- live `start -> prepare --one-pass -> complete`;
- staged `prepare -> decide -> finish` for evaluation;
- arbitrary room-file mounting and room chaining;
- persistent snapshots, immutable ledger events, Kit turns, pending turns, revisions, and telemetry;
- hidden-information/player-knowledge projection;
- bounded natural-language routing;
- checks, tolls, card procedures, minimal combat, claims/knowers, agendas, attitudes, Kit plans, and limited Kit memory;
- manifest/hash/rehydration support;
- retry/idempotency and stale-turn protection;
- explicit table-talk mode.

The audited suite is **813 tests green**.

This means the runtime substrate has generalized substantially.

It does **not** mean Kit is already a generalized good DM.

## Current content/evidence limit

Area 6c remains the only richly authored room on current `main`.

The watchroom is synthetic. The 17a room is sparse. Mounting a room proves loader/runtime compatibility, not satisfying play.

No committed room file on the inspected tree contains a `room_link`. Chaining is implemented and tested with temporary copies, not with an authored multi-room campaign already in the repo. Source-to-room authoring (untouched keyed adventure text to the next playable room) is not built. PR #100 is proposed, not landed.

Current evidence therefore supports:

> generalized runtime substrate; generalized excellent player experience not demonstrated.

Historical Area 6c playtests remain useful evidence of failure, but they must not be treated as a complete description of current implementation.

## Player-facing quality

The product target is the complete experience of playing and building D&D with Kit.

Green backend tests, valid state, good private reasoning, correct source use, or distinctive prose are component successes. They do not independently establish product success.

The next quality evidence must increasingly come from current-main end-to-end play across materially different situations and from evaluation that can distinguish:

- intent/routing failure;
- adjudication failure;
- state/continuity failure;
- NPC cognition failure;
- performance/expression failure;
- latency/tool friction;
- integration failures where individually working components combine into a worse experience.

## Current technical caveats

The 2026-10-07 executable audit found several important current facts:

- `room_intent()` still relies heavily on regex routing;
- unsupported physical actions and out-of-combat spells can still become `PendingRuling`;
- model-authored changes can become durable canon/state after validation, so “the model cannot write world state” is not a correct blanket description;
- table talk is a distinct runtime path, not the same thing as simply addressing Kit by name;
- the in-repo BFDM mirror is not canonical research truth;
- several open runtime PRs overlap and require explicit stack/ownership resolution before broad integration;
- visual runtime PRs #111 and #112 appear to compete.

## Current work routing

Default runtime integration owner: **Skippy / Grok Bots**.

A separate Grok Build audit established executable ground truth. Parallel GPT audits are examining project contradictions, player-facing quality, and BFDM research readiness. A separate GPT is handling corpus mechanical preparation.

Do not duplicate those temporary workstreams.

## Documentation status

`START_HERE.md` and `AGENTS.md` are the live-operation entry points.

`PROJECT_CONTROL.md` is the development orientation entry point.

Older architecture documents may describe an earlier slice. They are history/reference unless current control or executable code confirms them.

`docs/collab/BOARD.md` is history, not the current task queue.
