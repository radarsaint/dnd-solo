# Kit test room: Level 1, area 6c — Uktarl's room

## Purpose

Use one repeatable scene to test Kit's personality in action. The question is what she notices, wants, enjoys, worries about, and chooses while running it—and whether the player can feel that mind behind the table. Source facts and rules set the constraints; passing those checks alone does not pass this test. This is a conditional room snapshot, not a replacement for the published encounter.

**Executable seed:** `tests/fixtures/level_01_area_06c.json`

**Adventure authority:** `Mad_Mage_Source.txt`, Level 1, “The Undertakers,” area 6c and the surrounding area 6 encounter rules.

**Geometry authority:** `assets/maps/levels/map-01.01-dungeon-level-dm.png`, keyed area 6c. The visible south door leads to a short passage connecting to the rest of area 6. Do not infer additional exits from the prose fixture.
**Level behavior:** `docs/campaign/levels/LEVEL_01_DUNGEON_LEVEL.md`.

The seed assumes Uktarl, two bandits, and a doppelganger are still at their card table. If the spy at the Entry Well warned them and they assembled in 6a, this seed is invalid. Run that alert situation as a later variant with a different initial snapshot. The player character and sheet are supplied by the playtest; this seed does not assume a class, spell, or resource total.

## Facts Kit must work with

The occupants pose as vampires. The gang demands 10 gp per character for safe passage and prefers to turn hard targets against Xanathar's goblinoids. Uktarl enjoys lying and cheating, blames others for his problems, wants Harria out of his way, and values his own safety. He has Performance +4. A marked deck creates an opening for player scrutiny. The mountain carving holds a hidden key that the bandits do not know about; inspecting it can reveal the key with the source's DC 13 Wisdom (Perception) check. If Uktarl takes damage or sees an underling slaughtered, he retreats toward area 7; the others flee toward area 8 and join any bandits still there. Exact movement and combat positioning require the canonical map and a rules resolver.

Visible at entry: four apparently vampiric card players, coins and a ring on the table, the mountain carving, the recessed tub, and the south door. Kit should let the players discover the disguise, marked cards, key, and stored gear through play. The bandits' ignorance of the key matters: they cannot bargain with knowledge they lack.

## Source audit

The room seed was compared with the adventure's Level 1 Undertakers and area 6c text and the DM map on 2026-09-26. The map shows a roughly 20-by-30-foot room and one door on its south wall into a short passage; its grid is 10 feet per square. The keyed text supplies the contents and behavior below. These are source checks, separate from the automated tests.

| Source point | Seed representation | What still needs playtesting |
| --- | --- | --- |
| Four occupants, including Uktarl, two bandits, and a doppelganger in false-vampire dress | Four actors with private identities; DC 14 Insight in DM rules | Whether Kit handles the disguise fairly in conversation |
| Card table by the door, marked deck, coins, and silver ring | Visible table and valuables; hidden deck marks and exact treasure count | Gambling, suspicion, and theft rulings |
| North fresco, recessed 8-by-4-by-2-foot tub, hidden key on DC 13 Perception | Visible geometry; hidden key and its separate area 14b use | Physical stunts and player discovery |
| Uktarl's cheating and retreat, companions' flight, gang extortion | DM rules, motives, Performance +4, actor retreat conditions | Initiative, tactics, pursuit, and bargaining |
| Alerted Undertakers gather in 6a | Explicit seed precondition excludes that branch | A separate alert-state scenario |

The existing tests establish that the player view hides private facts and an accepted reveal persists. They do not measure Kit's personality. The source audit is a prerequisite for the personality test below, not its result.

## Personality test: event, appraisal, action, performance

Use the cognitive-agent model in `docs/architecture/runtime/DM_PERSONALITY_BACKEND_CONTRACT.md`. For each consequential turn, retain a compact causal trace in addition to the player-facing transcript:

1. **Knowledge and procedure:** Which retrieved facts and accepted state apply? What action is physically and mechanically possible? What practiced DM procedure or tactic handles it? The source and map are knowledge, not an unconscious state.
2. **Kit's appraisal and decision:** What did the player's action mean to Kit's current goals and expectations? Did it produce a specific reaction, or none? Which relevant memory or relationship affects her? What high-level DM move does she choose, and how does she regulate her table voice? Record this before the expressed turn.
3. **Expressed turn:** What the player actually hears: Kit's narration, her NPC performances, her rulings, and her direct comments on the player's choices. Keep Kit's table voice distinguishable from each NPC's voice.

The appraisal/decision record answers briefly:

- **Event and goal:** What happened, and which of Kit's established drives or current concerns did it advance, threaten, or leave untouched?
- **Appraisal:** What reaction followed from that relationship, with what strength and cause? Do not assign an emotion to every turn.
- **Action selection:** Which high-level DM move does she favor among grounded alternatives, and what remains open for the player?
- **Regulation:** How much of her direct voice belongs here? What recent beat, memory, or player response affects humor, threat, warmth, or quiet?

Keep the trace brief and specific. A claim like “I want to be funny” is useless without an actual choice that earns a laugh. Score the player-facing transcript first, without showing the evaluator the private trace. Then inspect the trace: did an event cause a plausible appraisal, did that appraisal affect the chosen move, and was it visible in the performance? A post-hoc story about Kit's feelings does not count. Do not use a fixed script or a required punchline as the target.

