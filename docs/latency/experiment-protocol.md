# Kit latency: experiment protocol

Priority 4 from the Phandelver postmortem and the October 2026 latency research. The goal is a
faster turn that is just as faithful and just as engaging. A fast turn that is wrong fails.

## What Python measures, and what it does not

Every `python3 -m runtime.kit_agent ...` call appends one line to `<db>.telemetry.jsonl` next to
the save (git-ignored). `runtime/kit_telemetry.py` holds the field list:

| Field | Source |
|---|---|
| `turn_id`, `session_id` | The packet's turn id. `session_id` is reused from the file, or set by `--session-id`. |
| `host` | `--host chatgpt` (or env `KIT_HOST`) if the host passes it, otherwise null |
| `command`, `packet_mode`, `exit_code` | The CLI call. `packet_mode` is `full`, `compact`, or `unlayered` (`--full`). |
| `engine_ms` | `time.perf_counter_ns` across the command, minus serialization. Python start-up and imports are not included. |
| `serialization_ms` | `json.dumps` of the reply |
| `packet_bytes`, `packet_sha256` | The exact stdout, UTF-8 |
| `tool_calls` | The number of CLI calls made so far for this turn id (prepare, rehydrate, complete, retries) |
| `model_wait_ms`, `cache_hit`, `first_visible_ms`, `complete_ms`, `input_tokens`, `output_tokens`, `retries` | **Always null.** Only the host or the provider knows these. Never estimate them. Fill them in by hand from the measurements below. |

`python3 -m runtime.kit_agent telemetry report --db kit.sqlite` prints the median and p95 per
command and packet mode, plus tool calls per turn. Set `KIT_TELEMETRY=0` to turn recording off.
Telemetry never changes what the player sees. The host never reports it during play.

## Packet modes

* **full** is the default and is unchanged. The opening sends the whole session manifest
  (personality core, instructions, schema) and the room manifest.
* **compact** is opt-in: `start --compact` records it in the save, and `prepare --compact` applies
  it to one turn. It keeps:
  * the operating contract (instructions, schema, limits, retry note)
  * the whole turn delta: the active scene, character state, reveal, story brief, `first_try`,
    and the read-aloud and clue ids
  * the live constraints
  * the room's hidden facts for the current area and every area one exit away

  It leaves out the personality core, which the host already read at load (`persona` prints
  it), and the hidden facts of far areas, which are listed by id in `far_facts_withheld`.
  `retrieval` names the commands, and `rehydrate --turn-id T` returns both bodies in full.

Lantern Ferry fixture opening (`tests/fixtures/adventures/lantern_ferry.txt`, location 1, the
`start` stdout): full is 57,176 bytes and compact is 38,156 bytes. Most of what is left is the
operating contract (~23 KB of instructions).

**Stable prefix.** Each packet opens with `session_manifest` and then `room_manifest`. The
`start` envelope puts `prepared` before `next_step`, which names the turn id. No timestamps and
no turn ids appear before the room manifest, and the session manifest is byte-identical across
sessions on the same build (tests/test_kit_latency_telemetry.py). Unlayered `--full` packets
(engineering and evals only) still lead with `first_try` by design.

## Conditions

Use the same build, the same chat settings, the same model and reasoning setting, the same
fixture and character, and the same player line in every run. Start each cold run in a new chat.

| | Condition | How |
|---|---|---|
| A | No Python | Ask Kit a table-talk question that needs no tool (e.g. "Kit, what's your favourite monster?"). This is the host and model baseline. |
| B | Python no-op | Have Kit run `python3 -m runtime.kit_agent status --db kit.sqlite` and answer in one line. This adds the tool loop with a tiny result. |
| C | Full packet | `start --room <fixture> --sheet <sheet>` (default full), through Kit's first spoken opening |
| D | Compact packet | The same as C with `--compact` |
| E | Warm C and D | In a chat that already ran C (or D), play 3 turns, then time the 4th `prepare` → spoken turn. Run E-full and E-compact as separate chats. |

## Measuring player-visible time by hand (ChatGPT)

ChatGPT exposes no timings, so measure what the player sees:

1. Use a screen recording (preferred) or a stopwatch. Start when you press send.
2. **first_visible_ms** is when the first word of Kit's reply appears. A "thinking" or tool
   indicator does not count.
3. **complete_ms** is when the reply stops streaming.
4. Note the number of tool calls shown in the reply (the "Analyzed" blocks) and any visible retry.
5. Afterwards, ask in a separate debrief chat, or download `kit.sqlite.telemetry.jsonl` (an
   engineering step, never during play), and copy `engine_ms`, `packet_bytes`, and `tool_calls`
   into the row.

Record one row per run: condition, cold or warm, first_visible_ms, complete_ms, tool calls,
engine_ms, packet_bytes, a **correct** check, and a **quality** note.

## How many runs

* Run each of A–E **10 times** to find the obvious differences. Randomize the order of conditions
  where you can.
* Then run **30 or more** for the leading comparisons (most likely C vs D cold, and E-full vs
  E-compact).
* Report the median and p95, not the mean. Keep cold and warm results separate.

## Reading the results

* If A is fast and B is much slower, the cost is the host's tool loop, not Kit.
* If B and C differ a lot, the large packet (or reading it) costs time.
* If C and D are close, compact alone is not worth it.
* If warm is much faster than cold, prefix reuse is working. Keep the prefix stable.
* If first_visible is fine but complete is slow, the cost is output length.
* For a rare very slow turn, check retries, extra tool calls, and rehydrates (`tool_calls` > 2).

Python time is `engine_ms + serialization_ms`. Everything else is **unattributed model or host
time**. Do not assign it to one component without a host trace.

## Fast but wrong fails

Every timed run also passes or fails on correctness:

* The opening commits on the first complete, with no rehydrate or retry caused by missing content.
* Every clue and read-aloud line the scene offered is available to Kit, and nothing hidden leaks
  (no DCs, no unrevealed facts, no hidden creatures by name).
* No invented rooms, NPCs, or stat blocks. State matches `view`.
* Kit's voice holds. In compact mode, watch for a flatter voice; that would mean the host
  lost the persona it read at load.

A compact run that fails any of these counts as a failure for D, however fast it was.

## Logging a hand-timed run

Record each stopwatch or screen-recording measurement next to the save, so `telemetry report` shows it beside Python's numbers:

```
python3 -m runtime.kit_agent telemetry note --db kit.sqlite --condition D --run 3 \
    --turn-id <turn_id> --host chatgpt --first-visible-ms 4200 --complete-ms 9100 --cache-hit yes
```

Notes are marked `kind: manual` and reported under `manual_by_condition`; they never count as tool calls or mix into the per-command stats. Only the values you give are set; the rest stay null.
