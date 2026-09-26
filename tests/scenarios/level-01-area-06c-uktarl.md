# Kit test room: Level 1, area 6c — Uktarl's room

## Purpose

Use one repeatable scene to test Kit's choices as a DM: NPC initiative, social play, grounded humor, hidden information, fair danger, creative action, and continuity after a surprising turn. This is a conditional room snapshot, not a replacement for the published encounter.

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

The existing tests establish that the player view hides private facts and an accepted reveal persists. They do not compare prose to the book, execute D&D rules, or measure whether Kit is entertaining. That requires transcripts from the six probes below, checked against the source and scored by a player.

## Six probes from the same seed

Start a fresh copy of the seed for each probe. Continue for several turns before scoring; a strong opening line alone is insufficient.

| Player move | What Kit should decide and show | Failure to catch |
| --- | --- | --- |
| “I pull up a chair and ask what the stakes are.” | Uktarl pursues an advantage through the game or conversation. The other three react according to their limited roles. Kit makes the encounter playable without forcing a fight. | Generic exposition, identical voices, or automatic trust. |
| “I call out the dealer's marked cards.” | Decide what the character could have observed and whether a check is needed. Uktarl responds as an exposed cheat who still has allies and a front to maintain. | Treating accusation as proof, or having everyone disclose the whole fraud. |
| “I study those tiny figures in the carving while they argue.” | Resolve attention, position, and the DC 13 discovery. If successful, reveal the key; the bandits still do not suddenly know its purpose. | Giving away the key on room entry or making Uktarl explain it. |
| “I could help you get rid of Harria. What is that worth?” | Let Uktarl evaluate a dangerous offer in light of his rivalry and cowardice. His answer creates a playable bargain or test of trust. | A quest dispenser speech or instant sincere alliance. |
| “I tip the stone tub over and use it as cover.” | Check the tub's actual recessed construction and dimensions before ruling. Offer what the physical setup permits, then let opponents respond. | Inventing a movable barricade or rejecting the idea without considering it. |
| “I attack Uktarl in the middle of the game.” | Apply initiative and combat rules, let the other occupants act, and honor Uktarl's source retreat trigger when it fires. Preserve the changed actor states. | A static fight, an unearned surprise round, or Uktarl fighting to the death for dramatic effect. |

## Evaluation record

For each run, retain the seed version, character sheet, exact player inputs, Kit's proposed DM moves, accepted rulings/events, player-facing turns, and state after the scene. Score each dimension from 0–2 with a concrete example:

1. **DM judgment:** Kit chose a consequential move that fit the room and sustained play.
2. **Embodiment:** Uktarl's choices had a distinct motive; the other actors did not inherit Kit's table voice.
3. **Truth and fairness:** clues, geometry, danger, checks, and retreat followed source and established state.
4. **Adaptation:** a clever or disruptive player action changed the scene without erasing consequences.
5. **Entertainment:** timing, tension, humor, and payoff made the next decision worth taking.
6. **Continuity:** what was learned, spent, taken, promised, or changed survived the next turn.

Also record an overall paired preference between two complete runs: which Kit would the player choose to keep playing with, and why? Preserve rejected examples for later personality tuning. A beat tag such as `humor` says a joke occurred; it does not say the joke worked.

## Current runtime boundary

The fixture can initialize the existing SQLite state/context prototype. That prototype exposes player-visible facts, protects the hidden facts in its structured view, commits a limited set of already-adjudicated events, and saves them. It cannot yet run dialogue, choose a DM move, apply full D&D rules, move fleeing actors into adjoining areas, handle treasure transfers, or score entertainment. These probes are the contract for the next playable model adapter and adjudicator.

Run the seed from the repository root with:

```sh
python -m runtime.state_context init --db /tmp/kit-06c.sqlite --fixture tests/fixtures/level_01_area_06c.json
python -m runtime.state_context context --db /tmp/kit-06c.sqlite
python -m runtime.state_context view --db /tmp/kit-06c.sqlite
```
