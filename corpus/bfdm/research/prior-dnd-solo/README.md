# Prior `dnd-solo` Research Snapshots

This directory centralizes research artifacts that were originally developed in `radarsaint/dnd-solo`.

They are preserved as **historical research snapshots**. Their presence here does not make every conclusion current or validated.

## PR #23 — modeled personality pilot

Origin:
- PR: `radarsaint/dnd-solo#23`
- title: *Develop Kit's personality from campaign and novel decisions*
- branch: `kit-modeled-personality`
- head at archival check: `54a8ece196c30979152b3bb37167cd3ab7a7ffd6`
- state: open draft, unmerged

Preserved here:
- pilot source coverage;
- evidence/retrieval records;
- novel retrieval manifest;
- modeled-DM-corpus methodology;
- personality-development / implementation artifacts.

Important limitation:
this work predates the broader private-corpus organization and many later corrections. It should be read as a pilot, not a finished model.

## PR #36 — decision corpus batch 1

Origin:
- PR: `radarsaint/dnd-solo#36`
- title: *Begin Brendon decision corpus with attributed evidence and held-out partition*
- branch: `kit-decision-extraction`
- head at archival check: `7eaa2e0eda14e7d9cee1cb0f99c94fa5f94fb70b`
- state: open draft, unmerged

The full `research/decision-corpus/2026-10-01/` package is preserved beneath this snapshot.

Its own dataset card reports:
- 23 decision records;
- 11 based on direct comments/revision comparison;
- 7 based on documented Kit feedback;
- 5 lower-confidence semantic-retrieval leads;
- 8 negative/preference records;
- 6 cross-project hypotheses;
- 3 blind A/B development probes;
- 15 Empire City files prospectively quarantined for evaluation.

This package is especially useful because it already separates:
- local evidence;
- analyst inference;
- generalization confidence;
- preferences;
- contradictions;
- evaluation partitions.

It is **not** a validated training set.

## PR #38 — creative/social requirements audit

Origin:
- PR: `radarsaint/dnd-solo#38`
- title: *Audit Kit creative-social requirements before architecture*
- branch: `kit-creative-social-requirements-audit`
- head: `2027f74592d63e5c4308814fae3e95831c439205`
- state: open draft, unmerged
- original path: `docs/personality/creative-social-requirements-audit.md`

A direct connector copy into this repository was blocked during archival. The original remains intact in `dnd-solo`.

The PR describes a requirements-only audit that:
- separates Brendon's stated design claims from GPT extrapolation;
- turns vague labels into observable requirements;
- treats "most satisfying for this table", "creative inner life", "good companion", and similar phrases as unsolved requirement labels rather than mechanisms;
- adds tests for persistent wants, selective taste, table talk, relational competence, emotional/escapist play, delayed satisfaction, emergence, plural initiative, and cross-layer identity;
- deliberately does not select a runtime architecture.

## Relationship to current work

Current BFDM research is broader and more conservative about generalization than these pilots.

Read old findings in light of:
- [../../CORRECTIONS_LOG.md](../../CORRECTIONS_LOG.md)
- [../../METHOD.md](../../METHOD.md)
- [../../CHRONOLOGY.md](../../CHRONOLOGY.md)

Do not silently overwrite old snapshots when current research disagrees with them. Preserve the disagreement.
