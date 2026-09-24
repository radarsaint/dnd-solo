# Decision: Canonical DM Personality Core

## Status
Accepted

## Context

The first personality pass produced a large long-form specification covering appetites, pillar weighting, inhibition rules, table presence, NPC behavior, stakes telegraphing, and self-evaluation. That document was useful for discovering the design space, but it is too large and diffuse to serve as the live answer to "who is the DM?"

The DM's identity also needs to be accessible from any project chat and any future runtime surface without depending on local conversation history.

## Decision

Use `docs/personality/dm-personality-core.md` as the canonical project-wide DM identity.

The core is intentionally compact. It defines:
- who she is;
- what she wants from the game;
- what she values;
- her personality boundaries;
- pillar-specific biases;
- when her own table presence surfaces;
- the central rule she uses when several equally valid DM choices exist.

Use `docs/personality/dm-personality-development.md` only for deliberate personality development and testing.

Treat `docs/personality/dm-personality-layer-v0.1.md` as the earlier design/workshop artifact, not as an additional live prompt.

## Runtime boundary

The personality core influences taste, emphasis, pacing preference, humor, reward presentation, nudging, and selection among equally valid DM choices.

It does not override:
- published/source facts;
- rules adjudication;
- campaign state;
- NPC motives and knowledge;
- canonical map geometry;
- player knowledge/hidden-information boundaries.

Local chats may explore personality changes, but changes become canonical only when they are promoted into `dm-personality-core.md`.

## Development pipeline

Personality work follows:

`workshop -> distill -> test -> diagnose repeated failures -> regression -> promote -> compress`

The goal is to make the live core smaller and sharper as the DM becomes better understood, rather than accumulating special-case instructions.
