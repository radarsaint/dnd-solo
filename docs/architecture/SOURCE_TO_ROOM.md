# Source-to-room authoring

**Status:** built on branch `kit-source-to-room`, which sits on PR-M (#97, `kit-monster-initiative`), so
authored rooms validate with real `triggers` and save riders, not a passthrough.
**Why (Brendon, 2026-10-04):** no more hand-written room files. When the PC nears a keyed area, Kit
reads that area's keyed text from the book and writes the room file herself; the engine checks it;
play goes on. Stages are still fleshed out just in time by the room loader (ROOM_LOADER.md §1).
**Long term (Brendon, 2026-10-04):** the book is scaffolding; Kit will DM adventures she writes
herself. So the check is **source-agnostic**: a keyed area from any author (the book's keyed prose
now, Kit's own design doc later) is extracted into one **source manifest** shape, and the fidelity
diff reads only that manifest. How a particular source is *written* (its bold labels, DC notation,
parentheticals, "area N" references) lives only in a pluggable extractor, never in the checker.
**Code:** `runtime/kit_source.py` (book text, keyed-area parser, level notes, geometry),
`runtime/kit_extract.py` (extractors: keyed text -> source manifest), `runtime/kit_fidelity.py` (the
generic diff: room vs manifest, and the leak scan), `runtime/kit_traps.py` (trap schema and engine),
`runtime/kit_author.py` (packet, validator, repair loop, fallback stand-in, session cache, CLI,
`author_ahead`), `runtime/srd_creatures.py` (SRD 5.1 stat blocks), small hooks in `kit_rooms.py`,
`state_context.py`, `kit_handoff.py` and `kit_agent.py`.

## 1. The book text never enters the repo

- Read from a local path: `KIT_SOURCE_TEXT`, else `config/kit_source.json` `{"text": "<path>"}`
  (gitignored). With neither, `kit_author` exits 2: "no book text ... never committed".
- Rooms written from it are cached beside the session database, in `<db>.authored/` (gitignored as
  `*.authored/`). They quote the book, so they are never committed either.
- `BookTextNeverInTheRepo` greps every tracked file (`git grep -F`) for a 60-character span from the
  middle of every long line of the configured source; it is skipped where no source is configured.
- Tests use `tests/fixtures/authoring/keyed_text.txt`: SYNTHETIC keyed text in the book's style, with
  a lying warden (a cover story, the truth, a bell with responders, an Insight DC), a trapped hall
  with sub-areas (a needle plate with a save and half damage, a secret door), a stirge roost woken
  when its lantern is touched (treasure), and mirror duplicates over an illusory niche, plus a
  numbered sidebar and a next-level "1." that must not read as areas. Real-book tests
  (`tests/test_kit_fidelity.py BookAreas`) run only where a book is configured and read it at test
  time; they commit no book text.

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
  `docs/campaign/levels/geometry/LEVEL_NN.json`, or `docs/campaign/levels/LEVEL_NN_GEOMETRY.json`: `{"areas": {"2a": {"exits": [{"to", "kind",
  "secret"}]}}}`) binds an area's exits; then any exit to an area the ledger does not connect is
  refused. **No ledger exists for any real level yet**; without one the packet says `bound: false`
  and the rule is: exits only to named neighbours plus one approach outside the area's own way in,
  nothing invented. Every accepted room then carries the warning `geometry unbound`.

## 3. The source manifest (`kit_extract`) and the fidelity diff (`kit_fidelity`)

**Manifest** (`source-manifest/1`, one shape for every source):

```
{"version", "area", "extractor",
 "sentences": [{"id", "text", "secret", "private", "deception"?, "kind": prose|treasure|hazard}],
 "creatures": [{"kind", "count"|null, "hidden"|null, "sentence", "quote", "npc"?}],
 "context_creatures": [...from the parent's intro: allowed, not required],
 "npcs": [{"name", "kind"?, "sentence", "quote"}], "items": [{"name", "gp"?, ...}],
 "hazards": [{"damage": [{"dice", "type"}], "dc": [n], "to_hit": [n], ...}],
 "scripted": [{"sentence", "quote"}], "numbers": {"dc", "hp", "gp", "dice", "to_hit", "ac"},
 "must_carry": [sentence ids], "exits": [{"area", "title", "way", "secret", "sibling"?, "back_reference"?}],
 "secret_ways": bool, "vocabulary": [stems]}
```

`secret`: the source keeps it from the players; `private`: about something only a secret sentence
introduces earlier (so its words are not public vocabulary); a cover story ("she claims that ...")
is secret (carried dm-side) but its words are what the liar says aloud, so not private.

**Extractors** (`kit_extract.EXTRACTORS`): `keyed_prose` (a published adventure's keyed text: label
paragraphs like "Treasure.", parentheticals, "DC 15", "7 (2d6) piercing", "area 17b", creature
names from the SRD list, counts in words) and `design_doc` (Kit's own manifest, shape-checked and
passed through). A source picks its extractor (`Book.extractor`, or an area's own `extractor`/`manifest`).

**The diff** (`kit_fidelity.check(room, manifest, context)`), every difference at once:

- creatures: every one, with its count and visibility (hidden in the source -> `status: hidden`);
  no creature the source does not have; alarm responders stand for the creatures a bell sends;
  `source_claims: [{"quote", "actors", "facts"}]` settle what the manifest cannot place (two
  sentences for one beast); each quote must be in this area's text;
- named NPCs are actors; deception sentences are carried dm-side (hidden facts, secrets, claims);
- every secret, treasure and hazard sentence is carried (its distinctive words and its numbers);
- numbers: no DC, hp, gp or dice the source does not state, in any string; no magic item it lacks;
  stat blocks are `{"srd": name}` (hp/ac overrides only with the source's numbers), the source's
  own block, or `needs_stats: true` (then no trigger may start a fight with it);
- scripted conditions need triggers or traps, of the kind the wording gives (`scripted.on`: "if
  the corpse is disturbed" is a `disturb` trigger, not `enter`); hazards need a `traps` entry with
  the source's dice;
- no creature named anywhere in the room's text (scenery included) that this area does not have
  (SRD names, minus everyday words like guard or shadow): another area's monster stays there;
- ways: only to areas the source names as a way (or sibling sub-areas); a neighbour it only
  mentions ("kept in area 1") is no way; `uncertain: true` on every exit to another keyed area
  while unbound; a secret exit only where the source names a secret way (from either side), and a
  way the source makes secret stays `secret: true`; area and exit names in the source's own words;
- the **leak scan** over every player-visible field (visible facts, every handling line, area
  name/called/arrival/tease/heard, exit name/labels/go_text, visible actors, story hook text):
  hidden actors' names (the head noun always; a modifier the source uses openly, "glistening black",
  is not a tell), words only the secret sentences use (the feature that `holds` the secret may say
  them when handled; a named NPC's own name is not a tell; plain place words never are; a secret
  exit's own words show only once found), any DC, bonus, AC or hit points, and an approach tease
  that hints at something alive ("something many-legged skitters") where every creature is hidden.
  Treasure is carried but is not secret by being treasure (a crown on a statue is in plain view).

`tests/test_kit_fidelity.py` builds a faithful room mechanically from whatever manifest it is given
(`tests/authoring_rooms.py`) and breaks it 35 ways over every synthetic area and, where a book is
configured, 17a, 17b, 3, 21, 31, 28d and 35; each break is caught, and all at once together.

## 4. The authoring packet (`kit_author.packet`)

`stage: author_room`, `room_id`, `source_hash` (source + schema + validator + extractor versions),
the area (`keyed_text`, parent `intro`, sub-areas), `named_neighbours`, `source_manifest` (the
checklist, by sentence reference; another area's text never appears, a back-reference says only
whether it is a way), `level_notes`, `geometry`, the room `schema` (limits, SRD creature list,
`traps`), the `hard_rules`, and the `submit` command. Level 1's packets run 9.2-15.1 KB compact
(median 10.5 KB; 17a 10.7 KB).

## 5. Validate, repair once, fall back

`kit_author.validate` reports **every** error at once (the repair gets one try): the authoring
rules (data only, id, `source_area`, author links to named neighbours, ledger exits, trigger `on`
is disturb or enter, hidden actors need a waking trigger, a fact in, under or in the grip of a
handled feature must be that feature's `holds`, a graspable part word (claw, lid, hand, hook...) on a
handled feature or its held item must be in `parts`, `layer` rules below), the fidelity diff above, the room
loader's checks with every later-stage compiler (`every_problem`: all entries, not the first),
alarms with no responders, trap schema, and a **mount probe** (`start_session` on a throwaway DB).

| Answer | When | What the host does |
|---|---|---|
| `accepted` | valid | cached at `<db>.authored/<level>-<area>-<hash16>.json` (absolute path), stamped `authoring` {level, area, source_hash, validator} |
| `repair` | first failure | fix the listed `errors` (the `packet` comes back with `previous_room`), submit again |
| `fallback` | second failure | `flag: authoring_fallback`: the PC still walks in (below); a later good submit replaces it (`replaces_fallback`) |
| `cached` | already accepted | nothing to write |

**Never trusted on disk:** `start --room` and every author link re-check an authored room (stamp or
`authored-` id) against its source and the current hash; a hand-edited room, a hand-written
job.json, or a stamp from another source text or validator version does not mount. The session
remembers which source it authored a level from (`<db>.authored/sources.json`).

**The fallback stand-in:** an unauthored or failed area is still entered. `resolve_link` writes a
minimal valid room (`.fallback-<session>.json`, area `inside`): the keyed text as hidden facts for
Kit to improvise from, its named ways as uncertain author links, neutral names, stamped
`authoring.fallback`. Every turn there carries `authoring_fallback` (prepare packet, kit timing,
committed record, handoff line), `author_ahead` lists the area for retry, and the next entry after
an accepted submit mounts the real room. A fallback belongs to its session (the session id in the
DB's `session_meta`): another session authors the area afresh.

### Parts, held items and layers

A feature with graspable parts or a held item lists them (`PARTS_RULE`): `handling.parts` (the claw,
the lid, the hand) and `handling.holds` (the held item, its own fact, hidden allowed), so "I pry the
claw open" or "I take the orb from the claw" is Kit's declared handles on that feature and fires its
trigger (#97, ROOM_TRIGGERS.md).

A visible fact may carry `"layer": "obvious"` or `"layer": "detail"` (`LAYER_RULE`). The first look
into an area gives the obvious layer and holds the detail layer until the player looks there (#101,
`kit_reveal`). The validator refuses `detail` on a fact a trigger fires on or that holds an item, and
on a fact that describes the way on (it shares two or more content words, area names aside, with that
area's exit names and labels). Ids are never matched as words. Leaving `layer` out is fine: the engine
works it out from the room data.

## 6. Traps (`kit_traps`)

`traps: [{"id", "on": {step|enter: area} | {disturb|open: fact}, "feature", "effect": {save|check,
dc (the source's, or null + needs_dc), damage [{dice, type}], attack?, condition?, half_on_success},
"detect", "disarm": [thieves_tools|sleight_of_hand {dc} | jam {with} | break {object} | spell],
"reset": once|auto|manual, "reveal", "spotted"}]`. On arrival a step/enter trap is spotted by
passive Perception against `detect.dc` (then stepped around), else it springs; a save or check is
the player's Avrae roll through a `roll_call` interstitial (no DC shown), the next input with the
roll lands the source's damage (dice average, halved on a success where it says so). Disarming:
`jam` needs no roll; tools or careful hands need a stated roll; `break` uses the SRD object table
(data only so far). `reset: auto` re-arms.

## 7. In play: links and authoring ahead

- An area's `room_link` may be `{"author": {"level": "01", "area": "17b"}}`. Arriving (a move into
  it, not any commit while standing in it) mounts the session's accepted room, else the fallback.
- **Latency:** every prepare packet carries `author_ahead` [{level, area, via, status, request,
  depth?}]: every author link in the room, a fallback here for retry, and from an approach two
  steps out (the neighbours' named ways). The host authors them between turns.
- A 6c, watchroom or other hand-made room has no `author` link, so its packets are unchanged
  (6c engine probe byte-identical).

## 8. CLI

```sh
export KIT_SOURCE_TEXT=/path/to/local/book.txt
python3 -m runtime.kit_author request --db kit.sqlite --level 1 --area 17a   # packet, or cached/fallback
python3 -m runtime.kit_author submit  --db kit.sqlite --level 1 --area 17a --input-file room.json
python3 -m runtime.kit_author status  --db kit.sqlite --level 1 --area 17a
python3 -m runtime.kit_agent start --db kit.sqlite --room <accepted room_path> --sheet <sheet>
```

Options: `--cache DIR`, `--source PATH`, `--map-index`, `--ledger`, `--pretty`.

## 9. Gaps

1. **No geometry ledger for any real level.** Exits are bounded by the keyed text's own references
   that read as ways; that is not adjacency. A Level 1 ledger needs someone who can read the DM map.
2. **The deployed GPT needs the book text in its sandbox** and `KIT_SOURCE_TEXT` pointing at it.
3. **Traps:** `break` is data only (not engine-run); out-of-combat trap damage is tracked as state
   `hazard_damage` (and per trap), not yet the fight's PC hit points.
4. **Fallback swap:** an accepted room replaces a fallback on the next entry, not mid-scene.
5. The extractor is heuristic prose reading; where it cannot place something the room settles it
   with `source_claims`, and the checker holds the room to the quote.
6. No same-pass authoring; no per-stage partial authoring (the whole area is one room file).
