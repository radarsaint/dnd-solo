# Runtime Layers

This is the target conceptual stack. The technical implementation may rename modules, but these responsibilities should remain separable.

## Persistent DM identity

Before the situational stack below, the runtime has one stable project-wide personality dependency:

- `docs/personality/dm-personality-core.md`

That file answers **who the DM is**: her enduring wants, tastes, personality boundaries, pillar biases, and selective table presence. It should remain stable across rooms, levels, sessions, and project chats.

Do not load `dm-personality-development.md` as additional live personality prose during ordinary play. That file defines how the core is tested and revised.

The personality layer influences emphasis, taste, humor, pacing preference, and how equally valid DM choices are selected. It does not override source truth, rules, campaign state, NPC motives, map geometry, or knowledge boundaries.

## 1. Source layer
Loads authorized campaign/rules/source material and returns scoped evidence.

## 2. Campaign state
Tracks established world facts, time, locations, NPC state, discovered information, active threats, unresolved threads, inventory, relationships, and consequences.

## 3. Campaign direction
Tracks authored through-lines and local concerns. These are opportunities and pressures, not rails.

## 4. Scene model
Determines the current situation, actors, physical environment, actionable objects, visible stakes, and immediate pressures.

## 5. NPC/opposition model
Runs NPC goals and creature-appropriate tactics independently enough that actors feel embodied rather than serving as exposition interfaces.

## 6. Personality arbitration
Applies the stable personality core to the current pillar(s) of play, scene pressure, recent appetite satisfaction, player behavior, and campaign concerns.

The runtime should normally allow one personality drive to lead a response with at most one or two supporting influences. The goal is a coherent person making choices, not a checklist that tries to express every trait in every response.

## 7. Adjudication
Resolves rules, uncertainty, checks, costs, consequences, and state changes.

## 8. Presentation
Chooses what the player actually sees: narration, NPC dialogue, direct DM voice, map/art references, rolls, mechanical information, and available choices when appropriate.

Direct DM table presence should be selective. Most personality should be felt through choice, pacing, NPC embodiment, challenge, humor timing, reward presentation, and what the DM chooses to care about.

### Visual asset resolution
Presentation resolves visual resources through the role-specific manifests:

- `assets/maps/index.json` for canonical DM/player map pairs;
- `assets/art/index.json` for level/scene and entity art;
- `assets/handouts/index.json` for reveal-gated handouts.

DM maps are private geometry authority. Player maps are presentation bases and remain knowledge-gated. Art may illustrate established source/state but cannot create hidden canon. Composite handouts must support partial reveals.

## 9. Reflection/test telemetry
After meaningful scenes, records a small amount of structured evidence about what worked or failed. This is for tuning the runtime, not for narrating self-evaluation to the player.

Personality changes should follow the development pipeline: workshop -> distill -> test -> diagnose repeated failures -> regression test -> promote -> compress.
