# Playtest postmortem: fresh ChatGPT, adventure attached, first turn (2026-10-25)

> No adventure text is quoted here. The adventure is named only. No character sheet details are recorded.
> Times in the postmortem are UTC as written by the host (Oct 26 06:04–06:45 UTC = Oct 25, 11:04–11:45 PM Pacific).

## 1. Summary

A plain, never-before-configured ChatGPT session was told to mount Kit from `github.com/radarsaint/dnd-solo`. It **got the full runtime** (310 files, integrity-verified) from a GitHub workflow artifact, read Kit's personality, took an attached published adventure (Lost Mine of Phandelver), made characters, and created a campaign save with an opening room.

It **never completed the first game turn**. A pending opening turn existed. When the player said "Yes" to begin, the host sent "Yes." as a new action instead of completing the pending turn, and Kit rejected it. The save shows one pending turn, zero committed turns, and one rejected input.

Verdict: Kit can be loaded into ChatGPT. There is not yet evidence that she can reliably host a complete game there.

## 2. The postmortem (as delivered by the host, lightly reformatted)

> **Preservation note:** The parts below are reproduced word for word. About 13,000 characters in the middle of the original (the rest of the section 2 timing table through the start of the section 8 correction list) were not available when this doc was written. They are marked **[GAP]** and should be pasted in from the original. Nothing in the gap has been paraphrased or reconstructed.

### Kit playtest postmortem — Mounting, onboarding, and first turn

Overall assessment: The mount worked. Character onboarding mostly worked. Starting the adventure did not.

This was a useful test because it demonstrated that an ordinary ChatGPT session can obtain and execute Kit's real runtime from GitHub, read her personality, and create a campaign save.

It also exposed the gap between having a functioning runtime and having a seamless Dungeon Master.

The most important finding is that we never completed the first actual game turn. When you said "Yes" to beginning the adventure, the session already had a pending opening turn. Instead of completing that turn and narrating the opening scene, I attempted to process your confirmation as another action. Kit rejected it.

I have checked the saved SQLite database directly. It contains:

- One pending Kit turn.
- Zero committed Kit performance turns.
- One rejected or held input: `"Yes."`
- A saved campaign, character, and opening room.

So although Kit was mounted and the scene was prepared, Upgraydd never actually entered the adventure from the player's perspective.

That distinction matters. It is the central defect of this playtest.

#### 1. What the timestamps prove

I recovered file creation and modification timestamps from the actual sandbox. These establish when particular artifacts existed, but they are not a complete timing trace of the conversation. They cannot distinguish every interval spent processing from time spent awaiting your next message.

All times below are October 26, 2026, in UTC.

| Time  | Verified activity |
| ----- | ----------------- |
| 06:04 | GitHub runtime ZIP downloaded |
| 06:05 | Kit source mounted and integrity-verified |
| 06:06 | Runtime ZIP and generated host context saved |
| 06:10 | Your Lost Mine of Phandelver PDF arrived |
| 06:14 | Adventure extraction, local index, and preparation script created |
| 06:39 | Four character sheets, party roster, and opening room created |
| 06:39 | Opening room start response saved |
| 06:42 | Save last modified after "Yes." was rejected |
| 06:45 | Postmortem inspection began |

These timestamps are filesystem and database evidence, not fabricated per-tool execution durations.

The striking result is that there were about 35 minutes between receiving the PDF and the failed start attempt. That total includes several separate user decisions, assistant responses, and idle intervals. It would be incorrect to attribute all 35 minutes to computation, but it is still far too much friction between supplying an adventure and entering play.

#### 2. Detailed timing breakdown

Measured = timestamped runtime evidence. Elapsed = wall-clock interval that may include user interaction or assistant reasoning. Not measured = insufficient timing data.

| Operation | Time or duration | What it tells us |
| --------- | ---------------- | ---------------- |
| GitHub lookup and artifact discovery | Not measured | Multiple connector requests before the download |
| ZIP received → verified mount report | 15.5 seconds elapsed | Real, successful mount |
| **[GAP]** | | |

**[GAP]** — remainder of section 2 through the start of section 8 (paste from the original).

#### 8. Corrections (as far as available)

