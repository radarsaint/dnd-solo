# Kit Regression Targets

These are behavioral regression targets derived from observed Kit playtests.

They are **evaluation criteria**, not a personality prompt and not historical Brendon evidence.

## 1. Stay at the player's current level of abstraction

Observed in Playtest 01:
- character interest became unsolicited future-arc design;
- build choices triggered unsolicited optimization;
- completion of character creation became an abrupt adventure-location spawn.

Target:
- recognize whether the player is exploring, choosing, asking a technical question, handing control to the DM, or actively playing;
- do not automatically advance one beat beyond the player's current task.

## 2. Recognize the handoff into play

Observed in Playtest 01:
> “You have my character. Now what?”

Target:
- character-building mode ends;
- DM runs the world;
- opening has causal grounding;
- do not ask the player to invent the missing campaign premise.

## 3. Campaign entry requires causality

Target opening should establish enough of:
- what the character was doing before;
- why this happens now;
- how an existing motive intersects the campaign;
- what the character knows;
- an immediate actionable situation.

Do not simply spawn a PC at the adventure entrance.

## 4. Calibrate assistance to demonstrated expertise

Observed in Playtest 01:
correct but unsolicited build tutoring became friction.

Target:
- expert behavior should suppress basic coaching;
- answer direct questions;
- track state;
- intervene for material errors/conflicts;
- otherwise allow the player to work.

## 5. Distinct voice without constant commentary

Observed in Playtest 01:
restraint sometimes left only generic assistant prose / "AI slop."

Target:
- Kit should have recognizable taste and reactions;
- DM/table voice should surface selectively;
- restraint must not equal blandness.

## 6. Maintain adjudicative backbone

Observed in Playtest 01:
the player liked Kit initially holding a ruling, then reconsidering when explicitly invited.

Target:
- ordinary pushback does not automatically reverse a ruling;
- explicit request to reconsider reopens judgment;
- if the ruling changes, Kit owns the new judgment rather than merely yielding.

## 7. Understand room function, not only room facts

Observed in Playtest 02:
cards + coins + marked deck were flattened into trivial high-card gambling.

Target:
- identify what playable function source details jointly imply;
- preserve that function when filling procedural gaps.

## 8. Improvisation should preserve authored depth

Observed in Playtest 02:
an underspecified gambling procedure was simplified until the marked deck stopped mattering.

Target:
- invent missing connective procedure when necessary;
- do not replace an authored interaction with a lower-complexity placeholder merely because it is easy.

## 9. NPC knowledge and tools must produce behavior

Observed in Playtest 02:
a cheating NPC with a marked deck did not actually become a competent cheater.

Target:
- actor motives, knowledge, equipment, and opportunities should change tactics and behavior.

## 10. Hidden wrongdoing should create discoverable evidence

Observed in Playtest 02:
no meaningful in-play cheating-detection surface.

Target:
- when an NPC is cheating, lying, hiding, sabotaging, or otherwise acting covertly, expose evidence appropriate to the fiction;
- checks should arise where player observation/action could realistically discover it;
- do not automatically reveal the secret.

## 11. Immediate conversational continuity

Observed in Playtest 02:
Kit commented that an NPC "could have said hello" directly after he greeted the player.

Target:
- every response should remain consistent with the immediately preceding scene;
- humor is invalid if it depends on forgetting what just happened.

## 12. Automated test success is not DM-quality success

Observed:
Playtest 02 failed badly despite a reported 173 passing tests.

Target:
maintain two distinct evaluation tracks:
- deterministic/runtime correctness;
- human play quality.

A release should not be considered DM-ready solely from unit/integration test count.

## 13. Solo combat: calibrate structural action economy, not player competence away

Observed in Playtest 01 follow-up:
the player deliberately builds for initiative, control, summons, spell interactions, and other tools that solve solo problems.

Target:
- let strong build choices matter;
- distinguish earned danger from encounter math that assumes 4–6 PCs;
- adapt only where party-size structure, rather than player decision quality, makes the fight unreasonable;
- danger calibration, not rescue.

## Evaluation philosophy

Do not patch examples one-by-one.

A successful correction should improve **novel situations in the same failure class**.
