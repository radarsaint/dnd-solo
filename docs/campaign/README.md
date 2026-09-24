# Dungeon of the Mad Mage Campaign Backend

This directory contains the campaign-specific state/behavior layers consumed by the generic runtime.

## Campaign through-line

- `HALASTER_DM_LAYER.md` — operational model for Halaster's motives, observation, regard, interventions, tests, favors, grievances, and portrayal constraints.
- `HALASTER_THROUGH_LINE_LAYER.md` — reverse-designed interaction spine identifying where rooms, scenes, conditions, and consequences develop the Halaster relationship from Level 1 through Level 23.

## Level story engines

`levels/LEVEL_LAYER_CONTRACT.md` defines the common causal model.

The campaign includes:
- `LEVEL_00_GAME_SETUP.md`;
- `HUB_SKULLPORT.md`;
- `LEVEL_01_DUNGEON_LEVEL.md` through `LEVEL_23_MAD_WIZARD_S_LAIR.md`.

Each numbered level is accountable for:
- initial equilibrium;
- active motion independent of the player;
- player-variable pressure points;
- trigger -> reaction rules;
- escalation and aftermath state;
- player-facing evidence;
- named NPC motive/knowledge/relationship state;
- cross-level consequences;
- canonical map binding.

## Geometry

Room IDs and DM maps are coordinated. Keyed area N binds to area N on that level's canonical DM map. Mapped geometry is fixed unless play physically changes it.

The runtime may describe geometry, but it may not invent or relocate rooms, doors, corridors, secret passages, stairs, shafts, gates, scale, or adjacency.
