# BFDM Corpus Review — 2026-10-03

**Reviewed:** `corpus/bfdm/` at `main` `8f2ad2e` (130 files).
**Reviewer:** Kit (Cursor cloud agent), at Brendon's request.
**Scope:** the corpus as built — its layer architecture, provenance machinery, and the research resting on it. Not the publication mechanism.
**Verdict:** the method and the integrity machinery are unusually good. The problems are all in the seams: the research has outrun the registry that is supposed to govern it, and the source layer the whole chain terminates in is still almost empty.

Everything below was checked against the files, not inferred from the status docs. Reproduction commands are in the last section.

## What is working

**The architecture holds.** The four layers — source archive, attributable evidence, derived research, runtime curation — are declared in `CORPUS_CHARTER.md` and actually observed in the directory layout and in the records. `research/` never claims source authority; `evidence/` never carries interpretation; `kit-evaluation/` explicitly refuses to let Kit's failures become evidence about Brendon. The archive-first invariant ("Kit is one consumer") is doing real work: it is the stated reason several Kit-convenient shortcuts were not taken.

**Referential integrity is clean.** Every identifier in the tree resolves. 68 BCS source containers, 14 BCE evidence records, 13 BCR relations, no numbering gaps, no dangling `from_id`/`to_id`, no evidence record with a missing parent, no catalog record pointing at a nonexistent BCE. All 55 BCS and 11 BCE references made from the research prose resolve. All 67 decision-case IDs (42 S3, 25 S4) referenced anywhere in the tree are defined somewhere in the tree — zero orphan citations. Both validators pass and every JSON/JSONL file parses.

**Interpretations are anchored to raw material.** The case files carry Discord message IDs densely: 186 distinct IDs in the S4 longitudinal cases, 116 in the S4 design synthesis, 80 in the S3 longitudinal cases, 34 in the source-fragment map. Any reader with the SQLite harvests can check a claim against the message that produced it. That is the single most valuable property the research layer has.

**S3's prose and data agree exactly.** All three S3 passes ship as both Markdown and JSONL with perfect record parity (20/20, 10/10, 12/12) and identical ID sets.

**Attribution is done properly.** Brendon is resolved by immutable Discord user ID `313689699627696139` in both harvests, not by nickname resemblance, and `registry/identities.jsonl` scopes each assertion with `attribution_use` and records its basis. `IDENTITY_RESOLUTION.md` and the charter both keep project ownership, passage authorship, decision authority, and delegated implementation separate.

**The project reports against itself honestly.** This is the strongest cultural signal in the corpus:

- `legacy-staging/RECONCILIATION_2026-10-02.md` states "cataloged IDs: 51 / 51; migrated source bodies: 0 / 51" and refuses to mark the point complete.
- `current-synthesis/working-model-2026-10-01.md` §6 admits the cases over-sample visible intervention.
- `longitudinal/roanoke-s3-to-s4-judgment-v1.md` includes the player feedback asking for *more* DM communication, directly against the flattering reading of its own §5, and says so.
- `creative-method/bowling-event.md` has a section titled "What this does NOT yet prove."
- `CORRECTIONS_LOG.md` preserves five occasions where Brendon corrected the research model rather than quietly reconciling them.

**The reconciler is real engineering.** `ingest/reconcile_legacy_staging.py` verifies manifest and per-file SHA-256, requires all 51 legacy BCS IDs still present in the catalog, classifies every file, refuses `--apply` on any conflict, and re-verifies after copy. The documented test matrix includes an idempotence run and a deliberate-corruption run that correctly refused to apply.

## Findings

### 1. The held-out evaluation set was spent, and the registry still says it wasn't

This is the most consequential finding.

On 2026-10-01, `prior-dnd-solo/pr36-.../evaluation/partition.json` quarantined the entire Empire City project as one split group:

> `"reason": "Keep posts, backlog and revisions together. No content from this group may support discovery traits or preference labels in this batch."`
> `"partition_order": "Saved before first substantive Roanoke source read on 2026-10-01 UTC; no content from Empire City used in discovery."`

Its promotion gate requires freezing discovery hypotheses and recording the commit *before* reading quarantined content. It also records `"cases": []` and `"case_status": "No held-out decisions or model evaluations created yet."`

