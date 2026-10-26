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

## 7. Open items

- Adventure-ingestion research (how other AI DM systems ingest a player-supplied module) is pending.
- When it returns, it and this postmortem will be synthesized into one ordered PR plan.
- Restore the **[GAP]** sections of the postmortem from the original text.
