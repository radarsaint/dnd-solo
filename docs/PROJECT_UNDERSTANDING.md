# Project Understanding — DM Kit / BFDM

**Purpose:** durable mental model for humans and AI collaborators  
**Status:** living orientation document, not executable or research authority  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-10-07

> This document exists so a fresh collaborator does not have to reconstruct the project from old chats, stale attachments, historical boards, scattered research papers, or repository archaeology before doing useful work.

It should explain **what the project is, what exists now, what the BFDM corpus actually contains, how the major creative lines fit together, what is known versus inferred, and which false mental models to avoid**.

It is deliberately not the final authority for changing facts.

For current executable state, use live `dnd-solo/main` plus `PROJECT_CONTROL.md`.  
For current corpus/source/research state, use live `bfdm-corpus/main` plus that repo's `PROJECT_CONTROL.md`.  
For proposed work, use the owning issue or PR.  
For player-facing quality, use current human/live evidence rather than architecture or test counts.

If this document conflicts with those current authorities, **this document is stale and must be corrected**.

---

# 1. The project in one paragraph

The project is building **Kitiara ("Kit", "DM Kit")**, an AI Dungeon Master and creative partner whose success is judged by the complete experience of playing and building D&D with her.

The near-term executable surface is a solo-DM runtime in `radarsaint/dnd-solo`. The deeper research program in `radarsaint/bfdm-corpus` preserves and studies Brendon's long history of campaign design, live Dungeon Master judgment, experimentation, failure, revision, and creative method.

The corpus is not the product. The runtime is not the product. The architecture is not the product. **Kit is the product. The total experienced game is the acceptance layer.**

Longer term, the ambition includes a Kit capable of carrying persistent, asynchronous, multi-player campaigns under Brendon's direction at a scale comparable to the historical Roanoke productions, without requiring Brendon or volunteer human DMs to function as the continuous runtime.

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

As of the current merged corpus state inspected on 2026-10-07, canonical source containers run through **BCS-000172**.

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

- The old Project attachment containing **KRABS v0.1** calls itself canonical but is stale relative to live repo authority.
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
