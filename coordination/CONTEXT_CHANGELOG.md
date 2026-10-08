# Recent Project-Context Changes

**Purpose:** short rolling summary of changes that alter how a capable fresh GPT should understand or approach the project.  
**Not:** code changelog, research log, or work queue.

Keep this file compact. Retain roughly the most recent 10–20 material context changes. Older provenance remains in Git history, PRs/issues, audits, and the context inbox.

## 2026-10-07 — Context continuity became an explicit project requirement

Brendon identified the recurring failure: each new chat was requiring him to rebuild the full context of what the project is, what tools/agents exist, current state, and prior work.

Project-level acceptance condition:

> The project itself must carry enough current, durable, growing context that an appropriate GPT can understand what is being built, what resources exist, what happened, what is currently true, and what changed—without Brendon reconstructing that context by hand.

This is broader than documentation. It requires bootstrap, context backflow, staleness detection, and resource identity.

## 2026-10-07 — Durable project-understanding layer added to coordination work

`docs/PROJECT_UNDERSTANDING.md` was added on the `dnd-solo` coordination branch as the durable mental-model layer.

It is intentionally distinct from:
- executable truth in `dnd-solo/main`;
- source/research truth in `bfdm-corpus/main`;
- current task state in issues/PRs;
- fast-changing `PROJECT_CONTROL.md`.

It must be rewritten as understanding improves rather than appended indefinitely.

## 2026-10-07 — Agent/resource identity became first-class context

Repeated routing mistakes showed that the project must explicitly distinguish:
- Kit;
- Nagatha;
- Skippy;
- Grok Bots;
- Grok Build;
- ordinary Grok;
- ordinary GPT workers;
- ChatGPT Work;
- temporary audit threads;
- control/synthesis functions;
- repositories and Project sources.

A key correction: asking a GPT "do you need Grok Build?" normally asks whether Grok Build should do shell/repository plumbing and whether the GPT should write the prompt—not whether ownership should move to Grok Build.

Another key correction: Nagatha is useful PM/review/reconciliation capacity but is token/context limited and must not become the sole project-memory substrate.

## 2026-10-07 — Durable context inbox created

`radarsaint/dnd-solo` issue **#115** is the project-context inbox for durable discoveries made in chats/audits/external workflows that do not already update the correct context file in an owning PR.

The inbox is provenance/intake, not authority and not a work queue.

## 2026-10-07 — Four-audit control correction

The October 7 audits converged on the governing rule:

> Proxy evidence is not demonstrated truth.

Project control now separates:
- executable runtime truth;
- player-experience evidence;
- BFDM research trust;
- project/coordination authority.

This also established that source/substrate readiness and derived-research trust are separate.

## 2026-10-07 — Live coordination work remains proposed, not merged

At this context refresh:
- `dnd-solo` PR #113 — project truth / cross-repo coordination — open draft.
- `bfdm-corpus` PR #39 — paired BFDM coordination — open draft.
- `bfdm-corpus` PR #38 — derived-research forensic integrity audit — open draft.
- `dnd-solo` PR #114 — obsolete in-repo BFDM mirror removal — open draft and stacked from the coordination work.

Fresh GPTs must not treat these as canonical `main` merely because they contain newer project understanding.
