# Kit quality / failure-localization audit — 2026-10-07

**Evidence basis**
- `radarsaint/dnd-solo main @ e3a5e9908357441051df24dac8086d8d4c7f26f5`
- `radarsaint/bfdm-corpus main @ 65513f294e72a3eb961d5699c21ddc1f14ceef2c`
- active BFDM PR #38 treated as an unmerged integrity audit
- playtests, evaluation runs, current open runtime PRs, and later fixes

**Purpose:** preserve the actionable delta from GPT Audit 2 without turning the full chat report into project state.

## Central finding

Kit is no longer mainly blocked by missing personality, missing source retrieval, or Area-6c-specific mechanics.

Current main has advanced substantially beyond the last serious player-facing quality tests.

Therefore the current picture is:

1. a small set of concrete runtime defects are still demonstrated;
2. many historically severe failures were mechanically addressed and require current human retesting;
3. the larger blocker to confident quality claims is now an evidence-freshness gap.

Do not infer either “Kit is still bad at X” or “Kit now solved X” when implementation changed materially after the last comparable human play.

## Demonstrated current failures

### PC roll ownership — PR #103

Current main can silently take ownership of a player check / reroll an established check in situations where the table procedure says Kit decides whether a check is needed and the player rolls it.

Classification: adjudication/procedure + runtime.

### Combat transition completeness — PR #97 / #101

Player-initiated combat exists and older “combat does not work” claims are stale.

Current main still lacks or incompletely handles ordinary transitions including monster initiation, surprise, player-rolled save riders, hidden actors, downed-PC/death-state and related continuation behavior.

Classification: combat adjudication + state.

### Validator word floors — PR #102

Current main can reject short, functionally complete DM turns because they miss raw word-count floors while allowing padded responses that accomplish less.

Classification: runtime validator interfering with DM performance.

### Deliberate social omission — PR #73

At least one live-observed case remains where deliberate omission intended to create a false impression is not recognized/adjudicated as a deception-shaped approach.

Classification: player-intent recognition + social adjudication.

## Demonstrated improvements

- Marked-deck play became materially better and produced at least one Brendon-approved actual-play moment.
- Onboarding improved when the opening followed character-established causality.
- Basic Area 6c execution improved dramatically in reruns.
- Watchroom routing/stall defects were mechanically repaired and replayed cleanly.
- Area 6c is no longer the declared architecture.

These successes have different evidence classes. Do not collapse actual play, scripted replay, and unit/regression success into one category.

## Historical failures that should not be repeated as current claims without retest

- trivial high-card / marked deck cannot matter;
- player-initiated combat does not work;
- Avrae damage/skill rolls basically do not work;
- the exact old idiom failures remain unfixed;
- the October 4 watchroom stalls/misreads are still current;
- Area 6c is Kit's architecture;
- missing retrieval is the primary Area 6c problem.

## Recurring pattern

The most important recurring quality pattern is not simply weak prose.

> Kit/private machinery often has more useful information than survives into the player-facing game.

That can originate in recognition, selected concern, performance direction, validator pressure, deterministic runtime text, or final expression.

Another recurring pattern is that ordinary mixed-intent play finds seams between runtime categories faster than scripted single-intent probes do.

## Evaluation coverage consequence

Architecture/generalization has moved faster than quality evidence.

Especially weak or essentially untested at current quality level:
- downtime;
- loot/reward satisfaction;
- shenanigans over sustained play;
- long-term relationships;
- callbacks;
- campaign-scale judgment;
- persona continuity across long chat/play/debrief spans;
- long-horizon consequences.

## Next-playtest gate

A new Brendon playtest should generate new information rather than immediately rediscover known defects.

Before or during that test:
- avoid or resolve the known #103 / #102 blockers;
- if the room needs ambush/downed-state/monster-init behavior, resolve or explicitly account for the #97/#101 gap;
- run actual current main;
- use a non-6c real room rich enough for exploration, social play, physical action, checks, NPC initiative, and potentially combat;
- capture player text, prepared situation, accepted runtime event, Kit decision, spoken result, retries/rejects, committed state, latency, and Brendon's reaction.

The goal is sustained ordinary play across boundaries, not a larger benchmark.

## Product-level delta

Do not currently say “DM judgment is the demonstrated primary bottleneck.”

It may become the long-term hard problem, but current evidence does not isolate it cleanly yet because:
- remaining runtime interference still contaminates play;
- current main is under-tested after major repairs.

Current best statement:

> Kit has demonstrated some genuinely good DM moments, has removed much of the machinery that previously sabotaged them, still has several concrete runtime blockers, and lacks enough post-fix non-6c sustained human play to establish her present DM-quality ceiling.

