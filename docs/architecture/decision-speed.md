# Faster decisions, same or better judgment

**Status:** Design note, 2026-10-04. Nothing here is built. It sits beside the [guard consolidation plan](guard-consolidation-plan.md) (step 9 already names the static-text cut) and the [expression pipeline](expressed-performance-pipeline.md) (quality stays the release gate).

**What this is for.** Live turns are slow because Kit is asked to author a large, exact JSON decision before anyone hears her. The Python that adjudicates the turn is already fast. The suggestions below cut the copying, the closed-form carriers, and the instruction text that does not change the judgment. The judgment itself stays, and a few of the cuts make it harder for a decision to contradict the scene.

## Where the time goes

The engine is not the wait. `scripts/README-kit-batch-runner.md` puts prepare plus complete at about 0.3 seconds on the 2026-10-03 baseline. The player-facing waits on record are the host writing the decision and the performance: 81 seconds for the first staged exchange, then 136, 133, and 97 seconds prepare-to-commit on the voice-spec run. Those intervals include host authoring. They are still the pace the table feels.

A fresh one-pass packet, measured from `start` on current main (the room loader is in), is mostly text that does not depend on what the player just said. The same instructions and schema go out for area 6c and for the synthetic watchroom.

| Piece | 6c opening, sheet loaded | Watchroom approach |
| --- | --- | --- |
| One-pass instructions | 23.1 KB | 23.1 KB |
| One-pass schema | 8.4 KB | 8.4 KB |
| Personality core | 17.8 KB | 17.8 KB |
| `dm_context` | 11.8 KB (`dm_only.actors` is 4.7 KB) | 1.7 KB |
| Story brief | 4.6 KB | 1.0 KB |
| `claims_here` | 2.9 KB | absent |
| Public half | 8.9 KB | 0.4 KB |
| **Printed `prepare` object** | **80.5 KB** | **55.4 KB** |

The [2026-10-03 host pass](../../tests/playtests/2026-10-03-gpt-adversarial-16081884.md), on the commit before the room loader, measured emitted packets at 81 KB (opening), 75 KB (table talk), and 86 KB (ordinary social), with about 32 KB of that being instructions plus schema. Current main matches that shape: instructions plus schema are 31.5 KB, and adding the personality core makes 49.3 KB that is byte-for-byte the same on every turn of every room. On the watchroom approach that prefix is most of the packet. The scene itself is the small part.

Inside a scene, the story brief and the actor block sit still until a hook, a threshold, or the cast moves. The new information on an ordinary turn is the player's words, the accepted event, the view diff, due hooks, and the last episodes.

The decision she must emit is smaller than the packet and more expensive than its size. A minimal valid plan, with no claims, no agenda, no detail candidates, and no running plan, is about 1.5 KB for the opening and 1.7 KB for a social line. A real turn adds those blocks. Every field is checked exactly: the accepted event copied character for character, `reply_to` a verbatim substring, the mirror matched to a regex, `kit_focus` forbidden from repeating her own private sentence, detail candidates counted and shaped. `complete` checks that object before it saves the plan. A miss there rejects the judgment and the speech together, and the host writes both again. Once the plan is saved, a speech rejection keeps it. The expensive retry is the decision retry.

The [same host pass](../../tests/playtests/2026-10-03-gpt-adversarial-16081884.md) already saw avoidable retry churn on `table_presence`, `kit_focus`, and `reacts_to`. That is the decision tax showing up at the table.

`PRIVATE_INSTRUCTIONS` is 14.9 KB. From the `DETAIL:` heading to the end is 8.3 KB of procedure (detail, claims, agenda, plan, attitudes, story, PC state). Table talk already drops claims, the story brief, and the agenda from the input. It still receives every one of those headings, plus the full schema, which still requires a `detail` object. A watchroom doorway, which has no claims block and no detail oracle, pays the same headings.

## What actually decides the turn

These are the choices that change what the player gets. They stay in her hands.

- What the player did (`improv_read.player_bid`) and why that collides with a live actor and a pressure that is active here (`connection`, `kit_choice`).
- Which of her goals leads, and the appraisal that goes with it (label, intensity, cause).
- The playable beat: objective, tactic, visible cue, player opening, scope, and a concrete `kit_focus`.
- Who speaks (`actor_ref`), the mood read, and whether she is quiet, brief, present, or in showtime.
- When someone states a claim: the stance and the want behind it.
- When an agenda advance is due: which declared move, or an honest hold.
- When a detail is open: which dealt card, or a real invention when the deck has none.
- When the running plan should change: the beats that changed.

These are carriers and copies. The runtime already knows them, or can derive them from a choice above.

