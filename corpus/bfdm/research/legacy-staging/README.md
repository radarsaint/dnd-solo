# Legacy Corpus Staging

This directory preserves metadata about the earlier ChatGPT Library staging body so it can be reconciled with the canonical private repository without losing source IDs or duplicating work.

## Canonical repository now

The old handoff document proposed creating a private repository such as `radarsaint/brendon-corpus`.

That instruction is **superseded**.

The canonical private corpus is:

`radarsaint/bfdm-corpus`

Do not create another private corpus repository.

## Staging archive

Library path:

`/Brendon Corpus Staging/Current/brendon-corpus-staging.zip`

Stable Library ID recorded at staging time:

`libfile_ed602fffc384819192d72433c61efdb4`

The staging body contained:
- 37 Roanoke source containers;
- 2 Earthfall source containers;
- 3 Bastion/Redoubt source containers;
- 8 At War's End source containers;
- 1 Exploration Impossible context-only container;
- 51 total containers;
- 75 extracted embedded assets;
- originals beside normalized Markdown;
- checksums and manifests.

## Attribution boundary

Inclusion in the staging body does not establish Brendon authorship.

`BCS-000059` is Michael Kennish's *Exploration Impossible* manuscript and is context-only for Brendon editorial evidence.

## Important reconciliation finding — 2026-10-01

The legacy staging manifest proves that two sources previously described by the S3 revision-family pass as "corpus gaps" had already been normalized:

- `BCS-000029` — *Roanoke S3 v2 W2 Breakdown.docx*
- `BCS-000037` — *Roanoke s3w4 Break down.docx*

They are therefore **canonical-repository reconciliation gaps**, not missing source containers.

The same manifest confirms:
- `BCS-000045` — *Roanoke Season 3 Rough Draft.txt*
- `BCS-000046` — *Roanoke Season3 Change Log.docx*
- `BCS-000048` — *RoanokeS3 doc V2 W1.docx*
- `BCS-000052` — *RoanokeS3W3 Breakdown.docx*
- `BCS-000053` — *RoanokeS3W5 Break Down.docx*

Future source-ID assignments should use the manifest rather than memory.

## Preserved metadata

[manifest.all.jsonl](manifest.all.jsonl) is copied here exactly as metadata from the legacy staging body. Raw source bodies remain in the staging archive / source-ingestion workflow and should not be duplicated into the research layer.


## Reconciliation audit — 2026-10-02

See:

- `RECONCILIATION_2026-10-02.md`
- `../../ingest/reconcile_legacy_staging.py`

Audit result:
- all 51 legacy IDs are present in `evidence/catalog.jsonl`;
- 51/51 source bodies are still absent from canonical `sources/` / `context/`;
- 284 source-container files remain to be transferred;
- the archive SHA-256 is `cebe18692ba3b8a2fe220d164cb722e18d81766edcc03f39ae0f18174350ea7a`.

The migration script was tested against the real archive for clean dry-run, apply, idempotence, and conflict refusal.

The current ChatGPT GitHub connector cannot directly transport the roughly 86 MB of binary DOCX/XLSX/image content from a Library file reference. This is an execution limitation, not a reason to weaken the definition of reconciliation.
