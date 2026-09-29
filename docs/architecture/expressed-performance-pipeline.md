# Kit's Expressed Performance Pipeline

**Status:** Design for the next implementation and playtest pass, 2026-09-28. The stages named below are a target contract. Only the current area 6c pieces identified as *existing* are implemented. **Player-facing quality is the release gate; latency is telemetry for now.**

## The problem this pipeline must solve

In the first room test, Nik greeted the card players and asked what was happening. After an 81-second wait, he got one small physical beat and a dealer who stated the price of passage. The saved trace said Kit cared about NPC embodiment, but her choice barely reached the player. The revised runtime now has a stronger scene read, actor card, saved opening, and one-pass option; none has yet passed a live test. See [the playtest record](../../tests/playtests/2026-09-26-area-06c-nik.md).

The target is a DM whose judgment is audible even when she keeps her direct voice quiet. A player should perceive an NPC trying something specific in a recognizable voice, an immediate response to the player's actual words or actions, a room with more than one possible future, and Kit's taste in the choice of what to foreground. A straightforward roll prompt may be one sentence. A charged exchange can take several sentences or a short monologue when it changes the player's next choice. We will not impose a universal word count, joke quota, accent, or number of speakers.

## Authority and information boundaries

| Responsibility | Authority | Output to next stage | Existing area 6c status |
| --- | --- | --- | --- |
| Player declaration | Exact message, prior accepted public conversation, and submitted roll if any | A typed bid with the original words intact | Recent public dialogue retained; the text router is limited and player-supplied rolls are not ingested |
| Rules and world | Source, map, current state, character mechanics, and allowed event vocabulary | Accepted or pending resolution; provisional world event; public projection | Bounded `Room6CAdjudicator` and `Runtime.preview`; many physical/social actions pause |
| Private Kit direction | Personality core, relevant memory, eligible story pressure, actor goal, accepted event | Appraisal, high-level DM move, and public-safe performance direction | `scene_discernment.py` and `PLAN_SCHEMA` exist; reference eligibility is checked, dramatic relevance is not |
| Expressed performance | Public projection, exact player words, public conversation, actor cards, accepted event, checked direction | Narrator, Kit, and NPC segments | Public performer exists; a single short NPC segment can pass |
| Validation and memory | Hard rules/knowledge/agency checks followed by accepted atomic commit; human review of quality | Saved spoken turn and state, then the next turn's public history | Atomic Kit/world commit and narrow literal leak checks exist; no player-facing quality gate |

The actor's motive and Kit's goal are separate. An NPC may want safety, money, status, or a relationship; Kit may want roleplay, a fair challenge, or an earned surprise. She selects which permitted pressure to present and whether to speak directly. An actor can resist Kit's preferred dramatic direction. A chosen story thread supplies context, never a license to invent a revelation or steer the player toward a mandatory outcome.

## Turn contract

### 1. Hear the player and resolve only what has happened

Preserve the full player utterance. Classify it enough to distinguish a rules question, an in-character social bid, observation, physical attempt, roll result, or a player handing control to Kit. This classification selects a procedure, not a scripted answer. If a check requires a roll, ask for it and keep that pending action; accept the player's result when supplied and save the ruling. Do not reinterpret `7+4=11` as a new in-world action. If an attempt is outside the current resolver, ask only for the missing information or make an explicit pending ruling; do not silently change the world. The present area 6c router and roll interface need this work before the Insight exchange can be replayed accurately.

Adjudication produces a bounded `AcceptedEvent` with its source or ruling basis and the public fact established. `Runtime.preview` applies the event provisionally. No dialogue, imagined motive, or private reaction can turn an unsupported bargain, discovery, combat result, or treasure transfer into canon. A spoken offer remains an offer until a corresponding validated event exists.

### 2. Read the live scene as Kit

Use the [existing scene discernment](scene-discernment.md) as the private first pass: the exact bid, recent speech, active and eligible story context, a present actor's goal, Kit's current appetite and relevant episodes. Choose `none` when no actor or larger thread belongs in the response. For NPC scenes, answer these questions briefly and in this order:

1. What did the player **actually** say or try? What changed after adjudication?
2. What does the actor think they can gain, avoid, or protect *now*, from established knowledge?
3. What allowed scene or level pressure makes that tactic matter? Which available fact must remain hidden?
4. Which of Kit's drives is engaged, if any, and what does she want the player to experience or decide next?
5. Which grounded move best serves the moment: rule, clarify, frame, let the actor act, or speak briefly as Kit?

The private answer is a **decision**, not dialogue and not a long introspective monologue. Store enough to later ask whether changing a relevant memory or appraisal changes the spoken turn. In staged evaluation, fix this decision before generation. The current one-pass chat path produces decision and speech together and cannot establish that causal order.

### 3. Give the performer a playable direction

