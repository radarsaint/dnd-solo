# Adventure ingestion (architecture 1: index once, compile just in time)

**Status:** first slice, PR "adventure ingestion". Code: `runtime/kit_adventure.py`, a loader hook in
`runtime/kit_rooms.load_link`, readiness in `runtime/kit_lifecycle.status`. Tests:
`tests/test_kit_adventure.py`. Corpus: `tests/fixtures/adventures/lantern_ferry.txt`, an original
synthetic adventure written for the tests. No published adventure text is in this repo.

## Host commands

```sh
python3 -m runtime.kit_agent adventure import  --db kit.sqlite --text-file adventure.txt   # or --pdf file.pdf
python3 -m runtime.kit_agent adventure compile --db kit.sqlite --location 1                 # deterministic
python3 -m runtime.kit_agent adventure compile --db kit.sqlite --location 1 --draft-file d.json  # host-model draft, validated
python3 -m runtime.kit_agent adventure status  --db kit.sqlite
python3 -m runtime.kit_agent status --db kit.sqlite     # lifecycle; carries "adventure" readiness
```

Then `start --db kit.sqlite --room <adventure.start_room> --sheet <sheet>` (status prints it as
`next_command`). After that, moving between locations is ordinary play: no host step.

## Private storage

Everything lives next to the save in `<db>.adventure/` (`source.txt`, `index.json`,
`rooms/<key>.json` and `rooms/<key>.provenance.json`). `*.adventure/` is git-ignored. The source
is never committed and never enters the per-turn packet: a compiled room is an ordinary room
file, so the packet is exactly as large as for any hand-written room (and capped by
`kit_rooms.DM_ONLY_ROOM_MAX_BYTES` the same way).

## Text the host supplies

Plain UTF-8. Page breaks as form feeds (`\f`, what `pdftotext` emits). Boxed read-aloud lines
prefixed `> `. Keyed locations as headings on their own line: `1. Ferry Landing`, `Area 3: Cellar`,
`A2. Gatehouse`. The stdlib `--pdf` reader is best effort (Flate streams, `Tj`/`TJ` strings); when
its yield is poor it refuses and asks the host to extract with `pdftotext -layout` or `pypdf`.

## What is deterministic, what is model-assisted

| Step | Who | Checked by |
|---|---|---|
| Index: chapters, keyed locations + offsets + pages, NPC mentions, stat-block refs, connections, map pages | runtime (regex, deterministic) | tests |
| Compile a location to a room draft | runtime by default; optionally the host model fills a draft | **runtime `validate`** in both cases |
| Pre-compile neighbours | runtime, after every compile | |
| Compile on arrival when not cached | runtime, via the `room_link.adventure` hook in the loader | |

`validate` refuses: any area, exit or fact with no `{quote, offset}` provenance; a quote that is
not verbatim in that location's own span; a visible fact quoting DM-only (non read-aloud) text;
a fact whose text uses words its quote does not; an exit quoting no connection the source states;
actors (not compiled yet); and anything the room loader itself refuses.

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
runtime does not ship. Stats are dm-only: the player view carries names, never AC, hit points or bonuses.

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
