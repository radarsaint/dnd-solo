# BFDM Corpus Review — 2026-10-03

**Reviewed:** `radarsaint/bfdm-corpus` at `main` `6337f81` (5,540 files), cross-checked against the readable copy in `dnd-solo` `corpus/bfdm/`.
**Reviewer:** Kit (Cursor cloud agent), at Brendon's request.
**Scope:** the corpus as built — its layer architecture, provenance machinery, and the research resting on it.
**Depth:** the S3 Discord harvest LFS object was pulled (64,847,872 bytes, 197,013 messages) so research citations could be resolved against the actual source rather than only checked for form.

**Verdict:** the method and the integrity machinery are unusually good, and the live-evaluation work is better still. The problems are all in the seams. The research has outrun the registry that is meant to govern it, the source layer the whole chain terminates in is still almost empty, and the single best body of Brendon judgment evidence the project has ever produced is sitting outside the evidence layer entirely because of where it was filed.

Everything below was checked against the files. Reproduction commands are in the last section.

## What is working

**The architecture holds.** The four layers — source archive, attributable evidence, derived research, runtime curation — are declared in `CORPUS_CHARTER.md` and actually observed in the layout and in the records. `research/` never claims source authority, `evidence/` never carries interpretation, and the archive-first invariant ("Kit is one consumer") is doing real work: it is the stated reason several Kit-convenient shortcuts were not taken.

**Referential integrity is clean.** Every identifier in the tree resolves. 68 BCS source containers, 14 BCE evidence records, 13 BCR relations, no numbering gaps, no dangling `from_id`/`to_id`, no evidence record with a missing parent, no catalog record pointing at a nonexistent BCE. All 55 BCS and 11 BCE references made from the research prose resolve, and all 67 decision-case IDs (42 S3, 25 S4) cited anywhere in the tree are defined somewhere in it — zero orphan citations. Both validators pass and every JSON/JSONL file parses.

**The citations are real — verified against the harvest, not just checked for form.** Of 105 distinct 17-to-19-digit IDs cited across the three S3 research files, 101 resolve to actual messages in `roanoke-season-3.sqlite`. The remaining four are not broken citations: they are user and role IDs appearing inside verbatim-quoted Discord mention syntax (`<@!…>`, `<@&…>`), plus Brendon's own user ID in the provenance headers. **There are no false message citations.** 88 of the resolved messages are authored by the confirmed Brendon user ID `313689699627696139`, and the 13 authored by others appear where the research is describing player or collaborator behavior.

**The quotes are faithful.** All 20 `representative_line` values in `decision-cases-v1.jsonl` trace to real Brendon messages in the harvest. Eighteen are exact substrings; the other two are ellipsis-marked elisions that also check out — BDC-S3-007 elides within a single message (`735253731406381078`), and BDC-S3-016 joins two consecutive Brendon messages (`740073889681375253`, `740074415441575937`). Nothing is fabricated, paraphrased-as-quote, or reattributed. The one small note is that `representative_line` can cross a message boundary behind an ellipsis without saying so.

**S3's prose and data agree exactly.** All three S3 passes ship as both Markdown and JSONL with perfect record parity (20/20, 10/10, 12/12) and identical ID sets.

**Attribution is done properly.** Brendon is resolved by immutable Discord user ID in both harvests rather than by nickname resemblance, and `registry/identities.jsonl` scopes each assertion with `attribution_use` and records its basis.

**The project reports against itself honestly.** `legacy-staging/RECONCILIATION_2026-10-02.md` states "cataloged IDs: 51 / 51; migrated source bodies: 0 / 51" and refuses to mark the point complete. `working-model-2026-10-01.md` §6 admits the cases over-sample visible intervention. `roanoke-s3-to-s4-judgment-v1.md` includes the player feedback asking for *more* DM communication, directly against the flattering reading of its own §5. `bowling-event.md` has a section headed "What this does NOT yet prove." `CORRECTIONS_LOG.md` preserves five occasions where Brendon corrected the research model instead of quietly reconciling them.

**The reconciler is real engineering.** `ingest/reconcile_legacy_staging.py` verifies manifest and per-file SHA-256, requires all 51 legacy BCS IDs still present in the catalog, classifies every file, refuses `--apply` on any conflict, and re-verifies after copy. The documented test matrix includes an idempotence run and a deliberate-corruption run that correctly refused to apply.

## Findings

### 1. The best Brendon judgment evidence in the corpus is outside the evidence layer

