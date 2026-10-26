# Phrase fuzz and log replay (no model)

Live playtests cost a model bot 10+ turns per bug round. Most of what they find is wording
(a search read as a move, a peek read as entering) or a leak (hidden text in a public line).
Both are found offline in seconds:

```
python3 tools/kit_fuzz.py                  # ~460 lines, ~7 s: table by category and by cause
python3 tools/kit_fuzz.py -v               # also list the known failures
python3 tools/kit_fuzz.py --line "I sift through the rubble." --room vault
python3 tools/kit_replay.py extract /workspace/kit2/<log>.md -o tests/fixtures/replay/<name>.json --room vault
python3 tools/kit_replay.py run tests/fixtures/replay/<name>.json [--update]
python3 -m unittest tests.test_kit_fuzz    # the suite wrapper (pytest collects it too)
```

- **Corpus** `tests/corpus/player_lines.jsonl`: one line per case, `{id, category, room, line,
  expect: [allowed outcomes], ritual?, pending: [skill, ability, target]?, interject?, source}`.
  Outcomes: search (a check called or resolved), look, act, move, attack, spell, social, roll
  (answers a called check), ruling (Kit rules: feature_act / physical_act), clarify (engine asks
  who or what), deferred, refused. Real playtest lines are tagged with their log; the rest are
  paraphrases on SRD-generic objects.
- **Rooms** `tests/fixtures/fuzz/vault.json`, `library.json`, plus `tests/fixtures/rooms/crypt.json`:
  hidden facts with DCs, visible and hidden magic objects, doors, traps (hidden claims), a hidden
  actor.
- **Stub Kit**: `RecordingModel`'s decision plus a neutral two-segment narration. If the engine
  rejects the stub, the line's outcome still counts (it is read from prepare); the reason is kept
  in `notes`.
- **Leak scan**: every public packet field, refusal text and committed player-facing string is
  checked for hidden fact text, hidden claim truths, hidden magic object names/places, hidden
  actor names and DC/AC/to-hit numbers. The player's own words and facts the engine reveals this
  turn (`player_view_after_event`) are allowed.
- **Known failures** `tests/corpus/known_failures.json` (`id -> cause`): expected failures on
  #150's head, so the suite stays green. A failure not listed fails `test_no_new_failures`; a listed
  case that now passes is printed. When a fix lands, rerun and delete the ids it fixed.
- **Replay fixtures** store the outcomes at the time of `--update` (a regression snapshot, bugs
  included); `run` exits 1 when an outcome changes or anything leaks.

The repo is public: genericize adventure names before committing a replay fixture.
