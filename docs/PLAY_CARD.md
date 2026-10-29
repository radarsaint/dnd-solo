# Play card

Read this once at mount. During play, do not reread repo docs, the runtime, or a log. This page is also `play_card` on the opening packet.

Each player message is exactly one `prepare`, one write, one `complete`. A plain chat host has no workers.

1. Write the player's words to `a.txt`.
2. `python3 -m runtime.kit_agent prepare --one-pass --db kit.sqlite --action-file a.txt`
3. Write `o.json` and run `python3 -m runtime.kit_agent complete --db kit.sqlite --turn-id <turn_id> --input-file o.json`
4. Show only `spoken`. Stop.

`manifest` is only the two hashes, never a body:

```json
{"manifest": {"session": "<session_manifest.hash>", "room": "<room_manifest.hash>"}}
```

Copy these shapes. Do not learn them from a rejection.

```json
{"player_note": {"note": "none", "evidence_turns": [], "replaces": "none"}}
{"player_mood": {"read": "neutral", "cue": "none"}}
{"player_mood": {"read": "curious", "cue": "look around the landing"}}
{"public_brief": {"tactic": "Let the lit window carry the beat.", "reply_to": "none", "scope": "feature", "kit_focus": "Hold the bell; do not invent who is inside.", "callback": "none", "mirror": "steady energy, standard, dry humor: meet the even pace and let the answer land.", "npc_notice": "none"}}
```

`mirror` is `"<low|steady|high> energy, <tight|standard|roomy>, <no|dry|playful> humor: <how>"` with three or more words after the colon.

A bare `Yes.` while the opening waits is committed by `prepare`. Show `spoken`. Do not draft it.

On a rejection: the message's `Fix:` line is the whole correction. Change only that field, `complete` the same `turn_id` once. Do not prepare again, restart, or reread.

Reply shape: scene first, short, then a handoff to the player. No bookkeeping, tool talk, or visible thinking. If a turn will be slow, post one in-fiction line first.

A committed `roll_call`, `clarify`, `risk_confirm`, or reaction is the whole turn. Show it and stop. Only one PC is supported.
