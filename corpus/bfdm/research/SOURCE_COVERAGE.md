# Source Coverage

This file tracks known corpus coverage relevant to the research program. It is not a substitute for the source manifest.

## Earlier normalized/staged body

Before the S3 Discord harvest, the working corpus staging contained **51 normalized source containers**:

- Roanoke: 37
- Earthfall: 2
- Bastion / Redoubt: 3
- At War's End: 8
- Exploration Impossible context: 1

The staging status records:
- 75 embedded assets;
- 62 export comments;
- 17 native Brendon comment supplements.

Those 17 supplements are a staging metric, **not the total known Brendon-comment corpus**.

Later `dnd-solo` attribution work (merged PR #40) identified **78 attributable Brendon editorial comments** on Michael Kennish's *Exploration Impossible* while keeping the manuscript itself third-party/context-only. The older staging bundle did not exhaustively mirror all native Drive comments/replies.

The prior consolidated staging archive was maintained in the ChatGPT Library as:

`/Brendon Corpus Staging/Current/brendon-corpus-staging.zip`

This staging body should eventually be reconciled/migrated into the canonical private repository rather than maintained as a parallel corpus.

## Canonical private repository

`radarsaint/bfdm-corpus`

Current known major source families include:
- Discord server harvests under `discord/`;
- campaign planning under `campaigns/`;
- derived research on draft/research branches.

## Roanoke Season 3 Discord

`discord/roanoke-season-3/roanoke-season-3.sqlite`

Known harvest:
- 197,013 messages;
- 194 text channels;
- 1,421 attachments captured;
- time window 2020-07-18 through 2020-08-22.

## Roanoke Season 4 / Empire City Discord

`discord/empire-city/empire-city.sqlite`

Known harvest:
- server ID `850779382791536640`;
- 189,761 messages;
- 247 text channels;
- 52 threads;
- 3,528 attachments captured;
- observed message range 2021-06-05 through 2026-10-01.

The server explicitly identifies the campaign as **Season 4, Empire City**. The observed server range is not treated as the campaign live window. Brendon's account mapping is now confirmed from the server users table by immutable Discord user ID `313689699627696139`.

## Google Drive / project corpus

Connected Drive contains a much broader creative record than S3 alone, including:
- campaign planning;
- custom races/classes/subclasses;
- worldbuilding and lore;
- adventure drafts;
- change logs;
- revision histories;
- homebrew mechanics;
- writing;
- unusual format experiments.

Full repository ingestion is still pending/in progress.

## S3 normalization / reconciliation status

The legacy staging manifest confirms the week documents used by the revision-family pass already have formal source containers:

- `BCS-000029` — Roanoke S3 v2 W2 Breakdown;
- `BCS-000037` — Roanoke s3w4 Break down.

Other confirmed mappings:
- `BCS-000045` — Roanoke Season 3 Rough Draft;
- `BCS-000046` — Roanoke Season3 Change Log;
- `BCS-000048` — RoanokeS3 doc V2 W1;
- `BCS-000052` — RoanokeS3W3 Breakdown;
- `BCS-000053` — RoanokeS3W5 Break Down.

The gap is now **repository reconciliation**: ensure the older staged containers and their originals/assets/comments are represented in canonical `bfdm-corpus` without changing their BCS IDs.

## Other Discords

S3 and Empire City / Season 4 are harvested. Remaining game servers still need harvesting. Until broader live coverage is present, cross-season conclusions should remain provisional.

## Coverage principle

Do not infer importance from what is easiest to search.

S3 remains unusually dense and methodologically mature, while Empire City now provides a second large live/server archive. Evidence density still must not be mistaken for importance. Later work—especially Earthfall—may be more representative of Brendon's current practice despite having fewer normalized records at present.
