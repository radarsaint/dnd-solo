# Project Understanding — DM Kit / BFDM

**Purpose:** living semantic Project Brain for humans and AI collaborators  
**Status:** canonical on `dnd-solo/main` after Brendon-approved merges of #113 and #117 on 2026-10-08. It is no longer a proposed side-branch draft.  
**Canonical location:** `radarsaint/dnd-solo/docs/PROJECT_UNDERSTANDING.md`  
**Sibling repository:** `radarsaint/bfdm-corpus`  
**Last substantive refresh:** 2026-10-26 (#150, #157, #166, #167, #168, #159, #169, #171, #172, #174, #181, #182, #183, #184, #185, and #187 merges)  
**Context reviewed against:** `dnd-solo/main @ 8dcf8d8b42ea0c1a3963a47bd09d0a501a493c25`; `bfdm-corpus/main @ df47554633b20ba872bd8cd393c420bbef7140d1`

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

Player-facing `start` and `init` with no `--room` no longer mount Area 6c or load a default character (Wren). They return `campaign_entry` (or `resume` if the save already holds a game) and do not create a database. The campaign is Dungeon of the Mad Mage. Its start—the Yawning Portal then Level 1 Area 1—is not a room file. Source-to-room authoring for Mad Mage remains unbuilt (rooms missing; host told not to invent). Area 6c mounts only with explicit `--regression --room tests/fixtures/level_01_area_06c.json`. A legitimate Mad Mage opening remains blocked on missing room files. The first slice of adventure ingestion is now live (#172): deterministic `adventure import` indexes a supplied text/PDF once into a private index, then `adventure compile` produces validated room JSON (read-aloud → visible facts, rest hidden, connections as exits with provenance) just-in-time, with cache, pre-compile of neighbours, and on-arrival compile. Status carries adventure_readiness. Limitations: host must extract PDF well and mark read-aloud with `> `; exit names are generic; room-format expressiveness for arbitrary adventures is unknown. #174 (2026-10-26) adds combat-capable actors from sourced creatures: book stat block (quoted) first, then SRD 5.1, else ask_player. Player-visible only if read-aloud names them; otherwise hidden until a disturb or enter reveal trigger. Multiattack is partial; recharge, spells, legendary, resistances, and full dice are unsupported (averages used, flagged on compile). Presence detection and reveal timing can misfire; stat-block name matching can drop attacks. Synthetic lantern_ferry fixture only; no published text. Tests include a full engine exchange. Tests 1,437 OK. dnd-solo #124 merged as `219f6e0478e153e73e7e10a73851036f7228d940` (2026-10-16).

On 2026-10-26, dnd-solo #181 merged (rebuild of #135): numbered and ambiguous targets ask, never misfire. New `runtime/kit_names.py` holds naming logic (numbered labels, perceivable names, ordinals, `resolve()` returning (key, tied)). `name_target` and new `target_ask` use it for weapon and spell attacks. Ambiguous or missing target becomes an `ask_target` ruling; no turn is committed. Precedence: no perceived foes → existing "nobody left"; named foe down; named foe missing ("There's no X here that you can see."); tie → "Which one: …? Name the one you attack. No turn was committed." Companion keys are not state actors. Synthetic fixtures only. Likely residual misfires noted (ordinal in flavour text, shared head nouns, sound-only perception). Supersedes #135 (#135 left open).

On 2026-10-26, dnd-solo #182 merged (rebuild of #139): surprise uses the ambusher's own Stealth. Each ambusher's known Stealth is rolled; a flat dc stands in only for an unknown Stealth. Updated room trigger docs and tests. Supersedes #139.

On 2026-10-26, dnd-solo #183 merged (rebuild of #131): unperceived actors stay out of view, speakers and roster. Actors carrying a hiding mark or gone status are excluded from player_view, present actors, turn speakers, hidden_actor_words and the combat roster until a trigger reveals them. Companions are not state actors. Synthetic fixtures only. Supersedes #131 (#131 left open).

On 2026-10-26, dnd-solo #184 merged (rebuild of #136): a threshold look never shows who or what is inside. Threshold looks refuse performances that name live actors' secrets, motives, knowledge, dm_identity, personal names, unlearned hidden claims, or non-visible non-found facts. Inside the room itself the restriction list is empty. A held description on the check may show who is there and visible facts. Words already given by tease, hearing, public view or the player are excused. Synthetic watchroom variants only. Likely residual misfires noted (capitalised non-SRD name, two-word secret runs, creature head noun). Supersedes #136 (#136 left open).

On 2026-10-26, dnd-solo #185 merged (rebuild of #138): rehydrate returns a pending turn's full one-pass packet. A new kit_packets table stores the last full packet for each pending one-pass turn (saved before layering, including window_answered). rehydrate returns it as packet alongside manifests when layers exist, or packet only when no layers. Abandoned/committed turns have no packet (refused if no layers). Precedence and misfires documented in MANIFESTS.md. Synthetic camp room tests. Supersedes #138 (#138 left open).

On 2026-10-26, dnd-solo #187 merged (rebuild of #103): let-it-ride for standing checks; the engine never rolls a PC's check. state.standing_check holds an established result that stands while the PC keeps the same endeavor. Material change (new area, watcher, approach, fight, or higher DC) calls a new roll for the player. No stated/pinned die raises RollNeeded, turned into check_called with the act in pending_check.action. Kit sees standing_check and check_called privately. Synthetic watchroom and variants. Likely residual misfires noted. Supersedes #103 (#103 left open).

The research substrate has also advanced. BFDM PR #40 merged on 2026-10-08: the catalog now holds 195 BCS identities through BCS-000195, with 193 indexed source containers (BCS-000059 is context-only; BCS-000068 is an excerpt without a source container). Model-facing Discord retrieval exists, and the old Git LFS opacity problem should not be restarted. The remaining missing revisions, Rowing Oak imagery, Bodfish Google Site, partial Earthfall/Saturday Project histories, and known-source gaps remain explicit archival work dependent on source access. Accessible evidence is not semantically verified judgment research.

[The remainder of the document continues unchanged from the previous canonical version on main. The updates above are the only semantic changes required by the recent merges.]