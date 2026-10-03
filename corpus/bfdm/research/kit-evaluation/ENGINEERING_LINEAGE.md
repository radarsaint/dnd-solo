# Kit Evaluation — Engineering Lineage

This is a compact map of what the automated/runtime work proved around the Area 6c tests.

It exists to prevent test counts from being confused with DM-quality evidence.

## PR #13 — `kit-voice-spec`

Head: `642b553180ba02d6fbb0a446eb1b442874170b25`

Reported:
- 173 automated tests passing;
- voice/mood/showtime/NPC-noticing carriers and validators;
- explicitly **not proven in play**.

Human Area 6c playtest then failed despite those 173 tests.

See:
- [source-records/2026-09-29-area-06c-voice-spec-nik.md](source-records/2026-09-29-area-06c-voice-spec-nik.md)

## Human failure — Area 6c

The failed run demonstrated:
- Kit's aside contradicted the dealer's immediately preceding greeting;
- the host invented trivial high-card gambling;
- the marked deck did not become playable cheating;
- no meaningful detection/counter-cheating surface existed;
- natural dialogue input required a routing workaround;
- response latency was poor;
- dialogue had improved somewhat but still failed the entertainment/continuity bar.

This is a human-quality failure, not a unit-test failure.

## PR #15 — playtest 03 fixes

Title:
*Playtest 03 fixes: Kit reacts to reality, answer the invitation, playable 6c card game, addressed-reply router, prices*

Merged.

Head: `e77ea519ea57e3d28d40c31183f53b22556591a7`

It added, among other things:
- a contradiction guard for Kit's asides;
- general detail-generation machinery;
- a runtime Three-Dragon Ante procedure;
- marked-deck cheating via dealing seconds;
- Perception / Insight / Sleight of Hand / accusation paths;
- persistent wager/payout handling;
- price hierarchy and formula support.

The PR initially reported 232 tests after its main implementation; its later fix pass reported 281.

Automated review also caught important new implementation errors, including:
- DM-only marked-deck provenance leaking into public procedure state;
- incorrect bet settlement after a raise;
- overly broad card-game routing;
- unresolved active-hand state when leaving;
- source-price representation issues.

Lesson:
**a fix can create new correctness surfaces.**

## PR #16 — claims and knowers

Merged.

Head: `a81ec28a13339db35eec819ee21d3e8861af5697`

Reported:
- 316 automated tests passing;
- knowledge bands;
- claim/knower state;
- character-sheet-driven checks;
- marked-deck passive Perception handling;
- repair of claim/numeric-state bugs.

Exact repair QA is preserved at:
- [source-records/2026-09-29-claims-qa.md](source-records/2026-09-29-claims-qa.md)

That QA explicitly says its bridge walkthrough uses **host-authored dialogue** and is not evidence that Kit's entertainment quality passed.

## Later human finding

Subsequent live feedback still found:
- gambling dominated the room;
- the room's point was not evident;
- motives/stakes were unclear;
- NPC personality faded;
- description/check ordering was weak;
- an unsupported Sentinel Shield advantage appeared;
- long waits sometimes produced thin replies.

See:
- [playtest-02-followup-human-findings.md](playtest-02-followup-human-findings.md)

## Evaluation principle

Track at least two independent gates:

### Runtime correctness
Can the system:
- preserve state;
- apply rules/procedures;
- protect private information;
- route input;
- reject contradictions;
- survive persistence/retry?

### Dungeon Master quality
Does the player experience:
- a legible situation;
- embodied NPCs;
- meaningful stakes;
- useful description;
- proportionate mechanics;
- sustained personality;
- pacing worth the wait;
- interesting choices?

A build can pass one gate and fail the other.
