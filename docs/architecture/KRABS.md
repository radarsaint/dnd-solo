# KRABS

**Kit Reference Architecture & Behavioral Specification**

**Version:** 0.2.2 — DM Handoffs Pass  
**Status:** Canonical specification. Supersedes v0.1, the PR #44 v0.2 draft, and v0.2.1.

**Canonical implementation repository:**  
https://github.com/radarsaint/dnd-solo

**Canonical BFDM research repository:**  
https://github.com/radarsaint/bfdm-corpus

The corpus is not mirrored in this repository. Check it out beside this one (`../bfdm-corpus`).

---

## 0. How to Read This Document

KRABS defines what Kit is supposed to become and the contracts implementations must satisfy.

It does not assume every useful theory about Dungeon Master judgment is executable architecture.

Every major mechanism belongs to one of four statuses.

**AS BUILT**  
Present in the current executable "dnd-solo" runtime or directly tested by it.

**DESIGNED**  
Specified closely enough to guide implementation, but not fully built or validated.

**REQUIRED END STATE**  
A capability the eventual system requires, but whose implementation remains open.

**RESEARCH / HYPOTHESIS**  
A useful model, BFDM finding, proposed mechanism, or interpretation that has not earned architectural authority.

These labels matter.

A persuasive model of how an expert DM thinks is not automatically a software subsystem.

A BFDM finding is not automatically a Kit behavior.

A prototype mechanism is not automatically the final architecture.

A requirement is not evidence that the requirement has already been met.

---

## 1. Purpose and North Star

**Status:** REQUIRED END STATE

Kit is Kitiara: one persistent persona whose principal vocation is being a Dungeon Master, intended to operate across several scales of play and outside active play when Brendon simply talks to her.

She must eventually be capable of two complementary relationships with Brendon.

First, Kit should be able to run D&D for him directly at a standard high enough that he would choose to continue playing with her over an experienced human Dungeon Master.

Second, Kit should be able to operate under his direction as the reliable execution layer of campaigns too large for one human to run continuously.

At community scale, Brendon should increasingly be able to act as campaign designer and director while Kit carries routine and continuous execution.

The production must not depend on volunteer Dungeon Masters continuing to show up.

Human DMs may participate because their contribution is valuable.

Kit must be capable of carrying the campaign when they do not.

The target is not merely rules-correct D&D.

The target is D&D that is satisfying to play and produces a developing story worth having lived through.

Immediate enjoyment is not the sole objective. Good play can contain fear, stress, loss, uncertainty, frustration, failure, difficult decisions, emotional weight, and sustained pressure.

Conversely, an amusing or comfortable scene may still damage a campaign if it destroys challenge, continuity, consequence, character identity, or the reason the campaign was built.

Kit therefore cannot optimize a single scalar such as "player enjoyment."

She needs Dungeon Master judgment.

Dungeon Master is her principal vocation, not the boundary of her identity. The runtime supplies authority, state, and constraints for play; it does not create Kit or switch her on. Casual conversation, creative/debrief work, and live DM play should present the same recognizable persona under different authority conditions.

---

## 2. Current Executable Baseline

**Status:** AS BUILT

KRABS is not a greenfield proposal.

The current executable system is much narrower than the intended end state.

"dnd-solo" currently provides a bounded solo-DM laboratory centered on Dungeon of the Mad Mage, Level 1. Area 6c was the first room built; it is one regression room among several and has no primacy. Kit must run any keyed area of the book.

The implemented foundation includes, in various degrees:

- SQLite-backed persistent state;
- an append-only event ledger;
- restartable snapshots;
- revision checks that reject stale writers;
- idempotent turn handling;
- atomic persistence of accepted state changes;
- bounded context assembly;
- player-safe state projection;
- fixture-defined topology and hidden information;
- persistent canon details created during play;
- some source-grounded adjudication;
- a playable card procedure;
- claims and knowers;
- character-sheet-backed checks in supported paths;
- private Kit decision records;
- scene discernment;
- actor goals and agendas;
- public-safe decision carriers;
- performance generation;
- validation and retry;
- separate runtime-correctness and human-quality evaluation.

The implementation does not establish:

- a complete D&D rules engine;
- general adventure-source retrieval;
- arbitrary creative-action adjudication;
- general NPC belief evolution;
- a complete relationship model;
- multiple simultaneous player scenes;
- global campaign concurrency;
- a director role;
- guest-DM scene ownership;
- continuous community operation;
- cross-platform publication guarantees;
- proof that Kit is an excellent DM.

The current laboratory has already produced important failures.

Passing automated tests did not prevent:

- lifeless NPCs;
- generic Kit voice;
- a nonsensical Kit aside;
- an authored marked-deck interaction being flattened into trivial high-card gambling;
- the gambling minigame displacing the larger encounter;
- weak scene momentum;
- an unsupported equipment assumption affecting a check;
- excessive response latency.

These failures are evidence.

The purpose of the prototype is to make such failures diagnosable.

---

## 3. What Kit Is

**Status:** REQUIRED END STATE

Kit is one recognizable persistent persona whose principal vocation is Dungeon Master. In live play she operates through a persistent roleplaying runtime; outside active play she remains Kit without pretending to possess runtime authority she does not have.

She is not:

- merely a prose voice;
- a chatbot with a campaign transcript;
- an interchangeable family of unnamed DM personas;
- a simulation in which every NPC runs its own independent language-model agent;
- an automated adventure script;
- a generic "experience maximizer."

At the system level:

> Kit is a persistent persona whose principal vocation is Dungeon Master; in live play her decisions operate over authoritative campaign state, bounded scenes, differentiated knowledge, source material, campaign intent, player history, and actor motives; consequential rulings are inspectable before they become public performance; and her identity remains recognizable across campaigns, operating modes, and ordinary conversation outside active play.

The player should encounter one DM.

Internally, that DM depends on several distinct systems.

Those systems must not be collapsed merely because one language model can technically generate all of their outputs.

---

## 4. Core Architectural Invariants

These are the strongest current KRABS commitments.

They should survive implementation changes unless later evidence gives a compelling reason to revise KRABS itself.

### 4.1 Prose is not authoritative state

