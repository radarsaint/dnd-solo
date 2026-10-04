# Brendon's DM decisions — extraction batch 1

**Status:** evidence collection and review candidates. No training, runtime personality update, live playtest or completed held-out evaluation.

The earlier personality work and pilot were published in [PR #23](https://github.com/radarsaint/dnd-solo/pull/23) before extraction began. This batch starts from main `4f4f0a3`, after reading Skippy's collaboration board and runtime handoff. It follows Brendon's decision-extraction brief; prose imitation is not the target.

## What is here

| Artifact | Contents |
| --- | --- |
| [Source index](SOURCE_INDEX.md) · [JSON](source-index.json) | 53 imported files plus 10 source/report/model entries; dates, attribution, reliability and partitions |
| [Decision records](DECISIONS.md) · [JSONL](decisions.jsonl) | 23 records across seven named families, with explicit vs inferred reasoning |
| [Negative/preference records](preferences.jsonl) | 8 evidenced rejections or design preferences; none is a complete approved response pair |
| [Trait evidence](TRAITS.md) · [JSON](trait-evidence.json) | 6 hypotheses, independent-project counts, dates, limits and tensions |
| [Contradictions and provenance corrections](CONTRADICTIONS.md) | Unresolved priorities, misattribution risks and corrected source dates |
| [Current-model audit](MODEL_AUDIT.md) | All 12 current drives reviewed, plus proposed changes for testing |
| [Evaluation partition](evaluation/partition.json) | 15 Empire City files quarantined prospectively; quality/attribution review pending |
| [Blind A/B probes](evaluation/BLIND_AB.md) | 3 newly authored development probes, with no Brendon preference labels |
| [Dataset card](DATASET_CARD.md) | Runtime fit, schema meaning, source limits and why this is not yet a fine-tuning dataset |
| [Short raw excerpts](evidence-excerpts.json) | Exact fragments with native comment/revision locators |
| [Working protocol](PROTOCOL.md) | Evidence hierarchy, four-layer separation and extraction constraints |

Eleven records use directly attributed comments or a revision comparison. Seven use documented Kit feedback. Five use earlier semantic retrieval and remain leads. Brendon authors the evidenced decisions; the analyst authors these records and generalizations.

## Findings worth testing

- **Depth depends on engagement.** The card game was first too shallow to make cheating matter, then too dominant when the player wanted another interaction. K02/K03 should be taught together.
- **An encounter's point must become perceptible.** A functioning hand of cards did not make the room's significance evident. K04 preserves the actual criticism without claiming it demands one secret or route.
- **Performance has a purpose.** Novel comments request grandstanding for a missed character beat, but also resist effortless superiority. N03/N04 challenge a simple “more theatrical” slider.
- **Adaptation has unresolved limits.** A Roanoke comment protects identifiable magical constraints; an Earthfall report accepts a bypass. R01/E01 do not yet yield an absolute hierarchy.

## Provenance improvement

The original Drive comments establish Brendon as the author of specific Roanoke and novel decisions. A revision comparison shows the sparse-preparation diagnosis added to Roanoke's change log. The unattributed guards postmortem is excluded from Brendon records. Several earlier novel-note dates were corrected using comment creation times.

Only short private-source quotations are reproduced here. Original campaign documents, full comment threads and revision bodies remain at the indexed sources. Imported file dates do not establish when the material was written.

## Next extraction increment

1. Recover complete attributed conversation windows for the five retrieval leads and more direct Kit corrections.
2. Establish who authored the Roanoke postmortem, FAQ procedures, and other season material; keep alternate versions together.
3. Find matched cases that resolve preparation versus bypass, challenge versus fairness, and humor versus emotional weight.
4. Freeze the discovery model at a commit, then curate strong, attributable Empire City judgments and remove duplicates or earlier-exposed snippets before constructing held-out situations.
5. Collect blind preferences, retain disagreements, and only then propose an approved policy update or training adapter.

The source collection is not exhausted. The current personality and Skippy's implementation choices remain hypotheses or project guidance, not independent historical evidence.


## Validation

Checked JSON/JSONL parsing, required evidence fields, authorship labels, all decision-to-source and trait-to-record references, unique IDs, project counts, local document links, and evaluation partition isolation. No reserved source supports a discovery record. All preference labels remain unapproved and all model-execution flags remain false. Runtime files are unchanged; this was data validation, not a new runtime or model test.
