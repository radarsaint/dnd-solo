# Kit's Personality: Implementation Audit and Next Build

**Status:** Updated 2026-09-30. The candidate identity is implemented in the canonical core and turn instructions. It now draws on Brendon's D&D craft and novel design decisions; a distinctive expressed personality has **not** been demonstrated. This file is development guidance, not an additional live prompt.

The [character development note](kit-character-development.md) explains the source decisions, the resulting personality, and newly authored demonstrations. The [transfer probes](../../tests/scenarios/modeled-personality-transfer.md) define the next comparison. The demonstrations are not generated play or approved training targets.

## What exists, exactly

| Piece | Present | What it proves |
| --- | --- | --- |
| Stable identity and values | `dm-personality-core.md` defines Kit's drives, taste, boundaries, and selective table presence | We have an intended character, not evidence that she performs like one |
| Richer workshop | `dm-personality-layer-v0.1.md` describes appetite pressure, inhibition, humor, relationships, and NPC embodiment | These are design notes; appetite and relationship dynamics were not ported into the turn loop |
| Live context | `Runtime.context()` loads the core; `prepare_inputs()` gives it to the private decision; `public_performance_base()` gives it to the performer | The text is available to both model stages |
| Turn reaction | `PLAN_SCHEMA` has a goal, appraisal, move, tone, and table-presence choice; state saves current appraisal and up to 24 episodes, with a selected subset in context | A model can label a reaction and recall recent episodes; there is no tested behavioral or emotional dynamics model |
| Public handoff | At baseline the performer received a four-part brief, tone, and presence, plus the core. On `kit-focus-brief` the brief adds `reply_to`, `scope`, and a checked public-safe `kit_focus` derived from the goal and `kit_choice` | `improv_read.kit_choice` and appraisal cause remain private. `kit_focus` gives Kit's choice a channel to the performer; whether the spoken turn actually acts it out still has to be judged in play |
| Expressed voice | The room has a dealer actor card; Kit's direct remarks can be labeled `Kit`. The `kit_expression_v1` performer instruction (Kit's table voice, distilled from the core) is the default for both chat-bridge paths on `kit-bridge-voice`, and each turn records which variant ran | One NPC has an authored cue. Kit's own repeatable vocal register and judgment have not been calibrated or evaluated; the voice is a hypothesis made default at Brendon's direction, not a proven improvement |

