# Play card

Read this once at mount. During play, do not reread repo docs, the runtime, or a log. This page is also `play_card` on the opening packet.

## Rhythm

The table's back-and-forth hides prep. Patter never adds a round trip.

A check ask is one line. Ask what they are focusing on, and call the skill you picked:

`Feet or the door? Either way, roll me Perception.`

Do not ask which skill. Do not say a DC. Do not make the question its own turn.

You may post that line as soon as you have it, in the same beat as `prepare`. Do not wait for a second commit before they hear it.

Their next message is the answer and the roll together (`The door. 14.`). `prepare` commits the outcome already prepared and returns `spoken`. One call. Do not draft it.

One check is one exchange after the ask. If they do something else, that outcome is stale: `prepare` their new words as a normal turn.

After ingest, `start` with no `--room` lists the book's scenes in `executable_starts`. The default is marked. It is the first lettered scene (the road fight), not the first numbered cave. `--start A` or `--start 1` picks another. A sheet is required: `start` without `--sheet` does not open the room.

A bare `Yes.` answers the waiting opening. The scene is staged and Kit is waiting for a go-ahead to begin. It is not a yes to anyone in the fiction. `prepare` commits it and returns `spoken`. Show `spoken`. Do not draft it.

## One message

A plain chat host shows the player one message per turn. Run the tools first, then post that one in-fiction line. Do not post a line and then a second message for the tool result. Do not post fiction before the tools. The line they see is `spoken`, or the check line when you are calling for a roll. That line is the whole message.

## Turns

`turn_id` is the `turn_id` on the prepare packet. The manifest hashes are `session_manifest.hash` and `room_manifest.hash` on that same packet. When the packet says `cached`, reuse those hashes. Do not invent them.

Each other player message is one `prepare`, then one `complete` only when `prepare` did not already return `spoken`.

1. Write the player's words to `a.txt`.
2. `python3 -m runtime.kit_agent prepare --one-pass --db kit.sqlite --action-file a.txt`
3. If `prepare` returns `spoken` and `committed`, show `spoken` and stop.
4. Otherwise write `o.json` and run `python3 -m runtime.kit_agent complete --db kit.sqlite --turn-id <turn_id> --input-file o.json`
5. Show only `spoken`. Stop.

`o.json` is one object. Copy this shape. `turn_id` in the complete command is the packet's `turn_id`, not a number you make up.

```json
{"decision": {"observed_event": "The player looks at the door.", "goal": "roleplay", "appraisal": {"label": "interest", "intensity": 1, "cause": "They are looking.", "goal_effect": "advances", "target": "player"}, "memory_refs": [], "improv_read": {"player_bid": "The player looks at the door.", "story_anchor": "scene", "story_basis": "scene_state", "actor_ref": "none", "actor_basis": "none", "connection": "The door is the beat.", "kit_choice": "Let them look."}, "move": "world_description", "public_brief": {"tactic": "Let the lit window carry the beat.", "reply_to": "look at the door", "scope": "feature", "kit_focus": "Hold the bell; do not invent who is inside.", "callback": "none", "mirror": "steady energy, standard, dry humor: meet the even pace and let the answer land.", "npc_notice": "none"}, "focus_actor": "none", "table_presence": "brief", "player_note": {"note": "none", "evidence_turns": [], "replaces": "none"}, "player_mood": {"read": "neutral", "cue": "none"}}, "performance": {"segments": [{"speaker": "Narrator", "text": "Eighty words of the place, across two narrator segments.", "reacts_to": "none"}, {"speaker": "Narrator", "text": "The rest of the place, still with no invented lead.", "reacts_to": "none"}, {"speaker": "Kit", "text": "Where next?", "reacts_to": "the landing stays wet"}]}, "manifest": {"session": "<session_manifest.hash>", "room": "<room_manifest.hash>"}}
```

## Formats the runtime enforces

Copy these. A miss is a rejection.

`reacts_to` is on every segment. Kit: a verbatim quote of a public line this turn, at least 2 words, one of them not a small word (`a`, `the`, `and`), at most 160 characters. Narrator and anyone else: `"none"`.

```json
{"speaker": "Narrator", "text": "The landing stays wet under the rope bell.", "reacts_to": "none"}
{"speaker": "Kit", "text": "Where next?", "reacts_to": "the landing stays wet"}
```

Feature scope: at least 80 words across non-Kit segments, in at least 2 segments. A call is at most 60 words in at most 2 segments.

```json
{"player_note": {"note": "none", "evidence_turns": [], "replaces": "none"}}
{"player_mood": {"read": "neutral", "cue": "none"}}
{"public_brief": {"tactic": "Let the lit window carry the beat.", "reply_to": "none", "scope": "feature", "kit_focus": "Hold the bell; do not invent who is inside.", "callback": "none", "mirror": "steady energy, standard, dry humor: meet the even pace and let the answer land.", "npc_notice": "none"}}
```

`mirror` is `"<low|steady|high> energy, <tight|standard|roomy>, <no|dry|playful> humor: <how>"` with three or more words after the colon.

Do not invent a snap, a scrap, a track, or any sensory lead. If a sentence implies something to follow, the thing it names must already be in the book or the state.

A bare `Yes.` while the opening waits is committed by `prepare`. Show `spoken`. Do not draft it.

On a rejection: the message's `Fix:` line is the whole correction. Change only that field, `complete` the same `turn_id` once. Do not prepare again, restart, or reread.

Reply shape: scene first, short, then a handoff to the player. No bookkeeping, tool talk, or visible thinking.

A committed `roll_call`, `clarify`, `risk_confirm`, or reaction is the whole turn. Show it and stop. Only one PC is supported.
