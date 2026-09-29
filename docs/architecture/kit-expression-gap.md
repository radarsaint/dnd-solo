# Kit's Expression Gap: A Build Guide for GPT

**Who this is for:** GPT, as the collaborator building and hosting Kit's runtime in ChatGPT through `KitChatBridge`. It explains why Kit did not come across as a particular DM, the one build principle that fixes that class of problem, a worked example of the principle (branch `kit-focus-brief`), and the next things to build, in order.

**How to read the line numbers:** **@79173a1** means the code before this change. **@673e9cd** means the code the Nik playtest actually ran on. Unmarked line numbers in sections (a)–(d) refer to **@cee2948**, the `kit-focus-brief` code. Later branches shift them, so section (e)'s *Built* notes name functions instead of line numbers.

---

## (a) The gap: what the design assumed vs. what the code did

The design was careful about secrecy, persistence, and rules. It assumed that if Kit's personality was *described* and *decided*, it would *show*. It did not show, because **nothing carried Kit's decision to the words the player reads.**

| The design assumed | What the code did |
| --- | --- |
| Loading the personality core makes Kit behave like Kit. | The core is read from disk (`runtime/state_context.py:14`, `:325-326` @79173a1) and pasted whole into both model calls (`runtime/kit_agent.py:434`, `:467` @79173a1). It is 97 lines of broad prose. It never turns into a specific choice on a specific turn. |
| Kit's private choice shapes the spoken turn. | The private decision records `goal`, `appraisal` (with a `cause`), and `improv_read.kit_choice` (`kit_agent.py:125-156` @79173a1; `runtime/scene_discernment.py:20`). The performer's input is built in `performance_input` (`kit_agent.py:475-484` @79173a1) and contains only move, focus actor, presence, tone, and a four-field brief. **The goal, appraisal, and `kit_choice` are dropped right there.** A test locked in that separation (`tests/test_kit_agent.py:106` @79173a1). In one-pass mode the model writes both parts together, but it is told to write the speech only from the brief, move, tone, focus actor, and presence (`kit_agent.py:249-250` @79173a1). |
| An emotion label shows an inner life. | `appraisal: interest (1)` is a string the model fills in. Nothing reads it to change what the player sees. It is saved and handed back to the next *private* decision only (`state_context.py:206` and `kit_agent.py:436-438`, both @79173a1). |
| Kit has appetites and a relationship with the player. | Kit's whole saved state is `{'episodes': [], 'current_appraisal': None}` (`state_context.py:73` @79173a1). Episodes are the last 8 turns by recency, not relevance (`kit_agent.py:425` @79173a1), and only the private stage sees them. "player model" is listed as a missing layer (`state_context.py:358` @79173a1). Appetites exist only in `docs/personality/dm-personality-layer-v0.1.md`. |
| The validator guards the turn. | `check_speech` (`kit_agent.py:384-417` @79173a1) checks segment count, speaker names, maximum length, presence consistency, that the chosen move happened, and a literal list of banned secret phrases (`:358-381`). It has **no minimum**. It never asks whether the reply answers the player, follows the brief, or reflects Kit's goal. The brief check (`:351-355`) only requires four non-empty strings. |
| Passing tests mean personality works. | The tests' fake model returns a short fixed reply (`tests/test_kit_agent.py:62-65` @79173a1), and it passes. The tests proved the database, secrecy list, and turn locking work. That is all they could prove. |
| The 81-second turn was a known, measured number. | Nothing measured time. The only time-related value was a 90-second HTTP timeout (`kit_agent.py:281` @79173a1). The 81 seconds came from a chat screenshot. |

### The Nik turn was partly a bad private decision

The playtest record says the private decision had `goal: npc_embodiment` and "a brief telling the dealer to name the toll" (`tests/playtests/2026-09-26-area-06c-nik.md:20`). The goal said "make this person real" and the instruction to the performer said "state the price". At that time the brief was one free-text string (`kit_agent.py:144`, `:270-271` @673e9cd), and `kit_choice` did not exist yet (it came in commit `6160e1f`). **Nothing checked that the brief agreed with the goal.** A perfect handoff would still have delivered "name the toll".