The first Nik exchange is the counterexample: Kit chose `npc_embodiment` and `interest`, then gave the player an ordinary price announcement. At baseline the validator accepted one short NPC segment, and nothing checked that the brief ("name the toll") agreed with the goal. On `kit-focus-brief` that exact reply is rejected as a flat `exchange`; see [Kit's expression gap](../architecture/kit-expression-gap.md) for what that guard does and does not prove. The failure is therefore partly a **personality implementation gap**, as well as a performance handoff and quality-evaluation gap. A more detailed actor card alone will not make Kit herself recognizable. More personality prose alone will not prove an improvement either.

## Build the person as behavior

Treat the canonical core as Kit's enduring preferences. Add a small *situational personality state* and an *expression choice* only when each affects her observable decisions. The intended turn relationship is:

1. **Stable wants:** The core says what she tends to care about across rooms and pillars.
2. **Recent history:** Accepted player actions, surprises, earned payoffs, failed attempts, recurring jokes, and explicit player feedback can alter which want is salient. Do not invent affection or player emotions from silence.
3. **Appraisal:** A real event affects one current want for a stated reason, or none. Kit's interest in play is distinct from an NPC's motive.
4. **DM choice:** She selects what to foreground, when to rule directly, when to let an actor try something, when to challenge, when to celebrate, and when to stay out of the way.
5. **Expressive intent:** Before dialogue, describe **one visible consequence of that choice** in public-safe terms. This is now the brief's `kit_focus` field on `kit-focus-brief`. It can be a particular framing, tactic she allows to breathe, direct Kit reaction, or purposeful restraint that changes the scene's focus. A generic `wry` or `present` label is insufficient.
6. **Performance and feedback:** The spoken turn must actually enact that choice. Only accepted play and explicit feedback update her later memory. Test whether relevant prior history changes the next expressed choice and irrelevant history does not.

No numeric appetite meter or permanent relationship score should be added merely to look like an inner life. The [long-form design](dm-personality-layer-v0.1.md) proposes appetite pressure; it must first beat a simpler recent-history approach in paired continuations. The NPC's emotional state and knowledge remain separate from Kit's.

## First candidate expression profile, for testing

This is a **hypothesis** about what will be recognizable in play. At Brendon's direction to develop and wire Kit, the 2026-09-30 candidate is now in the live core: perceptive staging, delight in audacity and competence, earnest commitment, emotional counterpoint, and room for unresolved relationships. Its effectiveness remains unvalidated. Use the novel's design decisions as craft evidence; keep its voices, lore, and predetermined outcomes out of the campaign.

| Situation | Kit's possible recognizable choice | Failure to watch for |
| --- | --- | --- |
| Player offers a specific social opening | She lets the actor answer that exact offer and try to gain something; her interest shapes which tension she spotlights | NPC dispenses price or lore irrespective of the player's words |
| Player attempts something audacious or absurd | Brief dry delight or disbelief can show, followed immediately by an honest ruling and available affordance | Empty praise, a long joke, or rewarding an impossible action |
| Player catches a setup | She enjoys being surprised; pressure falls on the actor to adapt rather than on preserving her planned reveal | NPC confesses, scene freezes, or Kit railroads back to the clue |
| Threat turns serious | Her enjoyment of capable opposition shows through fair, legible danger and the NPC's own tactics | Every enemy speaks in Kit's humor or the danger is described only with menacing adjectives |
| Player asks for a narrow roll or fact | She answers directly and stops, leaving space for the player | Personality appears as chatter that slows call and response |
| Emotional or quiet scene | She foregrounds the people and evidence and regulates her own voice | Mandatory wisecrack or sudden campaign exposition |

Her *candidate* direct register is candid, quick to recognize an interesting bid, dry when humor is earned, and precise when ruling. She is invested in what the player tries, including attempts that undo her expectations. This is a **behavioral direction**, not a set of catchphrases. The player should be able to identify Kit from which opportunities she notices, how she treats a creative failure, what she lets an NPC pursue, and when she steps forward. A dealer or goblin must still sound like themselves.

## Implementation and proof order

1. **Produce identity comparisons.** Use the same source, actor card, player input, accepted event, and model. Compare baseline commit `a936a26b570ebd1093ab8e51436a9a302bcedef7` with the candidate, preserving each revision's core and instructions. Both bridge paths default to `kit_expression_v1`. The `current` variant (CLI `--performance-variant current`) removes only the extra performer guidance; it still reads that revision's core and is therefore not a before-change personality baseline. Use it for a performer-guidance ablation. Use staged generation to preserve decision-before-performance, and hold a checked public brief fixed for a separate voice-only comparison. The trial does not implement appetite or relationship dynamics.
2. **Score continuity, not a single quip.** Blind-review an opening and at least two replies. Ask what Kit seemed to care about, how she differed from the NPC, whether the player wanted another turn, and which line or behavior supports that judgment. Include a narrow ruling and a serious moment where restraint is part of the identity.
3. **Retain the winner after play.** The public-safe `kit_focus` handoff was wired first on 2026-09-28, and this developed profile was wired on 2026-09-30, at Brendon's direction. Both remain subject to revision after real comparisons. Compress a successful profile into the existing core. Keep the handoff short, concrete, and public-safe. If it fails, reconsider the model, examples, or scene choice before adding more schema.
4. **Add longer-lived state when earned.** Test whether relevant remembered player behavior changes Kit's later attention and decisions. Introduce appetite satisfaction and relationship tracking only with observable event types and an ablation showing improvement. Preserve the ability to be wrong about the player.
5. **Transfer.** Repeat with different NPCs, exploration, rulings, threat, reward, and another playable room. Kit's signature should travel; the dealer's mannerisms should stay in area 6c.

This is the missing work between a character description and a DM a player wants to return to. Current passing backend tests establish storage and formatting. They do not establish this personality.
