# Room loader

**Status:** AS BUILT (KRABS §0) on branch `kit-room-loader`, with the gaps listed at the end.
**Why:** the Area 17a live start failed (PR #86, `tests/playtests/2026-10-03-area-17a-host-startup-failure.md`)
because the runtime could only run 6c, so the host tried to build 17a support during play.
**Goal:** any room file in the repo's room format mounts and runs with no 6c code path; rooms
chain in one session; a room that cannot mount fails fast with a plain line from Kit.
**Code:** `runtime/kit_rooms.py` (loader, stages, carry-over), plus small edits in
`runtime/kit_agent.py`, `runtime/state_context.py`, `runtime/kit_brief.py`, `runtime/kit_texture.py`.
Line numbers below are for this branch unless marked *main*.

# Visual authoring extension

Room files may optionally give the visual bridge explicit **player-safe appearance data** on an area, fact, or actor:

```json
"visual": {
  "public": [
    "Weathered human watchman.",
    "Brass-trimmed leather coat."
  ],
  "public_counts": {
    "arms": 2,
    "eyes": 2,
    "swords": 1
  },
  "public_art_id": "watch-warden"
}
```

This is presentation metadata. It does not create a new source of hidden canon.

- `public` is a string or list of strings that may enter a player-facing visual brief once that area/fact/actor is already player-visible.
- `public_counts` records discrete anatomy/equipment counts that image QA should preserve.
- `public_art_id` may resolve an exact entity in `assets/art/index.json` after that actor is player-visible.
- Private visual facts must remain in normal DM-only source/state. The visual bridge deliberately does not read a `visual.dm_only` field.

The loader validates this shape at mount. A visual descriptor never makes an otherwise hidden fact or actor visible.

## 1. A room is four stages, fleshed out just in time

The stages are read from state (`kit_rooms.stage`, kit_rooms.py:361), never a rail. The PC
can start in any stage (`start --area`), barge in, or go past; each stage prepares only what
it needs at that moment.

| Stage | What it is | Needs from the room file | Prepared, and when | Story brief's part |
|---|---|---|---|---|
| **1. approach** | Outside, not yet in: doors, what can be seen or heard | an area marked `"outside": true` and joined to an inside area; its **`tease`** (required: what is seen or heard from outside that points toward the hook, which hook, and who is audible); its visible `facts`; its `exits` with `name` and per-area `labels` | at mount: the area, its visible facts and known exits (`Runtime._observe`), and the tease checked (`kit_rooms.tease_problems`). Nothing else. | `stage: approach`; `about` is the tease; `tease` carries `points_to` (the hook's id, never its inside text); `present` lists the actors heard from outside, each with only `label` and `heard` (tease-only: no card, wants or secrets); endings "goes in" / "goes past" when the area has no story block (`kit_brief.brief`) |
| **2. first look** | Inside, no turn taken here yet: the framing that carries the hook | the room area (`name`, optional `arrival` line for the opening event); its visible facts and actors; `story.<area>.hooks` | on arrival: the opening packet (`prepare_opening`, kit_agent.py:2748) and the brief for that area (`kit_brief.brief`, kit_brief.py:366, called from `prepare_inputs`, kit_agent.py:2657) | `hooks` with `raise_by_beat`; `stage: first_look` |
| **3. full exploration** | The back-and-forth of choices and checks | whatever mechanics the file declares: `claims` (checks), handled features (`facts.<id>.handling`), `procedures` (card games), `tolls`, `combat`, `attitudes`, `agenda`, `texture_palette` | each when play first reaches it: a card engine only on a card call (`card_procedure`, kit_agent.py:375); a fight only when one starts; a texture palette checked the first time play draws on it (`kit_texture.area_palette`, kit_texture.py:64) | the beat counter (`story_beat` via `kit_brief.beat_event`, kit_brief.py:512, from `turn_events`, kit_agent.py:2303) makes an undelivered primary hook `raise_now` after `within_beats`, whatever stage the PC jumped to; thresholds cross (`threshold_events`, kit_brief.py:540) and shift attitudes (`kit_attitude`) |
| **4. resolution** | Out again, or past without going in | an outside area marked `"beyond": true` (past the room), or any outside area once the PC has been inside or elsewhere outside; a `room_link` area | on arrival there: if the area has `room_link`, the next room mounts in the same commit (state_context.py:487) | `stage: resolution`, `resolved: left | bypassed`; story `endings` |

A **bypass** is a resolution: leaving by an outside route without ever entering an inside area
gives `resolution(...) == 'bypassed'` (kit_rooms.py:355). **Barge-in** is the PC's first turn in
the room being an act, not a look: the stage goes `first_look` -> `explore` on that turn and the
hook still fires from the beat counter (`raise_now`), so skipping the doorway never skips the
hook. **Pivoting straight to resolution** is starting in (or arriving at) a `beyond` area:
`start --area stair_down` on the watchroom is `resolution`, `resolved: bypassed`. Kit's
**opening framing** is not the player's turn: its `scene_entry` beat does not count toward
`turns_in`, so the first look lasts until the player acts, and an area is opened at most once
(`room.opened`). `scene_close` still closes a scene inside a room; it does not end the room
(see gaps).

## 2. What a room file contains

Required (checked at mount, kit_rooms.py:85): `id`, `starting_area`, `areas`, `exits` (two
areas each, `secret`, a `label` from each side), `facts` (`area`, `text`, `visible`), `actors`
(`location`, `status`). `resources` defaults to `{}`; `fixture_only` is optional.

Every block has a JSON type (`kit_rooms.BLOCK_TYPES`): `id` and `starting_area` are non-empty
strings; `source_ref`, `map_ref`, `test_precondition` strings; `fixture_only`, `stub` booleans;
`room_rules` a list; everything else an object, and every area an object.

Area fields: `name` (required, a non-empty string); `called` (how a line names it: "the short passage"); `outside` (not in
the room); `beyond` (an outside area past the room: arriving there is resolution); `arrival`
(the opening event line); `room_link` (`{room, area}`: arriving here mounts that room);
**`tease`** (required on every approach, i.e. an outside area that is not `beyond` and is joined
to an inside area):

```json
"tease": {
  "text": "Lamplight through the gap in the iron door, and someone inside humming the same four notes...",
  "points_to": "challenge",
  "heard": [{"actor": "warden", "sound": "a man humming four notes over and over"}]
}
```

`text` is what reaches the PC from outside and points toward the hook; `points_to` names a
story hook id (required when the room has hooks); `heard` lists actors who are audible from
outside, with what is heard. The tease is perceivable from the doorway, so it must not name a
secret. Exit fields: `name` ("the south door"; its words are what the player
may say), optional `go_text` per area. Fact field `handling` (`nouns`, `holds`, `look`,
`enter`, `move`): a feature the router acts on by its own nouns (6c's tub).

**Actor fields that change play** (all data; watchroom live game, 2026-10-04):

- `stat_block`: required on every actor who can fight, meaning `armed: true`, non-empty
  `guards`, starting `hostile` in `attitudes.start`, or already listed in `combat.actors`
  (`kit_rooms.fighter_problems`; a missing or unknown block is a `RoomMountError`). Give it
  inline (`{"ac": 16, "hp": 11, "attacks": [{"name": "spear", "to_hit": 3, "damage": 4}]}`)
  or cite an SRD 5.1 creature (`{"srd": "Guard"}`; the list is in `runtime/srd_creatures.py`).
  The combat engine reads these directly (`kit_combat.config`), so a room needs no `combat`
  block to fight on-engine. A `combat.actors` entry still counts (6c).
- `guards`: the exit ids this actor keeps. Leaving by one while that actor is here, awake, and
  not friendly or helpful (or by any exit past a hostile actor here) is a contest, not a
  move: the turn records a pending check (Athletics or Acrobatics against 10 + the actor's
  Athletics), and only a success moves the PC (`RoomAdjudicator._exit_blocked`). An exit
  nobody blocks stays instant.
- `public_performance.actor_cards.<label>.speech_floor`: `true` asks for the 30-word actor
  floor (6c's dealer). Default is no actor floor, so a terse voice (a guard of short questions)
  passes; the exchange still needs its 40 words across narration and speech.

**Hook delivery.** A `said` condition may set `"challenge": true`: any question the hook's
actor puts to the PC delivers it, however it is worded ("Who goes there?"). A hook is
delivered when its actor says it from another area too: the warden calling through the door
to a PC on the landing (a heard actor in the tease) latches the hook without adding a beat
(`kit_brief.heard_events`). Actors heard from an approach, and the people in the area the PC
walks into, may speak on that turn.

**Room-file checklist (for GPT).** A room mounts only when:

1. every block has its JSON type and every area is an object;
2. every approach has a `tease` (`text`, `points_to` a hook id, `heard` actors);
3. secrecy blocks follow the schema below;
4. every actor who can fight has a `stat_block` (inline or `{"srd": ...}`), and `guards` lists
   exit ids;
5. a primary hook is delivered by what its NPC says (`said`; add `"challenge": true` for a
   challenge however it is worded);
6. every alarm or escalation (a bell, a horn, a shout for help) says who answers it, on its
   fact: `"alarm": {"responders": [{"who": "guards from the gatehouse below", "count": 2,
   "stat_block": {"srd": "Guard"}}], "arrives_in_rounds": 2}` (`kit_rooms.alarm_problems`; a
   malformed block fails the mount, and a fact that reads as an alarm with no `alarm` block
   mounts with a loud `RoomWarning`, because Kit would otherwise invent the responders);
7. the room's dm_only part stays under 9,700 B and claims_here under 3,150 B;
8. **the approach is tease-only** (Brendon, 2026-10-04): from an approach area Kit gets the
   area's own facts and exits, its `tease`, and who is `heard` there (label and sound only).
   Nothing from inside reaches her there: no inside fact, no inside actor's card, wants or
   secrets, no inside story (`about`, hook text, endings). The tease names its hook by id
   (`points_to`) only. Put anything the PC should sense from outside into the tease or the
   approach area's own visible facts; first look and exploration begin on entry
   (`DoorwayBriefCarriesTheTease.test_the_approach_is_tease_only`).

**The story brief** (`story.<area>`, all optional, kit_brief.py header): `about` (what the
scene is for), `purposes` (what each setup is for), `hooks` (`by` an actor, `primary`,
`within_beats`, `delivered_when`), `thresholds` (`when`/`then`, optional `trigger` and attitude
`shift`), `endings`. Who wants what comes from `actors.<id>.motive`/`immediate_goal`/`traits`
and `agenda` wants; what each NPC is *for* is the hook it carries (`by`) and the purposes that
root on it. A room with no story block still gets a sparse brief from its actors.

Optional mechanic blocks, each off unless declared: `claims`, `procedures` (`kind: card_game`,
`game: twenty_one | three_dragon_ante`), `tolls`, `combat`, `attitudes`, `agenda`,
`texture_palette`, `leak_phrases`/`leak_keywords`, `public_performance`. Any other top-level
block is refused as unsupported (`KNOWN_BLOCKS`, kit_rooms.py:37), as is any other procedure
kind or card game (kit_rooms.py:232). Room files hold only data.

**Secrecy blocks** (checked at mount, `kit_rooms.secrecy_problems`; read by `kit_guards`):
- `leak_keywords.<set>`: `groups`, one or more lists of non-empty words; a set leaks when one
  public sentence has a word from every group. Optional `revealed_by`: a fact id or a list of
  fact ids, each in `facts`; once one is public the set is no longer a leak.
- `leak_phrases`: `phrases`, a list of non-empty strings the public text may not contain until
  they are public; optional `player_may_name`, a list drawn from `phrases`, allowed once the
  player says them.

**Claims** (`claims.<thing>`, checked by `kit_claims.compile_claims`; this is what a puzzle or
any check on a hidden truth needs):

| Field | Required | What it is |
|---|---|---|
| `about` | yes | `"<kind>:<thing>/<facet>"`, e.g. `"feature:notched_door/order"` |
| `truth` | yes | the hidden truth, DM-only |
| `source` | yes | `adventure`, `canon`, `procedure`, or `kit` |
| `exposure` | yes | `hidden`, `perceivable`, or `public` |
| `roots` | yes | fact ids or actor ids it is grounded in (non-empty) |
| `pc_check` | yes | the skill that finds it (`pc_sheet.SKILLS`, e.g. `investigation`) |
| `pc_access` | yes | `passive` (the PC's passive is a shield: Insight/Perception) or `roll` (only a player-initiated roll finds it) |
| `pc_checks` | no | every skill that finds it, `pc_check` among them |
| `fact` | no | the fact made known when it is learned |
| `dc` | no | the adventure's DC; else a concealer's 10 + skill, else 10 + floor(level / 3) |
| `concealer`, `conceal_skill` | no | the actor hiding it and their skill |
| `holders` | no | `{actor: knows | close | anchored | unaware}`; others are computed from stats |
| `perception_details` | no | `[{fact, min_margin}]`: what a Perception result shows, by margin |
| `numeric_fact` | no | a `numeric_facts` key it carries |
| `fingerprint`, `learned_text`, `subject_words` | no | the wink line, the line once learned, the words that name it |

A puzzle: a `hidden` claim rooted on the feature's fact, `pc_access: roll`, `pc_check:
investigation` (or `perception`), with `fact` naming what the PC learns. Every refusal names
the field (`Claim notch_order: unknown source`); 6c's `claims` block is the worked example.

## 3. Mount and fail-fast contract

`kit_rooms.load_room(path)` (kit_rooms.py:278):

1. **Up front, blocking (stages 1-2):** the file exists, parses, is an object; the required
   blocks; every block's JSON type and every area an object; referential integrity of areas,
   exits, facts, actors, `room_link`, feature `holds`; the secrecy blocks' shape and references;
   every approach's tease (`first_framing_problems`). Every problem is named, not just the first.
   Any shape no check names yet is still a `RoomMountError` (`load_room`), never a traceback;
   `MalformedRoomsFailFast` fuzzes every top-level field of three rooms missing, mistyped, and
   empty, and every area, exit, fact, and actor entry mistyped.
2. **At mount, validated but not built (stages 3-4):** unsupported blocks and kinds, then the
   existing compilers run as checks only: claims, attitudes, agenda, tolls, story, each card
   procedure's config (kit_rooms.py:244). No engine, brief, or fight is created.
3. **Lazily:** the texture palette, per area, the first time play draws on it
   (kit_texture.py:64). It was the largest mount cost (~7-19 ms for 6c) and is never needed for
   the first framing.

A room that fails raises `RoomMountError` (kit_rooms.py:55):
- **Host sees** (`start` exits 2, stderr JSON): `{"stage": "rejected", "error": "room_unmountable",
  "room": <path>, "problems": [...], "table_line": ..., "committed": false}`; nothing is created.
- **Kit says, at the table:** `TABLE_LINE` (kit_rooms.py:32): *"I can't run that room yet; it
  isn't set up for play. We can stop here or go another way."* Plain, brief, no improvised room.
  (GPT owns Kit's voice; this is the floor and GPT may reword it.)
- **Mid-chain:** the adjudicator checks a linked room before accepting the move
  (`_check_onward`, kit_agent.py:943). If it cannot mount, the move is refused as a pending
  ruling whose message is the table line, with `host_error` attached; nothing commits and the
  session plays on. `Runtime._commit` mounts again inside the transaction with the same
  function (`kit_rooms.arrive`), so the two cannot disagree; the prepare-time read exists only to
  turn a failure into Kit's line (a failure at commit is just a host rejection).
- **Room context over its caps** (below) is refused the same way: at `start`, before a move into
  the room, and at prepare.

## 4. Rooms in a row

Arriving in a `room_link` area mounts the linked room in the same commit, no host step
(state_context.py:487, `kit_rooms.mounted_state`, kit_rooms.py:432):
- the room left is archived in `state['rooms'][id]` with its resolution (`left`/`bypassed`) and
  all of its room-scoped state; coming back restores it as it was left;
- the character carries over (`SESSION_KEYS`, kit_rooms.py:51): sheet, `pc_state`, roll seed,
  time, the player notes; `fold_pc` (kit_rooms.py:389) writes current HP (after any fight) and gold
  (table net, tolls paid outside a stake) into the sheet, and what was taken into `carried`;
  each change is folded once, even across revisits;
- nothing room-scoped crosses: actors, facts, exits, procedures, tolls, combat, claims, canon,
  Kit's running plan (`kit_plan`);
- **Kit's private memory stays with its room** (`kit_rooms.room_private_kit`): her episodes
  (including the one for the turn that left, which was decided in the room), her current
  appraisal, and any player note that names one of the room's secrets (a leak phrase, a leak
  keyword set, or a hidden fact's text) are archived with the room and restored on return. A
  room's secrets are guarded only by its own leak blocks, so they must not reach the next room's
  decision input at all. A note counts as secret only while its secret is unrevealed: once the
  player has learned the fact (a known fact, or the fact behind a learned claim) or a leak set's
  `revealed_by` fact, the note is the player's knowledge and travels with them, in the notes
  and in the next prepare packet (`kit_rooms.known_fact_ids`; `LearnedThingsTravel`). A note
  that still names any unrevealed secret stays archived. What she said in public stays in the
  dialogue history: it was public;
- room ids key the archive, so a linked file whose id is already used by another room file is
  refused.

**Context headroom.** The room file's own share of Kit's private input is capped
(`kit_rooms.check_context`): `dm_only` without play-grown canon and procedure state at 9,700 B,
`claims_here` at 3,150 B. 6c, the richest room, peaks at 9,554 B and 3,057 B in the suite, so
it plays; a room materially richer than 6c is refused at `start`, before a move into it, or at
prepare, naming the block, its size, and the cap, instead of the budget quietly trimming Kit's
memory to make room for it. Memory trimming for a long session still happens, and is now loud:
`prepare` returns `context_warning`.

The caps bound the room's share; the budget gives them room. The suite's worst case (a long
card game, a full detail ledger, every memory trim taken) was 101,904 B, with 6c's room share
at 9,126 B and 2,153 B in that packet. A room at both caps in that same situation comes to
about 103,475 B. Brendon's call (2026-10-04): `CONTEXT_BUDGET_BYTES` is 105,000 (was 103,000),
so a room at both caps fits with about 1.5 KB to spare; the personality core is not trimmed.
Past 105,000 after every memory trim, `fit_to_budget` still fails loudly ("Context budget
exceeded"); a room over its caps still fails to mount. With the extra room the same suite game
now keeps more of Kit's memory before the trims stop: it lands at 103,806 B (one-pass packet
112,704 B against 132,000). Both are tested
(`RoomContextIsCapped`).

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

The router counts as leaving: leave/go/walk/move/step with a door, an exit's name, or "out";
head/charge/barge/burst/continue with an exit named; take/use/climb/duck/crawl/slip/descend/...
with an exit named within three words ("I take the stair down", "I slip out the back door",
not "I take the key from the door"); and retracing ("I head back the way I came", "I retrace
my steps"), which goes by the exit the PC came in by.

A `room_link` whose `area` is not in the linked room is refused before the move, with the
table line and `host_error` (`kit_rooms.load_link`).

## 4a. Threshold, check requests, open threads (watchroom stalls, 2026-10-04)

Nine stalls from the Nik watchroom session (`tests/playtests/2026-10-04-watchroom-nik.md`),
fixed in general code, tested on the watchroom and the 17a stub (`tests/test_kit_watchroom_stalls.py`):

- **The approach brief is tease-only but never empty.** At an approach area the brief adds
  `visible` (this area's visible facts), `ways_on` (the exit labels from here), a default
  purpose (frame the threshold, stop at the choice), and `hooks_waiting` (the hook inside by
  id and speaker only, never its text).
- **Inside actors are only heard at the approach.** The performer's `speakers` list has only
  the actors in the PC's area (both sides of a doorway on a move). Someone in the tease's
  `heard` is listed under `heard` with the sound; they may call through the door.
- **The first framing commits.** On room entry `reply_to` defaults to none. The scene's story
  bases include the room's own (`tease` at an approach, story area ids, hook ids), and a
  story anchor or basis the turn does not offer settles to an offered one (a memory tag, not
  a secret). `actor_ref` stays strict.
- **Perception at a threshold is not movement.** Peek, peer, look or watch through, listen at,
  an eye or ear to the gap, cracking the door: kind `threshold_look`, the PC stays put. Going
  through, in, or past still moves.
- **A check request is Kit's call.** "Can I make a check?", "Could I roll Perception?": kind
  `check_request`, nothing rolled, every other intent kept in the event. The packet's
  `check_request` says Kit calls one (roll_call) or declines; a skill the player names is a
  request. Brendon's rule: the player never picks the skill and never rolls first.
- **A peek gets the next area's approach view.** `threshold_view` (through, into, label,
  tease, heard), tease-only, on the look and on the roll for a check Kit called on it.
- **A question declares nothing.** Sentences that ask ("Could I grab the spear before he
  moves?", "Is there anywhere to hide?") are dropped before the physical reading.
- **The engine's move line never follows Kit's handoff.** Entering the room, it comes first;
  leaving, it goes before her closing remark.
- **Open threads.** A decision may carry `open_threads` {plant: [{id, hint}], pay: [ids],
  drop: [ids]}. They live in state (`open_threads`), every prepare packet lists them, and
  `due` is true once the scene is ending (stage resolution). Paying an unknown id is refused.
- **First-try lines.** Every packet opens with `first_try`: the constraints this turn checks
  (reply_to, the story bases, the actor ids, the appraisal labels, the speakers and the heard,
  terse speakers, a due hook, a check request, a threshold view, open threads).

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
(`RoomWords`, kit_agent.py:209; `room_words`, kit_agent.py:225): feature nouns and exit-name
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
   which is allowed once per area while no turn has been taken there). There is no automatic
   second packet.
4. **`first_look` is approximated** as "no turn taken in this area yet" (`room.turns_in`).
5. **Resolution only by leaving.** Story `endings`, a closed scene, or everyone gone while the
   PC stays do not set `resolution`. The close-scene CLI stays parked.
6. **A lazy palette that fails mid-play** surfaces as a host rejection (`InvalidChange`), not
   Kit's table line.
7. **Carry-over is thin:** the sheet's `hp` becomes current HP (no max, no rest); gold counts
   table net and tolls; taken things carry as text; room `resources` do not carry.
8. **Kit's private memory is per room** (see section 4). The cost: in room B she does not
   remember her private reads of room A, only what was said in public and the player notes.
   Room A's leak guards do not travel either: carried, 6c's `bandit` and `cards` would block
   those words in every later room. Player notes about secrets the player has already learned
   do travel (section 4).
9. **Room files live in two places:** 6c stays in `tests/fixtures/` (14 test modules and the
   scripts load it from there) and the stub is in `rooms/`.
10. **Budget:** 105,000 B (raised from 103,000 by Brendon, 2026-10-04, so a room at both caps,
    ~103,475 B with every trim taken, fits). The suite's worst case now trims less and lands at
    103,806 B.
11. **No agenda fixture.** No room file in the repo declares an `agenda` block; Claude's probe
    showed the path works, but no test room carries one.

Spike: branch `kit-room-loader-spike` (`c5713b2`, no PR) answered one question: is dropping
the `area_06c` gate enough to run a non-6c room? No. The tub and `south_door` rulings were
hardcoded and either narrated a tub that isn't there or crashed (`Unknown fact`,
`Exit not discovered`).

### 4b. Short beats (plan update #3)

A short beat is a complete, call-sized turn with no floor padding:

- **Narrowing question / "are you sure?"** `move: ask_clarification`, `scope: call`: one real reaction
  from Kit plus the question. The call cap (60 words) is the only size rule.
- **Stall check on a heavy turn** (`opening`, `exit`, `threshold_look`; `kit_agent.STALL_KINDS`):
  `scope: call` with a `roll_call` for a sheet skill. On room entry the move may be `ruling`. It is
  only for an earned check: would Kit call it if the answer were instant? The engine keeps the check
  as `pending_check.held = {kind, area}`, where `area` is the place being described.
- **The held description is an obligation.** It stays in state until it is delivered (a turn with no
  roll does not clear it), and only for its own area: leaving that area lapses it, so it is never
  delivered in the wrong room. The next turn in that area carries `held_description` {kind, roll,
  rule, cues}. With the roll in, the description is scaled to the result; with no roll, it is the
  plain view. That turn must use `scope: feature`, may not call a new check, and must actually
  describe the place: its narration names at least two `cues` (the area's own visible things,
  `kit_agent.check_held_delivered`). Delivery clears the pending check. A second stall, or a stall
  while a due hook must land, is refused.
- **Never canned.** On a call-scope turn, a Kit segment is rejected when its statements (questions
  aside) are only filler words ("Ooh, bold!", "Well, well, well.") (`kit_guards.check_not_canned`).
  A bare laugh or gasp before a real question is a whole beat ("Ha! Are you sure?", "Wow. How do you
  want to do that?"). A line Kit already used is caught by the recycled-line check.
- **What counts as a check request.** The PC asking for themselves ("Can I roll…?", "Do I need to
  make a check?", "Can I make a saving throw?"). It is never an NPC asked to do something ("Dealer,
  can you check my hand?") and never "save" as a verb ("Can I save him?").

Tests: `tests/test_kit_short_beats.py`.
