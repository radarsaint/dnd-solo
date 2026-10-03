# Attributable Evidence

This directory is the private BFDM corpus evidence registry.

It mirrors the existing BCS/BCE/BCR ontology established in `dnd-solo/corpus/brendon/` and extends it inside the canonical private corpus.

## Files

- `catalog.jsonl` — source-container registry. Currently includes the existing BCS-000001–BCS-000067 bootstrap plus new private records.
- `evidence.jsonl` — bounded attributable Brendon evidence.
- `relations.jsonl` — explicit evidence/source relations.
- `sources/` — portable evidence snapshots when a native source is unavailable or insufficiently portable.

## Current extension

`BCS-000068` preserves a curated verbatim excerpt set from the 2026-10-01/02 ChatGPT project conversation.

It contains eight bounded evidence records:

- `BCE-000005` — growth across seasons + Roanoke scale retrospective context
- `BCE-000006` — "dating sim" emergence retrospective statement
- `BCE-000007` — corpus breadth / pushing D&D boundaries self-description
- `BCE-000008` — coverage-before-synthesis project directive
- `BCE-000009` — desired Kit usefulness: solo DM + future Season 6
- `BCE-000010` — future Roanoke-style design capability
- `BCE-000011` — identity assertion: changing screen names / DM radar
- `BCE-000012` — original corpus objective: judgment rather than prose/lore

## Important boundary

Direct attribution does not mean personality-seed eligibility.

Most project-goal and identity records above are deliberately marked `REJECTED_SEED` because their value is governance/provenance, not personality formation.

The retrospective creative-method/emergence records are only `ELIGIBLE_FOR_REVIEW`; they are not approved seed.

## Portability limitation

The current ChatGPT connector does not expose stable native message IDs for these conversation turns.

For BCS-000068:
- exact user wording is preserved;
- exact UTC timestamps are preserved;
- the portable snapshot is the durable local evidence object;
- the source explicitly labels itself as a curated excerpt set rather than a raw/full transcript.
