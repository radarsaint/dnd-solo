# Project Map

This file describes where different kinds of work currently belong.

It is project organization, not historical corpus evidence.

## `radarsaint/bfdm-corpus` — private archive and research

Canonical private corpus repository.

Use it for:
- raw/private Discord harvests;
- machine-readable campaign/project and identity registries under `registry/`;
- normalized campaign/source material;
- source provenance and chronology;
- derived BFDM research;
- Kit evaluation records that need to remain private/research-oriented;
- cross-campaign synthesis.

Current research workspace:
- branch `research/organize-current-work-v1`
- draft PR #5

## `radarsaint/dnd-solo` — Kit product/runtime

Use it for:
- Kit runtime;
- Dungeon of the Mad Mage source/runtime integration;
- state, bridge, adjudication, memory, claims, procedures;
- tests and fixtures;
- active personality/product specifications;
- implementation experiments.

It also contains earlier public research scaffolding and historical research PRs. Those are being indexed/copied into `bfdm-corpus/research/prior-dnd-solo/` where useful.

## Public corpus scaffold in `dnd-solo`

Important merged lineage:
- PR #39 — source-centric Brendon corpus index;
- PR #40 — Exploration Impossible attribution correction;
- PR #41 — source-container vs attributable-evidence ontology.

Those established useful public IDs/policies without publishing the full private corpus.

The private `bfdm-corpus` is now the canonical body. Public scaffold IDs and provenance rules should remain compatible where possible.

## Current human/agent work split

### Brendon
Provides:
- source access/ownership context;
- remaining Discord-server assignments;
- direct corrections;
- live Kit evaluation;
- final product/design judgment.

Do not turn him into the routine terminal/operator layer.

### Work GPT
Current expected focus:
- Google Drive/project ingestion;
- searchable + human-readable source storage;
- provenance, revisions, comments, IDs.

Binding assignment and schema:
- `INGESTION_CONTRACT.md`
- `ingest/WORK_GPT_TASK.md`
- `ingest/document_archive_schema.sql`
- `ingest/source_metadata.schema.json`
- `ingest/ingest_report.schema.json`

Work GPT should not improvise a competing ingestion layout.

### Grok
Current expected focus:
- additional Discord harvesting;
- lower-level Kit/runtime/GitHub engineering.

### Research GPT
Current focus:
- organize research;
- preserve corrections;
- identify source gaps;
- revision-aware / cross-source analysis;
- cross-era research once source coverage supports it.

## Non-duplication rule

Before creating a new corpus record or research artifact:
1. check whether it already exists in legacy staging;
2. check `bfdm-corpus`;
3. check the relevant `dnd-solo` research/PR lineage;
4. preserve stable IDs rather than inventing replacements.

## Authority distinction

- Source archive answers: **what exists / what happened?**
- Evidence layer answers: **what can be attributed and reconstructed?**
- Research layer answers: **what might it mean?**
- Kit runtime answers: **what is true and actionable in the current game?**

No layer should silently impersonate another.
