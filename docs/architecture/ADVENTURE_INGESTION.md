# Adventure ingestion (architecture 1: index once, compile just in time)

**Status:** index once, compile just in time, including a raw PDF. Code: `runtime/kit_adventure.py`,
`runtime/kit_pdf.py` (stdlib text layer), a loader hook in `runtime/kit_rooms.load_link`, readiness
in `runtime/kit_lifecycle.status`. Tests: `tests/test_kit_adventure.py` (text corpus
`tests/fixtures/adventures/lantern_ferry.txt`) and `tests/test_kit_adventure_pdf.py` (synthetic PDFs
generated in the test: two columns, read-aloud boxes, a stat block, keyed rooms, a scan). No
published adventure text is in this repo.

## Host commands

One step, then begin. `ingest` reads the PDF (or pasted text), writes the index, and compiles
the first scene. `status` prints `next_command`; run it when the player says begin.

```sh
python3 -m runtime.kit_agent ingest adventure.pdf --db kit.sqlite
python3 -m runtime.kit_agent status --db kit.sqlite          # next_command is start --room of the first scene
# pasted text, or a PDF the built-in reader cannot read:
python3 -m runtime.kit_agent adventure import  --db kit.sqlite --text-file adventure.txt
python3 -m runtime.kit_agent adventure compile --db kit.sqlite --location 1                 # deterministic
python3 -m runtime.kit_agent adventure compile --db kit.sqlite --location 1 --draft-file d.json  # host-model draft, validated
python3 -m runtime.kit_agent adventure status  --db kit.sqlite
```

`ingest` reports `ingest_ms`, `first_scene_ms`, `source_bytes`, `index_bytes`, and
`first_scene_bytes`. It compiles only the opening location. The next scene compiles when
play reaches it (the loader hook), and that compile's `scene_ms` / `scene_bytes` land in
the provenance sidecar. No host step between rooms.

## PDF text layer

`runtime/kit_pdf.py` is stdlib only. It inflates Flate streams, reads text with positions
(`Tm` / `Td` / `Tj` / `TJ`), puts a two-column page back in reading order (left column, then
right), drops a running header, footer, or page number, and prefixes a line inside a vector
box with `> ` so the compiler treats it as read-aloud. A page-sized frame is not a box.
UTF-16 hex strings and a font's ToUnicode CMap (`bfchar` / `bfrange`) are applied. Keyed
locations stay headings on their own line (`A1. Gatehouse`, `12. Ash Court`, `Area 3: Well
Shaft`); a table row stays one line.

`pdftotext -layout` and `pypdf` run only when the built-in reader cannot read the encoding,
and only if the host has them (`--reader stdlib` never calls them). A PDF with no text
operators is refused: `this PDF has no text layer` — paste the text and pass `--text-file`.
There is no OCR.

## Likely misfires

1. A font with no ToUnicode map (glyph indexes only) comes out garbled. Ingest refuses it
   (`has a text layer but the built-in reader could not read it`) rather than compiling
   nonsense. Paste the text, or use a host that has `pdftotext` / `pypdf`.
2. Three columns, a sidebar, or text drawn out of order can attach a paragraph or a stat
   block to the wrong location. Two columns with a full-width heading are the case this
   reader is built for.
3. Read-aloud that is not a vector rectangle (an image shade, or italics with no box) is
   not prefixed with `> `, so the scene compiles with nothing player-visible until it is
   revealed. A box around a secret would show it; a rectangle bigger than about a third of
   the page is ignored.

## Private storage

Everything lives next to the save in `<db>.adventure/` (`source.txt`, `index.json`,
`rooms/<key>.json` and `rooms/<key>.provenance.json`). `*.adventure/` is git-ignored. The source
is never committed and never enters the per-turn packet: a compiled room is an ordinary room
file, so the packet is exactly as large as for any hand-written room (and capped by
`kit_rooms.DM_ONLY_ROOM_MAX_BYTES` the same way).

## Text the host supplies

