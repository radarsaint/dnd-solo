"""Shared spoken quantities: shop counts and card ranks use one word list."""
import unittest

from runtime import kit_appraise, kit_cards, kit_text
from runtime.goldscale.parser import find_quantity, parse_item_text


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

    def test_one_grammar_for_shop_and_goldscale(self):
        samples = (
            ('3 torches', 3, 'torches'),
            ('three torches', 3, 'torches'),
            ('qty 3 torch', 3, 'torch'),
            ('quantity: 3 torch', 3, 'torch'),
            ('a dozen arrows', 12, 'arrows'),
            ('pair of daggers', 2, 'daggers'),
            ('torches x3', 3, 'torches'),
            ('torches x 3', 3, 'torches'),
        )
        for text, count, rest in samples:
            self.assertEqual(kit_text.parse_quantity(text), (count, rest), text)
            self.assertEqual(find_quantity(text), count, text)
            self.assertEqual(parse_item_text(text).quantity, count, text)

    def test_charges_bonus_and_articles_are_not_stacks(self):
        self.assertIsNone(kit_text.leading_count('7 charges'))
        self.assertIsNone(kit_text.parse_quantity('7 charges'))
        self.assertIsNone(find_quantity('wand of fireballs rare wand 8d6 aoe 7 charges'))
        self.assertIsNone(parse_item_text('wand of fireballs rare wand 8d6 aoe 7 charges').quantity)
        self.assertIsNone(find_quantity('+1 longsword'))
        self.assertIsNone(find_quantity('a torch'))
        self.assertEqual(kit_text.parse_quantity('a torch'), (1, 'torch'))
        self.assertEqual(find_quantity('qty 1 torch'), 1)
        self.assertEqual(find_quantity('sell qty 2 +1 sword uncommon weapon'), 2)

    def test_quantity_phrase_leaves_the_item_name(self):
        self.assertEqual(parse_item_text('3 torches').item_name, 'Torches')
        self.assertEqual(parse_item_text('torches x3').item_name, 'Torches')
        self.assertEqual(parse_item_text('qty 2 +1 sword uncommon weapon').item_name, '+1 Sword')
        wand = parse_item_text('wand of fireballs rare wand 8d6 aoe 7 charges')
        self.assertEqual(wand.item_name, 'Wand of Fireballs')
        self.assertEqual(wand.charges, 7)


if __name__ == '__main__':
    unittest.main()
