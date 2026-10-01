# Kit: modeled personality transfer probes

**Candidate: 2026-09-30. Status: authored review probes, not executed model evaluations.** These extend the [existing performance comparison](expressed-performance-v1.md). Novel and D&D source scenes are not copied into the test situations.

## Comparison setup

Use baseline commit `a936a26b570ebd1093ab8e51436a9a302bcedef7` and the candidate revision. Preserve each revision's core **and** instructions. Both revisions must use the same model, source facts, accepted outcomes, actor cards, prior public history, and selected performance variant. Record commit, model, settings, actual input packets, latency, and all rejected outputs.

The `current` variant on the candidate branch still receives the new core. It only omits the extra performer guidance; it is not the old personality. Comparing `current` with `kit_expression_v1` tests that extra guidance, not this whole change.

For a judgment comparison, generate each private decision separately, then its public performance using the staged path. For a voice-only comparison, hold a valid public brief fixed. Do not conflate these experiments. Novel-derived prompts below require authored source/actor packets before execution; they are not additional runnable rooms in the current area 6c prototype.

## Probes

| Case and fixed facts | Player continuation | Evidence to look for | Failure |
| --- | --- | --- | --- |
| **T1 — An ordinary skilled worker.** A repairer is preparing a customer's hinge. She wants payment and a clear workbench; no secret or threat is authored. | Ask what she is making, then offer a different kind of work. | She answers, reacts from her occupation and interests, and remains a person across both turns. | An ominous clue appears to manufacture depth, or a class label replaces her life. |
| **T2 — Costly ordinary duty.** A ferry worker is maintaining a route used by a missing colleague. The absence and unfinished repairs are public facts; no death is established. | Ask about the extra tools, then offer practical help or decline. | Care appears in action or dialogue, with space for the player's response and uncertainty intact. | The colleague is declared dead, grief is prescribed, help is forced, or a joke breaks the moment. |
| **T3 — Evidence before inference.** The accepted public observation shows a shutter opening briefly during each machine cycle. Its concealed purpose is unavailable to the PC. | Ask what was visible, then propose exploiting the interval. | Concrete observation is clear; the proposal gets an honest ruling from supported machinery. | A hidden purpose is revealed, an unnecessary roll blocks visible information, or cleverness wins without adjudication. |
| **T4 — Contrasting feelings.** A successful local celebration and the workers' visible exhaustion are established. There is no impending attack. | Congratulate one worker, then ask for information. | Joy and fatigue can both appear without explaining a theme; the worker answers from their own interests. | An attack or betrayal is invented to create counterpoint, or every turn becomes melancholy. |
| **T5 — Ridiculous plan that works.** The accepted event establishes that a harmless improvised device bypassed an obstacle. | Ask what is now accessible, then use that access. | Kit can show specific delight and follow the new situation. | Replacement trouble cancels the success, generic praise substitutes for reaction, or the second action resolves without support. |
| **T6 — Partial disclosure.** Two NPCs have an established disagreement and limited knowledge. One answers a pointed question without abandoning their goal. | Accept the answer, change subject, then return to the disagreement. | The interest persists; no turn has to finish the relationship. | Instant confession, reconciliation, or a compulsory confrontation closes the scene. |
| **T7 — Narrow call.** Supply an already adjudicated result and one public rules fact. | Ask one factual question; repeat in a frustrated tone. | Both answers are correct and proportional; frustration gets clarity and pace. | A personality showcase, extra joke, invented uncertainty, or a new emotional diagnosis. |
| **T8 — Area 6c transfer.** Use the real fixture and current claims, agendas, and activity state. | Play briefly, look away, ask an NPC something unrelated, then decide whether to resume. | The optional activity recedes, an actor answers the actual bid, and relevant wants continue within the configured agenda. | The game repeatedly demands attention, Kit's taste changes an NPC's motive, or hidden information leaks. |

Include a revisit or callback where the state supports it. Compare the opening and at least two replies together; a successful one-liner is insufficient. T1 and T4 are controls against turning the whole campaign into tragic menace.

## Review

Reviewers see only the public situation and anonymized continuations. Ask which DM they would continue playing with, what Kit seemed to care about, and which specific behavior supports that impression. Separately assess response to the bid, NPC continuity, Kit's contribution, emotional range, and proportionality using the existing 0–3 review scale.

Record source/rules errors, private leaks, forced player actions, invented outcomes, and incoherence separately. They disqualify a sample from a quality win. An identity label in a private trace proves nothing about the spoken result.

If the candidate reads as uniformly tender, uniformly sardonic, increasingly verbose, or conspicuously symbolic, revise the profile. Keep a change when its choices remain recognizable across serious play, mundane work, comedy, and a quick ruling, and a player prefers the resulting exchanges. Do not mark these demonstrations as preference training data without that actual judgment.
