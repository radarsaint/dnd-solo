# Dataset card and runtime fit

Version: `brendon-decision-v0.1`, first batch, 2026-10-01 UTC.

## Contents and status

- 23 decision records across seven named project families.
- 11 records from direct comments or a revision comparison; 7 from documented Kit feedback; 5 from older semantic-retrieval leads.
- 8 negative/preference records. None is a complete, approved chosen/rejected response pair.
- 6 cross-project hypotheses; 3 newly authored blind preference probes.
- 15 Empire City files in prospective evaluation quarantine; no validated held-out cases or model results.
- Source index: 53 imported files plus 10 source/report/hypothesis entries. Counts are source rows, not independent observations.

Every decision is written by an AI analyst. `authorship` identifies the evidenced contribution; it does not claim Brendon wrote the record. `confidence` describes evidence for the local decision. `generalization_confidence` separately qualifies its transfer to Kit.

## Representation

`decisions.jsonl` contains one object per decision. The context, desired experience, observation, diagnosis, decision, principle, anti-pattern and limits each carry a basis:

- `EXPLICIT`: stated or directly represented in the cited evidence; not necessarily verbatim. Source fidelity remains decisive.
- `INFERENCE`: analyst interpretation.
- `NOT_STATED`: null because the record lacks that reasoning.

Dates can be timestamps, days or documented intervals. Read source locators and date caveats before treating them as precise chronology. Missing original conversation IDs remain missing; provider-local retrieval labels are search leads, not permanent IDs.

`preferences.jsonl` distinguishes an actual rejected output, preferred design direction, self-reported edit and missing replacement. All `dpo_ready` flags are false. Do not manufacture preferred completions or label authored A/B responses as user choices.

## Architecture alignment

Kit currently separates adjudicated world state, private decision and public performance through KitChatBridge. The corpus can support future retrieval into the **private decision** phase: situation, competing concerns, demonstrated choice, limits and provenance.

The active runtime must still supply current facts, rules, claims, actor knowledge, agenda state and player intent. Historical lore is not runtime state. The public performer should receive only a scene-safe direction through the existing decision/public-brief mechanism. Do not forward this corpus's private historical facts as player-visible narration.

These records are not drop-in bridge turns: historical examples lack many live-state fields. No runtime adapter, automatic prompt loader, fine-tuning file, new model training or paid model call has been created. A future adapter should map evidence to `improv_read` / goal / move / public brief only where supported, and should never invent historical values to satisfy the runtime schema.

## Split and evaluation rules

The Markdown views repeat the JSON/JSONL records; do not ingest both as independent examples. Keep project families and near-duplicates together. This pass groups the whole Empire City project, including backlog and posts, outside discovery. Previously previewed TOC/planning snippets are ineligible. Existing pilot sources and transfer probes remain discovery-exposed.

Freeze the discovery model at a commit before curation reads the quarantined contents. Then verify attributable strong decisions and check duplication against old retrieval, related campaigns and conversation summaries. Construct new situations from the withheld judgments, with historical answers and scoring rubrics excluded from Kit's input.

The three A/B probes here are development probes. Present only BLIND_AB.md first; ab-analysis.json contains analyst predictions. Record order, response provenance, Brendon's choice and reason, including ties/neither. Disagreement is evidence; do not overwrite the original prediction.

## Raw source and publication boundary

Original campaign files remain in their indexed collection; comments and revisions have native IDs. Public artifacts preserve short exact excerpts and source pointers. Full fetched windows are an intermediate local cache, not a published manuscript archive. The prior PR #23 retrieval pilot remains historical material; its larger excerpts are not re-imported here.

This is a reviewable evidence corpus, not a validated personality or approved training dataset.
