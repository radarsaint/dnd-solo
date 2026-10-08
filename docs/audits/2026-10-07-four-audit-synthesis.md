# Four-audit synthesis — 2026-10-07

This synthesis reconciles four independent audits:

1. executable runtime ground truth;
2. Kit quality / failure localization;
3. BFDM / ChatGPT Work research readiness;
4. project truth / contradiction audit.

## Governing finding

All four audits expose the same project-level failure mode:

> **Proxy evidence has repeatedly been mistaken for demonstrated truth.**

Examples:
- passing tests != satisfying play;
- a landed fix != demonstrated player-facing improvement;
- citation presence != semantic verification;
- source accessibility != trustworthy derived research;
- room loading != source-to-room capability;
- architecture/specification != implemented capability;
- a document calling itself canonical != current authority;
- BFDM research quality != current Kit quality;
- DM judgment != the whole Kit experience.

## Four separate confidence layers

### 1. Executable runtime truth

This is the strongest current confidence layer.

`dnd-solo/main` is materially beyond the Area 6c prototype and has a generalized runtime substrate.

Important unresolved implementation boundaries remain, including source-to-room authoring, combat transitions, player-roll ownership, validator interference, some social-intent recognition, and overlapping PR stacks.

### 2. Player-experience truth

This is substantially weaker than runtime confidence.

Current implementation has advanced faster than serious human quality evaluation.

Therefore many historical failures are not safe to repeat as current failures, and intended fixes are not safe to call player-facing successes.

Use behavioral freshness states:
- DEMONSTRATED_CURRENT_FAILURE
- DEMONSTRATED_CURRENT_SUCCESS
- HISTORICAL_FAILURE
- MECHANICALLY_ADDRESSED_UNRETESTED
- STALE_FAILURE
- UNKNOWN_CURRENT

Current demonstrated blocker classes include PR #103, PR #97/#101, PR #102, and PR #73.

The larger uncertainty is current post-fix, non-6c sustained play quality.

### 3. BFDM research truth

Source accessibility is now strong enough for serious research, but derived-research trust is not equivalent to source readiness.

PR #38 concretely demonstrates why. Its first tranche stages 20 S3 cases / 120 propositions at UNVERIFIED. BDC-S3-004 has a broken prep-evidence reconstruction chain even though the live Discord event remains recoverable.

Use two readiness axes:
- SOURCE / SUBSTRATE READINESS;
- DERIVED-RESEARCH TRUST READINESS.

PR #28 is currently a useful hypothesis map, not a verified gold-label set for Stage 3.

### 4. Project / coordination truth

Several older authority surfaces still look current enough to mislead capable agents.

Major traps include:
- Project KRABS v0.1;
- pinned ZIPs mistaken for current main;
- old in-repo BFDM mirrors;
- append-only board used as live work queue;
- stale open PRs;
- duplicate cleanup PRs;
- “canonical” labels treated as timeless authority.

Current authority must be resolved by live repo state, current control documents, explicit supersession, and artifact type.

## Current project state

The project is no longer primarily blocked by lack of machinery.

It is blocked by insufficient confidence about:
- what current machinery produces in actual play;
- which BFDM-derived claims are trustworthy enough to build upon;
- whether every agent is operating from the same version of project truth.

This does not mean engineering should stop.

It means engineering, research, and evaluation should increasingly turn unknowns into evidence rather than automatically adding sophistication.

## Current sequencing

### Runtime lane

Skippy / Grok Bots should reconcile the runtime PR stack, land/fix demonstrated blockers, and maintain repeatable evaluation/instrumentation.

### Research lane

Scarce ChatGPT Work should prioritize:
1. semantic verification of high-leverage research dependencies;
2. adversarial Earthfall/Saturday attack on Phase 2 hypotheses;
3. restraint / negative-space research;
4. failure -> diagnosis -> correction -> later-behavior trajectories;
5. bounded creative-method contrasts;
6. only then trusted structural cases and minimal cognition experiments.

### Evaluation lane

After known blockers are merged/resolved/avoided, current-main sustained play should test materially different real rooms and cross ordinary boundaries between exploration, social interaction, physical action, checks, NPC initiative, and combat.

The goal is to discover the next quality ceiling rather than rediscover known plumbing defects.

### Coordination lane

Current-state control is rewritable. History remains in git/issues/PRs/audit artifacts.

Every substantial handoff should state repo/SHA, evidence class, scope, verification, unresolved dependencies, next owner/action, do-not-redo warnings, and delta.

## Ownership

- **Brendon:** product direction, high-value creative judgment, disputed requirements, merge approval.
- **Nagatha:** PM/review/acceptance coordination, reconciliation of overlapping work, bundle preparation, merge coordination.
- **Skippy / Grok Bots:** runtime engineering, wiring, tests, PR-stack coordination, integration.
- **Grok Build / shell-capable agents:** executable reconnaissance, deterministic repository/tool work.
- **GPT workers:** bounded research, evaluation, audits, synthesis, voice/taste/content work.
- **ChatGPT Work:** scarce autonomous multi-source work where its capabilities materially outperform ordinary GPT.
- **Control-room synthesis:** reconcile outputs against current repo truth and the total-experience north star.

## North star

**Kit is the product. The total experience is the acceptance layer.**

No proxy—judgment, cognition, memory, BFDM fidelity, runtime correctness, personality, latency, visuals, UI, or test coverage—gets to become the product.
