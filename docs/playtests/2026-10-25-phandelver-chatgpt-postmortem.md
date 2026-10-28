# Playtest postmortem: fresh ChatGPT, adventure attached, first turn (2026-10-25)

> No adventure text is quoted here. The adventure is named only.
> Times in the postmortem are UTC as written by the host (Oct 26 06:04–06:45 UTC = Oct 25, 11:04–11:45 PM Pacific).

## 1. Summary

A plain, never-before-configured ChatGPT session was told to mount Kit from `github.com/radarsaint/dnd-solo`. It **got the full runtime** (310 files, integrity-verified) from a GitHub workflow artifact, read Kit's personality, took an attached published adventure (Lost Mine of Phandelver), made characters, and created a campaign save with an opening room.

It **never completed the first game turn**. A pending opening turn existed. When the player said "Yes" to begin, the host sent "Yes." as a new action instead of completing the pending turn, and Kit rejected it. The save shows one pending turn, zero committed turns, and one rejected input.

Verdict: Kit can be loaded into ChatGPT. There is not yet evidence that she can reliably host a complete game there.

## 2. The postmortem (as delivered by the host)

> **Preservation note:** Reproduced verbatim from the original Brendon pasted on 2026-10-26, sections 1–9 and the final assessment. Nothing is paraphrased. The adventure is named only; no adventure text is quoted.

Kit playtest postmortem — Mounting, onboarding, and first turn

Overall assessment: The mount worked. Character onboarding mostly worked. Starting the adventure did not.

This was a useful test because it demonstrated that an ordinary ChatGPT session can obtain and execute Kit's real runtime from GitHub, read her personality, and create a campaign save.

It also exposed the gap between having a functioning runtime and having a seamless Dungeon Master.

The most important finding is that we never completed the first actual game turn. When you said “Yes” to beginning the adventure, the session already had a pending opening turn. Instead of completing that turn and narrating the opening scene, I attempted to process your confirmation as another action. Kit rejected it.

I have checked the saved SQLite database directly. It contains:

- One pending Kit turn.

- Zero committed Kit performance turns.

- One rejected or held input: "Yes."

- A saved campaign, character, and opening room.

So although Kit was mounted and the scene was prepared, Upgraydd never actually entered the adventure from the player's perspective.

That distinction matters. It is the central defect of this playtest.

1. What the timestamps prove

I recovered file creation and modification timestamps from the actual sandbox. These establish when particular artifacts existed, but they are not a complete timing trace of the conversation. They cannot distinguish every interval spent processing from time spent awaiting your next message.

All times below are October 26, 2026, in UTC.

Time	Verified activity

06:04	GitHub runtime ZIP downloaded
06:05	Kit source mounted and integrity-verified
06:06	Runtime ZIP and generated host context saved
06:10	Your Lost Mine of Phandelver PDF arrived
06:14	Adventure extraction, local index, and preparation script created
06:39	Four character sheets, party roster, and opening room created
06:39	Opening room start response saved
06:42	Save last modified after "Yes." was rejected
06:45	Postmortem inspection began

These timestamps are filesystem and database evidence, not fabricated per-tool execution durations.

The striking result is that there were about 35 minutes between receiving the PDF and the failed start attempt. That total includes several separate user decisions, assistant responses, and idle intervals. It would be incorrect to attribute all 35 minutes to computation, but it is still far too much friction between supplying an adventure and entering play.

2. Detailed timing breakdown

Measured = timestamped runtime evidence. Elapsed = wall-clock interval that may include user interaction or assistant reasoning. Not measured = insufficient timing data.

Operation	Time or duration	What it tells us

