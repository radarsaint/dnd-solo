# Project context status checker

Mechanical check for the shared Project Gardener checkpoint at `coordination/context_state.json`.

The checker does not rewrite `docs/PROJECT_UNDERSTANDING.md`, advance any reconciliation cursor, accept or reject semantic deltas, or open issues. A passing result does not prove that a GPT understands the project.

## Run the checker

From the `dnd-solo` repository root:

```sh
python3 scripts/project_context_status.py
python3 scripts/project_context_status.py --json
```

Online mode reads live `main` SHAs for `radarsaint/dnd-solo` and `radarsaint/bfdm-corpus`, reads dnd-solo issue #115, and reads BFDM `coordination/control.json`. It tries `main` first. If that file is not on `main` yet, it tries `BFDM_CONTROL_FALLBACK_REF` (default `docs/cross-repo-coordination-2026-10-07`) and labels that source as not live main.

Offline mode injects those inputs and does not use the network:

```sh
python3 scripts/project_context_status.py --offline \
  --dnd-sha <40-hex-or-UNAVAILABLE> \
  --bfdm-sha <40-hex-or-UNAVAILABLE> \
  --bfdm-control <path-to-bfdm-coordination/control.json> \
  --issue-fixture <path-to-issue-115-json> \
  --sibling-local-state absent
```

## Run the tests

```sh
python3 -m unittest tests.test_project_context_status -v
```

The fixture tests do not need GitHub. The repository's existing suite remains:

```sh
env -u PYTHONPATH python3 -m unittest discover -s tests -p 'test_*.py'
```

## Status values

Repo SHA status, one per repository:

| Status | Meaning |
|---|---|
| `REVIEWED_CURRENT` | Live `main` SHA matches `checkpoint.reviewed_against_main`, or the live tip is the same tree, or its only path change from the reviewed SHA is `coordination/context_state.json`. That checkpoint file records the review. It is not an undecided semantic advance. |
| `SHA_ADVANCED_REVIEW_NEEDED` | Live `main` moved and the diff was substantive, or the diff could not be inspected. A Gardener must decide whether the new commits change the project model. |
| `UNAVAILABLE` | The live SHA could not be retrieved or was not a commit SHA. |

Top-level classification:

| Classification | Exit | Meaning |
|---|---|---|
| `REVIEWED_CURRENT` | 0 | Local plumbing is intact and no review signal is present. |
| `SHA_ADVANCED_REVIEW_NEEDED` | 0 | At least one repo SHA advanced. Not an automatic claim that the Project Brain is stale or false. |
| `SEMANTIC_DELTAS_PENDING` | 0 | Issue #115 has comment ids newer than the recorded cursor. If a SHA also advanced, `review_signals` lists both. |
| `AUTHORITY_UNAVAILABLE` | 3 | A live SHA, issue #115, or the BFDM pointer could not be checked. Local files may still be intact. |
| `INTEGRITY_FAILURE` | 2 | The checkpoint, bootstrap contract, inbox cursor, or single-cursor rule is broken. |

Semantic inbox status is `CLEAR`, `SEMANTIC_DELTAS_PENDING`, `CURSOR_INTEGRITY_FAILURE`, or `UNAVAILABLE`.

`comment_count_at_checkpoint` is not a cursor. Comment ids newer than `last_fully_reconciled_comment_id` are pending. A null cursor with zero comments is valid. A cursor that is not a known comment id is an integrity failure, and the checker does not guess which deltas are pending. The checker never marks a delta accepted, rejected, or reconciled.

## What a human or GPT should do

`SHA_ADVANCED_REVIEW_NEEDED`: do not edit the Project Brain just because the SHA changed. Inspect the commits that landed after the reviewed SHA. If they do not change what a future collaborator should believe, a Gardener may later record the new reviewed boundary. If they do, update the Project Brain first and only then advance the checkpoint. This script will not do either.

`SEMANTIC_DELTAS_PENDING`: read the unreconciled issue #115 comments. Reconcile each one against live authority. Promote, reject, or leave it unresolved in the Project Brain / checkpoint unresolved list. Advance `last_fully_reconciled_comment_id` only after that decision is durable. This script will not post, close, or advance anything.

`INTEGRITY_FAILURE`: fix the plumbing named in `integrity_failures` before relying on the checkpoint.

The bootstrap contract includes the worker identity gate: step 0 before the Project Brain, identity distinct from tool availability, an ordinary GPT distinguished from Grok Build, ChatGPT Work, and a shell executor, repository work routed to a capable executor, Grok Build as the normal shell executor, Brendon excluded as the routine repository fallback, the action-state names, and a ban on weakening the acceptance condition because the current worker cannot perform it. A passing check does not prove project understanding or worker understanding. `proves_gpt_understanding` and `proves_worker_understanding` stay false.

`AUTHORITY_UNAVAILABLE`: retry when GitHub can be read. Do not treat the gap as semantic staleness.

Exit 0 with a review signal is a successful check that found review work. It is not a green claim that the semantic model was re-approved.
