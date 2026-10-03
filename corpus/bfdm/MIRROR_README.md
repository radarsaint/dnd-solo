# BFDM Public Mirror

This directory mirrors the readable Git-tracked layer of the private `radarsaint/bfdm-corpus` repository so external reviewers and AI systems can inspect the evidence behind KRABS.

Private canonical research repository:
https://github.com/radarsaint/bfdm-corpus

Public mirror:
https://github.com/radarsaint/dnd-solo/tree/main/corpus/bfdm

## Scope

The mirror preserves the source repository paths for all normal readable text/code/data files on `main`, including:

- corpus charter and ingestion rules;
- evidence catalogs and relations;
- chronology, corrections, uncertainties, and project decisions;
- BFDM research method and current synthesis;
- Roanoke and Empire City decision cases and longitudinal analyses;
- Kit design/evaluation records;
- prior decision-extraction datasets and audits;
- source indexes and coverage records.

## Raw Git LFS material

The private repository also contains Git-LFS-backed SQLite archives and media/attachment paths. The GitHub connector used for this publication can read their pointer files but cannot dereference the binary LFS payloads into another repository. `LFS_OBJECT_MANIFEST.jsonl` records every Git-tracked object that was not copied into this readable mirror.

The important raw databases include:
- `discord/roanoke-season-3/roanoke-season-3.sqlite` — LFS payload size 64,847,872 bytes in the source pointer.
- `discord/empire-city/empire-city.sqlite` — LFS payload size 66,834,432 bytes in the source pointer.

## Suggested entry points for KRABS review

1. `CORPUS_CHARTER.md`
2. `research/PROJECT_DECISIONS.md`
3. `research/current-synthesis/working-model-2026-10-01.md`
4. `research/METHOD.md`
5. `research/KNOWN_UNCERTAINTIES.md`
6. `research/roanoke-s3/longitudinal-decision-cases-v2.md`
7. `research/empire-city/longitudinal-decision-cases-v1.md`
8. `research/kit-evaluation/`
9. `evidence/`

The private BFDM repository remains canonical. This directory is the externally readable mirror.
