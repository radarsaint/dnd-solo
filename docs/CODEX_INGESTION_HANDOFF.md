# Codex ingestion handoff to Nagatha — 21 November 2026

Author/executor: **Codex**, running on Brendon's Windows machine. Base: main
`123653fd8596d8f57060fdf212c72bbaae683cc2`, v0.16.0.

Brendon authorized code changes, a separate pushed branch, a handoff in Nagatha's
Google Drive devlog, and upstream research. No merge is authorized by this handoff.

## Product direction

Improve Kit's ingestion for both play and design: fidelity, speed, varied material,
and useful application across books. Choose established tools on actual results.
The existing source library is
primarily structured HTML captures with retained assets and an existing sectioned
SQLite reference store. Do not convert that structure away merely to fit a tool.

## This code repair

`kit_prep._copy` hard-linked mutable JSON as well as PDFs. A synthetic check with
real hard links showed that changing a save altered the cached JSON, and restoring
into a second save rewrote the first save's database paths. The sandbox's link
restriction initially hid the bug by selecting the copy fallback.

Mutable files now copy independently. Only retained PDFs under `pdf_sources` retain
the link optimization. Preparation revision 2 bypasses potentially contaminated old
cache entries. Explicit reader requests use separate cache keys, and re-caching an
accepted skim keeps its reader selection. No old saves or cache directories are
deleted or retroactively repaired. The next preparation under this revision is cold.

Five synthetic regressions pass with real filesystem hard links. The existing eight
setup/preparation tests pass on Windows Python 3.13.3. A complete local suite is being
run separately; its final receipt and the exact pushed SHA belong in the devlog/PR.
Python 3.8/Linux and complete ZIP checks must be distinguished from Windows results.

## Findings still open

- A long location can retain a consequential final restriction in source but omit it
  from the bounded compiled room. A synthetic probe reported 113 omitted DM sentences.
  No real-book wrong ruling was inferred from this probe.
- `index_complete` certifies the indexing operation, not complete understanding.
- Opening and full-book extraction repeat work. Synchronous reader calls are not
  interrupted by the surrounding time-budget checks. Real-book speed needs measurement.
- Reader/request cache separation is repaired here; automatic fallback provenance
  and complete per-stage pipeline versioning still merit investigation.

## Existing library to reuse

An existing source library already retains HTML, source hashes, heading hierarchy,
tables, versions, edition filters and FTS5/BM25 search. Evaluate that foundation before
building another catalog. Keep images connected to their original source assets.
Local filesystem paths and inventory metadata are intentionally absent from this
repository handoff.

## Next investigation

Compare proven document models, parent/child retrieval, dependency expansion,
incremental ingestion and hybrid search against the existing library. Evaluate an
unfamiliar encounter, adventure adaptation and cross-book design. Preserve the play
compiler and game-state boundary while building reusable source access. Don't equate
search results with understanding or replace missing context with invented mechanics.

No private book text is included here. No host playtest, broader design acceptance,
full-book speed improvement, or production deployment is claimed.
