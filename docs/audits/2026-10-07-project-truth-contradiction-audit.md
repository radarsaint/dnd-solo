# Project truth / contradiction audit — 2026-10-07

**Basis**
- `radarsaint/dnd-solo main @ e3a5e9908357441051df24dac8086d8d4c7f26f5`
- `radarsaint/bfdm-corpus main @ 65513f294e72a3eb961d5699c21ddc1f14ceef2c`
- open PRs treated as proposed, not canonical
- Project attachments treated as pinned/historical unless they match live repo truth

## Central finding

The largest remaining mental-model failure is **authority-surface drift**.

The project now largely knows what current Kit is. The danger is that older artifacts still look authoritative enough to overwrite newer truth in a fresh agent's mental model.

## Current-truth corrections

1. `dnd-solo` is no longer architecturally an Area 6c runtime. Area 6c is a legacy/default regression fixture with no design primacy.
2. Generalized room loading is built; automatic source-to-room authoring from untouched adventure text is not on current main. PR #100 is a proposed path.
3. BFDM Stage 3 minimal cognition is not current work. Stage 1 is substantially landed; Stage 2 remains incomplete; Stage 4 architecture is later.
4. Canonical BFDM source integration reaches BCS-000172. Earthfall/Saturday workbench recoveries are partial.
5. SOURCE_RESEARCH_READY and LONGITUDINAL_RESEARCH_READY are intentionally narrow readiness labels, not broad completeness claims.
6. PR #38 has produced a concrete integrity regression: BDC-S3-004's cited prep locators do not reconstruct to the claimed support in preserved representations. The live Discord event remains recoverable.
7. PR #38 itself is only first-tranche staging/audit infrastructure; it does not certify BFDM broadly.
8. Pinned Project ZIPs are reproducible historical baselines, not current development truth.
9. Some `dnd-solo/main` overview prose remains stale enough to mislead agents unless routed through the control layer.

## Dangerous authority surfaces

- Project KRABS v0.1, which called itself canonical, is superseded by live repo KRABS v0.2.2.
- `dnd-solo/corpus/bfdm` and `corpus/brendon` are obsolete mirror/bootstrap surfaces.
- `docs/collab/BOARD.md` is useful provenance but not a live Kanban board.
- stale open PRs can look like current plans simply because they remain open.
- duplicate cleanup PRs create false competing futures if an agent extends the wrong one.

## Duplicate/stale PR traps

Particularly stale or superseded-looking runtime PRs:
- #5, #11, #23, #36, #43, #44, #67.

Duplicate cleanup families:
- #105 / #110 — current-state docs;
- #106 / #108 — retire in-repo corpus mirror;
- #107 / #109 — split live board from archive.

These should be reconciled rather than independently extended.

BFDM older paths:
- #24 / #26 — older Drive integration paths superseded in substance by merged #25.

## Settled decisions not to reopen casually

- `dnd-solo main` is current runtime truth.
- `bfdm-corpus main` is canonical corpus/research truth.
- Area 6c is not the architecture.
- room loading is built; general source-to-room authoring is not.
- pinned ZIPs are baselines.
- open PR != canonical main.
- preparation != live play.
- later artifact != automatic supersession without evidence.
- Stage 2 precedes Stage 3; Stage 4 waits for observed failures.
- unreviewed/changed derived propositions fail closed.
- merges require Brendon's approval.

## Friday traps for a powerful fresh agent

1. Treating Project KRABS v0.1 as current because it says canonical.
2. Reporting a pinned ZIP's behavior as current main.
3. Reconstructing Kit as an Area 6c architecture from reference density.
4. Treating generalized room loading as solved source-to-room authoring.
5. Reading the in-repo BFDM mirror as canonical research truth.
6. Selecting an old open PR because it still exists.
7. Using the append-only board as current project state.
8. Trusting polished/cited BFDM derived cases without semantic reconstruction.
9. Starting Stage 3/4 cognition because those stages are well described.
10. Resolving contradictions by choosing newest-looking prose instead of checking artifact type and authority.

## Delta

The control plane itself is a project failure surface.

The project needs current, version-aware orientation that makes stale authority difficult to mistake for live truth. This is why `PROJECT_CONTROL.md`, `COORDINATION.md`, machine-readable control state, historical-board demotion, and PR maintenance checks are necessary rather than cosmetic documentation work.