- `observed_event`. It must equal `accepted_public_event` or the decision is rejected.
- `focus_actor`. On an NPC move it must equal `improv_read.actor_ref`.
- `turn_mode` whenever `table_read.mode_hint` is binding: the opening, table talk, a fight round, a room action that is not social talk.
- The mirror's energy, length, and humor. `check_mirror` already forces tight length for a frustrated or bored player, forbids playful humor when the read is tense, frustrated, cautious, or the mode is combat, and forbids no humor when the read is playful or gleeful. The free part is the how-clause.
- An empty `player_note`, and `detail` equal to `NO_DETAIL`, on any turn with no detail oracle.
- A `callback` or `reply_to` that fails because of punctuation rather than because she picked the wrong line.
- Detail candidates, `typical`, `chosen`, owner, and handle when `detail_oracle.status` is `open` and the deal already carries `draw_id`, `entry`, `handle`, and roots. Writing those again is how a detail turn gets long. Picking a `draw_id` is the decision.
- A canon, source, or priced detail. The oracle already names the fact and, for a price, the amount.

## Suggestions

Do them in this order. Each one keeps the checks that protect secrets, player agency, and the accepted event. Each one is a small change to `prepare` and `check_plan`, with the existing tests as the safety net.

### 1. Stamp the copies

If she omits `observed_event`, the runtime writes `accepted_public_event`. If she sends a different string, that is still a rejection: she does not get to overrule the adjudication. The same for an omitted `player_note` (the empty note) and an omitted `detail` when there is no oracle (`NO_DETAIL`). When `mode_hint` is set, an omitted `turn_mode` becomes that hint; a conflicting mode still fails `check_turn_mode`.

`focus_actor` goes away as an authored field. `actor_ref` is the actor. The performer packet already resolves that id to a speaker label.

This removes the "Private decision changed the accepted event" failure and the empty objects she fills in on every turn, including table talk and a card hit. The judgment fields are untouched.

### 2. Choose ids from lists the packet already holds

Closed picks are faster and they are harder to contradict.

- **Callback.** `prepare` lists a few short quotable spans from the episodes she can cite (player line, public event, spoken line). She sets `callback` to `none` or to one span id. The runtime expands it to the quote the performer already knows how to use. An invented past moment cannot pass, which is the current rule, without a verbatim-typing retry.
- **Reply.** She still chooses which of the player's words the turn answers. If her string is not a substring, snap it to the longest substring of `player_action` that it contains. If none exists, reject, as now. The choice of clause stays hers. A comma or an ellipsis does not cost the turn.
- **Open detail.** When the oracle dealt cards, `choice` is a `draw_id` from that hand. She does not rewrite candidates. The card's entry, handle, and roots are the invention. `open_no_deck` still requires her own candidates: that is the turn where she is actually inventing. `canon_supplied`, `source_supplied`, and `priced` are filled by the runtime from the oracle. She records nothing unless she is refusing the oracle, which stays a rejection.
- **Agenda.** An advance names a declared move id from `agenda_here`. A new move, rooted in scene facts and inside the speaker's band, stays available for the case the room did not author. The essay form (`does`, `roots`, `why` repeated for a move the packet already spelled out) is the part to drop.

Quality moves up here, not only speed. The voice-spec live test invented a high-card game beside a marked deck the runtime already knew how to play. A decision that picks a dealt card or a declared move has less room to walk off the scene. The boldness stays in which card and which move.

### 3. Let the mood read write the mirror's three enums

She still reads the mood, and she still writes the how-clause: how this turn answers that energy. The runtime sets energy, length, and humor from the read and `turn_mode`, using the mappings `check_mirror` already enforces, and assembles the carrier string the performer sees.

A frustrated player still gets tight. Combat still gets no playful humor. A gleeful player still gets play back. The regex stop being a reason to throw the decision away. The how-clause is the part that was never determined by the table.

### 4. Send each procedure's instructions only when that procedure is in the packet

| Block in `PRIVATE_INSTRUCTIONS` | Send it when |
| --- | --- |
| `DETAIL:` | `detail_oracle` is present, and only the paragraph for its `status` |
| `CLAIMS.` | `claims_here` is present |
| `AGENDA.` | `agenda_here` is present |
| `PLAN:` | a short always-on line ("omit `plan` to carry it; send the whole plan only when it changes"). The beat format rides along only when `kit_plan` is non-empty |
| `STORY:` | `story_brief` is present |
| `PC STATE:` | always, kept short. It is the rule that stops her asking what the PC is holding |

Table talk already removes the private blocks. It should also remove their headings. A combat round should not sit under a detail-invention procedure it cannot use.

