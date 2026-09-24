# ADR 0002: Separate Geometry Authority from Visual Asset Lookup

**Status:** Accepted  
**Date:** 2026-09-23

## Context

The runtime needs maps, scene art, creature/NPC art, and handouts, but these asset types have different authority and reveal requirements. Treating every image as interchangeable presentation risks geometry drift and information leaks.

## Decision

Use separate manifests with distinct responsibilities:

- `assets/maps/index.json` is the authoritative repository binding for canonical DM/player map identity and geometry role.
- `assets/art/index.json` resolves level/scene art and entity-reference art.
- `assets/handouts/index.json` resolves reveal-gated handouts.

The canonical DM map controls original spatial geometry. The player map is a presentation base only and remains knowledge-gated. Adventure source controls room contents. Current state controls changes caused by play. Artwork cannot establish hidden canon by itself.

## Consequences

- The runtime may not invent replacement geometry when a canonical map exists.
- An unlabeled player map may not be shown wholesale merely because it lacks room numbers.
- Creature art is looked up by identity, not inferred from the current level.
- Composite handout sheets require partial-reveal handling.
- Future tooling should build a reveal graph and masked/cropped player-map renderer instead of duplicating map registries.
