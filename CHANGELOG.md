# Changelog

Versioning rule:

- Each merged PR bumps the minor version (0.10.0 -> 0.11.0).
- A fix commit on its own bumps the patch version (0.10.0 -> 0.10.1).
- Tag `vX.Y.Z` on main when the merge lands.
- v1.0.0 means Kit reliably finishes a whole module without stopping.
- The version is for the project only. Kit never shows it to players.

The current version is in `VERSION`.

## v0.15.0

- Proven data over hand typing: Kit now ships the whole SRD 5.1 monster list (329 creatures with an attack) as `runtime/data/srd_5_1_monsters.json`, numbers only, converted by `tools/build_srd_monsters.py` from 5e-bits/5e-database (MIT; SRD 5.1 is CC-BY-4.0). Before this, Kit knew 11 hand-typed creatures, so a module creature with no stat block in the book itself (a wolf, a hobgoblin, a zombie, a dragon) was never cast as a combatant and its fight could not run. In the test book, 6 of 115 locations gain combatants they were missing; nothing already found changes.
- Each shipped line carries AC, hit points, initiative, grapple, all six saves, Stealth, Perception, ability scores, challenge rating, and one turn's swings (the best weapon attack, repeated for a Multiattack of N) with average damage from the dice. The 11 hand lines stay as overrides where they carry riders the engine runs (save riders, the one swing a turn).
- The prep cache key now includes the SRD table revision (`srd_creatures.SRD_REVISION`), so a book prepared before this release is indexed again once against the full list.
- The SRD's NPC templates (Druid, Mage, Noble, Priest, Spy and the rest of the "any race" humanoids not already hand-listed) resolve when a room cites them, but Kit does not look for them in book text: there they are role words for people the book names and stats itself ("a friend of a druid"), not creatures in the room (`srd_creatures.DETECT`).
- Creature mentions now match f/fe -> ves and consonant-y -> ies plurals ("two wolves", "three harpies"), which the plain -s rule missed.
- A room may cite any SRD 5.1 creature by name (`{"srd": "Wolf"}`); an unknown name is still refused at mount.
- The 8-line scripted host pass gives the same lines as v0.14.0.

## v0.14.0

- One play path. The area-6c card-table, toll and twenty-one games are gone (`runtime/kit_cards.py`, `kit_toll.py`, `kit_twenty_one.py`), along with every branch that existed only for them: the card and toll resolutions in the turn loop, the card and toll guards (clean deal, stake offers, toll exchange, table narration), Kit-declared table procedures, the card and toll story-hook conditions, procedure and toll state in the save, and the `procedures` and `tolls` room blocks. A room that declares either block is now refused as an unsupported block. No book read from a PDF ever reached any of this. The 8-line scripted host pass gives the same lines as v0.13.0.
- `kit_agent.DEFAULT_ROOM` (the 6c fixture as a default room) is removed. Tests that mount that fixture name its path themselves.
- Kept: the general systems both paths used (attitude, combat, the room loader, story hooks, claims), the stdlib reader fallback and `runtime/kit_readers.py`. Stated-roll parsing (`supplied_roll`), which the live check path uses, moved from `kit_cards` to `kit_rolls`. NPC speaker labels come only from each actor's own `speaker` or `name` now; the 6c fixture carries its seat labels on its actors.

## v0.13.0

- Legacy removal, so the live host path (adventure prepare, start, the prepare/complete turn loop, record) is the one spine later work builds on. No player-visible change: the 8-line scripted host pass gives the same lines as v0.12.0.
- Removed 34 runtime functions nothing calls (found by `vulture`, confirmed never executed by `coverage` over the full suite plus the scripted pass, and by a whole-repo name search), among them the old opening and span guessers in `kit_skim`, compatibility shims in `kit_labels` (`apply_labels`, `frozen_labels`, `_picker`), `recover_encounter_span`, and unhooked helpers in `kit_scenes`, `kit_triggers`, `kit_opening`, `kit_agent`, `kit_combat`, `kit_adventure`, `kit_prices`, `kit_skills`, `kit_reveal`, `kit_telemetry` and Goldscale. Unused imports removed with `ruff`.
- Removed the area-6c batch harness and probe (`scripts/kit_batch_runner.py`, `kit_batch_grade.py`, `kit_engine_probe.py`, their README, the `6c_variety` scenarios and the harness-only test). The scripted host-command pass replaces them.
- Kept: the stdlib reader fallback and `runtime/kit_readers.py`; the room-loader chain walkthrough and room stub (they back multi-room tests); the combat fallback golden and watchroom replay (they back live regression tests). The 6c card-table and toll procedures are the next removal: no ingested module reaches them, but they are wired through the room schema, brief checks and turn loop, so they get their own PR.

