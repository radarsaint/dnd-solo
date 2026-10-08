# Kit cross-repository coordination contract

**Schema:** `kit-coordination/v1`  
**Applies to:** `radarsaint/dnd-solo` and `radarsaint/bfdm-corpus`

This is the durable coordination contract for humans and AI collaborators working on Kit.

The purpose is to keep many agents from building against different versions of the project.

## North star

**Kit is the product. The total experience is the acceptance layer.**

Runtime correctness, judgment, cognition, memory, BFDM fidelity, personality, latency, visuals, and UI are means. None is allowed to become a proxy for the whole product.

## Repository authority

- **`dnd-solo main`** is canonical for current executable runtime behavior.
- **`bfdm-corpus main`** is canonical for merged corpus/source/research state.
- **Open PRs are proposed state, not canonical main.** They may contain important current work and must be named explicitly when relied on.
- **GitHub issues/PR conversations** own live task state.
- **`PROJECT_CONTROL.md`** in each repo is the short, rewritable orientation snapshot.
- **Pinned ZIPs/snapshots** are authoritative only for reproducing that pinned build.
- Historical boards, old branches, dated handoffs, and closed PRs are evidence about prior state, not current truth.

If a task crosses the runtime/research boundary, inspect both repos.

## Proxy is not proof

Across this project, a strong-looking proxy must not be mistaken for the thing it is meant to demonstrate.

Examples:

- passing tests != satisfying play;
- a landed fix != demonstrated player-facing improvement;
- citation presence != semantic verification;
- source accessibility != trustworthy derived research;
- room loading != source-to-room capability;
- architecture/specification != implemented capability;
- a document labeling itself canonical != current authority;
- BFDM research quality != current Kit quality;
- DM judgment != the whole Kit experience.

When a claim matters, state what evidence actually demonstrates it and what remains inferred, historical, proposed, mechanically tested, or unknown.

## Authority precedence

Self-description does not outrank repository state.

If an artifact says “canonical,” “current,” “source of truth,” or similar, interpret that label within the authority hierarchy in this file.

Examples:
- a Project attachment may have been canonical when exported and still be historical now;
- an in-repo mirror may call itself canonical while the project has since moved authority to a sibling repo;
- an open PR may contain a newer-looking design than `main` without being canonical;
- a canonical specification can supersede older canonical specifications.

When labels conflict, prefer:
1. live repository metadata and `main`;
2. the current repo's control layer;
3. explicit supersession statements in newer canonical docs;
4. active issue/PR state for proposed work;
5. historical/pinned artifacts only for reconstructing their own version.

Never resolve a conflict by choosing the newest-looking prose alone.

## Session bootstrap

For substantial project/research/implementation work, start at `dnd-solo/PROJECT_BOOTSTRAP.md`.

That router requires a fresh GPT to acquire, in order:

1. durable project/corpus understanding;
2. the agent/tool/capability map;
3. live repository truth and current control state;
4. recent material context changes;
5. the issue/PR that actually owns the task.

Do not begin by consuming an append-only history log, an old Project attachment, or an arbitrary open PR.

For a narrowly bounded task, load only the portions of this context that can materially affect the work; the bootstrap is an orientation system, not an excuse to flood every worker with the entire archive.

## Work ownership

Ownership is a routing default, not a permanent monopoly. A current issue/PR can assign differently.

- **Brendon:** product direction, high-value creative judgment, disputed requirements, merge approval.
- **Nagatha:** PM/review/acceptance coordination, reconciliation of overlapping work, bundle preparation, and merge coordination. Nagatha helps keep Brendon out of routine implementation triage; this is a coordination role, not independent product authority.
- **Skippy / Grok Bots:** runtime engineering, wiring, tests, PR-stack coordination, executable integration.
- **Grok Build / shell-capable agents:** executable reconnaissance, repository surgery, deterministic rebuild/test work. Grok Build is not Skippy and is not a Grok Bot.
- **GPT research/review workers:** bounded audits, evaluation, voice/taste/content research, synthesis, contradiction finding.
- **ChatGPT Work:** scarce broad autonomous multi-source research or evaluation where its capabilities materially outperform ordinary GPT.
- **Control-room/synthesis thread:** reconcile outputs across workers against current repo truth and the product end state.

## Current state versus history

Current-state documents are **rewritten**, not appended forever.

