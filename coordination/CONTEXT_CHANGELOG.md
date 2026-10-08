# HISTORICAL — Project-Context Changelog

**Status:** superseded as an active context surface on 2026-10-07.  
**Do not maintain this file as current project memory.**  
**Do not require fresh collaborators to read it.**

This file is preserved only as provenance for the early project-context continuity design.

Its former active functions now belong to:

- `docs/PROJECT_UNDERSTANDING.md` — the living semantic Project Brain;
- live `main` + each repo's `PROJECT_CONTROL.md` — current changing facts/state;
- `coordination/context_state.json` — restartable Project Gardener reconciliation checkpoint;
- dnd-solo issue #115 — unreconciled semantic-delta inbox;
- Git history, PRs/issues, audits, and decision records — historical provenance.

The entries below describe real context changes from the initial October 7 continuity work, but they are a **historical snapshot**. If they conflict with the Project Brain or live authority, they do not control.

---

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
