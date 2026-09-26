# State and Context Prototype

Status: executable feasibility prototype, version 0.1.0. This is an implementation experiment, not completion of the broader runtime 0.4.0 milestone.

## Feasibility assessment

A playable version of the intended DM is a reasonable engineering target. The project already defines her personality and the authority boundaries needed to ground her choices. The practical work is connecting those contracts to persistent state, source retrieval, adjudication, and repeated playtests.

The model integration can use tools to retrieve state and propose actions; OpenAI documents [function calling](https://developers.openai.com/api/docs/guides/function-calling) for this connection and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) for constrained response shapes. These capabilities support the architecture. They do not establish that her dialogue, tactical choices, secrecy, or pacing will be consistently good. Those require evaluation with actual play.

This prototype makes a small part of the proposed architecture executable without selecting a model, requiring API credentials, or changing the canonical personality.

## Implemented

| Component | Behavior |
| --- | --- |
| Source baseline | A synthetic fixture is stored separately from live state. No published adventure text is included. |
| Persistent state | SQLite snapshots retain location, elapsed time, actor status, discoveries, resources, and recent beat tags. |
| Event ledger | Each accepted event records its adjudication evidence. Normal SQL update/delete operations on the ledger are rejected. |
| Turn commit | Events and the new snapshot are committed together. Invalid batches roll back completely. |
| Concurrent turns | Expected revisions reject stale writers. Turn IDs make identical retries idempotent. |
| Knowledge projection | Player output omits actor secrets, hidden actors, unknown facts, undiscovered exits, and unvisited destination names. |
| Topology | Movement follows explicit fixture connections. A discovered exit does not expose the contents of the destination. |
| Personality dependency | Context assembly reads `docs/personality/dm-personality-core.md` directly. No second personality copy is maintained. |
| Context bound | Only current-area facts/actors/connections and the last 12 beat records are assembled. Oversized packets fail explicitly at a configurable byte cap. |

The packet is a partial implementation of the personality backend contract. It names missing production layers explicitly. Its byte cap is not a model token estimate.

## Run

Requires Python with its standard-library SQLite support. Run from the repository root:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
python -m runtime.state_context init --db session.sqlite
python -m runtime.state_context context --db session.sqlite
python -m runtime.state_context commit --db session.sqlite --turn-file tests/fixtures/feasibility_turn.json
python -m runtime.state_context view --db session.sqlite
```

Use a fresh database for `init`. It refuses to overwrite an existing session. Repeating the supplied commit is safe: the turn is not applied twice. Reopening `view` in a new process loads the accepted state.

`context` is a developer/DM operation and includes secrets. `view` is the player projection. Neither command advances the clock. Time changes require an accepted `advance_time` event.

The supplied turn spends one of four arrows, marks a synthetic sentry dead after a stipulated adjudication, advances six seconds, and records a combat beat. These are test inputs; no attack or damage roll is calculated by this implementation.

## Trust boundary and limits

Only a trusted adjudicating DM/server adapter may call `commit`. Player text or model-proposed events must not be wired directly to it. Event evidence is recorded for audit; the prototype does not independently verify that the evidence is true or that a D&D ruling is legal.

The fixture assumes explicitly marked visible facts and exits are perceivable on entering an area. Production perception must also resolve light, senses, concealment, barriers, and discovery conditions. Remote reveals, resurrection, altered map geometry, inventory transfers, and most rules operations are intentionally unsupported in this experiment.

The structured player projection is tested. Free-form model prose is not generated or leak-checked here, so this is not a claim that an eventual language model cannot reveal a secret. A rendering boundary and actual model tests are still required.

The source graph is authored test data. Map manifests and image references are not themselves verified machine-readable topology. Mad Mage integration needs a source adapter and a checked map graph derived from the canonical maps.

This implementation does not yet include:

- live model calls or a conversational play loop;
- D&D rules, dice, initiative, attacks, saves, or spell resolution;
- production campaign/source retrieval or map reveal rendering;
- level-story, Halaster, faction, or NPC background simulation;
- persistent relationships, player preferences, or character patterns;
- state-schema migration, named saves, or rewind;
- human evaluation of her humor, pacing, voice, or entertainment value;
- measured model cost or response latency.

## Verification

Eight automated tests passed on 2026-09-24:

1. Accepted changes survive reopening the database; source retrieval does not revive the defeated fixture actor.
2. Player projection excludes secret facts, hidden actors, motives, and unexplored destination names.
3. Discovery and movement preserve topology and separate discovery of an exit from exploration of its destination.
4. An invalid batch leaves state, ledger, and turn records unchanged.
5. Identical retries do not spend a resource twice; reused IDs with different events fail.
6. A second connection cannot overwrite a turn using a stale revision.
7. An oversized context packet fails explicitly.
8. Ledger entries reject in-place updates and deletion.

## Next playable milestone

Connect this storage/context boundary to a small, source-verified campaign area and a model adapter. Give the adapter explicit permitted operations and validate proposed outcomes before commitment. Present only the accepted result to the player. Record a reproducible transcript and state changes.

Playtest a conversation, a creative bypass, a consequential failure, tactical opposition, and a save/resume. Judge her performance against `docs/personality/dm-personality-development.md`. Keep personality revisions small and make them only after repeated behavioral failures are observed.
