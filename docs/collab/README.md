# Kit collaboration protocol

This is the direct git channel between Skippy (Grok Bot) and GPT while we make Kit feel like a real person DMing.

## Roles

- **Skippy** owns the engine, wiring, tests, PR stacking, and project tracking.
- **GPT** owns voice, taste, and authored content drawn from Brendon's writing: style distillations, NPC voices, room agendas, and examples of how Brendon DMs/talks.

## Channels

- [`BOARD.md`](BOARD.md) is the shared, append-only handoff. Add dated entries beginning `From: Skippy` or `From: GPT`; each entry has **Ask**, **Done**, and **Blocked**.
- Use GitHub issues labeled `skippy` or `gpt` for discrete tasks.
- Use PR comments for review and decisions about the change under review.

## Rules

1. Read `BOARD.md` first every session.
2. Every entry names a concrete next action and its owner.
3. Never paste private source writing verbatim beyond short quoted examples; distill it instead.
