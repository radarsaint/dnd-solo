# Kit's Area 6c Play Slice

**Status:** Executable, bounded integration experiment. The first live room exchange failed the player's pace and personality test; see [Nik's first playtest record](../../tests/playtests/2026-09-26-area-06c-nik.md). The [voice-spec live test](../../tests/playtests/2026-09-29-area-06c-voice-spec-nik.md) found somewhat better dialogue but failed on a contradictory Kit aside and invented gambling rules that did not make the marked deck playable. No blind preference score yet.

## Play with Kit in this ChatGPT workspace (no API key)

Ask the assistant to start Kit's area 6c room, then give Kit an action in ordinary chat. The assistant uses its current model to run the private decision and public performance stages. The repository must be available to the assistant with Python 3.10+ and shell access; a plain chat without these tools cannot run the SQLite room.

For live chat, the shorter one-pass procedure is an experiment. From the repository root:

```sh
python3 -m runtime.kit_agent init --db kit-06c.sqlite
python3 -m runtime.kit_agent prepare --opening --one-pass --db kit-06c.sqlite
python3 -m runtime.kit_agent complete --db kit-06c.sqlite --turn-id ENTRY_ID --input-file /tmp/kit-entry.json
python3 -m runtime.kit_agent prepare --one-pass --db kit-06c.sqlite --action 'I pull up a chair and ask the stakes.'
```

`prepare --opening --one-pass` stages the **initial room introduction** before any player action. Its performance needs narration and a dealer utterance. Complete it using the returned entry ID and a combined JSON object, then show only its `spoken` field. It is saved as a scene-entry turn, so the first player response has its public words in history. An opening cannot be staged after a turn has committed. For a fresh room after an earlier turn, initialize a new test database; a previously initialized database retains its original fixture.

For ordinary turns, `prepare --one-pass` returns a turn ID, private decision context, a separate player-visible performance base, instructions, and a combined JSON schema. The assistant writes a single object with `decision` and `performance` to a temporary file, then calls:

```sh
python3 -m runtime.kit_agent complete --db kit-06c.sqlite --turn-id TURN_ID --input-file /tmp/kit-turn.json
```

`complete` validates the decision, fixes it for the pending turn, checks the speech, and commits the accepted event, Kit episode, and transcript together. A rejected performance leaves the world uncommitted and keeps the decision fixed for a retry. Every `prepare` response includes `performance_limits` (the flat-reply floors for `call`, `exchange`, and `feature`) and a `host_retry` note. Fill the brief's `reply_to` (verbatim player words), `scope`, and `kit_focus` as the instructions describe. If `complete` or `finish` is rejected, the error JSON carries `decision_fixed` and a specific `retry_instruction`; resubmit a corrected performance for the same turn ID, with the identical decision for `complete`. See [Kit's expression gap](kit-expression-gap.md). It saves one model/tool round trip compared with the staged route. **The model produces both parts in one output, so this route does not prove that the private decision caused the spoken performance.** The first live exchange took 81 seconds with the staged route; no end-to-end speed improvement has been measured yet.

**Packet size (branch `kit-slim`).** Bridge commands (`prepare`, `decide`, `finish`, `complete`, `abandon`, `feedback`) print compact JSON; pass `--pretty` to indent it for reading. On a one-pass turn whose event changes the player view (a card play, a new detail), `input.public.player_view_after_event` is sent as changes to `input.private.dm_context.player_perceivable`: `set` (new value at a dotted path), `appended` (items added to a list), and `removed`, so the table's unchanged rules, powers, and canon ledger are not repeated. The decision's episodes omit `event` (always equal to `public_event`), and an episode whose public words are already in `dialogue_history` says `same as dialogue_history[i].spoken` instead of repeating them. Validation always reads the full view and memory. Measured on the fourth turn of a seeded card game, the printed one-pass packet fell from 103.8 KB to 69.9 KB; the behavior rules, instructions, schema, and checks are unchanged.

For causal evaluation, use the original staged protocol. Run `prepare` without `--one-pass`, create the private plan JSON, and call:

```sh
python3 -m runtime.kit_agent decide --db kit-06c.sqlite --turn-id TURN_ID --input-file /tmp/kit-plan.json
```

`decide` validates and fixes the plan, then returns a public performance packet and speech schema. Create the speech JSON and call:

```sh
python3 -m runtime.kit_agent finish --db kit-06c.sqlite --turn-id TURN_ID --input-file /tmp/kit-speech.json
```

The assistant shows the player only the `spoken` field from `complete` or `finish`, never the private packet or `trace`. Pending stages survive a Python process restart. A stale revision leaves the world turn uncommitted. `init` refuses to overwrite an existing session; use `view` to resume. Load the player's sheet once with `character --sheet <file>` (any `character_sheet_v1` JSON; see `runtime/pc_sheet.py`); every check reads its bonuses and passives from it. When the PC's passive meets the DC, the check succeeds without a roll. Otherwise a player's own roll written in the action ("I rolled 14 + 3 = 17") is used, else the session seed rolls. With no sheet and no stated roll, the check pauses without consuming a turn. `--perception`/`--insight`/`--sleight-of-hand` on `prepare` remain as host overrides only. Never silently reroll a result. `--no-memory` on `prepare` hides previous Kit episodes and player notes for an ablation.

When the player says something out of character about how the game is going ("fewer menus, please", "more of the dealer"), record it between turns. Do not show the result to the player:

```sh
python3 -m runtime.kit_agent feedback --db kit-06c.sqlite --text 'Fewer menus of options, please.'
python3 -m runtime.kit_agent notes --db kit-06c.sqlite
```

`feedback` saves a private note that cites the latest committed turn (pass `--evidence TURN_ID` to cite another). It commits a new revision, so prepare the next turn afresh. Kit's decision stage sees the note; the performer never does. Its effect can reach the player only through `kit_focus` or `callback`.

Both chat paths use Kit's table-voice performer instructions (`kit_expression_v1`) by default: `prepare --one-pass` fixes the variant when the turn is staged, and staged `decide` applies it to the performance packet. For the baseline in a [Kit identity comparison](../personality/kit-personality-implementation.md), pass `--performance-variant current` to `prepare --one-pass` or to `decide`. The variant changes only the performer instruction and leaves the accepted event, plan, public packet, schema, and validators unchanged. Each committed turn records `performance_variant`, which `trace` shows. Prepare isolated copies of the same room snapshot for a fair comparison. The voice failed its first live test on this branch and has no blind quality score; see the [playtest record](../../tests/playtests/2026-09-29-area-06c-voice-spec-nik.md).

These chat-host paths need **no** `--model` choice and **no** `OPENAI_API_KEY`. The commands are a protocol for the assistant, not steps the player has to type. The Work interface may show tool/progress activity; a dedicated player surface is needed to hide it.

## The `play` command: not used, do not run

`python3 -m runtime.kit_agent play` calls the paid OpenAI Responses API. It is not how Kit is played and must not be run: play goes through the chat bridge above (`prepare`/`decide`/`finish`, or `prepare --one-pass`/`complete`), with no model choice and no API key. The command is kept only as legacy code.

Examples: “I pull up a chair and ask the stakes”; “I study the tiny dwarves in the carving”; “I look inside the tub”; “I try to tip the tub”; “I question their fangs”; “I leave by the south door.” The text router is conservative and recognizes only a small set of room actions. Conversation is open ended; unsupported physical actions and combat pause with an explanation and make no state change.

For a developer to inspect Kit's **private** decision records after play:

```sh
python3 -m runtime.kit_agent trace --db kit-06c.sqlite
```

Do not show `trace` or `runtime.state_context context` to a player during a blind playtest; both expose private state or source information.

## What each turn does