Three other things pushed toward a price quote:

1. **The accepted event said nothing.** Every social turn becomes "You address the figures at the card table." (`kit_agent.py:120`), and the decision must copy that word for word (`:387`). Kit's appraisal was attached to an empty sentence.
2. **The dealer was written to quote prices.** At Nik time the performer was told the dealer "wants a bargain" (`kit_agent.py:182-183` @673e9cd). The actor card added afterwards says he "can turn a courteous invitation into a blunt price" (`tests/fixtures/level_01_area_06c.json:26`), and his goal is "Control the encounter without risking himself" (`:109`).
3. **"Quiet" meant "absent".** Quiet presence bans any Kit segment (`kit_agent.py:213-214`, `:395` @79173a1), and nothing else carried her influence.

### Why documents, labels, prompts, and schema tests didn't make personality happen

A personality document, an emotion label, a prompt variant, and a passing schema test all have the same weakness: **none of them physically reaches the performer as an instruction for this turn, and none gives the validator anything to check.** The model that writes the words sees a general description of Kit, a generic brief, and the player's message. It writes a competent generic reply. That reply passes because the validator only checks shape. The private trace can say anything, because the player never sees it and no code acts on it.

---

## (b) The principle to build by

> **Every private decision that should change the player's experience needs a public carrier: a field the performer receives, stated in public-safe terms, that the validator can check.**

In practice:

1. **Decide privately, carry publicly.** Kit's reasoning (`kit_choice`, appraisal, the actor's secrets, hidden facts) stays in the private stage. What crosses to the performer is a short, public-safe *consequence* of that reasoning: what to answer, what to foreground, how big the moment is.
2. **Make the carrier checkable.** Where possible, give it a form code can verify: a quote that must appear in the player's words, a choice from a fixed list, a length limit, a ban on dialogue, a literal leak check. If code can't verify it, say so and check it in play.
3. **The performer must be told how to use the carrier**, and told what the carrier does *not* permit: no new facts, outcomes, NPC commitments, or player actions.
4. **NPCs keep their own motives and voices.** Kit's taste decides what the scene spotlights. It never becomes an NPC's words or opinions. An NPC can resist the direction Kit would like the scene to take.
5. **Private reasoning stays private.** Never pipe raw `kit_choice`, appraisal text, or hidden facts into the performer "to help". Restate them as public direction or leave them out.
6. **A carrier without a test is a hope.** For each carrier, write tests that it reaches the performer, that the private text it came from does not, and that the validator rejects a violation.

---

## (c) Worked example: what this change does

This branch applies the principle to the gap above. It adds no area-specific script, no dealer lines, and no model calls.

**Three new carriers in the brief** (`PLAN_SCHEMA`, `kit_agent.py:147-154`). The whole brief already flows to the performer (`performance_input`, `:625`), into one-pass output, into Kit's saved episodes (`state_context.py:216`), and through the leak check, so almost no extra wiring was needed.

| Carrier | Private source | What the performer does with it | What the validator checks |
| --- | --- | --- | --- |
| `reply_to` | The decision's reading of the player's bid | Answers those exact words | Must appear in the player's message after lower-casing, whitespace, and curly quotes are normalized; `none` only for the room opening (`check_reply_to`, `:454`) |
| `scope` (`call`/`exchange`/`feature`) | Kit's judgment of how much the moment deserves | Changes the *kind* of material: answer and stop, a real exchange, or a scene in motion | Opening must be `feature`; `call` only for a `ruling` or `ask_clarification` move, or no focus actor (`:432-438`); flat-reply floors per scope (`check_scope`, `:469`) |
| `kit_focus` | `goal` + `kit_choice` | Acts out Kit's choice through framing, emphasis, which actor tactic gets room, how a ruling is phrased, or a Kit remark when presence allows | 200 characters max, no quoted dialogue, not a verbatim copy of `kit_choice` or the appraisal cause (`:439-446`), literal leak check (`check_brief_public`, `:526`) |

**Other parts of the change:**

