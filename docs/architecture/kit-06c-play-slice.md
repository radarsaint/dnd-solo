# Kit's Area 6c Play Slice

**Status:** Executable, bounded integration experiment. It has automated backend tests; no live model playtest or entertainment score yet.

## Run it

Requires Python 3.10+, an OpenAI API key available to the process as `OPENAI_API_KEY`, a model ID available to that key, and access to the Responses API. From the repository root:

```sh
python -m runtime.kit_agent init --db kit-06c.sqlite
python -m runtime.kit_agent play --db kit-06c.sqlite --model YOUR_MODEL_ID --perception 2 --insight 1
```

The modifiers above are *example test-character values*. Enter your actual character's Wisdom (Perception) and Wisdom (Insight) modifiers. Omit a modifier and a check using it pauses without consuming a turn. Type an action at `You>`; `/quit` exits. `play` resumes the same SQLite session when restarted. `init` refuses to overwrite an existing session.

Examples: “I pull up a chair and ask the stakes”; “I study the tiny dwarves in the carving”; “I look inside the tub”; “I try to tip the tub”; “I question their fangs”; “I leave by the south door.” The text router is conservative and recognizes only a small set of room actions. Conversation is open ended; unsupported physical actions and combat pause with an explanation and make no state change.

For a developer to inspect Kit's **private** decision records after play:

```sh
python -m runtime.kit_agent trace --db kit-06c.sqlite
```

Do not show `trace` or `runtime.state_context context` to a player during a blind playtest; both expose private state or source information.

## What each turn does

1. The fixture router resolves a bounded action. Area 6c's DC 13 Perception key check and DC 14 Insight disguise check use a d20 and the supplied modifier. A failed model call cannot reroll the same uncommitted check. The source does not set a DC for detecting the marked deck, so this slice pauses that attempt instead of inventing one.
2. `Runtime.preview` validates provisional events and produces the resulting player projection. The accepted event is fixed before Kit plans.
3. A private model call sees the canonical personality core, bounded DM room context, relevant Level 1 pressure, the campaign through-line boundary, recent Kit episodes, and the accepted event. It records the event, affected drive, appraisal with cause/target/strength, referenced memories, move, tone, and table-presence choice. This record is made before performance.
4. A separate public model call sees the player projection, accepted event, prior **public** dialogue, personality core, and a checked public brief for the chosen move. It does not receive hidden room facts, actor secrets, or the private appraisal text. Its structured segments distinguish Kit, narrator, dealer, and other card players.
5. A limited output check catches literal secret leaks and mismatches between chosen presence and performance. Accepted speech, world events, and Kit's episode are committed together with revision and turn-ID checks. A rejected or stale result commits nothing.

The code borrows FAtiMA's event, appraisal, memory, and high-level action distinction; it does **not** port FAtiMA's C# toolkit or prove its emotional model has been reproduced. The model chooses the appraisal and move; deterministic rules constrain the world outcome. Two calls make the selected move available to a separate performer, so the private trace is not simply written afterward to justify finished dialogue.

## Scope and evaluation

This slice supports conversation and a few explicit room interactions. It has no character-sheet store, complete 5e rules, initiative/combat, validated NPC promises or inventory transfer, pathing beyond the south door, or background faction simulation. Social dialogue is retained as transcript and Kit memory; material NPC bargains need a future state transition before they can be authoritative.

The performer lacks private facts and a small literal-leak check rejects known phrases, but this **does not guarantee** that free-form prose cannot imply a secret or invent a new fact. Human review and adversarial model tests are required before treating the output as source-safe. The model may also choose an unconvincing reaction or flat dialogue. The automated tests use a fake model and one mocked API response; they verify orchestration and rollback, not humor or personality quality.

Use [the area 6c personality protocol](../../tests/scenarios/level-01-area-06c-uktarl.md) for multi-turn play, private-trace audit, memory ablations, blind player preference, and eventual human-DM comparison. The `--no-memory` flag hides previous episodes from Kit's planning call for an ablation without erasing the saved session.
