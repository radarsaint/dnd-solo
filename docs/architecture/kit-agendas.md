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
- **Pacing.** Something moves when it should, not every turn by force. `every: N` (default 1)
  says an advance is due once N turns pass without one; `pace: {area: N}` makes a calmer room.
  `must_advance` in `agenda_here` says when an advance is due. When it is not due, a **quiet** turn
  is valid even with agents present, as long as the decision's `hold.why` says why nothing
  advances this turn.
- **prepare.** `agenda_here` lists each present agent: its presence, disposition, want,
  available moves, moves blocked by knower bands, and turns since it last acted. It also lists
  the clocks, turns since the last advance, and `must_advance`.
- **decide.** `agenda {advances, ticks, hold}` is required whenever `agenda_here` is present. An
  advance is a declared move id, or `new` with roots (same root rules as new claims). A hold is
  `engaged` (the player is dealing with that onstage agent now, and the exchange is its advance),
  `quiet` (nothing advances, for the stated reason), `paced` (the same, named for the pace), or
  `none`. When `must_advance` is true and nothing advanced, only `engaged` passes: a quiet hold is
  rejected only when an advance is overdue. With agents present, a quiet `why` needs at least four
  words. A full clock cannot tick.
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
- **State.** `held`, `equipped`, and `active` say what is true now. They are not a sheet default:
  absent means not yet established, and unknown is never true. The decision's `pc_state` (or the CLI,
  `character --held "<item>"`) commits a `pc_state` event.
- **Passives.** A passive gets +5 only while its condition is true.
- **Example (one sheet, not a rule).** A sheet whose item grants advantage on Perception only while
  held sets no held state; its passive Perception stays at 10 + bonus until the item is established
  as held, then gains +5. (Nik's sheet is one such case: 14, then 19.)
- **Decide.** `roll_call {skill, mode, cause {kind, ref, roots}}`. Advantage or disadvantage
  needs an item held or equipped, an active spell or condition, a sheet feature, or a position
  rooted in scene facts.
- **Performance.** When the performance calls a roll with advantage or disadvantage, the plan's
  `roll_call` must match it and the text must name the cause.

## The PC's state follows the situation

- **Situation, then the player's word.** Seated at a table or talking: hands free, a carried item
  slung or stowed unless the player says it is in hand. A fight or on guard: a weapon or focus in hand. The player's declared state always
  wins. When the fiction changes it, the decision records the whole picture in
  `pc_state {held, equipped, active, why}`. It counts for that turn's `roll_call` and commits with the
  turn.
- **Odd is a scene event, not a correction.** A declared state that is odd for the situation (a held item
  kept up at a friendly table, a blade drawn at dinner, a focus in hand for a handshake) stands, with its
  advantage when it is really met. The people present notice and react from their wants:
  `pc_oddity {what, noticed_by, reaction}`. `noticed_by` names actors present here. The reaction
  reaches the performer through `npc_notice` (`gear:` or `stunt:`). An agenda agent whose actor
  noticed counts as having acted this turn, and a move with `trigger: odd` fires only with a
  `pc_oddity`.
- **Ask only when unknown.** When the state is genuinely unknown and it matters, Kit asks:
  `ask_player {about, question}`, with one short plain question, `ask_clarification`, and call scope.
  It is rejected when the item is already in force (known, even if odd). The turn resolves nothing. It
  commits only the public question and an `asked` rhythm beat: no adjudicated events, claims, canon,
  agenda turn, or `pc_state`. The host prepares the original action again with the answer.

## Natural routing

- **Table talk.** `is_ooc` still recognizes the old markers. It also recognizes a message
  addressed to Kit by name, and a question that names rules nouns (DC, advantage, bonus action,
  saving throw, etc.; in-world verbs like sneak do not count). Quoted speech never counts.
- **Missing apostrophes.** Detail questions accept a missing apostrophe ("Whats the game?").
