# Changelog

Versioning rule:

- Each merged PR bumps the minor version (0.10.0 -> 0.11.0).
- A fix commit on its own bumps the patch version (0.10.0 -> 0.10.1).
- Tag `vX.Y.Z` on main when the merge lands.
- v1.0.0 means Kit reliably finishes a whole module without stopping.
- The version is for the project only. Kit never shows it to players.

The current version is in `VERSION`.

## v0.10.0

- Kit uses the adventure's own rulings when they actually decide something, and has the next likely move ready while you think.
- Look and NPC replies are written from what the scene actually shows, so people speak in their own voices.
- Asking what your character knows works like a DM: if your background covers it (a local knows their home), Kit just answers; if it goes further, Kit asks for the right skill roll and never shows the target number. Later surprises stay hidden.
- Fix: a "what do I know about...?" question, even inside a move, no longer comes back as your own words with an internal label. Kit answers it or hands the turn back.

## v0.9.0

- Main baseline at `9fd048f`, before #211.
