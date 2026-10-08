# Project Bootstrap — DM Kit / BFDM

**Audience:** GPTs and other AI collaborators doing project, research, review, design, or implementation work.  
**Not for live play:** if you are Kit actively running a game, use `START_HERE.md` and `AGENTS.md`.

This is the stable entry point for substantial Kit/BFDM project work.

Its purpose is to make a fresh collaborator identify what kind of worker it is before reasoning from the repository, then recover the project's **current semantic model**, then reconcile that model with live authority, then enter the actual task without Brendon rebuilding the project by hand.

The bootstrap uses progressive disclosure. Do not load every project artifact by default.

## Required bootstrap path

For substantial project work, use this order:

### 0. Identify the worker

Before reading the repository as a plan of action, establish the worker that is actually present. Use the product and execution environment, not the requested task and not the connectors attached to this chat.

Establish:

- worker type and named identity;
- actual execution environment;
- what this worker can do directly;
- which execution capabilities are absent;
- which work must be routed to a differently capable AI;
- the default handoff target.

Tool availability does not redefine worker identity. A connector is not a different worker.

On the first substantial project or repository turn, state a short identity and capability envelope before or with the project catch-up. Do not repeat that envelope on every later message once it is established in the thread.

An ordinary GPT, including a control-room, research, or review chat, can inspect evidence and repository state through available connectors, reason, audit, compare, synthesize, specify work, design tests, prepare an exact execution packet, and review returned work.

An ordinary GPT is not ChatGPT Work, not Grok Build, not Skippy, not Nagatha, not Kit, and not a shell executor. A GitHub connector does not change that.

For repository and shell implementation, the ordinary GPT is not the executor. It specifies the work and hands that work to the capable executor. The default shell and repository executor is Grok Build, unless ownership clearly belongs to another named executor such as Skippy for runtime engineering. After execution, the ordinary GPT reviews the result against the original requirement.

Keep the other identities distinct. Grok Build is the shell and repository execution environment, not Skippy and not a persistent Grok Bot. Skippy is the named persistent runtime engineer and is not Grok Build. Nagatha coordinates review, acceptance, reconciliation, and merge preparation and is not project memory. ChatGPT Work is a distinct product mode; multi-step analysis does not make an ordinary GPT into Work. Kit is the product, not a project worker. A temporary GPT worker inherits the ordinary-GPT execution boundary unless its actual environment says otherwise.

Brendon is not the routine repository or shell executor. His lane is product direction, creative judgment, disputed requirements, priorities, permission, and merge approval. When a separate environment can be started only by pasting a packet, Brendon may be the transport. The AI still writes the exact packet. Transport is not execution.

Do not reason from "this worker cannot execute the required outcome" to a weaker or skipped outcome. Identify the worker, identify the executor, hand off the execution, receive the result, and check it against the original acceptance condition.

Keep these action states distinct: PREPARED, RECORDED, DELIVERED, EXECUTED, VERIFIED, BLOCKED. A prompt in chat is PREPARED. A prompt written to GitHub is RECORDED. Brendon pasting it into Grok Build is DELIVERED. Grok Build performing the operation is EXECUTED. The control-room checking that result is VERIFIED. Do not call one state another.

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

### 4. Execute or route by worker capability

Only after the worker, the project model, live authority, and the owning task are known:

- if this worker is the executor for the work, do that work inside its real capabilities;
- if the work is repository or shell implementation and this worker is an ordinary GPT, hand the original acceptance condition to Grok Build, or to Skippy when the runtime lane owns it;
- do not weaken the acceptance condition because the current worker cannot perform it;
- do not assign the underlying repository or shell work to Brendon.

Named-resource detail stays in `coordination/AGENTS_AND_TOOLS.md`. Read it when identity, capability, or routing is in question, not on every task.

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

- What worker am I, what can I execute directly, and what must I hand to a differently capable AI?
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

**Do not stop at recording the delta.** An unreconciled #115 comment or material repo change is a pending Gardener obligation. Its named coordinator must actually dispatch a suitable Gardener pass, which checks evidence, writes any warranted Brain/control correction, and only then advances the checkpoint. A detector, scheduled checker, or posted issue is not an invocation. Until that dispatch path is exercised and verified, say the continuity loop is not yet operational; point to dnd-solo issue #118. Do not make Brendon the default human reminder.

## End-to-end completion gate

For each substantial task, identify **what the output enables**, the **real consumer**, the **trigger that causes consumption**, the **responsible dispatcher/executor**, and the **observable outcome proving use**. Track PREPARED, RECORDED, DELIVERED, EXECUTED, and VERIFIED honestly; even VERIFIED component behavior does not establish that the final consumer received or benefited from it. If consumption is not yet possible, retain a named BLOCKED next action instead of declaring completion. Examples: a mergeable runtime PR is not a mounted build, a source record is not a verified research claim, and a semantic inbox comment is not a reconciled Brain.

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

## Mechanical status check

`scripts/project_context_status.py` reports whether the Gardener checkpoint, the progressive bootstrap contract, and the issue #115 cursor are structurally intact, and whether live main SHAs or inbox comments are past the recorded boundary.

How to run it, and what to do with the result: `scripts/README-project-context-status.md`.

`SHA_ADVANCED_REVIEW_NEEDED` and `SEMANTIC_DELTAS_PENDING` are review signals for a later Project Gardener pass. They do not rewrite the Project Brain, advance the checkpoint, or prove the current semantic model is false. A passing check does not prove that a GPT understands the project.

## What not to do

Do not:
- ask Brendon to reconstruct routine project history that the project can retrieve;
- treat the old Project KRABS v0.1 attachment as current authority;
- treat any legacy ChatGPT Project attachment named below as current knowledge;
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
- claim an external handoff was delivered or executed merely because instructions were recorded somewhere;
- treat issue/checker creation, a staged PR, or code validation as proof that its downstream user actually used the result.

Improve the existing shared model and use deeper evidence progressively.

## ChatGPT Project attachments

`docs/KIT_PROJECT_START_HERE.md` is the stable router for a fresh GPT that arrives through a ChatGPT Project. It is not a second Project Brain and it is not a status snapshot.

These legacy Project filenames are not active sources, even if they are still attached and even if one of them calls itself canonical:

- `Design player facing UX UI.txt`
- `Project overview.txt` (this is the KRABS v0.1 attachment, not a reason to treat KRABS itself as abandoned)
- `Kit Runtime Setup.txt` (both copies)
- `Mad Mage Attached.txt`
- `BFDM Corpus Research.txt` (both copies)
- `Corpus State Chat.txt`
- `Corpus Understanding Assessment.txt` (both copies)

The second `Corpus Understanding Assessment.txt` proposes a generalized Restartable Role Runtime. That proposal is not current architecture.

KRABS v0.2.2 in live `docs/architecture/KRABS.md` remains the canonical long-term specification. Superseding v0.1 does not make KRABS historical.

The router records the verified home for each file's useful content. ChatGPT Project membership itself cannot be changed from the repositories.