Use history for provenance:
- issues and PRs;
- git history;
- `docs/collab/BOARD.md` in `dnd-solo`;
- dated research handoffs/audits in `bfdm-corpus`.

Use current control for orientation:
- `PROJECT_CONTROL.md`;
- local machine-readable `coordination/control.json`;
- current issue/PR.

## When PROJECT_CONTROL must change

Update the local `PROJECT_CONTROL.md` when a merged change materially alters any of:

- what the repo actually does;
- canonical data/research state;
- a major active workstream or dependency;
- a settled decision;
- cross-repo responsibility;
- the next recommended entry point;
- an old warning becoming false.

Do not update it for every trivial commit.

When the sibling repo changes in a way that affects this repo, update the cross-repo dependency section here or in the local control file.

## Staleness rule

`coordination/control.json` records the `main` SHA last inspected for the control snapshot.

A different live SHA does **not** automatically make the snapshot false. It means the agent must verify whether intervening commits materially changed the claims it is about to rely on.

Never silently call a dated control snapshot current without checking live GitHub.

## Project Brain continuity and Gardener role

The project must carry forward durable semantic understanding rather than relying on Brendon, Nagatha, Skippy, any particular GPT, or any one chat's context window.

The semantic center is:

- `docs/PROJECT_UNDERSTANDING.md` — the living Project Brain: the best current human-readable model of what the project is, where it is, why it got here, what changed the team's thinking, how workstreams relate, what is believed, what remains uncertain, and where the evidence points.
- `coordination/context_state.json` in `dnd-solo` — the single shared Project Gardener resumability checkpoint/cursor. It records what has been fully reconciled; it is not a knowledge store and is not duplicated in the BFDM repo.
- live repository state and each repo's `PROJECT_CONTROL.md` — current operational/executable/research truth.
- Git history, PRs/issues, audits, playtests, decisions, source material, and BFDM evidence — episodic/history/evidence layers that support or challenge the current semantic model.
- `dnd-solo` issue #115 — intake for durable semantic changes discovered outside an appropriate repo-changing PR. Inbox material is proposed context, not truth.

The Project Brain is rewritten as understanding improves. It is not an append-only diary and must not become a substitute for live authority.

### The Project Gardener is a role, not an agent

There is no permanent "Gardener GPT."

**Project Gardener** is a restartable role that any suitable GPT with the necessary repository/evidence access may perform for one bounded pass.

No individual Gardener owns project continuity.

A Gardener pass must be resumable by another GPT that has none of the previous GPT's conversation context.

Nagatha may perform PM/review/reconciliation work in her normal lane, but she is not the project's memory substrate. The same is true of Skippy, ChatGPT Work, Grok Build, ordinary GPT threads, and control-room/synthesis threads.

### Starting a Gardener pass

Before selecting work, a Gardener must:

1. read the current Project Brain;
2. read the single shared checkpoint at `dnd-solo/coordination/context_state.json`;
3. resolve live `main` for each repo relevant to the pass;
4. identify material newer than the recorded reviewed boundaries, including unreconciled #115 comments after the recorded inbox cursor;
5. choose a bounded reconciliation scope that can be completed or safely stopped at a whole checkpoint boundary.

The checkpoint tells the Gardener **where reconciliation stopped**, not what to believe. The Project Brain carries the current semantic model; live authority and evidence determine whether that model must change.

### Purpose of a Gardener pass

A Gardener does not summarize activity for its own sake.

Its job is to answer:

> **Does new authoritative evidence, a correction, a decision, a result, or accumulated project work change what a competent future collaborator should believe about this project?**

If the answer is no, the Gardener records/reconciles the reviewed boundary without manufacturing a semantic change.

If the answer is yes, the Gardener updates the affected current model so a future collaborator inherits the better understanding.

### Bounded-pass rule

Every Gardener pass must choose a tractable, explicit scope before reconciling.

Valid scopes include, for example:

- a bounded range of new project-context inbox items;
- runtime/project changes since a known reviewed commit;
- a specific BFDM trust/research development;
- a bounded set of audits or playtest results;
- agent/tool capability or ownership changes;
- one contradiction affecting the Project Brain;
- one Project Brain section whose underlying authority materially changed.

Do not attempt to "re-read the whole project" on every pass.

Do not begin a pass whose completion boundary cannot be described.