1. The fixture router resolves a bounded action. A plain look ("I look at the fresco") is free description and never finds a hidden claim; an active search or read targets one hidden claim by its `subject_words` (the carving's key at DC 13, the disguise at DC 14, the marked deck at 13: the dealer's flat 10 + Sleight of Hand) and can reveal only that claim. A passive that meets the DC succeeds without a roll; otherwise the PC rolls d20 + the sheet's bonus. Any check the source gives no DC uses 10 + floor(floor level / 3). A lie read is the lie rule (flat 10 + Deception), Stealth rolls against the best present passive Perception, and a failed model call cannot reroll the same uncommitted check.
2. `Runtime.preview` validates provisional events and produces the resulting player projection. The accepted event is fixed before Kit plans.
3. The private decision stage sees the canonical personality core, bounded DM room context, relevant Level 1 pressure, the campaign through-line boundary, relevance-selected Kit episodes (the last two, plus earlier ones sharing the actor, story thread, or words with the action), evidence-cited player notes, the last four public dialogue turns, and the accepted event. A [reusable scene-discernment read](scene-discernment.md) selects a player bid, an eligible story basis (or none), a live actor and established goal (or none), and Kit's reason for foregrounding the collision. It also records her event appraisal, move, tone, and table-presence choice. The staged chat and API modes fix this decision before a separate performance generation. The one-pass mode validates and saves the decision before checking speech, but both are generated together.
4. The public performance packet contains the player projection, accepted event, prior **public** dialogue, personality core, a checked brief with objective, tactic, visible cue, player opening, `reply_to` (a verified quote of the player's words), `scope` (`call`/`exchange`/`feature`), `kit_focus` (Kit's public-safe visible choice, derived from her goal and `kit_choice`), and `callback` (a verified quote of an earlier public moment from a turn Kit cites in `memory_refs`, with its public source line, or `none`), plus a curated, public-safe actor card and entry frame. It omits hidden room facts, actor secrets, and the private appraisal text. Its structured segments distinguish Kit, narrator, dealer, and other card players. The API mode uses a separate model request. In a single assistant chat, the same model has already read the private stage, so the packet boundary is **not** a hard context isolation boundary.
5. A limited output check catches literal secret leaks and mismatches between chosen presence and performance. A scope-based flat-reply guard rejects, for example, an `exchange` whose focus actor says fewer than 30 words; a `call` must stay short. These are floors against flat replies, not quality judgments (see [Kit's expression gap](kit-expression-gap.md)). A rejected performance's retry names the failed check. Per-turn timing is stored outside the turn hash; inspect it with `python3 -m runtime.kit_agent timing --db kit-06c.sqlite`. Accepted speech, world events, and Kit's episode are committed together with revision and turn-ID checks. A rejected or stale result commits nothing.

The code borrows FAtiMA's event, appraisal, memory, and high-level action distinction; it does **not** port FAtiMA's C# toolkit or prove its emotional model has been reproduced. The model chooses the appraisal and move; deterministic rules constrain the world outcome. The staged chat protocol fixes the decision before performance. The one-pass option is a speed experiment with weaker evidence for causal order.

The dealer's card and voice are **one room's authored inputs**. The private read in `runtime/scene_discernment.py` is the reusable step that connects a player's current move, active story pressures, an actor's own aim, and Kit's personality before any performance brief is written. A different room supplies its own actors and story references; the scene module has no dealer or area 6c assumptions. Its eligible references can be validated, while their dramatic relevance and the quality of the resulting improv still require human playtests.

## Performance method and limits

This pass uses several documented ideas as design constraints, not as a claim that their systems were implemented here:

| Precedent | Applied in area 6c | Boundary |
| --- | --- | --- |
| [Mateas and Stern's *Façade*](https://ojs.aaai.org/index.php/AIIDE/article/view/18722) organizes reactive character actions into dramatic beats. | A scene-entry framing beat and a per-turn tactic/action/opening give the dealer something to do with a player's interruption. | This slice has no *Façade* drama manager or authored joint-behavior library. |
| [Evans and Short's *Versu*](https://cs.uky.edu/~sgware/reading/papers/evans2014versu.pdf) lets characters choose actions within recurring social practices; [Short's account of conversation](https://emshort.blog/2013/02/26/versu-conversation-implementation/) treats talk and other activity as concurrent, and remarks as interpretable by other participants. | The room keeps the card game and passage negotiation active during talk; the dealer responds to what the player actually says while a card or another player's small reaction may change the exchange. | There is no autonomous social-practice simulation or persistent NPC belief update in this slice. |
| [Comme il Faut](https://ojs.aaai.org/index.php/AIIDE/article/view/12454) and [Social Play in Non-Player Character Dialog](https://ojs.aaai.org/index.php/AIIDE/article/view/12838) represent reusable social interactions and open player participation across steps. | The performer has an invitation that the player may take, refuse, question, or redirect; one dealer monologue cannot silently complete a bargain. | We have a prompt-level scene beat, not CiF's social rules or an implemented dialogue planner. |
| [Justin Alexander's NPC scene method](https://thealexandrian.net/wordpress/48874/roleplaying-games/ptolus-running-the-campaign-roleplaying-npc-scenes) uses a specific objective, tactics, and a physical mannerism to make characters playable. | The dealer has a stable vocal cadence, diction, card-handling touchstone, and a turn-specific tactic, while Kit has her own separately labeled table voice. | The stage-style drawl is an **authored interpretation**, not an accent or vocal trait stated by the adventure. Text can indicate and enact a voice, but cannot literally sound different without audio. |

The first live result named an `npc_embodiment` goal in private but gave the player two flat sentences. For this pass, a valid *plan* must supply concrete directions (now including a quoted `reply_to`, a `scope`, and `kit_focus`), and a valid *opening* must be a `feature` with narration and a dealer utterance. Those checks cannot judge whether the words are funny, seductive, threatening, well timed, or recognizably Kit's. Do not mandate a monologue or accent every turn: the player needs a responsive actor, an intelligible social situation, and room to interrupt. Measure whether a blind player can identify the dealer's voice, objective, and possible next moves across several exchanges. The [claims-and-knowers live test](../../tests/playtests/2026-09-29-area-06c-claims-nik.md) failed to make the room's purpose evident and exposed further NPC, activity, description, equipment-condition, and latency failures. Its prepare-to-commit timings omit earlier host work; complete input-to-display latency remains unmeasured.

## Scope and evaluation

**Since playtest 03** (`kit-expression-gap.md`, sections i and j):

- An unquoted reply to an NPC's question routes as speech. Only a clearly declared physical action still asks for a ruling.
- Every Kit aside quotes what it reacts to.
- Detail questions go through the detail oracle and the canon ledger.
- Prices come from the source, the DMG, the SRD 5.1 tables, or Brendon's magic item formula, or they stay unpriced.
- Once a card game is declared, it is a runtime procedure: at 6c, twenty-one (blackjack) or one check a round, the player's choice (Brendon's table calls, issue #45), with the marked deck, watch and accuse, and a persisted wager. The passage toll is its own exchange with persisted state (`runtime/kit_toll.py`): pay, haggle, refuse (with consequences), put off, or play for it. Bonuses and passives come from the loaded sheet (`character --sheet`), or give your own roll in the action ("I rolled 14 + 3 = 17"). NPCs never roll: each contest is their flat 10 + skill.

This slice supports conversation and a few explicit room interactions. It stores any loaded character sheet (`character --sheet`), but has no complete 5e rules, initiative/combat, validated NPC promises or inventory transfer, pathing beyond the south door, or background faction simulation. Social dialogue is retained as transcript and Kit memory; material NPC bargains need a future state transition before they can be authoritative.

The public packet lacks private facts and a small literal-leak check rejects known phrases, but this **does not guarantee** that free-form prose cannot imply a secret or invent a new fact. In chat-host mode, the assistant still has access to the private planning context. Human review and adversarial model tests are required before treating the output as source-safe. The model may also choose an unconvincing reaction or flat dialogue. The automated tests use a fake model and one mocked API response; they verify orchestration and rollback, not humor or personality quality. The chat tool transcript may expose private packets to a person inspecting tool calls, so a blind player playtest needs a separate player-facing surface.

Use [the area 6c personality protocol](../../tests/scenarios/level-01-area-06c-uktarl.md) for multi-turn play, private-trace audit, memory ablations, blind player preference, and eventual human-DM comparison. The `--no-memory` flag hides previous episodes from Kit's planning call for an ablation without erasing the saved session.
