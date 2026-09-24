# Runtime Layers

This is the target conceptual stack. The technical implementation may rename modules, but these responsibilities should remain separable.

## 1. Source layer
Loads authorized campaign/rules/source material and returns scoped evidence.

## 2. Campaign state
Tracks established world facts, time, locations, NPC state, discovered information, active threats, unresolved threads, inventory, relationships, consequences, player-model state, character-pattern state, and recent rhythm state.

## 3. Campaign direction
Tracks authored through-lines and local concerns. For *Dungeon of the Mad Mage*, this includes the Halaster behavior/through-line layers and one story-engine layer per dungeon level. These are opportunities and pressures, not rails.

## 4. Scene model
Determines the current situation, actors, physical environment, actionable objects, visible stakes, and immediate pressures.

Mapped geometry is resolved from the canonical DM map and map registry. Geometry is not improvised when a canonical map exists.

## 5. NPC/opposition model
Runs NPC goals and creature-appropriate tactics independently enough that actors feel embodied rather than serving as exposition interfaces.

Named or individually characterized NPCs require motive state. Faction membership can provide defaults but does not replace an NPC's individual goals, fears, beliefs, relationships, or reconsideration triggers.

## 6. DM context assembly
Builds the bounded `dm_context` packet defined in `docs/architecture/runtime/DM_PERSONALITY_BACKEND_CONTRACT.md`.

It supplies the personality layer with current truth, knowledge boundaries, geometry, story motion, accountable actors, tactical state, stakes evidence, campaign callbacks, rewards, player/character history, Halaster relevance, momentum signals, and recent play rhythm.

The backend determines what is true, known, possible, and already in motion. It does not choose dramatic emphasis.

## 7. Personality arbitration
Consumes the current pillar(s) of play, recent appetite satisfaction, and the assembled `dm_context`. Chooses one leading appetite and at most one or two supporting influences.

The personality may emphasize valid possibilities. It may not create world facts to satisfy an appetite.

## 8. Adjudication
Resolves rules, uncertainty, checks, costs, consequences, and state changes.

## 9. Presentation
Chooses what the player actually sees: narration, NPC dialogue, direct DM voice, map/art references, rolls, mechanical information, and available choices when appropriate.

## 10. Reflection/test telemetry
After meaningful scenes, records a small amount of structured evidence about what worked or failed and tags meaningful play expression for rhythm tracking. This is for tuning the runtime, not for narrating self-evaluation to the player.
