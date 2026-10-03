# BFDM Corpus Charter

## Purpose

bfdm-corpus is the canonical private archive and research environment for Brendon's D&D creative body of work and the live-play context around it.

It is broader than:
- a Discord archive
- a campaign-planning folder
- a prose corpus
- a Kit personality prompt
- a training dataset

Those may be uses of parts of the corpus. None is the whole project.

## Archive-first invariant

> **`bfdm-corpus` is not primarily a training dataset. It is the durable research archive of Brendon's D&D creative history. Kit is one consumer of it.**

This is a governing constraint, not a temporary implementation preference.

Consequences:

- **Archive value is independent of Kit.** If Kit were retired, rebuilt, or replaced tomorrow, the corpus would still justify its existence as a research archive.
- **Current model limitations do not define archive structure.** Context windows, prompt budgets, RAG formats, embedding strategies, fine-tuning schemas, or a particular model vendor must not decide what historical material survives.
- **Seed eligibility is not an archival filter.** Material can be important to preserve even when it should never shape Kit directly.
- **Training-ready exports are derivative products.** Any prompt pack, fine-tuning set, preference set, retrieval index, voice file, or evaluation bundle should be reproducible from the corpus/evidence/research layers and must not become the canonical historical record.
- **Normalization must remain reversible in principle.** Searchable and human-readable forms may be added, but source lineage, originals, native IDs, revisions, comments, and attribution context must not be discarded merely to make data easier for a model to consume.
- **Research questions may outlive today's product goals.** Preserve dead ends, failed experiments, third-party context, contradictions, and material whose future value is not yet understood.
- **Kit-specific curation happens downstream.** Kit may consume selected evidence, research, summaries, retrieval indexes, or other exports. Her needs do not rewrite the archive.

When archive integrity and short-term Kit convenience conflict, preserve the archive and build a derived Kit-facing representation.

## What belongs in the archive

Potential source families include:
- Discord servers and attachments
- Google Drive planning documents
- revision history
- native comments/replies
- project files
- adventure/session material
- homebrew races, classes, subclasses, and items
- worldbuilding and lore
- campaign operations and schedules
- playtests and postmortems
- writing
- abandoned experiments
- context sources needed to interpret attributable Brendon evidence

A source can belong in the archive without being Brendon-authored or Kit-seed-eligible.

## Four layers

### 1. Source archive
High-fidelity material plus normalized/searchable representations.

Question: What source material exists?

### 2. Attributable evidence
Bounded contributions attributable strongly enough to review.

Question: What can reasonably be attributed to Brendon, and in what context?

### 3. Derived research
Decision cases, longitudinal studies, hypotheses, contradictions, developmental models, and evaluation assets.

Question: What might the evidence mean?

### 4. Runtime curation
Deliberately selected material translated into Kit's live behavior, retrieval, evaluation, or other product mechanisms.

Question: What should Kit actually use, and for what purpose?

Movement between layers is not automatic.

## Stable provenance

Maintain compatibility with the existing ontology:
- BCS-###### — source container
- BCE-###### — attributable evidence
- BCR-###### — supported relation

Derived research should cite evidence/source IDs rather than inventing a parallel provenance system.

## Preserve source history

Where available preserve:
- native IDs
- timestamps
- authorship metadata
- server/channel/thread hierarchy
- revisions
- comments
- attachments
- document-family/version relationships
- checksums

Human-readable exports and SQLite/search indexes are representations of the source lineage, not replacements for it.

## Development over time

Research must be able to distinguish:
- early practice
- later practice
- direct self-critique
- format-specific solutions
- recurring preferences
- abandoned techniques
- emergent practices later formalized

Do not average these into one timeless persona.

## Privacy and attribution

The archive contains other people's messages and collaborative work.

Private storage does not remove the need for:
- correct authorship
- bounded use
- avoiding unnecessary duplication
- keeping third-party/context material distinct from Brendon evidence

## Open-ended value

The corpus may eventually support:
- solo DM judgment
- future campaign / Season 6 design
- retrieval of old ideas and experiments
- developmental analysis
- evaluation sets
- preference/judgment seeding
- voice/style distillation
- campaign-format reconstruction
- future methods not yet chosen

Preserve enough richness that later uses do not depend on today's assumptions.

## Current sequencing

1. Broaden source coverage.
2. Preserve provenance and identity mappings.
3. Normalize/search without discarding source history.
4. Run research in bounded, reviewable passes.
5. Compare across campaigns and eras.
6. Produce human-readable synthesis when coverage supports it.
7. Curate selected findings into Kit only after the evidence chain and intended runtime role are clear.

## Success condition

The corpus succeeds if a future researcher or Kit can locate the source, see who produced it, reconstruct its context and chronology, distinguish source from interpretation, challenge a conclusion, and use the material for genuinely new work rather than merely imitate old prose.