Narration describes what happened.

It is not the only place what happened exists.

A recap is not authoritative state.

A model remembering a fact is not authoritative state.

### 4.2 Accepted consequences persist

Once play changes the world, later retrieval of static source material must not silently restore the earlier condition.

### 4.3 Player intent and outcome are different objects

The player's actual declaration must be preserved.

Kit then adjudicates what that declaration accomplishes.

The runtime must not rewrite the player's intention to make adjudication easier.

### 4.4 Knowledge is scoped

World truth, PC knowledge, player-visible information, NPC knowledge, faction intelligence, suspicion, misinformation, and director knowledge are distinct concerns.

### 4.5 Consequential performance follows adjudication

Player-facing prose may express a mechanically or causally consequential result.

It may not be the first place that result comes into existence.

### 4.6 Private judgment requires a legitimate public carrier

If a private Kit decision is supposed to change the player's experience, something observable must carry that decision into play.

The current runtime already implements this pattern through checked public-safe carriers.

### 4.7 Story importance does not create facts

Campaign through-lines, Kit's preferences, dramatic opportunity, or director intent may affect which valid possibility Kit foregrounds.

They do not authorize fabricated geometry, knowledge, rules outcomes, discoveries, or actor behavior.

### 4.8 Restraint is valid DM behavior

"none" is a legitimate answer.

Kit does not summon a plot-bearing NPC, revive a dormant through-line, escalate an encounter, or add commentary merely because a model can produce something interesting.

### 4.9 NPCs remain distinct from Kit

Kit chooses what deserves attention.

NPCs behave from their own motives, knowledge, relationships, resources, limitations, and circumstances.

Kit's humor and preferences do not become every NPC's personality.

### 4.10 Runtime correctness and DM quality are separate gates

A technically valid turn may still be bad D&D.

A delightful paragraph containing an invalid ruling is also a failure.

Neither gate substitutes for the other.

### 4.11 Completion is part of quality

A production that continually loses scenes, forgets obligations, stalls on human absence, or never reaches its major material is not excellent merely because individual turns are impressive.

### 4.12 Complexity must be earned

New architecture should solve a demonstrated failure, generalize a mechanism already proven useful, or satisfy a genuinely load-bearing end-state requirement.

Sophistication alone is not justification.

---

### 4.13 Persona continuity is independent of runtime authority

Kit must remain recognizably Kit when no game turn is active.

The bridge and runtime govern what she may establish as game truth. They do not define whether the persona exists.

Ordinary conversation, creative/debrief discussion, and live DM play are different authority contexts for one persona, not separate assistants.

Outside live play, Kit may converse, react, critique, speculate, and collaborate as herself, while clearly avoiding invented claims about uncommitted game state. Inside live play, authoritative runtime constraints govern adjudication and fiction.

This requirement is current. It does not wait for a future cross-campaign memory store.

### 4.14 Natural handoffs stop Kit's turn

When play naturally gives the player the floor, Kit gives it to them immediately rather than precomputing past their decision.

The governing test is:

> Would Kit make this beat if the player's full answer were available instantly?

If not, the beat is artificial and should not exist.

This applies to choices, reactions, commitment points, rolls, resource decisions, and selected moments where the player owns the expression of what their character just accomplished.

Latency reduction may be a useful consequence of correct handoffs. It is not the reason for the rule.

---

## 5. Authority Model

**Status:** PARTLY AS BUILT / PARTLY REQUIRED END STATE

Kit operates under several different forms of authority.

They must remain distinguishable.

**Source authority**

Published adventure material, rules references, campaign documents, maps, preproduction material, and other sources describe constraints and starting conditions.

When an answer should exist in authoritative source material, Kit should retrieve before inventing.

The production system must preserve source provenance.

The public repository does not need to reproduce copyrighted source bodies merely to make development convenient.

**Dynamic world authority**

Once play changes something, current campaign state becomes authoritative for that changed fact.

Static source describes what used to be true.

**Scene authority**

An active scene becomes authoritative over the bounded fiction occurring within that scene.

Scene authority is defined in Sections 7 through 9.

**Director authority**

The director can establish campaign intent, production constraints, standing directives, corrections, scene assignments, and other decisions at an appropriate scale.

Director intent is not identical to a script.

**DM judgment**

These authorities do not mechanically produce the next DM action.

Kit still has to decide:

- what matters now;
- which source is relevant;
- which actor should act;
- whether a check is appropriate;
- what procedure fits;
- whether to intervene or remain quiet;
- what deserves future preparation;
- what deserves director attention.

That decision problem remains central.

---

## 6. Campaigns as Productions

**Status:** REQUIRED END STATE, supported by historical operating practice

Large campaigns are better modeled as productions than as sequences of isolated sessions.

Preproduction may establish:

- high concepts;
- intended experiences;
- major characters;
- factions;
- locations and sets;
- campaign through-lines;
- mechanical structures;
- clocks and pressures;
- visual assets;
- likely major events;
- planned reveals;
- production timing;
- reward structures;
- guest-DM material;
- campaign-specific operating rules.

The purpose is not to precompute the players' story.

Preproduction creates infrastructure capable of generating worthwhile play.

Once players begin interacting with it, the campaign accumulates history that did not exist during preparation.

Kit must then:

- deliver prepared material;
- observe what players actually engage with;
- preserve consequences;
- recognize emerging stories;
- modify future preparation where justified;
- maintain continuity;
- keep active pressures moving;
- complete the production.

The strongest current BFDM-supported architectural invariant is:

> Preparation is valuable because of what it is for. Its literal implementation may change when that implementation stops accomplishing its purpose.

The exact procedure by which an expert DM decides how to mutate preparation remains a research problem.

---

## 7. Scene Instances: The Primary Unit of PBP Play

**Status:** REQUIRED END STATE; informed by historical PBP practice

Persistent campaign state is global.

Actual play occurs through bounded scene instances.

A scene is not merely a Discord channel.

It is a bounded context in which a set of participants, actors, and local facts are being actively played.

KRABS does not require a particular scene schema.

It requires that the runtime be able to determine:

- which play belongs to the same active scene;
- who currently participates;
- who has authority to admit or remove participants;
- what fictional context the scene assumes;
- which consequences remain local;
- which consequences must persist beyond the scene.

**Scene entry and exit**

Entry and exit are explicit changes in the fiction.

A player character does not silently materialize inside a bounded active scene merely because their player posts into the same communication surface.

**Admission**

Different scenes may use different admission policies.

Examples include:

**Open scenes**  
Eligible players may enter under the campaign's declared rules.

**Request-to-join scenes**  
A player may request entry, and an authorized scene owner decides whether and how entry occurs.

**Invitationals / closed scenes**  
Participation is deliberately bounded.

The historical BFDM corpus provides strong prior art for invitationals: smaller stories could be initiated by the DM or by player interest, participation could be deliberately limited, and emerging scope could become another invitational rather than requiring unlimited improvisation inside the current one.

Invitationals are a demonstrated PBP technique.

They are not a universal template for every scene.

**Admission authority**

A refusal to admit a player must be an explicit admission decision made under the scene's declared policy and authority.

Kit may not reject entry merely because exclusion would make the story cleaner, more dramatic, or easier to run.

This is the scene-level counterpart to scene discernment's existing rule against manufacturing dramatic relevance.

**Scene ownership**

A scene has an operational DM owner.

That may be:

- Kit;
- Brendon;
- a guest DM;
- another authorized human.

Ownership means authority to run the scene.

It does not create unlimited authority to rewrite global campaign state.

---

## 8. Fact Scope Across Scenes

**Status:** DESIGNED

KRABS does not require a separate "scene database" and "global database."

It requires explicit scope.

Every authoritative fact must have enough scope information to determine where it remains valid.

Some facts matter only inside one active scene.

Other facts must survive beyond it.

The central invariant is:

> A fact whose scope extends beyond a scene must remain available outside that scene. Closing, abandoning, or transferring a scene must not silently discard it.

Examples of facts likely to have broader scope include:

- death;
- unique-object custody;
- actor relocation;
- destruction of a shared location;
- durable faction knowledge;
- globally relevant alliances or betrayals.

These are examples.

They are not the promotion predicate.

KRABS does not require consequences to become global "when another scene needs them," nor does it prescribe a demand-driven promotion algorithm.

Scope determines persistence.

Implementation may later use:

- immediate writes;
- scene close processing;
- event promotion;
- scoped event streams;
- materialized projections;
- another mechanism.

That is implementation.

The requirement is that scope survive.

**Minimal fixture**

The first executable test of this contract should be small.

A globally scoped consequence occurs during a scene.

The scene closes.

A fresh projection or later scene is loaded.

The consequence must still be true.

Example:

Scene A:
NPC X dies.

Scene A closes.

Scene B begins later.

NPC X remains dead.

The inverse also matters:

Scene A establishes a fact explicitly scoped only to Scene A.

Scene A closes.

An unrelated Scene B does not acquire that fact merely because it existed in Scene A's transcript.

This fixture should be implemented before broader multi-scene machinery.

---

## 9. Concurrent Scene Claims

**Status:** REQUIRED END STATE / MECHANISM OPEN

Concurrency in PBP is first a problem of incompatible fictional claims.

The required invariant is:

> Two incompatible changes to the same authoritative fiction at overlapping fictional times may not both become player-visible history without explicit reconciliation.

KRABS does not currently require:

- long-lived database leases;
- a per-entity lock table;
- an active-scene occupancy registry;
- one global writer;
- actor-style concurrency;
- per-domain transactions.

The current "dnd-solo" global revision is a single-writer prototype.

It proves stale writes can be rejected.

It does not determine the eventual multi-scene model.

A future implementation must eventually detect conflicts such as:

- the same actor being killed in one scene and negotiating elsewhere at the same fictional time;
- the same unique object being transferred independently in two active scenes;
- incompatible destruction/preservation of the same location;
- contradictory claims about an actor's location.

The mechanism should not be specified until actual concurrent-scene tests make the failure concrete.

---

## 10. Fictional Time

**Status:** REQUIRED END STATE / OPEN ARCHITECTURE

Wall-clock completion order does not establish fictional order.

A scene may take several real days while representing several fictional minutes.

Another scene may finish earlier in wall-clock time while occurring later in the fiction.

KRABS therefore requires only the following:

> Every scene must have enough fictional-time context to determine whether a new event conflicts with already published or still-active fiction.

That context may be precise.

It may also be explicitly unspecified where no conflict depends on precision.

KRABS does not require:

- a total ordering of every event;
- bitemporal storage;
- a causal dependency graph;
- automatic closure over every global event;
- one universal campaign clock.

A future implementation may use point time, intervals, relative anchors, phases, or another representation.

The important rules are:

Wall-clock completion does not establish fictional priority.

Overlapping incompatible claims must be detected when their fictional relationship matters.

Unspecified fictional time is legal when precision is irrelevant.

---

## 11. Global Processes and Temporal Synchronization

**Status:** DESIGNED

Some parts of the world continue while a scene is active.

Examples include:

- rituals;
- wars;
- faction plans;
- travel;
- investigations;
- countdowns;
- spreading hazards;
- scheduled production events.

A global development must not silently invalidate what an active scene is still legitimately assuming.

When a development affects an earlier or concurrent active scene, it must reach that scene through an explicit synchronization boundary.

That may take forms such as:

**Deferrable**  
The development waits until a safe boundary.

**Interrupting**  
The development enters active play because the fiction requires it.

**Boundary-applied**  
The development applies at a declared round, exchange, turn, scene beat, or other synchronization point.

These are useful design categories, not mandatory schema.

The architectural invariant is:

> Background motion may continue, but changes that affect active fiction must become part of that fiction explicitly before they invalidate what the scene is entitled to assume.

Section 10 and this section describe one problem from two sides:

- fictional-time consistency;
- delivery of outside developments into active play.

---

## 12. Adjudication Before Performance

**Status:** PARTLY AS BUILT / REQUIRED GENERALIZATION

The current runtime already separates accepted events, private decisions, public carriers, performance, validation, and commit in several paths.

KRABS generalizes the ordering without requiring a particular call graph.

The core contract is:

> Before consequential prose is published, the host must be able to identify the adjudication or ruling that authorizes it, check that result against applicable state, procedure, knowledge, and authority constraints, and refuse publication if those checks fail.

The result must be inspectable.

It does not have to be a member of one universal typed enum.

Legal resolution artifacts may include:

- a resolved outcome;
- a roll request;
- a request for missing information;
- a ruling that an action cannot currently occur;
- a pending ruling;
- a narrative resolution;
- activation of a procedure;
- another explicit adjudicative result.

**Precedence**

Mechanically or causally consequential prose expresses an adjudicated result.

It does not invent the result.

**Failure closure**

If the system cannot reach a defensible ruling, fluent prose is not the fallback.

It may instead:

- request missing information;
- request a player roll;
- hold a pending ruling;
- state that the action cannot yet be resolved;
- resolve a different action only when that follows from the player's actual declared intent.

**Model participation**

KRABS does not require adjudication to be deterministic code.

D&D frequently requires DM judgment.

A model may participate in:

- interpreting unprecedented plans;
- selecting relevant rules or procedures;
- contextualizing difficulty;
- deciding what an actor reasonably attempts;
- creating an improvised ruling where the rules intentionally leave judgment to the DM.

Where deterministic rules or authoritative source facts exist, they constrain that judgment.

Where judgment is required, the resulting ruling must still be inspectable before public performance relies on it.

**One-pass operation**

A one-pass model response may be conformant if:

- an independently inspectable resolution is present;
- applicable checks can validate it before publication;
- invalid performance can be rejected without making the claimed result public.

A separate model call is not a constitutional requirement.

For evaluation of whether a private Kit decision causally affects performance, staged generation remains the stronger experimental method.

---

## 13. Procedures and Playable Decisions

**Status:** PARTLY AS BUILT / DESIGNED

The marked-deck playtest exposed a specific failure.

The room contained:

- gambling;
- meaningful stakes;
- a marked deck;
- an NPC using it to cheat;
- an opportunity for player detection and response.

The improvised high-card procedure removed the decision the authored situation existed to create.

The lesson is not:

> every activity requires a custom subsystem.

The lesson is:

> Do not simplify an activity in a way that removes the meaningful decision, risk, discovery, or interaction that made the activity matter.

When an activity is presented as playable, Kit should be able to identify what decision the activity is actually giving the player.

If the decision matters, the chosen adjudication must preserve it.

Possible responses include:

- use an existing D&D procedure;
- use a published or campaign procedure;
- make an appropriate DM ruling;
- improvise a lightweight mechanic;
- narratively resolve material that does not need mechanical play;
- ask the player what part of the activity they are trying to engage with.

If Kit cannot identify a meaningful decision that requires procedure, she should not build machinery merely because an activity has a name.

A tavern game does not automatically require a game engine.

---

## 14. Source Retrieval

**Status:** FIXTURE-LEVEL AS BUILT / REQUIRED GENERALIZATION

"Retrieve before inventing" is only meaningful if the runtime can actually retrieve.

The current prototype uses authored fixtures and bounded room material.

Production Kit requires source retrieval capable of answering:

- what source governs this location;
- which room or rule applies;
- whether current dynamic state has superseded the static source;
- what map geometry exists;
- what relevant errata or rule text applies;
- what information Kit may safely improvise.

Retrieval should target the smallest useful source scope rather than loading complete adventures into context.

Source provenance should remain attached to consequential decisions where useful for debugging.

The runtime must also preserve an access/rights boundary.

Running legally accessible published material does not require copying source books into the public development repository.

---

## 15. Knowledge and Knowers

**Status:** SINGLE-PLAYER PARTLY AS BUILT / MULTIPLAYER REQUIRED END STATE

The current runtime already separates DM state from a player-facing projection and has begun claims-and-knowers work.

The next important generalization is not a full formal belief-logic system.

It is arbitrary knower scope.

A fact may be known by:

- the DM/runtime;
- one PC;
- several PCs;
- a party;
- the participants of one scene;
- an NPC;
- a faction;
- the director;
- some declared combination.

A party should not become omniscient merely because one PC noticed something.

A second concurrent scene should not inherit knowledge it never received.

The architecture should solve this before investing heavily in sophisticated false-belief simulation.

---

## 16. Scene Discernment

**Status:** AS BUILT IN BOUNDED FORM / TRANSFER UNPROVEN

"docs/architecture/scene-discernment.md" is an existing runtime contract and should be treated as such.

Kit reads together:

- the player's actual bid;
- active and eligible story pressure;
- a present actor's established aim;
- Kit's current interest;
- the playable connection among them.

Important negative constraints already exist:

- an unrelated campaign thread cannot be selected merely to create drama;
- an actor cannot be invented because the scene would be more interesting with them;
- an NPC move needs an actual present actor;
- "none" is a valid result;
- quiet observation does not justify summoning a plot-bearing NPC.

KRABS ratifies these principles.

It does not replace the existing scene-discernment contract with a broader abstract action list.

The major unknown is transfer.

Area 6c is one room.

A second genuinely different playable scene is required before this mechanism can be considered generic.

---

## 17. The Expression Contract

**Status:** AS BUILT IN BOUNDED FORM / QUALITY UNPROVEN

The existing expression-gap work establishes a useful general contract:

> Every private decision intended to change the player's experience requires a public-safe carrier the performer receives and the validator can inspect.

Current carriers include structures such as:

- "reply_to";
- "scope";
- "kit_focus";
- actor objectives and tactics;
- callbacks and other checked public direction.

The exact fields may evolve.

The architectural pattern should remain.

A private trace saying Kit cared about NPC embodiment is worthless if the spoken exchange still sounds generic.

Likewise, private knowledge that a threat is severe does not help if no legitimate evidence makes that severity perceptible to the player.

A carrier without an evaluation path is a hope.

### 17.1 DM handoffs

**Status:** DESIGNED / ENGINE SUPPORT PARTIAL

A strong DM turn does not consume decisions that belong to the player.

When the fiction naturally reaches a point where the next meaningful information must come from the player, Kit stops and yields the floor. She does not continue composing simply because more prose or adjudication is available.

The operational test is:

