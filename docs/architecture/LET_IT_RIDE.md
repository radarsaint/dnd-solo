# Let It Ride and no silent PC rolls (PR-L)

## The rule
Players roll their own checks in Avrae. The engine never rolls a PC's d20. Kit rolls only
for NPCs, behind the screen.

An established check result **stands** while the PC keeps at the same endeavor. It is
re-rolled only when circumstances change materially:

| Change | Example | What happens |
|---|---|---|
| New observers | a sleeping guard wakes; someone walks in | a fresh roll is called |
| New area | the PC moves through an exit | the standing result ends (cleared on `move`) |
| Different approach | "I sprint along the wall" | a fresh roll is called |
| Complication | a fight starts; the number to beat rises | a fresh roll is called |
| The PC turns to something else | speaks up, attacks, bets, pays a toll | the standing result ends |
| The roll fails | Stealth 9 against passive 10 | nothing stands |

## State
`state['standing_check']` holds `{skill, total, die, modifier, area, route, against: {watchers, dc}, approach, since}`.
It is set and cleared with the `standing_check` event (`check: null` clears it). Today Stealth
is the only skill that writes one: a successful stated Stealth roll, or a Stealth roll Kit called.
The `against` field records the watchers who were present and able to perceive (asleep and
unconscious actors don't watch) and the passive Perception they set.

Kit sees the result in `planning_input.standing_check` (skill, total, area, against, since,
plus a "let it ride" rule) and in one first-try line. She must not call the check again.

## Called, never rolled
When an act needs the PC's roll and none was stated, `RoomAdjudicator._die` raises
`RollNeeded`, and `resolve` returns a `check_called` turn:
- public text: `Roll <Skill> for it.`, prefixed by the change if a standing result just ended
- a `check_called` beat
- a `pending_check` that keeps the act in `action`

The player's roll on the next turn re-resolves that act with the roll attached (kit_agent
`_resolve_called`). A host-pinned die (`RoomAdjudicator(roll=...)`, used by tests and the replay)
still stands in for the player's stated roll. This PR adds no tie logic; meet-or-beat
comparisons are unchanged.

## Audit of silent PC rolls (2026-10-04, main 0bce3ad)
Fixed here. Each of these used a hash-seeded d20 for the PC when no roll was stated, and now calls the check instead:
- `RoomAdjudicator._die` fallback, which served stealth, social checks (Deception, Persuasion,
  Intimidation, Performance, Athletics), claim and lie checks (`_check`, `_resolve_check`),
  combat grab and take checks, exit contests, Kit-called checks, and toll haggling
- `RoomAdjudicator._resolve_knowledge` (History, Arcana and other knowledge rolls)

Still open, reported but not changed, because they belong to card procedures with their own
supplied-roll handling:
- `kit_cards` `_player_roll` (card swap and sleight checks) falls back to `_d20`
- `kit_twenty_one` `_roll` (watch and round checks) falls back to `kit_cards._d20`

Fine as they are: NPC-only dice (`kit_combat.Fight.die` for NPC attacks and NPC saves,
`kit_attitude.npc_die`), the card shuffle RNG, and the texture RNG.
`tests/test_kit_let_it_ride.py::NoSilentPcRolls` pins this list statically.
