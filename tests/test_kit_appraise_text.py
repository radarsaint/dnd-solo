"""Question shells around a shop or appraisal line."""
import unittest

from runtime import kit_appraise


class StripQuestionTests(unittest.TestCase):
    def test_question_shells_leave_the_item(self):
        cases = {
            'how much for a torch': 'torch',
            "what's a torch worth": 'torch',
            "what's a torch worth?": 'torch',
            'price check on a torch': 'torch',
            'can I sell my torch': 'sell torch',
            'can I sell my torch?': 'sell torch',
            "what's a potion of healing worth?": 'potion of healing',
            'how much are 3 healing potions?': 'qty 3 potion of healing',
            'how much could I sell a potion of healing for?': 'sell potion of healing',
        }
        for line, want in cases.items():
            self.assertEqual(kit_appraise.strip_question(line), want, line)

    def test_typos_and_trailing_punctuation(self):
        self.assertEqual(kit_appraise.strip_question('hw much for 3 torches?'), 'qty 3 torches')
        self.assertEqual(kit_appraise.strip_question('prise check on torches...'), 'torches')
        self.assertEqual(kit_appraise.strip_question('whats a potion of healing wroth'), 'potion of healing')
        self.assertEqual(kit_appraise.strip_question('how much for...'), 'how much for...')

    def test_two_items_in_one_line(self):
        self.assertEqual(
            kit_appraise.strip_question('price a rope and two torches'),
            'rope and qty 2 torches')
        self.assertEqual(
            kit_appraise.strip_question('price a rope, two torches.'),
            'rope and qty 2 torches')

    def test_comma_bonus_moves_to_the_front_without_moving_a_trailing_bonus(self):
        self.assertEqual(
            kit_appraise.strip_question('longsword, +1 uncommon weapon'),
            '+1 longsword uncommon weapon')
        self.assertEqual(
            kit_appraise.strip_question('cloak of protection uncommon cloak +1'),
            'cloak of protection uncommon cloak +1')

    def test_known_goldscale_lines_still_price(self):
        heal = kit_appraise.price("what's a potion of healing worth?")
        self.assertEqual((heal['item'], heal['final_price'], heal['quantity']), ('Potion of Healing', 70, None))
        many = kit_appraise.price('how much are 3 healing potions?')
        self.assertEqual((many['item'], many['quantity'], many['transaction_total']), ('Potion of Healing', 3, 210))
        moved = kit_appraise.price('longsword, +1 uncommon weapon')
        straight = kit_appraise.price('+1 longsword uncommon weapon')
        self.assertEqual(moved['final_price'], straight['final_price'])
        self.assertEqual(moved['item'], straight['item'])
        cloak = kit_appraise.price('cloak of protection uncommon cloak +1')
        self.assertEqual(cloak['final_price'], 1400)


if __name__ == '__main__':
    unittest.main()
