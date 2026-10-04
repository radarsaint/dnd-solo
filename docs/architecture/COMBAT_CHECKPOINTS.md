# Combat checkpoints, interstitials, progressive reveal, and the handoff trace (PR-H)

The engine stops where the player owns the next input, records what it waits on in
`combat.awaiting = {kind, awaits, deferred_action_id, trigger, ...}` (the names PR-M's save
rider uses), commits the turn, and resumes exactly there when the answer comes.

## Engine checkpoints (`runtime/kit_combat.py`)
| kind | trigger | awaits | resumes with |
|---|---|---|---|
| `reaction_window` | `hit`: an NPC hit the PC and a reaction on the sheet could change it (Shield: beats AC by < 5, never a natural 20; Absorb Elements: elemental damage), a slot and the reaction free | `player_answer` | yes / no / the option named. Shield: +5 AC until the start of the PC's turn, a slot and the reaction spent. Declining keeps the reaction. |
| `reaction_window` | `leaves_reach`: a foe retreats out of the PC's reach | `player_answer` | an opportunity attack (with its Avrae roll) or no |
| `roll_call` | `save_rider`: a hit whose attack carries a save (SRD giant centipede) | `player_roll` | the PC's own save total (Avrae, "Con save 14", a bare number). The DC is never shown. |
| `flourish_window` | the kill of the leader, an `important` foe, a hook raiser, or the last foe | `player_description` | the player's description: Kit yes-ands it; it changes no outcome |

**Order:** the reaction comes first, before damage; then the save the hit carries. If Shield turns the hit, no save is owed. A surprised PC has no reaction until his lost turn ends. Anything that is not an answer (a check request, another action, a save stated during a Shield window) is held as a pending ruling. The window stays open and nothing is committed.

Engine interstitials commit without a model packet (`stage: interstitial`). Speculative
branches (what each answer would do) go to telemetry only, never to state or the ledger.

## Kit-raised interstitials (`runtime/kit_interstitial.py`)
`roll_call` (a check call), `clarify` (ask_player) and `risk_confirm` (state the risky fact,
then "are you sure?"; never twice for one fact). These get structural checks only.

## Progressive reveal on room entry (`runtime/kit_reveal.py`)
On the first look into an area (room opening, or an exit into a new area), the packet carries
`reveal: {rule, obvious, hold}`. A fact is in the obvious layer if it says `"layer": "obvious"`,
has `handling`, or is referenced elsewhere in the room (alarm, hook, exit, actor, trigger).
`"layer": "detail"` holds a fact back. Kit gives the obvious layer and ends with a handoff in
her voice ("Where do you look first?"). An NPC putting a question to the PC also counts.
Hard checks:
- the turn ends on that handoff;
- the narration does not give the held layer (cue words of two or more held facts).

There is no reveal at an approach, during a fight, when a held description or a due hook takes
the entry, on a stall-check turn, or when nothing is held.

## Per-turn handoff trace (`runtime/kit_handoff.py`, `scripts/handoff_trace.py`)
The trace is `<session dir>/<db stem>.handoff.jsonl`.
- **Turn lines:** one per committed turn, `{event: turn, turn_id, kind, by_player, handoff: {type, trigger, awaits, deferred_action_id, raised_by} | null, latency_s, latency_from, answers}`.
- **Held lines:** one per held input (pending ruling), `{event: held_input, input, reason, answers}`.
- **Types:** stall_check, reaction_window, flourish, narrowing_question, progressive_reveal, clarify, risk_confirm and roll_call.
- **`answers`** gives the verdict on the previous handoff: did the floor go to the player? That means the next input came from the player and resolved the awaited action.
  - An engine window must close (its `deferred_action_id` is gone).
  - A stall check or roll call needs a roll.
  - A held input counts as not resolved.
- **Latency** comes from the timing stamps: host end-to-end if stamped, else prepare-to-commit, else runtime prepare. The CLI refreshes it from the session database.
- **Engine-started fights:** `engine.monster_initiative` names the room trigger that started one (PR-M's seam).

    scripts/handoff_trace.py SESSION.sqlite [--json]
