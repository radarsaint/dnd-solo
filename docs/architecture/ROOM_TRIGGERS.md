# Room triggers: monster-initiated combat (PR-M)

Until now only a player attack (or 6c's theft) started a fight. A room file can now say what
wakes something up, as data only (`runtime/kit_triggers.py`, checked at mount).

```json
"actors": {
  "centipede_a": {"name": "Banded centipede", "location": "hall", "status": "hidden", "visible": false,
                  "stat_block": {"srd": "Giant Centipede"}, "...": "..."}
},
"triggers": [
  {"id": "carcass_disturbed",
   "on": {"disturb": "carcass"},
   "starts_combat": true,
   "actors": ["centipede_a", "centipede_b"],
   "surprise": {"stealth": 2},
   "reveal": "Two giant centipedes boil out from under the carcass, mandibles clicking."}
]
```

| field | meaning |
|---|---|
| `id` | unique name; a trigger fires once (`state.triggers_fired`) |
| `on` | exactly one of `{"disturb": <fact id>}` (Kit declares `handles` on that feature, one of its `handling.parts`, or what it `holds`: see "Declared acts" below) or `{"enter": <area id>}` (the PC arrives there, or takes his first turn there after starting there or arriving by room_link) |
| `starts_combat` | default `true`: the fight starts awaiting initiative, no player attack needed |
| `actors` | who it wakes. They must be `"status": "hidden", "visible": false` (the mount refuses hidden with visible true, a hidden actor no trigger wakes, and a doorway tease whose `heard` names a hidden actor): until it fires they are in dm_only only (not in present actors, speakers, the approach view, the brief, claims, discernment or the player view) and cannot be targeted |
| `surprise` | optional. `{"stealth": N}` (each actor rolls d20 + N; `null` uses the stat block's `stealth`) or `{"dc": N}` (one flat number). SRD: the PC is surprised only if every total meets or beats his passive Perception (the actor wins ties, `kit_rolls.meets_or_beats`); a surprised PC loses his round-one turn. The ambushers are never surprised. Omit for no surprise. |
| `reveal` | the public line read when they show themselves, before "Roll initiative." |

Firing commits `trigger_fired` (hidden -> alive and visible) plus the fight's `combat_state`.
A trigger that fires during a running fight adds its actors to the order. The resolution
carries `handoff` (`kit_triggers.handoff_trace`), a telemetry seam for the per-turn handoff log.

## Save riders on monster attacks

A stat-block attack may carry `"save": {"ability", "dc", "damage", "type", "half", "at_zero"}`
(SRD Giant Centipede: Con DC 11, 10 poison, no damage on a success, poisoned and paralyzed if it
drops the target to 0). On a hit the round stops at a roll call (`combat.awaiting`:
`{"kind": "roll_call", "awaits": "player_roll", "save": "con", ...}`) and the public line asks
"Roll a Constitution saving throw." (never the DC). The player rolls in Avrae; the next message's
save total (Avrae output, "Con save 14", "Constitution saving throw: 9", or a bare number)
resolves it and the round goes on. Anything else is held with a pending ruling until he rolls.
PR-H's typed interstitials can lift `awaiting` into a roll_call interstitial unchanged.

## Declared acts (`runtime/kit_acts.py`)

The engine does not read intent out of English to change the world. When the player's words
name a feature a pending disturb trigger watches, the turn carries an offer, and Kit's decision
says whether his hands go on it:

```json
"acts": {"handles": {"targets": {"carcass": ["claw", "talon", "foreleg"]}, "hint": {"target": "claw", "act": "pry"}}}
```

- `targets`: each watched feature here, with its parts (and what it holds, once the PC has seen
  it: an unseen orb is no handle). `hint` (optional) is a regex's guess at a hands-on act on the
  verb's own object. It only helps Kit confirm; it never fires a trigger or reveals anything.
- The decision may add `"handles": {"target": <feature, part or held id>, "act": <take|pry|lift|
  move|push|roll|pull|break|cut|stab|kick|climb|enter|open|search|hook|touch|other>}`. Omitted
  (or `none`) means no handling: a look, a step toward it, cover behind it, a question. A
  declaration naming anything not offered is rejected; so is one on an `ask_player` turn.
- The engine resolves a valid declaration at commit, on the state after the turn's events: the
  feature's `enter` line (climb, enter), `look` line (search, open), `move` line (move, push,
  roll, lift, kick the whole feature), else its `handle` line; what it holds comes into view; its
  trigger fires. The outcome is read after Kit's performance (`Narrator: ... Roll initiative.`),
  so a fight it starts ends the turn on the roll call. The record keeps `declared`, and the
  turn's timing keeps the `handoff` trace.
- A move, look-into or get-into that the router reads off the words on a watched feature
  commits nothing itself: the turn is `feature_act`, Kit's call (never a routine turn). A line
  the engine would have refused (`climb onto the carcass`) becomes Kit's call too.
- `handles` is the first of a family: each act field has an offer, an optional declaration and
  one validator in `kit_acts.FIELDS`, so a later field (#101's `react`) uses the same shape.

## Parts and held items

A handled feature may list `parts` (words that name it too: a carcass's claw, a coffin's lid) and
`holds` (a fact inside or on it: the claw's orb). Kit's `handles` on a part or the held item is
handling the owning feature. Looking at a part disturbs nothing. Coins and a ring lying about to
be taken exist only in a room whose combat block keys table loot (`loose_money`); `room_now` is
shown only there.

## The PC who cannot act

At 0 hit points in a running fight, or with an incapacitating condition (incapacitated,
paralyzed, petrified, stunned, unconscious), every in-fiction line is a pending ruling: he
cannot move, act or speak. Conditions are the PC's (`state.pc_conditions`, a session key that
travels between rooms), not the fight's: they outlast it until a `pc_conditions` event sets
the list when one ends by rule (healing, an hour of poison). A surprised PC has no reaction
until his first turn ends (`Fight.pc_can_react`, `fight.you_are_surprised` in the view).

## Save riders, more

Every rider that hits in a turn is asked, one at a time (`saves_queued`). `Con: 14`, `Con save 14`
and `Constitution 14` all answer a Constitution roll call. Anything declared after the save
(`Con save 14, then I cast magic missile`) is kept (`declared_next`) and taken on his turn.
The rider's source is `from` (or `attacker`, #101's name; `kit_combat.attacker` reads both).
A creature that joins a running fight takes its initiative count in the order.

