# Kit's Expression Gap: What the Design Assumed, What the Code Did

**Status:** 2026-09-28, branch `kit-focus-brief`. This document is written for whoever designs Kit next, including the model that wrote the original pipeline and prompts. It explains why Kit did not come across as a particular DM, what the code actually did, what this change fixes, and what it leaves unproven. Line numbers marked **@79173a1** refer to the baseline commit. Line numbers marked **@673e9cd** refer to the code the Nik playtest actually ran on. Unmarked line numbers refer to this branch.

## The short version

Kit's personality was written down, loaded, and labeled. It was never made to *do* anything the player could see. The private decision said "Kit cares about bringing this NPC to life". The performer that writes the words never received that decision. Nothing checked that the private plan agreed with its own goal. The validator only checked that the output had the right shape. A two-sentence price quote therefore passed every gate, and the 38 passing tests were telling the truth: they tested storage and formatting, not personality.

## What the design assumed vs. what the code did

| The design assumed | What the code actually did |
| --- | --- |
| Loading the personality core makes Kit's personality operate. | The core is read from disk (`runtime/state_context.py:14`, `:325-326` @79173a1) and pasted whole into both model calls (`runtime/kit_agent.py:434`, `:467` @79173a1). It is 97 lines of broad prose. Nothing turns "embody every important NPC" into a specific choice on a specific turn. Having the text in the prompt is not evidence that it changed anything. |
| Kit's private choice shapes the spoken turn. | The private decision records `goal`, `appraisal` (with a `cause`), and `improv_read.kit_choice` (`kit_agent.py:125-156` @79173a1; `scene_discernment.py:20`). The performer's input is built in `performance_input` (`kit_agent.py:475-484` @79173a1) and receives only `move`, `focus_actor`, `table_presence`, `tone`, and the four-field `public_brief`. The goal, appraisal, and `kit_choice` are dropped there. A test locked in that separation (`tests/test_kit_agent.py:106` @79173a1: `assertNotIn('improv_read', ...)`). One-pass mode writes the decision and the speech in one output, but the instructions tell the model to write the speech only from the brief, move, tone, focus actor, and presence (`kit_agent.py:249-250` @79173a1). |
| An emotion label is a sign of inner life. | `appraisal: interest (1)` is a string the model fills in. No code reads it to change anything the player sees. It is saved as `current_appraisal` and fed back to the next *private* decision only (`state_context.py:206` and `kit_agent.py:436-438`, both @79173a1). |
| Kit has longer-lived appetites and a relationship with the player. | Kit's entire saved state is `{'episodes': [], 'current_appraisal': None}` (`state_context.py:73` @79173a1). Episodes are the last 8 turns by recency, not relevance (`kit_agent.py:425` @79173a1), and only the private stage sees them. "player model" is listed as a missing layer (`state_context.py:358` @79173a1). The appetite model lives only in `docs/personality/dm-personality-layer-v0.1.md`. |
| The validator guards quality. | `check_speech` (`kit_agent.py:384-417` @79173a1) checks: 1–7 segments of at most 900 characters, known speakers, Kit's segment count against her presence choice, that the chosen move happened (an NPC spoke), and a literal list of banned secret phrases (`:358-381`). It has a maximum length and no minimum. It never asks whether the reply answers the player, follows the brief, or reflects Kit's goal. The brief check (`:351-355`) only requires four non-empty strings of 240 characters or fewer. |
| Passing tests mean the system works. | The fake model in the tests returns a short, fixed, two-segment reply (`tests/test_kit_agent.py:62-65` @79173a1), and it passes. The tests prove that the database, secrecy list, and turn locking work. They cannot prove a performance is good, and they never tried. |
| Latency was known to be 81 seconds. | Nothing in the code measured time. The only time-related value was a 90-second HTTP timeout (`kit_agent.py:281` @79173a1). The 81 seconds came from a chat screenshot, and most of it was the host model thinking between the `prepare → decide → finish` calls. The runtime could not see that time. |

## The Nik failure was partly a bad private decision

The playtest record says the private trace had `goal: npc_embodiment` and "a brief telling the dealer to name the toll" (`tests/playtests/2026-09-26-area-06c-nik.md:20`). That was Kit's own decision contradicting itself. The goal said "make this person real", and the instruction to the performer said "state the price". At that time the brief was one free-text string of up to 350 characters (`kit_agent.py:144`, `:270-271` @673e9cd). `kit_choice` did not exist yet; it arrived later in commit `6160e1f`. Even a perfect handoff would have delivered "name the toll". **Nothing checked that the brief agreed with the goal.** Fixing only the handoff would have delivered the wrong instruction faithfully.