Plain UTF-8, or a PDF (`ingest <file>`). Page breaks as form feeds (`\f`). Boxed read-aloud lines
prefixed `> ` (the PDF reader adds that prefix for a vector box). Keyed locations as headings on
their own line: `1. Ferry Landing`, `12. Ash Court`, `Area 3: Cellar`, `A1. Gatehouse`. A scanned
PDF is refused; paste the text and pass `--text-file`.

## What is deterministic, what is model-assisted

| Step | Who | Checked by |
|---|---|---|
| Index: chapters, keyed locations + offsets + pages, NPC mentions, stat-block refs, connections, map pages | runtime (regex, deterministic) | tests |
| Compile a location to a room draft | runtime by default; optionally the host model fills a draft | **runtime `validate`** in both cases |
| Pre-compile neighbours | runtime, after `compile` (not after `ingest`; the opening stays one scene) | |
| Compile on arrival when not cached | runtime, via the `room_link.adventure` hook in the loader | |

`validate` refuses: any area, exit or fact with no `{quote, offset}` provenance; a quote that is
not verbatim in that location's own span; a visible fact quoting DM-only (non read-aloud) text;
a fact whose text uses words its quote does not; an exit quoting no connection the source states;
an unsourced or misquoted creature stat (see Combatants); and anything the room loader itself refuses.

## Precedence

1. The adventure's own text (the location span; read-aloud is the only player-visible source).
2. The adventure's own stat blocks (`Armor Class` blocks found by the index).
3. SRD 5.1 (`runtime/srd_creatures.py`).
4. Ask the player (`ask_player` in the compile report). Never invent.

Secret connections (`secret|hidden|concealed` in the stating sentence) compile to `secret: true`
exits: the PC cannot use one until play reveals it.

## Combatants

A creature becomes an engine actor (`actors.<key>` with `stat_block`) only when the location puts it
there: a count or article before its name ("two bandits", "a reed lurker") or a "(see ...)" after it.
A passing mention ("someone called the Lantern Wight") is not a combatant.

* **Book stat block:** parsed into the inline engine shape `{ac, hp, attacks: [{name, to_hit, damage, type}]}`.
  Each of `ac`, `hp` and each attack carries the quote it came from (`Armor Class 13`, the attack line).
  Initiative, grapple and saves keep the engine defaults; nothing is guessed.
* **SRD 5.1:** `{"srd": name}` from `runtime/srd_creatures.py`.
* **Otherwise `ask_player`:** no actor; the creature stays a hidden fact.

The validator refuses an actor with no presence quote in the location, an inline stat whose quote is not in
that creature's book stat block or does not state the number, any extra stat field, or an SRD name the
runtime does not ship. Stats are dm-only: the player never sees AC, hit points or bonuses.

**Visibility.** A creature is player-visible only when the location's read-aloud text names it.
Otherwise it compiles `status: "hidden"`, `visible: false` (dm_only and nowhere else) and is woken
only by a room trigger, the existing reveal path. When the book ties it to something in the room
("they attack anyone who touches the ledger") the trigger is `disturb` on that fact, which gains
`handling.nouns` quoting the same sentence; otherwise it is `enter` on the area, so the creature
shows itself (and the fight starts) on arrival. The trigger is sourced to the creature's sentence.

Partial or unsupported: Multiattack (every listed attack is given to the engine, which uses its own
attack order), Recharge abilities, Spellcasting, legendary actions, saving-throw riders on attacks,
resistances, speeds, and damage dice (the average is used). Each is flagged on compile.

## Readiness levels (`status.adventure.adventure_readiness`)

* `source_available`: imported and indexed, nothing compiled.
* `location_executable`: at least one location compiled.
* `campaign_playable`: the mounted room is a compiled location and every location it connects to is
  compiled (the next move is executable).

## What the room format could not express (open question)

From the synthetic corpus alone: a bell that summons help without the book naming who
(loader alarm warning, carried as a flag); conditional text ("they attack anyone who touches the
ledger") as triggers; treasure as resources; sub-areas inside one keyed location; map-only layout.
Whether the format can express arbitrary published adventures is **not yet known**.
