# Project Status

Current development truth is GitHub `main`. This note describes the executable runtime on that branch. An older pinned ZIP is a snapshot of whatever commit is in its filename.

## What runs

Kit is a persistent persona whose principal vocation is Dungeon Master. In a live game the Python runtime owns rules, state, and hidden facts. Kit owns judgment and voice. Outside a game turn she is still Kit, and conversation is not game state.

The play bridge is `runtime/kit_agent.py`. A turn is `prepare` (or `prepare --one-pass`) and then `decide`/`finish` or `complete`. The model submits a private decision and a public performance. The runtime adjudicates and commits world changes. The model does not write storage. The `play` command calls a paid API and is not used.

### Room loader

`runtime/kit_rooms.py` mounts any room file in the repo's room format. The contract is `docs/architecture/ROOM_LOADER.md`. A room is data: areas, exits, facts, actors, and optional mechanic blocks (claims, procedures, tolls, combat, attitudes, story, agenda, texture). An unsupported block fails the mount. Rooms can chain in one session when an area carries a `room_link`. A room that cannot mount fails before any turn is committed, and Kit has a plain line for the table.

Play inside a mounted file is read from state, in four stages: approach, first look, exploration, resolution. Each stage prepares only what that moment needs from the file already loaded. That staging is the loader. It does not write the room.

`start` with no `--room` still opens `tests/fixtures/level_01_area_06c.json`. That path is a leftover fallback so an unnamed start and the old suite have a file. Area 6c is one past regression room. It is not the reference room, and it is not a template. The other room files on `main` are a synthetic watchroom (`tests/fixtures/rooms/watchroom.json`), a non-playable area 17a stub (`rooms/level_01_area_17a.json`), and an older synthetic feasibility fixture. None of them was built from the book at approach time. No committed room file yet carries a real `room_link`; the chain tests add links on temporary copies.

### Source-to-room authoring

The direction of the work is that a keyed area of the book becomes a room file when the PC approaches, and the loader mounts that file. That authoring path is in progress and is not on `main`. There is no `kit_source` or `kit_author` module in this tree, `docs/architecture/SOURCE_TO_ROOM.md` is not here, and the book's keyed text is not in the repository. The context packet still lists source retrieval as a missing production layer. Until authoring lands, a room plays only when a room file already exists.

### What the bridge already does

Present and tested, for whatever room file is mounted:

- SQLite snapshots, an append-only event ledger, stale-writer checks, idempotent retries, and an atomic commit of an accepted turn with its world changes.
- A player-safe projection. Hidden facts stay out of what the player is shown.
- Character sheets (`character_sheet_v1`).
- Claims and knowers, card procedures, tolls, a minimal fight, attitudes, and a story brief, each only when the room file declares the block. Agenda code is room-agnostic; no room file in the repo currently declares an `agenda` block.
- Scene discernment and a saved private decision before the public performance.
- Performance checks for secrecy, room-fit, and the expression floors the current guards implement.
- Session and room manifests, with hash echo and `rehydrate`.
- Table talk, which is not a PC action.
- Voice files joined to the personality core on each turn.

The same packet still names what is absent: a rules resolver, source retrieval, level-story state, Halaster state, faction ticks, a player model beyond evidence-cited notes, and character patterns.

### Personality

`docs/personality/dm-personality-core.md` is the live identity. `docs/voice/` is loaded with it. The core influences taste and emphasis. It does not override source, rules, state, NPC knowledge, geometry, or hidden information.

The core being loaded is not evidence that the spoken turn feels like Kit. Early live samples failed on voice, lifeless NPCs, an invented procedure, and wait time: character onboarding (2026-09-23) and the area 6c exchanges with Nik (2026-09-26 and 2026-09-29), recorded under `tests/playtests/`. Later engine work does not retire those failures. Quality is still judged in play.

### Maps, assets, and campaign docs

Map and art manifests live under `assets/`. Licensed image bytes stay out of the public repo (ADR 0003). The runtime does not request those assets by id during a turn.

`docs/campaign/` holds DM-facing level layers. They are design material. They are not mounted as the PC moves.

## Next

1. Land source-to-room authoring, so a keyed area becomes a room file when play reaches it, and prove it on rooms that were not hand-written in advance.
2. Keep rulings in the room file. The loader already refuses a room it cannot run; new mechanics should arrive as data, not as another room-specific code path.
3. Keep judging the spoken turn. A green suite is not a personality result.