GitHub lookup and artifact discovery	Not measured	Multiple connector requests before the download
ZIP received → verified mount report	15.5 seconds elapsed	Real, successful mount
Mount report → host context file's last write	64 seconds elapsed	Additional initialization/context work, not necessarily 64 seconds of engine execution
PDF received → preparation script saved	3 min 46 sec elapsed	Setup and analysis dominated this interval
Script saved → full PDF index saved	2.2 seconds	Actual text-index generation was fast
PDF index → initial play lobby	25.7 seconds elapsed	Further setup and host operations
Lobby → character and party files	24 min 18 sec elapsed	Includes our conversation and your choices; cannot be charged entirely to runtime work
Party files → prepared opening saved	9.5 seconds elapsed	Whole host process, including invocation and saving the result
Actual runtime prepare	20.36 milliseconds	Measured directly by Kit's telemetry
Prepared opening → rejected "Yes."	3 min 28 sec elapsed	Includes conversation and processing; not an individual command duration
Successful complete	Never occurred	No committed opening narration
First playable scene delivered	Never occurred	The user-facing objective remained incomplete

The biggest performance discovery

Measured runtime prepare

20 ms

Initial turn packet

65 KB

The engine's preparation operation was fast. The large model-facing packet and surrounding orchestration are much stronger candidates for the delay.

Kit's recorded first-turn telemetry reports runtime_prepare_ms: 20.36, with timestamps of 06:39:15.425 and 06:39:15.441.

That is extremely important. We should not optimize a 20-millisecond operation to fix a delay measured in minutes.

The actual work causing user-visible latency was around that operation: searching, inspecting, constructing files, interpreting the large response, examining its instructions, and trying to work out how to complete it.

There is also a measurement gap. We do not have reliable timestamps for model generation, first displayed word, tool-call scheduling, or complete execution. We need those before claiming that any single component is the primary latency bottleneck.

3. Mounting Kit: a genuine success

This was the strongest technical part of the test.

The initial response incorrectly treated mounting Kit as work that had to be handed to Grok Build. You corrected that. Once I followed the repository's actual LOAD_KIT.md, the process worked.

The evidence is concrete: the downloaded runtime ZIP, the Git tree verification, the mount report, and the generated host context.

Check	Result

Correct GitHub repository	Pass
Resolved real main commit	Pass
Retrieved complete workflow artifact	Pass
Extracted runtime ZIP	Pass
Verified source integrity	Pass — 310 files
Ran runtime persona command	Pass — exit code 0
Read host personality instructions	Supported
Started a real save later	Pass
Successfully completed a game turn	Fail
Tested recovery after Python reset	Not tested

The initial mount did not need a repository change, paid API access, or a separate worker.

That is a major architectural win: the binary distribution and mount procedure are functional in an ordinary GPT host.

The important improvement is to make mounting a standard host operation. A new GPT should follow the same established sequence without rediscovering the repository, evaluating alternative delivery strategies, or debating whether it has permission.

A cold mount can have unavoidable setup work. A warm session should never repeat it merely because the user asks to play a different adventure.

4. Adventure loading: source access succeeded, runtime readiness remained limited

You first supplied a URL for Lost Mine of Phandelver. I spent effort evaluating its download size, alternative online sources, and whether the web reader could handle it.

Once you uploaded the actual PDF, that research became irrelevant.

Your file was 55,961,050 bytes, containing 64 pages. It was processed into approximately 436 KB of searchable extracted text, with the PDF retained as the authority for maps and formatting.

The local extraction itself took only a few seconds.

The expensive part was deciding how to use it, writing the preparation script, establishing chapter indexing, and trying to fit an adventure PDF into Kit's runtime.

Finding: The time-consuming work was building a bridge between source material and Kit's executable room format.

That bridge should already exist as a product capability.

Kit needs to distinguish three levels of adventure readiness:

State	Meaning

Source available	Kit can consult the adventure
Executable location available	Kit can run a specific room through the engine
Campaign playable	Kit can progress through the adventure, including transitions, state, NPCs, and combat

We achieved the first two. We did not prove the third.

The generated module was explicitly scoped to the first roadside encounter. The next dungeon was not yet an executable room.

That means there was a foreseeable failure waiting after the initial encounter, even if the opening had succeeded.

Another finding: the PDF text extraction left map-heavy pages with little or no useful text. A robust adventure loader must retain access to the original page images and map geometry. A searchable text index alone cannot represent an adventure's spatial information.