The existing `public_brief` has `objective`, `tactic`, `visible_cue`, and `player_opening`. Extend or reinterpret it through an experiment before changing the live schema. A useful public-safe direction contains:

| Field | Practical job | Guardrail |
| --- | --- | --- |
| `reply_to` | Names the particular thing in the player's public utterance that deserves an answer | No guessed player emotion or intent |
| `objective` and `tactic` | Says what the actor visibly tries in this exchange and how that attempt could change after a refusal or surprise | No private identity, secret motive, or promise of a result |
| `scene_pressure` | Picks one active, perceivable tension worth foregrounding, or `none` | No dormant campaign thread inserted for drama |
| `visible_cue` | Grounds speech in an allowed action, prop, or relationship at this table | No invented geometry, discovery, or unseen reaction presented as fact |
| `scope` | Selects a quick ruling, ordinary exchange, or featured moment | A performance choice, never a word-count target |
| `kit_presence` | Chooses direct commentary, indirect direction through the scene, or quiet | Kit's jokes and beliefs do not become every NPC's voice |
| `player_opening` | Identifies a genuine possibility the reply leaves live | Do not write the player's next action or an options menu by default |

This is a proposed contract for testing, not a demand to add seven required JSON fields immediately. Existing actor cards carry a stable cadence, diction, and physical touchstone. A selected tactic changes with the current bid. The performer receives public facts and safe direction; private actor knowledge remains in Kit's stage. For Nik's greeting, an acceptable *direction* might say: answer his surprise about finding a game, let the dealer probe what he expected, show a change in how he handles a card, and leave several responses open. It must not prescribe a line or reveal the marked deck, the disguises, or the private leadership conflict.

### 4. Choose the amount of expression the moment earns

| Scope | Use when | What should reach the player |
| --- | --- | --- |
| **Call** | Roll prompt, clear ruling, narrow observation, or necessary clarification | A direct answer or request and the immediate perceivable consequence. Stop for the player's reply. |
| **Exchange** | Most social moves and contested exploration | A reaction to the specific bid, one embodied tactic or change in pressure, and a live opening. Kit may speak directly if her reaction earns it. |
| **Feature** | Scene entry, a newly important NPC, an earned threat or payoff, or a player move that turns the scene | A scene in motion with room for a brief speech, multiple reactions, silence, or a reversal if grounded. Stop when the player has a meaningful opening. |

Kit selects scope using stakes, novelty, the player's available decision, recent rhythm, and whether she has already offered enough. Do not use `Feature` merely because the room is authored or a model can write more. Do not suppress a compelling actor's invitation because a global brevity instruction says to be short. Changing scope should alter the *kind of playable material*, not just the number of words.

The performer enacts the actor card with language a reader can recognize on later turns: cadence, favored kinds of argument, humor tied to their own motive, and a consistent physical behavior that can change under pressure. Text can describe an audible quality once and enact rhythm; an actual accent or vocal identity needs a future audio layer and real listening tests. Narrator descriptions, Kit's table remarks, and each NPC's speech remain distinguishable. A second actor enters when their reaction changes what can happen next.

### 5. Validate, commit, and let the player answer

Run **hard gates** before publication: accepted event preserved; no player action or thought invented; no private fact leaked; actor present and permitted to know what they said; no unsupported geometry, rule result, commitment, or world change; speaker format valid; world revision current. The present `check_public_content` catches only literal phrases and cannot prove secrecy or semantic grounding. A groundedness review must examine paraphrases and implications in playtests. Rejected performance keeps the event uncommitted, retains the fixed staged decision, and gets at most a bounded retry with a specific reason. If the turn remains unsupported, give a candid pending ruling or clarification rather than a fabricated result.

After a valid performance, commit the world event, transcript, Kit episode, and applicable social state together. Show only the player-facing text. On the next turn, retrieve relevant accepted dialogue and consequences, including how the actor's tactic changed. A new durable NPC belief, promise, relationship, debt, or bargain needs a typed event and validated state transition; transcript memory alone is insufficient authority.

The runtime cannot automatically determine whether a joke landed, an NPC felt alive, or Kit made the scene worth continuing. That is the **soft quality gate** run on blind transcripts and live play, before a performance variant is promoted.

## Performance experiment before schema expansion

The first comparison uses the same room snapshot, model, source packet, accepted resolution, Kit personality core, actor card, recent dialogue, and private decision. Freeze the staged decision with `prepare → decide`; generate several candidate public performances from copies of that same safe input. Keep variants out of the live branch until the player-facing result wins. Candidate changes should be small enough to attribute: first try a prompt that explicitly rewards a response to the exact bid, actor tactic, recognizable cadence, and a live player opening; then test whether a scope choice improves the moments that need more space. Do not change the actor card, source facts, model, and prompt in the same comparison.

