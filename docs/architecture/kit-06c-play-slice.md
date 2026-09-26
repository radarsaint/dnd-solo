# Kit's Area 6c Play Slice

**Status:** Executable, bounded integration experiment. It has automated backend tests; no blind player preference test or entertainment score yet.

## Play with Kit in this ChatGPT workspace (no API key)

Ask the assistant to start Kit's area 6c room, then give Kit an action in ordinary chat. The assistant uses its current model to run the private decision and public performance stages. The repository must be available to the assistant with Python 3.10+ and shell access; a plain chat without these tools cannot run the SQLite room.

The assistant's room-host procedure, from the repository root:

```sh
python -m runtime.kit_agent init --db kit-06c.sqlite
python -m runtime.kit_agent view --db kit-06c.sqlite
python -m runtime.kit_agent prepare --db kit-06c.sqlite --action 'I pull up a chair and ask the stakes.'
```

`prepare` returns a turn ID, the accepted room event, Kit's private DM context, the canonical personality, and a JSON schema. The assistant makes the private decision **before** speaking, writes only that schema's JSON to a temporary plan file, and calls:

```sh
python -m runtime.kit_agent decide --db kit-06c.sqlite --turn-id TURN_ID --input-file /tmp/kit-plan.json
```

`decide` validates and fixes the private decision, then returns a public performance packet and speech schema. The assistant writes only the speech JSON to a temporary file and calls:

```sh
python -m runtime.kit_agent finish --db kit-06c.sqlite --turn-id TURN_ID --input-file /tmp/kit-speech.json
```

The assistant shows the player the `spoken` field from `finish`, not the private planning packet or `trace`. Pending stages survive a Python process restart. `finish` commits the accepted event, Kit's episode, and her spoken turn together. A failed validation or stale revision leaves the world turn uncommitted. `init` refuses to overwrite an existing session; use `view` to resume. For a check, supply the character's actual `--perception` or `--insight` modifier to `prepare`. Without it, that check pauses without consuming a turn. `--no-memory` on `prepare` hides previous Kit episodes for an ablation.

This chat-host path needs **no** `--model` choice and **no** `OPENAI_API_KEY`. The three commands are a protocol for the assistant, not steps the player has to type.

## Optional standalone API CLI

For a separate terminal process to call a model on its own, provide a Responses API model ID and `OPENAI_API_KEY`:

```sh
python -m runtime.kit_agent play --db kit-06c.sqlite --model YOUR_MODEL_ID --perception 2 --insight 1
```

The modifiers are example test-character values. Enter an action at `You>`; `/quit` exits. This API mode resumes the same SQLite session when restarted.

Examples: “I pull up a chair and ask the stakes”; “I study the tiny dwarves in the carving”; “I look inside the tub”; “I try to tip the tub”; “I question their fangs”; “I leave by the south door.” The text router is conservative and recognizes only a small set of room actions. Conversation is open ended; unsupported physical actions and combat pause with an explanation and make no state change.

For a developer to inspect Kit's **private** decision records after play:

```sh
python -m runtime.kit_agent trace --db kit-06c.sqlite
```

Do not show `trace` or `runtime.state_context context` to a player during a blind playtest; both expose private state or source information.

## What each turn does

1. The fixture router resolves a bounded action. Area 6c's DC 13 Perception key check and DC 14 Insight disguise check use a d20 and the supplied modifier. A failed model call cannot reroll the same uncommitted check. The source does not set a DC for detecting the marked deck, so this slice pauses that attempt instead of inventing one.
2. `Runtime.preview` validates provisional events and produces the resulting player projection. The accepted event is fixed before Kit plans.
3. The private decision stage sees the canonical personality core, bounded DM room context, relevant Level 1 pressure, the campaign through-line boundary, recent Kit episodes, and the accepted event. It records the event, affected drive, appraisal with cause/target/strength, referenced memories, move, tone, and table-presence choice before performance. In chat-host mode, `prepare` returns this to the assistant and `decide` validates and persists the result; in API mode the model supplies it directly.
4. The public performance packet contains the player projection, accepted event, prior **public** dialogue, personality core, and a checked public brief for the chosen move. It omits hidden room facts, actor secrets, and the private appraisal text. Its structured segments distinguish Kit, narrator, dealer, and other card players. The API mode uses a separate model request. In a single assistant chat, the same model has already read the private stage, so the packet boundary is **not** a hard context isolation boundary.
5. A limited output check catches literal secret leaks and mismatches between chosen presence and performance. Accepted speech, world events, and Kit's episode are committed together with revision and turn-ID checks. A rejected or stale result commits nothing.

The code borrows FAtiMA's event, appraisal, memory, and high-level action distinction; it does **not** port FAtiMA's C# toolkit or prove its emotional model has been reproduced. The model chooses the appraisal and move; deterministic rules constrain the world outcome. The staged chat protocol fixes the decision before performance, so the private trace is not written afterward to justify finished dialogue.

## Scope and evaluation

This slice supports conversation and a few explicit room interactions. It has no character-sheet store, complete 5e rules, initiative/combat, validated NPC promises or inventory transfer, pathing beyond the south door, or background faction simulation. Social dialogue is retained as transcript and Kit memory; material NPC bargains need a future state transition before they can be authoritative.

The public packet lacks private facts and a small literal-leak check rejects known phrases, but this **does not guarantee** that free-form prose cannot imply a secret or invent a new fact. In chat-host mode, the assistant still has access to the private planning context. Human review and adversarial model tests are required before treating the output as source-safe. The model may also choose an unconvincing reaction or flat dialogue. The automated tests use a fake model and one mocked API response; they verify orchestration and rollback, not humor or personality quality. The chat tool transcript may expose private packets to a person inspecting tool calls, so a blind player playtest needs a separate player-facing surface.

Use [the area 6c personality protocol](../../tests/scenarios/level-01-area-06c-uktarl.md) for multi-turn play, private-trace audit, memory ablations, blind player preference, and eventual human-DM comparison. The `--no-memory` flag hides previous episodes from Kit's planning call for an ablation without erasing the saved session.
