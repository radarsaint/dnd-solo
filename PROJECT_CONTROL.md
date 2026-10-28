# Project Control — DM Kit runtime

**Updated:** 2026-10-21 (bounded North Star/personality update; runtime audit below unchanged)  
**Last runtime truth audit:** `main @ e3a5e9908357441051df24dac8086d8d4c7f26f5`  
**Sibling repo:** `radarsaint/bfdm-corpus`

For substantial project work, start with `PROJECT_BOOTSTRAP.md`. It routes to the durable mental model, agent/tool map, this current-state control surface, recent context changes, and the owning issue/PR.

This file is the **current runtime-state layer**, not the complete project memory.

This file is deliberately short and rewritable. Git history, issues, PRs, and `docs/collab/BOARD.md` preserve history.

## What this repo is

`dnd-solo` is the current executable Kit runtime and player-facing development surface.

It is not the BFDM archive and it is not all future Kit cognition.

## Current executable reality

At the audited commit:

- live chat uses `start` -> `prepare --one-pass` -> `complete`;
- staged `prepare -> decide -> finish` remains reachable for evaluation;
- arbitrary room JSON can mount;
- SQLite persists source/state, revisions, ledger events, Kit turns, pending turns, and telemetry;
- Python handles bounded intent routing, deterministic checks when the player supplies no roll, tolls, card procedures, minimal combat, claims/knowers, agendas, attitudes, hidden-information guards, manifests, retries, and idempotent commits;
- Kit/model supplies private judgment and public performance plus a checked set of canon/state proposals;
- a live state that establishes a pinned situation can attach advisory `dm_judgment` to that private input (`runtime/kit_judgment.py`); a player sentence does not; this is not evidence that play is better;
- `--table-talk` is a distinct execution path;
- the audited suite is **813 tests green**.

This is materially beyond the old “Area 6c staged prototype” description.

## Complete host loading

The October 21 handoff exposed a distribution failure: readable GitHub text was not an executable mount, the 37-file workaround omitted host/reference files, and a Python reset removed the extracted tree. The release-only publisher also supplied no binary workflow artifact for the connector's artifact-download tool.

`LOAD_KIT.md` is now the host entry point. `scripts/kit_host.py` packages every tracked source blob, reconstructs the full Git tree during verification, checks every file, runs the actual persona command, and creates the host context for the GPT to read. The existing publishing workflow supplies that same ZIP as a connector-downloadable artifact and a pinned release. Repeated mounts verify or restore the source and preserve a damaged prior directory. Standalone stale persona files and the old PR #141 text-part transfer are superseded.

This repair's acceptance remains a complete load and reset recovery in a fresh ordinary GPT. CI or a Work-host check establishes only the tested path in that environment; do not mark ordinary-GPT acceptance complete without its actual download, integrity report, and full host-context read. The owning Work session handles repair/delivery; the destination GPT handles its own mount. This does not merge room-pack or gameplay PRs.

## Room-loader versus source-to-room boundary

This distinction is settled and important:

- **Built:** a generalized loader can mount conforming room JSON and chain rooms.
- **Not built on current main:** general adventure-source retrieval/authoring that takes untouched keyed adventure text and produces the next playable room on demand.

PR #100 is the current proposed source-to-room authoring path. Until equivalent functionality lands and is demonstrated across varied previously unplayed keyed areas, do not say “Kit can play any keyed room from the book” merely because the loader is generalized.

Chaining is a loader capability. On the tree inspected for this control snapshot, no committed room file contains a `room_link`. Chain tests build temporary copies. Area 17a mounts as a non-playable stub. Do not describe an authored multi-room campaign as already present on `main`.

## What is not proven

- Area 6c remains the only richly authored room on audited `main`. This branch proposes a different player-facing start, and that start is not on `main` until this PR merges: `start` with no `--room` and no `--campaign` greets and does not mount 6c. Dungeon of the Mad Mage is reported only when the player asks for it (`--campaign dotmm`), and it is not a playable room. `--regression --room tests/fixtures/level_01_area_06c.json` is the engineering path.
- Mounting arbitrary rooms proves loader/general runtime mechanics, not generalized excellent DMing.
- The watchroom is synthetic and 17a is sparse.
- Natural-language routing still relies heavily on regex classification.
- Social mechanics remain bounded/simple under the performance layer.
- Many overview documents lag the executable system.
- Green tests prove mechanical contracts, not that Kit is entertaining or satisfying to play with.