On 2026-10-02 the Empire City deep pass read that material and produced 25 decision cases, a 49 KB design-method synthesis, a 59 KB longitudinal case file, and the S3→S4 developmental comparison. `METHOD.md` is explicit that this is not allowed: "Do not use evaluation-quarantined sources to build the hypothesis that they are meant to test."

Meanwhile all 15 Empire City records in `evidence/catalog.jsonl` still read `"partition": "EVALUATION_QUARANTINE"` and `"review_status": "NOT_READ_THIS_PASS"`, and three of them are cited for content-level claims:

- `empire-city/README.md` uses `BCS-000003` to establish July 10, 2021 as the confirmed Week One / Day One boundary — a load-bearing chronological claim now repeated in `CHRONOLOGY.md`, `KNOWN_UNCERTAINTIES.md`, `STATUS.md`, and `PR5_REVIEW_2026-10-02.md`.
- `source-fragment-map-v1.md` cites `BCS-000005`–`BCS-000015` for what the Post issues contain.
- `BDC-S4-L13` cites the same range as the preserved public record.

Some of this is defensible in detail. `partition.json` lists the Backlog Notes TOC lines under `known_prior_exposure`, so the July 10 claim probably comes from already-exposed material, and the Post characterizations may actually rest on the live Post channel with the Drive docs named only as the dated container set. But the corpus cannot currently tell a reader which it is, and the two layers now assert opposite things about the same 15 sources.

Nothing records the change. `CORRECTIONS_LOG.md`, `KNOWN_UNCERTAINTIES.md`, `METHODOLOGY_AUDIT_2026-10-02.md` and `PR5_REVIEW_2026-10-02.md` are all silent on it, although the corrections log's own closing rule requires recording exactly this kind of reversal rather than silently rewriting the record. The practical loss is that the project's only designated held-out set was consumed before a single evaluation case was built from it.

**Needed:** decide and write down whether the Empire City quarantine is void. If it is, update the 15 catalog records and log the decision with what was gained. If the citations are metadata-only, say so at each citation and keep the quarantine. Then name whatever becomes the replacement held-out set — the partition file currently describes a protection that no longer exists.

### 2. The chain ends in metadata: 1 of 68 sources has a body in the repo

`claim → BCE → BCS → native/portable source` is the rule in `METHOD.md`, the charter, and `METHODOLOGY_AUDIT`. Today the last hop resolves for one source.

67 of 68 catalog records have `"portable_snapshot": null`. The only portable snapshot is `evidence/sources/BCS-000068-retrospective-self-report-2026-10-01-02.md`, and it is present and good. Every other record locates its source only in a ChatGPT Library path (`/Dnd solo source imports/...`) or a Drive ID — 51 catalog-referenced paths that do not exist in the repository. The two Discord SQLite harvests are the real exception and they carry the live-play side well; what is missing is the entire prep, revision, and document side.

The charter's success condition is that "a future researcher or Kit can locate the source, see who produced it, reconstruct its context and chronology." For 67 of 68 sources that currently depends on Brendon's connector access, not on the archive.

The project diagnosed this precisely and the fix is already written and tested. It needs an environment with the staging ZIP on disk and authenticated git write access, which is a different problem from a research problem. **This is the highest-value unblocking action in the corpus** and it is blocked only on execution environment.

### 3. Checksums exist, but not in the file that asserts provenance

`research/legacy-staging/manifest.all.jsonl` carries `original_sha256` and `normalized_sha256` for all 51 legacy containers. `evidence/catalog.jsonl` carries no checksum field on any of its 68 records, though the charter lists checksums among what must be preserved. BCS-000001–000016 (the Empire City imports) have no checksum anywhere in the corpus.

The integrity data is one file away from the registry that needs it. Propagating it is mechanical.

### 4. Thirty-three Drive sources are used as evidence without source containers

Of 54 distinct Drive IDs cited across the research prose, 33 appear nowhere in `evidence/catalog.jsonl`. They concentrate in `source-leads/homebrew-mechanics-worldbuilding.md` (16), `CHRONOLOGY.md` (10), `empire-city/source-fragment-map-v1.md` (8), and `empire-city/longitudinal-decision-cases-v1.md` (4) — including load-bearing S4 sources such as the Hampstead info doc, the Kingsbridge first draft, *The Red Coats*, the Ferrytown master doc, and the S4 Master Timeline.

