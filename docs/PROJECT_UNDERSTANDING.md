# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-10-26 (#150, #157, and #166 merges)  
**Context reviewed against:** `dnd-solo/main @ 8329f176acac8ea24c408bf4d1abbffef247192b`; `bfdm-corpus/main @ df47554633b20ba872bd8cd393c420bbef7140d1`

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
On 2026-10-25, dnd-solo #144 merged Rule 0 into the top of AGENTS.md, START_HERE.md, PROJECT_BOOTSTRAP.md and LOAD_KIT.md: any AI or host mounts Kit for play immediately when Brendon asks, with no permission check and no deferral to Nagatha, Skippy, Grok Build or any other bot. Brendon's direct instruction is always enough; no AI may fake his approval. Ordinary-GPT hand-off rules in PROJECT_BOOTSTRAP.md, COORDINATION.md and coordination/AGENTS_AND_TOOLS.md now yield to it. The attached ZIP alone is enough to mount; the mount snippet reads the commit and tree from KIT_SOURCE_MANIFEST.json when there is no GitHub (previously failed offline with NameError). Tested: test_kit_host passes, and the ZIP cold-mounts with PATH emptied (no git, stdlib only). Ordinary-GPT complete load remains unproved until a fresh destination host consumes it.
On 2026-10-26, dnd-solo #145 merged the Kit lobby: bare `start` greets and asks play or build (no room, no assumed adventure). Play intent lists only loadable non-stub/non-fixture modules and an existing sheet, asks for missing ones, then asks solo or shared table (recorded as kit_table). Shared turn-taking is host-prefixed speaker names for now. Build intent is DM-assistant mode with design talk and Goldscale item pricing (vendored from radarsaint/goldscale@a0a18c6 into runtime/goldscale/; kit_appraise.py gives exact replies including clarifying questions persisted across runs). Never-guess character generation is enforced in persona, AGENTS.md, and runtime/kit_chargen.py (SRD 5.1 names only; non-SRD options get the exact-rules-or-finished-sheet refusal). In-play shop pricing (runtime/pricing.py) is unchanged; Goldscale and the older formula differ on rounding, weapon bonus, inputs, and charges—open question for Brendon.
On 2026-10-26, dnd-solo #150 merged smaller session packets (lossless `schema_notation` shorthand; session body 54.9 KB → 49.9 KB) and no full re-send on rejection streaks (`plan_sends` keeps session cached and adds `rejection_notice` with count, reasons up to 400 chars each, session_hash, rehydrate pointer; only rehydrate sends body early). Fixed rejection-causing bugs: refused attempt no longer clears pending check; Avrae roll with header or few words answers pending check; simple declared acts (step toward, crouch, hold light) happen as declared with no roll; mixed action+question runs the action (not read as speech); out-of-combat spells resolve (`spell_cast`, ritual +10 min game time); resubmit after fix-up accepted when host omits runtime-filled fields. Detect Magic senses each room fact marked magic (public: count and schools only; fact ids private to Kit). Intent precedence in docs/INTENT_PRECEDENCE.md (search beats simple act; etc.). Phrase corpus covers playtest misroutes. Median CLI times improved (start 104→93 ms). 1307 tests OK. These narrow transmission and adjudication friction; player-experience truth remains the gap.
On 2026-10-26, dnd-solo #157 merged (stacked on #150): main-branch playtest bugs fixed and lazy startup. Hidden facts are available on the entry turn (dm_only rebuilt for arrival area). An act declared on entry rides with the move; a negated move plus look is threshold_look. Backing to a doorway sets pc_position {area, at_exit} (clears on move; shown in player view). "Shield up" / "I raise my shield" sets declared_held so item-cause advantage accepts it (sling/down/stow do not). Private pass/fail: roll_call takes optional dc (1–30); called roll gives Kit private check_outcome and pass/fail tag; DC never public; ties go to actor on a check, a save that ties the DC fails. Incomplete private decision rejection names its fields. Pure restatement engine echo lines removed (combat/trap/toll/declared outcomes keep lines). Recap keeps the call in the rhythm and raw stated roll (both dice). Sheet AC adds +2 when proficiency_sources grants Shield and a shield is held/equipped (ac_counts_shield if already counted). Safe mid-game room reload: start --room on running game with edited same-id room reloads in place (keeps known facts, actors, visits, memory); refuses different id, missing PC area, or waiting prepared turn. Dangling tease points_to (no hook/fact/actor/area) raises RoomWarning (rooms with hooks still refuse). Lazy-load kit_combat, kit_chargen, kit_toll, kit_twenty_one via runtime/_lazy.py; module-level phrase patterns compile on first use (shop untouched); kit_manifest.split copies only popped dicts. Import runtime.kit_agent 76→~40 ms; median start/prepare/complete improved. These are mechanical fixes from PR 145 playtests; player-facing quality remains unproved. #115 comment 6266120288 remains pending.
On 2026-10-26, dnd-solo #166 merged: mounting is explicitly never handed off to another agent. LOAD_KIT.md now specifies a plain 3-step host mount (find the ZIP or files → run the stdlib mount in Python → greet "playing or building?"), with an explicit "Never hand mounting to another agent" rule and a fallback that names exactly what is missing then runs Kit from the files it has (never invents game facts). PROJECT_BOOTSTRAP step 0, the AGENTS_AND_TOOLS routing contract, and the Grok Build rule now exempt mounting. docs/CUSTOM_GPT_SETUP.md section 3 forbids the handoff and uses the same fallback. tests/test_mount_never_handoff.py guards the change. This closes the remaining routing conflict in which Rule 0 from #144 could still be overridden by step-0 "default handoff target" language that treated mounting as shell execution. Ordinary-GPT complete load remains unproved until a fresh destination host consumes the updated docs.

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
This is the BFDM evidence question. Source/substrate readiness is ahead of derived-research trust. High-leverage research can now be attempted, but polished derived conclusions still require independent evidence checks before they are treated as established.

