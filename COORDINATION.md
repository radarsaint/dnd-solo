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

Before substantial work:

1. Resolve the live `main` SHA for every repo the task depends on.
2. Read that repo's `PROJECT_CONTROL.md`.
3. Read the issue/PR that owns the task.
4. Read only the domain documents needed for the task.
5. Read historical boards/handoffs only when reconstructing history or resolving a contradiction.

Do not begin by consuming an append-only history log.

## Work ownership

Ownership is a routing default, not a permanent monopoly. A current issue/PR can assign differently.

- **Brendon:** product direction, high-value creative judgment, disputed requirements, merge approval.
- **Nagatha:** PM/review/acceptance coordination, reconciliation of overlapping work, bundle preparation, and merge coordination. Nagatha helps keep Brendon out of routine implementation triage; this is a coordination role, not independent product authority.
- **Skippy / Grok Bots:** runtime engineering, wiring, tests, PR-stack coordination, executable integration.
- **Grok Build / shell-capable agents:** executable reconnaissance, repository surgery, deterministic rebuild/test work.
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