## v0.12.0

- Adventure PDFs are read by a proven library first: pdfplumber (MIT, on pdfminer.six) gives each word's position and font, and `runtime/kit_readers.py` puts a two-column page in reading order (a full-width line stays in place; between full-width lines the left column is read, then the right) and marks italic or boxed prose as read-aloud. The opening scene's hidden creatures and their goal now read as whole sentences instead of being spliced with the facing column. pdfplumber is optional (`requirements.txt`); when it is missing or fails on a file, the stdlib reader and host tools run as before. `--reader stdlib` still forces the stdlib reader.
- One reader interface for later layouts: subclass `kit_readers.PdfReader` and `kit_readers.register(reader, first=True)`; `--reader <name>` picks it. The prep cache is keyed by book and reader, so a prep made by another reader is not reused.
- A look or scan for someone hidden ("I scan the thickets for anyone watching") is a look that calls Perception, never talk, even though "watching" is also a social word.

## v0.11.7

- `start --sheet` takes a PDF sheet: it reads it with the same reader as `import-sheet`, so the player never needs to know which step reads it. The sheet is read before anything is written, so a failed start never half-mounts a game and the next start works. `start` without `--room` finds the opening room under the save's own `.adventure` folder, not the folder the command ran from. A question about what the character knows (lore, people, history, creatures) calls History, Nature, Religion or Arcana, whichever fits; Investigation stays the fallback.

## v0.11.6