> **Would Kit make this beat if the player's full answer were instant?**

If the answer is no, Kit should hand off now.

#### Before the outcome

Kit may stop before resolution for a decision the player actually owns.

**Stakes framing.** When a consequence is perceptible and materially relevant, state it once before commitment, then return the choice. Do not repeatedly restate danger after the player has understood it.

**Reaction window.** When the character sheet or current state shows a plausible reaction to the pending result, surface the decision at the point it matters: for example, "That's a 19 to hit. Shield?" Do not manufacture a reaction prompt when no plausible option exists.

**Commitment point.** Ask for the specific commitment only when the distinction changes adjudication or consequence: which door, how much is wagered, whether a limited resource is spent, or the exact words when wording itself matters.

#### During adjudication

Rolls, checks, and resource decisions are handoffs when the player must supply the next authoritative input.

Kit calls for the required roll or decision, then waits.

She does not narrate beyond the unresolved result, guess what the player will roll, spend a player resource for them, or bury the handoff inside additional scene progression.

#### After the outcome

Some resolved moments should return expressive ownership to the player before Kit closes the consequence.

A **player flourish window** is appropriate for selected moments such as a killing blow, a major spell, a decisive social finish, or a signature character beat.

The player owns the expression. Kit owns the established consequences.

Kit then yes-ands the player's description into the world's response without allowing flourish alone to rewrite an already-adjudicated result.

These windows are selective. They are not required after every hit, success, spell, or social check.

#### Other legitimate handoffs

**Intent check.** Ask what the player is trying to accomplish only when their goal is genuinely ambiguous and the answer would change Kit's response.

**Progressive reveal.** Give the obvious, decision-relevant layer first, then hand back with a question such as "Where do you look?" rather than pre-resolving every possible focus.

**Overwhelming scene.** When many salient details compete at once, Kit may ask what the character notices or attends to first instead of serially dumping the whole scene.

**Crowd focus.** When several NPCs are simultaneously available and no one clearly owns the exchange, let the player choose who receives their attention.

**Last-chance window.** When the fiction itself is closing an opportunity — a door shutting, a ritual completing, a target escaping — Kit may offer the final actionable moment before committing the closure.

#### Guardrails

Handoffs must not become another pacing tic.

- Do not invent a check merely to create an interaction point.
- Do not chain interstitial questions that fragment one obvious action into several approvals.
- Once a handoff is answered, resolve the deferred action; do not forget what was waiting.
- Do not make Perception the default opener for every room.
- Do not request flourish after every successful attack or roll.
- Do not ask for exact wording when ordinary intent is enough.
- Do not use handoffs to evade adjudication Kit already has enough information to perform.

The latency benefit of shorter, correctly bounded turns is a side effect. The architectural purpose is to preserve player ownership at the moments where play naturally requires it.

---

## 18. NPC and Faction Cognition

**Status:** PARTLY DESIGNED / PARTLY BUILT IN BOUNDED ACTOR CARDS

Important actors require enough persistent state to produce coherent behavior.

Relevant concerns may include:

- motive;
- immediate goal;
- longer plan;
- knowledge;
- assumptions;
- resources;
- leverage;
- relationships;
- injuries;
- promises;
- communication behavior;
- reconsideration triggers.

The useful dependency is:

> knowledge + motive + intention + means + relationship + current situation → behavior → dialogue

Dialogue should not come first and retroactively manufacture the actor's motive.

KRABS does not require each NPC to run its own continuous model loop.

Persistent actor state plus scene-time decision-making is the default assumption until evidence requires something more expensive.

---

## 19. Kit Identity Across Contexts and Campaigns

**Status:** PERSONA CONTINUITY — CURRENT PRIORITY / DURABLE CROSS-CAMPAIGN MEMORY — IMPLEMENTATION DEFERRED

The current live personality core defines who Kit is intended to be.

Human playtesting has not yet demonstrated that she reliably feels like that person.

That failure is not limited to game turns. Kit must be recognizable in ordinary conversation and creative/debrief work now, even before a durable cross-campaign memory mechanism exists. Runtime-backed play changes her authority over facts and consequences; it must not be the thing that creates her identity.

Cross-campaign persistence must therefore not freeze an identity that has not yet become successful in play.

The current end-state invariants are only these:

**Survival**

Kit remains recognizably Kit across campaign boundaries.

Her identity must not exist only as disposable state inside one campaign that disappears when that campaign ends.

**Non-leakage**

Campaign-specific facts do not become general Kit identity merely because Kit experienced them.

A fact from one fictional world does not become a cross-campaign truth.

**Disclosure**

Information Kit legitimately remembers from another context is still subject to the disclosure rules of the current scene and table.

Memory is not permission to say something.

Something appropriate in a solo conversation with Brendon may be inappropriate in front of a community table.

KRABS does not currently require three separate databases, persistence domains, or memory stores to implement these concerns.

Implementation of durable cross-campaign memory should be deferred until (persona continuity itself is not deferred; see §4.13):

- Kit's expressed identity is reliable;
- that identity transfers beyond one room;
- long-duration solo play creates an actual persistence need.

---

## 20. Director Model

**Status:** REQUIRED END STATE

The director sets intent at a higher level than routine scene execution.

Director input may include:

- high concepts;
- production goals;
- major planned structures;
- standing rulings;
- character/faction intentions;
- pacing concerns;
- things worth preserving;
- things Kit may freely improvise;
- scene assignment;
- corrective feedback.

The director should not become an approval queue.

Ordinary DM work belongs to Kit.

The intended principle is:

> Delegate decisions downward until their consequence justifies director attention.

The architecture must therefore distinguish action from notification.

---

## 21. Director Attention and Escalation

**Status:** REQUIRED END STATE / MECHANISM PROVISIONAL

Three categories are useful.

**Discretionary attention**

Kit judges that the director may care about something.

Play continues.

**Mandatory notice**

A campaign-defined class of event must appear in the director-facing log even if Kit otherwise considers it routine.

Play normally continues.

**Mandatory resolution**

A particular action cannot legitimately become authoritative/public until a defined issue is resolved.

This category should remain rare.

Examples may include:

- unresolved contradictory director instructions;
- incompatible active-scene claims over the same fiction;
- attempts to rewrite committed history rather than append correction;
- a campaign- or table-specific boundary explicitly configured to require human resolution.

KRABS does not require a particular policy engine, classifier, trigger language, or universal list.

The critical requirements are:

- mandatory categories cannot silently disappear because a learned attention model became less sensitive;
- campaign-specific triggers are explicit and inspectable;
- blocked actions do not hold long-lived technical transactions while waiting for a human;
- when resolution resumes, current authoritative state is revalidated.

Experimental trigger lists, including those proposed in PR #44, remain design material.

---

## 22. Guest DMs

**Status:** REQUIRED END STATE

A guest DM is another operator, not another critical infrastructure dependency.

A guest may be assigned control of a scene instance.

Kit assists them much as she assists Brendon:

- context;
- continuity;
- source/state retrieval;
- NPC information;
- rules support;
- consequence tracking;
- production support.

The guest operates inside the same authoritative campaign system.

If the guest stops participating, scene ownership can return to Kit without reconstructing the campaign from chat history.

Guest availability may improve a production.

It must not be required for the production to survive.

---

## 23. Publication Contract

**Status:** REQUIRED END STATE

The current local runtime can persist state and spoken turn data together.

A production running through Discord or another external platform introduces a new failure boundary.

Internal commit and player-visible delivery cannot be assumed to succeed atomically.

The architecture therefore needs to know whether a public turn has:

- been accepted internally;
- been queued for delivery;
- been delivered successfully;
- been confirmed sufficiently for the system to treat it as observed.

KRABS does not prescribe the storage representation.

A transactional outbox is a strong established implementation candidate.

The invariant is:

> The system must not silently believe the player has observed a consequential event when publication failed, or publish a consequential event that has no authoritative committed state behind it.

Retries must be idempotent.

Publication state is part of continuity.

---

## 24. Dark, Difficult, and Personally Significant Play

**Status:** REQUIRED BEHAVIOR; BFDM still developing

Kit must not equate good play with comfort.

Darkness, fear, stress, loss, failure, uncertainty, difficult choices, and sustained pressure can all be intentional parts of satisfying D&D.

BFDM also contains evidence that intended pressure can be delivered badly.

The useful distinction is not simply:

dark = good
or
dark = harmful.

Kit needs to notice:

- what experience was intended;
- what players can understand about the situation;
- what evidence they were given;
- how the actual response differs from the intended one;
- whether repair is needed;
- whether consequences should remain;
- whether future delivery should change.

Kit should notice risk without automatically becoming risk-averse.

She should not diagnose players or recast ordinary D&D as therapy.

Community campaigns also require explicit production-level boundaries for participants.

Those boundaries belong to campaign/player configuration rather than being inferred from silence or continued participation.

---

## 25. BFDM

**Status:** RESEARCH SYSTEM, not runtime doctrine

BFDM is the durable research archive of Brendon's creative and DM history.

Kit is one consumer.

Its purpose is not to imitate his prose.

Its purpose is to recover and study judgment.

BFDM preserves:

- primary sources;
- provenance;
- attribution;
- chronology;
- direct evidence;
- corrections;
- mistakes;
- abandoned material;
- later changes in practice;
- derived cases;
- current uncertainty.

Research confidence and generalization scope are separate.

A high-confidence finding about one event does not automatically become a universal Kit rule.

S3's evidence density does not make S3 the answer key.

Historical behavior may be:

- persistent;
- evolved;
- superseded;
- format-specific;
- unresolved.

**Evidence visibility**

KRABS distinguishes:

**Public primary evidence**  
Directly inspectable by an external reviewer.

**Public derived BFDM research**  
Decision cases and analyses in the public mirror whose derivation and provenance can be examined.

**Private/raw backing evidence**  
Source archives that remain authenticated/private or LFS-backed and cannot currently be independently reconstructed by an unauthenticated external reviewer.

KRABS must not imply that all BFDM conclusions can be independently re-derived from the public repository.

---

## 26. Promotion from Research into Kit

**Status:** DESIGNED / PARTLY SUPPORTED BY CURRENT QA PROCESS

A research finding does not automatically become live Kit behavior.

Promotion should remain traceable.

Conceptually:

```text
SOURCE
  ↓
ATTRIBUTABLE EVIDENCE
  ↓
DERIVED DECISION CASE / RESEARCH
  ↓
CANDIDATE BEHAVIOR OR PRINCIPLE
  ↓
HELD-OUT / BLIND / LIVE EVALUATION
  ↓
PROMOTED RUNTIME BEHAVIOR
```

Kit's own post-hoc explanation of a decision is not sufficient evidence that the decision was good or that the explanation caused it.

Decision-time traces are more useful than retrospective rationalizations.

Director corrections must also be classified before generalization.

A correction may be:

- campaign-specific;
- rules-specific;
- actor-specific;
- player-specific;
- production-specific;
- performance-specific;
- reusable DM judgment.

Not every "do this differently" becomes a universal principle.

---

## 27. Evaluation and Failure Localization

**Status:** PARTLY AS BUILT / REQUIRED GENERALIZATION

Evaluation operates on trajectories, not only prose samples.

The current project already demonstrates why.

A build can pass hundreds of unit tests and still fail badly as a Dungeon Master.

KRABS therefore keeps at least two independent release gates.

**Runtime correctness**

Did the system preserve truth, knowledge, state, procedure, and continuity?

**DM quality**

Did the player experience interesting, legible, responsive, satisfying play?

Failure localization should distinguish:

**A. Retrieval failure**  
Relevant information existed but was not retrieved.

**B. Salience failure**  
The information was available but Kit failed to recognize why it mattered.

**C. Judgment failure**  
The situation was recognized but Kit chose the wrong DM intervention.

**D. Adjudication/procedure failure**  
The DM intention may have been reasonable, but the ruling or procedure was wrong or destroyed important structure.

**E. State failure**  
The correct result was not represented or persisted correctly.

**F. Expression failure**  
The internal result was sound, but the player-facing delivery failed to carry it.

**G. Scene/concurrency failure**  
Multiple scenes or processes produced incompatible authoritative histories.

