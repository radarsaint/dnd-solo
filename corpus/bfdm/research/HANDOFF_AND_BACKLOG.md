# Research Handoff and Backlog

**Status date:** 2026-10-02  
**Purpose:** Keep current work from being stranded in chat history.

## Work streams

### Work GPT
Expected to resume:
- ingesting Google Drive documents and project files into the private `bfdm-corpus`;
- storing material in machine-searchable form (including SQLite/indexed form where appropriate);
- preserving human-readable forms;
- retaining IDs, timestamps, authorship, provenance, and revision relationships.

**Binding Work GPT contract:** `INGESTION_CONTRACT.md`

**Executable assignment:** `ingest/WORK_GPT_TASK.md`

Do not accept an ingestion PR that substitutes a different ID/dedup/layout/schema strategy without deliberate review.

### Grok
Expected to resume:
- lower-level Kit / GitHub/runtime work;
- harvesting additional Discord game servers into the corpus.

Remaining Discord servers still require Brendon to assign/provide access to Grok as needed.

### Research GPT
Current useful scope:
- research methodology;
- source-gap identification;
- organization of existing findings;
- cross-campaign research questions;
- evidence review;
- longitudinal / revision-aware analysis;
- synthesis only when source coverage supports it.

Avoid duplicating ingestion/runtime work unless a gap blocks research.

## Governing numbered cleanup sequence

The current cleanup sequence is authoritative in `research/NEXT_HANDOFF.md`:

- Points 1–3: completed;
- Point 4: reconcile the 51-source legacy staging body into canonical `bfdm-corpus`;
- Point 5: deliberately review and integrate PR #5;
- Point 6: recover the later Area 6c verbatim human-test transcript;
- Point 7: archive-first invariant, completed and governing.

Do not renumber normal research backlog items as replacements for these points.

## Immediate preservation priorities

1. **Migrate/reconcile earlier staged source containers**
   - Earlier staging contained 51 normalized source containers.
   - Reconcile these with canonical `radarsaint/bfdm-corpus`.
   - Do not create a second private corpus repo.

2. **Reconcile S3 staged containers**
   - Week 2 is already `BCS-000029`.
   - Week 4 is already `BCS-000037`.
   - Preserve existing BCS IDs while migrating/reconciling staged source bodies into canonical `bfdm-corpus`.
   - Use `research/legacy-staging/manifest.all.jsonl` as the ID map; do not reassign from memory.

3. **Complete remaining Discord harvests**
   - Needed before cross-season behavioral conclusions.
   - Preserve server/channel/thread/message/user/attachment/reaction provenance.

4. **Complete Drive/project ingestion**
   - Preserve revision history where available.
   - Preserve comments, authorship, document relationships, and dates.
   - Keep raw/human-readable versions in addition to searchable indexes.

5. **Refine the machine-readable campaign registry as coverage improves**
   - baseline chronology/identity registry is now implemented under `registry/`;
   - replace UNKNOWN fields only with source-supported dates, scale, format, staff, server, and identity evidence;
   - keep series-level context separate from project-specific claims;
   - continue recording major source families, revisions, and design experiments without treating the registry as evidence itself.

6. **Preserve mechanical/worldbuilding lineages**
   - early Arcanian race versions → Almanac → 2020 race edits/final handouts;
   - class/subclass experiments such as Clerrook;
   - 2026 mapped/reskinned isekai races;
   - drafting/balance documents where the reasoning survives.
   - see `research/source-leads/homebrew-mechanics-worldbuilding.md`.

7. **Preserve early Roanoke revision family**
   - `The Rowing Oak` and `The rowing oak guide.` now provide a revision-backed July 2018 anchor;
   - preserve their Drive revision history and collaborative modifier metadata;
   - reconcile whether the formal label "Season 1" exists elsewhere instead of silently assigning it.

## Research backlog after coverage improves

### A. Cross-era DM judgment
Compare early Roanoke → later Roanoke → intermediate campaigns → Earthfall.

Look for:
- persistent instincts;
- evolved technique;
- abandoned methods;
- later corrections of earlier assumptions.

### B. Negative-space pass
Current extraction over-samples visible changes.

Study:
- functioning play left alone;
- hooks allowed to fail;
- NPCs not promoted;
- mechanics not changed;
- cool ideas rejected;
- restraint as a successful decision.

### C. Emergence and formalization
Track features that begin as player behavior or ad hoc solutions and later become explicit design.

Candidate:
- interpersonal / "dating sim" play.

### D. Creative-method pass
Ask:
> What kinds of boundaries does Brendon repeatedly try to push, and how does he turn a strange idea into something playable?

Candidate evidence:
- 24-hour Roanoke format;
- Bowling Event;
- large persistent player populations;
- custom mechanics/classes/races;
- later Earthfall systems.

### E. Mechanical-design lineage
Study how custom races/classes/subclasses/items/systems change across drafts:
- what gets cut;
- what gets simplified;
- what survives;
- where flavor becomes mechanics;
- balance vs spectacle vs usability.

### F. Campaign-architecture research
Eventually reconstruct how Roanoke-class campaigns are designed and operated:
- scheduling;
- factions;
- free play;
- invitationals;
- persistent locations;
- multiple DMs;
- player-owned social space;
- adaptive slack.

This is distinct from general DM judgment.

## Evaluation assets

Keep the existing S3 v1/v2/v3 work available as:
- research history;
- candidate evaluation set;
- methodology examples.

Do not automatically feed every derived conclusion into Kit as truth.

## Current GitHub research workspace

Branch:
`research/organize-current-work-v1`

Draft PR:
`#5 — Organize current BFDM research and Kit evaluation`

S3 research PRs #2–#4 are now closed as superseded by PR #5, without merging. Their branches/history remain available as provenance.

Do not merge PR #5 without deliberate review.
