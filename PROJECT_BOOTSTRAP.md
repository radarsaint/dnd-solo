# Project Bootstrap — DM Kit / BFDM

**Audience:** GPTs and other AI collaborators doing project, research, review, design, or implementation work.  
**Not for live play:** if you are Kit actively running a game, use `START_HERE.md` and `AGENTS.md`.

This is the stable entry point for substantial Kit/BFDM project work.

Its purpose is to let a capable fresh collaborator recover the project's **current semantic model first**, then reconcile that model with live authority, then enter the actual task without Brendon rebuilding the project by hand.

The bootstrap uses progressive disclosure. Do not load every project artifact by default.

## Required bootstrap path

For substantial project work:

### 1. Project Brain first

Read `docs/PROJECT_UNDERSTANDING.md`.

Use it to understand:
- what Kit is and what success means;
- where the project currently is;
- how it got here;
- what changed the team's thinking;
- the current strategic model;
- the major workstreams and how they depend on one another;
- what is currently believed, uncertain, rejected, or approaching decision;
- the deeper creative/BFDM history needed to interpret current work.

This is the semantic starting model, not final authority for changing facts.

### 2. Reconcile with live authority

Before relying on current-state claims, inspect the live authority relevant to the task.

At minimum when state-sensitive:
- `radarsaint/dnd-solo/main` = current executable/runtime truth;
- `radarsaint/bfdm-corpus/main` = current merged corpus/source/research truth;
- read the relevant repo's `PROJECT_CONTROL.md`;
- open PRs are proposed state, not canonical `main`;
- current human/live evidence controls claims about player-facing quality.

If live authority materially changes the Project Brain's model, do not silently keep using the stale interpretation.

For a Project Gardener pass, also read the single shared checkpoint at:
- `dnd-solo/coordination/context_state.json`.

Ordinary workers do not need the Gardener checkpoint unless their task depends on reconciliation state.

### 3. Enter the owning task

Read the issue/PR or explicit user instruction that actually owns the work.

Its scope determines what deeper context is needed.

Do not infer active work merely from an old open PR.

## Load deeper context only when relevant

After the required path above, retrieve additional context according to the task.

### Agent/tool/resource questions

Read `coordination/AGENTS_AND_TOOLS.md` when identity, capability, persistence, availability, ownership, routing, or use of a named resource matters.

Do not load it merely because every project task has agents.

Do not silently substitute one named resource for another.

### Semantic reconciliation / Project Gardener work

Read:
- `coordination/context_state.json`;
- unreconciled comments in dnd-solo issue #115 after the recorded cursor;
- only the evidence needed for the bounded Gardener pass.

The issue is the semantic-delta inbox, not project truth.

### Historical or causal reconstruction

Use Git history, audits, decision records, PRs/issues, playtests, source material, and BFDM evidence as needed.

`coordination/CONTEXT_CHANGELOG.md` is historical provenance only. It is superseded as an active context surface; do not maintain it and do not read it unless reconstructing the early continuity-design history.

### BFDM research work

Follow the BFDM repo's research entry points and source/provenance rules. Distinguish:
- source/substrate readiness;
- derived-research trust readiness.

Do not treat retrieval success as semantic verification.

### Runtime / implementation work

Follow the current `dnd-solo` control state and owning issue/PR, then load the specific architecture/code/tests relevant to the change.

Do not use historical Area 6c documentation as a universal runtime model.

## Before doing substantial work

Answer internally:

- What exactly did Brendon ask for?
- What problem is this work supposed to stop or solve?
- What would demonstrate success from the project/user perspective?
- What does the Project Brain currently say that matters here?
- Which live source is authoritative for the changing facts I need?
- Has live authority advanced enough to require reconciliation?
- Which named agent/tool/resource did Brendon actually offer or request?
- Can my current tools perform the exact required operation, or only a proxy for it?
- If not, which project executor should receive the blocked operation without changing the acceptance condition?
- For repo/shell/environment investigation or mutation I cannot perform, have I routed it to Grok Build rather than handing routine glue work to Brendon?
- What exact action state applies: PREPARED, RECORDED, DELIVERED, EXECUTED, VERIFIED, or BLOCKED?
- What work is already underway?
- Am I about to redo work another worker owns?
- Am I treating an artifact, test, citation, architecture, or status marker as though it proves the actual outcome?
- If this work changes the project model, where will that understanding persist?

Then proceed.

## Context backflow

The project should become easier to understand as good work accumulates.

At the end of substantial work, decide whether you learned something a future capable GPT would otherwise need Brendon to explain again.

Classify context impact:

- `NONE` — no durable project-context change.
- `CONTROL` — current state/active dependency/authority changed.
- `UNDERSTANDING` — the semantic project model changed.
- `AGENTS_TOOLS` — identity, capability, availability, ownership, or correct use of a resource changed.
- `AUTHORITY` — source precedence or canonical location changed.

If authorized work already has an owning PR and appropriately updates the current semantic/control surface, do not duplicate the same change elsewhere.

If durable project understanding changed but the worker cannot appropriately update the Project Brain, post a structured `SEMANTIC_DELTA` to **dnd-solo issue #115 — Semantic delta inbox**.

Do not leave the only copy in chat history.

A semantic delta is proposed context, not project truth. A later Project Gardener reconciles it against authority before promoting it into the Project Brain.

## Staleness behavior

No prose file can truthfully promise to be "never stale."

Use this pattern instead:

- Project Brain = best current semantic model;
- live repo/source/player evidence = authority for changing facts;
- `PROJECT_CONTROL.md` = fast-moving orientation;
- `coordination/context_state.json` = Gardener reconciliation boundary;
- issue #115 = unreconciled semantic intake;
- Git/PR/issues/audits/decision records = provenance and history.

A different live SHA does **not** automatically invalidate the Project Brain. It means a state-sensitive worker or Gardener must determine whether the intervening change matters to the claims being relied on.

If an artifact conflicts with live authority, say so and use live authority.

## What not to do

Do not:
- ask Brendon to reconstruct routine project history that the project can retrieve;
- treat the old Project KRABS v0.1 attachment as current authority;
- treat Area 6c as the architecture of Kit;
- treat BFDM searchability as verified research;
- treat green runtime tests as proof of good play;
- treat a landed fix as demonstrated player-facing improvement;
- call Grok Build "Skippy";
- turn a question like "do you need Grok Build?" into a proposal to transfer project ownership;
- load every context/reference file for every task;
- reconstruct the Project Brain from a changelog when the Project Brain already exists;
- create another independent project-status or project-memory system because the current one is imperfect.
- weaken or redefine a required outcome because this GPT lacks the tool to execute it;
- hand routine executable work back to Brendon before checking/routing to the appropriate project executor;
- claim an external handoff was delivered or executed merely because instructions were recorded somewhere.

Improve the existing shared model and use deeper evidence progressively.
