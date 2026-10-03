# Project Decisions and Guardrails

**Purpose:** Preserve current project-level decisions that came from active planning conversations.  
**Evidence status:** These are not historical corpus findings and must not be cited as proof of Brendon's past DM behavior. They are current project directives / research guardrails.

## Governing corpus invariant

Brendon's explicit project directive:

> **bfdm-corpus is not primarily a training dataset. It is the durable research archive of your D&D creative history. Kit is one consumer of it.**

Operational interpretation:

- corpus preservation and provenance come before present-day model convenience;
- Kit integration is a downstream curation problem;
- material is not excluded because it is not immediately trainable or seed-eligible;
- no single Kit architecture gets to redefine the corpus;
- model-ready datasets are disposable/rebuildable derivatives, while the historical archive is canonical.

This directive governs ingestion, research, repo structure, and future Kit-export decisions.

## Desired outcome for Kit

Kit should become **interesting and useful to Brendon**, with at least two important future roles:

1. **Solo / small-table Dungeon Master**
   - run actual D&D competently;
   - notice what matters in play;
   - react with judgment rather than generic narration;
   - sustain NPCs, stakes, challenge, humor, continuity, and surprise.

2. **Creative design partner**
   - help design future campaigns and seasons, including something as structurally ambitious as a future Roanoke season;
   - challenge assumptions;
   - recall relevant past experiments and failures;
   - connect ideas across years of work;
   - generate genuinely new design rather than clone old campaigns.

The corpus should not be reduced prematurely to "imitate Brendon's prose" or "what would Brendon do?"

## Research sequencing

Current decision:

> Coverage and preservation should precede grand synthesis.

Roanoke Season 3 is useful as a methodology testbed, but broad claims about Brendon should wait until:
- additional Discord servers are harvested;
- Google Drive and project material are ingested;
- multiple campaigns / eras can be compared;
- later work, especially Earthfall, is represented strongly enough to study development over time.

Do not let S3's evidence density masquerade as importance.

## S3 caution

Roanoke sometimes operated with roughly **30–100 concurrent players**, multiple DMs/moderators, asynchronous channels, scheduled events, factions, and many simultaneous scenes.

Observed S3 behavior may therefore represent:
- Brendon's general judgment;
- Roanoke-scale operational adaptation;
- both;
- or unresolved context-specific behavior.

Future cases should preserve table/campaign scale.

## Development over time

Do not flatten early Brendon and later Brendon into an average.

The research should distinguish:
- persistent traits;
- evolved practices;
- format-specific adaptations;
- abandoned/superseded practices;
- explicit later corrections of earlier behavior.

The period from early Roanoke through Earthfall should be treated as developmental history.

## Emergent interpersonal play

The interpersonal/social layer later called the **"dating sim"** was described by Brendon as **entirely emergent**, rather than a deliberately authored initial campaign feature.

This should be preserved as current provenance/context and tested against source evidence before converting it into a generalized research conclusion.

Potential research pattern:
> emergent behavior → recognized value → accommodation / consequence → later formalization

## Human-readable synthesis

A human-readable synopsis for Kit remains a desired artifact, but **not yet**.

Reason:
- writing it now risks hardening S3 into doctrine;
- later seasons and later practice may contradict or refine S3;
- the broader archive contains more than DM judgment.

When eventually written, it should be understandable enough for Brendon and Kit to discuss, challenge, and revise together.

## Corpus breadth

The archive includes more than campaign transcripts:
- custom races/classes/subclasses;
- worldbuilding and lore;
- adventure drafts;
- campaign operations;
- mechanics;
- revision histories;
- comments;
- writing;
- experiments that went nowhere;
- unusual format experiments such as the Bowling Event.

Research should preserve that breadth because the ultimate value of the corpus is not yet known.

## Implementation restraint

Do not prematurely decide that Kit's use of the corpus must be:
- RAG;
- a static personality prompt;
- fine-tuning;
- preference training;
- a simulated apprenticeship;
- or any other single mechanism.

Those are implementation options downstream of understanding the material.

## Core archival principle

Keep separate:
1. raw sources;
2. attributable evidence / chronology;
3. research interpretation;
4. current project directives.

This allows conclusions to change without rewriting history.


## Identity across seasons

Brendon's screen names change from season to season.

Current user-confirmed alias:
- `DM radar`

Use `research/IDENTITY_RESOLUTION.md` for attribution. Prefer platform/account IDs and server/date-specific mappings over nickname matching.

This is a provenance rule, not a personality finding.

## Curation into Kit

The BFDM corpus is a research archive first.

Do not compress the corpus into one runtime prompt or one voice file merely because a current implementation has a small prompt budget.

Future Kit integration may use different mechanisms for:
- private DM judgment/personality;
- retrieval of precedent;
- expressed/table voice;
- evaluation.

Each promoted item should remain traceable to evidence/source provenance.
