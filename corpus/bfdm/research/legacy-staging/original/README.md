# Brendon Corpus — private staging body

This is the **actual corpus body**, prepared for migration into a private Git repository. It is not a summary dataset.

## Layout

- `sources/roanoke/` — 37 Roanoke source containers, normalized and accompanied by originals.
- `sources/earthfall/` — current Earthfall campaign/source documents in the catalog.
- `sources/bastion-redoubt/` — Bastion/Redoubt source documents.
- `sources/at-wars-end/` — the current At War's End draft/outline family.
- `context/exploration-impossible/` — Michael Kennish's manuscript, retained only as context for Brendon editorial evidence. It is not Brendon-authored corpus prose.

Every `BCS-######` directory contains `source.md`, an original file under `original/`, `metadata.json`, `comments.json`, and extracted `assets/` when present. Some Roanoke sources also contain `brendon-comments.native.json` where native Drive comments were needed to supplement export gaps.

## What inclusion means

A full source container is preserved so another agent can inspect the same context. Inclusion does not automatically mean Brendon authored every line. Attribution and Kit seed eligibility remain separate evidence/provenance questions.

The public `radarsaint/dnd-solo/corpus/brendon/` directory contains the current IDs, evidence registry, curation policy, and retrieval contract. This private staging body supplies the missing readable material behind those IDs.

## Normalization

Google Docs and Library DOCX files are retained as originals and normalized to GitHub-flavored Markdown with no hard wrapping. Embedded DOCX media is extracted beside the Markdown. The Roanoke schedule XLSX was read with `artifact_tool`, represented as Markdown, and retained as the original spreadsheet.

No spelling, grammar, terminology, or source claims were silently corrected.

## Verification

- `manifest.all.jsonl` — machine-readable inventory of the staged body.
- `INDEX.md` — human-readable source index.
- `CHECKSUMS.sha256` — checksums for every staged file.
- `STATUS.json` — current completeness and known gaps.

## Migration

Target: a private repository such as `radarsaint/brendon-corpus`. Do not put this body into the public `dnd-solo` repository.