Score **spoken turns before traces**. Blind reviewers see the player's message, preceding public exchange, and the response with variant labels hidden. Ask which continuation they want to play, and what exact moment decided it. Then score response specificity, voice distinction, legible actor aim, Kit's identifiable taste, usable room invitations, player agency, and pacing of the scene. A beautiful paragraph that does not answer the player's move fails. A funny line followed by an impossible ruling fails. Review a complete opening plus at least two exchanges as one sample; one line cannot prove a persistent personality.

For a first pilot, use the runnable cases in [the comparison packet](../../tests/scenarios/expressed-performance-v1.md). The new `scripts/blind_performance_review.py` turns two genuine public continuations into a randomized reviewer packet and separate answer key; it does not generate or judge the dialogue. Generate more than one sample per case, randomize left/right assignment, and keep source/knowledge violations as automatic exclusions. This is a development comparison, not statistical proof. After an approach wins in area 6c, run the same contract in a **second playable room with different actors and pressure**. The current flooding archive is only a synthetic reference test; it cannot establish transfer. Compare against a baseline with the same source and rules but without Kit's event-linked appraisal or memory, then use experienced human DM sessions to test the longer-term ambition. A stronger private trace with an unchanged generic transcript is a failed result.

See the [area 6c personality protocol](../../tests/scenarios/level-01-area-06c-uktarl.md) for broader scene families and causal memory ablations. Preserve exact inputs, model/settings, fixture and source hashes, public history, accepted event, chosen direction, transcript, reviewer evidence, and hard violations. Store private traces separately from blind review packets. Never include a DM-only fact in a player-facing evaluation export.

## Implementation order and evidence to collect

| Step | Exact change | Evidence required before proceeding |
| --- | --- | --- |
| 0. Baseline | Preserve the Nik failure and current one-pass/staged outputs with model/settings and timing. Add a blind comparison packet; do not present a target script as the answer. | Reproducible room snapshots and separate public/private artifacts. |
| 1. Performer experiment | Test alternative public instructions on the **same** accepted event and fixed private plan. Put a variant identifier in trial metadata, not the player text. | Blind preference plus written reasons; no new source or agency violations. |
| 2. Direction selection | If the performer experiment helps, test `reply_to`, `scope`, and pressure selection as optional public-safe direction. Only then change `PLAN_SCHEMA`, validation, and `performance_input` in `runtime/kit_agent.py`. | A wider range of fitting responses across call, exchange, and feature turns, with no forced verbosity. |
| 3. Honest turn loop | Ingest player-supplied rolls; persist pending check and ruling. Introduce typed social events for meaningful offers/acceptance, actor tactic or belief changes, and any promise with world consequences. | Nik's Insight exchange survives restart; offers and refusals change later behavior without invented commitments. |
| 4. Transfer | Replace the area-specific speaker/actor enum and router with a general scene adapter; author and run a second source-grounded room. | Recognizable Kit plus distinct new NPCs; no dealer mannerisms bleed into another room. |
| 5. Optimize | Compare staged and one-pass generation on the same quality suite, then remove round trips or add streaming only when safe. | No quality regression; measured end-to-end timings on the actual player surface. |

Record received-to-first-playable and received-to-complete time, model calls, context size, retries, and user-visible process chatter in every trial. There is **no latency acceptance threshold during the performance pass**. The 81-second result remains a problem, but we will optimize a performance worth keeping. Avoid extra calls when a known rule needs only a direct roll prompt, and avoid exposing private process messages to the player. Publication of speculative streamed text before validation would violate the atomic turn contract, so streaming needs a separately designed buffer or rollback protocol.

## Research used as a constraint, not a substitute for evidence

- [FAtiMA Toolkit](https://arxiv.org/abs/2103.03020) informs the event → appraisal → high-level action separation; our model-generated trace does not implement its full appraisal system.
- [*Versu*](https://cs.uky.edu/~sgware/reading/papers/evans2014versu.pdf) informs independent actors and social practices; Kit currently has no autonomous NPC simulation.
- [*Façade*](https://ojs.aaai.org/index.php/AIIDE/article/view/18722) informs responsive, directed dramatic beats; this pipeline has no authored joint-behavior library or drama manager.
- [*Generative Agents*](https://arxiv.org/abs/2304.03442) informs memory, reflection, and ablation tests; Kit currently retains only limited episodes and recent dialogue.
- [*Symbolically Scaffolded Play*](https://arxiv.org/abs/2510.25820) reports a small, role-dependent result: in its synthetic evaluation, more structure helped a quest-giver's stability while weakening suspects' believability, and its ten-person usability study found no reliable general difference. This is a reason to compare our own performances, not a universal law about prompts.

This design is successful when a player-facing transcript is more specific, embodied, and playable **because Kit made a better decision**, and that advantage survives a different actor, room, and player move. We have not yet shown that result.