Three other things pulled the dealer toward a price quote:

1. **The event was generic.** Every social turn becomes the same accepted event, "You address the figures at the card table." (`kit_agent.py:119` @79173a1), and the private decision must copy it word for word (`:310`). Kit's appraisal was therefore "about" a sentence that says nothing. Nik's actual words were in `player_action`, but no field required the plan to answer them.
2. **The dealer was written as a price machine.** At Nik time, the performer's instructions described the dealer as a performer "who wants a bargain" (`kit_agent.py:182-183` @673e9cd). The actor card added afterwards says he "can turn a courteous invitation into a blunt price" (`tests/fixtures/level_01_area_06c.json:26`), and his goal is "Control the encounter without risking himself" (`:109`). Given a greeting, the quickest path to those instructions is the toll.
3. **"Quiet" meant "absent".** `table_presence: quiet` bans any Kit segment (`kit_agent.py:213-214`, `:395` @79173a1). No other channel carried her influence, so when she stayed quiet she disappeared.

## Why a document, a label, a prompt variant, or a schema test proved nothing

- A **personality document** describes intent. It is evidence only if changing it changes what the player hears.
- An **emotion label** is the model's own claim about itself. With nothing downstream reading it, it is decoration.
- A **prompt variant** (such as `kit_expression_v1`) is a hypothesis until blind readers prefer its transcripts.
- A **schema test** proves the output has the required fields. The Nik reply had every required field.
- A **stronger private trace with the same generic transcript is a failed result**, not partial success. The player never sees the trace.

## What this change does

It was approved by Brendon on 2026-09-28 as the smallest general change. It adds no area-specific script, no dealer lines, and no new model calls.

1. **Three new fields in the brief** (`PLAN_SCHEMA`, `kit_agent.py:147-154`). Because the whole brief already flows to the performer (`performance_input`, `:598-607`), into one-pass mode, into Kit's saved episodes, and through the leak check, almost no new wiring was needed.
   - `reply_to`: the exact words from the player that the turn must answer. It must appear in the player's message after lower-casing, whitespace, and curly quotes are normalized (`check_reply_to`, `:427-436`). For the room opening it must be `none`.
   - `scope`: `call`, `exchange`, or `feature`. The room opening must be `feature`. `call` is allowed only for a `ruling` or `ask_clarification` move, or when no actor is in focus (`check_plan`, `:406-411`). An NPC reply therefore cannot declare itself a one-liner.
   - `kit_focus`: 200 characters or fewer. It is a public-safe statement of one visible effect of Kit's goal and `kit_choice` on this turn: what she foregrounds, which actor tactic she lets play out, how she frames a ruling, or a deliberate restraint. It must not contain quoted dialogue, and must not copy `kit_choice` or the appraisal cause verbatim (`:412-419`). It passes the same literal leak check as the rest of the brief (`check_brief_public`, `:499-503`). The raw `kit_choice` and appraisal cause stay private.
2. **Instructions.** The private stage is told that the brief must agree with its goal ("for npc_embodiment or roleplay, the tactic is something the actor tries in answer to the player, not only a price or a fact"), how to fill the three fields, and that the actor's objective and tactic come from the actor's motives, not Kit's taste. The performer is told to answer `reply_to`, to act out `kit_focus` through framing, emphasis, ruling style, or a Kit remark only when her presence allows, and that `kit_focus` grants no authority over facts, rules outcomes, NPC knowledge or commitments, or the player's choices. NPCs keep their own motives and actor-card voices and are never used to voice Kit's taste.
3. **A flat-reply guard in `check_speech`** (`check_scope`, `:442-470`; constants at `:182-201`).
   - A `call` must stay within 60 words and 2 segments.
   - An `exchange` needs the focus actor to speak at least 30 words, at least 40 words in non-Kit segments, and at least 2 segments.
   - A `feature` needs at least 80 non-Kit words in at least 2 segments.
   - Kit's own remarks do not count toward the actor's side.
   - The exact Nik reply (a 13-word beat plus 23 words of dealer speech) is now rejected. A one-line roll prompt under `call` is accepted.
