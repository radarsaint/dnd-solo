# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-11-13 (destination-assumes-origin link web from merged #210; prior playable picker from #209)
**Context reviewed against:** `dnd-solo/main @ 9fd048f04bad3af2aaf52dd804d68d2c2c69518a`; `bfdm-corpus/main @ 66f3c62fb87976224174180db0a57e50d129587e`

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
Source-span recovery for printed two-column layouts now reconstructs several physically plausible gutters instead of treating the earliest long space as the sole column boundary. Columns are read top-to-bottom, left-to-right; a source span is bound to its containing heading and stops before the next keyed location. The original book text and strict contiguous source citations remain unchanged. Scene acceptance is refused when the whole opening cannot be recovered, rather than accepting a fabricated or empty scene. This repairs the hollow Phandelver opening observed in Nagatha Blind Run 18. Synthetic tests cover interleaved layouts, right-column openings, same-page and cross-page continuations, wrong-room leakage, and fail-closed retries. Remaining Blind Run 18 defects (talk, Perception, pending_ruling, Stealth, index snapshot) were later addressed by #207 and #208. Real private-PDF blind retest and full suite certification remain outstanding. No change to North Star, KRABS, or non-adventure paths.

**2026-11-13 snapshot comparison and source recovery (merged #207 / 547199d):**
Accepting an opening can change the active index's selected start and derived scene fields without changing a byte of source. Snapshot comparison now checks only source-derived structural records (version, sha256, chars, chapters, pages, map_pages, stat_blocks, npcs, checks). This fixes the false rejection of the next full-book index observed in Blind run 18. Preparation-time whole-book structural index is retained. Changed source bytes, a missing snapshot half, or a tampered structural field still fail closed. Synthetic tests added; full suite reported 2138 passed, 1 skipped on Python 3.8 and 3.13. No change to North Star or KRABS.

**2026-11-13 playable fallback, prepare-time asks, NPC replies, off-script rulings (merged #208 / abe8e134):**
When two-column reconstruction yields an empty private source span, the retained PDF is re-read with a spatial extract or `pdftotext -raw`. If recovery still fails, the start is accepted as burst-only: attested people stay empty, and the host gets a clear re-ask plus a picker of real opening read-alouds. There is no silent legacy-guesser fallback and no stall. The host is handed the whole opening section (opening heading through the next keyed area or a heading of the same level, with a cap); validation requires contiguous quotes and checks statuses and visibility against the governing sentences. The failed-quote picker offers only playable opening read-alouds (boxed or second-person fiction), never a how-to, rules, or front-matter title. A look on an attested notice beat and a sneak ask for Perception and Stealth at prepare time, with a turn id. A failed Perception springs pressure only when the source's governing sentence says so. Host speaker aliases and short names map to the room's canonical NPC label so a present character can answer. Off-script fire and dousing acts go through the existing rules engine as a kit ruling, with a spoken line and a turn id; bare "light" in "hold up a light" stays a simple act. Host-transcript tests drive the real prepare/complete cycle on synthetic fixtures. Full suite reported 2147 tests, 1 skipped, 0 failed on Python 3.8.20 and 3.13.5. Real private-PDF blind retest remains outstanding. No change to North Star, KRABS, or non-adventure paths.

**2026-11-13 playable picker from index only and performed NPC replies (merged #209 / ecaec030):**
The failed-quote picker is built only from sections the index has already classified as playable (an adventure opening or a keyed area or encounter with attested boxed read-aloud). The heading-text scan that invented candidates is removed. Contents headings, rules and front matter, credits, appendices, and instructional lines are never candidates. If the index has no playable section, the table line is one honest short message with a working burst-only start, never a stall. Naming a listed title starts that section through the normal validated scene form. An accepted npc_reply for an attested present person is performed as that person speaking: a named speaker line in their voice, then a handoff to the player. guard_spoken no longer folds those lines into a Narrator paragraph; Python still validates who is present and refuses invented people. On a pick, section recovery reuses the prep-time index body bounded by the next keyed area already recorded (including a cross-page continuation) and ignores a later short derived scene that only repeats the boxed words; the burst is located with one search. Landing places the burst in recorded location bodies only and reuses the section already recovered on the scene-required pass, with no double recovery and no search of later pages of the whole book. Two-column handoff remains as landed in #208. Full suite reported 2170 tests, 1 skipped, 0 failed on Python 3.8.20 and 3.13.5. Real private-PDF blind retest remains outstanding. No change to North Star, KRABS, or non-adventure paths.

**2026-11-13 destination-assumes-origin link web (merged #210 / 9fd048f0):**
At preparation the index records each section's links to text elsewhere as a small graph. Continuations (a section that already runs onto a later page or past a column gap, bounded by the next keyed area) unify the recorded body into the graph. Explicit pointers ("see appendix", "see area N", page or chapter references). Names matching a stat block, magic item, or NPC entry (starting with creatures present in the opening section only). Standalone boxes (sidebars, handouts, rumor tables, NPC notes) are traced backward to an anchor (a nearby keyed area, a named person, or a trigger phrase such as "if the characters ask/search/touch"); boxes with no anchor are marked unlinked. Each link is confirmed or likely. At play time a section's own text is handed over immediately. Linked material one hop away loads lazily: confirmed links may be prefetched after the opening is up or on first touch; likely links only when play touches their subject. The landing path does not walk the graph or load target text. Python validates word for word any quote drawn from linked text, and the model cannot assert a link as fact. When play touches a linked thing, Kit answers from that attested text in one line, with no stall and no invented facts. Mechanics, DCs, and bonuses stay off the table. Full suite reported 2181 tests, 1 skipped, 0 failed on Python 3.8 and 3.13. Synthetic fixtures only. No change to North Star, KRABS, or non-adventure paths.

(The remainder of the document continues with the established sections on workstreams, risks, acceptance, and history. The updates above are the only semantic changes required by the recent merges and this provisional observation.)
