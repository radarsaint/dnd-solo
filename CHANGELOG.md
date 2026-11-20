# Changelog

Versioning rule:

- Each merged PR bumps the minor version (0.10.0 -> 0.11.0).
- A fix commit on its own bumps the patch version (0.10.0 -> 0.10.1).
- Tag `vX.Y.Z` on main when the merge lands.
- v1.0.0 means Kit reliably finishes a whole module without stopping.
- The version is for the project only. Kit never shows it to players.

The current version is in `VERSION`.

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