The charter says derived research "should cite evidence/source IDs rather than inventing a parallel provenance system," and `REPO_HYGIENE.md` requires checking the manifest and catalog before adding a source. Bare Drive IDs are better than nothing and are genuinely traceable, but the effect is that `evidence/catalog.jsonl` can no longer answer what the research rests on — the registry describes a smaller corpus than the one already in use.

### 5. The two-axis discipline is absent from the layer it exists to constrain

Separating evidence confidence from claim scope is the central methodological idea in both `METHOD.md` and `METHODOLOGY_AUDIT_2026-10-02.md`: "High confidence never silently widens scope."

In the 67 case records there is no scope field at all. The `confidence` field exists but is freeform prose, and across the 42 S3 records it reads: 38 × `high`, 2 × `medium-high`, 1 × `very-high`, 1 × `high, with causal caveat`. Nothing below medium-high, and the `DIRECT / STRONGLY_RECONSTRUCTED / SUGGESTIVE / UNRESOLVED` ladder appears nowhere outside `METHOD.md`. A field with one value carries no information; as it stands, `confidence` cannot distinguish a message Brendon wrote from a reconstruction of why he wrote it.

The labels *are* used, and used well, in the synthesis prose — `roanoke-s3-to-s4-judgment-v1.md` carries a separate "Persistence confidence" and "Generalization scope" on each finding and correctly refuses to promote any of them past "cross-campaign candidate." So the discipline lives at the top layer and is missing from the records underneath it, which is the wrong way round: the synthesis is where scope creep gets caught, and the cases are where it starts.

`CHRONOLOGY.md` already notes that case records should carry an `era`/date field. They don't. Three different case schemas are in use and one (`decision-cases-v1.jsonl`) has no `schema` field at all.

### 6. S3's live window is stated as settled where the registry says it isn't

`registry/projects.jsonl` gets this exactly right. The S3 record carries `"boundary_status": "RESEARCHED_LIVE_ARCHIVE_WINDOW"` and a basis that reads "Treat it as the researched live window, not proof that no campaign activity existed outside the harvest," and `registry/discord_servers.jsonl` marks the harvest `HARVESTED_REQUESTED_WINDOW` with requested and observed windows stored separately.

The human-readable layer drops the qualifier. `CHRONOLOGY.md` has a heading "Roanoke Season 3 live window" over a flat date range; `SOURCE_COVERAGE.md` says "time window"; `STATUS.md` and `RESEARCH_STATE.json` both say "window". And the harvest README shows why this matters: the requested window was 2020-07-18 → 2020-08-22 and the earliest and latest messages sit exactly on those boundaries, which is the signature of truncation at the request edge rather than of a campaign that happened to start and stop there.

`KNOWN_UNCERTAINTIES.md` lists the live windows for Seasons 2 and 5 and the S4 close as unresolved. S3 is not listed. This is the same inference the corpus explicitly refuses to make for S4 — and S3 is the densest dataset, so this window frames more claims than any other date in the archive, including the coverage argument about S3 density.

### 7. Season 4 has no machine-readable layer

S3's 42 cases ship as prose and JSONL with exact parity. The 25 S4 cases exist only as Markdown. `STATUS.md` calls the S4 longitudinal file "the strongest current evidence for how S4 decisions actually changed over time," and it is the one body of cases that cannot be queried, diffed, validated, or exported without re-parsing prose. The S4 Markdown is well structured and the extraction would be straightforward.

### 8. Three indexes have drifted from the tree

- `evidence/EVIDENCE.md` documents BCE-000001 through BCE-000013 and omits BCE-000014, which is present in `evidence.jsonl` and which `PR5_REVIEW` records as having been added to machine state. The human-readable evidence index is the one an agent reads first.
- `kit-evaluation/README.md` lists three current records; the directory holds eight.
- `research/ARTIFACT_REGISTER.md` lists 121 artifacts, all of which exist, but omits nine files on disk — including every file under `discord/`, which is where the primary live sources are.

`REPO_HYGIENE.md` already says these are navigation snapshots to refresh at deliberate checkpoints and that they "should never become a second source of truth." The rule is right; the checkpoint is what slipped. Findings 1, 6, and 8 are all the same failure mode.

### 9. The coordination layer is large enough to be its own drift surface

