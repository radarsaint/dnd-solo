# Legacy Staging Reconciliation Baseline — 2026-10-02

**Point:** 4  
**Status:** migration audited; source-body transfer still pending.

## What was checked

The Library staging archive at:

`/Brendon Corpus Staging/Current/brendon-corpus-staging.zip`

was materialized and inspected against the canonical `radarsaint/bfdm-corpus` research branch.

Archive SHA-256:

`cebe18692ba3b8a2fe220d164cb722e18d81766edcc03f39ae0f18174350ea7a`

The external staging checksum inventory was also available as `CHECKSUMS.sha256`.

## Identity / catalog reconciliation

The preserved legacy manifest contains **51 source containers**, exactly BCS-000017 through BCS-000067.

All 51 existing legacy BCS IDs are already represented in `evidence/catalog.jsonl`.

No replacement BCS IDs should be minted for these sources.

Project distribution:

- Roanoke: 37
- Earthfall: 2
- Bastion/Redoubt: 3
- At War's End: 8
- Exploration Impossible context: 1

## Physical bundle contents

The 51 source containers collectively contain **284 record files**:

- 51 originals;
  - 49 DOCX;
  - 1 XLSX;
  - 1 TXT;
- 51 normalized `source.md` files;
- 51 `metadata.json` files;
- 51 `comments.json` files;
- 5 `brendon-comments.native.json` supplements;
- 75 extracted assets.

The archive contains 296 non-directory files total when its top-level manifests/status/readme files are included.

The source-container originals and assets account for about 86 MB of binary material.

## Canonical-repo comparison

At audit time, the research branch contains:

- the 51-record manifest under `research/legacy-staging/`;
- staging README/index/status/handoff metadata;
- all 51 BCS IDs in the evidence catalog.

It does **not** contain the actual legacy source-container directories under canonical `sources/` or `context/`.

Therefore the current reconciliation state is:

- cataloged IDs: 51 / 51;
- migrated source bodies: 0 / 51;
- source-container files still pending transfer: 284;
- conflicting canonical source-body files observed: 0.

This is the concrete form of the earlier "two source stores" problem.

## Deterministic migrator

`ingest/reconcile_legacy_staging.py` performs the migration safely.

It:

1. verifies the archive manifest against the preserved repo manifest;
2. requires all 51 legacy BCS IDs to remain present in `evidence/catalog.jsonl`;
3. verifies manifest-declared original and normalized checksums;
4. optionally verifies the full external `CHECKSUMS.sha256` inventory;
5. compares every source-container file against the canonical target path by SHA-256;
6. classifies records/files as missing, already present, partial, or conflicting;
7. refuses `--apply` if any target differs;
8. copies only missing files;
9. verifies every copied file after transfer;
10. writes a machine-readable reconciliation report.

Tested locally against the real staging archive:

- clean dry-run: 51 `READY_TO_MIGRATE`, 284 `MISSING_TARGET`, zero errors;
- apply into an empty test repo: 284 files copied, zero checksum errors;
- second dry-run: 51 `ALREADY_RECONCILED`, 284 `ALREADY_PRESENT`;
- deliberate corruption test: 1 conflict detected and `--apply` refused with zero files copied.

## Current tooling limitation

The active GitHub connector can create UTF-8 files and base64 blobs, but it cannot accept a local/Library file reference as blob input. The staging archive contains roughly 86 MB of DOCX/XLSX/image binary material, so transporting those bytes through model-visible base64 is not a safe or practical migration mechanism.

For that reason, this pass does **not** falsely mark Point 4 complete.

The actual binary-safe transfer must be executed by an environment with both:

- filesystem access to the staging ZIP/checksum inventory; and
- authenticated git/GitHub write access to `bfdm-corpus`.

## Required execution

From a checked-out canonical repository:

```bash
python ingest/reconcile_legacy_staging.py \
  --archive /path/to/brendon-corpus-staging.zip \
  --checksums /path/to/CHECKSUMS.sha256 \
  --repo-root . \
  --report research/legacy-staging/reconciliation-report.json
```

Review the dry-run report. If it is clean:

```bash
python ingest/reconcile_legacy_staging.py \
  --archive /path/to/brendon-corpus-staging.zip \
  --checksums /path/to/CHECKSUMS.sha256 \
  --repo-root . \
  --report research/legacy-staging/reconciliation-report.json \
  --apply
```

Then commit the resulting `sources/` and `context/` source-container directories plus the final reconciliation report.

Point 4 is complete only when a final dry-run reports all 51 records `ALREADY_RECONCILED` in the canonical repository.
