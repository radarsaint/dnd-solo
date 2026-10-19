# START HERE: how to read this ZIP

> **Development / project work:** start with [PROJECT_BOOTSTRAP.md](PROJECT_BOOTSTRAP.md). It carries the project-wide context bootstrap. This file is the live-play/repository map, not the cross-agent work queue.

This is the `dnd-solo` repository: the runtime, docs, and test material for Kit (Kitiara), an AI Dungeon Master for solo D&D.
Kit runs a game by calling a Python engine in this folder (`runtime/`). The engine owns rules, state, and hidden facts. Kit owns judgment and voice.
Most files here are for the people and agents building Kit, not for play. The lists below say which is which. Don't move or rename anything: the engine finds files by path.

## If you are Kit running a game

Read and run in this order:

1. `AGENTS.md`: who you are and the bridge rules. Follow it.
2. `docs/personality/dm-personality-core.md`: who Kit is in every context. Read it before the first turn.
3. `docs/voice/`: Brendon's table voice. The engine loads these files into every turn for you, so you don't need to open them mid-game.
4. Run the engine from the repository root (Python 3.10+, no installs). These are the commands from `docs/CUSTOM_GPT_SETUP.md`:
   - First contact: `python3 -m runtime.kit_agent start --db kit.sqlite` is the lobby. It mounts nothing; Kit asks how the player wants to use her this session and names only what `available` lists (rooms packs and rooms, saved games, character sheets). Talk, debrief, or working on a character or a scene need nothing more. Do not assume an adventure.
   - They asked for Dungeon of the Mad Mage: `python3 -m runtime.kit_agent start --db kit.sqlite --campaign dotmm --sheet <file>`. The playable rooms come from a private rooms pack the host attaches next to this ZIP; `start` finds it, or pass `--pack <path>`. Add `--room <room id>` only for a room the pack lists. Say `table_line`. Never pass `--regression`. With no pack attached, the stage is `campaign_unavailable`: say so and stop.
   - They want to play and have not named a game: ask which one. Do not run `start`.
   - Resume a saved game they want to continue: copy `kit.sqlite` to the repository root and run `start` with no `--campaign`. `stage` will be `resume`. Do not open a second room.
   - Every in-fiction turn: `python3 -m runtime.kit_agent prepare --one-pass --db kit.sqlite --action-file <file>`, write one `{"decision", "performance"}` that follows the packet, then `python3 -m runtime.kit_agent complete --db kit.sqlite --turn-id <id> --input-file <file>`.
   - Lost the manifest copy: `python3 -m runtime.kit_agent rehydrate --db kit.sqlite --turn-id <id>`.
   - Out-of-character talk during a scene: `python3 -m runtime.kit_agent prepare --table-talk --one-pass --db kit.sqlite --action-file <file>`, then `complete`.
   - Player feedback: `python3 -m runtime.kit_agent feedback --db kit.sqlite --text "<their words>"`.
   - Character changes: `python3 -m runtime.kit_agent character --db kit.sqlite --sheet <file>` (or `--held ... --active ...`).
   - Show the player only the committed `spoken` text. Never run `play` (paid API).

Without `--room` and without `--campaign`, `start` is the lobby. It does not open a room and it does not assume Dungeon of the Mad Mage. There is no fallback room; Area 6c is never one.

## Load at table

Kit reads these, or the engine loads them during play. Everything in this block must exist (`tests/test_start_here.py` checks it).

<!-- load-at-table:begin -->
Kit reads:
- `AGENTS.md`
- `docs/personality/dm-personality-core.md`

The engine runs or loads these by itself (no need to open them):
- `runtime/*.py`: the engine
- `runtime/data/srd_5_1_prices.json`: SRD equipment prices
- `docs/voice/*.md`: table voice, joined to the personality core every turn
- `docs/personality/kit-taste.json`: texture palette
- `rooms/*.json`: room files the loader mounts with `--room`
- a private rooms pack the host attaches (a manifest.json with schema `kit-rooms-pack/v1`, and its room files): not in this ZIP; `runtime/kit_pack.py` finds it or takes `--pack`, and unzips it under .kit-packs next to the save
- the runtime fixtures under `tests/`, listed below
<!-- load-at-table:end -->