`research/kit-evaluation/table-calls-6c-2026-10-02.md` records ten numbered table calls Brendon gave on the worst Area 6c moments, mostly in his own words, with explicit attribution discipline already applied — "Quotes marked 'Brendon:' are his own words," with Calls 1 and 2 flagged `(summary)` because they were relayed rather than verbatim. Each call carries the bad moment that prompted it, the principle, and pass/fail regression checks. Calls 8, 9 and 10 are separately dated 2026-10-03. The file also holds the marked-deck addendum, the fresco addendum, and his praise of the live session: "Good turn. This is how we'd want players to play."

By the corpus's own taxonomy this is `DIRECT`/`EXPLICIT`, contemporaneous, first-person evidence about precisely the question `METHOD.md` opens with — what makes Brendon notice something, care about it, intervene, leave it alone, escalate it. There is nothing of comparable grade anywhere else in the archive.

**Nothing in `evidence/catalog.jsonl`, `evidence/evidence.jsonl` or `evidence/relations.jsonl` references it.** Zero matches for `kit-evaluation` or table calls in all three. The newest BCE record ends 2026-10-02T12:38Z and the latest catalog source date is 2026-10-01/02, so every table call from 2026-10-03, the live scorecard, both addenda and the praise sit outside the evidence layer.

The cause looks like a filing convention rather than a judgment. `kit-evaluation/README.md` draws the line as "Do not use Kit failures as evidence about Brendon's historical DM behavior," and `ARTIFACT_REGISTER.md` line 170 restates it: "`research/kit-evaluation/` evaluates Kit behavior; it is not historical Brendon evidence." That rule is correct about Kit's failures. But it has been applied to the container rather than the content, and so it has swept up Brendon's *rulings on* those failures — which are not Kit evidence at all.

This matters more than its filing suggests, because it is the exact gap the rest of the corpus keeps naming. `roanoke-s3-to-s4-judgment-v1.md` closes on "S3 and S4 share too much format… the next decisive comparison should come from a materially different operating environment." `KNOWN_UNCERTAINTIES.md` says later practice "may deserve more current-practice weight despite less normalized evidence." The corpus has been generating exactly that evidence — current, non-Roanoke, solo-format, explicitly about adjudication — every day for a week, and filing it where the evidence layer cannot see it. These calls would also be the first evidence in the corpus that could legitimately carry `GENERAL_CURRENT_PRACTICE_CANDIDATE` scope.

**Needed:** a BCS container per table-call session with the live scorecards as context containers, one BCE per call (they are already bounded and individually dated), and BCR relations to the playtest transcripts that prompted each. Calls 3–10 are `DIRECT_USER_STATEMENT`; Calls 1 and 2 are weaker and the document already says why. The provenance discipline is done — it just isn't registered.

### 2. The held-out evaluation set was spent, and the registry still says it wasn't

On 2026-10-01, `prior-dnd-solo/pr36-.../evaluation/partition.json` quarantined the entire Empire City project as one split group:

> `"reason": "Keep posts, backlog and revisions together. No content from this group may support discovery traits or preference labels in this batch."`
> `"partition_order": "Saved before first substantive Roanoke source read on 2026-10-01 UTC; no content from Empire City used in discovery."`

Its promotion gate requires freezing discovery hypotheses and recording the commit *before* reading quarantined content, and it records `"cases": []` with `"case_status": "No held-out decisions or model evaluations created yet."`

On 2026-10-02 the deep pass read that material and produced 25 decision cases, a 49 KB design-method synthesis, a 59 KB longitudinal case file, and the S3→S4 comparison. `METHOD.md` is explicit: "Do not use evaluation-quarantined sources to build the hypothesis that they are meant to test."

All 15 Empire City records still read `"partition": "EVALUATION_QUARANTINE"` and `"review_status": "NOT_READ_THIS_PASS"` on current HEAD, and three are cited for content-level claims: `BCS-000003` establishes the July 10, 2021 Week One boundary now repeated in four other files; `source-fragment-map-v1.md` cites `BCS-000005`–`BCS-000015` for what the Post issues contain; `BDC-S4-L13` cites the same range.

Parts of this are defensible in detail — `partition.json` lists the Backlog Notes TOC under `known_prior_exposure`, so the July 10 claim probably rests on already-exposed material, and the Post characterizations may actually come from the live Post channel with the Drive docs named only as the dated container set. But the corpus cannot currently tell a reader which, and the two layers assert opposite things about the same 15 sources. Nothing records the change: `CORRECTIONS_LOG.md`, `KNOWN_UNCERTAINTIES.md`, `METHODOLOGY_AUDIT_2026-10-02.md` and `PR5_REVIEW_2026-10-02.md` are all silent, though the corrections log's own closing rule requires recording exactly this kind of reversal.

