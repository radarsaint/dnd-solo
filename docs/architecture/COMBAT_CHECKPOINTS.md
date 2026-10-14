# Combat checkpoints, interstitials, progressive reveal, and the handoff trace (PR-H)

The engine stops where the player owns the next input, records what it waits on in
`combat.awaiting = {kind, awaits, deferred_action_id, trigger, ...}` (the names PR-M's save
rider uses), commits the turn, and resumes exactly there when the answer comes.

## Engine checkpoints (`runtime/kit_combat.py`)
| kind | trigger | awaits | resumes with |
|---|---|---|---|
| `reaction_window` | `hit`: an NPC hit the PC and a reaction he has could change it (Shield: the hit does not meet AC + 5, never a natural 20, or a magic missile; Absorb Elements: elemental damage; Chronal Shift, Silvery Barbs, Uncanny Dodge: any hit) | `player_answer` | Kit's `react` read (below) |
| `reaction_window` | `npc_spell`: an NPC attack marked `"spell": true` is cast (Counterspell, Mage Slayer) | `player_answer` | `react`; Counterspell stops a spell of level 3 or lower, anything else Kit adjudicates |
| `reaction_window` | `npc_save`: an NPC made its save against the PC's spell (Silvery Barbs, Chronal Shift) | `player_answer` | `react`; the reroll is pinned dice |
| `reaction_window` | `leaves_reach`: a foe engaged with the PC breaks away | `player_answer` | `react`: the opportunity attack with its Avrae roll (melee only; a ranged weapon cannot make one), or decline |
| `roll_call` | `save_rider`: a hit whose attack carries a save (SRD giant centipede) | `player_roll` | the PC's own save total ("Con save 14"). The DC is never shown. A declared act after it ("..., then I cast magic missile") waits for his turn (`declared_next`). |
| `flourish_window` | a death (or a knockout the player chose) of the leader, an `important` foe, a hook raiser, or the last foe | `player_description` | Kit's `flourish` read: `describe` (she yes-ands it; it changes no outcome) or `new_action` (the flourish is passed, the act resolves) |

**Order:** the reaction comes first, before damage; then the save the hit carries. If Shield turns the hit, no save is owed. A surprised, down or incapacitated PC has no reaction (`pc_can_react`, #97). Comparisons use `kit_rolls.meets_or_beats` (the actor wins ties).

**Decline once per round:** a declined trigger family (`hit`, `leaves_reach`, ...) is not offered again that round, unless the stakes rise to `drop` (this hit would take him to 0).

**Engagement** is tracked by default: a melee blow by the PC or an NPC's melee attack on him puts them in each other's reach (`combat.engaged`). A room's `combat.in_reach` is an optional starting position only.

### Reactions: inventory and spend (`runtime/kit_reactions.py`)
The PC's reactions are built from the sheet (`spells` as a level dict or a list, `slots` as counts or `{max, used}`, features, feats and items) into `state.pc_resources`, which is session state: slots and per-rest uses persist across fights and are refreshed by a `rest` event (`Runtime.rest('short'|'long')`). Own-turn leveled spells spend their slot too. The engine never spends a slot silently: a reaction spell is cast by the player in Avrae (`!cast shield`), and Kit's read says so (`cast_in_avrae`). Anything the engine has no effect for is flagged `adjudicate` for Kit. The session manifest carries one line, `available_reactions`; "used this round" is live in the fight view (`your_reaction`).

### Kit voices every window; Kit reads every answer
No engine-authored line speaks as Kit, and the engine reads no English for intent.
- **window_voice** (`stage: window_voice`): when a turn stops at a window, prepare returns a tiny packet `{window, narrate_first, character}`. Kit narrates the PC's hit or kill first, then voices the window (a question naming an option, no DC). Nothing commits until her lines pass `check_window_voice`.
- **window_answer** (`stage: window_answer`): the player's reply while a window is open comes back as `{window, player_reply}`. Kit declares one act field, validated by `kit_acts.check` with the open window as the offer (the same pattern as #97's `handles`): `react: {choice: <option id>|decline|unclear, cast_in_avrae, slot_level}` or `flourish: describe|new_action|unclear`. `unclear`, a spell not yet cast in Avrae, or an opportunity attack with no roll makes her ask: one short question in her voice, committed as a clarify interstitial, with the window still open. Otherwise the window resolves and the rest of the round is a normal one-pass turn under the same turn id.
- **Round trips:** every window packet is one extra small model trip. `timing.window_round_trips` counts them per turn. `scripts/watchroom_replay.py` reports `window_round_trips` and a `combat_window_leg` (roadcamp, a Shield window voiced, an unclear reply asked about, then the cast) against the speed estimate.

