# Host timing: from the player's message to Kit's first playable line

The engine can time only what runs inside it (prepare, validation, commit). Everything else
happens in the host (the Kit chat or room flow): reading the Discord/Avrae message, building
the prompt, the model call itself, retries, and posting the reply. To see the whole turn, the
host stamps four moments and the engine joins them with its own timings into one breakdown.

## What the host stamps

All stamps are epoch seconds (float, `time.time()` on the host clock). Unknown names are
rejected; a stamp the host does not send stays missing and is named, never guessed.

| Stamp | When the host takes it |
|---|---|
| `received_at` | The player's message reaches the host (Discord event / chat message arrives), before any host work. |
| `model_sent_at` | The host sends the packet to the model. Stamp it per attempt (on `complete`), so every retry has its own pair. |
| `model_done_at` | The model's reply (decision + performance) is back, before the host calls `complete`. |
| `shown_at` | Kit's first playable line is visible to the player. The host stays silent until speech commits, so this comes after `committed_at`. |

The engine records, by itself:

* `prepare_started_at`, `prepared_at`, `runtime_prepare_ms`, `packet_bytes` (on `prepare`);
* per `complete` attempt: `output_bytes`, `validation_ms`, `outcome` (`committed` / `rejected`) and the
  attempt's `model_sent_at` / `model_done_at` if the host passed them;
* `committed_at` when speech commits.

## How the host sends them

Python:

```python
packet = bridge.prepare(line, one_pass=True, host_stamps={'received_at': received})
sent = time.time(); reply = call_model(packet); done = time.time()
result = bridge.complete(packet['turn_id'], reply,
                         host_stamps={'model_sent_at': sent, 'model_done_at': done})
post(result['spoken']); bridge.stamp(packet['turn_id'], shown_at=time.time())
```

CLI (each command takes `--stamp NAME=EPOCH`, repeatable):

```
python3 -m runtime.kit_agent prepare --one-pass --action "..." --stamp received_at=1759581000.12
python3 -m runtime.kit_agent complete --turn-id T --input-file out.json --stamp model_sent_at=... --stamp model_done_at=...
python3 -m runtime.kit_agent stamp --turn-id T --stamp shown_at=...
python3 -m runtime.kit_agent timing           # each recent turn with its "latency"
```

## The breakdown (`turn_latency`, in `timing` as `latency`)

* `end_to_end_s` = `shown_at - received_at`
* `model_s` = sum over attempts of `model_done_at - model_sent_at`
* `retry_s` = time from the first rejected attempt's `model_done_at` to the last attempt's `model_done_at`
  (the cost of rejects; 0 when the first try commits)
* `runtime_prepare_ms`, `validation_ms` (sum over attempts): engine time
* `host_s` = `end_to_end_s - model_s - runtime - validation`, split further into
  `host_before_prepare_s` (received → prepare started) and `host_prepare_to_model_s`
  (packet ready → first model send)
* `shown_after_commit_s` = `committed_at → shown_at` (output/posting time)
* `packet_bytes`, `output_bytes` per attempt, `rejects`, and `missing` (stamps the host did not send)

## Replay baseline without a model

`scripts/watchroom_replay.py` replays the watchroom fixture with a scripted first-try Kit. It
measures engine time and bytes exactly. Model time is an **estimate, not a measurement**: per model
trip, `overhead_s + (packet_bytes/bytes_per_token)/prefill_tps + (output_bytes/bytes_per_token)/decode_tps`
(defaults 1.0 s, 2500 tok/s, 50 tok/s, 4 bytes/token; override with `--overhead-s`,
`--prefill-tps`, `--decode-tps`, `--bytes-per-token`). Each reject repeats a full trip; each stall
or misread costs one short trip (~200 output bytes) for Kit to read the ruling and reword. Use it to
compare builds under the same assumptions; real numbers come from host stamps.
