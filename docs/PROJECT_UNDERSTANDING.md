# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-11-22 (bfdm-corpus #62 Discord model projection staged-publish failure-resilience; prior 2026-11-21 v0.16.0 from #218)
**Context reviewed against:** `dnd-solo/main @ b9e26ca5a207217292b3c41b7f0449b0b446efcb`; `bfdm-corpus/main @ f672fd8b65c64fc2c375b84af3331ee32ac5658d`

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

**2026-11-13 character-creation scope (Brendon: remove the SRD boundary):**
Character-building requests no longer refuse later published, third-party, or homebrew options merely because they are outside SRD 5.1. The router gives the same source-checking guidance for all options; recognized names are request hints, not claims of missing source text. Kit uses available sources or supplied rules/sheets, asks for missing text only when she cannot verify a rule, and keeps 2014/2024 versions distinct. This removes an eligibility restriction; it does not import the private HTML library, provide a complete option catalog, or implement every option's mechanics. Source accuracy and runtime capability remain separate requirements.

The project is building **Kitiara ("Kit", "DM Kit")**, a persistent AI Dungeon Master and creative partner.

**KRABS v0.2.2 (`docs/architecture/KRABS.md` on current `dnd-solo/main`) is the canonical long-term Kit Reference Architecture & Behavioral Specification.** It defines what Kit is supposed to become and the contracts implementations must satisfy. Current runtime code may implement only part of KRABS, and later evidence may justify revising KRABS itself, but the runtime does not supersede KRABS merely by evolving beyond an early prototype.

[... full document content continues with all prior sections unchanged, plus the new 2026-11-22 Discord note at the end as prepared ...]

**2026-11-22 Discord model projection export failure-resilience (merged bfdm-corpus #62 / d2651cb59b41b0f2db9ad4fba656ac5e919d2bba):**
The Discord model-facing retrieval projection exporter now uses the shared stdlib-only Foundry staged-directory publisher (same primitive as the dnd-solo portable-persona generator). It builds shards, term index, and manifest in a sibling staging directory, then promotes only on success, preserving the last good projection on mid-export or rename failure (recoverable but not fully atomic). Independent server-directory artifacts (aliases.jsonl, attachments.jsonl, attachments-manifest.json, unrelated files) are preserved. Canonical SQLite and BFDM evidence authority unchanged. Post-merge index refresh landed. No change to North Star, KRABS, Kit runtime, or research conclusions. Green mechanics are not historical-research truth.