- **Instructions.**
  - The private stage (`PRIVATE_INSTRUCTIONS`, `:230`) is told the brief must agree with its goal: "for npc_embodiment or roleplay, the tactic is something the actor tries in answer to the player, not only a price or a fact". It is told how to fill each carrier, and that the actor's objective comes from the actor's motives, not Kit's taste.
  - The performer (`PUBLIC_INSTRUCTIONS`, `:266`) is told to answer `reply_to` and act out `kit_focus`. `kit_focus` "grants no authority over facts, rules outcomes, NPC knowledge or commitments, or the player's choices", and NPCs are never "mouthpieces for Kit's taste or humor".
  - One-pass instructions (`:321`) add "Do not copy improv_read or appraisal text into the performance".
- **Flat-reply floors** (constants at `:182-201`, checked in `check_scope`):
  - A `call` stays within 60 words and 2 segments.
  - An `exchange` needs the focus actor to speak at least 30 words, at least 40 words in non-Kit segments, and at least 2 segments.
  - A `feature` needs at least 80 non-Kit words.
  - The exact Nik reply (a 13-word beat plus 23 dealer words) is rejected. A one-line roll prompt passes as a `call`.
- **Retry reasons.** A rejected performance now hears exactly why, e.g. "Exchange scope: the Dealer spoke 23 words (floor 30)…" (`retry_instruction`, `:637`).
- **Latency** is recorded in a `kit_telemetry` table (`state_context.py:48-52`, `:245-267`) that sits outside the turn's hash, so an identical retry stays idempotent.
  - API mode records time from receipt to commit and per-call seconds.
  - Bridge mode records `prepare_to_commit_s`, which cannot see anything before `prepare`.
  - Read it with `python -m runtime.kit_agent timing --db …`.
- **The bridge (the ChatGPT path) carries all of it.**
  - `prepare` (both modes) returns the schema with the three fields, instructions on filling them, a `performance_limits` summary of the floors (generated from the same constants, `:204`), and a `host_retry` note (`:224`).
  - `decide` returns the brief with the three fields, the performer instructions, and the limits for the chosen scope.
  - When `finish` or `complete` is rejected on the command line, the output includes `decision_fixed`, the specific `retry_instruction`, and how to resubmit (`:879`). The host can therefore fix a turn in one retry instead of guessing.
- **A leak-check fix.** When a player says a secret word ("I accuse him of being a doppelganger"), the quoted `reply_to` would have failed the brief's leak check. The brief check now skips `reply_to`, because those are the player's own words. The performance is still checked.
- **Tests guard the build.** They cover:
  - the exact Nik reply being rejected;
  - a roll prompt accepted;
  - a long call rejected;
  - a misquoted `reply_to` rejected;
  - `kit_focus` reaching the performer while `kit_choice` and the appraisal cause do not;
  - bad `kit_focus` values;
  - opening scope;
  - the retry reason;
  - telemetry staying outside the hash;
  - the staged and one-pass bridge carrying and checking all three fields;
  - the command-line rejection telling the host how to retry.

---

## (d) What this change deliberately does NOT do, and its limits

**Not done, on purpose:**

- Raw `kit_choice` or appraisal is not sent to the performer.
- No appetite meters, relationship scores, or player model. (Step 3 below later added evidence-cited `player_notes`, which are still none of these.)
- The dealer card, source facts, rules, and the generic social event string are unchanged. They are next steps below.
- No model calls added.
- `kit_expression_v1` is not made the default.

**Limits to keep in mind while building on it:**

- **Floors are a guard, not quality.** They stop "price and done". A model can pass them with padding, and a 40-word reply can still be lifeless. Never treat longer as better, and never raise the floors to force life into a scene.
- **The leak check is literal.** It catches "marked deck", not "those cards have a funny shine on the back". `kit_focus` is a new place a paraphrased secret could slip through.
- **One-pass mode can't show cause and effect.** Decision and speech come out together, so the decision may have been written to fit the speech. Staged mode (fixed decision, then a separate performance) is the way to see whether a change to the decision changes the speech.
- **The ruling dodge.** A model that wants to be brief can call a social turn a `ruling` with no focus actor and use `call`.
- **`kit_focus` can be vague.** "Keep it interesting" passes every check. Only reading the turn tells you whether the focus was specific and was acted out.
- **Kit's voice can leak into NPCs.** The instructions forbid it; no code detects it.

