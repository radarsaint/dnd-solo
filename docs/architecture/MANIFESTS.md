# Three-layer packets: SessionManifest, RoomManifest, TurnDelta

`runtime/kit_manifest.py`, plan update #3 PR2. This replaces the earlier "hash + digest" idea in
guard-consolidation-plan.md step 9.

## Layers (stable first, so an unchanged prefix can be cached)

| Layer | Holds | Changes when |
|---|---|---|
| `session_manifest` | `personality_core` (untrimmed), `instructions` (the invariants), output contract (`schema`, `performance_limits`, `host_retry`), `performance_variant` | the code or the voice files change |
| `room_manifest` | the room's static DM truth for the scene: `source_id`, `source_ref`, `map_ref`, `fixture_only`, `level_context`, `campaign_context`, `constraints`, `dm_only` (untrimmed), `missing_production_layers` | the room or area does |
| turn delta (the rest of the packet) | `turn_id`, `first_try`, the move and event, `story_brief` (attitudes, positions, reveal status, live story pressure), memory, history, public side | every turn |

Each manifest is `{"hash": h, "body": {...}}` the first time and `{"hash": h, "cached": true}`
after that. `h` is the first 16 hex characters of the SHA-256 of the canonical JSON. Nothing is trimmed:
`kit_manifest.join(session, room, delta)` gives back the full packet, and a test checks that.

## The host's side

* Echo both hashes with the output: `{"decision": ..., "performance": ..., "manifest": {"session": h1, "room": h2}}`.
  A missing or wrong echo is refused (`ManifestMismatch`), and the refusal says to rehydrate.
  **What the echo does not prove (Nagatha's #94 review).** A cached layer carries its own hash
  (`{"hash": h, "cached": true}`), so the host can copy h back without holding the body at all. The echo
  only catches a host replying to a different turn or session, or one that dropped the field. It cannot
  catch a host that lost or garbled a body. That depends on Kit asking to rehydrate, which isn't
  guaranteed, and on the scheduled full re-send below.
* `rehydrate --turn-id T` (Python: `bridge.rehydrate(turn_id)`) returns both bodies in full. Resubmit with
  their hashes. A lost copy costs one retry, not a bad turn.
* Bodies are re-sent anyway at least every `FULL_EVERY` = 8 prepared turns, and on the turn after one with
  `REJECT_STREAK` = 2 or more rejections. **This re-send is the real safety net.** A lost body is
  stale for at most 8 turns, and a turn that keeps getting rejected gets the bodies back on the next one.
* The live CLI (`start`, `prepare --one-pass`) sends layers by default. `--full` sends the whole packet.
  The Python `KitChatBridge` default (`manifests=False`) and staged evals are unchanged.

## Does the runner carry prior context? (honest answer)

The runner in the repo is the ChatGPT custom GPT (docs/CUSTOM_GPT_SETUP.md). It runs the CLI in Code
Interpreter inside one long chat, so every earlier packet stays in that chat's context.
- **Yes, prior context is carried, but not reliably.** ChatGPT trims or summarizes long chats without
  any signal, and the sandbox resets after it sits idle (the chat survives, the files may not). That is
  the reason for the periodic re-send and for rehydrate. The echo is only a consistency check.
- **Full packets make it worse.** At ~70 KB each, ten full turns put ~700 KB (~175K tokens) into the
  chat, so earlier turns are pushed out sooner. Layered turns add ~10–25 KB each.
- **Prompt caching is not ours to control there.** The ChatGPT host exposes no caching control.
  Stable-first ordering only helps if the provider caches a matching prefix.
- **The replay's time estimate counts only the new bytes per turn.** It does not model any provider cache.

No other runner (a Discord bot, a room flow) is in this repo. If one is used, the same rule applies: it
must keep the bodies it was sent, or rehydrate.

## Sizes (watchroom replay, `scripts/watchroom_replay.py --manifests`)

* Full one-pass packet: ~59–78 KB (mean 68.7 KB).
* Layered: the first turn and each re-send are ~59–78 KB. Other turns are 8–24 KB (median 17.7 KB,
  mean over all turns 24.9 KB with two full sends in 11 turns).
