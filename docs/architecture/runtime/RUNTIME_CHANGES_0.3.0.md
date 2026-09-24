# Runtime Architecture Changes — 0.3.0

**Date:** 2026-09-23

This change set defines the backend interface required by the alpha DM Personality Layer.

## New contract

Added `DM_PERSONALITY_BACKEND_CONTRACT.md`.

The backend now has an explicit responsibility to assemble a bounded `dm_context` packet before meaningful DM responses. The packet supplies truth, state, knowledge boundaries, geometry, active story motion, accountable actors, tactical capabilities, stakes evidence, rewards, campaign callbacks, Halaster relevance, player/character history, momentum signals, and recent play rhythm.

The personality layer does not reconstruct these facts from raw adventure prose and does not create facts to satisfy its appetites.

## Appetite support

Every alpha personality appetite now has a documented backend dependency contract:
- Story Enjoyment -> existing threads, consequences, choices, callbacks, setup/payoff state.
- Roleplay / NPC Embodiment -> actor motives, beliefs, fears, secrets, relationships, reconsideration triggers, communication profile.
- Competent Opposition -> canonical geometry, capabilities, intelligence limits, tactical goals, morale, coordination, knowledge limits.
- Felt Challenge -> actual risks, resources, consequences, uncertainty, and perceivable warning evidence.
- Creative Play -> exact player intent, physical affordances, rules, conditions, leverage, constraints, consequences.
- Shared Humor -> grounded callbacks, habits, NPC personality, and actual absurd outcomes.
- Player Surprise -> expected-pattern evidence versus the action actually taken.
- Halaster Through-Line -> only dedicated Halaster state and source-supported/through-line-permitted hooks.
- Loot Pleasure -> exact reward state, significance, character relevance, and prior setup.
- Momentum -> recent action history, repetition, time since new information/choice, natural pressures, NPC next actions.
- Craft Pride -> already-established setups and currently valid payoffs only.

Character Development is supported as a derived evidence stream from repeated player-character choices rather than silently added as a new personality appetite.

## New persistent state requirements

The eventual save/runtime state now requires:
- `player_model` for out-of-character table patterns;
- `character_pattern_state` for in-fiction repeated choices/relationships;
- `rhythm_state` derived from tagged meaningful events.

These remain separate from one another and from NPC knowledge.

## Recent rhythm

Meaningful event-ledger entries may carry tags for types of play actually expressed. The backend supplies recency/frequency evidence to the personality. It does not decide which appetite should lead.

## Session loop

The runtime session loop now includes context assembly before personality judgment. The flow is:

`source + map + state -> valid possibilities -> dm_context -> personality emphasis -> adjudication/presentation -> state/event updates`

This keeps personality downstream of factual authority while still giving it enough information to behave consistently and develop rhythm across long play.