The right long-term behavior is to ingest the source once, create whatever structure the runtime needs, and prepare additional locations before the player reaches them. This should not require the host GPT to become an adventure-conversion engineer in the middle of a session.

5. Character creation and companions

This part was conversationally successful.

You asked for official pregenerated characters. We identified the original Starter Set options, you chose the high elf wizard, named him Upgraydd, and selected the cleric, fighter, and rogue as companions.

That is an efficient decision path from the player's perspective.

The implementation was much less efficient.

At 06:39:05, a setup script produced the four JSON character sheets and party roster. Those writes occurred within approximately half a second.

The user-facing friction came from constructing those assets during the session instead of loading reusable Starter Set character definitions.

The sheets reference the official Wizards character PDF. However, I found no copy of that character PDF among the local source assets used for this session. The sheets were generated as structured JSON, and I did not establish a complete field-by-field comparison against the published originals.

Consequently, the claim that the sheets were exactly official was stronger than the verification performed.

There is one specific outstanding setup detail: Upgraydd's six first-level spellbook spells are recorded, but his four prepared-spell choices are empty. That needs resolution before prepared spellcasting is adjudicated. It does not need to prevent the initial scene.

The companion problem is more serious

The roster gave the companions identities: Borin the cleric, Caldor the fighter, and Nim the rogue.

Their sheets and narrative motivations were established, but the runtime's current combat support does not mechanically process their allied attacks.

I explicitly placed that limitation in the saved campaign.

That's responsible handling of the limitation, but it means I should not have implied the four-person party was ready for normal four-person combat.

The opening encounter assumes several adventurers. Having three characters who exist narratively but cannot participate mechanically does not meet that requirement.

For this campaign, allied characters must be able to act, take damage, cast spells, be targeted, spend resources, and influence combat outcomes.

Independent companion personalities are valuable. They cannot substitute for functional companion turns.

6. The first-turn failure

This is the clearest operational bug.

The engine had already created an opening turn with a specific turn ID. The prepared response contained instructions to produce a structured decision and performance, then submit them with complete.

The correct sequence after your “Yes” was to finish that pending opening.

Instead, I performed extra investigation and eventually sent "Yes." through the action-preparation path.

The engine returned a pending-ruling rejection. The save's handoff log records that input as held, and no turn was committed.

The failure is visible at three levels.

Host control flow: The GPT failed to recognize that affirmative out-of-character consent should complete an already prepared opening.

Runtime protocol: The system exposed a large, highly structured opening response, and I spent time inspecting it instead of completing the documented contract.

Player experience: After explicitly agreeing to start the game, you received no narration.

There is no evidence that the core adjudication engine is intrinsically slow here. There is strong evidence that the host's handling of its lifecycle was unreliable.

This is exactly why your instruction to stop inspecting runtime internals during play was correct.

The manifest overhead

The saved start response is 62,008 bytes. Kit's telemetry records approximately 65 KB for the full initial packet.

That packet contains extensive performance and decision instructions, a structured output schema, personality information, campaign material, and constraints.

The architecture has a caching mechanism so later turns need not receive the entire session manifest again. That is sensible, but this test never reached a successful second turn, so the benefit remains unmeasured.

The host must receive and obey the contract. It should not have to rediscover how to use it after every command.

There was also evidence of residual test scaffolding in the opening manifest, including references to a different campaign and limitations inherited from an older test slice. Those are indicators that the adventure loading path is not yet cleanly separated from historical regression assumptions.

One smaller content issue: the opening room's reveal structure held back some basic travel setup rather than placing all immediately perceptible details in the obvious opening layer. Even after a successful complete, that could have made the opening less coherent than it should be.

7. Player-facing UX: what worked and what did not

The interaction had several successes that are worth preserving.

Kit's voice was reasonably recognizable. The conversations about character selection were playful without requiring a complicated form. Your choice of Upgraydd was accepted immediately, and the character remained the focus.

The interaction also demonstrated that Kit can respond outside a game without launching a campaign prematurely.

The problems were mostly in how the assistant moved between product states.

I gave technical progress reports during what was supposed to become a recreational experience. You saw references to runtime inspection, schema investigation, room conversion, and companion mechanics.

