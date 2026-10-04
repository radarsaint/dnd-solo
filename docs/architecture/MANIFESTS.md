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
| `{"hash": h, "nonce": n, "body": {...}}` | the host does not hold this layer: the session's first turn, or the turn after this layer's nonce came back wrong or missing |
| `{"hash": h, "base": h0, "nonce": n, "diff": [...]}` (room only) | the room changed and the host holds `h0`; each entry sets `value` at `path` or removes `path` (`kit_manifest.apply_diff`). Used only when the diff is smaller than the body |
| `{"hash": h, "cached": true}` | the host holds `h` (no nonce: the host must already have it) |

* **No scheduled re-send (PR-T).** Until #96 both bodies came back every 8th prepared turn (`FULL_EVERY`). That
  turn was 60–67 KB (T9 in the replay) and set p95. Now a body is sent only when the host does not hold it.
  What the host holds, and each copy's nonce, is recorded on each layered turn's telemetry (`manifest.held`,
  `manifest.nonce`), so it survives across CLI processes.
* **The safety net: nonces (#99 review).** Every body and every room diff carries a short random nonce
  (`kit_manifest.new_nonce`: a digit and 6 hex characters, so it is never an English word). Every layered packet
  carries `manifest_check`, and Kit answers it in the private `manifest` block of her output (stripped before
  anything is spoken): `"manifest": {"check": {"session": n1, "room": n2}}`, the nonces of the copies she holds.
  * The nonce of a cached layer is never in the packet, so only a host that read and kept the body (or applied
    the latest diff) can give it. A host whose room copy went stale, because it skipped a diff, gives the old
    nonce and is caught on that same turn. The line-completion check this replaces could not catch that: its
    room line was always the constraints boilerplate that every room shares (Nagatha's p99_stale and p99_pool).
  * A wrong or missing nonce is refused (`ManifestMismatch`, naming the layers) and marks **only those layers**
    as missed (`manifest.miss`). The next prepared turn re-sends just them. `rehydrate --turn-id T` returns just
    them, each with a new nonce, so Kit can rewrite the refused turn at once.
  * A correct resubmission of the same turn clears the miss, so nothing is re-sent needlessly.
  * The match is lenient: case, quotes, punctuation and extra words around the nonce don't matter
    (`_check_passes`, any order, at least 60% of the expected words; a nonce is one word, so it must be there).
  * The hash echo (`"session"`, `"room"` in `manifest`) is optional now. A cached layer carries its own hash,
    so echoing it proves nothing (#94 review). If Kit gives one it must match, and a wrong hash misses both layers.
* **Spoken guard.** Spoken that contains a manifest hash, a nonce or the check's wording is refused
  (`kit_manifest.check_spoken`, p99_leak).
* **Restore from an uploaded save.** A new chat that uploads `kit.sqlite` holds no bodies, but the database says
  it does. Every packet carries the check, so turn 1 of the new chat fails it, the turn is refused, and
  `rehydrate` sends both layers (p99_restore). No cached packet ever goes out without the check.
* **Rehydrate on request.** Kit can run `rehydrate --turn-id T` at any time. With no miss recorded, it returns
  both layers.

### Why a nonce every turn rather than a periodic check or a staggered refresh

The custom GPT runner trims or summarizes old turns without any signal, so some proof that the copy is still
there is needed. The options, measured on the watchroom replay (`--manifests`, model time is the labelled
estimate, Kit's private echo counted as output):

| Design | p95 | Catches a lost or stale copy within | Cost per turn |
|---|---|---|---|
| Full re-send every 8 turns (#96) | 15.6 s (T9, 66.6 KB) | 8 turns, only by luck of timing | +53 KB in on every 8th turn |
| Staggered refresh (one layer per turn, spread out) | ~15.6 s (the session body alone is ~53 KB) | 8 turns per layer | +53 KB in on a session turn |
| Line completion every 4 turns (first PR-T head, cf6296e) | 13.4 s | 4 turns for a lost copy, **never** for a stale room (p99_stale) | ~+0.5 KB in, ~+0.2 KB out on a check turn |
| **Nonce per layer and diff, echoed every turn (this)** | **13.7 s** | **the same turn, lost or stale, per layer** | **~+0.3 KB in (the check), 52 B out (~0.26 s)** |

The nonce costs about as much as the hash echo it replaces (51 B on main) and catches what the line check missed,
on the turn it happens. A host that fails it pays one re-send of only the layer it lacks.

**Limits.** A model that kept the nonce in a summary but lost the body would pass. The nonce is meaningless on
its own, so a summarizer has no reason to keep it, but it is a bet, not a proof. If the host loses its sandbox
(files gone), the database goes with it and the session restarts from `start`, which sends everything.

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

The replay now counts Kit's private manifest echo as output (#99 review). The main column adds main's 51-byte hash
echo (+0.26 s a turn), which its replay did not count.

| | #96 (main 0bce3ad) | PR-T (nonces) |
|---|---|---|
| T9 packet (the old scheduled re-send) | 66,593 B | 14,240 B |
| full-body sends after T0 | 1 session + 1 room | 0 session, 1 room diff (T7, the move into the watchroom) |
| packet median | 14,380 B | 14,240 B |
| echo out per turn | 51 B (hashes) | 52 B (nonces) |
| e2e median / p95 (model est) | 10.54 s / 15.61 s | 10.62 s / 13.72 s |
| worst steady-state turn | 15.99 s (T9) | 12.14 s (T7) |

The 11-turn p95 still includes T0, the session opening, which has to carry the bodies once (~60 KB, ~15 s).
Every later turn is an ordinary 9–17 KB delta, including the ~0.3 KB check.
