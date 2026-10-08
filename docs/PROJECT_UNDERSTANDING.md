# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-10-08  
**Context reviewed against:** `dnd-solo/main @ ea74255559faa57dc2b044f01731f61e0f85079d`; `bfdm-corpus/main @ c18796a2e988d91353707b33377c8ea0e670974d`

> This document is the project's current **semantic model**: what we are building, where we are, why we got here, what changed our thinking, how the major workstreams fit together, what we currently believe, what remains uncertain, and where the evidence points next.
>
> It exists so a capable fresh GPT can resume the project conversation without Brendon reconstructing the project by hand.

This document does **not** replace live authority.

For current executable facts, use live `dnd-solo/main` plus `PROJECT_CONTROL.md`.  
For current corpus/source/research facts, use live `bfdm-corpus/main` plus that repo's `PROJECT_CONTROL.md`.  
For proposed work, use the owning issue or PR.  
For player-facing quality, use current human/live evidence rather than architecture or test counts.

If those sources change the meaning of this document, this document should be **rewritten to match the better model**. Do not preserve an outdated interpretation merely because it has history behind it; Git, PRs, audits, and decision records preserve the history.

---

# 1. Living project brief

## 1.1 What we are building

The project is building **Kitiara ("Kit", "DM Kit")**, a persistent AI Dungeon Master and creative partner.

**KRABS v0.2.2 (`docs/architecture/KRABS.md` on current `dnd-solo/main`) is the canonical long-term Kit Reference Architecture & Behavioral Specification.** It defines what Kit is supposed to become and the contracts implementations must satisfy. Current runtime code may implement only part of KRABS, and later evidence may justify revising KRABS itself, but the runtime does not supersede KRABS merely by evolving beyond an early prototype.

The old ChatGPT Project attachment containing **KRABS v0.1** is superseded by the live v0.2.2 specification. That is a version/authority correction, **not** a decision that KRABS as a project architecture is obsolete or belongs to an "old era." The other legacy ChatGPT Project attachments are the same kind of non-authority; section 17 names them, and `docs/KIT_PROJECT_START_HERE.md` is only the router to live authority.

The near-term executable surface is the solo-DM runtime in `radarsaint/dnd-solo`. The deeper research program in `radarsaint/bfdm-corpus` preserves and studies Brendon's long history of campaign design, live Dungeon Master judgment, experimentation, failure, revision, and creative method.

The corpus is not the product.  
The runtime is not the product.  
The architecture is not the product.  
BFDM research is not the product.

**Kit is the product. The total experienced game is the acceptance layer.**

Longer term, the project aims at a Kit capable of carrying persistent, asynchronous, multiplayer campaigns under Brendon's direction at a scale comparable to the historical Roanoke productions, without requiring Brendon or volunteer human DMs to provide the continuous runtime.

The hard requirement is therefore larger than "make an LLM good at narration." Kit has to combine persistent world truth, source grounding, adjudication, differentiated NPC/faction state, campaign continuity, DM judgment, personality, presentation, restraint, long-horizon consequences, and director intent into one coherent Dungeon Master experience.

## 1.2 Where the project is now

The project is **past the stage where its main problem can honestly be described as missing machinery**.

The current runtime is materially beyond the original Area 6c prototype. It has a generalized chat-hosted SQLite substrate, room loading, hidden-information projection, claims/knowers, agendas, attitudes, persistence, one-pass and staged execution, bounded procedures and combat, manifests, retry/idempotency support, and a large mechanical test surface.

The research substrate has also advanced. BFDM PR #40 merged on 2026-10-08: the catalog now holds 195 BCS identities through BCS-000195, with 193 indexed source containers (BCS-000059 is context-only; BCS-000068 is an excerpt without a source container). Model-facing Discord retrieval exists, and the old Git LFS opacity problem should not be restarted. The remaining missing revisions, Rowing Oak imagery, Bodfish Google Site, partial Earthfall/Saturday Project histories, and known-source gaps remain explicit archival work dependent on source access. Accessible evidence is not semantically verified judgment research.

The important bottlenecks have moved upward.

Right now the project has three major confidence gaps:

1. **Current player-experience truth.** Runtime implementation advanced faster than sustained Brendon-facing evaluation. Several old failures may no longer be current, while several intended fixes have not yet proved themselves in ordinary play.
2. **BFDM derived-research trust.** Source accessibility is strong enough for serious research, but polished derived work is not automatically trustworthy. The active forensic audit exists because citations and locators can still reconstruct incorrectly or support claims too broadly.
3. **Shared project understanding.** Capable AI workers have repeatedly entered the project with different mental models, forcing Brendon to rebuild context, correct resource identities, explain what has already been solved, or stop agents from treating proxies as outcomes. The project itself now needs to carry that semantic continuity.

This means the current program is increasingly about **turning uncertainty into evidence and keeping the resulting understanding coherent**, rather than reflexively adding more architecture.

## 1.3 How we got here

The current approach is the result of several rounds of correction.

Early Kit work proved that a model could be given state, rules, personality material, and a bounded playable scene. Area 6c became a useful testbed because it was richly authored and repeatedly exercised.

That success also produced a false mental model: implementation and evaluation began to orbit Area 6c too heavily. Later work generalized the runtime substantially, while project audits clarified that Area 6c is a historical testbed, not the architecture of Kit and not a sufficient model of DM quality.

Player-facing tests then exposed another gap: strong architecture and green tests could coexist with flat NPCs, weak expression, bad pacing, missed social intent, or simply an unsatisfying game. The project increasingly separated **what the machinery knows** from **what actually reaches the player**.

At the same time, BFDM research expanded. The corpus became substantially more accessible, including model-facing Discord retrieval. That removed a major mechanical research blocker, but it exposed a deeper epistemic one: accessible evidence does not make existing derived conclusions correct. The forensic integrity work exists because some polished, cited research could not yet be treated as source-verified.

The October 7 audits unified these problems under one project-level correction:

> **Proxy evidence is not demonstrated truth.**

