# Runtime Backend Documentation

This directory contains the backend contracts developed to support the live DM personality core.

## Core files

- `DND_SOLO_RUNTIME.md` — full runtime architecture and authority model.
- `DM_PERSONALITY_BACKEND_CONTRACT.md` — bounded `dm_context` interface supplied to personality arbitration.
- `MAP_INDEX.md` — deterministic level/map/room binding and fixed-geometry contract.
- `RUNTIME_CHANGES_0.2.0.md` — introduction of level story engines, NPC accountability, Halaster layers, and map authority.
- `RUNTIME_CHANGES_0.3.0.md` — personality-backend context interface and persistent player/character/rhythm requirements.

## Boundary

The backend determines what is true, known, possible, physically reachable, and already in motion.

The personality core determines what deserves attention, which valid possibility to emphasize, and how the DM presents it.

The personality may not create world facts to satisfy a preference. The backend may not manufacture drama to satisfy the personality.

## Campaign-specific dependencies

The Mad Mage implementation lives under `docs/campaign/` and includes:
- Halaster behavior state;
- reverse-designed Halaster campaign through-line;
- shared level story-engine contract;
- game setup and Skullport layers;
- all 23 numbered dungeon level layers.

Map assets/manifests live under `assets/maps/`; runtime geometry remains authoritative and non-improvisational.
