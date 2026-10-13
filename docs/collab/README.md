# Kit collaboration protocol

The project now coordinates across **both** `radarsaint/dnd-solo` and `radarsaint/bfdm-corpus`, and across multiple AI surfaces.

Start with:

1. [`PROJECT_CONTROL.md`](../../PROJECT_CONTROL.md) — short current runtime orientation.
2. [`COORDINATION.md`](../../COORDINATION.md) — cross-repository truth, ownership, staleness, and handoff rules.
3. The GitHub issue or PR that owns your task.
4. Only the domain documentation needed for that task.

## This directory

`BOARD.md` is retained as collaboration **history**. It is no longer the current work queue and should not be read from top to bottom at the start of every session.

Use issues and PRs for live task state.

Use `coordination/HANDOFF_TEMPLATE.md` for substantial handoffs.

## Default routing

- Skippy / Grok Bots — runtime engineering, wiring, tests, PR-stack coordination.
- Grok Build / shell-capable agents — executable audits, repository surgery, deterministic rebuild/test work.
- GPT workers — bounded research, evaluation, voice/taste/content work, contradiction audits, synthesis.
- ChatGPT Work — scarce broad multi-source autonomous work where its capabilities materially matter.
- Brendon — product direction, high-value creative decisions, disputed requirements, merge approval.

A current issue/PR assignment outranks these defaults.

## Non-negotiable coordination rules

- Verify live `main` before making state-sensitive claims.
- `dnd-solo main` is executable runtime truth.
- `bfdm-corpus main` is merged corpus/research truth.
- Open PRs are proposed state and must be named when relied on.
- Pinned ZIPs are reproducible snapshots, not development truth.
- Do not use append-only history as current project state.
- Do not duplicate work already owned by another active worker.
- Do not equate green tests with good player experience.
- Do not harden unverified BFDM derived claims into runtime behavior.

The shared protocol in `COORDINATION.md` is authoritative when this file and older board entries disagree.