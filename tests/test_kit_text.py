"""Shared spoken quantities: shop counts and card ranks use one word list."""
import unittest

from runtime import kit_appraise, kit_cards, kit_text


class SharedQuantityTests(unittest.TestCase):
    def test_shop_count_is_the_appraise_helper(self):
        self.assertIs(kit_appraise.leading_count, kit_text.leading_count)
        self.assertEqual(kit_text.leading_count('a dozen potions'), (12, 'potions'))
        self.assertEqual(kit_text.leading_count('20 healing potions'), (20, 'healing potions'))
        self.assertIsNone(kit_text.leading_count('zero potions'))
        self.assertIsNone(kit_text.leading_count('potion of healing'))

    def test_card_ranks_stop_at_thirteen(self):
        self.assertEqual(kit_text.card_number('eight'), 8)
        self.assertEqual(kit_text.card_number('13'), 13)
        self.assertNotIn('fourteen', kit_text.CARD_WORDS)
        self.assertNotIn('zero', kit_text.CARD_WORDS)
        self.assertEqual(kit_cards.parse_card('I play the red eight', [('red', 8), ('black', 10)]), ('red', 8))
        self.assertEqual(kit_cards.parse_card('red 8', [('red', 8), ('black', 8)]), ('red', 8))


if __name__ == '__main__':
    unittest.main()
