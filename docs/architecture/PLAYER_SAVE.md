# Player save (campaign-record design P1 to P4)

`kit.sqlite` is the live runtime database. It is **runtime-only**: the `source` table holds the
whole room file (hidden facts, DCs, claims, secret actors and exits, and for book rooms the
book text), and `kit_turns`/`kit_pending` hold Kit's private decisions. It never leaves the
runtime and is never offered to a player.

The player's save is a ZIP written by:

```sh
python3 -m runtime.kit_agent save --db kit.sqlite [--recap-file FILE] [--journal-mode campaign|character]
                                  [--player NAME] [--campaign NAME] [--out FILE]
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

## P2: the ledger fold, journal, recap, hand edits

- **Fold at room exit.** When the PC leaves a room for a linked one, `kit_rooms.mounted_state`
  calls `kit_save.fold_room_exit`, which keeps that room's public record in the session key
  `state['campaign_log']` (the room file itself is replaced once the next room mounts): area
  names visited, visible actors met there, facts learned (`known_fact_ids`), and what the PC took.
  Every `save` folds again: the rooms left plus the current one (`status: current`), with HP and
  gold as if the room were left now (`fold_pc`). "On stop" is the host running `save`.
- **campaign.json** now carries `rooms[].areas`, `npcs_met`, `learned`, `loot`, `gold_gp`,
  `choices` (the player's own committed words, last 20, no table talk), `sessions` (one per
  revision saved, with Kit's recap) and `edits`. `threads` stays empty: Kit's open-thread hints
  are her private decision and are not exported. `debts` is player-kept for now.
- **Journal modes.** `--journal-mode campaign` (default) writes `journal.md`; `character`
  writes `characters/<pc>/journal.md`. The mode is stored in campaign.json and sticks.
  Kit asks; she never picks. Until the player answers, `save` returns `ask_player`
  (`journal_mode`) and `campaign` is only a placeholder (`journal_mode_chosen: false`).
  Sections: Threads, People met, What you learned, Loot and coin, Debts, Session log (newest
  first), then the `kit-state` block (revision, location, and the hashes of the JSON files this
  save wrote).
- **Recap.** `--recap-file`: Kit's voice, at most 120 words. Refused (and nothing written) if
  it names a DC, an unrevealed fact, an unseen actor or a secret exit of the current room, or
  fails the play-time public-text guards (`check_public_content` with the room's leak phrases
  and keyword sets). Rooms already left are no longer loaded, so their literals cannot be checked.
- **Hand edits (D6).** A JSON file whose hash differs from the one the last save wrote is a hand
  edit. An edited sheet is taken as written (the player owns it). An edited campaign.json at the
  same revision is taken as written; at a higher revision the runtime's record wins and the edit
  is logged as superseded. Either way the journal says "edited by player" and `save` returns
  `noticed` so Kit may mention it once, lightly. Never an accept prompt.

## P3: resume

```sh
python3 -m runtime.kit_agent start --save <save ZIP or folder> [--room FILE] [--sheet FILE]
```

- A `kit.sqlite` at `--db` whose room matches `campaign.location.room_id` continues mid-room
  (`stage: resume`). One for another room is refused: pass a new `--db`.
- No sqlite: the room is found by id (`--room`, else the db folder, the working dir, `rooms/`,
  and `/mnt/data`, `/mnt/user-data/uploads`, `/mnt/user-data`), mounted fresh at its
  `starting_area`, and a `campaign_restore` bookkeeping event applies the public record (rooms
  left with their status, people met, facts learned, loot carried) before the opening is
  prepared. The sheet is the save's `sheet.json`, as written. Mid-room hidden state is not
  rebuilt. `stage: resumed_from_save`. The save files are unpacked into `saves/<player>/<campaign>/`
  so the next save keeps the session history.
- Only the journal survived: the `kit-state` block gives the location, PC, mode and hashes
  (`rebuilt_from_journal: true`); without a sheet the stage is `need_character`.
- Neither: `stage: needs_rebuild`. Kit asks once for the room and sheet, the player confirms.
- A hand-edited file (hash differs from the `kit-state` record) is used as written and listed in
  `noticed`. A room file whose hash differs from `source_hashes` mounts anyway with
  `room_changed: true`, and Kit says so.
- ZIP members with absolute paths or `..` are refused; only the player files are read.
- The greeting (`start` with no room) lists saves it finds (`saves`: player, campaign, PC,
  room, area, last session and recap, open threads) and carries `new_campaign.ask`, starting with
  the journal-mode question.

## Imported adventures (#172, #174)

An imported adventure keeps its private book text, index and compiled rooms in
`kit.sqlite.adventure/` next to the save. That folder is runtime-only like `kit.sqlite`: the
save never reads or copies it. Compiled creatures start hidden; a hidden creature (its name and
stat block) stays out of the save until the player can see it in the public view.
`tests/test_kit_player_save.py` checks every location of the original synthetic Lantern Ferry
adventure.

Resuming an imported adventure: the save names the room (`adv-<book sha8>-<key>`) but never
carries the book. If the same book is imported next to `--db`, `start --save` compiles that
room on demand and restarts it from its start. Otherwise the stage is `needs_adventure`: Kit asks
once for the same adventure file, the host runs `adventure import`, then `start --save` again.
A different copy of the book has a different id and is refused, never guessed.

## P4: cross-room carry

- **Live room change.** Checked on `main` `e02f355` before this change: a level-1 slot spent in
  one room came back unspent after a room change (`pc_resources` was not a session key).
  Now `pc_resources` (spell slots and limited uses, with what is spent) is now a
  session key, so it follows the PC into the next room instead of being rebuilt full from the
  sheet. When the sheet changes on the way out (HP or gold folded), the inventory is rebuilt with
  `carry_spent`, so spent stays spent until a rest. Conditions, loot (`carried`) and the room
  archive already travelled.
- **campaign.json** adds `pc_state` (`slots` and `uses` spent, `conditions`) and, for every room
  left, `rooms[].carry`: ids of the areas visited, facts and exits the player knows, the met
  actors' statuses, and the room's public resources. Only what the player already knows.
- **Resume.** The restore event applies `pc_state` to the rebuilt inventory and keeps each room's
  `carry` in `campaign_log`.
- **Going back to a room left before a resume** (no archive in the new sqlite): the room mounts
  from its file and `apply_carry` puts back what the player knew and did: visited areas, known
  facts and exits, met actors' statuses (the warden stays dead), resources. Actors and secrets
  the player never met stay as the room file has them.
