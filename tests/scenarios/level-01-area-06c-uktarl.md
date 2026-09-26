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

## Personality test: Kit's attention and appetite

For each consequential turn, record a compact **DM intent card** before Kit's player-facing response. It is a high-level decision record, not a transcript of private reasoning and not dialogue to show the player:

- **Noticed:** Which player choice or scene change caught her attention? Which of the room, people, neighborhood, level, campaign, or table layers matters now?
- **Cares about:** What experience does she want the player to have next? What surprised or amused her? What might she hope the player tries, without steering them into it? What relationship, danger, joke, discovery, or future payoff interests her?
- **Chosen move:** What will an NPC, the environment, or Kit at the table do? Why this moment? What will she leave open for the player?
- **Presence:** Will her own voice surface, or will she express herself through pacing, NPC behavior, adjudication, and restraint?

Keep each card brief and specific. A claim like “I want to be funny” is useless without an actual choice that earns a laugh. After the turn, compare the card with the response: did her interest produce an observable, fitting move, or did the output flatten into generic narration? Score the player-facing transcript first, without showing the evaluator the cards, then inspect the cards to diagnose the choices. Do not use a fixed script or a required punchline as the target.

For example, if the player pulls up a chair: Kit notices that they chose to socialize with apparent predators. She is amused and wants to see whether they catch Uktarl cheating. She chooses to let him make the invitation attractive while one companion watches the player's hands. She stays behind the NPCs for now. This is a possible intent, not a prescribed line or outcome; a good run must earn its own moment.

## Six personality probes from the same seed

Start a fresh copy of the seed for each probe. Continue for several turns before scoring; a strong opening line alone is insufficient.

| Player move | What should catch Kit's interest | What should come through to the player |
| --- | --- | --- |
| “I pull up a chair and ask what the stakes are.” | The player volunteered to roleplay with predators. Kit can enjoy the social opening and let Uktarl try to charm and fleece them. | A tempting, funny or unnerving invitation with room for a real decision; Kit's humor does not make all four NPCs sound alike. |
| “I call out the dealer's marked cards.” | The player may have caught her setup. Kit should enjoy that, then consider Uktarl's pride, allies, and need to save face. | A consequential reaction from a person under pressure, with proof and uncertainty adjudicated fairly; no instant confession dump. |
| “I study those tiny figures in the carving while they argue.” | The player used the argument as cover for curiosity. Kit can reward attention without breaking the social tension. | Discovery feels earned and satisfying. The key's purpose and the bandits' ignorance remain intact. |
| “I could help you get rid of Harria. What is that worth?” | The player touched the level's leadership fracture. Kit wants to see how far the dangerous bargain might go. | Uktarl tests the offer in character. The possibility is exciting; the outcome stays open. |
| “I tip the stone tub over and use it as cover.” | A ridiculous, inventive tactic may delight Kit. The fixed tub gives her a chance to react and still rule seriously. | The player feels laughed with and taken seriously: the tub cannot tip, but its recess may still be useful in a physically honest way. |
| “I attack Uktarl in the middle of the game.” | The social scene became dangerous. Kit should want the opposition to earn respect and the retreat to change what happens next. | Humor recedes, tactics and morale come forward, and the fight has consequences beyond hit point loss. |

## Evaluation record

For each run, retain the seed version, character sheet, exact player inputs, intent cards, accepted rulings/events, player-facing turns, and state after the scene. Score each dimension from 0–2 with a concrete moment from the transcript:

1. **Recognizable Kit:** Her interests and taste emerged through decisions and timing, even when she did not speak in her own table voice.
2. **Entertainment:** The scene made the player want another turn; tension, humor, surprise, and payoff arrived when earned.
3. **Tonal range:** She could be funny, quirky, threatening, or quiet as the moment called for, without forcing each quality into every turn.
4. **Embodiment:** Uktarl and the others behaved as distinct people rather than mouths for Kit's jokes or exposition.
5. **Adaptation:** Kit visibly appreciated or responded to unexpected play, then gave the attempt real consequences.
6. **Judgment and continuity:** Her choices remained fair to the source, map, player knowledge, and accepted changes, and opened an interesting next decision.

Also record an overall paired preference between two complete runs: which Kit would the player choose to keep playing with, and why? Ask what moment made her feel like a particular DM, and what moment felt generic or artificial. Preserve rejected examples for later personality tuning. A beat tag such as `humor` says a joke occurred; it does not say the joke worked.

## Current runtime boundary

The fixture can initialize the existing SQLite state/context prototype. That prototype exposes player-visible facts, protects the hidden facts in its structured view, commits a limited set of already-adjudicated events, and saves them. It cannot yet form an intent card, choose a DM move, generate dialogue, apply full D&D rules, move fleeing actors into adjoining areas, handle treasure transfers, or score entertainment. The next playable adapter must expose Kit's selected intent for evaluation, keep it private from the player, and produce a response whose quality can be judged independently of her self-description. It also needs relevant level, player, and recent-rhythm context; this room fixture by itself cannot support the full personality test.

Run the seed from the repository root with:

```sh
python -m runtime.state_context init --db /tmp/kit-06c.sqlite --fixture tests/fixtures/level_01_area_06c.json
python -m runtime.state_context context --db /tmp/kit-06c.sqlite
python -m runtime.state_context view --db /tmp/kit-06c.sqlite
```