This is the attention cut. Input bytes matter, and so does a model spending the decision on rules that do not apply to the bid in front of her. The hard rules that always apply (the event is already adjudicated, secrets stay secret, she does not narrate the player's choices, Kit just plays) stay in the short preamble.

### 5. Send the stable prefix once per session

Step 9 of the [guard consolidation plan](guard-consolidation-plan.md) is the right mechanism: first turn sends the full static text and stores its hash; later turns send `static: {id, note}` plus a short digest; she echoes `static_id`; a mismatch returns the full text; re-send every 8 turns, after two rejections, and whenever the host passes `--full-static`.

Extend the accounting in that plan. It estimates about 28 KB of instructions and schema. Measured on current main, instructions plus schema are 31.5 KB, and the personality core adds 17.8 KB that the plan did not count. Those three are identical across rooms. The story brief and the actor block are stable for a scene (4.6 KB and 4.7 KB on 6c; about 1 KB and a short `dm_context` on the watchroom approach) and belong in the same prefix, invalidated when the scene, the cast, or the brief's delivered hooks change.

The risk named there is the real one. A chat host that trims the first turn will play from memory and will not error. The digest is what keeps secrecy, player agency, and "Kit just plays" present on the turns that only carry the hash. Log retry reasons. If decision rejections rise after the cache lands, the period drops from 8 toward always-on. The cache is a win only while the echo check is failing closed.

### 6. A bad carrier retries the carrier

After the copies are stamped and the ids are closed, split `complete` the way speech retries already work. If the judgment checks pass and a carrier check fails, save the plan and return `retry_fields` naming the carrier. The host resubmits the same decision with those fields replaced. Today that path exists only after `save_kit_plan`, so a `reply_to` miss or a vague `kit_focus` discards the bid, the tactic, and the claim stance and asks for a new scene read.

The second full write is where a turn picks up a contradiction: she answers a rejection by changing the story, not by fixing the quote. Keeping the judgment fixed is both faster and more coherent. Speech retries stay as they are, including degraded mode after two and abandon-and-prepare after four. Those caps exist so a live table does not wait on a loop. They should apply to carrier retries too.

### 7. Three decision sizes, picked from the action

One required schema currently covers a hit, a ruling, a greeting, and table talk. `prepare` should name the size, and `check_plan` should require only that size's fields.

| Size | When | What she writes |
| --- | --- | --- |
| **Call** | `ask_player`, a ruling, a roll still waiting, table talk | Mood read, scope `call`, move, tone, presence, a short `kit_focus`. Actor `none` unless an NPC is actually answering. No detail, no claims, no agenda, no story anchor. |
| **Procedure** | The event is a card action, a toll step, or a combat blow the runtime already resolved | Who reacts, the tactic for playing that result, tone, scope. The event text is the bid. She does not pick a campaign anchor to decorate a hit. |
| **Scene** | Opening, social bid, a detail question, anything where the collision is the point | The full read: bid, anchor, actor, connection, `kit_choice`, the brief, mood, and claims or agenda or detail when those blocks are in the packet. |

Scene discernment stays the scene size. It is the reusable read, and it is wasted on a turn whose facts are already committed. The procedure size is also the quality guard for cards: narration still has to match `kit_twenty_one` state, and a smaller decision has fewer free sentences in which to invent a second game.

### 8. One consistency check, and no new prose field

The private instructions already say that an `npc_embodiment` or `roleplay` tactic is something the actor tries in answer to the player, not only a price or a fact. Nothing checks it. The first live trace named `npc_embodiment` and then had the dealer state the toll. That is the failure this runtime was built to stop.

Check it against structure that already exists. On those two goals, with a focus actor, the tactic or `kit_focus` has to share a root with that actor's motive, immediate goal, a declared agenda move, or a due hook that actor is raising. A toll line can sit inside that tactic. A toll line that is the whole tactic fails.

This adds a rejection on a bad embodiment turn. Suggestions 1 through 6 remove more rejections than this adds. Do not add a field to carry the check. The brief already has the tactic.

## Leave these in place

The live path stays `prepare --one-pass` and `complete`. The staged path is for proving that a decision caused a performance. Adding that round trip back is how the first exchange reached 81 seconds.

`improv_read`, `kit_focus`, the story brief, and claim stance stay. Play has gone flat when those choices never reached the player, and it has gone wrong when speech invented facts the decision was supposed to have settled. Cutting them would make the packet smaller and the turn worse.

Speech stays behind `complete`. The expression pipeline already records why unvalidated streaming breaks the atomic turn. A faster decision that the player hears before the leak check is a leaked decision.

Scope floors stay. They are the floor under the Nik failure (a short beat and a price, offered as a scene). They are not a length target, and they are not what this brief trims. Trimming them would make the performance faster to write and easier to fail in the way the table already rejected.

The `play` command stays unused. There is one model, this one, and no second call to parallelize.

## How to know a cut worked

Record, on the timing row that already stores `last_rejection`:

- packet bytes, split into static prefix and this-turn input
- decision bytes actually submitted
- rejection class, grouped from the exception string (`observed_event`, `reply_to`, mirror, `kit_focus`, detail, agenda, speech floor, leak)

Replay the turns that already failed in a known way, on the same fixture, and read the spoken result before celebrating the timer:

- Nik's greeting. The dealer pursues an aim. The toll can appear inside that aim. The turn answers his actual surprise.
- A detail question. The answer is a dealt card or a source fact. It is not a new game with house rules.
- A card action. The narration matches the table state. The stake the player named is the stake that resolves.
- Table talk. Kit answers. No NPC advances, no story hook fires, no claim is stated.

Faster is a win when those four still hold and decision rejections drop. A shorter packet that brings back the flat toll line is a regression, whatever the clock says. Blind preference stays the quality gate the expression pipeline already set. This note only says which cuts are safe to make before that gate is run.
