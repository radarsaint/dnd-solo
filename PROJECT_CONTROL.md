# Project Control — DM Kit runtime

**Updated:** 2026-10-07  
**Last runtime truth audit:** `main @ e3a5e9908357441051df24dac8086d8d4c7f26f5`  
**Sibling repo:** `radarsaint/bfdm-corpus`

Read `COORDINATION.md` before substantial cross-agent work.

This file is deliberately short and rewritable. Git history, issues, PRs, and `docs/collab/BOARD.md` preserve history.

## What this repo is

`dnd-solo` is the current executable Kit runtime and player-facing development surface.

It is not the BFDM archive and it is not all future Kit cognition.

## Current executable reality

At the audited commit:

- live chat uses `start` -> `prepare --one-pass` -> `complete`;
- staged `prepare -> decide -> finish` remains reachable for evaluation;
- arbitrary room JSON can mount;
- SQLite persists source/state, revisions, ledger events, Kit turns, pending turns, and telemetry;
- Python handles bounded intent routing, deterministic checks when the player supplies no roll, tolls, card procedures, minimal combat, claims/knowers, agendas, attitudes, hidden-information guards, manifests, retries, and idempotent commits;
- Kit/model supplies private judgment and public performance plus a checked set of canon/state proposals;
- `--table-talk` is a distinct execution path;
- the audited suite is **813 tests green**.

This is materially beyond the old “Area 6c staged prototype” description.

## What is not proven

- Area 6c remains the only richly authored room on current `main`.
- Mounting arbitrary rooms proves loader/general runtime mechanics, not generalized excellent DMing.
- The watchroom is synthetic and 17a is sparse.
- Natural-language routing still relies heavily on regex classification.
- Social mechanics remain bounded/simple under the performance layer.
- Many overview documents lag the executable system.
- Green tests prove mechanical contracts, not that Kit is entertaining or satisfying to play with.

Current product-level statement:

> Kit has a substantially generalized runtime substrate and insufficient evidence of generalized excellent play.

## Product acceptance rule

**Kit is the product. The total experience is the acceptance layer.**

Do not let runtime correctness, judgment, cognition, personality, or any other subsystem become the project goal by proxy.

A feature can pass its own tests and still make Kit worse to use.

## Current engineering coordination

Default runtime integration owner: **Skippy / Grok Bots**.

Current executable audit was performed by Grok Build against the SHA above.

Important unresolved stack questions for Skippy include:

- intended ordering/ownership of overlapping runtime PRs touching `kit_agent.py`;
- whether visual PRs #111 and #112 are alternatives or a sequence;
- whether the accepted outside-combat grab behavior is the current `pc_grab` implementation or the later board ruling;
- retirement of the stale in-repo BFDM mirror;
- which pinned Kit build is actually mounted in external GPT/project environments.

Do not resolve these by guessing from open-PR age.

## Documentation state

This coordination branch refreshes the primary human/agent entry points: `README.md`, `START_HERE.md`, `AGENTS.md`, `docs/WHAT_WE_ARE_BUILDING.md`, `state/project-status.md`, and the collaboration protocol.

Older runtime architecture documents and historical Area 6c wording may still describe prior slices. Treat them as reference/history unless current control or executable code confirms the claim.

Future drift should be handled by rewriting this current-control layer and linking to the commit/PR that changed truth, not by appending another competing handoff.

## Cross-repo rules

Use `bfdm-corpus main` for canonical BFDM source/research state.

Do not use the in-repo corpus mirror as current research truth.

Do not harden derived BFDM claims into runtime behavior merely because they are polished or cited. Active corpus integrity work may downgrade them.

## Current temporary parallel work

Before Friday:

- GPT 1 — project truth / contradiction audit;
- GPT 2 — Kit quality / failure-localization audit;
- GPT 3 — BFDM research-readiness / Work queue;
- Grok Build — executable runtime audit (complete);
- separate GPT — mechanical corpus preparation;
- control-room thread — synthesis and task routing.

These are temporary assignments, not permanent architecture.

## Start points

For live runtime operation: `START_HERE.md` and `AGENTS.md`.

For development orientation: this file, then the owning issue/PR.

For cross-agent protocol: `COORDINATION.md`.

For history only: `docs/collab/BOARD.md`.
