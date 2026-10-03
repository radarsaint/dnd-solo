# KRABS v0.2 — External Review Brief

A prompt for handing [`KRABS.md`](KRABS.md) to a reviewing model. Paste everything below the line into the conversation and attach or paste `docs/architecture/KRABS.md` (one file, about 89 KB) alongside it.

If the reviewer has repository access, give it these instead of a paste:

- `https://github.com/radarsaint/dnd-solo` — runtime, architecture docs, tests, playtest records
- `https://github.com/radarsaint/dnd-solo/tree/main/corpus/bfdm` — public BFDM evidence mirror

Everything below the line is the prompt. Nothing in it needs editing before use.

---

You are reviewing an architecture specification. I want it attacked, not validated.

The document is **KRABS v0.2** (Kit Reference Architecture & Behavioral Specification), attached. It describes an AI Dungeon Master intended to run both a demanding one-player D&D campaign and, eventually, a continuously-operating asynchronous multi-party campaign of roughly a hundred players under a human director.

## What I do not want

A review that tells me the document is comprehensive, well-structured, or thoughtful is worthless to me. So is a review that recommends adding something the system already has. So is a list of generic architecture advice that would apply to any document of this kind.

The specification is long and internally consistent. That is exactly what makes it dangerous: a fluent document can hide a load-bearing assumption that will not survive contact with implementation, and fluency is not evidence against that.

## Context you need before reviewing

This is **not a greenfield proposal.** A working runtime exists, with 381 passing tests, real playtest failures on record, and several of the mechanisms the document describes already built. Reviewing it as though nothing exists produces findings I have to throw away.

v0.1 was a first architectural pass. External review of v0.1 produced three recommendations, and v0.2 exists to answer them:

1. Incorporate an explicit concurrency model — how scenes, regions, and clocks acquire write authority over authoritative state during continuous asynchronous multi-party play. → now **§24**.
2. Formalize the adjudication pipeline — a strict symbolic check on rules and affordances before the language model generates the narrative performance, so mechanics cannot be bypassed by creative phrasing. → now **§12**.
3. Define hard escalation rules — explicit, unmodifiable threshold triggers for human review, supplementing learned director attention. → now **§21**.

Those three sections, plus the supporting invariants in §5, are the primary subject of this review. The rest of the document is context and may be criticized where it conflicts with them.

### Implementation status, so you do not recommend what exists

| Area | Status |
| --- | --- |
| Append-only event ledger, atomic turn commit, rollback | Implemented and tested |
| Optimistic concurrency: one global revision, stale-writer rejection, turn-id idempotence | Implemented and tested |
| Adjudication before the model call; typed accepted events; provisional state preview | Implemented |
| Affordance gate: a procedure may be offered as playable only if the runtime can execute it | Implemented |
| Symbolic decision validation: knower bands, agenda rooting, roll calls, claim checks | Implemented |
| Performance validation with named failed checks and bounded retry against a fixed decision | Implemented |
| Player-facing projection with secret/knowledge boundaries | Implemented and tested |
| Multi-domain concurrency, leases, per-domain revisions (§24) | Designed only, nothing built |
| Escalation floor, director role, director channel (§21) | Designed only, nothing built; there is no director in the system at all |
| Multi-party play, guest DMs, continuous production | Not started |

§32 of the document carries its own version of this table. Check it rather than trusting mine.

### Weak claims I have already identified

Do not spend your review rediscovering these. Go past them, or tell me my characterization of them is wrong.

