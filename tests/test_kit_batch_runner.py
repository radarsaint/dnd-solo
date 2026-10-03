import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('kit_batch_runner', ROOT / 'scripts' / 'kit_batch_runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

from runtime import kit_cards  # noqa: E402


class BatchRunnerTests(unittest.TestCase):
    def test_roll_report_is_parsed_by_the_engine_as_die_plus_bonus(self):
        text, note = runner.roll_text({'skill': 'deception', 'total': 22}, {'skills': {'deception': 10}})
        self.assertEqual(kit_cards.supplied_roll(text), (12, 10))
        self.assertEqual(note, '')

    def test_impossible_scripted_total_is_clamped_and_noted(self):
        text, note = runner.roll_text({'skill': 'persuasion', 'total': 9}, {'skills': {'persuasion': 10}})
        self.assertEqual(kit_cards.supplied_roll(text), (1, 10))
        self.assertIn('clamped', note)

    def test_digest_replaces_only_long_unchanged_fields(self):
        ref = {'instructions': 'x' * 500, 'input': {'a': 'y' * 300, 'b': 1}}
        new = {'instructions': 'x' * 500, 'input': {'a': 'z' * 300, 'b': 1}}
        out = runner.dedupe(new, ref)
        self.assertEqual(out['instructions'], '=ref')
        self.assertEqual(out['input']['a'], 'z' * 300)
        self.assertEqual(out['input']['b'], 1)

    def test_runner_refuses_play(self):
        with self.assertRaises(SystemExit):
            runner.kit('play')

    def test_child_env_never_carries_the_api_key(self):
        import os
        os.environ['OPENAI_API_KEY'] = 'sk-test'
        try:
            self.assertNotIn('OPENAI_API_KEY', runner.child_env())
        finally:
            del os.environ['OPENAI_API_KEY']

    def test_scenarios_load_and_every_sheet_resolves(self):
        spec_ = json.loads((ROOT / 'tests' / 'scenarios' / '6c_variety.json').read_text())
        self.assertEqual([s['id'] for s in spec_['scenarios']], [f'V{i}' for i in range(1, 12)])
        local = {p.name for p in (ROOT / 'tests' / 'fixtures' / 'characters').glob('*.json')}
        for s in spec_['scenarios']:
            self.assertTrue(s['turns'])
            if s['sheet'] in local:
                self.assertTrue(runner.find_sheet(s['sheet'], []).exists())


if __name__ == '__main__':
    unittest.main()
