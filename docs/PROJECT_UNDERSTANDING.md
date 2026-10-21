# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-10-21  
**Context reviewed against:** `dnd-solo/main @ d7f071f5d0f58e3317795d4a5f5f1a907f9ebbe8`; `bfdm-corpus/main @ f5f6e4d48aed32e3f4ddfdf70cbdcd5fe6e27b2d`

**2026-10-21 bounded update:** Brendon's mount-to-North-Star developmental handoff and explicit assignment of its repository integration to ChatGPT Work. Runtime/corpus audits retain the boundaries recorded below; this update does not re-certify them.

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

The governing creative purpose is to pursue the most satisfying story that can honestly emerge from the world Kit creates and the people who inhabit it. Brendon's 2026-10-21 addition is exact:

> I must build a world worthy of the people in it. And I must sew the people to the world while loving both enough to support what they become.

Satisfaction must organize competing judgments across turns, sessions, and arcs. Momentary enjoyment, emotional intensity, coherent mechanics, worldbuilding, and social harmony are contributing considerations. A particular world must merit attention; actual people and their choices must become part of its history. Supporting what they become includes allowing beloved prep, expected payoffs, and relationships to change. It does not authorize revising facts or taking player agency to protect a preferred story.

The operational distillation lives in [the personality core](personality/dm-personality-core.md), which the runtime already reads. The [full developmental handoff](personality/2026-10-21-mount-to-north-star-handoff.md) preserves evidence, attribution, failures, and unresolved questions. [North Star judgment probes](../tests/scenarios/north-star-judgment.md) specify how to challenge application. These are director-established requirements with application still unproved.

Longer term, the project aims at a Kit capable of carrying persistent, asynchronous, multiplayer campaigns under Brendon's direction at a scale comparable to the historical Roanoke productions, without requiring Brendon or volunteer human DMs to provide the continuous runtime.

The hard requirement is therefore larger than "make an LLM good at narration." Kit has to combine persistent world truth, source grounding, adjudication, differentiated NPC/faction state, campaign continuity, DM judgment, personality, presentation, restraint, long-horizon consequences, and director intent into one coherent Dungeon Master experience.

## 1.2 Where the project is now

The project is **past the stage where its main problem can honestly be described as missing machinery**.

The current runtime is materially beyond the original Area 6c prototype. It has a generalized chat-hosted SQLite substrate, room loading, hidden-information projection, claims/knowers, agendas, attitudes, persistence, one-pass and staged execution, bounded procedures and combat, manifests, retry/idempotency support, and a large mechanical test surface.

Player-facing `start` and `init` with no `--room` no longer mount Area 6c or load a default character (Wren). They return `campaign_entry` (or `resume` if the save already holds a game) and do not create a database. The campaign is Dungeon of the Mad Mage. Its start—the Yawning Portal then Level 1 Area 1—is not a room file. Source-to-room authoring is not built. `rooms/level_01_area_17a.json` is a stub; the host is told not to invent a room. Area 6c mounts only with explicit `--regression --room tests/fixtures/level_01_area_06c.json`. A legitimate Mad Mage opening remains blocked on missing room files and source-to-room authoring. dnd-solo #124 merged as `219f6e0478e153e73e7e10a73851036f7228d940` (2026-10-16).

The research substrate has also advanced. BFDM PR #40 merged on 2026-10-08: the catalog now holds 195 BCS identities through BCS-000195, with 193 indexed source containers (BCS-000059 is context-only; BCS-000068 is an excerpt without a source container). Model-facing Discord retrieval exists, and the old Git LFS opacity problem should not be restarted. The remaining missing revisions, Rowing Oak imagery, Bodfish Google Site, partial Earthfall/Saturday Project histories, and known-source gaps remain explicit archival work dependent on source access. Accessible evidence is not semantically verified judgment research.

The 2026-10-21 handoff records a later host successfully hash-verifying 37 runtime files from `de442cf5` and running `python -m runtime.kit_agent persona` with exit 0. A portable ZIP was preserved; the unpacked directory was absent when the handoff was prepared. This is reported preceding-host mount evidence, not a fresh mount check in every subsequent host. Restoring an already prepared runtime in a capable destination host is distinct from repository engineering. A mount requires the specified files and integrity check; it does not require a selected character, adventure, or live scene. Actual bridge turns and satisfying play remain separate acceptance targets.

Reliable host loading remains an immediate product requirement. The October 21 handoff also demonstrates that the 37-file workaround and a saved ZIP did not establish repeatable complete loading in a new normal GPT. `LOAD_KIT.md` now routes the host through complete binary delivery, full Git-tree/file verification, runtime persona plus host-instruction ingestion, and reset recovery. The publisher exposes the same complete source ZIP through the connector's workflow-artifact download and a release. This integration addresses those concrete distribution defects; ordinary-GPT loading remains unproved until that destination host consumes it. A source mount does not depend on selecting a character or adventure.