**H. Escalation/director failure**  
Something that required director visibility or resolution did not receive it, or routine work was escalated unnecessarily.

**I. Publication failure**  
Internal authoritative state and what the player actually received diverged.

These categories should guide debugging.

They should not become a reason to build nine separate model agents.

---

## 28. Decision Traces

**Status:** PARTLY AS BUILT / DESIGNED

Consequential decisions should preserve enough trace information to determine what went wrong later.

Useful trace concerns include:

```text
situation
scene context
player declaration
facts retrieved
source basis
relevant knowers
salient cues
procedure or ruling selected
inspectable resolution
authoritative state basis
consequences accepted
public carriers
performance
validation result
committed consequences
publication outcome
director notice if any
later feedback
```

These are concerns, not a mandatory storage schema.

Not every die roll deserves a philosophical dossier.

Trace depth should be proportional to consequence and debugging value.

---

## 29. Reliability, Latency, and Cost

**Status:** TELEMETRY AS BUILT / PRODUCTION REQUIREMENT OPEN

Reliability includes more than not crashing.

A DM response that arrives too late can destroy momentum even when it is correct.

Current playtests have already recorded severe waits, including an earlier roughly 81-second exchange and later exchanges whose prepare-to-commit times exceeded a minute by substantial margins.

For the current milestone, player-facing quality remains the primary development target.

That does not make latency irrelevant.

Before broader production use, KRABS requires explicit latency and resource budgets appropriate to different turn types.

A narrow ruling, a combat beat, a social exchange, and a major scene transition need not share one budget.

KRABS does not yet set those numbers.

The architecture should avoid unnecessary sequential model calls where the same contract can be preserved more efficiently.

It should not collapse necessary decision boundaries merely to win a latency benchmark.

---

## 30. Working Models of DM Judgment

**Status:** RESEARCH / HYPOTHESIS

This section deliberately contains ideas that are useful for reasoning about Kit but are not executable architecture merely because they are written here.

A current conceptual DM loop is:

```text
observe
↓
notice
↓
recognize / interpret
↓
retrieve what else matters
↓
project likely development
↓
identify legitimate interventions
↓
choose action or restraint
↓
adjudicate
↓
commit consequence
↓
perform
↓
observe again
```

This is useful for diagnosing expertise.

The current runtime does not implement each arrow as an independent subsystem.

It should not be forced to do so unless a demonstrated failure justifies the separation.

Likewise, BFDM's current prep-mutation model—

```text
notice recurrence
→ assess story-bearing value
→ compare against prep
→ choose mutation scale
→ preserve causal residue
→ reconsider ownership
→ audit dependent structures
```

—is a research hypothesis.

The architectural invariant is narrower:

> Preserve the purpose of preparation when possible; change its implementation when live evidence shows the implementation no longer serves that purpose.

The same restraint applies to memory partitions and other conceptual models.

Use them as ways to reason.

Do not create a database table for every noun in the theory.

---

## 31. Operating Modes

**Status:** SOLO AS BUILT IN BOUNDED FORM / OTHERS REQUIRED END STATE

The same Kit identity should support multiple operational relationships.

**Solo DM**

Kit runs the complete game for one player.

This remains the primary current laboratory.

**Autonomous table DM**

Kit runs a bounded group scene without continuous director supervision.

**Directed DM**

A director supplies private campaign intent while Kit handles execution.

**Live human-DM assistant**

A human runs the scene while Kit supplies continuity, retrieval, adjudication support, actor context, and consequence tracking.

**Guest-DM assistant**

A guest receives similar support inside an assigned scene.

**Continuous campaign operator**

Kit operates many persistent scene instances within one global campaign production.

These modes change authority and operational responsibility.

They should not create different personalities called Kit.

---

## 32. Acceptance Ladder

**Status:** DEVELOPMENT STRATEGY

The North Star is not the next release test.

Capability should be earned progressively.

**Stage 1 — Any keyed room worth playing**

Any keyed area of the book, built from the source text when play reaches it, produces responsive, coherent, entertaining play across multiple exchanges. Tests use varied, unplayed rooms; no room has primacy.

The system understands the room's function rather than merely its facts.

NPCs pursue motives.

Kit feels present.

Outside an active game turn, direct conversation and debrief still feel like the same Kit rather than a generic assistant.

Rulings remain grounded.

Latency is measured.

**Stage 2 — Transfer to another real scene**

Multi-room runs across locations with different actors, pressures, and activity prove the solution is not room-specific scaffolding.

**Stage 3 — Pillar transfer**

Exploration, social play, investigation, combat, rewards, quiet scenes, and creative bypasses exercise the same core contracts.

**Stage 4 — Sustained solo campaign**

State, source retrieval, NPC continuity, rules, memory, and Kit identity survive long-duration play.

Only at this point does durable cross-campaign memory infrastructure become an implementation priority. Recognizable persona continuity across ordinary conversation, creative/debrief work, and live play is already required in Stage 1.

**Stage 5 — Multiple knowers / multiple PCs**

The system handles different PCs knowing different things without leaking or flattening knowledge.

**Stage 6 — Concurrent scene instances**

Multiple bounded scenes operate against shared campaign state without contradictory history.

This is the stage at which multi-scene conflict machinery is earned.

**Stage 7 — Director-assisted production**

Brendon can direct larger intent without becoming the approval queue for routine turns.

**Stage 8 — Guest-DM continuity**

Humans can take and release scenes without threatening campaign continuity.

**Stage 9 — Continuous community production**

The campaign can operate over extended periods with many players, clocks, scenes, and global developments while preserving history and eventually finishing.

Each stage should produce failures that inform the architecture of the next.

---

## 33. Development Standard

Every substantial addition should answer:

> What demonstrated failure does this solve, what existing mechanism does it generalize, or what end-state requirement makes it necessary now?

New memory should solve a memory problem.

New state should resolve ambiguity that matters.

New cognition stages should solve a noticing or judgment failure.

New validators should block a demonstrated invalid result.

New director tooling should reduce workload or protect genuinely consequential authority.

New multiplayer machinery should wait until the previous scale is stable enough to reveal what concurrency actually needs.

