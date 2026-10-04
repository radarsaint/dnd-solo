# Kit collaboration protocol

This is the direct git channel between Skippy (Grok Bot) and GPT while we make Kit feel like a real person DMing.

## Roles

- **Skippy** owns the engine, wiring, tests, PR stacking, and project tracking.
- **GPT** owns voice, taste, and authored content drawn from Brendon's writing: style distillations, NPC voices, room agendas, and examples of how Brendon DMs/talks.

## Channels

- [`BOARD.md`](BOARD.md) is the live handoff. It holds the settled rules and open work only. Read this file every session. Add dated entries beginning `From: Skippy` or `From: GPT`; each entry has **Ask**, **Done**, and **Blocked**.
- [`board-archive/`](board-archive/) is the history. Finished entries are moved there verbatim, one file per day (`YYYY-MM-DD.md`). The pre-split board is `2026-09-30.md`, `2026-10-01.md`, `2026-10-02.md`, and `2026-10-03.md` in that order; do not edit those four. Read the archive only when you need an old entry. An archived ask is not current.
- Use GitHub issues labeled `skippy` or `gpt` for discrete tasks.
- Use PR comments for review and decisions about the change under review.

## Rules

1. Read `BOARD.md` first every session. Do not read `board-archive/` by default.
2. Every entry names a concrete next action and its owner.
3. When an item is finished, superseded, or no longer active, move that entry verbatim into `board-archive/YYYY-MM-DD.md` (append to that date's file, or create it) and delete it from `BOARD.md`. Leave the live board holding only open work and the settled rules.
4. Never paste private source writing verbatim beyond short quoted examples; distill it instead.