Passing tests are not satisfying play.  
A landed fix is not demonstrated player-facing improvement.  
Citation presence is not semantic verification.  
Source accessibility is not trustworthy derived research.  
Room loading is not source-to-room authoring.  
Architecture is not implementation.  
A document calling itself canonical is not necessarily current authority.

**A built component is not an outcome until someone actually uses its output.** The October 8 PR #40 continuity check exposed a further failure: the semantic inbox, Gardener protocol, checkpoint, and drift checker could all exist while nobody was assigned or invoked to reconcile the recorded change. A successful status check can report an unreconciled Brain; it does not complete that reconciliation. The broader failure mode is **premature completion / missing downstream consumer**: work is marked finished at the build, record, review, or test boundary rather than at the promised consequence. It must be guarded against in every workstream.

This thread exposed the same failure at the project-management layer: a bootstrap file, context inbox, or freshness checker does not by itself mean a future GPT has inherited the project's real mental model.

The response is the current Project Brain design: the project should preserve not only state and evidence, but also the **best current semantic understanding of what that state means**.

## 1.4 Current strategic model

The project should now be understood as four linked questions:

**Can the machinery support the work?**  
This is primarily the `dnd-solo` runtime question. The answer is increasingly "yes, across a much broader surface than before," with concrete remaining gaps rather than a missing foundation.

**Can we trust the research we want Kit to learn from?**  
This is the BFDM evidence question. Source/substrate readiness is ahead of derived-research trust. High-leverage claims need semantic verification before they become runtime doctrine.

**Can Kit actually use and express what the project gives her?**  
Private state, BFDM insight, source knowledge, and runtime capability only matter if they survive into good DM judgment and player-facing performance.

**Does the player actually experience a better Dungeon Master?**  
This is the final acceptance question. It cannot be answered by tests, architecture, research quality, or internal reasoning alone.

A fifth supporting question has now become explicit:

**Can every serious collaborator start from the same evolving mental model of the project?**  
If not, the project repeatedly pays a tax in contradictory plans, duplicated work, stale assumptions, and Brendon having to act as manual memory.

No single agent or chat should be the memory substrate. Nagatha remains valuable for PM/review/acceptance reconciliation, Skippy remains central to runtime engineering, Grok Build is a shell/repository execution resource, ordinary GPTs perform substantial reasoning/research/synthesis, and ChatGPT Work is reserved for work where its autonomous multi-source capability materially matters. The project itself must carry the continuity between them.

## 1.5 Current workstreams and how they depend on one another

### Runtime and integration

The runtime lane is no longer "build a DM engine from scratch."

Its near-term job is to reconcile and land known runtime work, close demonstrated blockers, avoid stale failure claims, and preserve enough instrumentation that later player-facing evaluation can tell us what actually happened.