When the available context window is insufficient for the next whole unit of work, stop at the last completely reconciled boundary and hand off. Partial silent reconciliation is worse than a smaller completed pass.

### Evidence and authority during reconciliation

A Gardener applies the same authority rules as any other serious project worker.

In particular:

1. live `dnd-solo/main` controls current executable/runtime facts;
2. live `bfdm-corpus/main` controls merged corpus/source/research facts;
3. current human/live evidence controls player-experience claims;
4. owning issues/PRs describe proposed or active task state but do not become canonical merely by being open;
5. primary evidence outranks derived BFDM interpretation when the two conflict;
6. explicit current Brendon corrections/decisions outrank prior project interpretation within the scope of that correction;
7. historical artifacts remain evidence about history, not automatic current truth.

A Gardener must distinguish verified fact, historical fact, observed outcome, research interpretation, inference, proposal, disputed claim, and unknown.

Do not resolve a genuine contradiction by averaging sources or choosing the most polished prose.

### Semantic reconciliation rule

When new material changes the project model, reconcile meaning rather than append chronology.

For each material change, determine:

1. **Previous model** — what a competent collaborator would have believed before this evidence.
2. **New evidence or correction** — what changed.
3. **Revised model** — what should now be believed, at what scope and confidence.
4. **Why it matters** — what project reasoning, workstream, risk, priority, or decision changes because of it.
5. **Historical preservation** — whether an old decision/interpretation needs to remain available as provenance even though it is no longer current.

Then rewrite the affected Project Brain section so the new model is coherent with the rest of the document.

Do not merely append "on DATE we learned X."

Do not preserve both old and new beliefs as if they are simultaneously current when one has superseded the other.

Do not generalize a local correction farther than the evidence supports.

### What belongs in the Project Brain

Promote a change into the Project Brain when a future capable GPT would otherwise need Brendon to explain it again in order to reason correctly about the project.

Typical examples:

- project purpose or success criteria;
- current strategic model;
- major workstream relationships;
- important architecture/product boundaries;
- material changes in what is demonstrated versus merely proposed;
- durable research-trust changes;
- important failure/correction trajectories;
- repeated false mental models future workers must avoid;
- agent/tool identity or capability facts that materially affect routing;
- significant uncertainties, risks, or approaching decisions;
- changes in where the evidence points next.

Do not promote:

- routine implementation churn;
- every commit or test result;
- temporary worker chatter;
- raw research excerpts better left in their evidence layer;
- ephemeral task status already owned by an issue/PR;
- speculative ideas that have not become part of the working project model.

### Gardener write discipline

A Gardener should make the smallest semantic edit that produces the best current model.

Prefer:
- rewriting stale claims;
- narrowing overbroad claims;
- reclassifying confidence;
- moving a question from "belief" to "uncertainty";
- changing the stated strategic consequence when evidence changed;
- preserving deep history while improving the current synthesis.

Avoid:
- duplicating the same truth across multiple competing "brains";
- producing another standalone summary instead of improving the canonical Project Brain;
- changing executable/runtime behavior;
- silently changing BFDM source truth or research claims outside the evidence supported by the pass;
- using the Gardener role to make product/creative decisions that belong to Brendon.

### Stop conditions and safe handoff

A Gardener pass stops when any of these is true:

- the declared bounded scope is completely reconciled;
- the next item would exceed the available context window;
- authoritative evidence needed to resolve the next item is unavailable;
- the next step requires Brendon's product/creative/authority decision;
- the pass discovers a contradiction that cannot be resolved from evidence;
- continuing would cross into a different workstream that should be a separate pass.

At stop, the worker must leave durable evidence of:

- the exact scope completed;
- the authoritative repo/commit/evidence boundaries inspected;
- semantic changes made, or an explicit statement that none were warranted;
- unresolved items and why they remain unresolved;
- the next unreconciled boundary;
- the commit/PR containing any Project Brain change.

The handoff must be sufficient for a new GPT to resume without access to the departing GPT's chat.

### Checkpoint integrity

Never advance a reconciliation checkpoint merely because material was opened, skimmed, or partially processed.

A boundary counts as reconciled only when:

- the relevant evidence was inspected;
- its semantic impact was decided;
- required Project Brain edits were completed and durably written;
- unresolved contradictions were explicitly preserved rather than hidden.

