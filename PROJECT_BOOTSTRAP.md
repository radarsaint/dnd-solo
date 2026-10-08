# Project Bootstrap — DM Kit / BFDM

**Audience:** GPTs and other AI collaborators doing project, research, review, design, or implementation work.  
**Not for live play:** if you are Kit actively running a game, use `START_HERE.md` and `AGENTS.md`.

This is the stable entry point for the whole Kit project.

The goal is that Brendon should **not** have to reconstruct what the project is, what resources exist, what is current, or what changed every time a new chat starts.

## Bootstrap order

For substantial project work:

1. **Durable mental model** — read `docs/PROJECT_UNDERSTANDING.md`.
   - What Kit is.
   - What BFDM is.
   - What is actually in the corpus.
   - Creative/project history and major boundaries.
   - What repeatedly goes wrong when agents form the wrong model.

2. **Agent/tool map** — read `coordination/AGENTS_AND_TOOLS.md`.
   - Distinguishes Kit, Nagatha, Skippy, Grok Bots, Grok Build, ordinary GPT/Grok, ChatGPT Work, shell-capable workers, repositories, Project sources, and other available resources.
   - Do not silently substitute one named resource for another.

3. **Current truth** — inspect live GitHub before relying on status prose.
   - `radarsaint/dnd-solo/main` = current executable/runtime truth.
   - `radarsaint/bfdm-corpus/main` = current merged corpus/source/research truth.
   - Read the relevant repo's `PROJECT_CONTROL.md`.
   - Compare live `main` SHA with the SHA last reviewed by the control/context files.
   - Open PRs are proposed state, not canonical main.

4. **What changed recently** — read `coordination/CONTEXT_CHANGELOG.md`.
   - This is a short rolling summary of **material project-context changes**, not an implementation changelog.
   - Older provenance remains in Git history, PRs/issues, audits, and the context inbox.

5. **Current task** — read the issue/PR that actually owns the work.
   - Its explicit scope can override default routing.
   - Do not infer active work merely from an old open PR.

## Before doing substantial work

Answer internally:

- What exactly did Brendon ask for?
- What is the user-visible or project-visible acceptance condition?
- Which repo/source is authoritative for the facts I need?
- Which named agent/tool/resource did he actually offer or request?
- What work is already underway?
- Am I about to redo work another worker owns?
- Am I treating an artifact, test, citation, or architecture as though it proves the actual outcome?

Then proceed.

## Context backflow

The project must become better informed as work happens.

At the end of substantial work, decide whether you learned something a future capable GPT would otherwise need Brendon to explain again.

Classify the context impact:

- `NONE` — no durable project-context change.
- `CONTROL` — current state/active dependency/authority changed.
- `UNDERSTANDING` — durable mental model, history, corpus understanding, architecture boundary, or repeated correction changed.
- `AGENTS_TOOLS` — identity, capability, availability, ownership, or correct use of a resource changed.
- `AUTHORITY` — source precedence or canonical location changed.

If the work already has an owning PR and you are authorized to edit it, update the appropriate context surface in that PR.

If the durable learning happened in a chat/audit/external workflow with no appropriate repo change, post a structured `CONTEXT_DELTA` to **dnd-solo issue #115 — Durable context inbox**.

Do not leave the only copy in chat history.

## Staleness behavior

No prose file can truthfully promise to be "never stale."

This project instead makes staleness detectable:

- context/control files record the `main` SHAs they were reviewed against;
- a different live SHA requires checking whether intervening changes affect the claims you rely on;
- context-impacting work must update or enqueue the relevant context;
- a rolling context-change summary shows recent mental-model changes;
- the raw context inbox preserves unapplied deltas until reconciliation.

If an artifact conflicts with live repository authority, say so and use live authority.

## What not to do

Do not:
- ask Brendon to reconstruct routine project history that the project can retrieve;
- treat the old Project KRABS v0.1 attachment as current authority;
- treat Area 6c as the architecture of Kit;
- treat BFDM searchability as verified research;
- treat green runtime tests as proof of good play;
- call Grok Build "Skippy";
- turn a question like "do you need Grok Build?" into a proposal to transfer project ownership;
- create another independent project-status system because this one is imperfect.

Improve the existing context surfaces instead.