### Runtime fixtures under tests/ (don't delete)

`tests/` is dev-only, but the engine loads these files from it:

<!-- runtime-fixtures:begin -->
- `tests/fixtures/characters/example_pc.json`: an engineering example sheet (Wren). Not the campaign character. Player-facing start does not load it. Use it only when the player explicitly asks for the example.
- `tests/fixtures/level_01_area_06c.json`: a historical regression fixture. Mount it only with `start --regression --room` and this path. It is not the campaign and not a fallback.
- `tests/fixtures/rooms/watchroom.json`: a synthetic room (not from the book) that engineering tests mount with `--room`
<!-- runtime-fixtures:end -->

## Reference only when told

Open these only when `AGENTS.md`, the GPT instructions, a runtime message, or the person you're working with points you to them. They explain procedure. They are not game content, and you don't read them every turn.

<!-- reference:begin -->
- `docs/CUSTOM_GPT_SETUP.md`: GPT setup and the paste-ready instructions
- `docs/architecture/kit-06c-play-slice.md`: bridge procedure, commands, and retries. Its examples come from one early test room. The procedure applies to every room.
- `docs/architecture/MANIFESTS.md`: session and room manifests, hash echo, `rehydrate`
- `docs/architecture/ROOM_LOADER.md`: how room files mount and chain
- `docs/architecture/ROOM_PACKS.md`: the private rooms pack: manifest format, where `start` finds it, its errors
- `docs/architecture/HOST_TIMING.md`: turn timing stamps
- `docs/architecture/kit-claims-knowers.md` and `docs/GPT_HANDOFF_CLAIMS.md`: who knows what
- `docs/architecture/kit-agendas.md` and `docs/GPT_HANDOFF_AGENDAS.md`: what NPCs want and when they act
- `docs/architecture/kit-expression-gap.md`: how speech is checked
- `docs/architecture/KIT_VISUAL_STYLE_SPEC.md`: house visual language and generation rules; load when Kit is asked to create new campaign art
<!-- reference:end -->

## DEV ONLY: do not read during play, do not quote to players

These are for building and testing Kit. During a game, don't open them, don't quote them, and don't use them as a source of facts, rooms, NPCs, or voice. Each top-level dev folder has a `README_FOR_GPT.md` that says the same.

The old in-repo BFDM mirror is not in this branch. Canonical BFDM research is the radarsaint/bfdm-corpus repository. Do not recreate a corpus directory here.

<!-- dev-only:begin -->
- `docs/campaign/`: campaign DM layers for every level. Spoilers.
- `tests/` (except the runtime fixtures above): unit tests, `tests/playtests/` records, `tests/scenarios/` scripts
- `docs/collab/`: the agent collaboration protocol and `docs/collab/BOARD.md`
- `docs/architecture/` (except the reference files above): design specs and plans
- `scripts/`: dev and test tools (batch runner, probes, replays, asset import)
- `docs/decisions/`: architecture decision records
- `docs/personality/dm-personality-development.md`, `docs/personality/dm-personality-layer-v0.1.md`, `docs/personality/kit-personality-implementation.md`: how the core is tuned, and design history. Only `docs/personality/dm-personality-core.md` is live.
- `state/`: project status notes
- `assets/`: map and art indexes (the licensed images aren't in the repo)
- `README.md`, `CONTRIBUTING.md`, `docs/WHAT_WE_ARE_BUILDING.md`: overviews for humans
<!-- dev-only:end -->

Many dev files use one early test room (Level 1, area 6c) as their example. That is history, not a pattern to follow.

## Hidden information

`docs/campaign/` and the hidden facts in every room file (anything marked `"visible": false` or `"secret": true`, hidden creatures, and everything the engine sends as `dm_only`) are DM-only. Never show them to a player, list them, summarize them, or hint at them. That includes "what's in the ZIP" questions: if a player asks what files are here, describe the project in general terms and don't list campaign or room contents. The engine decides what the player has learned, and only committed `spoken` text reaches the player.

The published adventure's keyed text isn't in this ZIP. When a room needs it, it comes from the engine or a file the host supplies, never from memory.
