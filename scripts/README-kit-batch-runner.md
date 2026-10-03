# Kit batch runner (scripted scenarios, any model, no paid API)

`scripts/kit_batch_runner.py` plays the **player** from a script and hands every **Kit** turn to a DM model through the same bridge a chat host uses (`start`, then `prepare --one-pass` and `complete`). Each scenario gets a fresh `kit.sqlite`. Nobody has to paste lines into ChatGPT.

- Never runs `play`. Strips `OPENAI_API_KEY` from every child process and never reads it.
- The engine's own checks decide everything. A rejected submission is retried the way `host_retry` says: degraded mode after 2 rejections, abandon after 4. The runner records each rejection rather than hiding it.
- Records per turn: the player line, what the engine read it as (`action_kind`, or the stall message), the spoken result, rejections, and wall-clock `prepare_ms`, `dm_ms`, `complete_ms`, and `total_ms`.

## Scenarios

`tests/scenarios/6c_variety.json` holds V1 to V11 from bfdm-corpus `research/kit-evaluation/6c-variety-scenarios.md`. Each turn is one player line, plus an optional `roll` (`{"skill", "total"}`) that the runner appends Avrae-style as `[Skill: I rolled d + bonus = total]`, working the die back from the sheet. Conditions like "If they ask for money" are kept in `when` for the grader. Lines are sent in order whatever Kit said, so a scripted run is comparable from one run to the next.

Sheets resolve from `tests/fixtures/characters/` first, then from any `--sheets-dir` (for example the corpus `6c-variety-sheets/`).

## DM backends

**`command`**: any headless model CLI. The runner pipes one JSON request (`preface`, `packet`, and on a retry `rejection` plus `previous_reply`) to the command's stdin and reads one `{decision, performance}` object from stdout:

```sh
python3 scripts/kit_batch_runner.py --backend command \
  --dm-cmd 'cursor-agent -p --output-format text "Follow the preface in this JSON. Reply with JSON only: $(cat)"' \
  --sheets-dir ../bfdm-corpus/research/kit-evaluation/6c-variety-sheets --out /tmp/kit-batch
```

**`handoff`**: file exchange, for when the DM is an agent in a chat (a Cursor or Grok agent, a cloud agent, or a person). For each Kit turn the runner writes `<handoff>/<scenario>/<step>.a<attempt>.request.json` (the full request) and `.digest.json` (the same request, with long fields equal to the batch's first packet replaced by `"=ref"`; `reference.json` holds that first packet). It writes the path it is waiting for into `<handoff>/WAITING` and blocks until the matching `.reply.json` appears.

```sh
python3 scripts/kit_batch_runner.py --backend handoff --only V1,V3 \
  --sheets-dir ../bfdm-corpus/research/kit-evaluation/6c-variety-sheets --out /tmp/kit-batch
# the DM agent: read $(cat /tmp/kit-batch/handoff/WAITING | sed 's/reply/digest/'), write the reply file
```

The first full baseline (2026-10-03) used `handoff` with Grok as Kit. Its results are in bfdm-corpus `research/kit-evaluation/6c-baseline-2026-10-03/`.

## Output

```
<out>/<scenario>/kit.sqlite      the session (inspect with view / trace / timing)
<out>/<scenario>/turns.jsonl     one record per turn, timings and rejections included
<out>/<scenario>/transcript.md   what the player saw, with per-turn time
<out>/<scenario>/timing.json     the runtime's own prepare-to-commit timing
<out>/summary.json               per-turn outcomes and latency
```

## Grading

`scripts/kit_batch_grade.py <out> --md auto.md --json auto.json` writes one row per turn: what the engine read the line as, rejections, degraded mode, time, and the always-on checks a regex can see (TC-4 numbers in public text, TC-3e food or drink, TC-5b ending on a question). It also writes latency medians and maxes (whole turn, engine only, model only). Judgment checks, such as whether the ruse holds, whether the toll is a real exchange, and whether Uktarl flees as written, still need someone to read `transcript.md` against the table calls.

## Latency caveat

`dm_ms` is the model's time and includes everything the backend does (with `handoff`, the agent reading the digest and writing the reply). Engine time is `prepare_ms + complete_ms` (about 0.3 s per turn on the 2026-10-03 baseline). Compare model latency only within the same backend and model.
