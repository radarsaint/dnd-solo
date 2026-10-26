"""#150 retest-2 (fuzz-driven) router lines: searches win, negations drop, plain looks, asides."""
import unittest

from runtime.kit_agent import room_intent


class RetestTwoRouting(unittest.TestCase):
    def test_lines(self):
        cases = {
            'Can I investigate the door?': 'search',
            'Let me search the lid.': 'search',
            'I pat down the wall, testing it for a hollow.': 'search',
            'What do I see?': 'observe',
            'Describe the floor.': 'observe',
            'I eye the flagstones.': 'observe',
            'What a strange place.': 'social',
            'Hmm.': 'social',
            'Hey scribe, nice handwriting.': 'social',
            'Hmm, ten minutes is long. Never mind.': 'social',
            'I attack the brazier.': 'unsupported_action',
            'I shoot the breeze with Morwen.': 'social',
            'I set my torch down.': 'unsupported_action',
        }
        for line, kind in cases.items():
            with self.subTest(line):
                self.assertEqual(room_intent(line), kind)

    def test_a_negated_clause_is_dropped(self):
        self.assertNotEqual(room_intent("I don't search the rubble. I wait."), 'search')


if __name__ == '__main__':
    unittest.main()
