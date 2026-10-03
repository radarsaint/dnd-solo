"""PR A item 8 (live 6c, 2026-10-03): the narration's cards and mark counts must match the
running table. Live, Kit said "one prick on your four" when the marks give a four three."""
import json
import unittest
from pathlib import Path

from runtime import kit_agent, kit_twenty_one
from runtime.state_context import InvalidChange

ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / 'tests' / 'fixtures' / 'level_01_area_06c.json').read_text())
CONFIG = SOURCE['procedures']['twenty_one']
PUBLIC = {'round': {'cards': ['10 of clubs', '4 of spades'], 'dealer_shows': 'ace of hearts', 'phase': 'play'}}
LIVE = ('Tilted to the candle, the backs give it up. The faded vine border has tiny pinpricks worked into it '
        'near one corner, one on your four, a tidy row of them on your ten.')


class MarkCountTests(unittest.TestCase):
    def test_the_scheme_is_value_less_one(self):
        self.assertEqual([kit_twenty_one.mark_count(CONFIG, r) for r in ('2', '4', '10', 'king', 'ace')],
                         [1, 3, 9, 9, 10])

    def test_the_live_miscount_is_caught(self):
        problems = kit_twenty_one.check_narration(LIVE, PUBLIC, CONFIG)
        self.assertEqual(len(problems), 1)
        self.assertIn('4', problems[0])

    def test_right_counts_pass(self):
        for text in ('Three pinpricks on your four, nine on your ten.',
                     'The border is pricked: three on your four.',
                     'Eight pricks along its vine border.',  # no card named: nothing to check
                     'Four pricks on the corner of the dealer\'s hidden card.'):
            with self.subTest(text=text):
                self.assertEqual(kit_twenty_one.check_narration(text, PUBLIC, CONFIG), [])

    def test_a_count_after_the_unit_word(self):
        self.assertTrue(kit_twenty_one.check_narration('Two pricks on the ten of clubs.', PUBLIC, CONFIG))


class CardValueTests(unittest.TestCase):
    def test_named_cards_must_be_on_the_table(self):
        self.assertEqual(kit_twenty_one.check_narration(
            'You hold the ten of clubs and the four of spades; he shows the ace of hearts.', PUBLIC, CONFIG), [])
        self.assertTrue(kit_twenty_one.check_narration('The six of hearts lands in front of you.', PUBLIC, CONFIG))

    def test_your_card_must_be_held(self):
        self.assertTrue(kit_twenty_one.check_narration('Your five looks lonely.', PUBLIC, CONFIG))
        for text in ('Your four looks lonely.', 'Fourteen, and your fourteen is weak.', 'Keep your ten gold.',
                     'Your two cards sit face down.'):
            with self.subTest(text=text):
                self.assertEqual(kit_twenty_one.check_narration(text, PUBLIC, CONFIG), [])

    def test_no_round_no_card_check(self):
        self.assertEqual(kit_twenty_one.check_narration('The six of hearts.', {'round': None}, CONFIG), [])

    def test_the_performance_check_rejects_a_miscount(self):
        view = {'table_procedures': {'twenty_one': PUBLIC}}
        configs = {'twenty_one': CONFIG}
        with self.assertRaises(InvalidChange):
            kit_agent.check_table_narration([{'speaker': 'Narrator', 'text': LIVE}], view, configs)
        kit_agent.check_table_narration([{'speaker': 'Narrator', 'text': LIVE.replace('one on', 'three on')}],
                                        view, configs)


if __name__ == '__main__':
    unittest.main()
