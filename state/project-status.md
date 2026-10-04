# Project Status

Current state of `main`. Older snapshots in this folder and under `docs/architecture/runtime/` are marked HISTORICAL on their first line and are not a description of the runtime now.

## Active workstreams

### DM personality / behavior
Status: the canonical core is loaded every turn, with the voice files. Kit is the same person in ordinary conversation, creative work and debrief, and live play. The runtime supplies authority during a game turn. It does not create her.

Expressed personality is specified and partly wired: a private decision, scene discernment, a running plan, a public-safe `kit_focus`, and speech checks. A player who would rather sit with Kit than with an experienced human DM is still the standard to test. Early playtests, recorded under `tests/playtests/`, found generic voice, thin NPC performance, and at least one ruling that never reached the save. Those sessions are evidence about expression, from an earlier room model.

### Technical DM runtime
Status: a generalized room loader and a ChatGPT bridge, on SQLite.

`runtime/kit_rooms.py` mounts any room file in the repo's room format. A room has four stages — approach, first look, exploration, resolution — and each stage is prepared when play reaches it. The PC can start in a stage, barge in, or go past. Rooms chain in one session when an area carries a `room_link`: the room left is archived, the character carries over, and room-scoped facts stay behind. A room that cannot mount fails fast. Kit says a plain line, and the session does not invent a substitute room.

The bridge is `prepare` / `decide` / `finish`, or `prepare --one-pass` and `complete`. Packets are three layers (session manifest, room manifest, turn delta) with a hash echo and `rehydrate`. Table talk and feedback are separate from PC actions. What a room can do is data in its file: claims, agendas, attitudes, tolls, card procedures, combat, texture. Undeclared mechanics stay off.

Authoring a room from the book's keyed text, at runtime, as the PC approaches, is in progress off `main`. On `main`, play runs from room files that already exist. The loader prepares those files stage by stage.

Area 6c is one past regression room. The room format is the reference. `start` with no `--room` mounts that old fixture as a legacy fallback. Pass `--room` for the room you mean. See `docs/architecture/ROOM_LOADER.md`.

Full rules, general source retrieval, NPC belief over a long campaign, and a measured claim that Kit is the better DM remain open.

### Player-facing UX/UI
Status: the player meets Kit in chat through the bridge.

Action: define presentation contracts once the message and event shapes settle.

### Maps and visual assets
Status: map, art, and handout manifests are indexed. Licensed image bytes stay in a private asset pack. See `docs/decisions/0002-map-and-visual-authority.md` and `docs/decisions/0003-private-binary-assets.md`.

Action: the runtime requests assets by stable id and semantic role. Geometry stays with the canonical map. Artwork does not establish hidden canon.

### Campaign content
Status: campaign and level layers live in `docs/campaign/` as DM material. Retrieving an arbitrary keyed area from the book and turning it into a room file as the PC approaches is the authoring work above.

Action: prove play on varied, previously unplayed keyed areas once authoring is on `main`. No single room is the proof.

## Next integration milestone

A live playtest should be able to walk this path in whatever room the PC has reached:

source for that area -> current scene and state -> bounded adjudication -> Kit's appraisal and move -> player-facing performance -> validated state update

The milestone is KRABS stage 1: any keyed area of the book, built from the source text when play reaches it, produces responsive play across several exchanges. Tests use varied, unplayed rooms. Persona continuity across conversation, debrief, and play stays in force while that work lands. Latency is recorded. Quality of the spoken scene is the gate.
