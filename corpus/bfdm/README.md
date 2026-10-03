# BFDM Corpus

> **Governing invariant:** `bfdm-corpus` is not primarily a training dataset. It is the durable research archive of Brendon's D&D creative history. **Kit is one consumer of it.**

Private archive and research environment for Brendon's D&D creative body of work and the live-play context around it.

This repository must remain useful even if Kit's architecture changes completely or Kit is replaced. Training, retrieval, prompting, evaluation, and voice distillation are downstream uses of the archive—not the archive's organizing purpose.

This repository is broader than a Discord archive or a Kit training set. It is intended to preserve and make researchable:

- campaign planning and operations;
- Discord activity and attachments;
- Google Drive/project documents;
- revisions and comments;
- homebrew races, classes, subclasses, items, and systems;
- worldbuilding and lore;
- writing and abandoned experiments;
- playtests, corrections, and postmortems;
- derived research that remains traceable to source evidence.

See [CORPUS_CHARTER.md](CORPUS_CHARTER.md) for the project boundary and research layers, [REPO_HYGIENE.md](REPO_HYGIENE.md) for branch/artifact/duplication rules, and [INGESTION_CONTRACT.md](INGESTION_CONTRACT.md) for the binding Drive/Project ingestion contract.

## Current storage

- `campaigns/` holds campaign-level registry/metadata and cross-links; canonical document bodies live under `sources/` or `context/`.
- `discord/` holds searchable SQLite harvests, one database per server. See [discord/SCHEMA.md](discord/SCHEMA.md).
- `sources/` holds canonical human-readable non-Discord BCS source containers.
- `context/` holds context-only BCS source containers.
- `indexes/` holds rebuildable searchable indexes such as `documents.sqlite`.
- `registry/` holds machine-readable project/campaign, Discord-server, person, and identity mappings.
- `evidence/` holds the private BCS/BCE/BCR source/evidence registry and portable evidence snapshots.
- `research/` holds derived analysis, methodology, evaluation records, and source leads. Research is not source truth.

`.sqlite` databases and Discord attachment files are stored with Git LFS.

## Provenance

Maintain compatibility with the existing corpus IDs:
- `BCS-######` — source container;
- `BCE-######` — attributable Brendon evidence;
- `BCR-######` — supported relation.

A source may belong in this archive without being Brendon-authored or eligible to shape Kit.

## Canonical-repo rule

This is the canonical private corpus repository.

Do not create a parallel private Brendon-corpus repository. Reconcile older staging material here while preserving stable IDs and provenance.
