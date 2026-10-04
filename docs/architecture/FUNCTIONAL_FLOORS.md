# Functional floors (PR-F, reworked after Nagatha's #102 review)

`runtime/kit_floor.py` holds the one handoff rule. `runtime/kit_agent.py` `check_scope` applies it for each
scope. Together they replace the raw word floors (80 words in 2 segments for a feature, 40 words in 2 for an
exchange). Nothing here counts words or matches vocabulary lists. The first PR-F head had an 8-word minimum,
anchor-word "visible things" with a 6c-tuned `_THING_NOISE` list, and handoff phrase lists. All of that is
gone.

## Why

Brendon's harness run on 691e834 showed the word count and the job had come apart:
- A playable 44-word room opening was rejected only by the 80-word feature floor.
- A 10-word NPC challenge ("His hand settles beside the bell cord. / Who sent you?") was rejected only by the
  40-word exchange floor.
- A padded turn with 90+ words of mood that named nothing in the room and handed nothing to the player passed.

## Kit declares, the engine validates the structure

Kit's decision carries an optional `hands_off: {kind, reason}`. It works the same way as `handles` on #97
(runtime/kit_acts.py on kit-monster-initiative): a structured field the engine checks, never English it
guesses at.

| kind | the engine checks |
|---|---|
| `question` | the last sentence (of the last segment, or the last non-Kit segment) ends with `?` and speaks to the PC, or is a short narrowing question |
| `check_call` | the last segment names a check: a skill or ability from `pc_sheet`, initiative, a saving throw, a death save or an attack roll |
| `npc_challenge` | the focus actor speaks last outside Kit's remarks |
| `combat_prompt` | the last sentence is a short address to the PC ("Your move.") |
| `none` | `reason` is not blank, and the turn is not one that must hand off (`required`, e.g. a progressive-reveal room entry on #101) |

When `hands_off` is left out, any of the four prompts seen in the speech counts. Undeclared, an NPC line
must be a line, not a sound: two words or more, or ending in `?`/`!`, so "Stay down." passes and "Hm." does not.
A turn that answers the player's own look or inquiry (a reply_to quote on an observe, inspect, threshold-look,
check, knowledge or lie-read event) hands the floor back by being the answer.

The decision is fixed once it is saved for a turn. `hands_off` is the one key Kit may restate when she
resubmits (`Runtime.AMENDABLE_PLAN_KEYS`). That way a handoff rejection is answered by declaring the turn's
function, or by changing the speech, and never by appending a stock prompt.

## Per scope

| Scope | Must do |
|---|---|
| `feature` | hand the floor back (above) |
| `exchange` | hand the floor back. Unless the hand-off is a check call or a combat prompt (the mechanics taking the floor), the focus actor must also make a move: speak, or be named acting in the narration |
| `call` | unchanged: at most 60 words in 2 segments |

A card with `speech_floor: true` keeps its 30-word actor floor. That is room data the room opted into, not a
global word floor.

## One rule with #101's reveal handoff

PR-H (#101, kit-combat-checkpoints) needs a room entry with a progressive reveal to end on a prompt. That is
`kit_floor.function(segments, plan, guards, required=True)`, the same rule with `none` refused. The rejection
text is the same ("... does not end with handing the floor back to the player ..."). Answering a look
passes on the same basis.

## Watchroom replay (`scripts/watchroom_replay.py`, dice pinned, model time is the labelled estimate)

The replay no longer appends "What do you do?" to Kit's lines, and no longer pads a rejected turn. Lines run
exactly as played. When a handoff is rejected, the replay's Kit restates `hands_off` (none, with a reason)
and the reject still counts. `--pithy` swaps in the harness cases.

| run | rejects / unresolved | e2e median / p95 |
|---|---|---|
| default (lines as played) | 1 / 0 (T0: the opening ends on narration) | 15.73 s / 23.57 s |
| `--manifests` | 1 / 0 (T0) | 10.62 s / 21.43 s |
| `--pithy` | 0 / 0 | 14.75 s / 16.51 s |
| `--pithy --manifests` | 0 / 0 | 9.90 s / 13.29 s |