Those details are relevant to this postmortem. They are intrusive during play.

I also treated the act of preparing an encounter as a reason to keep performing more setup. That prevented the most important player-facing result: the scene.

You then had to correct the workflow twice: first by telling me to stop investigating the runtime, then by reminding me to ask whether you wanted to begin.

The second correction was especially revealing. The readiness question belongs to the experience. You wanted the moment of choosing to start. After you gave that choice, the system should have moved directly into the fiction.

That transition should be reliable, not improvised.

8. Prioritized correction set

P0

Finish pending openings correctly

“Yes,” “begin,” and similar confirmations must be interpreted against the existing lobby and pending-turn state. Once consent is given, finish the pending opening and deliver the committed spoken result. Never treat consent as an in-fiction physical action.

P0

Support actual allied companion turns

A four-adventurer party must be mechanically real. Companion actions, initiative, targeting, spells, resources, and consequences need runtime ownership. Until then, offering full four-person combat is misleading.

P0

Make source-backed adventures playable across locations

Accept an attached adventure, retain its source authority, and generate or retrieve valid runtime locations without forcing manual host engineering during play. A transition to the next location must work.

P1

Create a strict host lifecycle

The host should know whether it is unmounted, mounted, in a lobby, holding a pending opening, actively playing, or awaiting a ruling. Each state should permit a small set of documented actions. Routine turns should not trigger source-code inspection.

P1

Package verified premade characters

Store the official starter characters as reusable definitions, validate them against their source, and allow renaming without recreating statistics. Finish necessary choices while keeping onboarding short.

P1

Measure end-to-end latency

Record timestamps for message received, routing decision, tool start and finish, packet delivery, model generation, validation, commit, and player-visible narration. Include failure reasons and retry counts.

P2

Clean historical test assumptions from production sessions

A Phandelver manifest should contain Phandelver's rules, locations, and provenance. Historical Mad Mage regression language should never appear as operative campaign instructions.

9. What the next acceptance test should establish

I would use this exact sequence again because it is realistic: fresh ordinary GPT, mount Kit, attach an adventure, select an official premade wizard, add three companions, ask to begin, and play through a complete encounter.

The test should log the time spent at every phase, including the human decision gaps, so that we can distinguish actual software performance from conversational pacing.

My proposed performance goals—not measured achievements yet—would be a cold mount under 30 seconds, a warm ordinary turn with first narration in roughly 10 seconds, and no source-code inspection during normal play. We can refine those targets after collecting real host measurements.

The quality acceptance matters just as much as the timing: the first narration must be committed by Kit's bridge; all four characters must be mechanically valid participants; hidden information must remain hidden; and proceeding to the next location must not require an engineering session.

A separate recovery test should reset Python, restore the pinned build and save, and continue the same game without losing state.

Final assessment

This test was meaningful progress, despite the failed opening.

The binary-mounting solution worked. Kit's Python engine worked. The document could be processed. The character and campaign records could be created. The runtime was capable of preparing an opening turn in approximately 20 milliseconds.

The player-facing system surrounding those components was still too dependent on a GPT reasoning its way through setup and protocol details.

That's the central architectural lesson.

We have evidence that Kit can be loaded into ChatGPT. We do not yet have evidence that Kit can reliably host a complete game there.

The next engineering emphasis should be on making the path from player intent to committed narration deterministic, while completing the mechanics required by the chosen adventure and party. Further optimization of the core prepare command is not currently justified by these measurements.

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
1. Treat consent against lobby / pending-turn state: finish the pending opening, never treat consent as an in-fiction action. *(Postmortem title: "Finish pending openings correctly.")*
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

> **Preservation note:** Brendon's synthesis (after the research GPT read this postmortem), reproduced verbatim from the original pasted on 2026-10-26, sections 1–6.

### Research recommendation (before the synthesis)