Current demonstrated blocker classes include:
- player-roll ownership / Let It Ride behavior (#103);
- incomplete combat transitions and related state handling (#97 / #101);
- validator functional floors rewarding length over functional completeness (#102);
- at least one deliberate social-omission recognition gap (#73).

These are narrower than old blanket claims that combat, natural language, NPCs, or the whole runtime "do not work."

### Player-experience evaluation

This lane is now disproportionately important because implementation has outrun evidence.

The next valuable play evidence is not another proof that Area 6c can run. It is sustained current-build play in a materially different real room that crosses ordinary boundaries between exploration, social interaction, physical action, checks, NPC initiative, and combat where appropriate.

The goal is to discover the **next quality ceiling**, not to rediscover already-known plumbing defects.

### BFDM integrity and research

The corpus is sufficiently accessible for serious work.

The current research priority is trust: verify high-leverage derived claims against primary evidence, attack attractive hypotheses adversarially, find restraint/non-intervention cases that visible-action research can miss, and reconstruct failure -> diagnosis -> correction -> later-behavior trajectories.

PR #28 remains useful as a hypothesis map rather than a gold-label foundation. PR #38 is active forensic integrity work and demonstrates why semantic verification matters.

Stage 3 precedent/minimal-cognition experiments should consume evidence whose lineage and confidence are explicit. Stage 4 heavier cognition architecture remains later.

### Project understanding and continuity

This workstream exists because project knowledge was repeatedly trapped inside individual chats, stale Project files, branch-local handoffs, and agent-specific context windows.

The target is not "better documentation."

The target is:

> A fresh capable GPT should be able to understand what the project is, where it is, why it got here, what changed the team's thinking, what resources exist, what is currently true, what remains uncertain, and where the work is heading—without Brendon rebuilding that model by hand.

This document is the semantic center of that system.

The intended maintenance model is a **restartable Project Gardener role**, not a permanent Gardener agent. A suitable GPT reconciles bounded evidence into this Brain and leaves a checkpoint another GPT can resume. **A Gardener pass must be actually invoked and its output consumed.** Recording a #115 delta or detecting SHA drift is only intake; a named dispatcher/worker must begin a reconciliation pass, commit the supported semantic change or explicit no-change disposition, and advance the checkpoint only when the work is durable.

As of the 2026-10-08 approving merges, the coordination contract, this Project Brain, the Gardener checkpoint (`coordination/context_state.json`), and the context-status checker are on canonical `main`. They are not proposed or unmerged. dnd-solo #113 merged as `aba505351edf61df62445a4961090b4839435dc6`; stacked #117 merged as `ea74255559faa57dc2b044f01731f61e0f85079d`; paired bfdm-corpus #39 merged as `c18796a2e988d91353707b33377c8ea0e670974d`. Do not keep editing those coordination branches. A status-checker warning is not completion and does not accept a semantic delta. That merge wave started one Grok Automation Gardener pass per merged pull request, and those passes were not serialized: kit-gardener-on-merge (`ec1aff6e-c60a-4ee9-87a5-1ea4d7022cd6`) recorded successful runs `c6b15d24-3981-44a9-8486-4ff57393e22f` (after #113, started 2026-10-08T17:52:48Z), `7f376ca7-1fb2-490d-9645-0c2c34dffdb8` (after #117, started 2026-10-08T17:53:06Z), and `fbf0e7ba-903f-4fc7-9a41-a8458b40bfb4` (after #39, started 2026-10-08T17:53:10Z), with no gardener prompt pasted into any of them. Saying only that the #39 merge triggered the dispatcher is too narrow. The semantic result of the wave is the surviving Project Brain commit `86e4adefbcac04131f65c43b80ff33d9a923031d`, not every intermediate commit and not the checkpoint tip (for example `4228be7cccd66ee6c7509dedf57f5db54df6a0cd`, which only advances the cursor). GitHub stored no APPROVE review on #113, #117, or #39 because the author and the merging account are the same user; the approval record is Brendon's chat instruction plus those merge commits. Observed merge-triggered invocation is not proof the continuity system is operational. Issue #118 G4 (unbriefed cold start from default-branch entry) remains unmet. G5 remains unmet: invocation without a pasted prompt is not the full acceptance chain, which still requires a cold-start worker to use the corrected model. ChatGPT Project source membership remains a manual Project-UI change.

## 1.6 What changed our thinking recently

Several recent changes materially alter how a competent collaborator should reason about the project.

### Runtime maturity moved the bottleneck

The runtime generalized faster than older summaries reflected. Statements built around "Area 6c prototype" are now stale as project-level descriptions.

At the same time, generalized mechanics do not prove generalized excellent DMing. The project needs current human evidence.

### Retrieval stopped being the main BFDM problem

After merged archive-completion PR #40, the catalog has BCS-000001–BCS-000195 and the source index has 193 containers. The limited remaining archival gaps remain in the existing ledger; they do not license redoing the completed high-priority ingestion pass. PR #27 is separate Discord retrieval maintenance with merge conflicts.

Discord and source retrieval are usable enough that restarting the old Git LFS/searchability problem would waste effort.

The harder problem is now whether derived propositions actually reconstruct from their cited evidence at the confidence and scope claimed.

### The project separated source readiness from research trust

"Ready to research" does not mean "existing research is verified."

That distinction is now central to any attempt to turn BFDM findings into cognition, prompting, evaluation, or runtime behavior.

### Historical player-facing failures were reclassified

Some failures remain current and demonstrated. Others were mechanically addressed but not retested. Others are now stale.

This prevents both pessimistic carry-forward ("Kit is still broken in all the old ways") and unjustified optimism ("the fixes landed, therefore the experience is fixed").

### Project continuity became a product-support problem in its own right

Repeated GPT sessions could possess a great deal of information and still form the wrong project model.

The project now treats accumulated semantic understanding as durable state that must survive thread boundaries.

## 1.7 What we currently believe

These are current working conclusions, not eternal doctrine.

| Current belief | Confidence / basis |
| --- | --- |
| Kit is the product; total experienced play is the acceptance layer. | Settled project north star. |
| KRABS v0.2.2 on `dnd-solo/main` is the current canonical long-term reference architecture and behavioral specification for Kit. | Verified live repository authority; v0.1 is superseded, not KRABS itself. |
| `dnd-solo/main` is materially beyond the old Area 6c prototype. | Strong executable evidence. |
| Generalized runtime capability has not yet demonstrated generalized excellent DM play. | Strong; human evidence lags implementation. |
| The next major runtime-quality knowledge gain comes from sustained current-build play across ordinary boundaries. | Strong current evaluation conclusion. |
| BFDM source accessibility is substantially improved and is no longer the central research bottleneck. | Strong corpus-state evidence. |
| Derived BFDM research requires semantic verification before high-confidence downstream use. | Strong; active forensic audit already found reconstruction problems. |
| Heavy preparation in Brendon's work often functions as infrastructure/pressure rather than a script. | Strong recurring historical pattern, still subject to context and counterexamples. |
| Restraint, non-intervention, and what the DM declines to do are important BFDM evidence. | Strong research-direction conclusion. |
| No individual AI agent's context window can safely serve as project memory. | Strong operational conclusion from repeated project failures. |
| A fresh collaborator needs semantic continuity plus live authority, not one or the other. | Strong project-management conclusion. |
| A component, PR, index, evaluation, status signal, or handoff is not completed project value until its specified next consumer uses it and the intended result is observed. | Strong operational conclusion. The PR #40 delta is reconciled in this Brain; #113, #117, and BFDM #39 are merged. Unbriefed consumption and some runtime-deployment boundaries remain open. |

## 1.8 What we no longer treat as safe assumptions

Do not proceed from these older or tempting models:

- Area 6c is the architecture of Kit.
- A generalized room loader means source-to-room authoring is solved.
- Green tests demonstrate a good Dungeon Master.
- An old player-facing failure remains current merely because it once happened.
- A merged mechanical fix proves the player experience improved.
- BFDM material is trustworthy because it is polished, cited, or internally coherent.
- Searchability is the same thing as research verification.
- More cognition architecture is automatically the next useful step.
- A document's own "canonical" label outranks live repository authority.
- Nagatha, Skippy, Work, Grok Build, ordinary GPT, or any other single worker can be relied on as the whole project's persistent memory.
- A collection of context files is sufficient if a fresh GPT still has to reconstruct the actual project model from them.
- A posted semantic delta, green Gardener checker, passing unit suite, mergeable PR, generated packet, uploaded source, or prepared handoff demonstrates its downstream purpose was achieved.
- A task may be marked complete without identifying its real consumer, trigger/invocation, responsible actor, and observable acceptance result.

## 1.9 What remains uncertain

The most important unknowns are now relatively specific.

### Current DM-quality ceiling

We do not yet know how good current Kit actually feels over sustained ordinary play after the large wave of runtime repairs and generalization.

### Remaining expression gap

Historical evidence suggests that useful private machinery can fail to survive into player-facing performance. We do not yet know the present size or dominant cause of that gap on current main.

### Generalization beyond the richest testbed

The runtime is generalized more broadly than Area 6c, but current high-quality evidence across varied real adventure situations remains thin.

### BFDM trust depth

We do not yet know how much existing derived research will survive semantic forensic verification unchanged, narrowed, or downgraded.

### What minimal cognition is actually necessary

The project has hypotheses about precedent, recognition, retrieval, inhibition, attention, and longer-horizon judgment. It does not yet have evidence that a large cognition architecture is required to get the next major quality gain.

### Semantic continuity reliability

The Project Brain/Gardener design is intended to end repeated manual re-briefing. It is not proven until a bounded Gardener pass is invoked after a real change, reconciles the new evidence into durable Brain/control state, and a genuinely fresh GPT recovers the corrected model without Brendon prompting the pass or reconstructing the context. Structural status checks alone do not establish that loop.

## 1.10 What we are trying to learn next

The project should prioritize questions that reduce these uncertainties.

**Runtime / player experience:**  
What does current Kit actually do in sustained non-6c play once known blockers are removed, merged, or explicitly avoided?

**BFDM:**  
Which high-leverage derived claims survive semantic source verification, and which need narrowing, correction, or rejection?

**Judgment research:**  
What do failure/correction trajectories, restraint cases, and contrast families actually reveal about the recognition and judgment Kit needs?

**Cognition:**  
How much improvement can be achieved with trusted precedent and minimal recognition/retrieval mechanisms before heavier architecture is justified?

**Project continuity:**  
Does a material merge or semantic delta actually cause a suitable Gardener to run, reconcile and commit the updated model, and leave a checkpoint a fresh GPT can use without prompting from Brendon? Can the fresh GPT then reason correctly from the result?

## 1.11 Likely next moves

These are current directional expectations, not commitments.

- **Finish Gardener consumption closeout** (dnd-solo issue #118): PR #40 and the premature-completion correction are already in this Brain, and #113, #117, and BFDM #39 are on main. What remains is an unbriefed cold start from the default-branch entry and a second change handled without a person delivering the prompt. A checker warning, one receipt, or the checkpoint tip is not that closeout. The merge wave already started one unsynchronized pass per merged pull request; the surviving brain commit, not the main tip, is the semantic result.
- Reconcile the runtime PR stack into a combined build, ensure that build actually reaches the mounted Kit, and generate fresh sustained human play evidence beyond Area 6c.
- Finish BFDM PR #27's Discord retrieval conflicts as a separate engineering task. Preserve missing revision, Rowing Oak image, Bodfish Site, Project-history, and known-source gaps as capability-dependent archive work, not grounds to repeat merged PR #40.
- Prioritize forensic semantic verification in BFDM PR #38; then adversarially test PR #28's hypothesis families against independent Earthfall/Saturday evidence, respecting prep-versus-play distinctions.
- Only use verified research to shape later bounded Stage 3 cognition/precedent experiments; keep larger Stage 4 architecture deferred.
- For each substantial task, verify the full chain from output to named consumer, invocation, real use, and acceptance evidence. Do not mark an intermediary as the end result.

## 1.12 Decision horizon

Most current work should not require Brendon to perform repository archaeology or routine coordination.

The questions that genuinely belong with Brendon are the ones involving product judgment or authority, including:

- whether current player experience is actually good enough;
- whether a proposed behavior feels like Kit and serves the game;
- disputed creative or product priorities;
- meaningful tradeoffs between different desirable experiences;
- whether a research interpretation captures his actual judgment when evidence remains ambiguous;
- merge/authority decisions that have not been delegated;
- when the evidence is strong enough to move from experimentation into a more committed architecture.

The system should bring those decisions to him **with the relevant project model already assembled**.

It should not bring him the job of remembering the project.

---


# 2. Authority model

The project has repeatedly suffered when polished or old artifacts were mistaken for current truth. Keep these layers separate.

## 2.1 Current executable truth

`radarsaint/dnd-solo/main` is authoritative for what the current runtime actually does.

Code and current tests answer implementation questions. They do **not** by themselves prove that play is entertaining, coherent, satisfying, or better than earlier builds.

## 2.2 Current corpus/source/research truth

`radarsaint/bfdm-corpus/main` is authoritative for what source material, registries, evidence records, retrieval layers, and merged research currently exist.

A source being present does not prove it was used live.

A source being searchable does not prove a research conclusion derived from it is correct.

A research artifact containing citations or message IDs does not prove semantic verification.

## 2.3 Player-experience truth

Human play, sustained current-build use, and direct player-facing evidence answer whether Kit is actually good to play with.

Passing tests, landed fixes, design documents, and private reasoning traces are proxies.

They can support confidence in a component. They cannot substitute for experienced outcomes.

## 2.4 Project-control truth

Current control docs, live GitHub state, and owning issues/PRs answer what work is active, proposed, merged, superseded, or historical.

Open PRs may contain newer and important work while remaining non-canonical.

## 2.5 Historical truth

Old ZIPs, old branches, historical boards, archived handoffs, old Project attachments, and superseded architecture docs are valuable for reconstructing history. They do not automatically describe current state.

---

# 3. The two primary repositories

## `radarsaint/dnd-solo`

This is the current executable Kit runtime and player-facing development surface.

Its job is to make live play possible: world state, room loading, hidden information, adjudication, persistence, NPC/campaign context, Kit's private decision step, player-facing performance, and the bridge through which a chat-hosted Kit runs a game.

At the 2026-10-07 audited `main @ e3a5e9908357441051df24dac8086d8d4c7f26f5`, the runtime is substantially beyond the old Area 6c prototype. It has a generalized room loader, one-pass and staged host paths, SQLite-backed state and event history, hidden-information projection, claims/knowers, agendas, attitudes, bounded combat and procedures, manifests, retry/idempotency support, table-talk handling, and a large mechanical test suite.

That does **not** mean generalized excellent DM play has been demonstrated.

Area 6c remains historically important because it has the richest authored/testing history. It is a testbed, not the architecture of Kit and not a sufficient model of all DM quality.

General room loading also does not equal general source-to-room authoring. A runtime that can mount a conforming room file is different from a system that can take untouched keyed adventure text and reliably produce the next excellent playable room.

## `radarsaint/bfdm-corpus`

This is the durable research archive of Brendon's D&D creative history and BFDM research program.

It is deliberately broader than a training dataset for Kit.

It contains or indexes:
- canonical human-readable source containers;
- context-only source material;
- Discord harvests;
- model-facing Discord projections and deterministic term routing;
- campaign/project/person/identity registries;
- attributable evidence;
- source/evidence relations;
- derived research;
- research state, methodology, audits, and evaluation material;
- recovered current-project workbench history.

The corpus exists so later research can reconstruct **what Brendon actually made, ran, changed, rejected, learned, and valued**, with provenance and uncertainty preserved.

As of BFDM `main` merge `dc0d558188c3e492f69c34a8e278e0cf9e17373b` on 2026-10-08, the catalog contains **195 BCS records through BCS-000195**, with **193 indexed source containers**; BCS-000059 is context-only and BCS-000068 is an excerpt. The PR #40 admission and index repairs do not establish live use, historical revision completeness, or semantic verification of derived research.

---

# 4. The BFDM corpus is not one kind of evidence

Fresh collaborators should not flatten the archive into "Brendon's rules for DMing."

The corpus contains several materially different things.

## 4.1 Prepared campaign material

Schedules, encounters, maps, factions, systems, player guides, NPCs, mechanics, world lore, handoffs, public announcements, modules, props, economy rules, event plans, and campaign production documents.

These show intended design and available preparation.

They do not prove what happened live.

## 4.2 Live-play records

Discord harvests and other direct records show delivered play, player reactions, operational decisions, improvisation, corrections, staff discussion, actual consequences, and what persisted.

These are especially important when research asks what Brendon did **after players stopped behaving like the prep expected**.

## 4.3 Retrospective and workbench material

Later notes and recovered 2026 Project conversations show Brendon explaining, correcting, rejecting, and revising design in real time.

This material is unusually useful for distinguishing:
- what looked acceptable to an AI but was wrong;
- what Brendon considered too abstract, too authored, too "vibe"-driven, too verbose, or insufficiently playable;
- what constraints he expected an assistant to preserve.

Assistant-generated text inside those transcripts is not automatically Brendon-authored truth. The most useful evidence is often the sequence of user acceptance, correction, rejection, narrowing, or redirection.

## 4.4 Derived BFDM research

Decision cases, longitudinal cases, contrast families, source-fragment maps, synthesis papers, and other analysis attempt to turn historical material into reusable judgment.

These are research artifacts.

They may be excellent. They may also contain incorrect locators, unsupported scope, overgeneralization, or plausible interpretation that the primary evidence does not fully support.

Derived research must retain its trust status.

---

# 5. Retrieval state

The old problem where Discord content existed only behind Git LFS pointers and was therefore practically opaque to model-facing GitHub retrieval has been substantially addressed.

Canonical Discord SQLite remains source truth.

The corpus also contains non-LFS model-facing JSONL projections, manifests, deterministic term-routing indexes, and attachment metadata to make the archives usable by models and research agents.

Important rule:

> Retrieval solved enough to use is not the same thing as research verified enough to trust.

GitHub code search is not exhaustive. A zero code-search result is not reliable absence evidence.

When the model-facing projection reports exhaustive coverage, a zero match can be meaningful. Otherwise, absence must remain uncertain.

Do not restart the entire Discord/LFS accessibility project as though this infrastructure does not exist.

---

# 6. Creative history: the major lines currently represented

This is an orientation map, not a complete bibliography.

## 6.1 The Rowing Oak / early Roanoke

The early material already establishes concerns that persist for years:
- campaign worlds continuing between conventional sessions;
- players holding jobs and civic roles;
- inventory, scarcity, and production mattering;
- players depending on other players;
- settlement government and laws being player-authored;
- real or semi-real time affecting play;
- the world operating as a place rather than a queue of encounters.

The early designs are rougher and often more simulation-heavy than later work. That roughness matters because later campaigns revise many of the same problems.

## 6.2 Roanoke Season 2

Season 2 contains an explicit guide to persistent remote play.

Discord is used as an augmented theater-of-the-mind environment with rooms functioning as places, timekeeping rules, asynchronous scenes, and persistent roleplay outside table sessions.

A major concern is **attention fairness**: verbose or fast typists should not erase slower players, and the pause-emoji procedure exists because giving people room to be heard is treated as part of successful play.

The campaign also contains player production/crafting systems, settlement development, secret societies, colonial politics, occult cosmology, cryptids, and large amounts of bespoke mechanical experimentation.

Later revisions matter as much as the original designs. Some early economic systems become evidence of what not to do when the system's actual effect on play differs from its intended social function.

## 6.3 Roanoke Season 3

Season 3 is a large scheduled production with multiple DMs, a multiweek calendar, voice events, persistent Discord play, major factions, a colony, politics, cryptids, occult history, bespoke encounters, and campaign-wide systems.

It is important not to misunderstand the presence of a detailed schedule as proof of a scripted campaign.

S3 also deliberately contains:
- invitationals;
- improv periods;
- player-created side material;
- unresolved pressures that can advance;
- late-campaign space left less authored so accumulated history can matter;
- co-DM passdowns and operational continuity tools.

This creates one of the central tensions in Brendon's design lineage:

> Heavy preparation provides pressure, infrastructure, characters, consequences, and things worth discovering. It does not pre-author the players' story.

The S3 Discord record is especially valuable for studying what happens when prepared material collides with actual party state, player energy, scheduling, emergent relationships, consent boundaries, and unexpected interests.

## 6.4 Empire City / Roanoke Season 4

Empire City pushes the persistent-world form further.

Historical, political, folkloric, and urban ideas are transformed into systems the players can interact with.

Examples include:
- borough-specific mechanics;
- revolutionary occupation and taxation expressed as mechanical/environmental pressure;
- a functioning stock-market layer;
- newspapers carrying world state, propaganda, economic information, jokes, clues, and player voice;
- player participation in institutions;
- persistent locations whose meaning changes through play;
- player-authored government and constitutional procedure;
- historical figures converted into fantasy actors while retaining recognizable historical hooks;
- cryptids and folklore integrated as encounter ecology and long-running threads.

Empire City is also rich in examples where live population, staffing, scheduling, player uptake, or production bandwidth forced design changes.

## 6.5 Season 5 / Legends

Season 5 moves the historical-fantasy project westward toward the Brown Bear Republic and Legend.

Its material includes player-facing web/site content, campaign rules, character creation, setting material, lifepaths, regional cultures, transport infrastructure, and a more formalized approach to onboarding and limiting option complexity.

It should be studied partly as a response to problems seen in earlier persistent campaigns rather than merely as "more Arcania."

## 6.6 Bastion / Redoubt

Bastion/Redoubt represents another design mode: institutions, public/private truth, civic procedure, investigation, requisition, bureaucracy, social systems, and locations with operational function.

It is useful evidence against reducing Brendon's work to encounter design or whimsical worldbuilding.

## 6.7 At War's End

At War's End contains a more literary and dramatic mode.

The material deals heavily in memory, identity, institutional violence, social hierarchy, bureaucracy, mortality, historical residue, and symbolic recurrence.

"Mirabelle — A Tragedy in Five Acts" is a strong example: an in-world work about quarantine, substitution, class, bureaucracy, dehumanization, remembered identity, and the difference between truth and what institutions accept as socially real.

This line of work matters because the BFDM archive is not only a catalog of DM procedures. It also contains authored dramatic and thematic craft.

## 6.8 Earthfall

Earthfall is a modern live-production mode built around a lethal spectacle show, R.O.D. as host/adjudication persona, a transformed Dungeon of the Mad Mage substrate, audience/sponsor pressure, corporate parody, achievements, loot boxes, live-feed pressure, and aggressively physical encounter design.

Its absurdity coexists with consequences and mass stakes.

Corporate brands, celebrity figures, grotesque jokes, sponsor mechanics, audience numbers, and dungeon threats are not separate comedy sketches; once admitted into the setting, they become causal parts of the world.

Recent Earthfall work also shows strong emphasis on:
- player-facing clarity;
- runnable encounter structure;
- physical arenas;
- stat blocks first;
- meaningful interactables;
- monster tactics;
- clues that exist in the environment;
- avoiding "vibe lists" masquerading as mechanics;
- adapting when an encounter lands poorly in actual play.

## 6.9 2026 Saturday D&D workbench

Recovered Project conversation segments are especially valuable because they preserve the **design conversation**, including rejected AI output.

Recurring corrections include:
- less "vibe writing," more WotC-style runnable material;
- do not assume the players said or learned something they did not;
- do not turn encounter preparation into a predetermined story;
- preserve the actual map and physical room;
- make clues and interactables concrete;
- keep NPC and monster behavior grounded in what they know and want;
- use DCs, actions, state, and terrain rather than atmospheric lists;
- respect the distinction between a DM-facing plan and player-facing narration.

This is contemporary evidence of Brendon's current working standards, but it remains context-sensitive. Do not retroactively declare all older work "wrong" because current preferences are sharper.

---

# 7. Recurring creative patterns visible in primary material

These are **observed patterns**, not immutable laws. They should be tested against counterexamples and chronology before being promoted into universal BFDM doctrine.

## 7.1 Build environments that create interaction

Systems often exist to make people need, notice, recruit, bargain with, protect, challenge, or depend on one another.

Economies, jobs, factions, institutions, titles, scarcity, civic structures, shared threats, and public information systems frequently have a social purpose.

A mechanically elaborate system that does not create useful play can be judged a failure even if it works exactly as designed.

## 7.2 Preparation is infrastructure and pressure, not a script

Brendon often prepares heavily.

That preparation can include calendars, major reveals, villains, physical sets, systems, encounters, event windows, consequences, and long-term through-lines.

The preparation is valuable because of what it lets the live game do.

When current party state, player attention, production capacity, or delivered history makes the prepared implementation wrong, the implementation can change while its useful function is preserved.

## 7.3 Player-created material can be promoted

Unexpected relationships, civic responsibility, jokes, theories, locations, institutions, and side interests can become major content when players invest in them and they generate usable consequences.

Promotion is not automatic.

Interest, feasibility, fairness, collaborator ownership, time, and campaign purpose still matter.

## 7.4 Restraint is part of DMing

The DM does not improve every scene by intervening more.

Some player-owned decisions should remain player-owned.

Some successful play should be left alone.

Some cool ideas should be declined.

Some hooks can fail.

Some consequences should remain.

A future Kit trained only on visible interventions would become overactive and overauthorial.

## 7.5 Abstract ideas become physical/playable

A recurring creative move is **literalization**.

Examples across campaigns include:
- town health becoming buildings and shared infrastructure;
- taxation becoming changing magical/mechanical deprivation;
- a city's social foundation becoming a magical cornerstone;
- newspapers becoming live world-state surfaces;
- government becoming a player-run procedure;
- audience attention and sponsorship becoming dungeon-facing systems;
- symbolic or historical ideas becoming items, places, offices, rules, or pressures.

The important pattern is not "turn every metaphor into a mechanic." It is the tendency to make ideas interactable.

## 7.6 Absurd premises retain causal seriousness

The work frequently combines grotesque comedy, historical jokes, puns, parody, celebrities, cryptids, and serious stakes.

Once something exists in the world, it is usually allowed to have consequences.

The joke does not excuse the setting from causality.

## 7.7 Failure is diagnosed by play function

A design can fail because it:
- excludes someone from meaningful participation;
- requires a path the game failed to provide;
- consumes time without enough value;
- produces social incentives opposite its intent;
- no longer fits live party state;
- cannot be delivered at current population scale;
- exceeds available DM bandwidth;
- hides danger badly;
- makes administration more painful than the reward is worth.

This makes failure/correction trajectories unusually important BFDM evidence.

## 7.8 Production operations are part of the craft

Schedules, passdowns, staff ownership, player-count limits, onboarding, announcements, continuity, shared state, deadlines, event advertising, handoff practices, and asynchronous moderation are not peripheral bureaucracy.

They are part of what made large persistent campaigns possible.

Any attempt to reconstruct "how Brendon DMs" while discarding production operations will miss a large portion of the actual expertise represented by the corpus.

---

# 8. Important developmental changes

Chronology matters.

Do not average the entire archive into a timeless personality profile.

Useful distinctions include:

- **persistent trait:** recurs across materially different eras and formats;
- **evolved practice:** the underlying concern persists but the implementation changes;
- **format adaptation:** useful because of a particular player count, platform, or campaign structure;
- **abandoned practice:** later work gives evidence the earlier method was rejected;
- **unresolved contradiction:** both versions exist and the reason for change is not yet established.

Examples of likely evolution include:
- early heavy simulation becoming more selective about which procedures earn their cost;
- persistent-world social goals surviving while specific economies change;
- increasingly explicit protection of player agency and consent boundaries;
- increasing concern with runnable physical specificity in current encounter design;
- stronger intolerance for prose that sounds evocative but gives the DM little to adjudicate;
- more explicit separation between authored intent and player-owned outcome.

These are research leads unless the evidence chain has been verified across the relevant periods.

---

# 9. The current BFDM research direction

The current research program has deliberately moved away from prematurely specifying a giant cognitive architecture.

The working empirical sequence is:

1. **Make the history researchable.**
2. **Reconstruct expert judgment from decision trajectories, contrasts, failures, corrections, and restraint.**
3. **Build compact precedent representations and cheap experiments.**
4. **Test whether simple recognition/retrieval is sufficient before adding complex cognition machinery.**
5. **Let observed failures determine what architecture is actually required.**

A major methodological correction is:

> Stage 3 experiments should falsify cheap/simple approaches before Stage 4 commits to heavy cognitive architecture.

The research increasingly favors:
- decision trajectories over generic "principles";
- explicit disagreement/supersession relations;
- adversarial and negative cases;
- restraint cases;
- context-blindfold experiments;
- evidence of changed judgment across time;
- separation of fixed facts, hidden fixed facts, constrained unresolved state, and genuinely open state.

Do not resurrect an older architecture proposal merely because it is polished or ambitious.

---

# 10. Current research trust problem

The source substrate has improved faster than confidence in the derived research layer.

That distinction is central.

The corpus is now much more searchable and source-complete than it was.

At the same time, the active forensic integrity work exists because some derived research may look verified simply because it contains source locators.

The governing rule is:

> A research claim is source-verified only when the cited source content has actually been retrieved and shown to support the claim at the stated confidence and scope.

Current active integrity work should therefore be treated as a dependency for downstream attempts to turn BFDM findings into runtime doctrine or cognitive gold labels.

Unverified research can still be useful as:
- a lead;
- a hypothesis;
- a retrieval map;
- a candidate contrast;
- a prompt for adversarial checking.

It should not silently become "what Brendon believes."

---

# 11. What Kit is not

Avoid these false mental models.

## Kit is not Area 6c

Area 6c is a historically dense testbed.

Do not infer that its fake-vampire card room, its mechanics, or its interaction pattern define the architecture of good DMing.

## Kit is not the runtime

The runtime is one implementation surface.

A correct engine can still produce a bad DM experience.

## Kit is not the corpus

The corpus is historical evidence and research ancestry.

Kit should not mechanically imitate old campaigns or quote the corpus at players.

## Kit is not BFDM research

A correct research finding still has to be represented, recognized, retrieved, expressed, and used well in live play before Kit possesses the skill.

## Kit is not a personality prompt

Voice matters, but NPC behavior, adjudication, pacing, source truth, physical environment, relationships, campaign memory, challenge, restraint, and consequences all contribute to the experienced DM.

## Kit is not a giant prewritten story engine

Prepared campaigns can be highly authored.

Player action still creates the actual history.

## Kit is not validated by tests alone

Tests are essential for mechanical contracts and regression control.

The player-facing standard remains actual experienced play.

---

# 12. Current product-level quality model

The best current project statement is narrower than either "Kit is bad" or "Kit is basically solved."

The runtime has advanced rapidly.

Several serious historical defects have been mechanically addressed or materially changed.

Some current blockers remain demonstrable.

Human player-facing evidence has not kept pace with implementation.

Therefore:
- historical failures should not automatically be called current;
- intended fixes should not automatically be called successful;
- mechanically green behavior should not automatically be called fun;
- lack of recent failure evidence should not automatically be called quality.

Use explicit freshness categories from `COORDINATION.md` when making current behavioral claims.

---

# 13. Current project roles

Treat this section as coordination state, not permanent architecture. Verify current control/PRs before relying on it.

For the detailed identity/capability map—including the distinction between Nagatha, Skippy, Grok Bots, Grok Build, ordinary GPT/Grok, ChatGPT Work, temporary workers, repositories, and tool surfaces—use `coordination/AGENTS_AND_TOOLS.md`. Do not infer one named resource is interchangeable with another.

Current working division reflected in the October 7 coordination drafts:

- **Brendon:** product direction, high-value creative judgment, disputed requirements, and merge approval.
- **Nagatha:** PM/review/acceptance/reconciliation and merge coordination; helps keep Brendon out of routine implementation triage.
- **Skippy / Grok Bots:** primary runtime engineering, wiring, tests, PR stacking, and executable integration.
- **Grok Build / shell-capable agents:** executable reconnaissance, deterministic rebuild/test work, repository surgery.
- **GPT research/review workers:** bounded audits, evaluation, contradiction finding, synthesis, voice/taste/content research.
- **ChatGPT Work:** scarce autonomous multi-source research/evaluation where its capabilities materially outperform ordinary chat work.
- **Control/synthesis thread:** reconcile worker outputs against live repo truth and product goals.

A named current assignment outranks this default routing.

---

# 14. The most important active conceptual boundary

The project repeatedly needs to separate four questions:

1. **Does the machinery work?**
2. **Is the research claim trustworthy?**
3. **Can Kit actually express/use the capability?**
4. **Did the player experience improve?**

A "yes" to one does not entail a "yes" to the next.

This is the single most common category error in the project's recent history.

---

# 15. How a fresh chat should bootstrap

A fresh collaborator should not reread the entire corpus before doing anything.

Use this sequence:

1. Read this document once for the durable mental model.
2. Resolve live `main` SHA for each repo involved.
3. Read the relevant repo's `PROJECT_CONTROL.md`.
4. Read the issue/PR that owns the current task.
5. Retrieve only the primary sources, runtime code, tests, or research artifacts needed for that task.
6. If a derived BFDM claim matters, check its trust state and inspect primary evidence when required.
7. If a player-experience claim matters, check the build and evidence freshness.
8. Do not restart completed substrate work unless current evidence shows it is broken.

The purpose of this document is to make step 1 sufficient for orientation.

The purpose is **not** to let step 1 replace steps 2–7 when correctness depends on current state.

---

# 16. How this document should stay alive

This file should be **rewritten in place**, not grown into an append-only project diary.

Update it when a change would cause a competent fresh collaborator to form the wrong mental model if this file remained unchanged.

Examples:
- a major repository changes responsibility;
- an important research stage completes or is invalidated;
- a major campaign/source family is added to the corpus;
- the product goal materially changes;
- a recurring interpretation is disproven;
- a current proposed architecture becomes implemented fact;
- a historical assumption is superseded by strong new evidence;
- the authority hierarchy changes;
- a major creative lineage or developmental correction becomes clear.

Do **not** update it for:
- every merged bug fix;
- every new test;
- every ordinary research note;
- every temporary worker assignment;
- every minor PR.

Those belong in code, issues/PRs, `PROJECT_CONTROL.md`, research state, and git history.

When updating this file:
- preserve distinctions between verified fact, interpretation, hypothesis, and proposal;
- prefer primary evidence over derived summaries;
- preserve chronology;
- record important counterexamples;
- remove stale claims instead of layering contradictory prose underneath them;
- keep the document understandable to a fresh collaborator who has never seen the old chats.

---

# 17. Current known traps for future agents

- **KRABS itself is not historical.** Current `dnd-solo/main` carries **KRABS v0.2.2** as the canonical long-term Kit Reference Architecture & Behavioral Specification. The old Project attachment containing **KRABS v0.1** is stale only because that version was superseded. Never compress this into "KRABS is old-era material."
- **Legacy ChatGPT Project attachments do not outrank live GitHub.** Ignore these filenames as current sources even if a chat still has them mounted: `Design player facing UX UI.txt`; `Project overview.txt`; both copies of `Kit Runtime Setup.txt`; `Mad Mage Attached.txt`; both copies of `BFDM Corpus Research.txt`; `Corpus State Chat.txt`; both copies of `Corpus Understanding Assessment.txt`. The router and the verified homes are `docs/KIT_PROJECT_START_HERE.md`. That router is not a second Project Brain. The generalized Restartable Role Runtime in the later assessment is not current architecture.
- Old pinned ZIPs reproduce old builds only.
- Open PRs can be important and newer without being merged truth.
- `dnd-solo` contains historical BFDM mirror material that should not outrank the canonical `bfdm-corpus`.
- Area 6c's density can make it appear more architecturally central than it is.
- Discord searchability can create false confidence in zero-match searches if coverage is not checked.
- Derived research can look more certain than the primary evidence warrants.
- 2026 workbench transcripts contain both Brendon turns and AI-generated turns; do not attribute the assistant's inventions to Brendon merely because they appear in a canonical source container.
- A source document may show intent but not delivered play.
- A live message may show a local decision but not a universal preference.
- A later correction does not automatically prove every earlier instance was wrong.
- A successful technical component does not establish a successful Kit experience.

---

# 18. Working understanding of Brendon's design practice

This is intentionally phrased as a **working model**, not doctrine.

Across the primary material read so far, Brendon appears to care unusually strongly about building worlds that **produce behavior** rather than merely describing settings.

He prepares extensively, but much of that preparation establishes:
- pressures;
- institutions;
- characters with wants;
- physical places;
- public information;
- resource constraints;
- opportunities;
- consequences;
- things players can take ownership of.

He tends to value player-authored history enough to mutate expensive preparation when live play creates something better or makes the original implementation invalid.

He is willing to use absurdity, parody, grotesquerie, historical remixing, and spectacle, while still demanding that the resulting world behave causally.

He repeatedly treats social and operational design as part of game design.

His modern work shows increasing impatience with material that is evocative but not runnable, with AI assumptions that quietly alter established state, and with designs that predetermine the player's story instead of presenting a situation with usable affordances.

He also repeatedly diagnoses failure by asking what a design **did to the game** rather than whether the design was technically executed as written.

These observations are strong enough to orient research.

They are not yet a license to turn them into universal rules without checking chronology, context, counterexamples, and the active integrity state of any supporting derived research.

---

# 19. The long-term research/product question

The deepest project question is not:

> How do we make an AI imitate Brendon's prose?

It is closer to:

> How do we build a persistent Dungeon Master who can recognize what kind of situation she is in, know what matters, retrieve useful precedent without becoming formulaic, respect source and world truth, understand players and characters over time, make strong local judgments, preserve long-horizon campaign value, express those judgments entertainingly, and learn from actual outcomes without turning every historical pattern into doctrine?

The BFDM corpus exists because a large portion of the evidence needed to answer that question already exists in years of actual creative work.

The runtime exists because insight that cannot survive contact with live play is not enough.

The research program exists to connect the two without confusing evidence, hypothesis, implementation, and outcome.

---

# 20. Maintenance note

This document should remain the project's **durable mental-model layer**.

It should sit between:
- short current-state control documents, which change frequently; and
- the underlying repositories/corpus, which contain far more detail than a fresh collaborator should have to ingest for orientation.

If a future agent needs to ask "what is this project really?" or "what is actually in the corpus?" before every substantial task, this document has failed and should be improved.