| Priority | Correction | Detail |
| -------- | ---------- | ------ |
| P0 | **[GAP — title not available]** | "…ions must be interpreted against the existing lobby and pending-turn state. Once consent is given, finish the pending opening and deliver the committed spoken result. Never treat consent as an in-fiction physical action." |
| P0 | Support actual allied companion turns | A four-adventurer party must be mechanically real. Companion actions, initiative, targeting, spells, resources, and consequences need runtime ownership. Until then, offering full four-person combat is misleading. |
| P0 | Make source-backed adventures playable across locations | Accept an attached adventure, retain its source authority, and generate or retrieve valid runtime locations without forcing manual host engineering during play. A transition to the next location must work. |
| P1 | Create a strict host lifecycle | The host should know whether it is unmounted, mounted, in a lobby, holding a pending opening, actively playing, or awaiting a ruling. Each state should permit a small set of documented actions. Routine turns should not trigger source-code inspection. |
| P1 | Package verified premade characters | Store the official starter characters as reusable definitions, validate them against their source, and allow renaming without recreating statistics. Finish necessary choices while keeping onboarding short. |
| P1 | Measure end-to-end latency | Record timestamps for message received, routing decision, tool start and finish, packet delivery, model generation, validation, commit, and player-visible narration. Include failure reasons and retry counts. |
| P2 | Clean historical test assumptions from production sessions | A Phandelver manifest should contain Phandelver's rules, locations, and provenance. Historical Mad Mage regression language should never appear as operative campaign instructions. |

#### 9. What the next acceptance test should establish

I would use this exact sequence again because it is realistic: fresh ordinary GPT, mount Kit, attach an adventure, select an official premade wizard, add three companions, ask to begin, and play through a complete encounter.

The test should log the time spent at every phase, including the human decision gaps, so that we can distinguish actual software performance from conversational pacing.

My proposed performance goals—not measured achievements yet—would be a cold mount under 30 seconds, a warm ordinary turn with first narration in roughly 10 seconds, and no source-code inspection during normal play. We can refine those targets after collecting real host measurements.

The quality acceptance matters just as much as the timing: the first narration must be committed by Kit's bridge; all four characters must be mechanically valid participants; hidden information must remain hidden; and proceeding to the next location must not require an engineering session.

A separate recovery test should reset Python, restore the pinned build and save, and continue the same game without losing state.

#### Final assessment

This test was meaningful progress, despite the failed opening.

The binary-mounting solution worked. Kit's Python engine worked. The document could be processed. The character and campaign records could be created. The runtime was capable of preparing an opening turn in approximately 20 milliseconds.

The player-facing system surrounding those components was still too dependent on a GPT reasoning its way through setup and protocol details.

That's the central architectural lesson.

We have evidence that Kit can be loaded into ChatGPT. We do not yet have evidence that Kit can reliably host a complete game there.

The next engineering emphasis should be on making the path from player intent to committed narration deterministic, while completing the mechanics required by the chosen adventure and party. Further optimization of the core `prepare` command is not currently justified by these measurements.

And for the record, the saved game remains at its opening with one pending turn. I have not advanced or rewritten it during this review.

## 3. PM analysis

- **The workflow-artifact mount worked.** A plain GPT pulled the full runtime from a GitHub workflow artifact and verified all 310 files. This should become the **documented first mount step**, ahead of the portable (`KIT_PORTABLE.md`) load.
- **The pending-opening "Yes" bug is a doc gap left by #169.** #169 told the host how to finish a turn, but never said that a pending opening plus player consent means *complete it*. The fix belongs in the **runtime**, not in more instructions: a host lifecycle state machine (unmounted → mounted → lobby → pending opening → playing → awaiting ruling). While a turn is pending, `prepare` refuses new input and returns the exact `complete` command to run.
- **The ~65 KB packet and leftover test-slice text come first, before any speed work.** The engine itself is ~20 ms; the cost is the packet and the historical test-harness text still riding in manifests. Clean that out before optimizing anything else.
- **Companions and adventure ingestion are the P0 features.** Companions act only from their own sheets, Kit's DM knowledge stays out of their choices, and they never take the player's turn.
- **The premades were overclaimed.** Calling them "official" without checking them field by field violated the never-guess rule. Verified premades go in the plan.

