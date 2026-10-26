# Player save (P1 of the campaign-record design)

`kit.sqlite` is the live runtime database. It is **runtime-only**: the `source` table holds the
whole room file (hidden facts, DCs, claims, secret actors and exits, and for book rooms the
book text), and `kit_turns`/`kit_pending` hold Kit's private decisions. It never leaves the
runtime and is never offered to a player.

The player's save is a ZIP written by:

```sh
python3 -m runtime.kit_agent save --db kit.sqlite [--player NAME] [--campaign NAME] [--out FILE]
```

It writes `saves/<player>/<campaign>/` next to the database (default player `player`; default
campaign `dotmm` for `dotmm-*` rooms, otherwise `solo`) and a ZIP of it,
`kit-save-<campaign>-<pc>.zip`, which is what the host offers as a download:

```
campaign.json                 kit_campaign_v1, player-safe
journal.md                    rendered from campaign.json; ends in a kit-state block
characters/<pc>/sheet.json    the player's character_sheet_v1, as loaded
characters/<pc>/sheet.md      a render of that sheet
```

`saves/` is in `.gitignore`. `dm-notes.json` and `kit.sqlite` are never in the ZIP.

## What is exported (whitelist)

Everything comes from the public player view (the same view the player is shown), the
player's own sheet, ids, counts and a hash. Nothing is copied from the room file or Kit's trace.

| `campaign.json` field | From |
|---|---|
| `location` `{room_id, area, turn_id}` | room id; the public area name |
| `rooms` | the current room, `status: current` |
| `npcs_met` | actors visible to the PC right now (name, status) |
| `gold_gp` | the sheet |
| `pcs`, `pc`, `sheet_source`, `journal_mode` | the sheet; `journal_mode: campaign` |
| `sessions` | revision and committed turn count |
| `source_hashes` | sha256 of the mounted room file (detects pack drift; reveals nothing) |
| `loot`, `debts`, `threads`, `choices` | empty in P1; filled by the ledger fold (P2) |

## Tests

`tests/test_kit_player_save.py` mounts every synthetic room under `tests/fixtures/rooms/`,
the 6c regression fixture, and a watchroom variant with a secret exit, a hidden actor with
secrets and a hidden fact. For each, it collects every string of the room the player cannot
see, plus the room's DCs and the raw `source` body, and checks that none appears in any
exported file. A clean-dir test builds the release ZIP, unzips it, and runs `start` then `save`
under `env -i python3`.

## Later phases

P2 folds the ledger into `campaign.json` and renders the full journal with Kit's recap; P3
resumes from the save ZIP. Until P3, an uploaded `kit.sqlite` from an older save still resumes.

## Imported adventures (#172, #174)

An imported adventure keeps its private book text, index and compiled rooms in
`kit.sqlite.adventure/` next to the save. That folder is runtime-only like `kit.sqlite`: the
save never reads or copies it. Compiled creatures start hidden; a hidden creature (its name and
stat block) stays out of the save until the player can see it in the public view.
`tests/test_kit_player_save.py` checks every location of the original synthetic Lantern Ferry
adventure.
