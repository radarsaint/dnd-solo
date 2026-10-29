# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-10-29 (#201: one-step adventure PDF ingest and first-scene compile)
**Context reviewed against:** `dnd-solo/main @ 10615958da2e7ce890be7da338159c9781e1f0d9`; `bfdm-corpus/main @ cf65ec04572b2a033383344d1f2583e3380686f7`

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

The operational distillation lives in [the personality core](personality/dm-personality-core.md), which the runtime already reads. The [full developmental handoff](personality/2026-10-21-mount-to-north-star-handoff.md) preserves evidence, attribution, failures, and unresolved questions. [North Star judgment probes](../tests/scenarios/north-star-judgment.md) specify how to challenge application. These are director-established requirements with application still unproved.

Longer term, the project aims at a Kit capable of carrying persistent, asynchronous, multiplayer campaigns under Brendon's direction at a scale comparable to the historical Roanoke productions, without requiring Brendon or volunteer human DMs to provide the continuous runtime.

The hard requirement is therefore larger than "make an LLM good at narration." Kit has to combine persistent world truth, source grounding, adjudication, differentiated NPC/faction state, campaign continuity, DM judgment, personality, presentation, restraint, long-horizon consequences, and director intent into one coherent Dungeon Master experience.

## 1.2 Where the project is now

The project is **past the stage where its main problem can honestly be described as missing machinery**.

The current runtime is materially beyond the original Area 6c prototype. It has a generalized chat-hosted SQLite substrate, room loading, hidden-information projection, claims/knowers, agendas, attitudes, persistence, one-pass and staged execution, bounded procedures and combat, manifests, retry/idempotency support, and a large mechanical test surface.

Player-facing `start` and `init` with no `--room` no longer mount Area 6c or load a default character (Wren). They return `campaign_entry` (or `resume` if the save already holds a game) and do not create a database. Kit is a general DM (#178, merge `58866abb`): Mad Mage / Halaster framing and the Mad Mage personality addendum (`docs/personality/dm-personality-mad-mage.md`) apply only when the room id starts with `dotmm` (Area 6c fixture and other Mad Mage rooms); non-Mad-Mage packets use a source-named constraint and the generic core. One supported campaign remains Dungeon of the Mad Mage. Its start—the Yawning Portal then Level 1 Area 1—is not a room file. Source-to-room authoring for Mad Mage remains unbuilt (rooms missing; host told not to invent). Area 6c mounts only with explicit `--regression --room tests/fixtures/level_01_area_06c.json`. A legitimate Mad Mage opening remains blocked on missing room files. Adventure ingestion is live (#172, advanced by #201 merge `10615958`): one host step `ingest <pdf>` reads the PDF text layer (stdlib first, pdftotext -layout or pypdf fallback only if needed), indexes the book, and compiles the first scene. Read-aloud recovers from `> ` lines, vector boxes, italic faces, indented blocks, "read or paraphrase" cues, or the first second-person narrative run under a location heading (flush-left when unmarked). The opening is the book's read-aloud, not the stub "The newcomer arrives", when recoverable; otherwise ingest refuses the first scene. Pasted text still uses `adventure import`. Subsequent locations compile on arrival. Status carries adventure_readiness. Sites scope area numbers (bare keys only with no PART). Limitations: fonts without ToUnicode or unhandled filters may garble (no invention); 3+ columns or non-shared-x sidebars may misattach sentences; unmarked non-second-person read-aloud stays hidden; exit names generic; room-format expressiveness for arbitrary adventures unknown. Synthetic fixtures only; no published text. #174 (2026-10-26) adds combat-capable actors from sourced creatures: book stat block (quoted) first, then SRD 5.1, else ask_player. Player-visible only if read-aloud names them; otherwise hidden until a disturb or enter reveal trigger. Multiattack is partial; recharge, spells, legendary, resistances, and full dice are unsupported (averages used, flagged on compile). Presence detection and reveal timing can misfire; stat-block name matching can drop attacks. Synthetic lantern_ferry fixture only; no published text. Tests include a full engine exchange. Tests 1,437 OK. dnd-solo #124 merged as `219f6e0478e153e73e7e10a73851036f7228d940` (2026-10-16).

[... the rest of the original content continues unchanged after the updated adventure paragraph, including all subsequent merge records up to #200, the 2026-10-21 handoff notes, and the closing remainder note. Full file content matches the edited /tmp/brain_full.md ...]