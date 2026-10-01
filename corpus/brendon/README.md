# Brendon Corpus Library

This directory is the canonical cross-agent **index** for the historical material used to seed Kit.

The decision corpus answers: **what judgment did Brendon demonstrate?**

This library answers: **what is the underlying source, where is the full context, what versions are related, and how can another agent retrieve it?**

## Current state

The bootstrap catalog contains 66 historical source records across 5 named project families. It incorporates the 53 imported Roanoke/Empire City source files already present in ChatGPT Library and adds native Drive locators for major Earthfall, Bastion/Redoubt, and At War's End sources discovered during this pass.

The catalog is intentionally broader than the current decision extraction. A source can belong in the library before anybody has decided what it teaches Kit.

## Canonical identifiers

Every source receives a stable `BCS-######` corpus ID.

Existing extraction IDs such as `IMP-021` remain in `legacy_source_id` so old decision records do not lose provenance.

Agents should cite the `BCS` ID in new cross-agent work and preserve the legacy ID when referring to existing extraction artifacts.

## Full-context rule

Do not train or reason from an isolated quote when the surrounding source can be retrieved.

For a small source, read the whole source.

For a large source, retrieve the relevant section plus neighboring sections and the source's version-group context. If a judgment came from a comment, revision, playtest correction, or before/after change, preserve that interaction as a child evidence object rather than flattening it into the parent manuscript.

A derived decision record is never a substitute for the raw source.

## Storage tiers

1. **Original/native source** — Google Drive or the user's ChatGPT Library. Highest-fidelity location.
2. **Portable snapshot** — future normalized text/JSON snapshot for agents that cannot authenticate to the original source.
3. **Derived evidence** — decision records, traits, preferences, evaluations. These cite source IDs; they are not source replacements.

The public `dnd-solo` repository currently hosts the catalog, not the full private source archive. Raw source text should not be copied into this public repository merely to make retrieval convenient.

## Deliberate exclusions

Personal-response spreadsheets and other sources containing unrelated people's personal information are not corpus training material. The catalog preserves their existence/exclusion when relevant to provenance, but agents should not ingest them as Brendon evidence.

Empire City remains evaluation-quarantined where the decision-corpus split says so. A source's presence in this library does not authorize using it in discovery/training.

## Files

- `catalog.jsonl` — authoritative source registry.
- `CATALOG.md` — human-readable registry.
- `SCHEMA.md` — meaning of fields and evidence boundaries.
- `RETRIEVAL.md` — agent retrieval rules and bundle format.
- `ACCESS_GAP.md` — what is and is not yet truly portable across GPT/Grok surfaces.

## Relationship to the decision corpus

The decision corpus should migrate from bare `IMP-###` references to `BCS-######` + passage/child-evidence locators. This library should remain source-centric even if later models disagree about what the source means.