> These are complementary techniques, not a proven end-to-end solution. My recommendation is to prototype architecture 1 using Kit's current JSON room contract and measure it against architecture 3 as a baseline. Full conversion is worth evaluating afterward if the lazy compiler's transition costs or global dependency failures prove unacceptable. That makes the next development decision evidence-driven, while keeping Kit's portability, source fidelity, and existing gameplay runtime intact. This is a research recommendation only. I have not implemented or tested a new ingestion pipeline in radarsaint/dnd-solo.

In short: **architecture 1** = a global index of the module plus source-backed, just-in-time scene compilation into Kit's existing room JSON. Measure it against **architecture 3** as the baseline. Evaluate **full upfront conversion** later, only if transition costs or global-dependency failures demand it.

### The synthesis

The research and this postmortem fit together very well. More importantly, the postmortem changes what I think we should prioritize.

My central conclusion: Kit's runtime is becoming capable, but the system responsible for turning that capability into an actual game is still incomplete.

This playtest gives us enough evidence to stop treating several different problems as one.

### 1\. What we now know

| Component               | Evidence                                     | Assessment           |
| ----------------------- | -------------------------------------------- | -------------------- |
| Runtime distribution    | 310 files verified; persona command executed | Working in this host |
| Core preparation        | 20.36 ms                                     | Fast                 |
| PDF text extraction     | Index generated in 2.2 seconds               | Working for this PDF |
| Adventure understanding | Only opening encounter compiled              | Incomplete           |
| Character onboarding    | Four sheets and roster created               | Partially functional |
| Companion simulation    | Allied combat turns unsupported              | Incomplete           |
| Turn lifecycle          | One pending turn, zero commits               | Failed               |
| Player experience       | No opening narration                         | Failed               |

The critical insight is that none of the successful components guaranteed that the player could actually play.

That changes how we should evaluate Kit.

A valid mount, a successful preparation call, a generated character sheet, and an indexed adventure are intermediate achievements. The product succeeds when the player can enter the world, act, receive consequences, and continue.

### 2\. I see three architectural problems

### A. Host orchestration

This is the most immediate defect.

The GPT was effectively acting as an integration engineer while simultaneously trying to be Kit's host.

It had to interpret a large manifest, inspect the runtime, decide which commands to execute, and remember which stage of the transaction it was in.

When you said "Yes," the system had a perfectly valid pending opening. The host failed to finish it.

The solution I favor is an explicit host-facing lifecycle with a very small action vocabulary.

Proposed Kit host lifecycle

* Mount Kit — verify runtime and establish session.

* Load adventure — register its private source.

* Onboard player — resolve character, companions, and choices.

* Ready — prepare the opening and ask whether to begin.

* Begin — complete the pending opening and deliver committed narration.

* Play — process turns, update state, and continue.

A host should not need to reason about which lifecycle operation to use whenever an obvious state transition occurs.

And importantly, pending operations must survive interruptions.

This is where I would spend the first engineering effort, because otherwise we cannot reliably test anything downstream.

### B. Adventure ingestion

Our research identified a sensible solution: global indexing followed by source-backed, just-in-time scene compilation.

The playtest gives us direct evidence supporting that approach.

The original PDF was readable. Indexing was fast. The bottleneck was creating the executable material that Kit actually needs.

We should distinguish:

* Source knowledge: Kit can find information in the adventure.

* Executable understanding: Kit has converted that information into locations, entities, mechanics, secrets, and dependencies she can operate.

* Campaign continuity: Kit can move between locations while preserving source fidelity and changes produced by play.

The current importer reaches the first stage and can produce part of the second.

It does not yet provide the third.

I would retain Kit's current room representation and add a source-backed compilation layer around it, rather than replace the room engine.

There is one refinement from the postmortem: the importer needs both a text index and a representation of spatial evidence. A dungeon's connections cannot be trusted if those relationships appear only on map pages that were omitted from text extraction.

The game should be able to start once its opening is genuinely runnable, while upcoming rooms are prepared through the same standardized process.

### C. Party simulation

This is distinct from adventure ingestion, and I don't want it hidden inside that work.

Four characters were created, but only one was fully supported by combat execution.

That is a simulation capability gap. Improving PDF parsing will not fix it.

