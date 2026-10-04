# Kit collaboration board

Live board. Standing rules and open work only.

Read this file at the start of a session. Finished history is in [`board-archive/`](board-archive/). Open it only when you need an old entry. An archived ask is not current: later entries supersede earlier ones, and this file is the list of what is still open.

The board as it stood through 2026-10-03 is preserved verbatim in these four files. Concatenate them in this order to recover that text unchanged, including its preamble:

- [`board-archive/2026-09-30.md`](board-archive/2026-09-30.md)
- [`board-archive/2026-10-01.md`](board-archive/2026-10-01.md)
- [`board-archive/2026-10-02.md`](board-archive/2026-10-02.md)
- [`board-archive/2026-10-03.md`](board-archive/2026-10-03.md)

SHA-256 of that concatenation: `7a8cb92af8032e73f0a8ed8bdaa56577f95983c0b3354c2e91c5b495e3b71a96`.

## How to move finished work

Add open work here as a dated entry beginning `From: Skippy` or `From: GPT`, with **Ask**, **Done**, and **Blocked**. Name one concrete next action and its owner.

When an item is finished, superseded, or no longer active, move that entry verbatim into `board-archive/YYYY-MM-DD.md` and delete it from this file. Append to the file for that date, or create a new dated file if the day does not have one yet. Do not edit the four pre-split files above. This board keeps the settled rules and whatever is still open.

## Settled rules — don't re-ask

Brendon has already decided these. Apply them; never raise them as open decisions. Add to this list (dated) when he settles another one.

- **Unnamed DCs (settled more than once, recorded 2026-10-02):** when the source names no DC, Kit sets it at DM discretion. The baseline the runtime uses is 10 + floor(dungeon floor level / 3) (`kit_claims.default_dc`; the area's `floor_level`, else 1). An NPC who actively hides something brings a flat 10 + their skill instead. Example: the ring appraisal is not an open question.
- **Numbers stay in the ledger (table call 4, 2026-10-02):** public text never shows a DC, a roll total, a modifier, or die math. A roll request names the skill only; a success is told as what the character notices. The numbers stay in event evidence and traces.
- **No paid OpenAI API:** Kit runs inside ChatGPT through the bridge on Brendon's subscription. No `OPENAI_API_KEY`, no paid-API play path.
- **PR merges need Brendon's OK (settled 2026-10-03):** never merge to `main` without his say-so. The PM bundles ready PRs into one approval ask instead of pinging once per PR.
- **Skill gates the reveal (table call 8, 2026-10-03):** players may substitute a plausible skill; Kit accepts the swap and gates what each skill reveals. Perception notices what is there (a snapshot of details that scale with the roll, never a conclusion). Investigation deduces what happened from physical clues. Insight (Wisdom) reads motive and the why. Persist the skill actually used.
- **A grab outside combat (Brendon/Nagatha, 6c rerun ruling, recorded 2026-10-03; not built yet):** a grab outside combat starts the fight if the target resists or allies react. The situation decides; it is not automatic either way.
- **Project ZIPs are pinned baselines; GitHub `main` is current development truth (Brendon, 2026-10-03):** a commit-stamped runtime ZIP in Project Files, GPT Knowledge, Drive, Library, or a conversation represents that exact reproducible snapshot. Use it to run/reproduce that build. Do not call it current merely because it is mounted. For current development state, inspect `radarsaint/dnd-solo` `main`. New stable Project snapshots get new commit-stamped filenames; preserve older ones as baselines unless Brendon explicitly replaces or deletes them.
- **bfdm-corpus visibility (Brendon, 2026-10-03):** `radarsaint/bfdm-corpus` was public as of this date. Older board notes that call it private are history. Visibility can change; check the repository rather than old prose. Visibility does not change provenance, attribution, seed-eligibility, or evidence-scope rules.

## Open

### GPT

- **[#27](https://github.com/radarsaint/dnd-solo/issues/27):** write `docs/voice/brendon-dm-voice.md`. Distill how Brendon describes, jokes, paces, does NPCs, and reacts to players, with short paired examples of bland versus Brendon. The file is still absent. Asked 2026-09-30; the 2026-10-03 maintenance audit left it open.
- **[#28](https://github.com/radarsaint/dnd-solo/issues/28):** commit a new playtest under `tests/playtests/` and hand it off with a dated note on this board. Later playtests exist, including `tests/playtests/2026-10-03-gpt-adversarial-16081884.md`. The issue is still open; that audit did not treat them as closing this ask.
- **[#29](https://github.com/radarsaint/dnd-solo/issues/29):** author the Area 6c agenda in the order and boundaries in `docs/GPT_HANDOFF_AGENDAS.md`, hidden key claim first. The maintenance audit did not find that agenda on main. Later story-brief work does not close it.
- **[#35](https://github.com/radarsaint/dnd-solo/issues/35):** [#23](https://github.com/radarsaint/dnd-solo/pull/23) is still an open draft on the old `kit-refactor-2` base. Rebase it onto the current line or explicitly supersede it. Do not call it done in silence.
- **[#46](https://github.com/radarsaint/dnd-solo/issues/46):** hold [#73](https://github.com/radarsaint/dnd-solo/pull/73) until the public `raise_now` wording no longer leaks the secret ("ruse"), then rebase. G2 / TC-6b still wants those toll and act lines as a full in-character exchange inside the act. Keep host friction and validator false positives from the 2026-10-03 adversarial pass separate from the router: ordinary live hosting was churning on `table_presence`, `kit_focus`, and `reacts_to`, and dealer speech with `wager` and `door` in one sentence was rejected as if the door were the stake.
- **[#67](https://github.com/radarsaint/dnd-solo/pull/67):** still an open draft, and it conflicts with `main`. Do not treat that BFDM cleanup as landed.

### Skippy

- **[#45](https://github.com/radarsaint/dnd-solo/issues/45):** generalize the natural-language router at the verb, object, and idiom level. The exact phrases from the #70 audit are fixed and covered by `tests/test_kit_router_idioms.py`. The 2026-10-03 adversarial pass on main `16081884` still found nearby ordinary English committing the wrong action: false attacks (`shoot him a look`, `stab at a guess`, `hit on the dealer`, `cut him off`, `murder him with a look`, `slash him a grin`), false exits (`step out of the way`, `go out of my way to compliment the dealer`), and a false tub mutation (`move around the tub`). Harmless gestures and posture were still stopping as unsupported physical rulings. Do not patch those as another exact-phrase list. Evidence is `tests/playtests/2026-10-03-gpt-adversarial-16081884.md` and the adversarial entry in `board-archive/2026-10-03.md`.

### Blocked

- **Persona-continuity E1** waits on Brendon re-uploading the merged custom GPT instructions and the standalone `docs/personality/dm-personality-core.md` Knowledge file. Nothing else here is a Brendon decision gate. [#73](https://github.com/radarsaint/dnd-solo/pull/73) waits on the ruse-leak fix before anyone rebases it.

## Parked

Not active. The 2026-10-03 stage-1 entry parked these until a live game shows the need:

- A CLI command for closing a scene.
- Taking the pot by force as its own mechanic. It stays prose; the fight path covers it.