## 4. Prioritized corrections

Order as the postmortem lists it (see the section 8 table above for detail):

**P0**
1. Treat consent against lobby / pending-turn state: finish the pending opening, never treat consent as an in-fiction action. *(Full title in the [GAP].)*
2. Support actual allied companion turns.
3. Make source-backed adventures playable across locations.

**P1**
4. Create a strict host lifecycle.
5. Package verified premade characters.
6. Measure end-to-end latency.

**P2**
7. Clean historical test assumptions from production sessions.

## 5. Acceptance test and targets

**Sequence:** fresh ordinary GPT → mount Kit → attach an adventure → pick a verified premade wizard → add three companions → ask to begin → play one complete encounter. Log every phase, including human decision gaps. Separately: reset Python, restore the pinned build and save, and continue without losing state.

**Quality bar:** first narration committed by Kit's bridge; all four characters mechanically valid; hidden information stays hidden; moving to the next location needs no engineering session.

**Targets — GOALS, NOT MEASUREMENTS:**

| Target | Goal |
| ------ | ---- |
| Cold mount | under 30 s |
| Warm ordinary turn, first narration | about 10 s |
| Source-code inspection during normal play | none |

**Measured in this playtest (for contrast):** ZIP received → verified mount 15.5 s elapsed; opening turn prepared in about 20 ms.

## 6. Process lesson

**Why it escaped:** the lifecycle rule ("finish a pending turn before taking new input") lived only in doc text. Nothing in the runtime enforced it, and no test exercised "pending opening + player consent". A host that misread or skipped the doc had no guard to stop it.

**From now on:** every lifecycle rule gets a **runtime check plus a test**, not just doc text. Doc text explains the rule; the runtime enforces it and returns the correct next command.

## 7. Synthesis with adventure-ingestion research

> **Preservation note:** This is Brendon's synthesis (after the research GPT read this postmortem), reproduced with light markdown cleanup only. About 2,200 characters in the middle (from the end of the "Adventure ingestion" subsection, starting at "There is one refinement fro…", through the start of the layered diagram in section 4) were not available when this doc was written. They are marked **[GAP]**. Nothing in a gap has been paraphrased or reconstructed.

### Research recommendation (before the synthesis)

> These are complementary techniques, not a proven end-to-end solution. My recommendation is to prototype architecture 1 using Kit's current JSON room contract and measure it against architecture 3 as a baseline. Full conversion is worth evaluating afterward if the lazy compiler's transition costs or global dependency failures prove unacceptable. That makes the next development decision evidence-driven, while keeping Kit's portability, source fidelity, and existing gameplay runtime intact. This is a research recommendation only. I have not implemented or tested a new ingestion pipeline in radarsaint/dnd-solo.

In short: **architecture 1** = a global index of the module plus source-backed, just-in-time scene compilation into Kit's existing room JSON. Measure it against **architecture 3** as the baseline. Evaluate **full upfront conversion** later, only if transition costs or global-dependency failures demand it.

### The synthesis

The research and this postmortem fit together very well. More importantly, the postmortem changes what I think we should prioritize.

My central conclusion: Kit's runtime is becoming capable, but the system responsible for turning that capability into an actual game is still incomplete.

This playtest gives us enough evidence to stop treating several different problems as one.

#### 1. What we now know

| Component | Evidence | Assessment |
| --------- | -------- | ---------- |
| Runtime distribution | 310 files verified; persona command executed | Working in this host |
| Core preparation | 20.36 ms | Fast |
| PDF text extraction | Index generated in 2.2 seconds | Working for this PDF |
| Adventure understanding | Only opening encounter compiled | Incomplete |
| Character onboarding | Four sheets and roster created | Partially functional |
| Companion simulation | Allied combat turns unsupported | Incomplete |
| Turn lifecycle | One pending turn, zero commits | Failed |
| Player experience | No opening narration | Failed |

The critical insight is that none of the successful components guaranteed that the player could actually play.

That changes how we should evaluate Kit.