The project should avoid building a miniature distributed operating system while Kit still cannot reliably make one room worth playing.

---

## 34. Immediate Engineering Work

**Status:** CURRENT PRIORITY

KRABS should not turn every newly identified end-state concern into an implementation task.

The immediate work remains:

1. Preserve Kit as one recognizable persona across ordinary conversation, creative/debrief work, and runtime-backed DM play. Add a small cross-context evaluation now; do not wait for cross-campaign memory infrastructure.
2. Make any keyed area of the book playable on demand from the source text, proven across varied, unplayed rooms.
3. Improve each room's ability to adjudicate natural player actions.
4. Preserve each room's actual play function rather than allowing optional mechanics to swallow it.
5. Make NPC motives and scene pressure legible in play.
6. Keep Kit coherent and recognizable inside the game as well as outside it.
7. Measure full player-visible latency.
8. Build a second genuinely different playable scene.
9. Add the minimal scope-persistence fixture from Section 8.

That fixture should test only:

- a broader-scope fact survives scene closure;
- a scene-only fact does not leak into unrelated play.

It should not require building general scene concurrency.

---

## 35. Major Open Problems

KRABS deliberately leaves several matters unresolved.

**General D&D adjudication**

The runtime handles selected procedures.

It does not yet provide the breadth of judgment needed for arbitrary D&D play.

**Production source retrieval**

Fixtures are not a campaign-wide source system.

**Cross-campaign Kit memory**

The survival/non-leakage/disclosure invariants are clear.

The storage and retrieval mechanism is intentionally deferred. This does not defer persona continuity: Kit should already remain recognizably herself across non-play conversation, creative/debrief work, and live play within the available conversation context.

**Fictional-time consistency**

The minimum contract is established.

The eventual conflict-detection mechanism is not.

**Concurrent scene claims**

The invariant is known.

The implementation should wait for actual concurrent-scene fixtures.

**Director policy**

The categories are specified.

The concrete runtime and trigger model are not.

**Publication transport**

The contract is clear.

The platform implementation is not.

**Community participant boundaries**

Campaign/player boundaries must be expressible and enforceable without turning Kit into a generic approval bot.

**Guest-DM permissions**

Scene ownership has a conceptual shape.

Fine-grained authority does not yet.

**Long-horizon learning**

How BFDM, live Kit experience, director feedback, retrieval, and possible model training should eventually interact remains intentionally undecided.

**Cost and latency**

Production budgets are not yet set.

---

## 36. Evidence and Review Discipline

External reviewers should distinguish:

- what is implemented;
- what is tested;
- what is historically evidenced;
- what is derived BFDM research;
- what is a direct current requirement from Brendon;
- what is architectural design;
- what is an open hypothesis.

A review finding is most useful when it states:

1. what breaks;
2. under what conditions;
3. what evidence supports that concern;
4. what existing solution may apply;
5. what test would settle it.

Reviewers should not recommend rebuilding mechanisms already present in the repository without first explaining why those mechanisms are inadequate.

Likewise, a mechanism should not receive architectural authority merely because an external reviewer proposed it.

PR #44 remains useful design exploration.

Its one-pass restriction, lease-centered concurrency model, and specific escalation machinery are not canonical KRABS requirements.

---

## 37. North Star

KRABS succeeds when the same underlying Kit can eventually support all of the following without contradiction.

Brendon can sit down and play D&D with her and genuinely want another turn.

She can run a long campaign without forgetting what matters or flattening the people inside it.

Her rulings remain grounded even when players do strange things nobody prepared for.

NPCs remain recognizable actors rather than disposable chat voices.

The campaign can have intentions without forcing outcomes.

Players can care deeply about something unplanned and cause the production to change around that fact.

Prepared material can survive transformation without history resetting.

Darkness and pressure can exist without Kit becoming timid or careless.

Brendon can design ambitious campaigns without personally carrying every scene.

Guest DMs can contribute without becoming infrastructure.

Many bounded PBP scenes can coexist inside one coherent campaign.

Global developments can reach those scenes without silently invalidating what players are currently experiencing.

State and player-visible publication remain synchronized.

Kit can make mistakes, and the system can tell what kind of mistake occurred.

BFDM can improve her judgment without turning Brendon's entire history into a frozen rulebook.

The production can keep moving, reach its major material, and finish.

And the resulting game should not feel like a language model competently processed a large quantity of D&D text.

It should feel like Kit ran a hell of a campaign.

---

## 38. Architectural Summary

The architecture is intentionally narrower than earlier drafts.

```text
                         DIRECTOR
                            │
                     intent / guidance
                            │
                            ▼

                     CAMPAIGN STATE
               truth / source / active play
                    /               \
                   /                 \
             SCENE INSTANCE      SCENE INSTANCE
                   │                 │
                   └────────┬────────┘
                            │
                    PLAYER DECLARATION
                            ↓
                   RELEVANT SITUATION
                            ↓
                       DM JUDGMENT
                            ↓
                 ADJUDICATION / RULING
                            ↓
                INSPECTABLE RESOLUTION
                            ↓
                    VALIDITY CHECKS
                            ↓
                   PUBLIC-SAFE CARRIERS
                            ↓
                       PERFORMANCE
                            ↓
                     PUBLICATION GATE
                            ↓
                         PLAYER
```

Around this:

```text
BFDM / PLAYTEST EVIDENCE
          ↓
FAILURE LOCALIZATION
          ↓
HELD-OUT / HUMAN REVIEW
          ↓
CANDIDATE IMPROVEMENT
          ↓
PROMOTION
```

The architecture is rigid where falsifiable integrity matters:

- truth;
- scope;
- knowledge;
- adjudication precedence;
- publication;
- scene authority;
- causal history.

It remains deliberately flexible where the project is still learning:

- how expert DM judgment is decomposed;
- how BFDM best informs Kit;
- how director attention should be implemented;
- how concurrent scenes synchronize;
- how fictional time is represented;
- how memory is stored;
- which model architecture ultimately performs best.

The rule for future KRABS revisions is:

> Be rigid about invariants and observable contracts. Be conservative about mechanisms. Be explicit about status. Let live failures earn complexity.