**Needed:** decide and write down whether the quarantine is void. If it is, update the 15 records and log what was gained. If the citations are metadata-only, mark them so at each site and keep the quarantine. Either way, name the replacement held-out set — `partition.json` currently describes a protection that no longer exists.

### 3. The chain ends in metadata: 1 of 68 sources has a body in the repo

`claim → BCE → BCS → native/portable source` is the rule in `METHOD.md`, the charter, and `METHODOLOGY_AUDIT`. The last hop resolves for one source.

67 of 68 catalog records have `"portable_snapshot": null`. The only portable snapshot is `evidence/sources/BCS-000068-retrospective-self-report-2026-10-01-02.md`, which is present and good. Every other record locates its source only in a ChatGPT Library path or a Drive ID — 51 catalog-referenced paths that do not exist in the repository. `sources/`, `context/`, `campaigns/` and `indexes/` each contain nothing but a README.

The two Discord harvests are the real exception and they carry the live-play side well; what is missing is the entire prep, revision and document side. The charter's success condition is that "a future researcher or Kit can locate the source" — for 67 of 68 that currently depends on Brendon's connector access rather than on the archive.

The project diagnosed this precisely and the fix is written and tested. It needs a machine with the staging ZIP on disk and authenticated git write access, which is an environment problem rather than a research problem. **This remains the highest-value unblocking action in the corpus.**

### 4. The evaluation layer sets a higher evidentiary standard than the method describes

This is a finding in the corpus's favour that nonetheless needs acting on.

`6c-rerun2-2026-10-03/SCORECARD.md` names the exact commit of both heads under test, reports the suite count on each (450 and 492), tracks every check as FIXED / STILL / NEW against the previous rerun, runs engine probes on both heads so each claim can be checked independently, preserves every DM reply attempt including rejected ones, names its own auto-grader's false positives, separates blockers from agreed follow-ups, and states plainly that nothing was merged. It then volunteers the fact that undercuts its own headline: "I reused the previous rerun's committed DM replies… Rejection counts and DM latency are therefore not comparable." It discloses a Kit-side change made mid-run, and separates nondeterministic card deals from deterministic damage parsing. `table-calls-6c` goes further and specifies an actual ablation (TC-3c: remove the ruse objective from the carrier and require the NPC lines to change, or the objective is decoration).

That is per-claim evidence, differential comparison across runs, independent probes, and ablation — a stronger standard than the historical research applies to itself, where `confidence` is a single prose word (finding 7). The corpus has two halves running two different methods, and only the weaker one is written down. `METHOD.md` says nothing about evaluation design, and `METHODOLOGY_AUDIT_2026-10-02.md` does not mention the evaluation program at all.

**Needed:** fold the evaluation discipline into `METHOD.md` as a named layer with its own standards, so it survives a change of executor and so the historical passes can borrow from it. The practice already exists; it is the documentation that is missing.

### 5. Checksums exist, but not in the file that asserts provenance

`research/legacy-staging/manifest.all.jsonl` carries `original_sha256` and `normalized_sha256` for all 51 legacy containers. `evidence/catalog.jsonl` carries no checksum field on any of its 68 records, though the charter lists checksums among what must be preserved. BCS-000001–000016 have no checksum anywhere in the corpus. The integrity data is one file away from the registry that needs it.

### 6. Thirty-three Drive sources are used as evidence without source containers

Of 54 distinct Drive IDs cited across the research prose, 33 appear nowhere in `evidence/catalog.jsonl` — concentrated in `source-leads/homebrew-mechanics-worldbuilding.md` (16), `CHRONOLOGY.md` (10), `empire-city/source-fragment-map-v1.md` (8) and `empire-city/longitudinal-decision-cases-v1.md` (4), including load-bearing S4 sources such as the Hampstead info doc, the Kingsbridge first draft, *The Red Coats*, the Ferrytown master doc and the S4 Master Timeline.

The charter says derived research "should cite evidence/source IDs rather than inventing a parallel provenance system," and `REPO_HYGIENE.md` requires checking the manifest and catalog before adding a source. Bare Drive IDs are traceable and better than nothing, but the effect is that the catalog describes a smaller corpus than the one already in use.

### 7. The two-axis discipline is absent from the layer it exists to constrain

Separating evidence confidence from claim scope is the central methodological idea in `METHOD.md`: "High confidence never silently widens scope."

