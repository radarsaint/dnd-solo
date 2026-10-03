# Work GPT Ingestion Contract

**Applies to:** Google Drive documents/files and ChatGPT Project/Library files ingested into `radarsaint/bfdm-corpus`.

**Owner of this workstream:** Work GPT.

**Primary objective:** grow the durable BFDM research archive without losing provenance, creating duplicate source identities, or shaping the archive around a current Kit implementation.

## 0. Governing rule

> **`bfdm-corpus` is not primarily a training dataset. It is the durable research archive of Brendon's D&D creative history. Kit is one consumer of it.**

Ingestion is archival work.

Do not optimize source selection, structure, or normalization for a prompt budget, fine-tuning format, embedding model, or current Kit runtime.

## 1. Start condition

Before writing anything, Work GPT MUST read the current versions of:

- `README.md`
- `CORPUS_CHARTER.md`
- `REPO_HYGIENE.md`
- `INGESTION_CONTRACT.md`
- `evidence/catalog.jsonl`
- `research/legacy-staging/manifest.all.jsonl`
- `research/legacy-staging/RECONCILIATION_2026-10-02.md`
- `research/IDENTITY_RESOLUTION.md`

Current repository state at contract creation:

- governance/research branch: `research/organize-current-work-v1`
- draft PR: #5

If PR #5 has merged, create the ingestion branch from current `main`.

If PR #5 has **not** merged, create the ingestion branch from `research/organize-current-work-v1`, not from stale `main`. Retarget/rebase after #5 is integrated.

Recommended branch:

`ingest/drive-project-v1`

Do not ingest directly on `main`.

### Legacy reconciliation prerequisite

Before assigning any new BCS ID or importing material that may overlap the 51-source legacy staging body, run:

```bash
python ingest/reconcile_legacy_staging.py \
  --archive /path/to/brendon-corpus-staging.zip \
  --checksums /path/to/CHECKSUMS.sha256 \
  --repo-root . \
  --report research/legacy-staging/reconciliation-report.json
```

Review the dry-run report.

If it is clean, rerun with `--apply` and commit the resulting source-container directories and final report before or as the first logical commit of the larger Drive/Project ingest.

Point 4 is not complete merely because the 51 BCS IDs appear in `evidence/catalog.jsonl`. The actual source bodies, originals, comments, metadata, and assets must exist in the canonical repository.

## 2. Scope

### Include

Preserve D&D/TTRPG creative-history material available through connected Drive and Project/Library sources, including:

- campaign planning and prep;
- session/voice-event material;
- NPC, faction, location, encounter, map, and schedule material;
- worldbuilding and lore;
- homebrew races, classes, subclasses, items, crafting, and subsystems;
- campaign operations and DM coordination;
- change logs and postmortems;
- writing connected to the creative body of work;
- abandoned or superseded experiments;
- source comments/replies;
- revision metadata and retrievable revision content;
- assets embedded in or attached to source documents;
- third-party/collaborative material when needed to interpret attributable Brendon work.

### Do not silently exclude because

- it is old;
- it is messy;
- it appears unsuccessful;
- it is not immediately useful to Kit;
- it is third-party context;
- it contradicts later work;
- it does not fit a current model input format.

### Exclude from source ingestion

- clearly unrelated personal/non-D&D material;
- generated research already stored in this Git repository;
- duplicate raw copies of the Discord SQLite harvests;
- temporary AI scratch files with no independent historical/source value.

If relevance is uncertain, record the candidate in the ingest report instead of inventing certainty or asking Brendon to manually triage every file.

## 3. Canonical identity: BCS source containers

Every logical source document/file gets one stable `BCS-######` identity.

### Never renumber an existing BCS

Existing IDs are permanent.

### Deduplication order

Before assigning a new BCS, check in this order:

1. exact native provider ID already present in `evidence/catalog.jsonl`;
2. exact native provider ID or known path in `research/legacy-staging/manifest.all.jsonl` / staged metadata;
3. exact raw/export SHA-256 already associated with a known source;
4. verified locator relationship showing a Project/Library copy and Drive document are the same logical source;
5. only then consider a new BCS.

### What is NOT enough to merge sources

Do not merge solely because of:

- matching titles;
- similar filenames;
- similar text;
- same campaign;
- same author;
- same checksum when the files may be intentionally duplicated as distinct historical artifacts.

Ambiguous duplicates are preserved separately or flagged `POSSIBLE_DUPLICATE` for review.

### Drive + Project copies

If a ChatGPT Project file is a connector-synced or exported representation of a known Drive document, use **one BCS** and retain multiple locators/representations.

Do not mint one BCS for the Drive doc and another for its Project copy.

### Separate draft documents

Distinct native documents such as *first draft*, *second draft*, *third draft* remain distinct BCS containers even when clearly related.

Their differences are research data.

Link them as a document/version family; do not collapse them into a single “latest” source.

## 4. New BCS allocation

At the beginning of an ingest run:

1. parse the current target branch's `evidence/catalog.jsonl`;
2. determine the highest existing BCS number;
3. allocate sequentially from the next unused number;
4. record every allocation in the ingest report.

Do not trust a hard-coded “next BCS” written in this contract.

Before marking the PR ready:

1. compare against the latest target branch;
2. detect BCS collisions caused by concurrent work;
3. if a collision exists, renumber only the **new, unmerged** records created by this ingest;
4. never renumber IDs already present in canonical history.

## 5. Canonical human-readable source layout

New document/file source containers use:

`sources/<project-slug>/BCS-######/`

Third-party context-only material may use:

`context/<project-slug>/BCS-######/`

Existing legacy containers keep their historical paths when migrated; do not rename them merely for cosmetic consistency.

Each new container SHOULD contain:

```text
BCS-######/
├── source.md
├── metadata.json
├── comments.jsonl
├── revisions.jsonl
├── original/
│   └── source.<ext>
├── revisions/
│   └── <provider-revision-id>.md
└── assets/
    └── ...
```

Only create files that have actual content. Empty `assets/` or `revisions/` directories are unnecessary.

### `source.md`

Human-readable current/source snapshot.

Rules:

- preserve source wording, spelling, terminology, and organization;
- do not “clean up” prose;
- do not merge multiple documents;
- preserve headings/tables where feasible;
- preserve line-oriented text suitable for later citation/search;
- note extraction limitations in metadata, not by silently repairing source text.

### `metadata.json`

Must include at minimum:

- `corpus_id`
- `project`
- `project_slug`
- `title`
- `source_role`
- `source_kind`
- `provider`
- native provider/file/document ID
- native URL when available
- original/current filename
- MIME type
- created timestamp when available
- modified timestamp when available
- ingest timestamp
- SHA-256 for every stored file representation
- locator(s) to Drive / Project / Library
- authorship status
- authorship basis
- normalization method
- extraction warnings
- related document-family ID if known
- current source/body path
- original/export representation kind

### `original/source.<ext>`

Preserve exact raw bytes when an actual uploaded/original file exists.

For Google-native documents, an exported DOCX/XLSX/PPTX/PDF is a **snapshot/export**, not the metaphysical native original. Record that explicitly in `metadata.json` with a representation type such as:

`GOOGLE_NATIVE_EXPORT_SNAPSHOT`

Do not claim an export is an original native Google file.

### `comments.jsonl`

Preserve comments and replies with native IDs and attribution.

Do not summarize them in place of the original text.

### `revisions.jsonl`

Preserve every revision metadata record returned by the provider, including:

- revision ID;
- modified time;
- last-modifying-user metadata;
- whether revision body was fetched;
- content hash/path if fetched;
- fetch/export failure if not.

### `revisions/<revision-id>.md`

If a historical revision body is retrievable as text, preserve it.

Do not overwrite earlier revision snapshots.

## 6. Revision policy

Revision history is research data.

### Mandatory

For each Google-native source when the API supports it:

- enumerate all available revision metadata;
- preserve the revision list;
- preserve modifier metadata exactly as reported;
- fetch current body;
- fetch comments/replies.

### Revision bodies

Fetch and preserve available historical revision bodies when technically retrievable and reasonably bounded.

If a document exposes a very large revision count or the connector cannot practically retrieve all bodies:

1. preserve **all available revision metadata**;
2. preserve the current body;
3. preserve any revision bodies already used by research;
4. record exactly which bodies were and were not fetched;
5. do not pretend the revision archive is exhaustive.

