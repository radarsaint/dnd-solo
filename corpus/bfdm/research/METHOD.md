# Research Method

## Research purpose

The original narrow question remains useful:

> Given a situation at the table, what makes Brendon notice something, care about it, intervene, leave it alone, escalate it, reward it, change preparation, improvise around it, or decide that something is not working?

The corpus also supports broader questions about:
- creative method
- mechanical design
- campaign architecture
- worldbuilding
- revision/failure diagnosis
- development over time
- unusual experiments with the form of D&D

Do not force every source through one question.

## Archive-first research constraint

The BFDM corpus is a durable historical/research archive first.

Kit is one consumer.

Therefore research must never discard, flatten, or rewrite source material merely because it does not fit a current training, retrieval, prompt, or evaluation format. Model-facing datasets are derived research products and should remain reproducible from the underlying archive/evidence chain.

The method should answer research questions about Brendon's creative history on their own terms, including questions that may have no immediate Kit application.

## Four-layer discipline

Keep these layers separate:

1. **Source archive** — what material exists?
2. **Attributable evidence** — what bounded contribution can be tied to Brendon?
3. **Derived research** — what might the evidence mean?
4. **Runtime curation** — what, if anything, should Kit actually use?

Use the existing provenance ontology where available:
- `BCS-######` — source container
- `BCE-######` — attributable evidence
- `BCR-######` — supported relation

Derived research is never a replacement for source/evidence.

## Two axes: confidence and scope

Do not use one ladder for both certainty and generalization.

### Evidence confidence

- **DIRECT / EXPLICIT** — statement, correction, signed contribution, attributable comment, or clear attributable revision.
- **STRONGLY RECONSTRUCTED** — chronology and source comparison support the claim with little ambiguity.
- **SUGGESTIVE** — plausible but meaningful alternative explanations remain.
- **UNRESOLVED** — evidence is insufficient or conflicting.

### Claim scope

- **EVENT_SPECIFIC**
- **CAMPAIGN_SPECIFIC**
- **FORMAT_SPECIFIC**
- **ERA_SPECIFIC**
- **CROSS_CAMPAIGN_CANDIDATE**
- **DEVELOPMENTAL**
- **GENERAL_CURRENT_PRACTICE_CANDIDATE**

A claim can be DIRECT and still remain EVENT_SPECIFIC.

High confidence never silently widens scope.

## Source classes

Distinguish at least:

- contemporaneous prep
- live-play record
- change log / design note
- revision delta
- attributable comment
- playtest correction
- postmortem
- retrospective self-report
- collaborative/project context
- third-party context
- derived analysis
- current project directive

Brendon's present recollections about older games are `RETROSPECTIVE_SELF_REPORT`: direct evidence of his present recollection/interpretation, not a substitute for contemporaneous records.

## Claim-specific source authority

There is no universal source type that always wins.

Ask what claim is being made.

- **What was delivered/recorded in play?** Prefer captured live evidence over stale prep.
- **What was documented before play?** Prefer dated prep/revision history.
- **Why does Brendon say he made a choice?** Prefer an explicit contemporaneous comment or retrospective self-report.
- **What actually caused the change?** Compare chronology, semantic delta, live triggers, and stated reasons; preserve unresolved causes.

A live Discord archive establishes what is **documented in the captured live record**, not everything that happened.

A dated prep artifact establishes what was **documented in that artifact**, not everything Brendon privately intended.

## Revision-aware causality

A timestamp is not a motive.

Useful labels:
- `PREP_DRIVEN`
- `LIVE_OPERATIONAL`
- `LIVE_RESPONSE`
- `PREPARED_ADAPTABILITY`
- `MIXED / UNRESOLVED`

A strong `LIVE_RESPONSE` reconstruction should have:
1. a dated pre-change baseline;
2. a meaningful semantic delta;
3. a live trigger before the change;
4. preferably downstream delivery tied to the same trigger.

If one element is missing, narrow the claim.

## Identity and authorship

Screen names change across seasons.

Use [IDENTITY_RESOLUTION.md](IDENTITY_RESOLUTION.md).

Prefer immutable platform IDs and server/date-specific alias mappings. Do not globally attribute a nickname without a supported identity link.

Keep separate:
- project ownership
- message/passage authorship
- decision authority
- delegated implementation

A collaborator's work can belong to a Brendon-run campaign without becoming Brendon-authored evidence.

## Campaign-context metadata

Research cases should record, when available:
- campaign/project
- approximate date
- table/player scale
- synchronous vs asynchronous
- single-DM vs multi-DM
- live table vs persistent server
- session-time pressure
- degree of authored structure
- relevant collaborators
- evidence phase: prep, live play, postmortem, retrospective

This prevents a Roanoke-scale solution from becoming a universal small-table rule.

## Development over time

Do not flatten early and late Brendon into an average.

Look for:
- persistent traits
- evolved practices
- format-specific adaptations
- abandoned/superseded practices
- explicit later contradictions
- emergent behaviors later formalized

A useful candidate pattern is:

> emergent practice → recognized value → later formalization

The interpersonal/social layer later called the "dating sim" is one candidate, but its chronology still needs source work.

Do not assume "newer always wins." Later work may be different because the task changed.

## Negative-space research

Visible changes are easier to extract than restraint.

Deliberately sample:
- player activity left alone
- prep left unchanged despite attention
- ideas considered but rejected
- hooks allowed to fail
- NPCs/mechanics not promoted
- functioning scenes not "improved"

Without negative-space cases, Kit would be overtrained to intervene.

## Coverage and survivorship

Archive density is not prevalence.

Before making absence/frequency claims across eras, check whether the compared periods have comparable:
- Discord coverage
- revision coverage
- voice/off-platform capture
- document survival
- authorship resolution

S3's density must not masquerade as importance or frequency.

## Derived-research independence

Do not count multiple analyses of the same underlying source as independent confirmation.

S3 v1/v2/v3, prior `dnd-solo` studies, syntheses, and longitudinal cases are navigation and hypothesis tools.

New claims should trace to source/evidence:

`derived claim -> BCE/equivalent evidence -> BCS source container -> native/portable source`

If the chain breaks, the conclusion is not source-ready.

## Discovery vs evaluation

Where material has been designated held-out/evaluation-only, respect that partition.

Do not use evaluation-quarantined sources to build the hypothesis that they are meant to test.

When practical, formulate the research question before opening held-out evidence.

## Keep the archive open-ended

The corpus may support:
- human-readable synthesis
- retrieval
- evaluation
- preference/judgment training
- creative apprenticeship
- design assistance
- campaign-format reconstruction
- longitudinal creative research
- voice/style distillation

Do not choose one use early and discard information needed for others.

## Promotion into Kit

No research artifact becomes Kit behavior automatically.

Future promotion should be deliberate and traceable:

`Kit behavior/seed -> curated derived record -> BCE evidence -> BCS source -> native/portable source`

A compact voice payload is one possible downstream artifact for expressed table voice. It is not a substitute for judgment/personality research.

## Default research posture

Prefer:
- narrower supported claims over elegant broad theories;
- unresolved causality over invented motive;
- contradictory evidence preserved together;
- source history over cleaned narrative;
- explicit correction over silent reconciliation.

The standard is not "does this interpretation sound like Brendon?"

The standard is "can another researcher reconstruct why we believe it, see the limits, and disagree intelligently?"
