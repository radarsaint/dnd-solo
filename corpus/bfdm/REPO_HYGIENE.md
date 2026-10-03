# Repository Hygiene

This repository is a private archival/research corpus. Hygiene should optimize for traceability, low duplication, and a small amount of durable structure—not for preserving every temporary analysis mechanism.

## Main branch

`main` is the canonical archival state.

Keep temporary experiments, one-off workflows, scratch scripts, and transient analysis outputs off `main`.

Merge durable work only when:
- source/provenance boundaries are clear;
- the final file layout is stable enough to keep;
- temporary artifacts are no longer required;
- superseded drafts are identified.

## Branches and pull requests

Use branch families consistently:

- `ingest/...` — source ingestion / normalization
- `research/...` — research organization or synthesis
- `derived/...` — bounded derived datasets / analyses
- `analysis/...` — temporary computational work; delete after the durable result is preserved

Rules:
- one logical body of work per active PR;
- close superseded PRs instead of leaving multiple active versions;
- preserve provenance through the PR/commit record, not by keeping every obsolete branch forever;
- after a superseding PR is merged and verified, old `analysis/` and `derived/` branch refs should be deleted;
- API-generated one-file-at-a-time commit noise should be squashed before merge.

## Commit hygiene

Prefer a small number of coherent commits.

Connector/API work often creates one commit per file. Before merge, squash mechanical commit noise into a logical commit or small logical series.

Do not preserve dozens of commits whose only meaning is “create the next file.”

## Raw source duplication

There should be one canonical source representation per storage role.

For Discord:
- canonical database: `discord/<server-slug>/<server-slug>.sqlite`
- canonical attachments: `discord/<server-slug>/attachments/`
- README records harvest scope and provenance

Do not keep additional raw database copies in research folders, release assets, or long-lived Actions artifacts.

For Drive/project material:
- preserve native locator/provenance;
- keep normalized/searchable and human-readable representations where useful;
- do not create parallel source-container IDs for the same source.

## Large files

SQLite databases and harvested Discord attachments belong in Git LFS according to `.gitattributes`.

Avoid committing:
- database journals/WAL/SHM files;
- temporary archives produced only for analysis;
- duplicate database snapshots;
- generated scratch output.

A temporary Actions artifact should have the shortest practical retention and disappear after the durable result is preserved.

## Archive versus model exports

The repository is not organized around a current model's ingestion format.

Training, retrieval, prompting, voice, evaluation, or embedding artifacts are derivative outputs.

Rules:
- never delete or simplify canonical source material because a model-facing export does not need it;
- never treat a generated model dataset as the only surviving representation of a source/evidence lineage;
- keep model-specific packaging out of canonical source directories;
- prefer regeneration of model-facing artifacts from the archive over preserving stale generated copies;
- a change in Kit architecture should require rebuilding exports, not restructuring or rewriting historical source data.

If a model export and the archive disagree, the archive/evidence provenance chain is authoritative.

## Source versus research

Keep these boundaries visible:

- source/archive material answers what exists;
- attributable evidence answers what can be tied to Brendon;
- research answers what the evidence may mean;
- runtime curation answers what Kit actually uses.

Do not place analyst summaries inside normalized source bodies.

Do not place raw/private source dumps in `research/` merely for convenience.

## Stable IDs

Preserve existing:
- BCS source-container IDs;
- BCE attributable-evidence IDs;
- BCR relation IDs;
- native Drive/Discord IDs.

Before adding a source, check:
1. legacy staging manifest;
2. current `bfdm-corpus`;
3. prior public `dnd-solo` corpus index where relevant.

Never solve duplication by minting a new ID for an already-known source.

## Generated indexes and state files

Files such as:
- `research/ARTIFACT_REGISTER.md`
- `research/RESEARCH_STATE.json`

are navigation/state snapshots.

Refresh them at deliberate checkpoints, not after every tiny edit.

They should never become a second source of truth for historical facts.

## Historical research snapshots

Copies under `research/prior-dnd-solo/` are intentionally preserved research snapshots.

They should:
- retain their originating PR/branch metadata;
- remain clearly labeled historical/provisional;
- not be edited into current conclusions;
- not be duplicated again elsewhere.

## Temporary analysis cleanup

Current known temporary lineage:
- branch `analysis/s3-distill`
- closed PR #1
- temporary Actions artifacts from the S3 extraction

The durable research output is preserved elsewhere. After temporary artifacts expire and PR #5 is safely integrated, the `analysis/s3-distill` branch should be deleted.

Closed S3 `derived/` branches #2–#4 may likewise be deleted after PR #5 is merged and verified; their PR records preserve provenance.

## Root-directory discipline

Keep the root small.

Durable root-level files should be things such as:
- README
- corpus charter
- repository hygiene/maintenance guidance
- Git/LFS configuration

Campaign/source bodies belong under their source-family directories; derived work belongs under `research/`.

## No silent cleanup of evidence

“Hygiene” must never mean deleting historical evidence merely because it is messy.

Delete:
- duplicates;
- temporary packaging;
- obsolete branch refs;
- scratch outputs;
- redundant artifacts.

Preserve:
- source history;
- revisions;
- comments;
- provenance;
- contradictions;
- superseded research when it has interpretive value.

The goal is a clean repository without a cleaned-up history.
