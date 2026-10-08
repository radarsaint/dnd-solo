# Unbriefed bootstrap evaluation — 2026-10-08

This is the evidence record for dnd-solo issue #118 item G4. It is not a claim that G4 is closed.

## What the subject was told

A fresh worker was given only this instruction: start at `PROJECT_BOOTSTRAP.md` on `radarsaint/dnd-solo` branch `docs/coordination-refresh-2026-10-07`, follow that reading path, verify live default-branch SHAs, and answer six questions. The prompt did not state catalog counts, container exceptions, research order, or the name of the failure mode. It did ask, in general, for corpus limits, what work should happen next, and what failure mode the project warns about when a component is built but not used. That last question names the situation. It does not name the finding.

The subject was not told to treat open pull requests as canonical main.

## What it opened

It read the branch at `3c438ba6c65b08ebd9295e2caa410809a0d4eb38`, which is the parent of checkpoint commit `3fa91c5ac8024cf95389211bcdd279cdbee7c85e`. Its statement that the checkpoint still reviewed `65513f294e72a3eb961d5699c21ddc1f14ceef2c` with a null inbox cursor was true of that SHA. It is not true of `3fa91c5` or of stacked head `be0d32819986d48dc28f2441baa0fe4f50c84ff9`.

## What it reconstructed without being given the numbers

- Live `dnd-solo` main `e3a5e9908357441051df24dac8086d8d4c7f26f5`.
- Live `bfdm-corpus` main `dc0d558188c3e492f69c34a8e278e0cf9e17373b`, which is the merge of PR #40.
- Catalog counted from `evidence/catalog.jsonl` on that main: 195 contiguous BCS ids, BCS-000001 through BCS-000195.
- Exceptions it checked on disk: BCS-000059 context-only, BCS-000068 excerpt, and the completion report's 193 indexed source containers. It did not query the LFS sqlite. It treated 193 as the report's count, consistent with the two exclusions, not as its own SQL count.
- It refused `research/STATUS.md` on main, which still says the corpus stops at BCS-000172.
- It named premature completion / missing downstream consumer, with PR #40's recorded-but-unreconciled delta as the example, and it separated that from proxy-evidence rules.
- It ranked the Gardener consumption loop ahead of more ingestion, then PR #38 semantic verification, with PR #27 as separate conflicting Discord engineering and PR #28 after relevant evidence checks.
- It stated that the bootstrap, Project Brain, and checkpoint are absent from `dnd-solo` main, and that BFDM `PROJECT_CONTROL.md` is absent from `bfdm-corpus` main.

## Why this does not close G4

The subject was sent to the proposed branch. A collaborator who clones default `main` does not get `PROJECT_BOOTSTRAP.md`. The corrected model is consumable on the proposed route and is not yet what canonical main serves. G5, a second change with no personal reminder, was not run.