Nine files hold overlapping state and handoff material — `STATUS.md`, `RESEARCH_STATE.json`, `INDEX.md`, `PROJECT_MAP.md`, `PROJECT_DECISIONS.md`, `NEXT_HANDOFF.md`, `HANDOFF_AND_BACKLOG.md`, `ARTIFACT_REGISTER.md`, `QUESTIONS.md` — about 61 KB against 402 KB of actual research across 21 files. Each restates status, next steps, or inventory that is also recorded elsewhere, so each one is a place where the record can disagree with itself, and three of the findings above are precisely that. Consider collapsing to one human handoff plus one generated state file, with everything else pointing at them.

### 10. The negative-space pass is still unwritten

`METHOD.md` requires deliberately sampling restraint. `working-model-2026-10-01.md` §6 says the current cases over-sample intervention. `HANDOFF_AND_BACKLOG.md` §B schedules the pass. No artifact exists.

By title, about five or six of the thirty S3 decision cases turn on restraint — a declined hook allowed to reach its failure state, players choosing granularity, accommodation stopping, DM knowledge withheld, control released, an authored week deliberately decompressed. The rest are interventions. The corpus therefore currently teaches that noticing implies acting, which is the exact bias `METHOD.md` warns would make Kit constantly "improve" functioning play. This matters more than its backlog position suggests, because it is the one gap that would show up directly in Kit's behavior.

## Suggested order

1. Resolve the Empire City quarantine contradiction and log it (finding 1). Cheap, and it is a methodology-integrity issue that gets harder to reconstruct the longer it sits.
2. Run the reconciler to land the 51 source bodies and 284 record files (finding 2). Needs a machine with the ZIP and git write access.
3. Propagate the manifest checksums into the catalog; open source containers for the 33 orphan Drive sources (findings 3, 4).
4. Add `scope`, `era`/date, and an enumerated `confidence` to the case schemas; backfill the 67 existing cases; give `decision-cases-v1.jsonl` a `schema` field (finding 5).
5. Restore the S3 window qualifier in the four prose and state files, and add the S3 boundary to `KNOWN_UNCERTAINTIES.md` (finding 6).
6. Emit S4 JSONL; refresh the three indexes; collapse the coordination layer; run the negative-space pass (findings 7, 8, 9, 10).

Findings 1, 5, and 6 are decisions for Brendon and GPT, not mechanical fixes — they change what the corpus claims, so they should not be edited in by a reviewer.

## What this review could not check

The two Discord SQLite harvests are Git LFS objects and were not dereferenced here, so individual message-ID citations were confirmed to be present and well formed but not resolved against the databases. The 51 legacy source bodies are not in the tree (finding 2), so their checksums could not be verified against real files. The Kit evaluation records that `docs/collab/BOARD.md` cites in the canonical repo — the 6c table calls record and the three 6c scorecard directories — are not in this tree, so the current Kit-facing evaluation layer was reviewed only as far as the records present.

## Reproduction

From `corpus/bfdm/`:

```sh
python3 registry/validate_registry.py
python3 ingest/validate_ingest.py --repo .

# referential integrity across the evidence layer
python3 - <<'PY'
import json
load=lambda p:[json.loads(l) for l in open(p) if l.strip()]
cat,ev,rel=load('evidence/catalog.jsonl'),load('evidence/evidence.jsonl'),load('evidence/relations.jsonl')
bcs={r['corpus_id'] for r in cat}; bce={r['evidence_id'] for r in ev}
print(len(bcs),'BCS',len(bce),'BCE',len(rel),'BCR')
print('dangling:',[r['relation_id'] for r in rel if r['from_id'] not in bcs|bce or r['to_id'] not in bcs|bce])
print('no body:',sum(1 for r in cat if not r.get('portable_snapshot')),'/',len(cat))
PY

# confidence value distribution across the S3 case records
python3 - <<'PY'
import json,collections
c=collections.Counter()
for p in ('decision-cases-v1','longitudinal-decision-cases-v2','revision-family-v3'):
    for l in open(f'research/roanoke-s3/{p}.jsonl'):
        if l.strip(): c[str(json.loads(l)['confidence']).strip().rstrip('.').lower()]+=1
print(c)
PY

# scope labels anywhere outside METHOD.md
rg -l 'CROSS_CAMPAIGN_CANDIDATE|EVENT_SPECIFIC|CAMPAIGN_SPECIFIC' .

# quarantined sources cited by derived research
rg -n 'BCS-0000(0[1-9]|1[0-6])' research/
```