- The ready step ("We're set. Say Yes...") starts on any clear affirmative, with extra words or a quote around it ("Yes, let's start", '"That's the shield." Yes, let's start.', "Ready when you are, let's go"); a clear no or a question keeps waiting (`kit_lifecycle.is_ready_yes`).

## v0.11.5

- While a recorded fight is on with initiative pending, a bare number or "Initiative 14" is the PC's initiative (`initiative_rolled`), never "What is the 14 for?". With combat off the reply is unchanged. Tested through the host CLI (record, then prepare).

## v0.11.4

- The initiative guard reads the one combat state, not the line: when a fight is on (an engine fight or a recorded encounter with no engine fight data) it says initiative is pending, never "Nobody here is fighting you"; when off, the reply is unchanged. The per-line fight parse it used is gone.

## v0.11.3

- A rolled knowledge check answers with the roll line itself as the turn's player input ("12"), the earlier question carried as what it answers; it was replaying the question as the input. A one-word line is quoted whole in `reacts_to`. Tested end to end through the host CLI (record, rules question, the History call, "12", complete).
- A missed scan is textured only from what the player has perceived (the read-aloud heard, facts the table recorded), never from DM-only or skimmed scene notes.
- A restored (cached) book starts like a cold one: prepare says the landing line, start says the ready line, Yes speaks the opening. One session's opening flags are no longer carried in the cache.
- In combat or not is one engine-owned state (`state_context.in_combat` / `combat_view`): ON when initiative is called or a record step starts an encounter, OFF when the fight ends or a record step ends it. Every turn carries it (`combat` in the turn packet, the router's reasons), with a pending initiative shown. Object interactions: out of combat they just happen; in combat one is free per turn and a second costs the action. The brief, reveal, trigger-surprise and scene-close checks read it instead of their own copies.

## v0.11.2

- Using an object at a place ("toss a stone into the thicket", "knock on the door", "poke the brush with my staff") is the use move and simply happens; an attack needs a target creature and intent to harm. "Ready to cast" is a stance, not a cast. A named object and place no longer get "How are you doing that?".
- No host-tool, file or field names reach the player: refusals are scrubbed (`kit_moves.player_safe`), and the speaking check (`internal_label`, `check_no_internal_labels`) rejects them.
- Every refusal names its exact field. Performance problems name `performance.segments[i].text`, quote the offending words and give a fix; a changed pending event names `player_input`, `public_event` or `events[i]`; the generic "change only the field named above" is gone.
- `kit_agent record --db <db> --input-file beat.json` records a hand-resolved beat (`happened`, `revealed`, `facts`, `encounter`): revealed names leave the spoiler fence, matching hidden actors come out, and an encounter flag reaches later rules answers. No combat is run (v0.13). Documented in AGENTS, LOAD_KIT, PLAY_CARD and KIT_PORTABLE.
- A pending roll survives table talk and rules questions; the next bare number or "I rolled N" answers it until it resolves or a new call replaces it.
- Rules questions ("Do I need to roll...", "Can I stay hidden if I use my bonus action...?") route to ask_dm (table talk) whatever the stance.
- A missed scan still shows the scene: one visible fact here instead of "You do not spot anyone."

## v0.11.1

- Faster first play: `adventure prepare <book.pdf> --db kit.sqlite` does the whole engine side of setup in one step, about a second. It times each part and keeps the result per book, so the same book never prepares twice. A fresh save for a book already prepared, with its opening accepted, is ready in under half a second.
- Kit says her landing line as soon as prepare returns and reads the opening while you answer. Hosts have hard time caps: 3 minutes for all of setup and 90 seconds a turn. Past a cap the host stops and tells you in one line what it was doing, and during setup you get a progress note at least every minute. No more silent setup.
- The opening scene's form lists every item shape, so a host never has to open the engine to learn one. An accepted opening now says `scene_verified`.
- Fix: an opening told before a part's first heading is named for that part, not for a later site whose heading sits beside it on the page. The creatures in it stay in the scene.

## v0.11.0

- The turn spine. Every message is read as one of eight moves (look, talk, recall, move, use, fight, rest, or a rules question), along with where you said your character stands. Kit's reply must fit that read.
- Looking or listening for anything hidden, like scanning the brush for movement, is now Perception, not Investigation. Your passive Perception counts first: if it is enough against a known Stealth, you spot them with no roll. A low active roll never notices less than your passive would.
- When Kit asks you for something, she remembers what she asked and why. A roll with a question attached ("Perception? I rolled a 15.") answers the ask she already made. If you argue the skill and it fits the act, Kit agrees and the roll counts. If it doesn't fit, she says why and keeps the roll open. She never answers with just "You go ahead."
- Kit's replies are checked before you see them. A bare number, an internal label, a question the same reply already answers, asking again for a roll or choice you already gave, or narration that moves your character when you said he holds back all get rewritten.
- A plain act Kit has nothing to add to now reads "You do that." "Roll History." is no longer flagged as an unknown name. The ready line reads cleanly: "We're set. Say Yes and we start at the beginning of the book."
- Host instructions (play card, play loop, portable Kit) explain moves, open asks and the speaking contract.

## v0.10.1

- Fix: when Kit asks you to roll to remember something (History, Arcana, Religion, Nature, or any "do I know..." question) and you give her the number, she now tells you what your character recalls, scaled to the roll, then hands the turn back. A low roll still gets a half-remembered rumor or tavern talk, never just "You roll History: 12."
- Questions like "do I know any old stories about...?" are now recognized as knowledge questions and get the right roll.

## v0.10.0

- Kit uses the adventure's own rulings when they actually decide something, and has the next likely move ready while you think.
- Look and NPC replies are written from what the scene actually shows, so people speak in their own voices.
- Asking what your character knows works like a DM: if your background covers it (a local knows their home), Kit just answers; if it goes further, Kit asks for the right skill roll and never shows the target number. Later surprises stay hidden.
- Fix: a "what do I know about...?" question, even inside a move, no longer comes back as your own words with an internal label. Kit answers it or hands the turn back.

## v0.9.0

- Main baseline at `9fd048f`, before #211.
