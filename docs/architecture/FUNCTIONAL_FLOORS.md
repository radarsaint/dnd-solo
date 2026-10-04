# Functional floors (PR-F)

`runtime/kit_agent.py`: `check_scope`, `hands_off`, `visible_things`, `things_named`. These replace the raw word floors
(80 words in 2 segments for a feature, 40 words in 2 for an exchange).

## Why

Brendon's harness run on 691e834 showed the word count and the job had come apart:
- A playable 44-word room opening was rejected only by the 80-word feature floor.
- A 10-word NPC challenge ("His hand settles beside the bell cord. / Who sent you?") was rejected only by the
  40-word exchange floor.
- A padded turn with 90+ words of mood that named nothing in the room and handed nothing to the player passed.

## The checks (soft, like the floors they replace: warnings in degraded mode)

| Scope | Must do |
|---|---|
| all but `call` | at least `SANITY_MIN_WORDS` = 8 words outside Kit's segments (Kit's count under showtime), against empty turns |
| `feature` | name at least `FEATURE_MIN_THINGS` = 2 of the area's visible things (fewer if the area has fewer), and hand the floor to the player |
| `exchange` | the focus actor makes a move (speaks, or the narration names them acting), and the player gets something to answer |
| `call` | unchanged: at most 60 words in 2 segments |

* **Visible things** come from the public view only: each known exit, each present actor, each known fact here
  and each established detail, reduced to anchor words (content words, stemmed, room-noise words removed). A
  thing counts as named when a spoken word matches one of its anchors. Each spoken word names at most one thing.
  No room data is needed beyond what the player can already see, so this works on any room, including rooms
  authored from the book at runtime.
* **Handing off** (`hands_off`): the last segment, or the last non-Kit segment when Kit reacts after it, asks a
  question, calls a roll or check, says "what do you do", "your move" and the like, or is an NPC's line the player
  can answer ("Hands out. Now.", "Stay down."). In an exchange, the focus actor asking anything also counts.
* **A card with `speech_floor: true`** keeps its 30-word actor floor. That is room data the room opted into,
  not a global word floor.

The packet states all of this up front (`performance_limits`, the room-entry `first_try` line), so Kit can meet
it on the first try. Short is fine when the turn does its job, and long is not enough when it doesn't.

## Watchroom replay (`scripts/watchroom_replay.py`, dice pinned, model time is the labelled estimate)

`--pithy` swaps in the harness cases: a 44-word opening on T0, the 10-word challenge on T5, and short lines on T6,
T8 and T10.

| | word floors (PR-T head) | functional floors |
|---|---|---|
| `--pithy` rejects / unresolved | 12 / 2 | 0 / 0 |
| `--pithy` e2e median / p95, full packets | 16.96 s / 60.04 s | 14.70 s / 16.46 s |
| `--pithy` e2e median / p95, `--manifests` | 11.68 s / 47.69 s | 9.58 s / 12.94 s |
| live lines (default) rejects | 0 | 0 (Kit ends a feature on a question, as the limits now say) |
| live lines with `--live-speech` (exactly as played, no handoff) | 0 | 3 (T0, T2, T4 end on narration and are sent back once for a handoff) |
