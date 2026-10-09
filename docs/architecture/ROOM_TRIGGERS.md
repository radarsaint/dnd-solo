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

The engine does not read intent out of English to change the world. On ANY non-OOC physical
turn (not a question, not speech, not table talk) in an area where a pending disturb trigger
watches a feature the PC has found, the turn carries an offer, and Kit's decision says whether
his hands go on it. Kit resolves pronouns and synonyms ("I push it open", "I heave the stone
slab aside"); no noun has to match.

```json
"acts": {"handles": {"targets": {"sarcophagus": ["lid", "seal"]}, "hint": {"target": "lid", "act": "move"}}}
```

- `targets`: each watched, found feature here, with its parts (and what it holds, once the PC
  has seen it: an unseen orb is no handle). A hidden feature (a trapdoor nobody has found) is
  not offered, not shown outside `dm_only`, and cannot fire; it becomes found when the PC
  legitimately discovers it (a search or check that reveals it, its own reveal). `hint`
  (optional) is a regex's guess at a hands-on act. It only hints: it never gates the offer,
  fires a trigger or reveals anything.
- When an offer exists the decision MUST answer it: `"handles": {"target": <feature, part or
  held id>, "act": <take|pry|lift|move|push|roll|pull|break|cut|stab|kick|climb|enter|open|
  search|hook|touch|other>}`, or `{"target": "none", "act": "none"}` (a look, a step toward it,
  cover behind it). Looking or examining is not disturbing unless the PC physically manipulates
  something. An omitted answer, a declaration naming anything not offered, or one on an
  `ask_player` turn is rejected.
- A performance that names or describes a hidden actor (its name, its SRD creature, words of
  its reveal) is rejected unless this turn's declaration fires that actor's trigger: no "a grey
  ghoul lunges out" without a `handles` that opens the sarcophagus.
- The engine resolves a valid declaration at commit, on the state after the turn's events: the
  feature's `enter` line (climb, enter), `look` line (search, open), `move` line (move, push,
  roll, lift, kick the whole feature), else its `handle` line; what it holds comes into view; its
  trigger fires. The outcome is read after Kit's performance (`Narrator: ... Roll initiative.`),
  so a fight it starts ends the turn on the roll call. The record keeps `declared`.
- Mid-fight, handling a feature costs the PC's action (or his free object interaction for a
  simple open/take/pull, per SRD).
- The router picks the feature the words name first (longest name on a tie), not file order:
  "I look inside the chest beside the sarcophagus" is the chest.
- `handles` and `downed` (below) share one shape: an offer, a required answer, one validator in
  `kit_acts.FIELDS`. #101's `react` uses it too.

## Parts and held items

A handled feature may list `parts` (words that name it too: a carcass's claw, a coffin's lid) and
`holds` (a fact inside or on it: the claw's orb). Kit's `handles` on a part or the held item is
handling the owning feature. Looking at a part disturbs nothing. Coins and a ring lying about to
be taken exist only in a room whose combat block keys table loot (`loose_money`); `room_now` is
shown only there.

## The PC who cannot act

At 0 hit points, or with an incapacitating condition (incapacitated, paralyzed, petrified,
stunned, unconscious), in-fiction acts are refused, but the session never freezes:

- He still reports rolls. The engine never rolls for the PC. At the start of each of his turns
  at 0 HP the round stops on "Roll a death saving throw." He rolls in Avrae and reports it: 10+
  succeeds, 3 successes stabilize, 3 failures kill, a natural 20 regains 1 HP, a natural 1 is two
  failures. Damage at 0 HP is a failure (two on a crit); damage at 0 HP that meets his max HP is
  death (SRD massive damage, also on the hit that drops him).
- Healing from an ally, an effect or a potion revives him (`unconscious` ends, death saves reset).
- Monsters keep acting. Before a monster's turn against a downed PC the turn carries a `downed`
  offer; Kit answers `{"downed": {"<foe id>": "attack" | "turn_away"}}` (required). Attacks on a
  paralyzed or unconscious PC have advantage and a hit within 5 ft is a crit.
- Conditions carry their SRD terms (`state.pc_condition_terms`: a duration in seconds and/or a
  repeat save at the end of his turn, e.g. a ghoul's paralysis: Con DC 10, one minute). The
  player rolls repeat saves and reports them; conditions expire with time (rounds in a fight,
  `advance_time` outside one). Every change is a `pc_conditions` event. Conditions are the PC's
  (a session key that travels between rooms), not the fight's.
- A surprised PC has no reaction until his first turn ends (`Fight.pc_can_react`).

## Ties

One rule, Brendon's: when a creature acts on another, the actor meets or beats.
`kit_rolls.meets_or_beats(actor_total, target)` for attack vs AC, a check vs a passive score,
Stealth vs passive Perception (both ways, surprise included). `kit_rolls.attacker_wins(dc,
save_total)` (`dc >= save_total`) for every save: a save that ties the DC fails, the PC's and a
monster's alike (a house rule over 5e). Death saves have no attacker: 10 or more succeeds.

## Save riders, more

Every rider that hits in a turn is asked, one at a time (`saves_queued`). `Con: 14`, `Con save 14`
and `Constitution 14` all answer a Constitution roll call. Anything declared after the save
(`Con save 14, then I cast magic missile`) is kept (`declared_next`) and taken on his turn.
The rider's source is `from` (or `attacker`, #101's name; `kit_combat.attacker` reads both).
A creature that joins a running fight takes its initiative count in the order.

