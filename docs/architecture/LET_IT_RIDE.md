# Let It Ride, and no silent PC rolls

Rebuilt on main from #103's spec. Code: `runtime/kit_agent.py` (`RollNeeded`, `_call_roll`,
`_resolve_stealth`, `_stealth_change`) and `runtime/state_context.py` (`standing_check`).

## Standing result

`state['standing_check']` is `{skill, total, die, modifier, area, route, against: {watchers, dc}, approach, since}`.

- **Set by:** a successful stated Stealth roll, or a successful Stealth roll that Kit called.
- **Cleared by:** a `move`, a failed roll, or the PC turning to something else. Something else
  means any result kind outside `STANDING_KEEPS`, such as speech, a fight or a bet.
- **Continuing the same endeavor:** the total stands. No die is rolled, and the evidence says
  "stands … let it ride".
- **A material change calls a new roll, and the player rolls it.** Material changes are:
  - a new observer (an actor who is asleep, unconscious or otherwise unable does not watch);
  - a new area;
  - a different approach (`DIFFERENT_APPROACH`: run, sprint, rush, loudly, openly…);
  - a complication (a fight starts, or the number to beat rises).
- **Kit sees it:** `planning_input.standing_check` and one first-try line.

## The engine never rolls a PC's check

`_die` and `_resolve_knowledge` take the player's stated roll, or else the host's pinned die
(tests, replays). With neither, they raise `RollNeeded`. `resolve()` then turns it into a
`check_called` turn:
- The public line is "Roll <Skill> for it.".
- The `pending_check` carries the act in `action`.
- The player's roll re-resolves that act.

Ties are unchanged: meet-or-beat.

## Audit of hash-seeded d20s

- **PC check, now called:** `_die` (stealth, social, claim and lie checks, grab and take, exit
  contests, called checks, toll haggling) and `_resolve_knowledge`.
- **Still open, not changed:** the card procedures `kit_cards._player_roll` and
  `kit_twenty_one._roll`.
- **NPC dice, which are fine:**
  - `kit_combat.Fight.die` (NPC attacks and saves, companions);
  - `kit_attitude.npc_die`;
  - `kit_triggers.surprise_roll` (an ambusher's roll).
