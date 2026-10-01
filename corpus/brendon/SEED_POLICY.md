# Brendon seed eligibility policy

The corpus library contains more material than Kit is allowed to learn from as Brendon's personality seed.

## Three different things

### 1. Source container — `BCS-######`

A document, file, conversation, playtest, revision history, or third-party work that may contain relevant evidence.

A source container is **searchable context**. Its presence in the catalog does not make its entire contents Brendon-authored or seed-eligible.

### 2. Attributable evidence — `BCE-######`

A bounded contribution whose authorship can be tied to Brendon with evidence: a comment, correction, revision delta, playtest judgment, explicit instruction, conversation window, or authored source whose provenance is sufficiently established.

This is the level from which seed material may eventually be curated.

### 3. Derived decision/policy record

An analyst's interpretation of one or more evidence records. These belong in the decision corpus. They are not raw evidence and should never overwrite the source record.

## Eligibility states

For source containers:

- `PENDING_EVIDENCE_EXTRACTION` — indexed, but no whole-source Brendon claim has been established.
- `CONTAINER_NOT_DIRECT_SEED` — known mixed/collaborative container; only attributable child evidence may seed.
- `CONTEXT_ONLY` — third-party or otherwise non-Brendon material retained solely to understand linked evidence.
- `EXCLUDED` — privacy, evaluation, copyright, or relevance boundary prevents ingestion.

For evidence records:

- `ELIGIBLE_FOR_REVIEW` — authorship is strong enough to review for semantic value.
- `APPROVED_SEED` — Brendon or an authorized curation process has approved this bounded evidence for personality-seed use.
- `REJECTED_SEED` — directly attributable but not representative/useful for the seed.
- `EVALUATION_ONLY` — held out from discovery/training.

Direct attribution alone does not equal `APPROVED_SEED`. Administrative notes, typo fixes, or context-specific instructions may be Brendon's without teaching useful DM judgment.

## Evidence-strength hierarchy

Strongest:
1. Brendon's explicit correction plus stated reason.
2. Brendon's comment anchored to the exact material being criticized/changed.
3. Verified before/after revision with Brendon revision attribution.
4. Brendon's explicit postmortem or playtest judgment.
5. Brendon-authored source with independently established provenance.

Weaker:
6. Ownership plus revision metadata.
7. File possession or upload history.
8. Analyst inference from style or campaign familiarity.

Items 6–8 cannot establish whole-source authorship by themselves.

## Mixed authorship

For a collaborative source, preserve the entire source as context but create child evidence only for contributions with attributable authorship.

Do not train on the collaborative prose as if it were Brendon's.

If an edit cannot be attributed at passage level, leave it unclaimed until revision comparison or other evidence resolves it.

## Third-party works edited by Brendon

The third-party work is `CONTEXT_ONLY`.

Brendon's comments, edits, or revision deltas are separate `BCE` records.

Example:
- `BCS-000059`: Michael Kennish's *Exploration Impossible* manuscript — context only.
- `BCE-000001`: 78 Brendon-authored editorial comments — attributable evidence.

## Seed provenance requirement

Anything ultimately loaded into Kit as a Brendon seed must be traceable:

`Kit seed item -> derived decision/trait if any -> BCE evidence -> BCS source container -> native or portable source locator`

If that chain breaks, the item is not seed-ready.