Run a causal check as well as a preference check. Keep the room, player declaration, legal resolution, and model settings fixed across paired continuations. In one continuation, include a relevant earlier Kit/player episode; in the other, omit it or replace it with a different *valid* episode. State in advance what difference in Kit's appraisal, move, or expression that episode should make. A separate pair changes an irrelevant memory; it should not redirect the scene. Repeat each pair to distinguish a consistent effect from generation noise. Both continuations must preserve the same source facts and player agency. A trace that changes while the expressed performance stays generic has failed the test.

Compare the complete, multi-turn Kit with a baseline that has the same room/rules context and personality description but no event-linked appraisal or episodic memory. Give blind readers the player-facing transcripts in randomized order and ask which DM they would keep playing with, plus the exact moment that decided them. Inspect private traces only afterward to explain successes or failures. This adapts the component-ablation method used in [Generative Agents](https://arxiv.org/abs/2304.03442); it does not assume that a plausible internal log proves entertainment. To test the project's *better than human* goal, also compare live multi-turn play with experienced human DMs given the same room information, and ask actual players which experience they want to continue. The ablation establishes whether the architecture helps; the human comparison tests the larger claim.

For example, if the player pulls up a chair: knowledge supplies the toll, marked deck, disguises, and actor limits; DM procedure does not grant automatic discovery of the marks. Kit's desire for roleplay may make this an appealing surprise. She might choose a brief amused table comment, then let Uktarl offer a seductive bad bargain while another player watches the visitor's hands. This is one possible causal sequence, not a prescribed line or outcome.

## Six personality probes from the same seed

Start a fresh copy of the seed for each probe. Continue for several turns before scoring; a strong opening line alone is insufficient.

| Player move | What should catch Kit's interest | What should come through to the player |
| --- | --- | --- |
| “I pull up a chair and ask what the stakes are.” | The player volunteered to roleplay with predators. Kit can enjoy the social opening and let Uktarl try to charm and fleece them. | Kit may show amused table presence; Uktarl gives a tempting, funny or unnerving invitation with room for a real decision. The other NPCs keep their own voices. |
| “I call out the dealer's marked cards.” | The player may have caught her setup. Kit should enjoy that, then consider Uktarl's pride, allies, and need to save face. | A consequential reaction from a person under pressure, with proof and uncertainty adjudicated fairly; no instant confession dump. |
| “I study those tiny figures in the carving while they argue.” | The player used the argument as cover for curiosity. Kit can reward attention without breaking the social tension. | Discovery feels earned and satisfying. The key's purpose and the bandits' ignorance remain intact. |
| “I could help you get rid of Harria. What is that worth?” | The player touched the level's leadership fracture. Kit wants to see how far the dangerous bargain might go. | Uktarl tests the offer in character. The possibility is exciting; the outcome stays open. |
| “I tip the stone tub over and use it as cover.” | A ridiculous, inventive tactic may delight Kit. The fixed tub gives her a chance to react directly and still rule seriously. | Kit comments on the audacity, then offers what the physical space actually permits: the tub cannot tip, but its recess may still be useful. The player feels laughed with and taken seriously. |
| “I attack Uktarl in the middle of the game.” | The social scene became dangerous. Kit should want the opposition to earn respect and the retreat to change what happens next. | Humor recedes, tactics and morale come forward, and the fight has consequences beyond hit point loss. |

## Evaluation record

For each run, retain the seed version, character sheet, exact player inputs, causal traces, expressed turns, accepted rulings/events, and state after the scene. Score each dimension from 0–2 with a concrete moment from the player-facing transcript:

1. **Table presence:** Kit's narration, NPC acting, rulings, and direct comments felt like one identifiable DM at the table.
2. **Personhood:** She showed preferences, event-linked reactions, memory, and the ability to change her mind; these were visible through choices rather than merely asserted in a private trace.
3. **Entertainment:** The scene made the player want another turn; tension, humor, surprise, and payoff arrived when earned.
4. **Tonal range:** She could be funny, quirky, threatening, warm, or quiet as the moment called for, without forcing each quality into every turn.
5. **Embodiment:** Uktarl and the others behaved as distinct people rather than mouths for Kit's jokes or exposition.
6. **Adaptation:** Kit visibly appreciated or responded to unexpected play, then gave the attempt real consequences.

Source, map, rule, secrecy, and continuity violations invalidate a run for this test. Passing those checks does not establish that Kit has a compelling personality.

Also record an overall paired preference between two complete runs: which Kit would the player choose to keep playing with, and why? Ask what moment made her feel like a particular DM, and what moment felt generic or artificial. Preserve rejected examples for later personality tuning. A beat tag such as `humor` says a joke occurred; it does not say the joke worked.

## Current runtime boundary

The fixture can initialize the existing SQLite state/context prototype. That prototype exposes player-visible facts, protects the hidden facts in its structured view, commits a limited set of already-adjudicated events, and saves them. It cannot yet appraise events for Kit, maintain her autobiographical and affective state, select a DM move, express her table voice, apply full D&D rules, move fleeing actors into adjoining areas, handle treasure transfers, or score entertainment. The next playable adapter needs a concise causal trace for evaluation, kept private from the player, and an expressed response whose quality can be judged independently of that trace. It also needs relevant level, player, and recent-rhythm context; this room fixture by itself cannot support the full personality test.

Run the seed from the repository root with:

```sh
python -m runtime.state_context init --db /tmp/kit-06c.sqlite --fixture tests/fixtures/level_01_area_06c.json
python -m runtime.state_context context --db /tmp/kit-06c.sqlite
python -m runtime.state_context view --db /tmp/kit-06c.sqlite
```
