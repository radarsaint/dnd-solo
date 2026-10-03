# Area 17a live-host startup failure — Nik

**Date:** 2026-10-03 PT  
**Host:** ChatGPT / GPT  
**Player:** Brendon  
**PC:** Nik  
**Target:** Level 1, Area 17a (Stone Temple Pileup — Foyer)  
**Build:** Drive snapshot `dnd-solo-main-6a2b7ed4.zip`, matching GitHub `main` at `6a2b7ed44cfc429d9d888b53aa2b330014bdb26d`

## Purpose

Move live testing away from Area 6c and begin a fresh room test in Area 17a. The intended test was ordinary exploration: enter the foyer as Nik and see whether Kit could frame and run the room cleanly from source-grounded state.

The test failed before the first Area 17a play turn was delivered.

## Failure 1 — opaque generated metaphor

During the mount / room-selection conversation, Kit said:

> "The dead basilisk is already making promises."

Brendon immediately rejected the line as nonsensical and non-human-legible in context.

### Classification

**Expression failure — opaque metaphor / semantic non sequitur.**

There was no established promise, no concrete referent for "making promises," and no useful table meaning carried by the metaphor. The line appears to reach for personality or wit instead of saying something intelligible.

### Why it matters

This is not merely a style preference. A DM line must remain semantically legible. Personality cannot be purchased by replacing concrete meaning with decorative metaphor.

A safe plain version would have been closer to:

> "Area 17, then. Dead basilisk in the foyer."

The exact replacement is not the important part. The requirement is that Kit's table voice remain comprehensible and contextually grounded.

## Failure 2 — pre-play host stall and runaway preparation

After restarting, Brendon said:

> "Hey. Lets pick up on the adventure. I'll be playing nik."

The host should have quietly prepared the immediately necessary material and begun the room.

Instead, it spent more than five minutes of user-visible wall-clock time performing setup/research before delivering any play. Brendon's direct feedback was:

> "Why did you just spend more than 5 minutes on an ambient lighting detail."

The host had expanded a simple room-entry preflight into a broad engineering/retrieval task. It chased map geometry, visibility, environmental preconditions, and ambient lighting, while also trying to adapt a runtime still centered on the Area 6c slice.

No Area 17a player-facing room entry was delivered before Brendon stopped the test.

### Classification

Primary:

**Host/orchestration failure — unbounded preflight / latency / scope discipline.**

Contributing:

**Salience failure — treating a low-value environmental detail as blocking.**

**Execution-boundary failure — attempting runtime-development work during what the player understood to be live play.**

This should not be mislabeled as an Area 17a content failure. The room never actually ran.

## What the host should have recognized

For the opening of 17a, an environmental fact is blocking only if it materially changes what Nik can perceive, what action is legal, or what immediate adjudication is required.

Exact ambient-lighting resolution was not shown to be necessary before framing the visible room.

Likewise, if the mounted runtime cannot yet execute a new-room slice, the host must not silently turn the player's game start into an open-ended implementation session. That incompatibility should be handled before live play or surfaced plainly and briefly.

## Regression target

A future Area 17a start should pass this basic host test:

1. Player says they are continuing as Nik and is about to enter 17a.
2. Host performs only bounded, immediately necessary preparation.
3. Non-blocking unknowns do not delay room framing.
4. If a missing fact truly affects the opening, retrieve it once and continue.
5. If the runtime cannot legally run the room, fail fast and say so rather than rebuilding it during the session.
6. First player-facing room framing arrives without development chatter.
7. Kit's prose is concrete and human-legible; no opaque metaphor is added merely to sound distinctive.

## Important distinction

This test produced useful evidence about **the host surface around Kit**, not yet about Kit's actual Area 17a exploration judgment. Do not claim Area 17a itself has been playtested from this run.

The next useful test begins only after the host can enter 17a without a prolonged engineering preflight.
