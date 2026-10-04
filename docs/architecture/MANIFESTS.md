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

Each manifest is sent in one of three forms:

| Form | When |
|---|---|
| `{"hash": h, "body": {...}}` | the host does not hold any copy: the session's first turn, or the turn after a cache miss |
| `{"hash": h, "base": h0, "diff": [...]}` (room only) | the room changed and the host holds `h0`; each entry sets `value` at `path` or removes `path` (`kit_manifest.apply_diff`). Used only when the diff is smaller than the body |
| `{"hash": h, "cached": true}` | the host holds `h` |

* **No scheduled re-send (PR-T).** Until #96 both bodies came back every 8th prepared turn (`FULL_EVERY`). That
  turn was 60–67 KB (T9 in the replay) and set p95. Now a body is sent only when its hash is new to the host.
  What the host holds is recorded on each layered turn's telemetry (`manifest.held`), so it survives across
  CLI processes.
* **Echo.** Kit echoes both hashes: `"manifest": {"session": h1, "room": h2}`. A missing or wrong echo is
  refused (`ManifestMismatch`) and counts as a **cache miss**: the turn is marked `cache_miss`, and the next
  prepared turn sends both bodies in full. The echo alone proves little (a cached layer carries its own hash,
  Nagatha's #94 review), so it is a consistency check, not the safety net.
* **Rehydrate.** `rehydrate --turn-id T` (Python: `bridge.rehydrate(turn_id)`) returns both bodies in full and
  records that the host now holds them. Kit can ask for it at any time. A lost copy costs one retry, not a bad turn.
* **The safety net: a manifest check.** Every `CHECK_EVERY` = 4 layered turns since the last full session send
  or the last check, and on the turn after one with `REJECT_STREAK` = 2 or more rejections, the packet carries
  `manifest_check`. It holds the first 6 words of one sentence from each of the `instructions`, the `core` and
  the `room`. Kit adds `"check": {key: "<the next 8 words>"}` inside `"manifest"`, copied from the bodies she holds.
  6 of 8 words in place must match (case and punctuation ignored). A failed or missing answer is a cache miss.
  The turn is refused with a pointer to rehydrate, and Kit writes it again from the full bodies.
  * The lines are chosen so that only a host holding the body can answer. The continuation does not appear
    anywhere in the turn delta, and the 6 prompt words occur exactly once in the layer. The choice is
    deterministic per session hash and turn number.
  * The check covers all three things a trimmed chat loses: the invariants, the persona core and the room's DM truth.
  * A check that is never committed (the turn was abandoned) is asked again on the next turn.

### Why a check rather than a staggered refresh

The custom GPT runner trims or summarizes old turns without any signal, so some periodic proof is needed. These
are the options, measured on the watchroom replay (`--manifests`, model time is the labelled estimate):

| Design | Worst steady-state turn | Catches a lost body within | Extra cost on the turn that checks |
|---|---|---|---|
| Full re-send every 8 turns (#96) | 15.7 s (T9, 66.6 KB) | 8 turns, only by luck of timing | +53 KB in |
| Staggered refresh (one layer per turn, spread out) | ~15.6 s (the session body alone is ~53 KB) | 8 turns per layer | +53 KB in on a session turn |
| **Manifest check every 4 turns (this)** | **11.8 s (T7, an ordinary turn)** | **4 turns, and proven, not assumed** | **~+0.5 KB in, ~+0.2 KB out (~0.08 s)** |

The session body is ~53 KB of the ~60 KB opening, so any design that re-sends it on a schedule keeps a ~15 s turn
in the tail. The check costs about a sentence. It also tells you when the copy is really gone, where a blind
re-send only bets that it might be. A host that cannot answer pays one full rehydrate (the same 60 KB, once),
and only when the loss is real.

**Limits.** A model could in principle copy the 8 words from an old summary that kept them verbatim while
losing the rest. With three lines from three different places changing every check, that is unlikely to hold
for long. If the host loses its sandbox (files gone), the database goes with it and the session restarts from
`start`, which sends everything.

## Does the runner carry prior context? (honest answer)

The runner in the repo is the ChatGPT custom GPT (docs/CUSTOM_GPT_SETUP.md). It runs the CLI in Code
Interpreter inside one long chat, so every earlier packet stays in that chat's context.
- **Yes, prior context is carried, but not reliably.** ChatGPT trims or summarizes long chats without
  any signal, and the sandbox resets after it sits idle (the chat survives, the files may not). That is
  the reason for the manifest check and for rehydrate. The echo is only a consistency check.
- **Full packets make it worse.** At ~70 KB each, ten full turns put ~700 KB (~175K tokens) into the
  chat, so earlier turns are pushed out sooner. Layered turns add ~10–25 KB each.
- **Prompt caching is not ours to control there.** The ChatGPT host exposes no caching control.
  Stable-first ordering only helps if the provider caches a matching prefix.
- **The replay's time estimate counts only the new bytes per turn.** It does not model any provider cache.

No other runner (a Discord bot, a room flow) is in this repo. If one is used, the same rule applies: it
must keep the bodies it was sent, or rehydrate.

## Sizes (watchroom replay, `scripts/watchroom_replay.py --manifests`, T0–T10, dice pinned)

| | #96 (main 2804b79) | PR-T |
|---|---|---|
| T9 packet (the old scheduled re-send) | 66,593 B | 13,658 B |
| full-body sends after T0 | 1 session + 1 room | 0 session, 1 room diff (T7, the move into the watchroom) |
| packet median / mean | 14,380 / 21,872 B | 13,658 / 17,232 B |
| e2e median / p95 (model est) | 10.28 s / 15.35 s | 10.30 s / 13.39 s |
| e2e p95 over T1–T10 (steady state, no opening) | 13.99 s | 11.24 s |
| worst steady-state turn | 15.74 s (T9) | 11.79 s (T7) |

The 11-turn p95 still includes T0, the session opening, which has to carry the bodies once (~60 KB, ~15 s).
Every later turn is an ordinary 8–17 KB delta, with ~0.5 KB extra on a check turn (T4, T8).
