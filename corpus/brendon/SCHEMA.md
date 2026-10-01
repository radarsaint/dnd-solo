# Corpus catalog schema

Each line of `catalog.jsonl` is one source object.

Required conceptual fields:

- **corpus_id** — stable cross-agent source identity.
- **legacy_source_id** — previous extraction ID when one exists.
- **title / project** — source identity and family.
- **source_role** — raw historical source, not a derived judgment.
- **source_kind** — current native/storage form.
- **authorship / authorship_basis** — attribution status. Ownership/uploader identity is never sufficient by itself.
- **approximate_source_date** — historical date when supported; null otherwise.
- **partition / split_group** — discovery/evaluation/exclusion boundary and grouping of related versions.
- **reliability / review_status** — evidence maturity.
- **context_policy** — how much surrounding material to retrieve.
- **locators.chatgpt_library** — Library IDs/path when available.
- **locators.google_drive** — native Drive ID/URL when available.
- **portable_snapshot** — future cross-agent snapshot location. Null means the source is not yet portable to an agent lacking authenticated access.
- **notes** — exposure or provenance caveats.

## Child evidence

Comments, revision deltas, playtest corrections, and conversation windows should be indexed as child records in a later `evidence.jsonl` with:

- `evidence_id`
- `parent_corpus_id`
- `evidence_type`
- `author`
- `timestamp`
- `native_locator`
- `context_start/context_end` or equivalent section anchors
- `full_context_policy`
- `partition`
- `portable_snapshot`

Do not bake an analyst interpretation into the child source record. Interpretations belong in the decision corpus.
