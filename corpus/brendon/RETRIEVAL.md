# Retrieval contract for agents

## Goal

Return enough original context for another agent to independently judge the source rather than merely trusting a prior summary.

## Retrieval order

For questions about **Brendon's judgment/personality**, search `evidence.jsonl` first. For historical/campaign context, search `catalog.jsonl`.

1. Resolve any cited `BCE-######` evidence ID first, then follow its parent `BCS-######` container for context. If no evidence ID exists yet, search source containers to locate material for provenance review.
2. Respect `partition` before reading. Evaluation-quarantined material stays withheld from discovery/model-building work.
3. Prefer the native source locator when the agent has access.
4. If native access is unavailable, use `portable_snapshot` once populated.
5. Retrieve the whole source when reasonably sized.
6. For large sources, return a **context bundle**:
   - the matched passage;
   - the enclosing section;
   - the preceding and following section or equivalent local window;
   - relevant comment/revision child evidence;
   - version siblings when the claim depends on a change across drafts.
7. Cite both the `BCE` evidence ID and parent `BCS` source ID in derived judgment records whenever attributable evidence exists. A `BCS` citation alone does not prove Brendon authored the cited passage.

## Query dimensions

Agents should be able to filter or rank by:

- project/campaign;
- date;
- source type: plan, finished session material, postmortem, comment, revision, playtest correction, manuscript, procedure, brainstorm;
- authorship confidence;
- decision family;
- positive/negative outcome;
- explicit reason vs inferred reason;
- discovery/evaluation partition;
- version group;
- NPC/social, exploration, combat, challenge, humor, pacing, reward, continuity, adaptation, preparation, failure, player reaction.

The current bootstrap catalog does not yet contain all of these semantic tags. Add them during source review, not by guessing from filenames.

## Anti-flattening rule

Never answer "what does Brendon think?" from one extracted principle if the underlying library contains contradictory or conditional cases. Retrieve the conflicting source bundles together.

## Portable snapshots

A portable snapshot should preserve:
- full normalized text where legally/privacy-safe;
- headings/section boundaries;
- comment/revision attribution when available;
- line/paragraph anchors stable within that snapshot;
- original source ID and checksum;
- no hidden analyst summary inside the source body.

Portable snapshots exist so GPT, Grok, and other collaborators can inspect the same evidence. They should live in a non-public shared store unless Brendon explicitly chooses to publish that source.


## Seed-safety rule

A source container with `seed_eligibility=PENDING_EVIDENCE_EXTRACTION` or `CONTAINER_NOT_DIRECT_SEED` may be searched for context, but its whole text must not be handed to Kit as Brendon personality seed.

Only bounded `BCE` evidence can advance toward seed approval. See `SEED_POLICY.md`.
