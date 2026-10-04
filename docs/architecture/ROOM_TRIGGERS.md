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
| `on` | exactly one of `{"disturb": <fact id>}` (the PC moves, searches, or gets into that handled feature: prod, poke, kick, roll, search...; or puts hands on one of its `handling.parts` or takes what it `holds`: "I pry the claw open", "I take the orb from the claw") or `{"enter": <area id>}` (the PC arrives there) |
| `starts_combat` | default `true`: the fight starts awaiting initiative, no player attack needed |
| `actors` | who it wakes. Give them `"status": "hidden", "visible": false`: until it fires they are in dm_only only (not in present actors, speakers, the approach view, the brief, claims, discernment or the player view) and cannot be targeted |
| `surprise` | optional. `{"stealth": N}` (each actor rolls d20 + N; `null` uses the stat block's `stealth`) or `{"dc": N}` (one flat number). SRD: the PC is surprised only if his passive Perception is below every total; a surprised PC loses his round-one turn. The ambushers are never surprised. Omit for no surprise. |
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

## Parts and held items

A handled feature may list `parts` (words that name it too: a carcass's claw, a coffin's lid) and
`holds` (a fact inside or on it: the claw's orb). Prying, wrenching, pulling, lifting, taking...
a part or the held item resolves as `handle_feature` on the owning feature: its `handling.handle`
line (else `move`, else `look`), the held fact comes into view, and the feature's `disturb`
trigger fires. Looking at a part disturbs nothing. A scene's own loot (a card table's coins and
ring) is never taken from a feature the room keys.