---

## (e) Next build steps, in order

Each step uses the same pattern: **private source → public carrier → performer instruction → validator check → test.**

**Status (branch `kit-memory-relationship`):** steps 2 and 3 are **done**; steps 1, 4, and 5 are still open. Each done step ends with a *Built* note naming where the pattern lives.

1. **Replace the generic social event with the player's actual action.**
   - *Now:* `Room6CAdjudicator.resolve` sets every social turn's event to "You address the figures at the card table." (`kit_agent.py:120`).
   - *Build:* make the social event a faithful public restatement of the declared action (for example, `Nik says: "<exact words>"`, trimmed to the 500-character event limit checked at `:387`). Keep the full text in the event evidence.
   - *Carrier:* the event is already public and already reaches the performer as `accepted_public_event`.
   - *Check:* the existing "copy observed_event exactly" rule now forces the appraisal to be about what the player actually did.
   - *Tests:* the social event contains the player's words, and the idempotency test's expected evidence string is updated.
2. **[DONE] Put Kit's choices into memory, and pick memories by relevance.**
   - *Now:* episodes save the goal, move, and brief (so `kit_focus` is already saved) but not `kit_choice` or the player's bid (`state_context.py:212-219`). Decisions get the last 8 episodes by recency (`kit_agent.py:575`, `:745`, `:802`).
   - *Build:*
     - Save `improv_read.kit_choice` and `player_bid` in each episode. Episodes are private, so this is safe.
     - Replace `[-8:]` with a small selector: always keep the last 2 episodes, then add those that share the current actor, story anchor, or meaningful words with the player's action, up to 8.
     - Add one optional brief carrier, `callback`: a short quote of an earlier *public* moment (from `public_history`) that this turn picks up, or `none`.
   - *Check:* `callback` must appear in the public history, the same way `reply_to` must appear in the player's words, and `memory_refs` stay limited to real episode IDs.
   - *Tests:* a relevant earlier episode is selected over a more recent irrelevant one; `callback` must quote public history; private episode text never reaches the performer.
   - *Built:*
     - **Private source.** Each episode now also saves `player_bid`, `kit_choice`, `actor_ref`, `story_anchor`, and `story_basis` from the `improv_read`, and the store keeps 24 episodes (`_commit` in `state_context.py`).
     - **Selector.** `select_episodes` (`kit_agent.py`) always keeps the last 2 episodes. It then scores earlier ones and adds the best, up to 8. The score counts meaningful words shared with the action (weighted most), the actor the action names or the conversation is already with (`ACTOR_ALIASES` maps "dealer" to the dealer's id), and the active level or campaign thread (not the generic scene). Episodes that score zero are left out, not padded in. `kit_memory` runs the same selection in `prepare`, `decide`, and `complete`, so `memory_refs` are checked against exactly what Kit was shown. Each selected episode also carries that turn's public `spoken` text, so Kit can quote it.
     - **Carrier.** `public_brief.callback`, required in the schema, is a short exact quote or `none`.
     - **Checks.** `check_callback`: at most 160 characters, at least two words including a distinctive one, and it must quote the player's words, the accepted event, or a spoken line from a turn **listed in `memory_refs`**. So a callback always has a private reason ("I remembered turn X") and a public origin ("the player saw this"). `check_callback_used` then rejects a performance that shares no meaningful word with the callback. The brief's leak check skips `callback`, just as it skips `reply_to`, because it is a verified quote of words already seen or said.
     - **Performer.** The performer receives the callback and a `callback_source` (that public line and the player's words on that turn, never the episode's private reading). It is told to let the moment visibly return through an actor who was there reacting from their own motives, a returning detail, or Kit's framing, without re-quoting it or adding facts.
     - **Tests:** `tests/test_kit_memory.py` (`EpisodeMemoryTests`, `CallbackTests`).
     - **Limit:** the used-callback check is a floor. One echoed word passes. Whether the callback mattered is judged in play.
3. **[DONE] Add a minimal player relationship built from recent history, before any appetite meters.**
   - *Build:* a short list of `player_notes` in Kit's state. Each note is an observable pattern with the turn IDs that show it, e.g. "accepted an NPC's invitation", "tried an audacious physical stunt", or "asked for fewer menus" from explicit feedback. Add a bridge command (e.g. `feedback --text`) so the host can record out-of-character player feedback as a note. No affection scores, no guessed emotions, and old notes can be contradicted by new behavior.
   - *Carrier:* notes go to the private stage only. Their public effect travels through the existing carriers: `kit_focus` (what she chooses to spotlight for this player) and `callback`.
   - *Check:* every note must cite committed turn IDs; the validator rejects a note without evidence.
   - *Tests:* a note needs evidence; feedback is stored and reaches the next decision but never the performer verbatim.
   - *Why not appetite meters yet:* a number that nothing observable reads repeats the `appraisal` mistake at a larger scale. Build appetites only if recent-history notes demonstrably fail to change Kit's choices, and let that failure say which event types an appetite must track.
   - *Built:*
     - **State.** `kit.player_notes` holds at most 8 notes. Each is `{id, source: observed|feedback, note, evidence_turns}`.
     - **Two ways in.**
       - The private decision's new `player_note` field records at most one observable pattern per turn. Its `evidence_turns` are committed turn IDs, or `this_turn`, which is stored as the real ID when the turn commits. `replaces` retires an observed note that new behavior contradicts.
       - The bridge command `feedback --text "…" [--evidence TURN_ID] [--replaces nX]` (`KitChatBridge.feedback`, `Runtime.record_player_feedback`) records the player's out-of-character comment verbatim. It cites the latest committed turn by default.
     - **Feedback is a committed change.** It becomes an append-only `player_note` ledger event and a new revision, so a turn prepared before it must be prepared again. Retrying the same comment about the same turn does not duplicate it.
     - **Feedback outranks inference.** Only new feedback can replace feedback. When the list is full, the oldest *observed* note is dropped first.
     - `notes` prints the list for the host.
     - **Checks** (`check_player_note`, `_add_player_note`):
       - every note needs 1–4 committed turn IDs as evidence;
       - notes are 1–300 characters;
       - ratings are rejected (`7/10`, `%`, "score", "meter", "affection", "rating");
       - `replaces` must name a real note.
       The same rules run when the decision is checked and again inside the commit transaction.
     - **Carrier.** Notes reach `kit_state.player_notes` in the private stage only. They are hidden by `--no-memory`. Their public effect travels through `kit_focus` or `callback`. `check_plan` rejects any brief direction field that copies a note's text (20 or more characters) verbatim.
     - **Tests:** `tests/test_kit_memory.py` (`PlayerNoteTests`).
     - **Migration.** `STATE_SCHEMA_VERSION` is 2. `upgrade_state` runs on every `load`: it adds an empty `player_notes` and fills missing episode fields with `None` (unknown, not guessed). Stored snapshots are never rewritten; the next commit saves the new shape. A decision fixed before the upgrade (no `callback` or `player_note`) can still finish. Tests: `MigrationTests`.
     - **Limit:** code cannot tell whether a note is a fair reading of the player, or whether `kit_focus` really reflects one. Check that in play (section f).
4. **Loosen the dealer card's pull toward the toll.**
   - *Now:* the card says he "can turn a courteous invitation into a blunt price" (`tests/fixtures/level_01_area_06c.json:26`); his public objective lists "the passage bargain" (`:28`); his immediate goal is control (`:109`).
   - *Build:*
     - Rewrite the card so the price is one move among several. He sizes up a visitor, wants to learn what they are worth to him, and prefers a game where he controls the deck.
     - Answer the visitor's actual words before naming terms. Keep the source facts (10 gp toll, marked deck, rivalry) intact.
     - Pattern for future cards: state what the actor wants *from this visitor* and two or three tactics. Never state a default line.
   - *Carrier:* the actor card is already public and reaches the performer.
   - *Check:* no code can judge this. Check it in play (section f): does the dealer answer `reply_to` before any price?
5. **Let the bridge's one-pass path honor the Kit expression profile.**
   - *Now:* only staged `decide` accepts `performance_variant='kit_expression_v1'` (`kit_agent.py:737`). One-pass `prepare`, which is the ChatGPT live path, always uses the default instructions. The standalone API adapter hardcodes them too (`:379`).
   - *Build:*
     - Add `performance_variant` to `prepare(one_pass=True)` and to the `prepare` CLI. Build the one-pass instructions from the chosen variant, and store the variant in the pending body so `complete` records which one ran.
     - Pass the variant through `OpenAIResponsesModel.perform` as well.
   - *Check:* the variant name is on the fixed list.
   - *Tests:* one-pass instructions include `KIT_EXPRESSION_V1` only when chosen; the input and schema are unchanged; the variant is recorded.

After these, the larger items in `expressed-performance-pipeline.md` still apply: ingest player-supplied rolls, add typed social events for real offers and promises, and replace the area 6c enums (`kit_agent.py:72`, `:155`, `:169`) with a general scene adapter so a second room can be built.

---

## (f) How to check your own work while building (in ChatGPT, through the bridge)

Use the bridge exactly as the player would experience it. No API key is needed.

1. **Run the unit tests after every change** (`python -m unittest discover -s tests -p 'test_*.py'`). For each new carrier, add three tests: it reaches the performer, its private source does not, and the validator rejects a violation.
2. **Play a short fresh room.** Run `init` on a new database, the opening, Nik's greeting ("Hi, I'm Nik. I wasn't expecting to find people gambling. Whats going on here?"), then a follow-up that pushes back, using `prepare --one-pass` / `complete`.
3. **Read only the spoken text first.** Answer these before looking at any trace:
   - Did the reply answer the player's actual words?
   - What does the dealer want, and how is he trying to get it?
   - What did Kit choose to spotlight, and can you name it without the trace?
   - Could this line appear in any room with any NPC?
   - Did the dealer sound like himself, not like Kit?
4. **Then open the trace** (`python -m runtime.kit_agent trace --db …`) and hold `kit_focus` against the spoken turn. Point to the sentence that acts it out. If you can't, the carrier failed on that turn. Tighten `kit_focus` wording or the performer instruction, not the floors.
5. **Check cause and effect in staged mode.**
   - Copy the database (`cp kit-06c.sqlite /tmp/a.sqlite`, `cp kit-06c.sqlite /tmp/b.sqlite`). Prepare the same action in each, and `decide` with the same plan except a different `kit_focus`.
   - Write each performance from its packet. If the two performances are interchangeable, `kit_focus` isn't doing work yet.
6. **Check memory.**
   - Play a turn that should matter later (e.g. Nik boasts about a lucky coin), then several unrelated turns, then a turn where it could matter ("Deal me in; my lucky coin is my stake."). In the `prepare` packet, confirm the coin episode was selected even though it is no longer among the last few.
   - If the decision uses a `callback`, point to the sentence where the moment returns, and check that the actor who reacts to it was actually there.
   - Repeat on a copy with `prepare --no-memory`. Remember the public dialogue history is still visible there.
   - **Check the relationship.** Record out-of-character feedback with `feedback --text "…"` between turns, then prepare the next turn fresh. The note should appear in `kit_state.player_notes`, and the next `kit_focus` should change in a way you can name. The feedback text itself must never appear in the performance packet or the spoken turn. Use `notes` to see what Kit has recorded.
7. **Check a narrow turn stays narrow.** Ask for a roll or a rule. The reply should be a short `call` with no chatter.
8. **Watch rejections and time.** `python -m runtime.kit_agent timing --db …` shows `prepare_to_commit_s` and rejected attempts. Repeated rejections mean the host isn't reading `performance_limits` or the instructions; fix that before anything else, because every retry costs the player time.
9. **Never show the player a trace, a brief, or a rejection message.** Show only `spoken`.