For Kit to run a conventional published adventure with a party, companions need legitimate participation in initiative, actions, reactions, damage, targeting, spellcasting, and resource consumption.

Their personalities and autonomy matter too, but those concerns sit above functional combat participation.

One constraint on the proposed reusable pregenerated characters: we should verify redistribution rights before placing official character content in Kit's public repository. User-supplied sheets and legitimately reusable rules data can take a different path.

### 3\. The performance evidence changes our priorities

Runtime prepare

### 20 ms

Measured engine work

Initial packet

### 65 KB

Model-facing context

The engine's preparation speed is encouraging. But the entire exchange stalled around host operations and interpretation.

I would separate future performance measurements into three categories:

Computational latency: actual execution time for mounting, extraction, compilation, preparation, and committing.

Orchestration latency: time spent assembling context, interpreting the protocol, generating responses, validating calls, and recovering errors.

Experience latency: elapsed time from the player's request to a meaningful, committed response.

That last measurement is what matters most to a player.

We still cannot attribute the minutes of elapsed time to a particular subsystem without better instrumentation. The 65 KB packet is a plausible contributor, not a proven bottleneck.

### 4\. The architecture emerging from both sources

Player and host session

Deterministic lifecycle and intent routing

Private adventure layer

Source, index, maps, dependencies, scene compilation

Game state layer

Characters, companions, discoveries, combat, continuity

Kit's existing runtime and DM judgment

Prepare → adjudicate → complete → commit

Player-facing narration and interaction

This is a proposed synthesis, not a claim about Kit's currently implemented modules.

Notice what I am deliberately preserving: Kit remains the DM. Her personality, judgment, world state, and encounter execution don't need to be reinvented to solve this specific problem.

The adventure layer supplies authoritative material. The lifecycle layer ensures the work actually happens.

### 5\. What I'd prioritize now

I would organize the next development work around one end-to-end acceptance test, with three supporting improvements.

| Priority | Work                                   | Acceptance                                           |
| -------- | -------------------------------------- | ---------------------------------------------------- |
| 1        | Repair pending-turn lifecycle          | "Yes" results in committed opening narration         |
| 2        | Establish reusable adventure ingestion | Next location runs without manual host engineering   |
| 3        | Complete companion mechanics           | Four-person party can resolve an encounter correctly |
| 4        | Instrument the full experience         | Latency and failures attributed to actual stages     |

These can be developed independently where appropriate, but all three functional capabilities are required before declaring this particular player journey successful.

The acceptance test should be the same one that failed: mount Kit in an ordinary GPT session, supply a private published adventure, create the party, begin, play the encounter, and transition into the next location.

Then reset Python and resume from saved state.

That final recovery step matters because portability isn't just getting Kit into a host. It's being able to continue the campaign after the host session changes.

### 6\. The larger lesson

Something about this postmortem is particularly revealing.

We have spent substantial effort ensuring Kit can be mounted, has a personality, understands adventures, models the world, remembers events, and adjudicates D&D.

Those are necessary capabilities.

But the player experienced a failed session because the connections between those capabilities were unreliable.

That suggests a development principle I would adopt going forward:

Evaluate Kit at the boundary where the player experiences her, and use the failures there to determine which internal component actually needs work.

This doesn't mean abandoning architectural research. The adventure-ingestion survey is still useful; in fact, this playtest supplies evidence about which architecture to pursue.

It means we should stop promoting component readiness into product readiness.

The first successful complete turn is therefore a more important immediate milestone than another sophisticated subsystem. The first successful room transition will be the next. A complete encounter with real companions, followed by successful session recovery, will establish substantially more.

And there is one uncertainty I want to preserve: we don't yet know whether Kit's existing room format is expressive enough to represent arbitrary published adventures. The research suggests a compiler can adapt source material to it, but the current test only reached a single opening encounter. That question deserves testing before we commit to a generalized schema.

My current synthesis is that we should keep the hybrid adventure architecture, repair the host lifecycle first, and test the entire experience without adding another layer of infrastructure until a demonstrated failure requires it.

