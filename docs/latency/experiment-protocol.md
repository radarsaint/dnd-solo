# Latency experiment protocol (priority 4)

Goal: find where a Kit turn's time actually goes **as the player experiences it**, before
optimizing anything. The engine is ~20 ms. The rest of a turn (the model reading the packet,
the tool round trip, writing the reply) is outside Python and is measured here, never guessed.

Acceptance rule: **a fast-but-wrong turn fails.** A turn counts only if it is mechanically
correct (right state, no invented fact, no leaked hidden fact, the engine committed it) *and*
plays as well as the full-packet turn. Speed never excuses a miss.

## What Python records by itself

Every CLI call that names a save appends one line to `<db>.telemetry.jsonl` next to the save
(git-ignored). Fields: `turn_id`, `session_id`, `host` (`--host` or `KIT_HOST`, else null),
`command`, `engine_ms` and `serialization_ms` (`time.perf_counter_ns`), `packet_bytes` (UTF-8
bytes printed), `packet_sha256`, `packet_mode` (full / layered / compact), `tool_calls` (CLI
calls on this turn so far). `model_wait_ms`, `cache_hit`, `first_visible_ms`, `complete_ms`,
`input_tokens`, `output_tokens` and `retries` are always `null` in these records: Python cannot
see them. `KIT_TELEMETRY=0` turns logging off. It prints nothing and never changes play.

```
python3 -m runtime.kit_agent telemetry report --db kit.sqlite          # medians and p95
python3 -m runtime.kit_agent telemetry note --db kit.sqlite --condition D --run 3 \
    --first-visible-ms 4200 --complete-ms 9100                          # one hand-timed run
```

`telemetry note` writes a separate `kind: manual` record, so hand timings are never mixed up
with Python measurements. The report gives medians and p95 per command and per condition.
(For hosts that can stamp times themselves, see docs/architecture/HOST_TIMING.md.)

## Conditions

Same adventure, same character, same opening, same player line, same model and settings in
every condition. Use the fixture adventure (tests/fixtures/adventures/lantern_ferry.txt) or
one private adventure, never a mix.

| | Condition | What the player-side test does | Isolates |
|---|---|---|---|
| A | No Python | Ask Kit a table question she answers without running anything ("What's your favourite kind of tavern?"). | Host + model baseline |
| B | Python no-op | Ask the host to run `python3 -c "print('ok')"` and then answer in one line. | The tool round trip itself |
| C | Full packet | Start or prepare with the full packet: `start --full ...`, `prepare --one-pass --full ...` | Cost of the ~60 KB packet |
| D | Compact packet | The same with `--compact` on `start` and every `prepare`. | What packet reduction buys |
| E | C and D warm | Repeat C, then D, as later turns in a conversation that already ran the same packet (E-C, E-D). | Prefix reuse / caching |

Compact (`--compact`) holds the operating contract, the active scene, the character's current
state, live constraints and retrieval commands (`persona`, `fetch --part schema|production_layers|area`).
The personality core, the full JSON schema, static catalogs and other areas' DM-only facts are
fetched on demand. The full packet stays the default. Fidelity tests
(tests/test_kit_latency_telemetry.py) check that compact carries every fact the active scene
needs, byte for byte: clues, read-aloud text, reveal holds and hidden-state guards.

Opening sizes on the fixture adventure (location 1, Nik): see the PR description.

## Measuring player-visible time in ChatGPT by hand

ChatGPT gives no timing data, so measure what the player sees.

1. **Pick one method and keep it for the whole series.**
   * Stopwatch: start when you press Enter, mark **first visible** when the first word of Kit's
     reply appears (not "Thinking" or "Analyzing"), and stop at **complete** when the reply
     stops growing.
   * Screen recording (more precise): record the window, then read both moments off the video
     frame by frame. Time from the frame your message appears.
2. **Cold vs warm.** A cold run is a new chat (and a new sandbox). A warm run is a later turn in
   the same chat. Never mix them in one condition; E exists for warm runs.
3. **Order.** Alternate conditions (A B C D, then D C B A, …) instead of running all of one
   condition in a row, so time of day and server load spread evenly.
4. **Record each run** with `telemetry note` (or a spreadsheet with the same columns):
   condition, run number, first_visible_ms, complete_ms, and the correctness check below.
   Leave anything you did not see blank. Never estimate.
5. **Correctness, every run.** Did the engine commit the turn? Did Kit stay in the scene's
   facts (nothing invented, nothing hidden revealed, no DC or bonus shown)? Was the turn as good
   as the full-packet turn? If not, the run **fails**, whatever its time.
6. **How many runs.** Start with **10 runs per condition** to see the obvious gaps. Then run
   **30 or more** for the two or three leading comparisons (usually C vs D, and C vs E-C).
   Report the median and p95, not the mean.

## Reading the results

* A fast, B much slower: the tool round trip is the cost; cut tool calls per turn.
* B ≈ C: packet size is not the problem.
* C much slower than D, and D passes every correctness check: adopt compact for that host.
* C ≈ D: compact is not worth its retrieval risk on that host.
* Warm (E) much faster than cold: prefix reuse works; keep the stable contract first.
* First visible fine but complete slow: output length is the cost, not input.
* Rare very slow turns: look at `tool_calls` per turn and retries in the telemetry report.

Do not compare across hosts or models within one table. During play Kit never reports timings
or any of this to the player; the experiment is run by Brendon, not narrated by Kit.