Never infer motive from edit timing during ingestion.

### Authorship warning

`lastModifyingUser = Brendon` means that revision was last modified by Brendon.

It does **not** prove Brendon authored every line in the document or even every changed line.

Store the metadata. Leave semantic attribution to evidence/research review.

## 7. Comment policy

Native Drive comments/replies are first-class source context.

For each comment/reply preserve when available:

- native comment/reply ID;
- document/BCS ID;
- author display name;
- stable author/account ID if exposed;
- `me`/self flag if exposed;
- created time;
- modified time;
- resolved/deleted status;
- quoted/anchored context;
- full comment text;
- parent comment ID for replies.

Do not treat document-export comments as exhaustive when native Drive comments are available.

Do not convert every Brendon-authored comment into BCE automatically. Store source attribution; research curation decides BCE boundaries.

## 8. Authorship and ownership

Default source-level authorship is `UNKNOWN` unless supported.

Never infer whole-document authorship from:

- Drive ownership;
- file location;
- inclusion in Brendon's project;
- last modifying user;
- campaign ownership;
- title/voice resemblance.

Use supported statuses such as:

- `BRENDON`
- `COLLABORATIVE`
- `OTHER_AUTHOR`
- `UNKNOWN`

Keep separate:

- project ownership/authority;
- source authorship;
- comment authorship;
- revision modifier;
- delegated implementation.

Third-party source material can remain in the archive as `CONTEXT_ONLY_THIRD_PARTY`.

## 9. Project/Library file policy

For ChatGPT Project/Library files:

- preserve stable Library file ID when available;
- preserve Project file ID/reference when available;
- preserve original filename and raw bytes when materializable;
- calculate SHA-256;
- record source surface and project;
- preserve cloud/Drive locator if the file is connector-synced.

If a Project item points to a live Drive source:

- treat Drive as the native locator;
- do not create a second BCS from stale indexed Project text;
- Project metadata becomes an additional locator/representation.

If the Project file is a unique upload with no Drive source:

- it may become its own BCS source;
- preserve exact uploaded bytes plus normalized human-readable representation where possible.

## 10. SQLite document index

Maintain one SQLite index for non-Discord document/file sources:

`indexes/documents.sqlite`

This database is a searchable representation of the source archive.

It is not the sole canonical copy of source content.

Schema is defined in:

`ingest/document_archive_schema.sql`

### Required behavior

- one row per BCS in `source_containers`;
- multiple provider locators may point to one BCS;
- current normalized body is searchable;
- revision metadata is queryable;
- retrieved revision bodies are queryable/searchable;
- comments/replies are queryable/searchable;
- assets/raw files are indexed by path/hash, not duplicated inside SQLite;
- database uses UTC ISO-8601 timestamps where possible;
- `VACUUM` before commit;
- SQLite integrity check must pass;
- FTS index must rebuild successfully.

The SQLite file is stored through Git LFS under existing `*.sqlite` rules.

## 11. Evidence registry updates

Ingestion MAY update:

- `evidence/catalog.jsonl` for BCS source-container records.

Ingestion MUST NOT automatically mint:

- new BCE records;
- personality conclusions;
- DM-decision cases;
- training examples;
- generalized research claims.

Comments, revisions, and direct authorship metadata are preserved as source material first.

Evidence/research curation happens separately.

## 11A. Project and identity registry updates

During ingestion, Work GPT must update the machine-readable registries conservatively when new source evidence establishes:

- a previously unregistered project/campaign;
- a planning/date anchor;
- an exact live window;
- a source anchor;
- a project-family relationship;
- a Drive identity/revision-modifier assertion.

Registry files:
- `registry/projects.jsonl`
- `registry/project_relations.jsonl`
- `registry/people.jsonl`
- `registry/identities.jsonl`
- `registry/discord_servers.jsonl`

Rules:
- do not turn document-created timestamps into live campaign dates;
- do not assign Brendon's general 30–100 Roanoke retrospective range as a season-specific exact count;
- do not infer a person from a matching screen name alone;
- do not replace UNKNOWN/null with a guess;
- preserve support refs and uncertainty text;
- run `python registry/validate_registry.py` before merge.

