# Project Scope

## Goal

Build a single-player D&D experience with Kitiara, an AI Dungeon Master whose personality and competence make players want to keep playing. The long-term test is whether players would choose her over an experienced human DM given the same adventure and character. That preference has not been demonstrated yet.

The DM should care about the campaign, enjoy roleplay, run competent opposition, embody NPCs, telegraph stakes, reward creativity, make loot exciting, maintain momentum, and develop an identifiable table relationship with the player over time.

For a plain-English account of the approach, current progress, first playtest, and next steps, see [What We Are Building](../WHAT_WE_ARE_BUILDING.md).

## Separation of concerns

### Generic DM runtime
Responsible for adjudication, scene handling, NPC execution, opposition behavior, state transitions, source retrieval, campaign-memory access, and response composition.

### Personality layer
Responsible for what the DM prefers, notices, enjoys, prioritizes, restrains, and occasionally reveals about herself at the table.

### Campaign layer
Responsible for the actual adventure's through-line, local floor/area concerns, factions, NPCs, clues, encounters, authored pacing, and intended long-term payoffs.

### Asset layer
Responsible for maps, tokens, art, references, metadata, and stable identifiers that the runtime can request without depending on chat history.

### Player-facing UX
Responsible for what is shown to the player, how much is revealed, how maps/art are surfaced, and how the DM distinguishes in-world presentation from direct table talk.

## Non-goals

- Do not encode one campaign as if it were the universal DM personality.
- Do not make personality synonymous with jokes or a prose style.
- Do not let hidden plot requirements automatically override legitimate player choices.
- Do not solve the campaign for the player.
- Do not use one enormous prompt as the primary architecture.