Current product-level statement:

> Kit has a substantially generalized runtime substrate, a small set of demonstrated current runtime blockers, and insufficient post-fix human evidence to know the current DM-quality ceiling.

The implementation has advanced faster than player-facing evaluation. Several historically serious failures should now be classified as `MECHANICALLY_ADDRESSED_UNRETESTED` or `UNKNOWN_CURRENT`, not silently carried forward as current defects.

## Current demonstrated quality blockers

The 2026-10-07 quality/failure-localization audit identified four current-main defects supported strongly enough to call demonstrated:

- **PR #103 — PC roll ownership / Let It Ride:** current main can silently reroll a player's established check across several adjudication paths.
- **PR #97 + dependent #101 — combat transition completeness:** player-initiated combat exists, but monster initiation, surprise/save riders, hidden-actor reveal, downed/death-state and related transition handling remain incomplete on main.
- **PR #102 — validator functional floors:** raw word-count floors can reject short complete DM turns and reward padding.
- **PR #73 — deliberate social omission:** at least one live-observed deception-shaped omission class remains unfixed on main.

These are narrower than the older claims that “combat does not work,” “NPCs are lifeless,” “natural language is broken,” or “Area 6c is the architecture.” Those broader claims are stale or currently unproven.

## Current quality-evidence gap

The largest uncertainty is now **freshness of human evidence**.

Major runtime changes landed after the last serious Brendon-facing quality sessions: story briefs, attitudes, router work, room loading, watchroom repairs, packet layering, output diet, compute routing, and speed work.

Therefore both of these claims are currently too strong:

- “Kit still has the old player-facing failures.”
- “The new machinery fixed the player-facing experience.”

The next meaningful acceptance evidence should come from sustained current-main play in a materially different real room, after known blockers are merged or deliberately avoided. The purpose is to discover the next quality ceiling rather than rediscover known plumbing defects.

## Four-audit synthesis

The four October 7 audits converge on one project-level failure mode:

> **proxy evidence has repeatedly been mistaken for demonstrated truth.**

Runtime tests can pass while play is poor. Historical failures can outlive the builds that caused them. Searchable sources can support unverified derived claims. Old documents can still call themselves canonical after authority moved elsewhere.

Current confidence should therefore be tracked separately across:
- executable runtime truth;
- player-experience evidence;
- BFDM research trust;
- project/coordination authority.

The machinery is currently ahead of the evidence on both runtime quality and BFDM research trust.

## Product acceptance rule

**Kit is the product. The total experience is the acceptance layer.**

The October 21 director clarification makes the creative purpose explicit: pursue the most satisfying story that can honestly emerge from this world and these people. Brendon's exact addition is:

> I must build a world worthy of the people in it. And I must sew the people to the world while loving both enough to support what they become.

The [personality core](docs/personality/dm-personality-core.md) carries the operating principles through the existing runtime input. The [Project Brain](docs/PROJECT_UNDERSTANDING.md) explains the consequences; the [developmental handoff](docs/personality/2026-10-21-mount-to-north-star-handoff.md) preserves the record; the [judgment probes](tests/scenarios/north-star-judgment.md) remain unrun acceptance work. This is a requirement clarification, not demonstrated improvement in play or a fresh runtime audit.

Do not let runtime correctness, judgment, cognition, personality, or any other subsystem become the project goal by proxy.

A feature can pass its own tests and still make Kit worse to use.

## Current engineering coordination

Default runtime integration owner: **Skippy / Grok Bots**.

Current executable audit was performed by Grok Build against the SHA above.

Important unresolved stack questions for Skippy include:

- intended ordering/ownership of overlapping runtime PRs touching `kit_agent.py`;
- whether visual PRs #111 and #112 are alternatives or a sequence;
- whether the accepted outside-combat grab behavior is the current `pc_grab` implementation or the later board ruling;
- which pinned Kit build is actually mounted in external GPT/project environments.