4. **A specific retry reason.** When the performer is rejected, the retry now says exactly which check failed, e.g. "Exchange scope: the Dealer spoke 23 words (floor 30)…" (`retry_instruction`, `:610-613`). The old message was "failed the public visibility or format check". The chat bridge logs rejected attempts and the last reason.
5. **Latency recording outside the turn hash.**
   - A new `kit_telemetry` table (`state_context.py:48-52`, methods `:245-267`) stores timing separately from `turns`, `ledger`, and `kit_turns`, so it never enters the idempotency digest.
   - API mode records time from receipt to commit or rejection, model call count, per-call seconds, and rejection reasons.
   - Chat mode records `prepare_to_commit_s`. That covers the host model's time between stages, but not anything before `prepare` is called.
   - See `python -m runtime.kit_agent timing --db …`.
6. **Tests.** The fake model's replies were updated. There are new regression tests for:
   - the exact Nik reply being rejected;
   - a roll prompt accepted under `call`;
   - a long `call` rejected;
   - a misquoted `reply_to` rejected;
   - `kit_focus` reaching the performer while the raw `kit_choice` and appraisal cause do not;
   - bad `kit_focus` values;
   - opening scope;
   - the retry reason;
   - telemetry staying out of the hash.

   One real bug was found while writing them: a player who says a secret word ("I accuse him of being a doppelganger") would have made the quoted `reply_to` fail the brief's leak check. The brief check now skips `reply_to`, because those are the player's own words, which the performer already receives. The performance itself is still checked.

## What it deliberately does NOT do

- It does not send the raw `kit_choice` or appraisal to the performer.
- It does not add appetite meters, relationship scores, or a player model.
- It does not change the dealer's actor card, the source facts, the rules, or the accepted-event machinery. The generic social event string is unchanged.
- It adds no model call and does not change any model.
- It does not make the `kit_expression_v1` trial the default.
- It does not claim Kit is now entertaining. **No real model has run this code yet.**

## Its limits: read these before trusting a passing test

- **Word floors are a guard, not proof.** They stop the specific "price and done" failure. A model can pass them with padding, and a 40-word reply can still be lifeless. They also run against the pipeline doc's "no universal word count" principle. The numbers are named constants so blind-review evidence can tune them. Longer is not better.
- **The leak check is literal.** It catches "marked deck", not "those cards have a funny shine on the back". `kit_focus` is a new place where a paraphrased secret could slip through. Humans must still read for implied leaks.
- **One-pass mode cannot prove causation.** The decision and the speech come from one output, so the speech may have come first and the decision written to justify it. Only staged mode (fixed decision, then a separate performance) can test whether Kit's choice caused the words.
- **The ruling dodge.** A model that wants to be brief can label a turn `ruling` with no focus actor and use `call`. Checking whether that label is honest needs human review or a real rules router.
- **`kit_focus` can be vague.** "Make it interesting" passes every check. Whether the focus is specific, and whether the speech actually acts it out, is a judgment for blind review.
- **Kit's voice can leak into NPCs.** The instructions forbid it, but no code can detect it.

## Why "recent history first" is still the right order for appetites and relationship

The long-form design proposes appetite pressure and relationship tracking. They are still unbuilt, and that is correct for now:

1. Kit does not yet reliably express one choice on one turn. A drive that shifts over many turns cannot show up until a single turn can.
2. A numeric appetite or affection score is another label. Without an observable effect and a comparison against a simpler approach, it would repeat the `appraisal` mistake at a larger scale.
3. Kit's episodes now keep `kit_focus` with each turn. The next test is whether a *relevant* remembered episode changes her next visible choice and an *irrelevant* one does not. If recent history is enough, meters are unnecessary. If it is not, the failure will show which event types a longer-lived state must track.
4. Relationship state must come from observable player behavior and explicit feedback, not invented feelings, and Kit must be able to be wrong about the player.

## How to gather the first real evidence

```sh
export OPENAI_API_KEY=...            # the script refuses to run without it and writes nothing
python scripts/run_kit_live_comparison.py --check                  # exports both refs, no model calls
python scripts/run_kit_live_comparison.py --model gpt-5 --samples 2 --jobs 10
# writes OUT/blind/review.md (randomized A/B) and OUT/blind_answer_key.json automatically
```