## Kit-raised interstitials (`runtime/kit_interstitial.py`)
`roll_call` (a check call), `clarify` (ask_player) and `risk_confirm` (state the risky fact,
then "are you sure?"; never twice for one fact). These get structural checks only.

## Progressive reveal on room entry (`runtime/kit_reveal.py`)
On the first look into an area (room opening, or an exit into a new area), the packet carries
`reveal: {rule, area, exits, obvious, hold}`. A fact is in the obvious layer if it says `"layer": "obvious"`,
has `handling`, or a trigger, hook, claim or held item names it in a fact-id field (ids are never matched as words).
The exits are always obvious. `"layer": "detail"` holds a fact back.

**The handoff rule lives in one place:** `kit_reveal.entry_mode(plan)` / `check_entry(plan, reveal)` decide
whether the turn must hand the floor back, from Kit's structured `decision.reveal_entry {mode: handoff|directed, relevant}`.
- `handoff` (no directed action): the turn ends on a short question in Kit's own words. There is no stock line; any line in the rules is marked as an example.
- `directed` (the entry directs an action, "I go in and roll the carcass over"): the action is honored. The engine resolves the rest of the message in the new area (a watched feature becomes Kit's `handles` declaration), Kit gives the held facts it touches (`relevant`), and no handoff question is needed.
- The leak check runs per held fact (even one): its own cue words (two, or all if it has fewer), not counting words the shown layer, the actors present, the area name or the exits already use.

(#102 is moving the turn's function to a structured `hands_off` field validated by the same kit_acts pattern; `entry_mode`/`check_entry` is the seam to fold into it.)

There is no reveal at an approach, during a fight, when a held description or a due hook takes
the entry, on a stall-check turn, or when nothing is held.

## Per-turn handoff trace (`runtime/kit_handoff.py`, `scripts/handoff_trace.py`)
The trace is `<session dir>/<db stem>.handoff.jsonl`.
- **Turn lines:** one per committed turn, `{event: turn, turn_id, kind, by_player, handoff: {type, trigger, awaits, deferred_action_id, raised_by} | null, latency_s, latency_from, answers}`.
- **Held lines:** one per held input (pending ruling), `{event: held_input, input, reason, answers}`.
- **Types:** stall_check, reaction_window, flourish, narrowing_question, progressive_reveal, clarify, risk_confirm and roll_call.
- **`answers`** gives the verdict on the previous handoff, taken from the input that actually closes or resolves it: did the floor go to the player? A barge-in (another action, a held input) never counts as answering; a re-ask carries the original handoff (`reasks`).
  - An engine window must close (its `deferred_action_id` is gone).
  - A stall check or roll call needs a roll.
  - A held input counts as not resolved.
- **Latency** comes from the timing stamps and says which: `host_stamps (received to shown)` when the host stamped `shown_at`, else labelled `(no shown_at)` (prepare-only), else prepare-to-commit, else runtime prepare. The CLI refreshes it from the session database.
- **Engine-started fights:** `engine.monster_initiative` names the room trigger that started one (PR-M's seam).

    scripts/handoff_trace.py SESSION.sqlite [--json]
