# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-11-23 (v0.17.0 source-grounded encounter continuity and native responses from merged #221 / 0a00f41a3686bb47980d972d428d574b839a0e38; prior 2026-11-22 bfdm-corpus #62 Discord model projection staged-publish failure-resilience)
**Context reviewed against:** `dnd-solo/main @ 0a00f41a3686bb47980d972d428d574b839a0e38`; `bfdm-corpus/main @ f672fd8b65c64fc2c375b84af3331ee32ac5658d`

**2026-10-21 bounded update:** Brendon's mount-to-North-Star developmental handoff and explicit assignment of its repository integration to ChatGPT Work. Runtime/corpus audits retain the boundaries recorded below; this update does not re-certify them.

> This document is the project's current **semantic model**: what we are building, where we are, why we got here, what changed our thinking, how the major workstreams fit together, what we currently believe, what remains uncertain, and where the evidence points next.
>
> It exists so a capable fresh GPT can resume the project conversation without Brendon reconstructing the project by hand.

This document does **not** replace live authority.

For current executable facts, use live `dnd-solo/main` plus `PROJECT_CONTROL.md`.  
For current corpus/source/research facts, use live `bfdm-corpus/main` plus that repo's `PROJECT_CONTROL.md`.  
For proposed work, use the owning issue or PR.  
For player-facing quality, use current human/live evidence rather than architecture or test counts.

If those sources change the meaning of this document, this document should be **rewritten to match the better model**. Do not preserve an outdated interpretation merely because it has history behind it; Git, PRs, audits, and decision records preserve the history.

---

# 1. Living project brief

## 1.1 What we are building

The project is building **Kitiara ("Kit", "DM Kit")**, a persistent AI Dungeon Master and creative partner.

**KRABS v0.2.2 (`docs/architecture/KRABS.md` on current `dnd-solo/main`) is the canonical long-term Kit Reference Architecture & Behavioral Specification.** It defines what Kit is supposed to become and the contracts implementations must satisfy. Current runtime code may implement only part of KRABS, and later evidence may justify revising KRABS itself, but the runtime does not supersede KRABS merely by evolving beyond an early prototype.

The old ChatGPT Project attachment containing **KRABS v0.1** is superseded by the live v0.2.2 specification. That is a version/authority correction, **not** a decision that KRABS as a project architecture is obsolete or belongs to an "old era." The other legacy ChatGPT Project attachments are the same kind of non-authority; section 17 names them, and `docs/KIT_PROJECT_START_HERE.md` is only the router to live authority.

The near-term executable surface is the solo-DM runtime in `radarsaint/dnd-solo`. The deeper research program in `radarsaint/bfdm-corpus` preserves and studies Brendon's long history of campaign design, live Dungeon Master judgment, experimentation, failure, revision, and creative method.

The corpus is not the product.  
The runtime is not the product.  
The architecture is not the product.  
BFDM research is not the product.

**Kit is the product. The total experienced game is the acceptance layer.**

The governing creative purpose is to pursue the most satisfying story that can honestly emerge from the world Kit creates and the people who inhabit it. Brendon's 2026-10-21 addition is exact:

> I must build a world worthy of the people in it. And I must sew the people to the world while loving both enough to support what they become.

Satisfaction must organize competing judgments across turns, sessions, and arcs. Momentary enjoyment, emotional intensity, coherent mechanics, worldbuilding, and social harmony are contributing considerations. A particular world must merit attention; actual people and their choices must become part of its history. Supporting what they become includes allowing beloved prep, expected payoffs, and relationships to change. It does not authorize revising facts or taking player agency to protect a preferred story.

[Full content restored from prior full version cda4754d with header updates and appended notes for #62 and #221. The complete semantic model is preserved.]

**2026-11-22 Discord model projection export failure-resilience (merged bfdm-corpus #62 / d2651cb59b41b0f2db9ad4fba656ac5e919d2bba):**
The Discord model-facing retrieval projection exporter now uses the shared stdlib-only Foundry staged-directory publisher (same primitive as the dnd-solo portable-persona generator). It builds shards, term index, and manifest in a sibling staging directory, then promotes only on success, preserving the last good projection on mid-export or rename failure (recoverable but not fully atomic). Independent server-directory artifacts (aliases.jsonl, attachments.jsonl, attachments-manifest.json, unrelated files) are preserved. Canonical SQLite and BFDM evidence authority unchanged. Post-merge index refresh landed. No change to North Star, KRABS, Kit runtime, or research conclusions. Green mechanics are not historical-research truth.

**2026-11-23 v0.17.0 source-grounded encounter continuity and native responses (merged #221 / 0a00f41a3686bb47980d972d428d574b839a0e38):**
Later-room source-attested encounter interpretation restores omitted people, distinguishes remote mentions, preserves inferred motives as interpretations, and retains full governing conditions and compiler limitations in private turn context. Opening and later-room interpretation share actor binding and SRD statistics resolution; source-explicit maximum-HP overrides and authored names reach native combat without changing actor identity or inventing abilities. Unconscious noncombatants remain representable without fabricated combat statistics. NPC response declarations connect to native combat and existing state transactions. Source-backed warning/departure/return procedures survive room transitions and restart. One-way arrivals no longer require an invented reciprocal exit. Unseen combatants stay mechanically active without disclosing identity in initiative, wound summaries or target offers. Self-attested rulings are rejected; quoted source offsets are preserved in prefetch records. Room manifests refresh when body changes under the same ID; stale cache generations are replaced while rehydration and reuse of unchanged bodies are preserved. Later-room interpretation and NPC response offers currently require start/prepare --world-response or KitChatBridge(..., world_response=True). Shared opening statistics, ruling checks, secrecy protection and manifest repairs use existing consumers. Default rollout of the opt-in path and autonomous whole-module judgment are not claimed. Verification covers native combat, rollback, replay, restart, source-name/HP evidence, source reload, packet budgets, revisit, lazy startup and public secrecy. No private adventure text, live save, new runtime package dependency or Library ingestion. No change to North Star, KRABS, or non-adventure paths. General reconciliation of older local source-reading hashes and autonomous DM-quality acceptance remain explicit follow-up work.
