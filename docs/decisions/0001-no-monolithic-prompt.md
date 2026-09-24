# ADR 0001: Do not implement the DM as one monolithic prompt

Status: Accepted

## Context

The personality design is already large enough that adding campaign state, source material, maps, rules, tactical logic, and UX instructions to the same document would make behavior harder to reason about and harder to test.

## Decision

Keep personality as a versioned behavioral layer. Keep runtime contracts, campaign content, assets, and test scenarios in separate files/modules with explicit interfaces.

## Consequences

- Personality can be tuned without rewriting campaign logic.
- Campaigns can reuse the generic DM runtime.
- Tests can target one layer at a time.
- Large source collections can be indexed rather than embedded into prompts.
