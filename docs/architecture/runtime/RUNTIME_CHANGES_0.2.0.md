# Runtime Architecture Changes — 0.2.0

**Date:** 2026-09-23

This change set moves D&D Solo from retrieval-first architecture toward an operational Dungeon Master runtime.

## Behavioral architecture

The runtime now maintains three distinct attention layers: campaign through-line, current-level story, and current scene. Halaster has a dedicated behavior model plus a reverse-designed interaction spine. Every numbered dungeon level has a living story engine with accountable NPC motives, active motion, pressure points, reaction rules, escalation states, outcomes, player-facing evidence, and cross-level consequences.

## NPC accountability

A named or individually characterized NPC cannot be run as a stat block alone. Relevant NPCs receive stable motive state and retain it across rooms and, when they move, across levels. Shared-body/multiple-will cases receive separate motive records when goals can diverge.

## Geometry architecture

Canonical DM/player map pairs are present for all 23 numbered levels, plus three Skullport regions. `MAP_INDEX.md` binds each numbered level to its exact level story layer, canonical DM map, player map, keyed-area range, and indexed room headings. Each numbered level file also contains its own explicit geometry binding.

The runtime has **zero improvisational authority over mapped geometry**. DM maps determine original room placement, boundaries, adjacency, doors, corridors, secret passages, stairs, shafts, gates, vertical relationships, and printed scale. Keyed adventure text determines room contents and rules. Current spatial state controls physical changes caused by play.

Map and room numbering are a shared binding key: keyed source area N corresponds to map area N on that level.

Player-map assets do not reveal secrets by themselves. Player-known topology remains a derived subset of DM topology.

## Runtime load sequence

When a numbered level becomes active:
1. load its level story layer;
2. resolve its canonical DM map through `MAP_INDEX.md`;
3. load current spatial/knowledge/NPC/faction/Halaster overrides;
4. retrieve the smallest keyed room text for the current position;
5. adjudicate movement and navigation against canonical map geometry rather than memory or improvisation.

## Still pending

The specifications and map bindings now exist. Live persistence still needs concrete save schemas, event-ledger storage, revealed-topology persistence, SAVE/LOAD execution, and migration/version handling.