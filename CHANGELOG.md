# Changelog

Versioning rule:

- Each merged PR bumps the minor version (0.10.0 -> 0.11.0).
- A fix commit on its own bumps the patch version (0.10.0 -> 0.10.1).
- Tag `vX.Y.Z` on main when the merge lands.
- v1.0.0 means Kit reliably finishes a whole module without stopping.
- The version is for the project only. Kit never shows it to players.

The current version is in `VERSION`.

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
