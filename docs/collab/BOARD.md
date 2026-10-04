# Kit collaboration board

Live board. Settled rules and open work only. Read this file at the start of a session.

Finished history is in [`board-archive/`](board-archive/). Open it only when you need an old entry. An archived ask is not current: later entries supersede earlier ones, and this file is what is still open.

The board as it stood before this split (826 lines, 71,967 bytes) is preserved byte for byte. Concatenate these four files in order. Do not edit them. Newer finished entries go in a later `board-archive/YYYY-MM-DD.md`.

- [`board-archive/2026-09-30.md`](board-archive/2026-09-30.md) — original preamble, the settled rules as first written, and the 2026-09-30 entry
- [`board-archive/2026-10-01.md`](board-archive/2026-10-01.md)
- [`board-archive/2026-10-02.md`](board-archive/2026-10-02.md)
- [`board-archive/2026-10-03.md`](board-archive/2026-10-03.md)

SHA-256 of that concatenation: `7a8cb92af8032e73f0a8ed8bdaa56577f95983c0b3354c2e91c5b495e3b71a96`.

## How to write and retire an entry

Add open work as a dated entry beginning `From: Skippy` or `From: GPT`, with **Ask**, **Done**, and **Blocked**. Name one concrete next action and its owner.

When an item is finished, superseded, or no longer active, move that entry verbatim into `board-archive/YYYY-MM-DD.md` (append to that date's file, or create it) and delete it from this file. Leave the settled rules here.

## Settled rules — don't re-ask

Brendon has already decided these. Apply them; never raise them as open decisions. Add to this list (dated) when he settles another one.

- **Unnamed DCs (settled more than once, recorded 2026-10-02):** when the source names no DC, Kit sets it at DM discretion. The baseline the runtime uses is 10 + floor(dungeon floor level / 3) (`kit_claims.default_dc`; the area's `floor_level`, else 1). An NPC who actively hides something brings a flat 10 + their skill instead. Example: the ring appraisal is not an open question.
- **Numbers stay in the ledger (table call 4, 2026-10-02):** public text never shows a DC, a roll total, a modifier, or die math. A roll request names the skill only; a success is told as what the character notices. The numbers stay in event evidence and traces.
- **No paid OpenAI API:** Kit runs inside ChatGPT through the bridge on Brendon's subscription. No `OPENAI_API_KEY`, no paid-API play path.
- **PR merges need Brendon's OK (settled 2026-10-03):** never merge to `main` without his say-so. The PM bundles ready PRs into one approval ask instead of pinging once per PR.
- **Skill gates the reveal (table call 8, 2026-10-03):** players may substitute a plausible skill; Kit accepts the swap and gates what each skill reveals. Perception notices what is there (a snapshot of details that scale with the roll, never a conclusion). Investigation deduces what happened from physical clues. Insight (Wisdom) reads motive and the why. Persist the skill actually used.
- **A grab outside combat (Brendon/Nagatha, 6c rerun ruling, recorded 2026-10-03; not built yet):** a grab outside combat starts the fight if the target resists or allies react. The situation decides; it is not automatic either way.
- **Project ZIPs are pinned baselines; GitHub `main` is current development truth (Brendon, 2026-10-03):** a commit-stamped runtime ZIP in Project Files, GPT Knowledge, Drive, Library, or a conversation represents that exact reproducible snapshot. Use it to run/reproduce that build. Do not call it current merely because it is mounted. For current development state, inspect `radarsaint/dnd-solo` `main`. New stable Project snapshots get new commit-stamped filenames; preserve older ones as baselines unless Brendon explicitly replaces or deletes them.
- **bfdm-corpus visibility (Brendon, 2026-10-03):** `radarsaint/bfdm-corpus` was public as of that date. Older board notes that call it private are history. Visibility can change; check the repository rather than old prose. Visibility does not change provenance, attribution, seed-eligibility, or evidence-scope rules.

## Open

Checked against GitHub and `main` at the split (`62ef279`). Issues #27, #28, #29, #35, #45, and #46 are still open. Work the archive already recorded as landed stays off this list: #77 merged, card backlogs (a) and (c) landed in #83, the wider table-talk leak scan is on main, the V1–V11 offline probe was reported done in the 2026-10-03 adversarial entry, and the exact #70 router phrases are covered by `tests/test_kit_router_idioms.py`.

### GPT

- **[#27](https://github.com/radarsaint/dnd-solo/issues/27):** write `docs/voice/brendon-dm-voice.md`. Distill how Brendon describes, jokes, paces, does NPCs, and reacts to players, with short paired examples of bland versus Brendon. The file is still absent. Asked 2026-09-30; the 2026-10-03 maintenance audit left it open.
- **[#28](https://github.com/radarsaint/dnd-solo/issues/28):** commit a new playtest under `tests/playtests/` and hand it off with a dated note on this board. Later playtests exist, including `tests/playtests/2026-10-03-gpt-adversarial-16081884.md` and `tests/playtests/2026-10-04-watchroom-nik.md`. The issue is still open; that audit did not treat later playtests as closing this ask.
- **[#29](https://github.com/radarsaint/dnd-solo/issues/29):** author the Area 6c agenda in the order and boundaries in `docs/GPT_HANDOFF_AGENDAS.md`, hidden key claim first. The maintenance audit did not find that agenda on main, and the issue is still open. Later story-brief work does not close it.
- **[#35](https://github.com/radarsaint/dnd-solo/issues/35):** [#23](https://github.com/radarsaint/dnd-solo/pull/23) is still an open draft on the old `kit-refactor-2` base. Rebase it onto the current line or explicitly supersede it. Do not call it done in silence.
- **[#46](https://github.com/radarsaint/dnd-solo/issues/46):** hold [#73](https://github.com/radarsaint/dnd-solo/pull/73) until the public `raise_now` wording no longer leaks the secret ("ruse"), then rebase. G2 / TC-6b still wants those toll and act lines as a full in-character exchange inside the act. Keep host friction and the stake-language false positive separate from the router: `check_stake_offers` still treats `door` as an uncarried stake in any NPC sentence that also says `wager`.
- **BFDM cleanup is not on main.** [#67](https://github.com/radarsaint/dnd-solo/pull/67) is still an open draft and conflicts with `main`. [#106](https://github.com/radarsaint/dnd-solo/pull/106) is a later unmerged draft that claims to supersede it. Do not treat either as landed.

### Skippy

- **[#45](https://github.com/radarsaint/dnd-solo/issues/45):** generalize the natural-language router at the verb, object, and idiom level. Do not add another exact-phrase list. On current `main` the 6c adjudicator still misroutes the ordinary English from the 2026-10-03 adversarial pass (`board-archive/2026-10-03.md`, and `tests/playtests/2026-10-03-gpt-adversarial-16081884.md`):
  - false attacks, still an unarmed-strike prompt: `shoot him a look`, `hit on the dealer`, `cut him off`, `murder him with a look`, `slash him a grin`; `stab at a guess` asks who is being attacked
  - false exits: `step out of the way` and `go out of my way to compliment the dealer` (`room_intent` treats a moving verb plus `out` as leaving)
  - false tub mutation: `move around the tub` resolves as `move_feature`
  - A literal `shoot the dealer` is still an attack, and `shoot the breeze with the dealer` is still talk. Harmless gestures and posture that stop as unsupported physical rulings are behind the consequential misses above.

## Blocked

- **Persona-continuity E1** waits on Brendon re-uploading the merged custom GPT instructions and the standalone `docs/personality/dm-personality-core.md` Knowledge file. Nothing else here is a Brendon decision gate. [#73](https://github.com/radarsaint/dnd-solo/pull/73) waits on the ruse-leak fix before anyone rebases it.

## Parked

Not active. The 2026-10-03 stage-1 entry parked these until a live game shows the need. Full wording is in `board-archive/2026-10-03.md`.

- A CLI command for closing a scene.
- Taking the pot by force as its own mechanic. It stays prose; the fight path covers it.