## 12. Document-family relationships

Ingestion should preserve obvious technical families without collapsing them.

Examples:

- first draft → second draft → third draft;
- W1/W2/W3 planning family;
- public export derived from a native Drive document;
- Project upload copied from Drive source.

Store family/link metadata in source metadata and SQLite.

Do not create interpretive claims such as “this draft was abandoned because…” during ingestion.

## 13. No silent content transformation

Do not:

- rewrite grammar;
- modernize terminology;
- normalize character names;
- merge duplicate-looking passages;
- remove offensive/embarrassing old material;
- reconcile contradictory dates;
- “fix” rules;
- infer missing text;
- replace source prose with summaries.

If extraction is lossy, preserve the warning.

## 14. Ingest run report

Every ingestion PR must contain:

`ingest/reports/<YYYY-MM-DD>-<scope>.md`

and a machine-readable companion:

`ingest/reports/<YYYY-MM-DD>-<scope>.json`

Report at minimum:

- branch/base SHA;
- ingest start/end;
- source surfaces searched;
- candidate count;
- ingested new BCS count;
- reconciled/reused BCS count;
- possible duplicates;
- excluded clearly unrelated files count;
- failed/unavailable sources;
- files with comments;
- files with revision history;
- revision metadata rows captured;
- revision bodies captured;
- assets captured;
- SQLite row counts;
- checksum/integrity results;
- highest BCS allocated;
- known gaps;
- explicit statement that no BCE/personality/training judgments were minted.

## 15. Acceptance checks

Before requesting merge, Work GPT MUST run:

```bash
python ingest/validate_ingest.py
```

The validator is a minimum gate, not a substitute for the manual/source-specific checks below.

Before requesting merge, Work GPT MUST verify:

### Identity

- no duplicate BCS IDs;
- no new BCS duplicates an existing native Drive ID;
- no Project/Drive duplicate was split into two BCS records;
- legacy BCS IDs were reused where matched.

### Source preservation

- every ingested source has metadata;
- every stored representation has SHA-256;
- current human-readable body exists when extraction is possible;
- raw/uploaded bytes or Google export snapshot is preserved when available;
- comments/revisions have explicit completeness status.

### SQLite

Run:

```sql
PRAGMA integrity_check;
```

Expected:

`ok`

Also verify:

- BCS row count equals the intended indexed source-container count;
- locator foreign keys resolve;
- no orphan comments/revisions/assets;
- FTS query returns known test documents.

### Attribution

Spot-check at least:

- one collaborative file;
- one Brendon-authored comment;
- one non-Brendon/context source;
- one document with Brendon as revision modifier.

Confirm none of those metadata classes were collapsed into whole-document Brendon authorship.

### Repo hygiene

- no WAL/SHM/journal files committed;
- no duplicate raw SQLite copy;
- no temporary archives;
- no generated research conclusions in source containers;
- branch commit history squashed to a small logical series before merge.

## 16. Stop conditions

Work GPT should stop and report instead of guessing if:

- a candidate appears to require reusing an existing BCS but identity is ambiguous;
- source bytes/content cannot be retrieved and no trustworthy representation exists;
- a provider ID collision occurs;
- schema migration would destroy existing indexed history;
- it cannot distinguish a Project copy from a Drive native source;
- ingestion would require deleting source history;
- a source appears unrelated and personally sensitive rather than part of the D&D creative archive.

Do **not** stop merely because authorship is unknown. Preserve source context and mark authorship unknown.

## 17. Definition of done for this workstream

This ingestion pass is done when:

1. the selected Drive/Project corpus has been enumerated;
2. legacy BCS-000017 through BCS-000067 source bodies are reconciled into the canonical repository rather than merely indexed or duplicated;
3. each ingested source has stable BCS identity and provenance;
4. human-readable source containers exist;
5. comments and revision history have explicit capture status;
6. the document SQLite index is complete for the ingested scope;
7. integrity/dedup checks pass;
8. an ingest report states exactly what remains uncovered;
9. no research/personality/training conclusions were silently mixed into ingestion.

The goal is **not** “get the documents into a database.”

The goal is:

> make the creative history durable, searchable, attributable, reconstructable, and safe for later research.
