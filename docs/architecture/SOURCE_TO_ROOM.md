# Source-to-room authoring

**Status:** built on branch `kit-source-to-room`, which sits on PR-M (#97, `kit-monster-initiative`), so
authored rooms validate with real `triggers` and save riders, not a passthrough.
**Why (Brendon, 2026-10-04):** no more hand-written room files. When the PC nears a keyed area, Kit
reads that area's keyed text from the book and writes the room file herself; the engine checks it;
play goes on. Stages are still fleshed out just in time by the room loader (ROOM_LOADER.md §1).
**Code:** `runtime/kit_source.py` (book text, keyed-area parser, level notes, geometry),
`runtime/kit_author.py` (packet, validator, repair loop, session cache, CLI, `author` links), small
hooks in `kit_rooms.py` (`resolved_link`), `state_context.py` (`Runtime.path`, `authored_dir`) and
`kit_agent.py` (`author_ahead`, the adjudicator's `authored`).

## 1. The book text never enters the repo

- Read from a local path: `KIT_SOURCE_TEXT`, else `config/kit_source.json` `{"text": "<path>"}`
  (gitignored). With neither, `kit_author` exits 2: "no book text ... never committed".
- Rooms written from it are cached beside the session database, in `<db>.authored/` (gitignored as
  `*.authored/`). They quote the book, so they are never committed either.
- `BookTextNeverInTheRepo` greps every tracked file (`git grep -F`) for a 60-character span from the
  middle of every long line of the configured source; it is skipped where no source is configured.
- Tests use `tests/fixtures/authoring/keyed_text.txt`: SYNTHETIC keyed text in the book's style, with
  an NPC room (a toll-keeper, a bell with responders, an Insight DC), a trapped hall with sub-areas
  (a pressure plate, a save), and a monster lair ("they attack all who enter"), plus a numbered
  sidebar and a next-level "1." that must not read as areas.

## 2. Areas, notes, geometry

- **Areas** (`kit_source.keyed_areas`): the level's headings come from `MAP_INDEX.md` ("Indexed room
  headings"). The parser walks the book for them in order (exact title, so a numbered list elsewhere
  is not an area) and takes sub-areas (`17a.`, `17b.`) between a parent and the next heading. A
  parent's own lines before its first sub-area are its `intro`. The level's last area stops at the
  next level's "1.", a "Chapter"/"Appendix"/"Level N:" line, or "Aftermath". Level 1 of the book
  parses to 88 areas (1 ... 41, with sub-areas).
- **Level notes** (`kit_source.level_notes`): from the level DM layer (MAP_INDEX "Level layer"): the
  geometry binding rules, every line naming the area by number or range ("Areas 6–8", "Areas 23, 28,
  and 39"), the room-scoped NPC audit, and each preloaded NPC (motive, plan) that the keyed text names.
- **Neighbours:** areas the slice names ("area 17b"), areas whose own text names this one (ids and
  titles only, never their text), and sibling sub-areas. The parent is the container, not a way out.
- **Geometry:** the DM map is a licensed image the runtime cannot read (and it is not on this box).
  A machine-readable **geometry ledger** (`KIT_LEVEL_GEOMETRY`, or
  `docs/campaign/levels/geometry/LEVEL_NN.json`: `{"areas": {"2a": {"exits": [{"to", "kind",
  "secret"}]}}}`) binds an area's exits; then any exit to an area the ledger does not connect is
  refused. **No ledger exists for any real level yet**; without one the packet says `bound: false`
  and the rule is: exits only to named neighbours plus one approach outside the area's own way in,
  nothing invented. Every accepted room then carries the warning `geometry unbound`.

## 3. The authoring packet (`kit_author.packet`)

`stage: author_room`, `room_id`, `source_hash`, the area (`keyed_text`, parent `intro`, sub-areas),
`named_neighbours`, `level_notes`, `geometry`, the room `schema` with its limits (room 16,000 B,
dm_only 9,700 B, claims_here 3,150 B, 2 attempts) and the SRD creature list, the `hard_rules`, and
the `submit` command. It never carries another area's text (`AuthoringPacket.test_it_never_carries_
another_area_s_text`). Level 1's packets run 7.2-9.2 KB (17a: 7,190 B compact).

Hard rules, in short: data only; contents, creatures, traps, treasure and numbers from keyed_text;
geometry from geometry and neighbours, `source_area` on every area; a stat block on every creature
that can fight (`{"srd": ...}` or inline, save riders as PR-M defines); **Kit emits the triggers
herself** ("if the corpse is disturbed, the centipedes emerge and attack" is a `disturb` trigger with
hidden actors; "attack all who enter" is an `enter` trigger); hidden actors named nowhere public;
alarms list responders; the approach is tease-only; checks on hidden truths are claims with the
book's DC; onward areas carry `room_link: {"author": {"level", "area"}}`.

## 4. Validate, repair once, fall back

`kit_author.validate` reports **every** error at once (the repair gets one try):

1. authoring rules: one object, size, data only (no code-like keys or values), `id` and `source_ref`,
   `source_area` in the allowed set (another area's stand-in must be `outside`), `author` links to
   named neighbours only, ledger exits; the keyed text sets creatures off but no `triggers`; a hidden
   actor no trigger wakes, or one not `visible: false`; a trigger's actor with no stat block; a
   hidden actor's name or kind in a visible fact, area name/called/arrival, tease, heard sound or exit
   label (singular and plural); a story hook `by` a hidden actor (who cannot raise it); a claim DC the
   book does not give (a warning);
2. the room loader's own checks (`kit_rooms.check_room`), plus the later-stage compilers even when the
   first framing fails, and alarm-looking facts with no responders as errors;
3. a **mount probe**: `start_session` on a throwaway database, building the real first packet; a
   hidden actor id in its public half is an error.

| Answer | When | What the host does |
|---|---|---|
| `accepted` | valid | cached at `<db>.authored/<level>-<area>-<hash16>.json`; `start --room <path>` or walk into its link |
| `repair` | first failure | fix the listed `errors` (the `packet` comes back with `previous_room`), submit again |
| `fallback` | second failure | `flag: authoring_fallback`, `improvise_from: keyed_text` with the text: Kit runs it off-engine, flagged; the area's links then refuse with this record |
| `cached` | already accepted | nothing to write |

Each job is a file beside the room (`.job.json`: status, attempts, errors). A fallback is final for that
source hash; a changed source (new hash) asks again.

## 5. In play: links and authoring ahead

- An area's `room_link` may be `{"author": {"level": "01", "area": "17b"}}` (optional `area` in that
  room, default its `starting_area`). Arriving mounts the session's accepted room
  (`kit_rooms.resolved_link` -> `kit_author.Session.resolve_link`). Not authored yet: the move is a
  pending ruling with `host_error.error: room_not_authored` and the `request` command; nothing commits.
- **Latency:** every prepare packet one step from such a link carries `author_ahead` [{level, area,
  via, status, request}]. The host authors it between turns, while the player reads the doorway, so
  the room is ready by entry (the cheap pre-pass). The same-pass variant (authoring inside a turn's
  output) is not built: it would grow the turn packet by ~7-9 KB and the output by the room.
- A 6c, watchroom or other hand-made room has no `author` link, so its packets are unchanged
  (6c engine probe byte-identical).

## 6. CLI

```sh
export KIT_SOURCE_TEXT=/path/to/local/book.txt
python3 -m runtime.kit_author request --db kit.sqlite --level 1 --area 17a   # packet, or cached/fallback
python3 -m runtime.kit_author submit  --db kit.sqlite --level 1 --area 17a --input-file room.json
python3 -m runtime.kit_author status  --db kit.sqlite --level 1 --area 17a
python3 -m runtime.kit_agent start --db kit.sqlite --room <accepted room_path> --sheet <sheet>
```

Options: `--cache DIR`, `--source PATH`, `--map-index`, `--ledger`, `--pretty`.

## 7. Gaps

1. **No geometry ledger for any real level.** Exits are bounded by the keyed text's own references
   (named or naming), which is not adjacency: a text may name an area it does not touch ("see area
   18"). A Level 1 ledger needs someone who can read the DM map.
2. **The deployed GPT needs the book text in its sandbox** and `KIT_SOURCE_TEXT` pointing at it.
3. **Disturb verbs:** PR-M's `disturb` fires on move/search/enter of a handled feature. In the 17a dry
   run "I search the corpse", "I roll the basilisk over" and "I poke the corpse" fire it, but "I pry
   the claw open" and "I take the orb from the claw" are pending rulings, so the most natural 17a act
   does not wake the nest (a router/PR-M item, not room data).
4. **A room whose only creatures are hidden cannot have a story hook**: hooks need a speaking actor
   (`by`), and a hidden actor cannot raise one. Such rooms use `purposes` and the tease without
   `points_to`.
5. No same-pass authoring (above); no per-stage partial authoring (the whole area is one room file).