The machine-readable checkpoint/cursor is `dnd-solo/coordination/context_state.json`. It is a resumability mechanism, not a knowledge store. It is the single shared Gardener checkpoint for the project; sibling repos point to it rather than duplicating cursor/review state. Git history and the underlying evidence preserve provenance; the Project Brain preserves the current semantic model.

### Context impact from ordinary work

Not every worker is performing a Gardener pass.

At the end of substantial ordinary work, classify project-context impact as:

- `NONE`
- `CONTROL`
- `UNDERSTANDING`
- `AGENTS_TOOLS`
- `AUTHORITY`

If authorized work already updates the correct current semantic/control surface in its owning PR, do not duplicate the same change elsewhere.

If durable project understanding changed but the worker cannot appropriately edit the Project Brain, persist the change for later reconciliation in the project context inbox (#115).

Chat history alone is not durable project state.

A semantic/context delta is **not project truth merely because it is in the inbox**. A later Gardener must reconcile it against authoritative evidence before promoting it into the Project Brain.

## Handoffs

Every substantial worker result should include the capsule in `coordination/HANDOFF_TEMPLATE.md`.

A handoff is incomplete if it omits:
- repo and SHA inspected;
- scope;
- evidence/result;
- changes made;
- tests/verification;
- unresolved questions;
- dependencies;
- next owner/action;
- explicit do-not-redo warnings where applicable.

## Task discipline

- One task has one owning issue/PR when implementation begins.
- Parallel agents must have non-overlapping scopes or explicitly shared boundaries.
- Findings are not implementation.
- Design is not executable truth.
- Passing tests are not player-experience proof.
- A citation is not semantic verification.
- A mounted room is not evidence of generalized excellent play.
- A source being present is not evidence it was used live.
- A successful component is not automatically a successful product change.



## Research readiness has two axes

Do not collapse source accessibility into research trust.

For BFDM work, distinguish:

1. **SOURCE / SUBSTRATE READINESS** — the relevant primary material exists, is oriented, and can be retrieved.
2. **DERIVED-RESEARCH TRUST READINESS** — the specific propositions/hypotheses being reused have been semantically reconstructed from the primary evidence at the claimed scope/confidence.

A source family may be ready to research while the existing paper written about it remains unverified.

Current example: S3/S4 live-judgment material is source-researchable, while PR #38 is still auditing whether existing derived case propositions deserve semantic trust.

When a downstream task depends on a derived claim, name which axis is satisfied and which is still open.

## Behavioral evidence freshness

Player-facing quality claims must name both the evidence type and whether it still applies to the current build.

Use these states:

- **DEMONSTRATED_CURRENT_FAILURE** — reproduced on current `main` or directly shown by a failing-first test against current `main`.
- **DEMONSTRATED_CURRENT_SUCCESS** — current-build human/live evidence shows the behavior works well.
- **HISTORICAL_FAILURE** — real failure on an older build; still useful for regression history, but not proof of current failure.
- **MECHANICALLY_ADDRESSED_UNRETESTED** — code/tests/replay indicate the old defect was repaired, but comparable human play has not confirmed the experienced result.
- **STALE_FAILURE** — evidence now supports removing the old failure from the current indictment.
- **UNKNOWN_CURRENT** — implementation changed enough that neither the old failure nor the intended fix has current player-facing confirmation.

Always record the build/commit and evidence class where practical.

Do not upgrade:
- unit-test success -> behavioral-eval success;
- behavioral-eval success -> actual-play success;
- an old failure -> current failure after material implementation changes;
- an intended fix -> demonstrated player-experience improvement.

When implementation moves faster than player-facing evaluation, say so explicitly. Lack of current evidence is not proof of quality and not proof of failure.

## Conflict resolution

When two agents disagree:

1. compare the exact repo/branch/SHA each inspected;
2. separate executable fact, source fact, research interpretation, design proposal, and product judgment;
3. retrieve the underlying evidence;
4. preserve a genuine unresolved contradiction rather than averaging it away;
5. ask Brendon only when evidence cannot settle a product or creative decision.

## Cross-repo boundary

`bfdm-corpus` preserves and researches evidence. It must not be reorganized merely to fit the current Kit architecture.

`dnd-solo` executes Kit. It may consume research, but it must not treat unverified derived research as doctrine.

Future cognition may span or sit beside both repositories. Do not force that architecture prematurely.