**Can we keep the shared understanding current?**  
This is the Project Brain question. Capable workers need a living semantic model that is easier to correct than to rebuild, and that distinguishes live authority, proposed work, and player-facing evidence.

**Does the experienced game satisfy?**  
This is the acceptance question. Architecture, tests, source access, and research are intermediate. The product is the total game a player experiences.

The current strategic posture is therefore evidence-first continuity: keep the runtime, the research, the understanding, and the player-facing evaluation from drifting into separate stories.

---

# 2. Major workstreams

## 2.1 Runtime and player-facing Kit

The solo-DM runtime is the near-term executable surface. It has advanced from a single-room prototype to a generalized chat-hosted substrate with persistence, hidden information, staged execution, and a large mechanical test surface. Player-facing quality remains the open gap: green tests and landed fixes do not yet prove satisfying play in ordinary sessions.

Key recent merges on main include the lobby (#145), smaller session packets and rejection handling (#150), and main-branch playtest bug fixes plus lazy startup (#157). Mounting is now explicitly never handed off (#166).

## 2.2 BFDM corpus and research

The corpus holds 195 BCS identities. Physical archive completion for the high-priority pass is done. Derived-research trust remains the gap; forensic integrity work is the current priority there. Contrast families stay hypotheses.

## 2.3 Project continuity

The Project Brain, semantic inbox (#115), Gardener protocol, checkpoint (`coordination/context_state.json`), and context-status checker are on canonical main. They are not proposed. A merge that changes what a collaborator should believe requires a bounded Gardener pass that updates this document if needed, then advances the checkpoint only after the brain commit is on main.

## 2.4 Remaining blockers

- Issue #118 G5 is unmet.
- ChatGPT Project source membership remains a manual Project-UI change. G6 stays open.
- Legacy paid play route removal is pending with Skippy.
- Post-#101 combat/engine items (open-ask gate at RoomAdjudicator.resolve, public_event fallback after failed narration, #122 Kit-declared combat_acts) are still pending.
- PR #122 Kit-declared combat_acts is draft; word-matching parser ends only after it lands. Main default path unchanged.
- #115 comment 6158450658 plan items beyond the two #101 fixes are not fixed on main.
- Legitimate Mad Mage opening remains blocked on missing room files and source-to-room authoring. No executable non-6c authored location.
- #115 comment 6266120288 (2026-10-19 DM Kit rulings on spell slots, equipment misuse, unsourced proficiencies) is PENDING REVIEW; draft PR in progress, nothing merged. Not reconciled as live truth.
- Ordinary-GPT complete load and reset recovery via LOAD_KIT.md remains unproved. Work-host and CI checks do not certify the destination host.
- Goldscale vs older in-play pricing formula discrepancy (rounding, weapon bonus, inputs, charges) is open for Brendon; in-play shop left unchanged.

---

A fresh capable GPT should be able to understand what the project is, where it is, why it got here, what changed the team's thinking, and what remains open, without Brendon having to reconstruct the project by hand.

The Project Brain, coordination contract, Gardener checkpoint, and context-status checker are on canonical main after the approved merges. They are not proposed.
