# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-11-12 (source-attested opening/native adjudication from merged #204; adventure PDF indexing lifecycle from merged #205; two-column PDF encounter recovery from merged #206)
**Context reviewed against:** `dnd-solo/main @ c1c9034ebe858971433b3d3befcc50fa5e1fd34f`; `bfdm-corpus/main @ cf65ec04572b2a033383344d1f2583e3380686f7`

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

**2026-11-02 provisional non-DM creative-judgment observation (from #115 comment 6598407850):**
A single self-reported trajectory in a Warden's Creations homebrew remaster collaboration changed from repeated dissatisfaction with an initial GPT (generic visuals, malformed details, inaccurate mechanics, revisions damaging prior wins) to explicit user approval after Kit was used as a creative assistant/personality rather than the DM runtime. The work was reframed around the user's end objective. Task decomposition separated source-faithful page/art-direction composition, independently typeset authoritative mechanics, and standalone character illustration, so one revision did not damage approved components. User approved page direction and a standalone winter-clad Tatankan Gun Fu illustration (said to be embedded in a Google Doc). One five-barrel firearm anomaly was tolerated. Publication readiness, final assembly, mechanics sync, and release sign-off were not established.

Supported: one reported case where protection of prior successful decisions and recognition of the whole creative objective (rather than local correction alone) coincided with user satisfaction. Consistent with KRABS emphasis on situation recognition, whole-task purpose, intervention choice, and preservation of accepted state.

Not supported: Kit has a superior image model; a complete/verified Kit runtime was active; Kit's persona alone caused the improvement; the behavior reliably generalizes; non-DM satisfaction is solved; the homebrew was completed. Full transcript, runtime identity/manifest verification, image-generation conditions, and controlled comparison have not been independently audited. Archive retrieval from Drive lacked established complete manifest verification. Treat as one case/possible future regression probe, not a conclusive architectural result or change to North Star, KRABS, or runtime architecture. Confounds include additional references, repeated corrections, and framing change.

**2026-11-12 adventure indexing lifecycle (merged #205 / aba4b93):**
Full-book structural indexing of a retained PDF now occurs during preparation, after the fast opening-window extract and before the opening skim is submitted, via the returned `index_command`. It indexes the whole book structurally without sending the rest of the book to the model. An already-accepted skim, heard cursor, and mounted scene are preserved by `deepen_index()`; a verified opening is not reset to `scene_required`. Player Yes., Go on, or in-fiction action does not trigger full indexing. This is a lifecycle repair plus scheduling change on main; Mad Mage rooms remain unauthored and room-format expressiveness open. No change to North Star, KRABS, or non-adventure paths.

**2026-11-12 source-attested opening and native adjudication (merged #204 / 1b3b9d81):**
Source-verified openings use a host-proposed compact scene contract (place/people/goal/knowledge/discovery/pressure analysis with source quotes and evidence status). Python validates shape, contiguous location-bounded quotations, visible text scope, and complete conditional sentences; rejects unquoted extra mechanics. Source-verified scenes no longer use the lexical goal/people/place guessers. Verified opening verbs route through existing RoomAdjudicator rather than the opening-specific fixed Perception threshold, auto-bypass or forced surprise handler. Source-attested hidden actors participate in native Perception/Stealth handling; prospective entry attacks deferred unless explicitly represented as entry activation. Read-aloud progress is carried by an opening_cursor event in the authoritative SQLite transaction (sidecar is a convenience cache after successful commit). The entire supplied PDF is retained private, content-addressed, and SHA-256-checked next to the save. Local synthetic tests (203 selected) passed on Python 3.13.5; complete unittest discovery timed out at 150s; full suite is NOT CERTIFIED. Owner's private adventure PDFs, answer keys, second/third-book results, and a fresh independent human-host playthrough are NOT VERIFIED. Text-matched citations constrain inventions but cannot prove the model interpreted a person's actual goal or trigger timing correctly; human review and adversarial semantic cases remain necessary. Legacy skim requests without scene still follow existing logic for compatibility. No change to North Star or KRABS.

**2026-11-12 two-column PDF encounter recovery (merged #206 / c7478c9):**
Source-span recovery for printed two-column layouts now reconstructs several physically plausible gutters instead of treating the earliest long space as the sole column boundary. Columns are read top-to-bottom, left-to-right; a source span is bound to its containing heading and stops before the next keyed location. The original book text and strict contiguous source citations remain unchanged. Scene acceptance is refused when the whole opening cannot be recovered, rather than accepting a fabricated or empty scene. This repairs the hollow Phandelver opening observed in Nagatha Blind Run 18. Synthetic tests cover interleaved layouts, right-column openings, same-page and cross-page continuations, wrong-room leakage, and fail-closed retries. Remaining Blind Run 18 defects (talk, Perception, pending_ruling, Stealth, index snapshot) are not addressed. Real private-PDF blind retest and full suite certification remain outstanding. No change to North Star, KRABS, or non-adventure paths.

(The remainder of the document continues with the established sections on workstreams, risks, acceptance, and history. The updates above are the only semantic changes required by the recent merges and this provisional observation.)