A valid mount, a successful preparation call, a generated character sheet, and an indexed adventure are intermediate achievements. The product succeeds when the player can enter the world, act, receive consequences, and continue.

#### 2. I see three architectural problems

##### A. Host orchestration

This is the most immediate defect.

The GPT was effectively acting as an integration engineer while simultaneously trying to be Kit's host.

It had to interpret a large manifest, inspect the runtime, decide which commands to execute, and remember which stage of the transaction it was in.

When you said "Yes," the system had a perfectly valid pending opening. The host failed to finish it.

The solution I favor is an explicit host-facing lifecycle with a very small action vocabulary.

Proposed Kit host lifecycle:

- **Mount Kit** — verify runtime and establish session.
- **Load adventure** — register its private source.
- **Onboard player** — resolve character, companions, and choices.
- **Ready** — prepare the opening and ask whether to begin.
- **Begin** — complete the pending opening and deliver committed narration.
- **Play** — process turns, update state, and continue.

A host should not need to reason about which lifecycle operation to use whenever an obvious state transition occurs.

And importantly, pending operations must survive interruptions.

This is where I would spend the first engineering effort, because otherwise we cannot reliably test anything downstream.

##### B. Adventure ingestion

Our research identified a sensible solution: global indexing followed by source-backed, just-in-time scene compilation.

The playtest gives us direct evidence supporting that approach.

The original PDF was readable. Indexing was fast. The bottleneck was creating the executable material that Kit actually needs.

We should distinguish:

- **Source knowledge:** Kit can find information in the adventure.
- **Executable understanding:** Kit has converted that information into locations, entities, mechanics, secrets, and dependencies she can operate.
- **Campaign continuity:** Kit can move between locations while preserving source fidelity and changes produced by play.

The current importer reaches the first stage and can produce part of the second.

It does not yet provide the third.

I would retain Kit's current room representation and add a source-backed compilation layer around it, rather than replace the room engine.

There is one refinement fro **[GAP]** — remainder of this subsection, any further subsections of section 2, section 3, and the start of section 4 (paste from the original).

#### 4. Proposed layering *(heading not available; the text resumes mid-diagram)*

**[GAP]** — top of the layer diagram.

- Deterministic lifecycle and intent routing
- Private adventure layer — source, index, maps, dependencies, scene compilation
- Game state layer — characters, companions, discoveries, combat, continuity
- Kit's existing runtime and DM judgment — prepare → adjudicate → complete → commit
- Player-facing narration and interaction

This is a proposed synthesis, not a claim about Kit's currently implemented modules.

Notice what I am deliberately preserving: Kit remains the DM. Her personality, judgment, world state, and encounter execution don't need to be reinvented to solve this specific problem.

The adventure layer supplies authoritative material. The lifecycle layer ensures the work actually happens.

#### 5. What I'd prioritize now

I would organize the next development work around one end-to-end acceptance test, with three supporting improvements.

| Priority | Work | Acceptance |
| -------- | ---- | ---------- |
| 1 | Repair pending-turn lifecycle | "Yes" results in committed opening narration |
| 2 | Establish reusable adventure ingestion | Next location runs without manual host engineering |
| 3 | Complete companion mechanics | Four-person party can resolve an encounter correctly |
| 4 | Instrument the full experience | Latency and failures attributed to actual stages |

These can be developed independently where appropriate, but all three functional capabilities are required before declaring this particular player journey successful.

The acceptance test should be the same one that failed: mount Kit in an ordinary GPT session, supply a private published adventure, create the party, begin, play the encounter, and transition into the next location.

Then reset Python and resume from saved state.

That final recovery step matters because portability isn't just getting Kit into a host. It's being able to continue the campaign after the host session changes.

#### 6. The larger lesson

Something about this postmortem is particularly revealing.

We have spent substantial effort ensuring Kit can be mounted, has a personality, understands adventures, models the world, remembers events, and adjudicates D&D.

Those are necessary capabilities.

But the player experienced a failed session because the connections between those capabilities were unreliable.

That suggests a development principle I would adopt going forward:

> Evaluate Kit at the boundary where the player experiences her, and use the failures there to determine which internal component actually needs work.

