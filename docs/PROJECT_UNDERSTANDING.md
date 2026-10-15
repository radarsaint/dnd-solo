# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-10-15  
**Context reviewed against:** `dnd-solo/main @ 5c0b133fcd5e9d5049fbb05e0b57a66f4132ebdf`; `bfdm-corpus/main @ 6795362e967e89230086afc28c04450cc7d0cce4`

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

The project is building **Kitiara ("Kit", "DM Kit")**, a persistent AI Dungeon Master and creative partner. Dungeon Master is her principal vocation, not her only job. Conversation, debrief, and creative work do not require a running game, and she does not open a game unless the player names one. Dungeon of the Mad Mage is one campaign she can be asked to run. Area 6c is not a silent start. That is current product intent. It is not yet what executable `main` does.

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

The current runtime is materially beyond the original Area 6c prototype. It has a generalized chat-hosted SQLite substrate, room loading, hidden-information projection, claims/knowers, agendas, attitudes, persistence, one-pass and staged execution, bounded procedures and combat, manifests, retry/idempotency support, and a large mechanical test surface. On `main` at `5c0b133f`, `start` with no room still loads `tests/fixtures/level_01_area_06c.json`. Treating Area 6c as a historical testbed does not mean the player-facing command has stopped mounting it.

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
- incomplete combat transitions and related state handling (#97 monster-initiated combat and #101 combat checkpoints landed);
- validator functional floors rewarding length over functional completeness (#102);
- at least one deliberate social-omission recognition gap (#73).

These are narrower than old blanket claims that combat, natural language, NPCs, or the whole runtime "do not work."

### Player-experience evaluation

This lane is now disproportionately important because implementation has outrun evidence.

The next valuable play evidence is not another proof that Area 6c can run. On current `main` the no-room start still opens that fixture. [PR #124](https://github.com/radarsaint/dnd-solo/pull/124) (`kit-campaign-entry` at `1ac91c55`) proposes a greeting that does not pick an adventure, and reports Dungeon of the Mad Mage only when the player asks for it. The pull request is open and unmerged. A fresh ChatGPT host has not consumed it. After that correction is on `main` and a host is actually using it, the evidence that matters is sustained play in a real room other than the fixture.

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

As of the 2026-10-08 approving merges, the coordination contract, this Project Brain, the Gardener checkpoint (`coordination/context_state.json`), and the context-status checker are on canonical `main`. They are not proposed or unmerged. dnd-solo #113 merged as `aba505351edf61df62445a4961090b4839435dc6`; stacked #117 merged as `ea74255559faa57dc2b044f01731f61e0f85079d`; paired bfdm-corpus #39 merged as `c18796a2e988d91353707b33377c8ea0e670974d`. Do not keep editing those coordination branches. A status-checker warning is not completion and does not accept a semantic delta. That merge wave started one Grok Automation Gardener pass per merged pull request, and those passes were not serialized: kit-gardener-on-merge (`ec1aff6e-c60a-4ee9-87a5-1ea4d7022cd6`) recorded successful runs `c6b15d24-3981-44a9-8486-4ff57393e22f` (after #113, started 2026-10-08T17:52:48Z), `7f376ca7-1fb2-490d-9645-0c2c34dffdb8` (after #117, started 2026-10-08T17:53:06Z), and `fbf0e7ba-903f-4fc7-9a41-a8458b40bfb4` (after #39, started 2026-10-08T17:53:10Z), with no gardener prompt pasted into any of them. Saying only that the #39 merge triggered the dispatcher is too narrow. The semantic result of the wave is the surviving Project Brain commit `86e4adefbcac04131f65c43b80ff33d9a923031d`, not every intermediate commit and not the checkpoint tip (for example `4228be7cccd66ee6c7509dedf57f5db54df6a0cd`, which only advances the cursor). GitHub stored no APPROVE review on #113, #117, or #39 because the author and the merging account are the same user; the approval record is Brendon's chat instruction plus those merge commits. Observed merge-triggered invocation is not proof the continuity system is operational. Issue #118 G4 and C2 are accepted from the unbriefed default-main cold start recorded in https://github.com/radarsaint/dnd-solo/issues/118#issuecomment-6068887374. That read consumed this Brain's canonical model, including the G0/G1 missing-consumer lesson. It did not consume the execution-history correction in this paragraph, so G5 remains open. The earlier G2 gap, live main `2cdcee1f` ahead of reviewed brain `e4e3431b`, is disposed as checkpoint-only: `2cdcee1f` advanced the cursor and did not change this Brain. dnd-solo #119 merged as `6d97381210454654950fcb339f438a5d432cc9f1` and recorded the G4/C2 acceptance already in this paragraph; it is not a new semantic model. dnd-solo #120 merged as `e12b97fc925b2be9281fd11828b0bb61a964452f` and landed that checker rule on main. A later commit is already reviewed when its tree matches the reviewed SHA or its only path change is `coordination/context_state.json`; an uninspected SHA difference stays undecided. On 2026-10-09 the checker on that main, against reviewed `cf3547e9c8c767a9085e9fbd477666a706381c79`, reported `REVIEWED_CURRENT` with disposition `CHECKPOINT_ONLY` for live `e12b97fc` (diff is only `coordination/context_state.json`) and `REVIEWED_CURRENT` for bfdm-corpus `54a2093838b69138eb72e513a4eb813d0717fd19`. Inbox cursor remained `6065921827`. That run is the G2 evidence. It does not accept G5, G6, or player-quality play. G6 remains open because ChatGPT Project source membership is still a manual Project-UI change. Accepted G4 is not complete end-to-end continuity and is not high-quality Kit play.

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

### Approved cleanup retired the in-repo corpus mirror

On 2026-10-13, #114 merged as `c9ce777729b77610944314b544cad709becbfe2d` and removed the obsolete in-repo BFDM mirror. There is no `corpus/` directory on `dnd-solo` main. `radarsaint/bfdm-corpus` is the only corpus. #121 merged as `a62bc0c70ead981f5175c632c71867d2fb2d91c4` and salvaged historical design notes, the Roanoke Discord exporter, and a 2026-09-28 playtest onto main; those files are repository history, not proof of player-facing quality. Superseded PRs #5, #11, #23, #36, #38, #43, #44 and issue #35 are closed. 87 stale branches were deleted. The legacy paid play route remains in `runtime/kit_agent.py` until Skippy removes it. Do not restart finished cleanup or treat the closed items as active direction.

### Monster-initiated combat landed via structured handles and sealed features

On 2026-10-13, #97 merged as `e94e9fdd53381a504d649386f8978674837da71d` (head `9ba408382698c2acaf3d72767e5e828c8f755e38`). Disturb triggers now fire only from Kit's structured `handles: {target, act}` declaration against the engine's offer; the noun regex is only a hint. A watched unfired feature is sealed: narration cannot reveal its interior/contents or claim it open/moved without a firing declaration. Hidden actors stay filtered until their trigger fires. Death and condition saves are player-rolled in Avrae and reported. Ties: the actor wins contests; a save that ties the DC fails (house rule). Pending rulings are structured and curtain-safe. Green tests do not prove player-facing quality. On 2026-10-14, #101 combat checkpoints landed on main via #123 (merge `5c251092101c0abecf86a0418304442e3407565b`, reviewed head `23b464f4faf799716bbc3805db53ea6562a45c1a` plus fixes in `f725c420ad8e02ff7809c724a406349f4fedf053`): reaction windows (Shield, Absorb Elements, Uncanny Dodge, Hellish Rebuke, Counterspell, Chronal Shift, late reactions, one per round), slot tracking/fizzle at Avrae `-l`, persistence and rest, OA window on flee, door second-move rule, window threshold max(¼ current HP, 5). `KIT_COMBAT_CLAUSES` stays off by default. A late reaction now pops only its own unprompted event; a leveled spell with no slot left fizzles, says so, and the action counts. Green tests do not prove player-facing quality.

## 2. Evidence and truth classes

### 2.1 Executable truth

Live `dnd-solo/main` plus the current runtime code answer what the machinery currently does.

`PROJECT_CONTROL.md` is the live orientation/control surface for that executable state. It is not a substitute for the semantic model in this document.

A pinned zip is a snapshot of one commit, not a newer source of truth than `main`. From `5c0b133f` on, a push to `main` is supposed to publish that commit as GitHub release `runtime-<8-char sha>`, asset `dnd-solo-main-<8-char sha>.zip`. For `5c0b133f` the workflow run succeeded and the asset is uploaded. Its download count was 0 at this review, so a published asset is not a host that mounted it. A `runtime-*` release whose target commit is not on `main` is not current Kit. The workflow did not backfill every older `main` commit. `runtime-5c251092` is an earlier ancestor snapshot that was uploaded separately, also with download count 0.

### 2.2 Corpus/source/research truth

Live `bfdm-corpus/main` plus that repo's control and research-status files answer what sources, indexes, and research claims currently exist.

A passing index or green validation suite is not semantic verification of derived research.

### 2.3 Player-experience truth

Current human/live evidence answers whether Kit is actually delivering a better Dungeon Master experience.

Test counts, architecture documents, and green suites do not answer this question.

### 2.4 Proposed work

Owning issues and PRs answer what is proposed or in progress. They are not current truth until merged to main.

### 2.5 Semantic model

This document answers what a competent collaborator should currently believe about the project, including where the evidence is strong, where it is weak, and what remains uncertain.

## 3. Current BFDM state

After PR #40, the catalog holds 195 BCS identities. The index has 193 source containers. BCS-000059 is context-only. BCS-000068 is an excerpt without a source container. Model-facing Discord retrieval exists. The old Git LFS opacity problem should not be restarted.

Accessible evidence is not semantically verified judgment research. The forensic integrity work exists because citations and locators can still reconstruct incorrectly or support claims too broadly.

## 4. Current known gaps and open questions

- Player-experience truth is the largest remaining confidence gap. Runtime and research have advanced faster than sustained current-build evaluation with Brendon.
- BFDM derived-research trust is the second gap. Source accessibility is strong; polished derived claims still need adversarial verification against primary evidence.
- Shared project understanding is the third gap. This Brain and the Gardener process exist to close it. A status-checker warning is not completion.
- Issue #118 G5 is unmet. The unbriefed cold start consumed the canonical model but not the execution-history correction.
- ChatGPT Project source membership remains a manual Project-UI change. G6 stays open.
- Legacy paid play route removal is pending with Skippy.
- PR #101 combat checkpoints reaction model is now on main via #123; remaining post-#101 combat/engine items (open-ask gate, public_event fallback, #122 Kit-declared acts) are still pending.
- A live playtest of an ambush (Area 17a or similar) and a downed PC is still owed. Green tests do not prove player-facing quality.
- Player-facing `start` on `main` still mounts Area 6c. PR #124's greeting, and Mad Mage only when asked, stay proposed until that pull request merges and a host actually uses the build.
- The `5c0b133f` runtime zip is uploaded and had not been downloaded at review. Publication is not consumption.

The rest of the original document continues with sections on historical context, resource identities, and earlier decision records. Those sections are unchanged by this reconciliation pass.