No case record carries a scope field. `confidence` is freeform prose and across the 42 S3 records reads 38 × `high`, 2 × `medium-high`, 1 × `very-high`, 1 × `high, with causal caveat` — nothing below medium-high, and the `DIRECT / STRONGLY_RECONSTRUCTED / SUGGESTIVE / UNRESOLVED` ladder appears nowhere outside `METHOD.md`. A field with one value carries no information; as written, `confidence` cannot distinguish a message Brendon typed from a reconstruction of why he typed it.

The labels *are* used well in the synthesis prose — `roanoke-s3-to-s4-judgment-v1.md` carries separate "Persistence confidence" and "Generalization scope" on each finding and refuses to promote any past "cross-campaign candidate." So the discipline lives at the top layer and is missing underneath, which is the wrong way round: the synthesis is where scope creep gets caught, the cases are where it starts. `CHRONOLOGY.md` already notes case records should carry an `era`/date field; they don't. Three case schemas are in use and `decision-cases-v1.jsonl` has no `schema` field at all.

### 8. S3's live window is stated as settled where the registry says it isn't

`registry/projects.jsonl` gets this right: the S3 record carries `"boundary_status": "RESEARCHED_LIVE_ARCHIVE_WINDOW"` and a basis reading "Treat it as the researched live window, not proof that no campaign activity existed outside the harvest," and `registry/discord_servers.jsonl` marks the harvest `HARVESTED_REQUESTED_WINDOW` with requested and observed windows stored separately.

The human-readable layer drops the qualifier: `CHRONOLOGY.md` heads a flat date range "Roanoke Season 3 live window", `SOURCE_COVERAGE.md` says "time window", `STATUS.md` and `RESEARCH_STATE.json` say "window". The harvest README shows why it matters — the requested window was 2020-07-18 → 2020-08-22 and I confirmed against the database that the earliest and latest messages sit exactly on those boundaries (`2020-07-18T15:09:44.724Z`, `2020-08-22T06:59:43.567Z`), which is the signature of truncation at the request edge rather than of a campaign that happened to start and stop there.

`KNOWN_UNCERTAINTIES.md` lists the live windows for Seasons 2 and 5 and the S4 close as unresolved. S3 is not listed. This is the same inference the corpus explicitly refuses to make for S4, and S3 is the densest dataset, so this window frames more claims than any other date in the archive — including the coverage argument about S3 density.

### 9. Season 4 has no machine-readable layer

S3's 42 cases ship as prose and JSONL with exact parity. The 25 S4 cases exist only as Markdown. `STATUS.md` calls the S4 longitudinal file "the strongest current evidence for how S4 decisions actually changed over time," and it is the one body of cases that cannot be queried, diffed, validated or exported without re-parsing prose. The Markdown is well structured and the extraction would be straightforward.

### 10. The artifact register covers 8 of the 470 files in the largest research directory

`research/kit-evaluation/` now holds 470 files — 470 of the 548 files under `research/`, making the evaluation program the majority of the research layer by file count. `ARTIFACT_REGISTER.md` lists 128 artifacts in total, eight of them under `kit-evaluation/`. The four 6c run directories, their scorecards, probes, per-scenario transcripts, DM helper scripts, the table-calls record, the failure-localization record, the persona-continuity eval and the variety sheets are all uninventoried.

Two smaller instances of the same drift: `evidence/EVIDENCE.md` documents BCE-000001 through BCE-000013 and omits BCE-000014, which is present in `evidence.jsonl` and which `PR5_REVIEW` records as having been added to machine state; and `kit-evaluation/README.md` lists three current records for a directory holding far more. `REPO_HYGIENE.md` already says these are navigation snapshots to refresh at deliberate checkpoints and that they "should never become a second source of truth." The rule is right; the checkpoint is what slipped. Findings 2, 8 and 10 are all this same failure mode.

### 11. The coordination layer is large enough to be its own drift surface

Nine files hold overlapping state and handoff material — `STATUS.md`, `RESEARCH_STATE.json`, `INDEX.md`, `PROJECT_MAP.md`, `PROJECT_DECISIONS.md`, `NEXT_HANDOFF.md`, `HANDOFF_AND_BACKLOG.md`, `ARTIFACT_REGISTER.md`, `QUESTIONS.md` — about 61 KB against 402 KB of substantive research. Each restates status, next steps or inventory recorded elsewhere, so each is a place the record can disagree with itself. Consider collapsing to one human handoff plus one generated state file, with everything else pointing at them.

### 12. The negative-space pass is still unwritten