The script exports baseline `79173a1` and the candidate (default `HEAD`) with `git archive`, so your checkout is untouched. It runs each version's own agent with identical inputs and settings. Output goes to `tests/playtests/live-runs/<UTC stamp>-<model>/`: `transcripts/` (player-facing only), `traces/` (DM-only; do not show reviewers), `latency.csv`, `blind_pairs.json`, `blind/review.md` with `blind_answer_key.json`, and `run.json`. `--max-output-tokens` defaults to 8000 for both versions, because reasoning models spend output tokens on thinking and the runtime's own 1800 limit may cut them off. Pass `--max-output-tokens 1800` to reproduce the runtime default exactly. Dice for keyed checks come from each fresh session's seed, so a check result can differ between versions; compare those turns with that in mind.

## Checklist: what future design work must include to count as evidence

Nothing below is satisfied by a document, label, prompt, or passing unit test.

- [ ] **Real model transcripts.** Record the model ID, settings, commit SHA, fixture hash, exact player inputs, and whether staged or one-pass mode was used. Use `scripts/run_kit_live_comparison.py`.
- [ ] **Same inputs, one change at a time.** Compare the baseline and candidate on the same room, player words, rules outcome, and model. Do not change the prompt, schema, and actor card together.
- [ ] **More than one sample.** Generate at least two samples per arm, because a single run can be noise.
- [ ] **Blind review before reading traces.** Reviewers see only public context and spoken turns (`scripts/blind_performance_review.py`). They say which DM they would keep playing with and quote the deciding moment. Open private traces only afterwards, to explain the result.
- [ ] **A full session, not one line.** Review the opening plus at least two exchanges as one sample.
- [ ] **Relevant vs. irrelevant memory.** Write the expected difference down in advance. A relevant earlier episode should change Kit's next visible choice; an irrelevant one should not. Run a no-memory control, remembering that the public dialogue history still carries earlier words.
- [ ] **A narrow turn stays narrow.** Include a roll prompt or a ruling and confirm it stays short and direct.
- [ ] **A quiet or serious moment.** Restraint is part of her identity, so include one and check she holds back.
- [ ] **A second actor and a second scene.** Kit's signature should carry over while the dealer's mannerisms stay in area 6c. The runtime is currently hard-wired to area 6c (area check `kit_agent.py:72`, speaker enum `Dealer`/`Card player`, `focus_actor` enum `uktarl`/`other`/`none`). A general scene adapter and a second source-grounded room are prerequisites.
- [ ] **Hard violations logged separately.** Source errors, private leaks, invented player actions, and unsupported results disqualify a sample, whatever its prose quality.
- [ ] **Latency from real runs.** Report per-turn time (from `kit_telemetry` or the harness `latency.csv`), model calls, and retries. Speed is telemetry, not a gate, during this phase.
- [ ] **A failure is a result.** If the private trace improves and the transcript does not, record that and do not promote the change.

## Results so far

**No real-model evidence exists yet.** This section will change when it does.

- **Attempted:** 2026-09-28 at 7:12 PM PT. Command: `python scripts/run_kit_live_comparison.py --model gpt-5 --samples 2 --jobs 10`, with all five arms, baseline `79173a1` versus candidate `b6168e2`, and the default `--max-output-tokens 8000` for both versions.
- **Result:** every request was refused with `HTTP 429 insufficient_quota` / `credit_balance_exhausted` ("You have no credits remaining"). The account's model list does include `gpt-5`, so the model choice was not the problem. A one-line request to `gpt-5-nano` and to `gpt-4.1-nano` got the same billing refusal, so no other model would have helped.
- **No Kit turn reached a model**, so there are no transcripts, no validator pass/fail/retry counts, no latency figures, and no violation findings for either version. The error-only output folder was deleted rather than committed, because it would look like data.
- **Harness changes made because of this:**
  - The script now stops at once on an auth or quota failure (401, 403, or `insufficient_quota`) and writes nothing.
  - It automatically writes a randomized blind A/B packet (`blind/review.md`) and a separate answer key (`blind_answer_key.json`) with a recorded seed.
  - `--jobs N` runs the (version, arm) workers concurrently. Turns inside an arm stay in order, and per-call latency is still timed per request.
- **To produce the first results once credits are added:** `python scripts/run_kit_live_comparison.py --model gpt-5 --samples 2 --jobs 10`. Output lands in `tests/playtests/live-runs/<UTC stamp>-gpt-5/`.
- **Caveats that will still apply:**
  - The author of this change also wrote the harness. Its first run is a check that the harness works and a list of violations, not a quality verdict. Quality needs blind reviewers who did not write the change.
  - `other_scene` is a stand-in in the same room, not a second actor or room.
  - Check outcomes use each session's random dice, so they can differ between versions.
