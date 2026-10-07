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