`METHOD.md` requires deliberately sampling restraint, `working-model-2026-10-01.md` §6 says the current cases over-sample intervention, and `HANDOFF_AND_BACKLOG.md` §B schedules the pass. No artifact exists.

By title, about five or six of the thirty S3 decision cases turn on restraint — a declined hook allowed to reach its failure state, players choosing granularity, accommodation stopping, DM knowledge withheld, control released, an authored week deliberately decompressed. The rest are interventions. The corpus therefore currently teaches that noticing implies acting, which is the exact bias `METHOD.md` warns would make Kit constantly "improve" functioning play. It deserves promotion out of the backlog, because it is the one gap that shows up directly in how Kit behaves at the table.

## Suggested order

1. Register the table calls as BCS/BCE/BCR (finding 1). Highest value for the least work, and it closes the current-practice gap every other document complains about.
2. Resolve the Empire City quarantine contradiction and log it (finding 2).
3. Run the reconciler to land the 51 source bodies and 284 record files (finding 3). Needs a machine with the ZIP and git write access.
4. Write the evaluation layer into `METHOD.md` as a named layer with its own standards (finding 4).
5. Propagate the manifest checksums into the catalog; open containers for the 33 orphan Drive sources (findings 5, 6).
6. Add `scope`, `era`/date and an enumerated `confidence` to the case schemas and backfill (finding 7).
7. Restore the S3 window qualifier in the four prose and state files, and add the S3 boundary to `KNOWN_UNCERTAINTIES.md` (finding 8).
8. Emit S4 JSONL; regenerate the artifact register over the real tree; collapse the coordination layer; run the negative-space pass (findings 9, 10, 11, 12).

Findings 1, 2, 7 and 8 change what the corpus claims and were deliberately left to Brendon and GPT rather than patched by a reviewer.

## What this review could not check

The Empire City harvest was not pulled, so S4 message-ID citations were confirmed well formed but not resolved against `empire-city.sqlite` the way the S3 ones were. The 51 legacy source bodies are not in the tree (finding 3), so their manifest checksums could not be verified against real files. Discord attachments were left as LFS pointers. Claims about Drive documents rest on the research prose, since no Drive body is in the repository.

## Reproduction

From a clone of `radarsaint/bfdm-corpus`:

```sh
python3 registry/validate_registry.py
python3 ingest/validate_ingest.py --repo .

# evidence-layer integrity and source-body coverage
python3 - <<'PY'
import json
load=lambda p:[json.loads(l) for l in open(p) if l.strip()]
cat,ev,rel=load('evidence/catalog.jsonl'),load('evidence/evidence.jsonl'),load('evidence/relations.jsonl')
bcs={r['corpus_id'] for r in cat}; bce={r['evidence_id'] for r in ev}
print(len(bcs),'BCS',len(bce),'BCE',len(rel),'BCR')
print('dangling:',[r['relation_id'] for r in rel if r['from_id'] not in bcs|bce or r['to_id'] not in bcs|bce])
print('no body:',sum(1 for r in cat if not r.get('portable_snapshot')),'/',len(cat))
print('checksums:',sum(1 for r in cat if 'sha256' in json.dumps(r)))
PY

# finding 1: the evidence layer does not know the table calls exist
grep -c 'kit-evaluation\|table.call' evidence/*.jsonl

# finding 7: confidence carries one value, scope carries none
python3 - <<'PY'
import json,collections,glob
c=collections.Counter(); scope=False
for p in glob.glob('research/roanoke-s3/*.jsonl'):
    for l in open(p):
        if l.strip():
            r=json.loads(l); c[str(r.get('confidence')).strip().rstrip('.').lower()]+=1
            scope |= 'scope' in r
print(dict(c),'scope field present:',scope)
PY

# citations resolved against the real harvest (needs the LFS object)
git lfs pull --include="discord/roanoke-season-3/roanoke-season-3.sqlite"
python3 - <<'PY'
import sqlite3,re,glob,collections
db=sqlite3.connect('discord/roanoke-season-3/roanoke-season-3.sqlite'); c=db.cursor()
ids=set()
for p in glob.glob('research/roanoke-s3/*.md'):
    ids |= set(re.findall(r'\b\d{17,19}\b', open(p,encoding='utf-8').read()))
n=collections.Counter()
for i in ids:
    c.execute("SELECT author_id FROM messages WHERE id=?", (i,)); r=c.fetchone()
    n['brendon' if r and r[0]=='313689699627696139' else 'other' if r else 'unresolved']+=1
print(len(ids),'cited:',dict(n))
PY
```
