# Executable runtime ground-truth audit — 2026-10-07

**Repository:** `radarsaint/dnd-solo`  
**Audited main:** `e3a5e9908357441051df24dac8086d8d4c7f26f5`  
**Test result at audit:** 813 tests, OK.

## Central finding

Live `main` is a chat-hosted Python/SQLite runtime that has generalized substantially beyond the old Area 6c prototype.

It is not yet evidence that Kit is a generalized excellent DM.

## Executable turn shape

Live chat:
`start -> prepare --one-pass -> model decision/performance -> complete`

Staged evaluation remains reachable:
`prepare -> decide -> finish`

The runtime persists source/state, snapshots, immutable ledger events, committed Kit turns, pending turns, revisions, and telemetry.

Python handles bounded intent routing, checks, tolls, card procedures, minimal combat, claims/knowers, agendas, attitudes, hidden-information guards, manifests, retry/idempotency, and some state mutation.

Kit/model supplies private judgment and public performance plus a bounded validated set of canon/state proposals.

`--table-talk` is a distinct runtime path.

## Important limits

- Area 6c remains the only richly authored room on current main.
- The watchroom is synthetic; 17a is sparse.
- General room loading is built.
- General adventure-source retrieval/source-to-room authoring is not on main.
- Natural-language routing still relies heavily on regex classification.
- Unsupported physical actions and out-of-combat spells can still become `PendingRuling`.
- Social mechanics beneath performance are intentionally simple.
- Several open runtime PRs overlap.
- Visual PRs #111 and #112 appear to be competing implementations.
- The in-repo BFDM mirror is stale relative to the canonical BFDM repository.

## Test interpretation

The 813 tests protect mechanical contracts.

They do not establish:
- good judgment;
- compelling NPCs;
- satisfying pacing;
- entertaining narration;
- current player-facing quality;
- generalized room quality.

A turn can pass all guards and still be poor D&D.

## Context implication

The runtime already assembles substantial context. Future cognition work should not assume that better intelligence follows from simply adding more material to the packet.

## Product-level conclusion

> Kit has a substantially generalized runtime substrate. Generalized excellent play is not yet demonstrated.

This audit should be read together with the 2026-10-07 quality/failure-localization audit, BFDM Work-readiness audit, and project-truth contradiction audit.