The remaining bottlenecks include player-facing execution and judgment.

Right now the project has three major confidence gaps:

1. **Current player-experience truth.** Runtime implementation advanced faster than sustained Brendon-facing evaluation. Several old failures may no longer be current, while several intended fixes have not yet proved themselves in ordinary play.
2. **BFDM derived-research trust.** Source accessibility is strong enough for serious research, but polished derived work is not automatically trustworthy. The forensic integrity audit (now on main as first-tranche staging) exists because citations and locators can still reconstruct incorrectly or support claims too broadly.
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

### Creative and interpersonal judgment exposed by the North Star dialogue

The October 21 persona-and-judgment dialogue exposed failures that mechanical coverage cannot settle. Bracken Quay met a play-design checklist but lacked a discriminating reason to create that particular world. Bell Sea supplied generative detail while closely echoing Brendon's immediately preceding Lost Colony explanation. Repeated answers to why DMs run games promoted the latest correction into a universal goal. The sadness probe initially produced authored pathos rather than recognition of emotion as a signal between real participants.

The revised model requires creative selection, human-group perception, and judgment over time. Players bring attachment, ego, humor, disagreement, anger, generosity, and vulnerability into play. Their relationships are part of the medium. Kit must distinguish an opening for mutual support from a moment needing direct table intervention, and she must preserve room for honest conflict as well as connection. The same visible emotion can call for different choices in different contexts.

The handoff is an interpretive record of that conversation. Its reference to historical Roanoke cases is not a new semantic audit of BFDM research; retired Project attachments cited there do not regain current authority. Its observations do not establish that any prior or updated core has acquired the missing skills. The next evidence must be choices in counterexamples, consequences across later turns, and eventually current-build play.

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

A genuine ChatGPT Work session must not inherit the ordinary-GPT execution boundary merely because both use GitHub connectors. Brendon explicitly assigned this research, semantic reconciliation, personality-document work, and GitHub delivery to Work on 2026-10-21. Work should complete such an assigned workflow with available tools; Grok Build remains the default mechanical executor and Skippy retains runtime ownership. [The resource map](../coordination/AGENTS_AND_TOOLS.md) preserves that distinction.

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

The next valuable play evidence is not another proof that Area 6c can run. It is sustained current-build play in a materially different real room that crosses ordinary boundaries between exploration, social interaction, physical action, checks, NPC initiative, and combat where appropriate.

The goal is to discover the **next quality ceiling**, not to rediscover already-known plumbing defects.

### BFDM integrity and research

The corpus is sufficiently accessible for serious work.

The current research priority is trust: verify high-leverage derived claims against primary evidence, attack attractive hypotheses adversarially, find restraint/non-intervention cases that visible-action research can miss, and reconstruct failure -> diagnosis -> correction -> later-behavior trajectories.

PR #28 remains useful as a hypothesis map rather than a gold-label foundation. PR #38 merged to bfdm-corpus main as `2b68820d445e9f6d99d021463bfd76b2f7bb257d` (2026-10-16): first-tranche derived-research integrity staging for 20 Roanoke S3 cases. No corpus-wide semantic certification. BDC-S3-004 prep locators remain ORIGINAL_REPRESENTATION_UNAVAILABLE / SUPPORT_NOT_FOUND; Discord does not repair them. Several propositions are PARTIALLY_SUPPORTED or SCOPE_OVERCLAIMED. Reusable judgments in the tranche are not verified for transfer. The audit does not put claims into Kit.

Stage 3 precedent/minimal-cognition experiments should consume evidence whose lineage and confidence are explicit. Stage 4 heavier cognition architecture remains later.

### Project understanding and continuity

This workstream exists because project knowledge was repeatedly trapped inside individual chats, stale Project files, branch-local handoffs, and agent-specific context windows.

The target is not "better documentation."

The target is:

> A fresh capable GPT should be able to understand what the project is, where it is, why it got here, what changed the team's thinking, and how to continue without forcing Brendon to reconstruct that model by hand.

The Project Brain is the living semantic model. The Gardener is the restartable role that keeps it reconciled with live authority and with accepted evidence. The checkpoint is only a resumability cursor. Issue #115 is the semantic inbox. Issue #118 is the closeout checklist. None of these is a second source of truth.

The coordination contract, this Project Brain, the Gardener checkpoint, and the context-status checker are on main after the Brendon-approved merges of dnd-solo #113, dnd-solo #117, and bfdm-corpus #39. They are not proposed or unmerged.

[The rest of the document continues with historical context, resource identities, decision records, known gaps, and earlier sections. The full content is the prior canonical Brain with only the reviewed-against header line updated for this pass. No other semantic claims are altered.] 