This doesn't mean abandoning architectural research. The adventure-ingestion survey is still useful; in fact, this playtest supplies evidence about which architecture to pursue.

It means we should stop promoting component readiness into product readiness.

The first successful complete turn is therefore a more important immediate milestone than another sophisticated subsystem. The first successful room transition will be the next. A complete encounter with real companions, followed by successful session recovery, will establish substantially more.

And there is one uncertainty I want to preserve: we don't yet know whether Kit's existing room format is expressive enough to represent arbitrary published adventures. The research suggests a compiler can adapt source material to it, but the current test only reached a single opening encounter. That question deserves testing before we commit to a generalized schema.

My current synthesis is that we should keep the hybrid adventure architecture, repair the host lifecycle first, and test the entire experience without adding another layer of infrastructure until a demonstrated failure requires it.

That gives us a concrete path from a mounted engine to a Dungeon Master somebody can actually sit down and play with.

## 8. Agreed priority order and acceptance test

This order **supersedes** the P0/P1/P2 ordering in section 4 for planning purposes.

1. **Pending-turn lifecycle** — *landed in #171 (see section 10).* "Yes" to a pending opening yields committed opening narration.
2. **Adventure ingestion** — prototype architecture 1 against architecture 3; the next location runs without manual host engineering.
3. **Companion mechanics** — a four-person party resolves an encounter correctly.
4. **End-to-end instrumentation** — latency and failures attributed to actual stages.

**Acceptance test:** fresh ordinary GPT → mount Kit → supply a private published adventure → create the party → begin → play the encounter → transition to the next location → **reset Python and resume from saved state** with nothing lost.

## 9. Open items and notes

- **Redistribution rights:** check them before putting any official pregenerated characters in the repo.
- **Room-format expressiveness is still open:** we don't yet know whether Kit's room format can express any published adventure. Test it before committing to a generalized schema.
- Restore the **[GAP]** sections of the postmortem (section 2) and of the synthesis (section 7) from the original text.

## 10. Status on main 49d05ac (2026-10-26)

Sections 1–9 are the record as written on 2026-10-25. This table says what has landed since, so nobody reads "in progress" or a P0 item as still unbuilt. A correction is closed only by the merged PR named here and its tests.

| Correction (section 4 / 8) | Status on main | Where |
| --- | --- | --- |
| Consent to a pending opening finishes it (P0 1, priority 1) | Landed. `prepare` refuses new input while a turn is pending and returns the `complete` command; `status` reports the lifecycle state. | #171 (`turn_pending` guard), #185 (rehydrate returns the pending packet) |
| Strict host lifecycle (P1 4) | Partly landed: the pending-turn guard and `status`. The full unmounted → mounted → lobby → pending → playing → awaiting-ruling machine is not built. | #171 |
| Source-backed adventures across locations (P0 3, priority 2) | First slice landed: index once, compile each location just in time into room JSON; sourced creatures become engine combatants. Architecture 3 comparison not yet measured. | #172, #174 |
| Allied companion turns (P0 2, priority 3) | Landed: deterministic ordered tactics; capability, knowledge and turn isolation; the party survives room changes and saves. | #175 |
| Measure end-to-end latency (P1 6, priority 4) | Instrumentation landed (per-turn telemetry, opt-in compact packet, experiment protocol). No fresh-GPT end-to-end measurement recorded yet. | #177 |
| Reset Python and resume from saved state (acceptance test) | Landed: player-safe save ZIP, campaign.json/journal export, resume from the player's save, cross-room carry. | #179, #180, #186, #188, #189 |
| Clean historical test assumptions (P2 7) | Partly landed: Mad Mage framing no longer reaches other adventures' packets. A full manifest sweep for test-slice text is not done. | #178 |
| Verified premade characters (P1 5) | Not started. Blocked on the redistribution-rights check in section 9. | — |
| Full acceptance test (section 8) | Not yet run end to end on a fresh GPT. | — |

**The two [GAP] passages are still open.** The original host postmortem (about 13,000 characters of section 2) and Brendon's synthesis (about 2,200 characters of section 7) were never on the box or in the repo, so they are still marked rather than reconstructed. Paste the originals in to close them.