That gives us a concrete path from a mounted engine to a Dungeon Master somebody can actually sit down and play with.

## 8. Agreed priority order and acceptance test

This order **supersedes** the P0/P1/P2 ordering in section 4 for planning purposes.

1. **Pending-turn lifecycle** — *done in #171 and #196 (see section 10).* "Yes" to a pending opening yields committed opening narration.
2. **Adventure ingestion** — prototype architecture 1 against architecture 3; the next location runs without manual host engineering.
3. **Companion mechanics** — a four-person party resolves an encounter correctly.
4. **End-to-end instrumentation** — latency and failures attributed to actual stages.

**Acceptance test:** fresh ordinary GPT → mount Kit → supply a private published adventure → create the party → begin → play the encounter → transition to the next location → **reset Python and resume from saved state** with nothing lost.

## 9. Open items and notes

- **Redistribution rights:** check them before putting any official pregenerated characters in the repo.
- **Room-format expressiveness is still open:** we don't yet know whether Kit's room format can express any published adventure. Test it before committing to a generalized schema.

## 10. Status on main d342e983 (2026-10-26)

Sections 1–9 are the record as written. Each row below was checked in the code and tests on main `d342e983`, not from PR titles. **Done** means a named test on main proves it. **Partial** means part of it is built and tested, and the rest is not. **Not started** means nothing on main does it.

### Postmortem §8 corrections

