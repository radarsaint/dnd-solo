"""Model-free phrase fuzz (tools/kit_fuzz.py): every line in tests/corpus/player_lines.jsonl runs
prepare -> complete on the synthetic SRD rooms in tests/fixtures/fuzz/ (plus the crypt), with
Kit's decision stubbed and dice pinned, and every public output is scanned for leaks.

Failures already listed in tests/corpus/known_failures.json (id -> cause, measured on #150's
head) are expected; a failure not listed fails this test. A listed case that now passes is
printed so the list can be trimmed. Runs in a few seconds; pytest and unittest both collect it."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import kit_fuzz  # noqa: E402
import kit_replay  # noqa: E402


class PhraseFuzz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = kit_fuzz.run_corpus()
        cls.known = kit_fuzz.load_known()

    def test_corpus_is_big_and_well_formed(self):
        cases = kit_fuzz.load_corpus()
        self.assertGreaterEqual(len(cases), 400)
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        for case in cases:
            self.assertIn(case['room'], kit_fuzz.ROOMS)
            self.assertTrue(set(case['expect']) <= set(kit_fuzz.OUTCOMES), case['id'])

    def test_no_new_failures(self):
        new = [f"{r['id']} {r['line']!r}: {'; '.join(r['failures'])}" for r in self.results
               if not r['ok'] and r['id'] not in self.known]
        fixed = [r['id'] for r in self.results if r['ok'] and r['id'] in self.known]
        if fixed:
            print(f'\n{len(fixed)} known failures now pass (trim known_failures.json): {", ".join(fixed)}')
        self.assertEqual(new, [], 'new fuzz failures (not in tests/corpus/known_failures.json)')

    def test_known_list_has_no_stale_ids(self):
        ids = {r['id'] for r in self.results}
        self.assertEqual(sorted(set(self.known) - ids), [])


class LeakScanner(unittest.TestCase):
    """The scanner itself: it must catch the #150 retest-3 Detect Magic leak (the public line
    named a hidden buried ring and where it lay) and must not flag a fact the engine revealed."""

    def setUp(self):
        self.harness = kit_fuzz.Harness(rooms={'vault': kit_fuzz.ROOMS['vault']})
        self.addCleanup(self.harness.close)

    def run_line(self, line, **kw):
        return self.harness.run({'id': 't', 'line': line, 'room': 'vault', 'expect': list(kit_fuzz.OUTCOMES), **kw})

    def test_scanner_flags_a_hidden_object_named_in_public(self):
        secrets = self.harness.secrets['vault']
        leaks = kit_fuzz.scan('The auras cling to a zircon signet ring buried under the rubble in the south corner.', secrets)
        self.assertTrue(any('zircon_ring' in leak for leak in leaks), leaks)
        self.assertTrue(kit_fuzz.scan('The DC is 14.', secrets))
        self.assertEqual(kit_fuzz.scan('You sense a magical aura (abjuration).', secrets), [])

    def test_a_revealed_fact_is_not_a_leak(self):
        secrets = self.harness.secrets['vault']
        text = 'A zircon signet ring lies buried under the rubble in the south corner.'
        self.assertEqual(kit_fuzz.scan(text, secrets, allowed=[text]), [])

    def test_the_players_own_words_are_not_a_leak(self):
        self.assertEqual(self.run_line('I search the rubble for the ring.')['leaks'], [])

    def test_detect_magic_names_no_hidden_object(self):
        self.assertEqual(self.run_line('I cast detect magic.')['leaks'], [])


class Replay(unittest.TestCase):
    """tools/kit_replay.py reruns a playtest's player lines (pr150c, genericized) in order."""

    def test_extract_finds_player_lines_only(self):
        lines = kit_replay.extract('Fresh: "I sift through the bones." -> "You declare: x"; roll "1d20 (5) + 4 = 9".')
        self.assertEqual(lines, ['I sift through the bones.', '1d20 (5) + 4 = 9'])

    def test_pr150c_replay_matches_its_stored_outcomes(self):
        fixture = json.loads((ROOT / 'tests/fixtures/replay/pr150c.json').read_text(encoding='utf-8'))
        results = kit_replay.replay(fixture)
        self.assertEqual([r['outcome'] for r in results], fixture['outcomes'])
        self.assertEqual([r['leaks'] for r in results if r['leaks']], [])


if __name__ == '__main__':
    unittest.main()