Do not resolve these by guessing from open-PR age.

## Current authority traps

Fresh agents are at particular risk of being misled by surfaces that still look current:

- **KRABS authority** — live `dnd-solo/main` contains **KRABS v0.2.2**, the current canonical long-term Kit Reference Architecture & Behavioral Specification. It supersedes KRABS v0.1, PR #44's v0.2 draft, and v0.2.1. The stale item is the old Project attachment that still presents v0.1 as canonical; do not generalize that into “KRABS is historical” or “KRABS is old-era.”
- **Legacy ChatGPT Project attachments** — `docs/KIT_PROJECT_START_HERE.md` names the ten audited filenames and their verified homes. They do not outrank live `main`, including when they are still attached. The generalized Restartable Role Runtime proposed in one of them is not current architecture.
- **No in-repo corpus mirror** — #114 merged as `c9ce777729b77610944314b544cad709becbfe2d` and removed `corpus/`. Canonical BFDM authority is `radarsaint/bfdm-corpus`. Do not recreate the mirror.
- **Append-only collaboration board** — historical decision provenance, not the current work queue. Board-split drafts #107 and #109 are not adopted; a second live board would compete with this file.
- **Closed superseded PRs** — #5, #11, #23, #36, #38, #43, #44, and #35 are closed. Do not treat them as open or current direction. 87 stale branches were deleted.
- **Salvaged historical files** — #121 merged as `a62bc0c70ead981f5175c632c71867d2fb2d91c4` and brought design notes, the Roanoke exporter, and a playtest onto main. They are repository history, not proof of player-facing quality.
- **Legacy paid play route** — still present in `runtime/kit_agent.py`. Removal is scoped to Skippy and not done.
- **Pinned ZIPs** — reproduce their commit only; they do not answer what current main does.

## Documentation state

The merged coordination refresh (dnd-solo #113, now on `main`) refreshed the primary human/agent entry points: `README.md`, `START_HERE.md`, `AGENTS.md`, `docs/WHAT_WE_ARE_BUILDING.md`, `state/project-status.md`, and the collaboration protocol. #117 (context-status checker) and bfdm-corpus #39 are also on main. They are not proposed side-branch drafts.

Older runtime architecture documents and historical Area 6c wording may still describe prior slices. Treat them as reference/history unless current control or executable code confirms the claim.

Future drift should be handled by rewriting this current-control layer and linking to the commit/PR that changed truth, not by appending another competing handoff.

## Current BFDM / Friday research dependency

The current BFDM bottleneck is not source searchability. It is semantic trust in the derived layer and adversarial testing of candidate hypotheses.

Runtime/cognition work should **not** assume that PR #28's contrast families are verified gold labels. PR #38 currently has 20 staged S3 cases / 120 propositions at `UNVERIFIED`.

For Friday, scarce ChatGPT Work is better spent establishing trustworthy research dependencies and attacking hypotheses from primary evidence than building precedent/retrieval/cognition infrastructure.

Skippy/runtime work should consume verified research outputs only when their scope/confidence is explicit, and should keep current-main player-experience evidence separate from BFDM research quality.

## Cross-repo rules

Use `bfdm-corpus main` for canonical BFDM source/research state.

Do not use an in-repo corpus mirror; there is none on main.

Do not harden derived BFDM claims into runtime behavior merely because they are polished or cited. Active corpus integrity work may downgrade them.

## Current temporary parallel work

Before Friday:

- GPT 1 — project truth / contradiction audit (complete; incorporated);
- GPT 2 — Kit quality / failure-localization audit (complete; incorporated);
- GPT 3 — BFDM research-readiness / Work queue (complete; incorporated into paired coordination PRs);
- Grok Build — executable runtime audit (complete);
- separate GPT — mechanical corpus preparation;
- control-room thread — synthesis and task routing.

These are temporary assignments, not permanent architecture.

## Start points

For live runtime operation: `START_HERE.md` and `AGENTS.md`.

For development orientation: this file, then the owning issue/PR.

For cross-agent protocol: `COORDINATION.md`.

For history only: `docs/collab/BOARD.md`.
