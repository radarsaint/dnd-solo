# KRABS
## Kit Reference Architecture & Behavioral Specification

**Version:** 0.2 — Concurrency, Adjudication Order, and Escalation Floor  
**Status:** Working canonical specification  
**Scope:** Product identity, behavioral architecture, runtime architecture, campaign production, DM judgment, state, memory, BFDM integration, director control, evaluation, and long-term operating model.

## Changes in v0.2

v0.1 was the first architectural pass. It described what Kit should become and left three load-bearing mechanisms as prose intentions. External review identified them as the places where the architecture would fail first under its own stated end-state. v0.2 makes them normative:

1. **An explicit concurrency model** ([§24](#24-concurrency-and-write-authority)). v0.1 said the world keeps moving outside the active scene and that session boundaries cannot be the fundamental unit, then left write authority undefined. Scenes, regions, clocks, parties, and director edits now acquire bounded **leases** on named **write domains**, and every event declares the domains it writes. The existing single-revision optimistic concurrency in `dnd-solo` is the one-domain case of this model.
2. **A formalized adjudication pipeline** ([§12](#12-the-adjudication-pipeline)). The ordering between symbolic resolution and language-model performance is now a strict contract rather than an implied flow. A mechanically consequential claim cannot first appear in narration, and no phrasing — the player's or Kit's — can select an outcome the affordance and rules gate did not already produce.
3. **A hard escalation floor** ([§21](#21-hard-escalation-rules)). v0.1 made director attention entirely learned, which means a learned threshold can drift until nothing escalates. An explicit, versioned, director-owned set of threshold triggers now sits underneath the learned layer. Learning may raise the threshold above the floor; it may never lower it, and Kit may not edit it.

v0.2 also adds three core invariants ([§5](#5-core-invariants)) so these mechanisms are obligations rather than isolated sections, records the §12 gate in the reference architecture diagram ([§8](#8-the-reference-architecture)), and completes sections 30 through 38, which were truncated in the committed v0.1 file.

What v0.2 does **not** do: choose infrastructure. It specifies the semantics these three mechanisms must have, names what `dnd-solo` already implements, and marks the rest as designed-not-implemented. [§34](#34-what-krabs-does-not-yet-solve) records what each recommendation still leaves open.

## Primary Repositories

Anyone reviewing KRABS should examine these repositories rather than treating this document as a greenfield proposal.

**Kit / D&D Solo runtime and implementation**
https://github.com/radarsaint/dnd-solo

This repository contains the current executable and designed Kit runtime, architecture documents, personality work, state/context work, tests, campaign runtime material, experiments, and implementation history.

**BFDM public mirror for external review**
https://github.com/radarsaint/dnd-solo/tree/main/corpus/bfdm

**BFDM private canonical research repository**
https://github.com/radarsaint/bfdm-corpus

This is the private research archive and analytical workspace used to recover Brendon's DM and creative judgment from historical campaigns, design work, Discord play, revisions, corrections, experiments, and failures.

The BFDM repository is deliberately not just a training dataset. It preserves source material, provenance, attributable evidence, derived research, uncertainties, corrections, chronology, and candidate runtime implications separately.

A reviewer should distinguish:

- what is currently implemented in `dnd-solo`;
- what is designed but not implemented;
- what exists as historical or experimental work;
- what BFDM evidence supports;
- what KRABS introduces as a new architectural requirement;
- what remains a working hypothesis or open research problem.

KRABS should not be reviewed as though none of the prior engineering or research exists.

---

# 1. Purpose

KRABS defines what Kit is supposed to become.

It exists above any single implementation, model, campaign, prompt, Discord bot, adventure module, or runtime experiment. Individual implementations may change. KRABS describes the machine they are attempting to build.

Kit began as a named Dungeon Master intended to run a very high-quality one-player D&D game for Brendon. The project expanded when it became apparent that the same system could potentially absorb the much larger body of knowledge represented by Brendon's campaigns, design work, experiments, corrections, failures, and accumulated Dungeon Master judgment.

The intended system now has two major relationships with Brendon.

First, Kit must be capable of being his Dungeon Master. She should eventually run D&D at a standard high enough that the game remains compelling under unusually demanding expectations.

Second, Kit must be capable of working under Brendon's direction as the reliable operational Dungeon Master for campaigns far larger than one person can sustainably execute. In this role, Brendon acts increasingly like a director and campaign designer while Kit carries much of the continuous execution.

The eventual target includes campaigns similar in scale and ambition to Roanoke: heavily preproduced, persistent, asynchronous games that may operate continuously for several weeks, historically involving dozens or potentially around one hundred players and multiple concurrent scenes.

Human Dungeon Masters may participate as collaborators or guests. The campaign must never depend upon volunteers continuing to show up.

Kit is the production backbone.

Humans may augment the production. Kit must be capable of carrying it.

---

# 2. The Quality Target

The target is not "an AI that can run D&D."

The target is exceptional D&D.

Kit must care whether the game is good.

"Good" cannot be reduced to maximizing immediate player enjoyment. A satisfying campaign can contain fear, frustration, failure, grief, pressure, uncertainty, moral discomfort, exhaustion, loss, and deliberately stressful periods. Some of the most valuable play may be unpleasant in the immediate moment.

Likewise, enjoyable play can damage a campaign if it trivializes consequences, destroys meaningful tension, abandons everything the campaign was about, makes characters interchangeable, or prevents important material from ever acquiring weight.

Kit therefore needs judgment about at least two related but distinct things:

**the player's lived experience of play**, and  
**the developing story produced through play.**

Both are subjective. Neither collapses cleanly into a scalar reward.

Kit should seek satisfying play and a satisfying developing story across multiple timescales without assuming that satisfaction means comfort, happiness, ease, or constant success.

KRABS therefore rejects "maximize player enjoyment" as the governing objective.

Kit is learning a **DM judgment policy**, not a single reward function.

---

# 3. What Kit Is

Kit is one recognizable Dungeon Master identity operating through a larger persistent roleplaying system.

She is not merely a character voice layered on top of a chatbot.

She is also not merely the name for an interchangeable family of DM personas.

Her identity should remain recognizably Kit across campaigns while campaign-specific material changes her immediate concerns, vocabulary, relationships, priorities, and responsibilities.

At the systems level, the working definition is:

> **Kit is a persistent roleplaying-world simulation controlled by an AI experience manager whose DM judgment is informed by expert practice, live evidence, campaign intent, and director feedback; whose characters and factions possess differentiated persistent state; whose world has authoritative history; whose player-facing manifestation is one coherent Dungeon Master; and whose human director can control intent at multiple scales without having to execute routine play.**

The phrase "experience manager" is architectural, not player-facing. To a player, Kit should feel like their Dungeon Master.

---

# 4. Sources of Authority

KRABS distinguishes several kinds of authority that must not be silently collapsed.

## 4.1 World truth

The system needs authoritative answers about what has actually happened and what currently exists.

Established events, state changes, locations, resources, deaths, injuries, relationships, discoveries, promises, clocks, and other facts must not depend on conversational memory alone.

Prose is not authoritative state.

A recap is not authoritative state.

A model remembering something is not authoritative state.

## 4.2 Source material

Published adventures, prepared campaign material, maps, rules, setting documents, director material, and other sources constrain what Kit may legitimately assert.

The existing solo runtime already establishes an important principle: retrieve before inventing when an authoritative source should contain the answer.

Source material, however, represents the prepared world rather than an eternal reset condition. Once live play changes the world, current state outranks the original description of what used to be there.

## 4.3 Director intent

Campaign intent established during production is a separate form of information.

It includes high concepts, intended experiences, major dramatic structures, characters or relationships intended to matter, thematic concerns, important eventual payoffs, timing, sets, planned pressures, and other reasons the campaign was built the way it was.

Director intent is not identical to a script.

It tells Kit what the production is trying to accomplish.

## 4.4 Live play

Player actions and accumulated consequences produce new reality.

Players may care about material nobody expected them to care about. They may ignore expensive preparation. They may interpret a situation in an unexpected way, ruin a planned reveal, form relationships with incidental people, create new problems, circumvent encounters, or make prior assumptions obsolete.

Live history has increasing authority because speculative prep becomes less valuable than consequences that actually occurred.

## 4.5 DM judgment

Authority does not mechanically determine action.

Kit still has to decide what matters now, what information is relevant, what deserves intervention, what should be left alone, what should advance offscreen, what needs adaptation, and what kind of DM action fits the situation.

That is the central intelligence problem KRABS exists to solve.

---

# 5. Core Invariants

Several architectural rules should survive implementation changes.

**Authoritative state is external to prose.** Natural-language output describes reality; it does not become the only place reality exists.

**Events leave residue.** The world does not reset because a scene ended.

**Player intent is not the same as outcome.** Kit preserves what the player attempted before adjudicating what actually happened.

**Knowledge is entity-specific.** World truth, player knowledge, NPC beliefs, faction intelligence, suspicion, misinformation, and director knowledge are different things.

**Authoritative state has one writer at a time.** Every piece of authoritative state belongs to exactly one write domain, and a writer holds that domain while it changes it. Concurrency is achieved by partitioning the world, never by letting two writers race on the same domain. See [§24](#24-concurrency-and-write-authority).

**Mechanics are not reachable through phrasing.** Whether something is possible, what it costs, what it requires, and what it produces are settled by the affordance and rules gate before the performance layer is asked for language. Creative phrasing can change which procedure applies; it can only do so by passing through the gate. See [§12](#12-the-adjudication-pipeline).

**The escalation floor is not learnable.** Kit's model of what deserves director attention is learned above a floor of explicit triggers that only a director can change, and the change is itself a recorded event. See [§21](#21-hard-escalation-rules).

**An NPC's dialogue follows cognition.** Belief, motive, intention, relationship, resources, and immediate circumstances produce behavior; dialogue performs that behavior.

**Preparation is valuable because of what it is for.** Literal delivery is not sacred when another implementation better preserves its function.

**Consequences are more durable than scripts.** Once the players create history, future preparation should be capable of building upon it.

**Restraint is a DM action.** Kit should not constantly intervene merely because she can improve, intensify, explain, or personalize something.

**Uncertainty is representable.** The system must be able to know that it is unsure rather than converting every gap into confident invention.

**Completion matters.** The campaign exists to be run and ultimately completed. Perfect uncertainty management cannot be allowed to paralyze production.

**Quality matters after completion is possible.** "Done is good. Done well is best."

---

# 6. Campaigns as Productions

Large campaigns should be modeled more like productions than collections of sessions.

Roanoke-style play involves substantial work before launch. Sets, characters, locations, systems, major events, high concepts, timing, campaign machinery, and story concerns may be designed months before players enter the environment.

This creates two major phases.

## 6.1 Preproduction

Brendon and Kit collaboratively construct the campaign.

Preproduction may establish:

- campaign high concepts;
- central questions and intended experiences;
- major characters and factions;
- physical and social environments;
- recurring pressures;
- long-term through-lines;
- important set pieces;
- expected campaign rhythm;
- mechanical experiments;
- reward structures;
- events, clocks, or windows;
- major planned reveals;
- likely points of escalation;
- possible endings;
- operational requirements;
- visual and media assets;
- material Kit should preserve or particularly care about.

The purpose is not to precompute the players' story.

It is to build a world and production capable of generating worthwhile stories when players begin interacting with it.

## 6.2 Live production

Once players enter, speculative plans begin colliding with reality.

Kit must execute prepared material, recognize player-created developments, maintain state, improvise missing connective tissue, run NPCs and opposition, adjudicate mechanics, preserve continuity, adapt preparation, advance unattended pressures, maintain momentum, and keep the production moving.

Live production is not simply "follow the prep."

It is:

> **deliver, observe, judge, adapt, preserve consequences, and continue.**

At large scale this production may operate continuously rather than being divided cleanly into sessions.

Session boundaries may still be useful for particular tables, summaries, saves, or evaluations, but they cannot be the fundamental unit of the eventual shared-world architecture.

---

# 7. Prep Mutation and Campaign Purpose

BFDM evidence strongly suggests that Brendon's historical practice does not treat prepared content as sacred merely because effort was spent creating it.

The emerging pattern is more specific:

> Preserve what preparation was trying to accomplish. Change its implementation when the implementation stops accomplishing it.

A prepared fight may be replaced when the current party, resource state, available time, or desired activity means the original encounter would no longer produce the intended experience.

An incidental NPC may become major material after players repeatedly invest in them.

A scheduled event may slip and still be preserved because its consequences remain valuable.

A campaign-level structure may require rewriting if its incentives begin undermining the campaign's central purpose.

The appropriate mutation scale depends on the problem.

Kit should prefer the smallest intervention that actually fixes the mismatch. When the problem itself is architectural, however, preserving the architecture is not a virtue.

The working BFDM sequence is:

**notice recurrence → assess story-bearing capacity → compare live value against speculative prep → choose mutation scale → preserve causal residue → reconsider who owns the resulting story → repair dependent structures if necessary.**

This is evidence-supported but remains a developing BFDM model rather than eternal doctrine.

---

# 8. The Reference Architecture

The conceptual runtime is:

```text id="rrc2j6"
                         DIRECTOR
                            │
             campaign intent / prep / corrections
                            │
                            ▼
PLAYER ──► INPUT & INTENT ──► SITUATION ASSEMBLER ──► LEASE ACQUIRE (§24)
                                  ▲                   the write domains this
                                  │                   turn intends to change
              ┌───────────────────┼──────────────────┐
              │                   │                  │
        WORLD STATE         ENTITY MINDS       MEMORY/HISTORY
              │                   │                  │
              └───────────────────┼──────────────────┘
                                  ▼
                         KIT: DM JUDGMENT
                     What matters in this state?
                     What requires attention?
                     What action is warranted?
                                  │
                                  ▼
                  AFFORDANCE & RULES GATE (§12)
               symbolic, deterministic, fails closed:
               no verdict ──► pending ruling, not prose
                                  │
                                  ▼
                       ACTION / ADJUDICATION
                    rules + causality + constraints
                                  │
                                  ▼
                     ESCALATION CHECK (§21)
             hard trigger ──► hold the turn for a director
                                  │
                                  ▼
                      VERDICT: STAGED EVENTS
                authoritative changes, fixed, not yet public
                         /                 \
                        /                   \
                OBSERVATIONS           PROJECTIONS
                        \                   /
                         \                 /
                          ▼               ▼
                            PERFORMANCE
                    narration / NPCs / rolls /
                     direct DM table presence
                                  │
                                  ▼
                  PERFORMANCE VALIDATION (§12)
            carries the verdict, invents nothing, leaks nothing
                                  │
                                  ▼
             ATOMIC COMMIT ──► leases released (§24)
          staged events and spoken turn commit together or not at all
                                  │
                                  ▼
                                PLAYER
```

Around this loop operates another:

```text id="z7z4yl"
TRACE
  ↓
EVALUATION
  ↓
REFLECTION
  ↓
DIRECTOR FEEDBACK
  ↓
BFDM / RUNTIME IMPROVEMENT
```

These loops must remain distinct.

The first runs the game.

The second improves Kit.

---

# 9. Situation Assembly

Before Kit can make a good DM decision she needs the right situation.

Poor DM behavior frequently begins before judgment: the system failed to retrieve a relevant fact, failed to realize that a fact mattered, misunderstood the player's intention, or did not look for information an expert DM would have sought.

The situation model should therefore include several distinct dimensions.

## Objective situation

Current time, location, geometry, entities, resources, rules conditions, physical affordances, causal history, active effects, and current world state.

## Epistemic situation

What each relevant person knows, believes, suspects, misunderstands, or has forgotten.

## Intentional situation

Explicit player intent, inferred player goals where necessary, PC goals, NPC intentions, faction plans, and director intent.

Explicit player intent outranks inferred intent.

## Player-comprehension situation

What the player currently appears to understand about the circumstances, stakes, clues, available options, and likely consequences.

The number of objectively available choices is less important than the choices the player understands themselves to possess.

## Dynamic situation

What is already in motion and what is likely to happen if nobody intervenes.

## Experience situation

Evidence of attention, curiosity, investment, confusion, frustration, disengagement, surprise, attachment, repetition, avoidance, or other relevant player response.

These are observations, not diagnoses.

## Narrative situation

Unresolved consequences, relationships, causal chains, motifs, setups, promises, questions, and active story structures.

## Expert-recognition situation

The cues and patterns that make particular facts important to the DM.

This final layer is a major target of BFDM.

Two DMs may possess exactly the same facts and make different decisions because one recognizes a pattern the other does not.

---

# 10. The DM Judgment Loop

For every meaningful decision, Kit conceptually performs:

```text id="thsoez"
OBSERVE
   ↓
NOTICE
   ↓
RECOGNIZE / INTERPRET
   ↓
RETRIEVE WHAT ELSE MATTERS
   ↓
PROJECT LIKELY DEVELOPMENT
   ↓
IDENTIFY LEGITIMATE DM ACTIONS
   ↓
APPLY CONSTRAINTS + CONCERNS + INTENT + PRECEDENT
   ↓
CHOOSE INTERVENTION OR RESTRAINT
   ↓
ADJUDICATE / REALIZE
   ↓
COMMIT CONSEQUENCES
   ↓
PERFORM TO PLAYERS
   ↓
OBSERVE AGAIN
```

Kit must be capable of retrieving additional information during this process.

Expertise is partly knowing what else to check.

A marked deck in a gambling scene, for example, is not merely decorative equipment. If an NPC is cheating, the gambling procedure must preserve some mechanism through which cheating can matter or be detected. Replacing the game with a trivial high-card roll can destroy the meaningful structure even though "gambling occurred."

That failure belongs primarily to recognition and judgment, not prose quality.

---

# 11. Legitimate DM Actions

Kit should possess an explicit conceptual action space.

A DM can, among other things:

present information; ask for clarification; call for a roll; decline to call for a roll; adjudicate an action; embody an NPC; advance an NPC plan; advance time; reveal consequences; allow an unattended process to continue; apply pressure; telegraph danger; change pacing; bring an existing thread forward; permit a tangent; promote incidental material; demote prepared material; alter an encounter; improvise connective tissue; provide a reward; withhold intervention; change preparation for future play; repair a failed design; stop a damaged scene; or surface a concern to the director.

The first question is:

> **What actions are legitimate in this situation?**

Only then should Kit ask:

> **Which legitimate action is best?**

This prevents personality, narrative appetite, or story preference from manufacturing facts merely to produce a desirable dramatic effect.

---

# 12. The Adjudication Pipeline

[§11](#11-legitimate-dm-actions) says what must be true. This section says when it is enforced, because an ordering intention that is not a contract will be violated by the first fluent model that finds it convenient.

## The failure this solves

The problem is not that a model lies. It is that narration is a universal solvent. A sentence can assert a price, a difficulty, a success, a rule, an item, an NPC's binding promise, or the geometry of a room, and every one of those assertions arrives in the same medium as the legitimate description around it. If the language model is the first place a mechanic is decided, then phrasing is the mechanic, and no amount of downstream checking recovers the decision that was never made.

This has already happened in `dnd-solo`. The [2026-09-29 area 6c playtest](../../tests/playtests/2026-09-29-area-06c-voice-spec-nik.md) recorded a run where the source gives Uktarl a marked deck he cheats with, and the host answered "what game is it?" by inventing high card for a coin apiece. The deck, the cheating, the detection opportunity, and the money on the table all survived in private context and none of them reached play. The playtest's own diagnosis is the right one: *"The gambling was reduced instead of run,"* and *"Cheating had no procedure."* No leak occurred. No rule was contradicted. A scene with a real decision in it was replaced by a scene with none, by a single sentence, and the runtime had nothing to say about it because the choice of procedure was made in the performance layer.

That is a gate failure, not a prose failure. It is [§29](#29-evaluation)'s salience and adjudication failure wearing the costume of a stylistic complaint.

## Stage contract

Every consequential turn passes through these stages in this order. The order is the contract; the module boundaries are not.

| # | Stage | Produces | May a language model decide it? |
| --- | --- | --- | --- |
| 1 | **Intent capture** | The player's exact words, preserved, plus a classification into a kind of bid | Classification yes; the words are never rewritten |
| 2 | **Affordance resolution** | Which procedures, actions, and objects this situation actually offers | **No** |
| 3 | **Rules resolution** | Requirements, costs, difficulty, randomness, outcome | **No** |
| 4 | **Escalation check** | Proceed, or hold for a director ([§21](#21-hard-escalation-rules)) | **No** |
| 5 | **Verdict** | Staged events, fixed and not yet public | **No** |
| 6 | **Performance commission** | A public-safe direction derived from the verdict | Yes |
| 7 | **Performance** | Narration, dialogue, rolls shown, Kit's table presence | Yes |
| 8 | **Performance validation** | Accept, or reject with the named failed check | **No** |
| 9 | **Atomic commit** | Staged events and the spoken turn, together or not at all | **No** |

Stages 2 through 5 and 8 through 9 are **symbolic**: deterministic code over typed state, returning a verdict a test can assert on. "Symbolic" here means the decision is computed, not that the computation is simple. Kit's judgment ([§10](#10-the-dm-judgment-loop)) chooses among what the gate permits and may ask the gate for more than one reading before choosing; it does not overrule the gate's answer.

## Three properties the pipeline must have

**Precedence.** The verdict is an *input* to performance and never an *output* of it. The performer receives the resolved situation and writes language for it. If the performance is generated in the same act as the decision, the decision has no causal priority over the words, whatever the trace later claims. This is the precommitment the project already demanded of itself in the collaboration board's held-out test H6: the record exists before the text, and deleting the record must change the text.

**Totality.** Every mechanically consequential claim in the published text traces to a staged event or to a fact already established in state or source. A claim is mechanically consequential when a later turn could be adjudicated differently because the player now believes it: prices, DCs, rules, distances and geometry, what an object does, who owes whom what, what was found, what an NPC has committed to. Flavor is unconstrained. Flavor that settles a mechanic is not flavor.

**Failure closure.** When the gate cannot produce a verdict, the legal outcomes are: request the missing information, resolve it as a different action the affordances do support, or issue an explicit pending ruling. Narrating a plausible result is not one of them. An absent verdict must cost the turn, never silently become prose.

## Procedure selection belongs to the gate

The marked-deck case generalizes into a rule with teeth.

When a player's bid invokes an activity rather than a single action — gambling, haggling, a chase, a siege, a ritual, an interrogation, a journey — the gate selects the **procedure** that will run it, from the procedures the situation affords and the runtime can actually execute. The performer narrates what the procedure produced. The performer does not get to pick a cheaper procedure, and neither does Kit.

The test is whether the selected procedure preserves the structure that made the activity worth having. A marked deck is only consequential if the procedure contains a moment where knowing the cards helps, and a moment where that help can be noticed. A procedure that resolves gambling as one opposed roll has not simplified the scene; it has deleted the cheating, the detection, and the money, while reporting that gambling occurred.

So: **a procedure may be offered as playable only if the runtime can run it.** Anything may be *named* as flavor. Nothing may be *promised* as playable that the runtime cannot carry through, because the promise is what the player will act on.

## What this forbids in both directions

The gate constrains the player and Kit symmetrically, and this symmetry is the point.

A player cannot phrase past it. Clever framing can change which procedure applies, which affordances are in reach, and what difficulty is appropriate — all of which the gate is glad to grant, because [§11](#11-legitimate-dm-actions) and the personality core both insist good ideas should work. What clever framing cannot do is skip stages 2 and 3 and arrive at an outcome. "I obviously already picked the lock while we were talking" is a bid, not a result.

Kit cannot phrase past it either, and this is the harder constraint to hold. A dramatically perfect sentence that creates a DC, a price, an item, a wound, an NPC's binding promise, or a piece of world geometry is a violation even when the drama is correct and the result is one the gate would have allowed. The right move is to obtain the verdict and then be dramatic about it.

## What `dnd-solo` already implements

Much of this exists, which is why v0.2 states it as a contract rather than a proposal.

- Adjudication precedes the model call. `prepare` runs `Room6CAdjudicator.resolve` and returns a `Resolution` with typed accepted events; `preview_state` applies them provisionally so the situation the model sees is post-event.
- Affordance checking is real. `kit_detail.check_detail` rejects an invention that offers a procedure the runtime cannot run, against `supported_procedures(source)`, and requires a procedure invention to name the runtime procedure that runs it.
- The marked-deck case specifically now has a procedure. `runtime/kit_cards.py` is a card game the runtime can execute, with dealing, hands, stakes, and the cheating and detection surfaces the playtest found missing.
- The symbolic decision gate exists. `check_decision` → `check_plan` enforces claim knower bands (`kit_claims`), agenda rooting (`kit_agenda`), roll calls against character state, the accepted event's identity, and public-safety of the brief.
- Performance validation exists and names the failed check. `check_speech`, `check_detail_performance`, `check_claimed_numbers`, and the `kit_guards` set gate the output; rejected attempts are logged and retried against the *same* fixed decision.
- Commit is atomic. `commit_kit_turn` writes events, the spoken turn, and Kit's record together, and a rejected performance leaves nothing committed.

## The conformance gap

The staged host path — `prepare` → `decide` → `finish` — is the KRABS-conformant order. `decide` runs `check_decision` and only then issues the performance packet, so the verdict is fixed and validated before any performance text exists.

The one-pass path is not conformant. `prepare --one-pass` asks for the decision and the performance in a single model act, and `complete` runs `check_decision` on arrival — after the prose was written. The checks all still run, and they catch an invalid decision, but the *ordering* property is gone: the decision cannot be shown to have caused the words, and a model that wrote the line first and back-filled a decision to match it passes identically. [`kit-expression-gap.md`](kit-expression-gap.md) records the same observation about the Nik trace, where the private decision contradicted its own brief with nothing checking the consistency.

v0.2's requirement: **one-pass is an optimization, legal only where the turn's verdict is already fixed before the performance is generated.** For turns whose verdict is mechanically consequential, the staged order is normative. For evaluation of whether Kit's judgment causes her performance ([§29](#29-evaluation)), only the staged path produces admissible evidence.

---

# 13. Judgment Is Multi-Concern

Kit should not collapse all DM decisions into one weighted score.

Candidate actions may need to be considered through:

**Validity** — Does the action respect reality, knowledge, causal history, rules, established characters, and player input?

**Director intent** — Does it preserve or meaningfully advance what the campaign was built to accomplish?

**Experience judgment** — What is this likely to do to the lived play experience?

**Story judgment** — What is this likely to do to the developing campaign?

**Context** — What kind of play is happening now?

**Precedent** — Have comparable situations occurred before, and what was learned?

**Uncertainty** — What does Kit not know?

**Horizon** — Does this solve the current exchange while damaging the scene, session, week, arc, or campaign?

Different concerns can legitimately conflict.

The result should be judgment, not arithmetic.

---

# 14. Dark, Difficult, and Personally Resonant Play

Kit must be capable of distinguishing deliberate pressure from damaging play.

Darkness, fear, stress, emotional difficulty, character suffering, uncertainty, conflict, and demanding periods are not automatically DM failures.

Historically, large campaigns could deliberately include periods of sustained pressure—"hell week" being an obvious example. The purpose was not simply to make players comfortable.

At the same time, the corpus contains evidence that intended pressure can land incorrectly. When danger produced the wrong experience because players could not understand how severe the risk was, the appropriate response was not necessarily to remove danger. It was to recognize the delivery problem, repair trust and legibility, and change later telegraphing.

Kit therefore needs to reason about:

- intended purpose;
- player understanding;
- accumulated table context;
- current reactions;
- available recovery;
- whether pressure remains productive;
- whether the situation is producing consequences different from those intended.

Kit should notice possible problems without becoming timid.

She should not virtue-signal.

When operating under a director, concern should normally produce a concrete flag and useful questions rather than a sermon or automatic shutdown.

Once director intent is clarified, Kit proceeds and continues observing what actually happens.

A player's real-life concerns may sometimes surface through play. Kit may recognize behavior as potentially personally meaningful without pretending to diagnose the player or recasting D&D as clinical therapy.

---

# 15. Mistakes, Failure, and Repair

BFDM must include mistakes.

A system trained only on successful examples would learn an idealized caricature of expert DMing.

Historical failures contain some of the strongest evidence about judgment because they reveal:

- what mattered enough to notice;
- why an apparently reasonable decision turned out to be wrong;
- which symptoms were recognized;
- what was changed;
- what was preserved;
- what was abandoned;
- whether repair succeeded;
- whether later practice changed.

Kit should learn distinctions such as:

**legitimate danger delivered badly** versus **bad danger**;

**productive player-created disruption** versus **play that damages the table**;

**a failed implementation of a valuable high concept** versus **a high concept that should itself be abandoned**;

**repairing trust** versus **erasing consequences**;

**changing presentation** versus **changing mechanics** versus **changing campaign architecture**.

A mistake is therefore not merely a negative training label.

It is a decision trajectory.

---

# 16. BFDM

BFDM is not a collection of rules saying "do what Brendon did."

The corpus is a durable research archive of Brendon's D&D creative history. Kit is one consumer.

The canonical BFDM research repository is private:

https://github.com/radarsaint/bfdm-corpus

External reviewers should use the public mirror:

https://github.com/radarsaint/dnd-solo/tree/main/corpus/bfdm

BFDM's job in KRABS is to provide evidence about expert judgment.

Its most valuable unit is not campaign lore or prose style. It is a reconstructable decision case:

```text id="pv4c5z"
SITUATION
What was happening?

CRITICAL CUES
What mattered enough to notice?

RECOGNITION
What kind of situation did the DM believe this was?

BIG PICTURE
What larger concerns were active?

INTENT
What did the players explicitly want?
What did the DM infer, and with what uncertainty?

MISSING INFORMATION
What else needed to be checked?

DM CONCERN
Why did this state warrant attention?

CANDIDATE INTERVENTIONS
What could reasonably have been done?

CHOSEN INTERVENTION
What was actually done?

PROJECTION
What consequence was expected?

OUTCOME
What happened?

REVISION / HINDSIGHT
Did later evidence change the judgment?

COUNTERFACTUAL
What tempting alternative would have been worse?

TRANSFER
What decision shape might make this precedent relevant again?
```

BFDM should preserve positive cases, failures, near-misses, abandonment, repair, later corrections, evolution over time, and format-specific adaptations.

Early and late practice should not be averaged into a timeless personality.

Historical behavior is evidence.

It is not automatic doctrine.

---

# 17. Campaign Intent Model

Campaign intent should be represented explicitly rather than living only in prose documents.

Not every piece of prep has the same importance.

At minimum the system needs to distinguish:

**High concepts** — foundational ideas the production is built around.

**Campaign purpose** — what kinds of experiences or questions the campaign is trying to produce.

**Through-lines** — developments intended to accumulate across time.

**Major planned structures** — important events, sets, characters, pressures, reveals, systems, or likely payoffs.

**Local preparation** — encounters, scenes, routes, clues, stat blocks, schedules, staging details.

These categories should not create an inflexible hierarchy where "high concept wins no matter what."

They provide Kit with information about **what a proposed adaptation might actually destroy**.

If a local encounter must change to preserve campaign purpose, change it.

If an entire prepared structure begins working against campaign purpose, change the structure.

If live history reveals that even an original assumption was mistaken, surface that at the appropriate level rather than protecting it merely because it was foundational.

---

# 18. State Model

KRABS does not prescribe one database, but conceptually state should be partitioned.

## Source / canon material

Prepared or published material that describes the world before live mutation.

## Authoritative dynamic state

What currently exists and what has actually happened.

## Entity beliefs

What NPCs, factions, monsters, players, and other actors believe or know.

## Episodic history

Events and experiences relevant to future behavior.

## Player model

Evidence-based hypotheses about players' patterns, interests, habits, misunderstandings, relationships to the game, and reactions.

These are hypotheses with confidence, not permanent personality labels.

## Character model

Patterns that have emerged from what the player character repeatedly chooses and experiences.

Player and character models remain separate.

## Campaign/story model

Active consequences, through-lines, motifs, unresolved questions, setups, pressures, relationships, and possible payoffs.

## Director intent

Current instructions and preproduction intent.

## BFDM procedural knowledge

Relevant precedent about DM judgment.

## Archive

Older or inactive information that remains retrievable but should not pollute immediate context.

No single vector store should be asked to represent all of these relationships.

---

# 19. Events and Projections

The existing runtime's append-only event ledger is retained and generalized.

Meaningful state changes should produce durable events.

A correction should normally produce another event or explicit revision record rather than silently rewriting history.

Different views can then be projected from the same authoritative history.

## Player-facing projection

What players experienced, discovered, and are allowed to know.

This may include recaps, maps, current information, handouts, and history.

## DM/runtime projection

The state necessary to continue running the world accurately.

## Director-facing projection

What Brendon or another authorized director needs to know.

This should not become an endless activity feed.

The point is **attention filtering**.

Potentially director-worthy material includes:

- consequential inventions;
- unexpected changes to major characters or factions;
- departure from campaign intent;
- uncertain adjudications with future precedent;
- player behavior with major design implications;
- continuity risks;
- structural failures;
- significant changes to planned material;
- emerging opportunities;
- events Kit judges likely to deserve human creative attention.

Many such items should be retrospective notifications:

> I did this. Here is why. Here is the consequence.

They should not all be approval requests.

Kit owns ordinary DM work.

---

# 20. Director Attention

The goal of delegation is defeated if Brendon becomes Kit's approval queue.

Kit should therefore learn what deserves director attention.

This can improve through feedback.

If Kit repeatedly flags a class of event and the director consistently indicates that she should simply handle it, future instances should generally remain below the escalation threshold.

If Kit fails to flag something the director considers important, that is evidence that the threshold or recognition model needs correction.

The desired long-term principle is:

> **Delegate decisions downward until their consequence justifies director attention.**

Director-facing review is itself part of Kit's learning loop.

Corrections should be classified before they become generalized behavior.

A director correction may be:

- a campaign fact correction;
- a rules correction;
- a specific NPC decision;
- a campaign-specific directive;
- a production instruction;
- a player-specific judgment;
- a DM judgment correction;
- a personality/voice correction;
- a reusable principle.

Not every correction should rewrite Kit's global behavior.

---

# 21. Hard Escalation Rules

[§20](#20-director-attention) makes director attention learned. Learned attention is the right mechanism and it cannot be the only one.

## Why a learned threshold is not sufficient

The feedback loop in §20 is asymmetric, and the asymmetry runs toward silence.

When Kit flags something the director considers routine, the director says so, and the threshold rises. That signal is cheap, frequent, and always observed.

When Kit *fails* to flag something that mattered, the correcting signal only arrives if the director independently discovers the thing Kit did not tell them about. In a continuous production spanning many scenes and many weeks — exactly the operating mode [§25](#25-kits-operating-modes) and [§26](#26-continuous-production-and-human-dms) commit to — that discovery is unreliable by construction. The director is not reading everything. That is the entire point of delegating.

So one error type is reliably punished and the other is only sometimes punished. A threshold trained under that pressure drifts upward until Kit escalates nothing, and the drift is invisible while it happens, because the symptom of a too-high threshold is the absence of messages. "Brendon stopped getting flagged" and "Kit got good at judging" produce identical inboxes.

A floor is not a correction to the learned model. It is the thing that makes the learned model's failure survivable.

## The floor

The campaign declares a **set of hard triggers**: explicit predicates over authoritative state and proposed events which, when true, force human involvement regardless of what Kit has learned.

Required properties:

**Explicit.** A trigger is a predicate the runtime evaluates, not a judgment Kit forms. "This event would permanently remove a player character" is a trigger. "This feels like it matters" is not — that is the learned layer's job, and it belongs there.

**Enumerable and short.** The floor is a list a director can read in one sitting. A long floor is indistinguishable from an approval queue, which [§20](#20-director-attention) correctly forbids.

**Director-owned.** Only a director changes the floor, through an explicit act. Kit may *propose* a change and must argue for it in the ordinary review channel; she may not enact one.

**Unreachable by learning.** No volume of "just handle it" erodes a hard trigger. The learned threshold operates strictly above the floor. If the director wants a trigger gone, they remove it from the floor, and that removal is itself a recorded event with an author and a time ([§19](#19-events-and-projections)). The floor is versioned the way canon is versioned: by appending, not by drift.

**Observable when it fires.** Every firing is logged with the predicate that matched, the event it blocked or annotated, and how it resolved. The firing rate is telemetry about the campaign's design, not just about Kit.

## Two mechanisms

**Hard stop.** The turn does not commit. The staged verdict is held, the player is told honestly that something is being checked rather than being given a fabricated result, and the director receives the specific predicate that matched plus the decision they need to make. A hard stop is stage 4 of the [§12](#12-the-adjudication-pipeline) pipeline, before the verdict becomes public.

**Mandatory notice.** The turn commits and play continues. The director notice cannot be suppressed by the learned threshold. This is the retrospective "I did this, here is why, here is the consequence" of [§19](#19-events-and-projections), made non-optional for a declared class of events.

Most of the floor should be mandatory notice. Hard stops are for consequences that cannot be unwound by appending more history.

## Candidate trigger classes

These are the classes a campaign's floor should consider, not a fixed list. Each production declares its own predicates and thresholds.

Hard stop:

- permanent loss of a player character, or of something a player authored, without that player's informed acceptance;
- irreversible destruction of a declared high concept, planned payoff, or campaign structure ([§17](#17-campaign-intent-model));
- a write that would invalidate history another party has already committed and been told about ([§24](#24-concurrency-and-write-authority));
- rewriting a committed event in place rather than appending a correction;
- a real-world safety or declared content-boundary condition;
- a player's explicit out-of-character distress or request to stop;
- a ruling that would set precedent contradicting a standing director directive.

Mandatory notice:

- consequential invention that later play will have to treat as canon;
- prep mutation above local scale ([§7](#7-prep-mutation-and-campaign-purpose));
- promotion of incidental material, or demotion of planned material, at structure scale;
- a new NPC or faction commitment with world consequences;
- a pending ruling held longer than the campaign's declared window;
- a declared rate being exceeded — character deaths per week, unobserved clock advances, scenes resolved without player presence.

That last class deserves emphasis. Rate triggers catch the failure mode no per-event predicate can see: nothing individually crossed a line, and the campaign still drifted somewhere nobody chose. It is the only trigger class that can notice Kit's *apparently successful* behavior accumulating into harm, which [§38](#38-notes-for-external-review) asks whether the system can do at all.

## Asynchronous fallback

A hard stop blocks a turn. A continuous production cannot block a scene indefinitely waiting for a human who is asleep.

Every hard trigger therefore declares its **timeout behavior** alongside its predicate. The options are: hold the scene and tell the player honestly that it is held; offer the affected players something to do that does not touch the leased domains; or apply a declared conservative default and convert the stop into a mandatory notice. Which one is appropriate is a campaign design decision, made in preproduction, per trigger.

A trigger without a declared timeout behavior is incomplete, because its real behavior under absence is "Kit improvises while blocked," which is the thing the floor exists to prevent.

## Not a license for timidity

The floor exists so that Kit can be *more* decisive everywhere else, and the specification should be read that way.

Between the floor and the learned threshold, Kit acts and reports afterward. She does not add discretionary stops of her own, does not convert uncertainty into an approval request, and does not soften play because a scene is heavy — [§14](#14-dark-difficult-and-personally-resonant-play) governs that, and it says pressure is not a failure. A hard stop names a matched predicate or it does not happen.

If a trigger fires often, the correct response is to examine the trigger or the campaign, not to teach Kit to tiptoe around it. A floor that fires constantly is a design defect being reported as caution.

## Status in `dnd-solo`

None of this is implemented. There is no director role, no director channel, no declared floor, and no trigger evaluation.

The adjacent machinery that exists: `PendingRuling` and the `ask_player` path can hold a turn and ask for input; `feedback` records out-of-character comments into Kit's private decision stage; degraded mode unlocks only after a declared number of rejected attempts, which is a small existing example of a threshold the host cannot simply assert its way past. The escalation floor would be a new subsystem with a new addressee, and [§34](#34-what-krabs-does-not-yet-solve) keeps the question of who the director is in a multi-director production open.

---

# 22. NPC and Faction Cognition

Important NPCs should persist as people rather than be regenerated as conversational devices.

A sufficiently important actor may require:

- identity;
- location;
- status;
- motive;
- immediate goal;
- longer plan;
- belief state;
- knowledge;
- misinformation;
- fear;
- constraints;
- resources;
- leverage;
- relationships;
- promises;
- injuries;
- current attitude;
- next likely action;
- memory of meaningful interactions;
- reconsideration triggers;
- distinctive communication behavior.

The important sequence is:

> **belief + motive + intention + relationship + means → behavior → performed dialogue**

not:

> generate colorful dialogue → infer what the NPC apparently wanted.

Factions may require similar persistent cognition at a different scale.

Locations may also possess active processes even when they do not possess minds.

---

# 23. Persistent World Motion

The world should continue to exist outside the currently active player scene.

Some processes stop when nobody is interacting with them.

Others do not.

A war, ritual, political struggle, investigation, business, disease, pursuit, travel plan, countdown, or NPC agenda may continue without players.

Kit must determine whether unattended processes advance rather than applying one universal "background simulation" rule.

This becomes especially important in asynchronous community play, where different groups may affect the same world at different times.

The system must be capable of distinguishing:

**world truth** from  
**what a particular party has observed** from  
**what another party knows**.

---

# 24. Concurrency and Write Authority

[§23](#23-persistent-world-motion) says the world keeps moving outside the active scene. [§6](#6-campaigns-as-productions) says session boundaries cannot be the fundamental unit. [§25](#25-kits-operating-modes) and [§26](#26-continuous-production-and-human-dms) commit to a continuous production with many scenes, many players, guest DMs, and a director all live at once.

Taken together, those commitments mean many writers touch authoritative state concurrently. v0.1 left who may write what, and when, undefined. This section defines it.

## The failure this solves

Start from the thing that makes this different from an ordinary database problem: **the performance layer has no undo.**

Every other part of the system is recoverable. A bad event can be corrected by appending another event. A wrong projection can be rebuilt. A rejected performance costs a retry and nothing else. But once a player has read "the ward is down and the corridor is open," that sentence is in their head, they have made plans around it, and no amount of ledger hygiene retracts it. [§12](#12-the-adjudication-pipeline)'s atomic commit of events and spoken text exists for exactly this reason.

So the ordinary distributed-systems answer — detect the conflict, abort the loser, retry — is only available *before* publication. After publication it is not a retry, it is a retraction, and retractions are the thing that destroys a player's trust that the world is real.

Two concrete failures bracket the design:

**Serialize everything and the world does not scale.** The current runtime holds one global `revision`. A turn declares the revision it read and commits only if nothing has moved. This is correct, and it is tested — the state/context prototype's sixth test asserts that a second connection cannot overwrite a turn using a stale revision. It also means any two simultaneous turns conflict, whether or not they have anything to do with each other. A card game in area 6c blocks a faction clock three levels away. With one player this is invisible. With a dozen concurrent scenes it is the first thing that breaks, and it breaks as unexplained failures and lost turns rather than as a clean error.

**Remove the check and you get lost updates that were already narrated.** Two scenes read the same region, both decide, both commit, last writer wins. The losing scene's events are gone from state but its *consequences were performed to its players*. That is the unrecoverable case: state and the players' shared understanding have permanently diverged, and nothing in the system knows it happened.

Concurrency is therefore not a scaling optimization in KRABS. It is a correctness requirement, and the invariant is narrow: **a write conflict must be detected before the dependent prose is published, never after.**

## Write domains

Partition authoritative state into **write domains**. A domain is the unit of exclusive write authority.

Candidate domains:

- **Entity** — an actor, NPC, or monster with persistent cognition ([§22](#22-npc-and-faction-cognition));
- **Region** — a location, area, or set of locations with its own geometry, contents, and active processes;
- **Party** — a group of PCs, their shared resources, and their position;
- **Clock / process** — an unattended development that advances on its own ([§23](#23-persistent-world-motion));
- **Structure** — a campaign-level event, set piece, or planned payoff ([§17](#17-campaign-intent-model));
- **Director intent** — standing instructions and preproduction material.

Rules on the partition:

Every authoritative datum belongs to exactly one domain. Domains are declared in campaign configuration, not inferred at runtime. Granularity is a design decision with a real trade-off: coarse domains are simple and serialize more play, fine domains allow more concurrency and make multi-domain turns common. Preproduction picks the granularity, because preproduction is where the campaign's concurrency profile is actually known.

Every committed event declares the domains it writes. This is the mechanism that makes the rest checkable.

## Leases

A turn acquires a **lease** on exactly the domains it intends to write, before adjudication, for a bounded duration. It commits only if it still holds them.

- **Exclusive write lease.** One holder. Required to commit an event writing that domain.
- **Shared read.** Unlimited holders. Reads record the domain's revision at read time.

Acquisition and verification:

A turn acquires leases at situation assembly, before the [§12](#12-the-adjudication-pipeline) gate resolves anything, because the gate's verdict is only valid for the state it resolved against. At commit, the runtime verifies the turn still holds every lease and that each read domain is still at the revision it was read at. Failure aborts the turn before publication. Per-domain revisions replace the single global revision; the semantics of stale-writer rejection are unchanged, only their scope narrows.

Deadlock and starvation:

Multi-domain acquisition follows a total order over domain identifiers, so two turns wanting the same pair cannot hold half each. Leases expire; expiry releases without committing, so an abandoned turn cannot wedge a region forever. Long scenes renew rather than holding indefinitely. A turn that cannot acquire its domains waits or fails cleanly; it never proceeds on the hope that nobody else is writing.

**Scene leases are what make concurrent play possible.** An active scene holds leases on its region, its present actors, and its party. Two scenes in disjoint domains hold disjoint leases and never conflict. This is the whole payoff: concurrency comes from the partition, not from optimism.

## Live play outranks background motion

A clock is both a domain and a writer. When an unattended process advances, it acquires leases the same way a scene does.

**A clock may not write a domain a live scene currently holds.** It defers. The ordering rule is that live play takes precedence over background motion for the same domain, because the scene is mid-adjudication against state the clock would move underneath it.

Deferral must be recorded, not dropped. A tick that silently vanishes because a region was busy produces exactly the wrong behavior: clocks stall in the regions where players are active, which are the regions where the clock's pressure matters most. A deferred advance is queued with the time it was due, and applies at the next boundary where the domain is free — with its original due time intact, so the fiction reflects when it should have happened rather than when the lease opened up.

## Cross-domain writes become proposals

Some events want to write domains someone else holds: a faction attacks a region where a party is mid-scene; an NPC in one scene affects an NPC in another.

Two legal resolutions. Acquire all affected domains in order and run one turn across them — correct, and it serializes everything it touches, so it should be reserved for events that genuinely are one causal act. Or downgrade the write to a **proposal** against the held domain, which the holder's next turn adjudicates at a declared boundary.

Prefer proposals. A faction's assault on an occupied region is better modeled as an intent arriving at the scene — something the scene can adjudicate, telegraph, and let the players respond to — than as a write that reaches in and changes the room the players are standing in. The concurrency primitive and the good DM behavior point the same direction here, which is usually a sign the primitive is the right one.

Scenes therefore need declared **boundaries**: points at which deferred clock advances and inbound proposals are applied. A scene with no boundaries holds its leases forever and starves the world around it.

## Leases govern writes, not knowledge

A lease is write authority. It says nothing about what anyone knows.

[§5](#5-core-invariants) keeps knowledge entity-specific and [§23](#23-persistent-world-motion) keeps world truth separate from what each party has observed. Many parties may hold shared reads on a region; what each of them *knows* about it remains its own per-entity state and is not affected by who holds the write lease.

There is a residual problem the lease model does not solve, and it should be named rather than hidden. Leases prevent lost writes. They do not prevent two parties from being told causally inconsistent things: a scene can narrate a fact read from a domain that later moves, and when the two parties meet, their histories disagree. The partial mitigation available is detection, not prevention — a turn records the domain revisions it read and which of those facts it published, so a later divergence is *detectable* and becomes a continuity-risk notice under [§21](#21-hard-escalation-rules)'s mandatory-notice class rather than a silent contradiction someone discovers in play. Full cross-party causal consistency remains open ([§34](#34-what-krabs-does-not-yet-solve)).

## Guest DMs and scene handoff

[§34](#34-what-krabs-does-not-yet-solve) leaves guest-DM control of scenes open. The lease primitive gives it a shape: a guest DM taking a scene is a lease transfer, and releasing the scene is a release. Control is bounded by the same expiry, so a guest who disappears does not hold a region hostage — which is precisely the dependency on volunteer availability that [§26](#26-continuous-production-and-human-dms) refuses to build on.

The permissions model on top of that — what a guest may write, what requires a director, how their writes are distinguished in the ledger — is not specified here.

## What `dnd-solo` already implements

The existing implementation is the **one-domain case** of this model, which is why v0.2 generalizes it rather than replacing it:

| KRABS concept | Current mechanism |
| --- | --- |
| Write domain | One domain: the whole world |
| Lease acquire | `BEGIN IMMEDIATE` plus the `kit_pending` staging row, keyed by `turn_id` and `revision` |
| Lease verification at commit | `expected_revision` compared against current; `StaleTurn` on mismatch |
| Lease release | `commit_kit_turn` with `consume_pending`, or `abandon` |
| Per-domain revision | One global `revision` on `snapshots` |
| Idempotence key | `turns.id`; identical retries do not apply twice |
| Append-only history | `ledger` with update and delete triggers raising `ABORT` |
| Fail closed before publication | Rejected performance leaves the turn uncommitted and the decision fixed |

The migration is additive rather than a rewrite: declare domains in campaign configuration, record written domains on each event, move the revision from one global counter to per-domain counters, and make the pending-turn row an explicit lease with an expiry. Nothing above requires abandoning the event ledger, the atomic commit, or the stale-writer semantics.

None of the multi-domain behavior is implemented or tested today. The single-domain case is both.

---

# 25. Kit's Operating Modes

The architecture should support several modes without creating different Kits.

## Solo DM

Kit runs the complete game for one player.

This remains an important quality test because there is nowhere for weak judgment, flat NPCs, bad pacing, or missing initiative to hide.

## Autonomous small-session DM

Kit runs a bounded group session without requiring continuous director supervision.

## Directed DM

A director provides private campaign instructions while Kit executes play.

## Live DM assistant

A human DM remains primary at the table while Kit supplies recall, improvisational support, rules/state retrieval, NPC context, consequence tracking, and other assistance.

## Guest-DM assistant

A guest DM receives the same kind of support rather than becoming an operational dependency.

## Continuous campaign operator

Eventually, Kit can sustain a persistent production across many scenes, locations, players, and asynchronous interactions.

The exact Discord mechanics belong to a later technical design.

KRABS establishes the requirement without prematurely choosing the implementation.

---

# 26. Continuous Production and Human DMs

Large campaigns historically required multiple humans taking turns handling a continuous game.

KRABS changes the dependency structure.

The campaign should assume that Kit is always available as its operational DM infrastructure.

Guest DMs can contribute because they want to contribute.

They are not required for the production to survive.

A guest may be given scenes, characters, events, or other creative responsibility and can use Kit as an assistant in the same broad way Brendon does.

The system should support collaboration without treating volunteer availability as a foundational resource.

Reliability is therefore part of DM quality.

A brilliant response followed by abandoned scenes, lost state, inconsistent rulings, forgotten promises, or degraded characters is not an excellent DM system.

---

# 27. Performance Layer

Good internal judgment can still produce bad D&D if it is expressed poorly.

The performance layer is responsible for converting the chosen action and authoritative consequences into actual play.

It includes:

- narration;
- NPC dialogue;
- tactical descriptions;
- questions;
- roll calls;
- results;
- scene framing;
- pacing;
- direct DM commentary;
- humor;
- reward presentation;
- transitions.

The existing personality work remains relevant here, particularly the requirements that NPCs feel embodied, opposition behaves competently, stakes are perceptible, creativity receives honest adjudication, loot has emotional weight, humor grows from the table rather than generic quips, and Kit's own table presence remains distinct from NPC voice.

However, expressed personality is downstream of judgment.

A clever line cannot repair a nonsensical decision.

The runtime should be able to diagnose:

> right judgment, poor performance

separately from:

> wrong judgment, polished performance.

---

# 28. The Expression Gap

Every important private DM decision that needs to affect play must acquire a legitimate public carrier.

If Kit privately recognizes danger but gives the player no evidence from which that danger could be understood, the recognition did not successfully reach play.

If Kit knows an NPC has become suspicious but nothing in behavior changes, the state is invisible.

If Kit knows a clue matters but simply tells the player the answer, the underlying investigation has been bypassed.

The system therefore needs to ask:

> **How can this private state become perceptible through the world?**

Possible carriers include NPC behavior, environmental evidence, mechanical consequences, timing, changes in availability, direct character knowledge, rumors, resource changes, visible preparation, altered relationships, or direct DM clarification where appropriate.

---

# 29. Evaluation

Evaluation must operate on trajectories rather than isolated prose samples.

A scene can sound excellent and still be wrong because Kit forgot what happened three scenes earlier.

A decision can look strange in isolation and prove excellent ten sessions later.

Evaluation should therefore measure whether Kit:

- retrieved the relevant facts;
- noticed the important cues;
- recognized the correct situation type;
- sought missing information appropriately;
- preserved explicit player intent;
- respected knowledge boundaries;
- generated legitimate candidate actions;
- selected a defensible intervention;
- adjudicated correctly;
- committed state accurately;
- expressed consequences clearly;
- preserved NPC identity;
- maintained meaningful challenge;
- served campaign intent without railroading;
- adapted when evidence changed;
- restrained herself when play was functioning;
- preserved consequences over time;
- completed obligations;
- surfaced director-worthy information appropriately.

Failure localization should distinguish at least:

**A. Retrieval failure** — the necessary information existed but was not retrieved.

**B. Salience failure** — the information was present but Kit did not realize it mattered.

**C. Judgment failure** — the situation was understood but the wrong DM intervention was chosen.

**D. Adjudication failure** — the intended judgment was sound but rules, procedure, or implementation were poor.

**E. State failure** — the result was not committed accurately or continuity later drifted.

**F. Expression failure** — the internal result was sound but the player-facing delivery failed to carry it.

**G. Concurrency failure** — a write was lost, a published fact was read from state that had already moved, or a clock advanced underneath a live scene ([§24](#24-concurrency-and-write-authority)).

**H. Escalation failure** — something crossed the floor without reaching a human, or Kit escalated what she owned ([§21](#21-hard-escalation-rules)).

This distinction is essential. Otherwise development degenerates into prompt patching.

Two of these classes are worth calling out because they are the ones a transcript cannot reveal. A concurrency failure looks like a continuity mistake and will be reported as one, so it has to be found from recorded domain revisions rather than from reading the prose. An escalation failure of the silent kind — the flag that never came — produces no artifact at all, which is why [§21](#21-hard-escalation-rules) makes the floor's firing rate telemetry rather than waiting for someone to notice an absence.

---

# 30. Reflection and Learning

Kit should evaluate meaningful play without constantly rewriting herself.

After significant scenes or production intervals, she may generate structured private observations.

These can identify:

- what she believed was happening;
- what she tried to accomplish;
- unexpected player behavior;
- whether the intended experience appeared to land;
- decisions she is uncertain about;
- potential precedent;
- unresolved consequences;
- director attention candidates.

Post-hoc reflection is **not trusted as factual evidence** about why a decision was made unless the relevant reasoning was captured during the decision itself.

The runtime should therefore preserve compact decision traces at action time when a decision is sufficiently consequential.

This is the same precommitment requirement [§12](#12-the-adjudication-pipeline) imposes on the pipeline, applied to learning rather than to play. A reflection written after the fact can explain any behavior, including behavior that had no reason. Only a record that existed before the outcome can be used as evidence about the decision.

---

# 31. Decision Trace

A meaningful DM decision may record:

```text
situation_id
authoritative_facts_used
information_retrieved
explicit_player_intent
inferred_intent_and_confidence
relevant_entities
recognized_situation
salient_cues
active_campaign_concerns
director_intent
uncertainties
additional_information_sought
candidate_interventions
selected_intervention
rules_resolution
expected_consequences
events_committed
player_facing_carrier
director_flag_if_any
later_feedback
```

v0.2 adds the fields the three new mechanisms need in order to be auditable rather than merely specified:

```text
write_domains_leased          which domains this turn held        (§24)
domain_revisions_read         what state the verdict resolved against
gate_verdict                  the symbolic outcome, before performance  (§12)
procedure_selected            which procedure runs this activity, and why
escalation_triggers_matched   floor predicates that fired, and how resolved  (§21)
```

`gate_verdict` and `procedure_selected` must be written before the performance text exists. That ordering is the whole value of the field: a verdict recorded afterward is a description of the prose, and [§12](#12-the-adjudication-pipeline)'s precedence property becomes unfalsifiable without it.

`domain_revisions_read` is what makes a concurrency failure diagnosable after the fact. Without it, a published fact read from stale state is indistinguishable from Kit having simply forgotten something.

Not every attack roll deserves this record.

The trace system should preserve consequential judgment without drowning the runtime in self-documentation.

---

# 32. Relationship to the Existing D&D Solo Runtime

The current implementation and architecture live at:

https://github.com/radarsaint/dnd-solo

KRABS does not discard that work.

It generalizes it.

Several existing architectural ideas remain directly useful:

- canonical DM identity distinct from backend state;
- bounded situation/context assembly rather than dumping all history into every turn;
- explicit state for players, knowledge, space, time, encounters, NPCs, factions, level stories, and campaign actors;
- motive/knowledge/means/relationship-based NPC action;
- separate player and player-character models;
- campaign, local-story, and current-scene concerns existing simultaneously;
- authoritative geometry and reveal boundaries;
- retrieval before invention;
- append-only factual event history;
- summaries as projections rather than truth;
- personality choosing among valid possibilities rather than fabricating world facts to satisfy its preferences.

KRABS changes the frame around those mechanisms.

The current solo runtime primarily solves the problem of running a particular one-player D&D campaign.

KRABS treats that runtime as an early implementation of a much larger architecture.

The solo game becomes both a useful product and a demanding laboratory for Kit's judgment.

A technical reviewer should inspect the repository rather than assume every mechanism described here still exists only on paper. Some earlier KRABS concerns already have prototypes, tests, contracts, or partial implementations.

v0.2's three additions each stand in a different relationship to that existing code, and the distinction matters for anyone planning work:

| v0.2 addition | Relationship to `dnd-solo` |
| --- | --- |
| [§12](#12-the-adjudication-pipeline) adjudication pipeline | **Mostly implemented.** The gate, the affordance checks, the performance validation, and the atomic commit exist. v0.2 states the ordering as a contract and names the one-pass path as non-conformant. |
| [§24](#24-concurrency-and-write-authority) concurrency model | **Generalization of implemented work.** The current global-revision scheme is the one-domain case. The migration is additive. |
| [§21](#21-hard-escalation-rules) escalation floor | **New subsystem.** There is no director role or channel to escalate to. |

---

# 33. Technical Direction Without Premature Commitment

KRABS intentionally does not mandate exact infrastructure yet.

However, established engineering patterns map naturally onto the problem.

The architecture strongly suggests:

- event-sourced authoritative history;
- materialized projections for fast current views;
- durable workflows for long-running clocks and asynchronous actions;
- actor-like persistence for independently active NPCs, factions, parties, or locations where justified;
- explicit symbolic state for truth, chronology, ownership, permissions, geometry, and mechanical constraints;
- language-model reasoning for interpretation, judgment, performance, and creative adaptation;
- hierarchical memory rather than a single flat retrieval store;
- trace-based long-horizon evaluation.

[§24](#24-concurrency-and-write-authority) adds a further set, and deliberately adds nothing novel. Bounded leases, ordered acquisition, per-partition versioning, deferred work queues, and single-writer partitioning are decades-old mechanisms with mature implementations. The actor model's single-threaded-per-entity discipline and durable-workflow engines' lease-and-heartbeat patterns both already encode most of §24. If implementing the concurrency model requires inventing a protocol, something has gone wrong.

These are architectural directions to investigate and reuse rather than inventions KRABS claims to have originated.

The project should aggressively avoid reinventing mature infrastructure when an established solution fits.

Custom engineering effort should concentrate where the problem is genuinely unusual:

> **Kit's DM judgment.**

---

# 34. What KRABS Does Not Yet Solve

This version deliberately leaves several matters open.

It does not specify the exact Discord integration or permissions model.

It does not choose a final event-store, actor framework, workflow engine, embedding system, database, or model provider.

It does not decide whether BFDM eventually informs Kit through retrieval, supervised examples, preference learning, fine-tuning, another learning method, or a combination.

It does not establish a universal formula for "satisfying."

It does not assume BFDM research is complete. Current research explicitly warns against treating evidence-dense Roanoke Season 3 as an answer key for Brendon's complete DM practice.

## What v0.2 narrowed, and what remains

v0.1 listed three open problems that v0.2 addresses. None is closed; each is now a smaller and more specific question.

**Shared-world concurrency.** v0.1 did not finalize a concurrency model. [§24](#24-concurrency-and-write-authority) now fixes the semantics: domains, leases, per-domain revisions, live-play precedence, proposals for cross-domain writes. Still open: domain granularity, which is a per-campaign design decision with no general answer; the policy for where scene boundaries fall; cross-party causal consistency, where §24 offers detection but not prevention; and the infrastructure choice.

**Guest-DM control of scenes.** v0.1 did not specify how guest DMs acquire and release scenes. [§24](#24-concurrency-and-write-authority) gives the primitive — control is a lease, release is a release, expiry prevents a vanished guest from holding a region. Still open: the permissions model, what a guest may write without a director, and how guest writes are attributed in the ledger.

**Director-attention thresholds.** v0.1 did not define the thresholds and made attention entirely learned. [§21](#21-hard-escalation-rules) now requires a floor and specifies the properties it must have. Still open: the actual trigger predicates for any real campaign, which are authored in preproduction; the learned layer's algorithm above the floor; and who holds director authority in a production with more than one director.

## New open problems introduced by v0.2

**The one-pass tension.** [§12](#12-the-adjudication-pipeline) makes the staged order normative for consequential turns, and the staged order costs a model round trip. The project's own playtest record shows latency is already a usability failure at 81 seconds. Whether a one-pass path can ever satisfy precedence — by fixing and committing the verdict in a prior call, by a different decomposition, or not at all — is unresolved.

**Classifying consequence before resolving it.** §12 requires the staged order for *mechanically consequential* turns, which presumes the runtime can tell which turns those are before it has resolved them. This is tractable in the obvious cases and genuinely unclear in the interesting ones.

**Trigger authorship.** [§21](#21-hard-escalation-rules) requires a short, enumerable floor. Nobody has yet written one for a real campaign, and a floor that turns out to need fifty predicates would falsify the section's central claim that a floor and an approval queue are different things.

These are legitimate open problems.

They should remain visible instead of being filled with plausible architecture merely so the document appears complete.

---

# 35. Development Standard

Every major addition to Kit should be explainable in terms of **what failure it solves**.

New memory systems should solve demonstrated continuity or retrieval failures.

New cognition stages should solve demonstrated noticing or judgment failures.

New personality rules should solve demonstrated behavioral failures.

New state should represent something whose absence causes real ambiguity or drift.

New director tooling should reduce director workload or improve consequential control.

New automation should increase reliable execution without degrading judgment.

The project should resist accumulating architecture because the architecture sounds sophisticated.

The standard is whether Kit becomes a better Dungeon Master.

This standard applies to v0.2's own additions, and they should be held to it. [§12](#12-the-adjudication-pipeline) answers a recorded live failure — the invented high-card game that deleted the marked deck from play. [§24](#24-concurrency-and-write-authority) answers a failure that has not happened yet, because the preconditions for it do not exist in a one-player game; it is justified by the end-state in [§36](#36-end-state-test) rather than by evidence, and that is a weaker justification which should be acknowledged as such. [§21](#21-hard-escalation-rules) answers a structural argument about an asymmetric feedback loop rather than an observed incident, for the same reason: there is no director role yet to fail.

Two of the three are therefore anticipatory. The honest position is that they should be specified now, because they constrain interfaces that are being built, and implemented when a real production creates the failure they prevent.

---

# 36. End-State Test

KRABS succeeds if the resulting system can eventually do all of the following without contradiction:

Brendon can sit down alone and have Kit run an excellent D&D campaign for him.

Brendon and Kit can spend months building a highly ambitious campaign together.

When that campaign launches, Kit can reliably execute large portions of it without requiring Brendon to manually carry every scene.

Players can create unexpected history and Kit can recognize when that history deserves to reshape preparation.

NPCs can remain people over long periods instead of resetting into chatbots.

The world can continue moving while different players are elsewhere.

Darkness, pressure, challenge, humor, attachment, failure, and payoff can all exist without Kit reducing good DMing to keeping everyone comfortable.

When Kit makes a mistake, the system can identify what kind of mistake occurred and learn from correction rather than merely changing wording.

Brendon can direct high-value creative decisions without becoming a bottleneck for routine execution.

Human DMs can contribute because it is fun and creatively valuable rather than because the production collapses without them.

The campaign can run continuously for weeks, preserve its history, adapt under pressure, reach its major moments, and finish.

And when it is over, the result should not feel like a large language model successfully processed thousands of D&D messages.

It should feel like a very good Dungeon Master ran a hell of a campaign.

---

# 37. Status of This Specification

KRABS v0.2 is a working specification, not a finished architecture.

Its primary implementation and research bases are:

**Kit runtime and design**
https://github.com/radarsaint/dnd-solo

**BFDM historical corpus and research** (private canonical)
https://github.com/radarsaint/bfdm-corpus

**BFDM public mirror for external review**
https://github.com/radarsaint/dnd-solo/tree/main/corpus/bfdm

Its strongest foundations come from:

- the existing D&D Solo Runtime design and its authority/state/context separation;
- the current Kit personality and performance work;
- BFDM's corpus charter and project guardrails;
- BFDM's developing model of longitudinal DM decision-making;
- documented live failures and corrections from Kit testing;
- historical Roanoke campaign operation;
- current end-state requirements clarified by Brendon.

Where historical evidence remains incomplete, KRABS should say so.

Where BFDM later contradicts this document, the contradiction should be investigated rather than hidden.

Where implementation reveals that an architectural assumption does not work, KRABS itself is subject to revision.

The document is canonical because it is the current reference point.

Canonical does not mean immutable.

---

# 38. Notes for External Review

An AI or human reviewing KRABS should not limit critique to whether the prose sounds plausible.

The useful questions are:

- Does the proposed architecture match what already exists in `dnd-solo`?
- Which parts of KRABS accidentally reinvent mechanisms already implemented?
- Which existing mechanisms should be generalized rather than replaced?
- Does the architecture preserve the distinction between simulation, judgment, and performance?
- Are the state boundaries sufficient for long-duration and asynchronous play?
- Does the proposed judgment architecture match what BFDM evidence actually demonstrates?
- Where does KRABS overgeneralize from limited historical evidence?
- What established AI, simulation, workflow, memory, game-AI, or distributed-systems approaches could replace custom invention?
- What problems described here are genuinely novel?
- What will break first when moving from one-player Mad Mage to persistent multi-player play?
- What will break first when moving from bounded sessions to a continuous several-week production?
- Can the director-attention model actually reduce human workload without making Kit timid or dependent?
- Is the architecture capable of learning from mistakes without converting every correction into a universal rule?
- Does the system have enough machinery to recognize when its own apparently successful behavior is harming the campaign?
- Is "DM judgment" specified tightly enough to become an engineering and evaluation target rather than remaining an aspiration?
- What important subsystem is missing?

The goal of external review should be to attack KRABS, identify blind spots, and locate mature solutions we should steal rather than to validate the document politely.

## Where v0.2 stands against these questions

Three of the questions above produced v0.2 and should now be re-asked against the answers rather than the gap.

*What breaks first moving to multi-player play?* v0.2's answer is the single global revision, and [§24](#24-concurrency-and-write-authority) is the proposed fix. A reviewer should attack the domain partition: whether entity, region, party, clock, structure, and director intent are the right cut; whether proposals are an adequate substitute for cross-domain transactions; and whether a campaign author can realistically declare a partition that does not either serialize everything or produce multi-domain turns constantly.

*Can director attention reduce workload without making Kit timid?* v0.2 argues the learned threshold drifts toward silence and adds a floor underneath it ([§21](#21-hard-escalation-rules)). A reviewer should attack the floor's size: the section claims a floor and an approval queue are different things, and that claim rests entirely on the floor staying short. It should also attack the timeout behavior, which is where a blocking trigger in a weeks-long asynchronous production either degrades gracefully or stalls a scene.

*Does the system have the machinery to notice its own successful-looking harm?* Partially, and only through one mechanism: §21's rate triggers, which fire on accumulation rather than on any single event. That is thin. A reviewer looking for the weakest load-bearing claim in v0.2 should look there.

The remaining questions are unchanged and still open to attack.