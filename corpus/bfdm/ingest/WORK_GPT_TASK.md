# Work GPT Assignment — Drive / Project Corpus Ingestion v1

This is the executable assignment. The binding rules are in [../INGESTION_CONTRACT.md](../INGESTION_CONTRACT.md).

## Goal

Build the durable non-Discord source archive for BFDM from:

1. the existing 51-container legacy staging body;
2. connected Google Drive D&D/TTRPG creative-history material;
3. relevant ChatGPT Project/Library files.

Deliver both:

- human-readable, provenance-preserving BCS source containers;
- `indexes/documents.sqlite` using [document_archive_schema.sql](document_archive_schema.sql).

Do not do personality synthesis, DM-decision extraction, or training-data construction during this task.

## Branch

PR #5 has been merged.

Create `ingest/drive-project-v1` from current `main`.

Do not write directly to `main`.

### Current Point 4 transport note

The reconciliation audit and migrator are already complete. The previous chat runtime re-materialized and verified the 86.9 MB Library archive but could not push the binary source containers because it lacked an authenticated/networked binary Git transport.

Work GPT should therefore make **Phase A the first write task**. If its environment has a real authenticated Git checkout or another binary-safe repository path, perform the migration and final dry-run. If it has the same connector-only content-string limitation, stop Phase A and report that exact transport boundary rather than attempting model-visible base64 transport or starting overlapping Phase B ingestion.

## Phase A — reconcile the existing staging body first

Canonical staging archive:

`/Brendon Corpus Staging/Current/brendon-corpus-staging.zip`

Recorded Library ID:

`libfile_ed602fffc384819192d72433c61efdb4`

Before assigning any new BCS IDs:

1. obtain the archive;
2. verify its manifest against `research/legacy-staging/manifest.all.jsonl`;
3. migrate/reconcile its 51 BCS source containers into canonical source/context paths;
4. preserve the existing BCS IDs;
5. preserve original/export bytes, normalized text, comments, assets, and checksums;
6. do not recreate W2/W4 or any other staged source under a new BCS.

Expected existing project counts in that staging body:

- Roanoke: 37
- Earthfall: 2
- Bastion/Redoubt: 3
- At War's End: 8
- Exploration Impossible context: 1

The staging body is not assumed complete. It is the starting source shelf.

## Phase B — enumerate Drive and Project/Library candidates

Create an inventory before ingesting.

For every candidate record:

- provider/surface;
- native ID;
- title/filename;
- MIME/type;
- created/modified timestamps when exposed;
- project/folder context;
- Drive URL/cloud locator when present;
- Project/Library IDs when present;
- candidate existing BCS match;
- disposition: `REUSE_BCS`, `NEW_BCS`, `POSSIBLE_DUPLICATE`, `EXCLUDE_UNRELATED`, `UNAVAILABLE`.

Do not assign a new BCS until deduplication checks are complete.

## Phase C — ingest sources

For each accepted source:

1. establish/reuse BCS;
2. write/update the human-readable source container;
3. preserve current body;
4. preserve exact raw bytes or clearly-labeled export snapshot when available;
5. preserve native comments/replies;
6. enumerate revision metadata;
7. fetch historical revision bodies according to the contract;
8. extract/preserve embedded assets when feasible;
9. update `evidence/catalog.jsonl` only for BCS source-container metadata;
10. update `indexes/documents.sqlite`.

Do not mint BCE/BCR research conclusions in this phase.

## Phase D — validate

Required:

- validate every JSON/JSONL file;
- verify no duplicate BCS IDs;
- verify no Drive native ID maps to multiple BCS records;
- verify every stored representation's SHA-256;
- run SQLite `PRAGMA integrity_check;`;
- verify no orphan foreign keys;
- run known FTS smoke queries;
- run `python registry/validate_registry.py`;
- update project/identity registry only where source evidence supports it;
- verify Git LFS is used for SQLite;
- verify no WAL/SHM/journal/temp archives are in the PR.

## Phase E — report

Create:

- `ingest/reports/<date>-drive-project-v1.md`
- `ingest/reports/<date>-drive-project-v1.json`

The report must state exactly:

- what surfaces were searched;
- how many candidates were found;
- how many existing BCS records were reconciled/reused;
- how many new BCS records were created;
- highest BCS allocated;
- possible duplicates requiring later review;
- clearly unrelated exclusions;
- inaccessible/failed sources;
- comments/replies captured;
- revision metadata count;
- historical revision bodies captured;
- assets captured;
- SQLite table counts;
- integrity/checksum results;
- known remaining gaps.

## Do not make Brendon do clerical work

Use the connected sources and repository state to resolve routine identity/deduplication work.

Ask Brendon only when a stop condition in the contract genuinely requires human provenance/context that cannot be established from the source record.

## Completion standard

Do not report “ingestion complete” merely because files were copied.

Completion means a later researcher can start from a BCS ID and reconstruct:

- what the source is;
- where it came from;
- which representations were preserved;
- what comments/revisions were available;
- what was not captured;
- how to search it;
- and whether the source is attributable, collaborative, unknown, or context-only without guessing.
