"""#122's fallback held to REAL main, not a twin: tests/fixtures/combat_acts_main_fallback.json was
recorded by scripts/combat_acts_main_golden.py run in a checkout of main (its SHA is in the file),
on Nagatha's four playtest cases rebuilt on the synthetic fixture rooms, dice pinned. When Kit
declares no combat acts (the key omitted, null or []), #122 must give main's pending ruling and
leave the state exactly as main left it."""
import json
import unittest
from pathlib import Path

from runtime.kit_agent import KitChatBridge, PendingRuling, pending_ruling_result
from test_kit_combat_acts_slice2 import plan_for

GOLDEN = json.loads((Path(__file__).parent / 'fixtures' / 'combat_acts_main_fallback.json').read_text())


def load_generator():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'combat_acts_main_golden.py'
    spec = importlib.util.spec_from_file_location('combat_acts_main_golden', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FallbackIsRealMains(unittest.TestCase):
    def test_the_golden_was_recorded_on_main(self):
        self.assertEqual(GOLDEN['main_sha'], 'de442cf')
        self.assertEqual(len(GOLDEN['cases']), 4)
        for case in GOLDEN['cases'].values():
            self.assertEqual(case['ruling']['stage'], 'pending_ruling')

    def test_undeclared_is_mains_ruling_and_state(self):
        gen = load_generator()
        for name, case in GOLDEN['cases'].items():
            for declared in ('omitted', None, []):
                with self.subTest(case=name, declared=declared):
                    arena = gen.build(self, case['room'], case['sheet'], case['die'])
                    bridge = KitChatBridge(arena.runtime, arena.adjudicator)
                    packet = bridge.prepare(case['text'], 't', one_pass=True)
                    self.assertIn('combat_acts', packet['input']['private']['acts'], '#122 offers it')
                    plan = plan_for(packet)
                    plan.pop('combat_acts', None)
                    if declared != 'omitted':
                        plan['combat_acts'] = declared
                    with self.assertRaises(PendingRuling) as caught:
                        bridge.complete('t', {'decision': plan, 'performance': {'segments': [
                            {'speaker': 'Narrator', 'text': 'You hold.'}]}})
                    self.assertEqual(pending_ruling_result(caught.exception), case['ruling'])
                    self.assertEqual(json.loads(json.dumps(gen.state_view(arena.runtime))), case['after'])


if __name__ == '__main__':
    unittest.main()