| Item | Status | Evidence on main |
| --- | --- | --- |
| P0 Finish pending openings correctly | **Done** | `runtime/kit_lifecycle.py` (`is_confirmation`, `turn_pending`, `status`). `tests/test_kit_lifecycle.py::test_yes_on_a_pending_opening_then_complete_commits_it`, `test_deeds_and_questions_do_not`, `test_a_confirmation_on_a_waiting_turn_points_at_complete` (#171). Retry/resend after a rejected opening: `tests/test_kit_opening_friction.py::test_a_corrected_decision_commits_after_a_rejected_performance`, `test_the_identical_resend_commits_the_new_performance` (#196). |
| P0 Allied companion turns | **Partial** | `runtime/kit_party.py`: initiative, sheet-only attacks, SRD spells, slots/features spent, targeting, death saves, conditions, hidden info kept from companion decisions. `tests/test_kit_party.py::test_pc_and_three_companions_fight_a_compiled_creature`, `test_engine_spends_slots_and_stops_when_empty`, `test_decision_cannot_see_hidden_creatures_or_secrets`, `test_save_resume_and_next_room_keep_the_party` (#175); declared combat acts in `tests/test_kit_combat_acts_acceptance.py` (#195). **Not built: companion reactions** (nothing in `kit_party.py` handles them). |
| P0 Source-backed adventures across locations | **Partial** | `runtime/kit_adventure.py`: index once, compile each location just in time, precompile neighbours, provenance on every field, book/SRD creatures become engine combatants. `tests/test_kit_adventure.py::test_a_to_b_and_on`, `test_compile_caches_and_precompiles_neighbours`, `test_a_fight_in_a_compiled_room_runs_on_the_engine` (#172, #174). Proven on test fixtures only, not on a real published book in a fresh host. The architecture 1 vs 3 comparison has not been measured. |
| P1 Strict host lifecycle | **Partial** | `kit_lifecycle.status` reports `unmounted` / `mounted` / `ready` / `awaiting_completion` / `playing` with the exact next command, read from the save (`tests/test_kit_lifecycle.py::test_cli_status_reads_the_save`, `test_unmounted`). No explicit `lobby` or `awaiting_ruling` state, and no rule that blocks source inspection during play. |
| P1 Verified premade characters | **Not started** | No premade definitions in `runtime/` or `tests/`. **Blocked on the redistribution-rights check** before any official character content enters this public repo. Related fix that did land: a caster with slots but no prepared spells is flagged to ask (`kit_party.py`; `tests/test_kit_party.py::test_incomplete_sheets_are_flagged_or_refused`), which covers the empty prepared-spells case from §5. |
| P1 Measure end-to-end latency | **Partial** | `runtime/kit_telemetry.py`: one record per call, tool-call counts, p95, failures recorded, opt-in compact packet. `tests/test_kit_latency_telemetry.py::test_one_record_per_call_with_null_host_fields`, `test_compact_is_smaller`, `test_unhandled_error_is_recorded_as_a_failure` (#177). Host-side stages (message received, model generation, first visible word) are null fields the host must fill. No fresh-GPT measurement exists. Full packet is still the default (`test_full_stays_the_default`), so the ~65 KB opening is not reduced unless compact is on. |
| P2 Clean historical test assumptions | **Partial** | Mad Mage persona lines load only for Mad Mage (#178; `tests/test_persona_docs.py`, `tests/test_kit_persona_command.py`). But `runtime/kit_agent.py` still sets `DEFAULT_ROOM` to the 6c regression fixture and carries 6c-baseline comments and patterns. No test asserts that an imported adventure's manifest has no test-slice text. |

### Postmortem §9 acceptance test

| Part | Status | Evidence |
| --- | --- | --- |
| Fresh GPT → mount → attach adventure → premade wizard + 3 companions → begin → complete encounter | **Not run** | Each piece has a unit or integration test on fixtures (above). The full sequence has not been rerun in a fresh GPT. The premade step can't pass as written until the rights question is settled; a player-supplied sheet is the stand-in. |
| First narration committed by Kit's bridge | **Done in tests** | `tests/test_kit_lifecycle.py::test_yes_on_a_pending_opening_then_complete_commits_it` |
| All four characters mechanically valid | **Partial** | `tests/test_kit_party.py::test_pc_and_three_companions_fight_a_compiled_creature`; no reactions. |
| Hidden information stays hidden | **Done in tests** | `tests/test_kit_player_save.py::test_nothing_hidden_in_any_exported_file_across_fixtures`, `tests/test_kit_adventure.py::test_secrets_stay_hidden`, `tests/test_kit_party.py::test_decision_cannot_see_hidden_creatures_or_secrets` |
| Next location without an engineering session | **Partial** | `tests/test_kit_adventure.py::test_a_to_b_and_on` on fixtures only. |
| Timing logged per phase incl. human gaps | **Partial** | Runtime side only (#177). Host fields stay empty unless the host fills them. |
| **Python reset → restore pinned build + save → continue** | **Done in tests, not yet run live** | `tests/test_kit_lifecycle.py::test_the_pending_opening_survives_a_python_reset`, `tests/test_kit_party.py::test_reset_and_resume`, `tests/test_kit_campaign_resume.py::test_save_then_resume_in_a_new_sandbox_from_the_bare_runtime` (#179, #180, #186, #188, #189). |
| Runtime parses on the host's Python | **Done** | `tests/test_runtime_py38_syntax.py::test_every_runtime_file_parses_as_3_8` (#197). |

### Synthesis priority table (§7)

| Priority | Acceptance | Status |
| --- | --- | --- |
| 1 Repair pending-turn lifecycle | "Yes" results in committed opening narration | **Done** (#171, #196; tests above) |
| 2 Reusable adventure ingestion | Next location runs without manual host engineering | **Partial**: works on fixtures (#172, #174), not proven on a real book in a fresh host |
| 3 Companion mechanics | Four-person party resolves an encounter correctly | **Partial**: works in tests (#175, #195), no reactions |
| 4 Instrument the full experience | Latency and failures attributed to actual stages | **Partial**: runtime stages only (#177) |

### Flags kept open

- **Premade-character redistribution rights.** Check before any official pregenerated character goes into this public repo. User-supplied sheets are the path until then.
- **Map/spatial evidence from map-heavy pages.** `kit_adventure.py` flags pages with little text as `needs_map_look` (`tests/test_kit_adventure.py::test_map_pages_are_flagged`). It does not read map geometry, so connections shown only on a map still need a look at the page.
- **Is the room format expressive enough?** Still untested beyond fixtures and one opening encounter. Test it on a real multi-location adventure before committing to a generalized schema.
- **Python-reset recovery.** Covered by tests (above) but never run live in a host.
