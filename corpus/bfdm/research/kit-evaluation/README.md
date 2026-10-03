# Kit Evaluation

This directory preserves **development and playtest evidence about Kit herself**.

It is deliberately separate from the historical Brendon corpus.

Historical corpus question:
> What can we learn from Brendon's body of work?

Kit evaluation question:
> When we put the current system in front of a player, what actually works, what fails, and what must not regress?

Do not use Kit failures as evidence about Brendon's historical DM behavior.

## Current records

- [playtest-01-character-onboarding.md](playtest-01-character-onboarding.md) — 2026-09-23 character creation → campaign handoff.
- [playtest-02-area-6c-gambling.md](playtest-02-area-6c-gambling.md) — 2026-09-29 Area 6c gambling/marked-deck test.
- [REGRESSION_TARGETS.md](REGRESSION_TARGETS.md) — cross-test behavioral targets.

## Evaluation discipline

Preserve:
- the user-facing failure;
- the relevant source/runtime expectation;
- whether the failure was competence, state control, voice, source use, or adjudication;
- direct user correction;
- whether a later fix was actually retested.

Do not convert every failure into a narrow sentence patch.

A recurring goal is to diagnose the **class of failure** and then test whether later versions solve it in genuinely different situations.
