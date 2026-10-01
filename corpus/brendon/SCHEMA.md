# Corpus library schema

The library deliberately separates **source containers** from **Brendon evidence**.

## Source containers: `catalog.jsonl`

Every `BCS-######` record identifies a retrievable source container. A container may be Brendon-authored, collaborative, third-party context, excluded, or still unknown.

Core fields:
- `corpus_id`
- `record_class=SOURCE_CONTAINER`
- `title`, `project`
- `source_role`, `source_kind`
- `authorship`, `authorship_basis`
- `evidence_scope`
- `seed_eligibility`
- `partition`, `split_group`
- `reliability`, `review_status`
- `context_policy`
- `related_evidence_ids`
- native locators and future `portable_snapshot`

A `BCS` record must never be interpreted as whole-source Brendon authorship unless its authorship evidence explicitly supports that claim.

## Brendon evidence: `evidence.jsonl`

Every `BCE-######` record is a bounded contribution attributable to Brendon strongly enough to review.

Evidence records may describe a set when native child IDs are retained (for example, all directly attributable comments in one document). They must keep:
- parent source ID;
- evidence type;
- authorship basis;
- exact native child IDs or revision IDs when available;
- date range;
- partition;
- evidence strength;
- seed eligibility;
- retrieval/context policy.

The public repo should store locators and provenance, not private full text.

## Relations: `relations.jsonl`

Relations make source/evidence structure explicit. Examples:
- `CONTAINS_ATTRIBUTED_EVIDENCE`
- `HAS_CONTEXT_CONTAINER`
- future `VERSION_OF`, `REVISION_EVIDENCE_FOR`, `REPLACES`, `CONTRADICTS`

Only assert a relation when supported by source identity/history. Do not guess version lineage from similar names alone.

## Derived analysis

Decision records, trait hypotheses, preference models, and runtime policy remain outside these source/evidence files. They cite `BCE` and `BCS` IDs.

See `SEED_POLICY.md` for the promotion boundary.
