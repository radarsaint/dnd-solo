# Agendas, backgrounded activities, salience, conditioned advantage

Code: `runtime/kit_agenda.py` (plus small hooks in `runtime/kit_agent.py`, `runtime/pc_sheet.py`,
`runtime/state_context.py`). Tests: `tests/test_kit_agenda.py`. Why: playtest 04
(`tests/playtests/2026-09-29-area-06c-claims-nik.md`). The room had a point, but the point never
showed. Everything here is general. Nothing is keyed to a room or a PC.

## Agenda engine

This is Dungeon World fronts and GM moves plus Blades in the Dark clocks, built as one mechanism.
An **agent** is anything that wants something: an `npc`, a `monster`, a `faction`, the
`environment`, or a `clock`. The source declares one top-level `agenda` block (the schema is in
the module docstring), and it is validated when the session initializes.

- **Agents.** Each agent has `wants` (what it wants from the PC specifically), `roots`, and
  `moves`. Each move has `does`, `roots`, a `trigger` (stall, elsewhere, engaged, or any),
  optional `needs` (claim ids), and an optional `ticks` (a pressure). An agent tied to an `actor`
  is onstage wherever that actor is, unless the actor is fled or dead. With `areas`, an agent
  acts on those areas from offstage: an absent lair owner, a wandering threat, or a faction that
  spans rooms (`"*"`). Hazards, decay, and traps are `environment` agents.
- **Pressures.** Each pressure is a clock with `segments`, `ticks_on`, `when_full`, `roots`, and
  `areas`.
- **Pacing.** The default `every: 1` means something advances every turn. `pace: {area: N}`
  makes a calmer room. A room with nothing live is **quiet**, and that is valid. The rule is that
  something moves when it should, not that drama is forced.
- **prepare.** `agenda_here` lists each present agent: its presence, disposition, want,
  available moves, moves blocked by knower bands, and turns since it last acted. It also lists
  the clocks, turns since the last advance, and `must_advance`.
- **decide.** `agenda {advances, ticks, hold}` is required whenever `agenda_here` is present. An
  advance is a declared move id, or `new` with roots (same root rules as new claims). A hold is
  `engaged` (the player is dealing with that onstage agent now, and the exchange is its advance),
  `quiet`, `paced`, or `none`. When `must_advance` is true and nothing advanced, only `engaged`
  passes. A full clock cannot tick.
- **Knowers.** If a move's `needs` or roots touch a claim, or the fact behind a claim, that the
  agent's actor is `unaware` of, the move is blocked in prepare and rejected in decide.
- **finish.** An `agenda_turn` event persists the turn count, `last_acted` for each agent
  (including an engaged hold), clock fills, and `last_advance` in `state['agenda']`. This state
  is session-wide, so a faction's clock carries across areas and a revisited room remembers.

## Backgroundable activities

Before this change, "I look around the room" hit no route. Now looking around, looking elsewhere,
or asking "what else" routes to `observe`. At the card table this takes precedence over card
parsing unless the player is watching the deal. Whenever a card procedure exists and this turn
is not a card action, the private input carries `activities: {id: backgrounded...}`. The
procedure's state is kept. Kit does not remind the player, prompt a choice, or choose for them,
and the activity resumes when the player acts in it again.

## Salience

`salience: [{thing, reason, roots}]`. When the performance says something catches the eye, draws
attention, or stands out, salience must be present. Its reason must be a concrete detail of at
least four words. Its roots must be observable: a visible fact in this area, a known fact, a
present actor, canon, or an established claim. A root that is still a secret is rejected.

## Advantage needs a present reason

- **Sheet.** `advantage_on` entries may be conditional: `{skill, source, while: held|equipped|active}`.
- **State.** `held`, `equipped`, and `active` say what is true now. A `pc_state` event (CLI
  `character --held "Sentinel Shield"`, `--active "..."`) changes them.
- **Passives.** A passive gets +5 only while its condition is true.
- **Nik.** Nik's sheet now holds nothing by default, so passive Perception is 14. Holding the
  Sentinel Shield makes it 19.
- **Decide.** `roll_call {skill, mode, cause {kind, ref, roots}}`. Advantage or disadvantage
  needs an item held or equipped, an active spell or condition, a sheet feature, or a position
  rooted in scene facts.
- **Performance.** When the performance calls a roll with advantage or disadvantage, the plan's
  `roll_call` must match it and the text must name the cause.

## Natural routing

- **Table talk.** `is_ooc` still recognizes the old markers. It also recognizes a message
  addressed to Kit by name, and a question that names rules nouns (DC, advantage, bonus action,
  saving throw, etc.; in-world verbs like sneak do not count). Quoted speech never counts.
- **Missing apostrophes.** Detail questions accept a missing apostrophe ("Whats the game?").