- **§24's domain partition.** The whole section rests on a campaign author being able to declare a partition that neither serializes most play nor makes multi-domain turns the common case. Nobody has tried this for a real campaign.
- **§21's floor size.** The section claims a hard escalation floor and an approval queue are different things, and that claim rests entirely on the floor staying short. Nobody has authored a floor for a real campaign either.
- **§21's rate triggers** are the only machinery in the whole document for noticing that Kit's apparently successful behavior is accumulating into campaign harm. That is thin and I know it.
- **§12's one-pass conformance gap** is a real, shipped, non-conformant code path. The fix costs a model round trip against a latency problem already measured at 81 seconds in a playtest. I have not decided whether to pay it.
- **Two of the three additions are anticipatory.** §12 answers a recorded live failure. §24 and §21 answer structural arguments, because there is no multi-party production and no director role yet to fail. §35 admits this.

## What a useful finding looks like

Each finding should name **what breaks, under what conditions, and what would fix it or what evidence would settle it.** A finding I cannot act on or test is not a finding.

Particularly valuable:

- A load-bearing assumption that is false, or that becomes false at scale.
- A place where two sections of the document contradict each other.
- A place where the specification is unfalsifiable as written — it cannot be violated, so it constrains nothing.
- A mature, boring, existing solution I should steal instead of specifying my own. §33 claims §24 invents no protocol; check that claim and name the specific systems or patterns that already encode it.
- A mechanism I am generalizing that I should replace outright, or replacing that I should generalize.
- A subsystem that is missing entirely.

## Questions, roughly in order of how much I care

1. **§24.** Is the domain taxonomy (entity, region, party, clock, structure, director intent) the right cut? Where does it fail? Is "cross-domain writes become proposals" an adequate substitute for cross-domain transactions, or does it hide a correctness problem? The section argues that because the performance layer has no undo, a write conflict must be detected before publication — is that argument sound, and does the lease model actually deliver it?
2. **§24's residual problem.** The section admits leases prevent lost writes but not causally inconsistent narratives told to different parties, and offers detection rather than prevention. Is detection enough? What do systems with this same problem actually do?
3. **§21.** The section's central argument is that a learned escalation threshold drifts toward silence because "just handle it" is always observed while a missed flag is only sometimes observed. Is that argument correct? Does the floor actually fix it, or does it just relocate the problem into whoever authors the trigger list?
4. **§21's timeout behavior.** Every hard trigger must declare what happens when no human responds, because an asynchronous production cannot block on a sleeping director. Are the three declared options sufficient? What is the failure mode of each?
5. **§12.** Are precedence, totality, and failure closure the right three properties, and are they checkable? Totality depends on classifying a claim as "mechanically consequential" — is that classification tractable? §34 already flags that §12 requires knowing whether a turn is consequential *before* resolving it, which may be circular.
6. **§12's symmetry claim.** The gate is specified to bind the DM exactly as hard as the player: Kit may not write a dramatically perfect sentence that creates a DC, a price, or an NPC's binding promise. Is that constraint holdable in practice, or will it quietly erode?
7. **Cross-cutting.** Do these three sections interact badly? §12's staged ordering, §21's blocking stops, and §24's bounded leases all touch the same turn, and a held lease during a human-blocked escalation is an obvious suspect.
8. **What breaks first** when this moves from one player to persistent multi-party play, and separately, from bounded sessions to a continuous multi-week production? v0.2's answers are the single global revision and the learned-threshold drift respectively. If you think something else breaks first, say what.
9. **Is "DM judgment" specified tightly enough** to be an engineering and evaluation target rather than an aspiration? §29's failure-localization classes and §31's decision trace are the attempt. Do they work?
10. **What is missing** that none of my questions reach.

## Output format

1. **Verdict on each of §12, §21, §24** — one of: sound as specified; sound but underspecified in a named place; wrong in a named way; should be deleted. State it plainly before you justify it.
2. **Findings**, most consequential first. Each one: what breaks, under what conditions, what would fix it or what evidence would settle it.
3. **Existing solutions I should steal**, with names specific enough to look up.
4. **Contradictions** between sections, cited by section number.
5. **The finding you are least confident about**, and what would change your mind.

Say "I cannot assess this" where that is true. A short review that is right is worth more to me than a long one that is complete.
