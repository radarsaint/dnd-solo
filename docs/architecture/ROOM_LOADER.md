# Room loader

**Status:** AS BUILT (KRABS §0) on branch `kit-room-loader`, with the gaps listed at the end.
**Why:** the Area 17a live start failed (PR #86, `tests/playtests/2026-10-03-area-17a-host-startup-failure.md`)
because the runtime could only run 6c, so the host tried to build 17a support during play.
**Goal:** any room file in the repo's room format mounts and runs with no 6c code path; rooms
chain in one session; a room that cannot mount fails fast with a plain line from Kit.
**Code:** `runtime/kit_rooms.py` (loader, stages, carry-over), plus small edits in
`runtime/kit_agent.py`, `runtime/state_context.py`, `runtime/kit_brief.py`, `runtime/kit_texture.py`.
Line numbers below are for this branch unless marked *main*.

## 1. A room is four stages, fleshed out just in time

The stages are read from state (`kit_rooms.stage`, kit_rooms.py:196), never a rail. The PC
can start in any stage (`start --area`), barge in, or go past; each stage prepares only what
it needs at that moment.

| Stage | What it is | Needs from the room file | Prepared, and when | Story brief's part |
|---|---|---|---|---|
| **1. approach** | Outside, not yet in: doors, what can be seen or heard | an area marked `"outside": true`; its visible `facts` (what shows or sounds through the door); its `exits` with `name` and per-area `labels` | at mount: the area, its visible facts and known exits (`Runtime._observe`). Nothing else. | `stage: approach`; endings "goes in" / "goes past" when the area has no story block (kit_brief.py:416) |
| **2. first look** | Inside, no turn taken here yet: the framing that carries the hook | the room area (`name`, optional `arrival` line for the opening event); its visible facts and actors; `story.<area>.hooks` | on arrival: the opening packet (`prepare_opening`, kit_agent.py:2714) and the brief for that area (`kit_brief.brief`, kit_brief.py:366, called from `prepare_inputs`, kit_agent.py:2627) | `hooks` with `raise_by_beat`; `stage: first_look` |
| **3. full exploration** | The back-and-forth of choices and checks | whatever mechanics the file declares: `claims` (checks), handled features (`facts.<id>.handling`), `procedures` (card games), `tolls`, `combat`, `attitudes`, `agenda`, `texture_palette` | each when play first reaches it: a card engine only on a card call (`card_procedure`, kit_agent.py:357); a fight only when one starts; a texture palette checked the first time play draws on it (`kit_texture.area_palette`, kit_texture.py:64) | the beat counter (`story_beat` via `kit_brief.beat_event`, kit_brief.py:499, from `turn_events`, kit_agent.py:2279) makes an undelivered primary hook `raise_now` after `within_beats`, whatever stage the PC jumped to; thresholds cross (`threshold_events`, kit_brief.py:527) and shift attitudes (`kit_attitude`) |
| **4. resolution** | Out again, or past without going in | an outside area (or a `room_link` area) beyond the room | on arrival there: if the area has `room_link`, the next room mounts in the same commit (state_context.py:462) | `stage: resolution`, `resolved: left | bypassed`; story `endings` |

A **bypass** is a resolution: leaving by an outside route without ever entering an inside area
gives `resolution(...) == 'bypassed'` (kit_rooms.py:190). **Barge-in** is the PC's first turn in
the room being an act, not a look: the stage goes `first_look` -> `explore` on that turn and the
hook still fires from the beat counter (`raise_now`), so skipping the doorway never skips the
hook. `scene_close` (state_context.py:632) still closes a scene inside a room; it does not end
the room (see gaps).

## 2. What a room file contains

Required (checked at mount, kit_rooms.py:79): `id`, `starting_area`, `areas`, `exits` (two
areas each, `secret`, a `label` from each side), `facts` (`area`, `text`, `visible`), `actors`
(`location`, `status`). `resources` defaults to `{}`; `fixture_only` is optional.

Area fields: `name`; `called` (how a line names it: "the short passage"); `outside`
(approach/beyond); `arrival` (the opening event line); `room_link` (`{room, area}`: arriving
here mounts that room). Exit fields: `name` ("the south door"; its words are what the player
may say), optional `go_text` per area. Fact field `handling` (`nouns`, `holds`, `look`,
`enter`, `move`): a feature the router acts on by its own nouns (6c's tub).

**The story brief** (`story.<area>`, all optional, kit_brief.py header): `about` (what the
scene is for), `purposes` (what each setup is for), `hooks` (`by` an actor, `primary`,
`within_beats`, `delivered_when`), `thresholds` (`when`/`then`, optional `trigger` and attitude
`shift`), `endings`. Who wants what comes from `actors.<id>.motive`/`immediate_goal`/`traits`
and `agenda` wants; what each NPC is *for* is the hook it carries (`by`) and the purposes that
root on it. A room with no story block still gets a sparse brief from its actors.

Optional mechanic blocks, each off unless declared: `claims`, `procedures` (`kind: card_game`,
`game: twenty_one | three_dragon_ante`), `tolls`, `combat`, `attitudes`, `agenda`,
`texture_palette`, `leak_phrases`/`leak_keywords`, `public_performance`. Any other top-level
block is refused as unsupported (`KNOWN_BLOCKS`, kit_rooms.py:36), as is any other procedure
kind or card game (kit_rooms.py:124). Room files hold only data.

## 3. Mount and fail-fast contract

`kit_rooms.load_room(path)` (kit_rooms.py:170):

1. **Up front, blocking (stages 1-2):** the file exists, parses, is an object; the required
   blocks; `exits`, `facts`, `actors` are objects; referential integrity of areas, exits,
   facts, actors, `room_link`, feature
   `holds` (kit_rooms.py:79). Every problem is named, not just the first.
2. **At mount, validated but not built (stages 3-4):** unsupported blocks and kinds, then the
   existing compilers run as checks only: claims, attitudes, agenda, tolls, story, each card
   procedure's config (kit_rooms.py:136). No engine, brief, or fight is created.
3. **Lazily:** the texture palette, per area, the first time play draws on it
   (kit_texture.py:64). It was the largest mount cost (~7-19 ms for 6c) and is never needed for
   the first framing.

A room that fails raises `RoomMountError` (kit_rooms.py:49):
- **Host sees** (`start` exits 2, stderr JSON): `{"stage": "rejected", "error": "room_unmountable",
  "room": <path>, "problems": [...], "table_line": ..., "committed": false}`; nothing is created.
- **Kit says, at the table:** `TABLE_LINE` (kit_rooms.py:31): *"I can't run that room yet; it
  isn't set up for play. We can stop here or go another way."* Plain, brief, no improvised room.
  (GPT owns Kit's voice; this is the floor and GPT may reword it.)
- **Mid-chain:** the adjudicator checks a linked room before accepting the move
  (`_check_onward`, kit_agent.py:925). If it cannot mount, the move is refused as a pending
  ruling whose message is the table line, with `host_error` attached; nothing commits and the
  session plays on. `Runtime._commit` checks again inside the transaction (state_context.py:462).

## 4. Rooms in a row

Arriving in a `room_link` area mounts the linked room in the same commit, no host step
(state_context.py:462, `kit_rooms.mounted_state`, kit_rooms.py:246):
- the room left is archived in `state['rooms'][id]` with its resolution (`left`/`bypassed`) and
  all of its room-scoped state; coming back restores it as it was left;
- the character carries over (`SESSION_KEYS`, kit_rooms.py:45): sheet, `pc_state`, Kit's memory,
  roll seed, time; `fold_pc` (kit_rooms.py:222) writes current HP (after any fight) and gold
  (table net, tolls paid outside a stake) into the sheet, and what was taken into `carried`;
  each change is folded once, even across revisits;
- nothing room-scoped crosses: actors, facts, exits, procedures, tolls, combat, claims, canon.

**Long-lived hosts.** A chat host or `KitAgent` keeps one adjudicator for the whole session.
`prepare_turn` calls `RoomAdjudicator.mount(runtime.source())` every turn, because a commit may
have mounted another room since the last one. The adjudicator's only room-derived state is
`source`. Everything else is read from it on each call: the router's feature nouns and exit
words (`room_words`), exits, handled features, procedures, tolls, attitudes, and the fight
config. The one module cache, the texture palette check (`kit_texture._CHECKED`), is keyed by
room id, area, and palette. `LongLivedHost` tests A -> B -> A through one bridge.

**Which exit.** `_exit_taken` picks the exit the player means:
1. The most specific match wins: the whole exit name first, then words that no other exit here
   shares ("the oak door" over "the iron door").
2. A word several exits share ("the door") narrows to one of two exits, but only if exactly
   one is left:
   - the exit in view, named in Kit's last line;
   - when the player says they're going back, the exit they came in by (`room.came_by`, which
     is cleared on a mount).
3. Otherwise Kit asks one short question, "The iron door or the oak door?", and nothing is
   committed. `WhichExit` tests this on a non-6c room with two doors.

A `room_link` whose `area` is not in the linked room is refused before the move, with the
table line and `host_error` (`kit_rooms.load_link`).

## 5. 6c hardcodes

Removed (line numbers on *main* 6a2b7ed):

| Where (main) | Was | Now |
|---|---|---|
| kit_agent.py:368 | `area_06c` gate: "This play slice covers area 6c only" | removed |
| kit_agent.py:2568-2572 | opening only in `area_06c`; "A newcomer has reached the card room." | any area; the line is 6c's `arrival` |
| kit_agent.py:42, 3189, 3295 | `start`/`init` always read the 6c fixture | `--room` (and `--area`) via `load_room`; 6c is the default only |
| kit_agent.py:478-479 | every exit was `south_door`, "into the short passage" | `_exit_taken` picks the exit the words name (or the only one); text from exit `name`/`go_text` and area `called` |
| kit_agent.py:786-797 | stealth always left by `south_door` | same exit chooser |
| kit_agent.py:260 | exit words `south|door`; `'tub' not in words` | general `door`/`out` plus the room's own exit-name words; the room's features |
| kit_agent.py:178-199, 262-274 | `TUB_ENTRY`, `TUB_MOVED`, `'tub'` look | built from a fact's `handling.nouns`; kinds `move_feature`/`enter_feature`/`inspect_feature` (were `*_tub`) |
| kit_agent.py:481-493 | tub texts and `tub_stash` in code | 6c's `facts.tub.handling` (`look`, `enter`, `move`, `holds`) |
| kit_agent.py:499 | evidence "social bid at the card table" | "social bid" |
| kit_agent.py:645 | "start a fresh area 6c test database" | "start a fresh database" |
| kit_agent.py:3241, 3393 | default db `kit-06c.sqlite`; banner "Kit's area 6c test" | `kit.sqlite`; banner names the room id |
| kit_agent.py `Room6CAdjudicator` | 6c in the class name | `RoomAdjudicator` (all callers and tests) |
| state_context.py:254 | every palette checked at init | lazy, per area |
| state_context.py:959 | `source['fixture_only']` required | optional |

Left in, and why:
- `DEFAULT_ROOM` = the 6c file (kit_agent.py:45): `start` with no `--room` still plays 6c, the
  only full room; AGENTS.md (GPT's) documents that command. Changing the default is a call for
  Brendon and GPT.
- General-noun vocabulary in router and guard regexes ("dealer", "vampire", "fangs", "paint"):
  kit_combat.py:68, 111, 124, 312; kit_guards.py:386; kit_claims.py:489; kit_attitude.py:59;
  the card modules' "dealer". They are English words, not 6c ids, and fire only on matching
  text; making them come from actor labels is the router generalization, which stays parked.
- `kit_cards.game_of` defaults a card game with no `game` key to `three_dragon_ante`
  (kit_cards.py:879): 6c's Three-Dragon Ante block has no `game` key. The loader accepts that
  default explicitly.
- The card modules are imported unconditionally but inert: no card machinery runs unless a
  `card_game` procedure is declared (`card_procedure` returns None; tested).
- Comments and docstrings that cite 6c history.

**Router touch the loader needed (the only one):** `room_intent` takes the room's words
(`RoomWords`, kit_agent.py:210; `room_words`, kit_agent.py:226): feature nouns and exit-name
words from the file, because the tub and the south door were hardcoded in the router. Also
`head`, `charge`, `barge`, `burst`, `continue` count as leaving, but only with a named exit
(barge-in and bypass lines). Nothing else in the router changed. The V1-V11 engine probe output
is identical except for the renamed `inspect_feature` kind.

## 6. Proof

`tests/test_kit_room_loader.py`. All dice and decks are pinned.
- **Headline, `ChainOfRooms`:** one character, one session, 6c -> watchroom -> 17a stub -> back
  to the watchroom (`scripts/room_chain_walkthrough.py`; transcript
  `tests/playtests/2026-10-03-room-loader-chain-walkthrough.md`). It asserts:
  - each room mounts on arrival with no host step;
  - rooms left are archived as left or bypassed, and come back as they were left;
  - nothing room-scoped crosses, and the whole first packet in the room returned to has no 6c word;
  - HP 32 -> 18 and gold 805 -> 795 carry over, and so does the coin taken;
  - barge-in goes straight to exploring and the hook still raises;
  - the bypass of 17a counts as a resolution;
  - a broken room is refused mid-chain with the table line and the session plays on;
  - every transition is fast.
- **The 17a stub** (`rooms/level_01_area_17a.json`, marked `stub`; GPT writes the content)
  mounts and runs a basic turn: approach -> through the doors -> first look -> explore.
- **Non-6c fixtures:** `tests/fixtures/rooms/watchroom.json` (feature, NPC, hook, way past) and
  `tests/fixtures/feasibility_room.json` both mount and run.
- **Barge-in and bypass** run on the watchroom and on the 17a stub.
- **Fail-fast:** each case names its problem, creates no database, and returns in milliseconds:
  missing file, bad JSON, missing blocks, bad starting area, unsupported block, kind, or card
  game. The CLI test checks stderr JSON with `table_line`.
- **No 6c ids remain in runtime string literals** (an AST scan).
- **The 6c suite stays green**, with behaviour read from its file: the tub texts, the south
  door, and the arrival line all come from the fixture.

## 7. Latency (this box; median of 3, `start` to first packet, sheet loaded)

| Room | main 6a2b7ed | this branch |
|---|---|---|
| 6c | 28 ms | 23 ms (palette now lazy) |
| 17a stub | cannot mount | 10 ms |
| watchroom fixture | cannot mount | 11 ms |
| feasibility fixture | cannot mount | 10 ms |
| each mid-chain transition (commit + mount + first packet) | n/a | 5-7 ms |

Python import of the runtime is about 80 ms on top, once per process. Runtime time to first
framing was never the 17a stall; the host's unbounded prep was (#86). The loader removes the
reason for that prep: a room either mounts in milliseconds or says plainly that it can't.

## 8. Gaps (for review)

1. **No real `room_link` yet.** The chain's links are added to temporary copies in the test,
   because which rooms truly connect is room content (17a's neighbours are GPT's to write).
2. **6c has no approach.** 6c starts inside; its `south_passage` is the way out. Entering 6c
   from outside needs content.
3. **Opening after a mount is the host's call.** The move turn's packet was built before the
   mount, so the first packet in the new room is the next `prepare` (or `prepare --opening`,
   which is allowed while no turn has been taken there). There is no automatic second packet.
4. **`first_look` is approximated** as "no turn taken in this area yet" (`room.turns_in`).
5. **Resolution only by leaving.** Story `endings`, a closed scene, or everyone gone while the
   PC stays do not set `resolution`. The close-scene CLI stays parked.
6. **A lazy palette that fails mid-play** surfaces as a host rejection (`InvalidChange`), not
   Kit's table line.
7. **Carry-over is thin:** the sheet's `hp` becomes current HP (no max, no rest); gold counts
   table net and tolls; taken things carry as text; room `resources` do not carry.
8. **Kit's memory carries across rooms** by design, under the same leak guards. The chain test
   commits engine turns directly, so it does not exercise carried episodes.
9. **Room files live in two places:** 6c stays in `tests/fixtures/` (14 test modules and the
   scripts load it from there) and the stub is in `rooms/`.
10. **Budget:** `stage` in the brief adds 42 B. The worst-case private context is 101,904 B
    against 103,000 (1,096 B left).

Spike: branch `kit-room-loader-spike` (`c5713b2`, no PR) answered one question: is dropping
the `area_06c` gate enough to run a non-6c room? No. The tub and `south_door` rulings were
hardcoded and either narrated a tub that isn't there or crashed (`Unknown fact`,
`Exit not discovered`).
