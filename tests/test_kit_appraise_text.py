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


class NameMatchTests(unittest.TestCase):
    def test_plural_article_and_unique_misspelling(self):
        torch = {'item': 'Torch', 'quantity': 1, 'price': 1, 'unit': 'cp', 'source': 'srd', 'mode': 'buy'}
        self.assertEqual(kit_appraise.read_items('torches'), [torch])
        self.assertEqual(kit_appraise.read_items('a torch'), [torch])
        self.assertEqual(kit_appraise.read_items('the torches'), [torch])
        self.assertEqual(kit_appraise.read_items('troch'), [torch])
        self.assertEqual(kit_appraise.read_items('longsowrd')[0]['item'], 'Longsword')
        self.assertEqual(kit_appraise.read_items('dager')[0]['price'], 2)

    def test_same_bonus_either_order(self):
        left = kit_appraise.read_items('+1 longsword uncommon weapon')
        right = kit_appraise.read_items('longsword, +1 uncommon weapon')
        bare = kit_appraise.read_items('+1 longsword')
        flipped = kit_appraise.read_items('longsword, +1')
        self.assertEqual(left, right)
        self.assertEqual(left[0]['price'], 1200)
        self.assertEqual(bare[0]['item'], flipped[0]['item'])
        self.assertEqual(bare[0]['item'], '+1 Longsword')
        self.assertIsNone(bare[0]['price'])
        self.assertNotEqual(bare[0]['price'], 15)

    def test_unknown_item_is_not_a_neighbor(self):
        for line in ('blorbo', 'a sword', 'a rope', 'flaming cheese'):
            row = kit_appraise.read_items(line)[0]
            self.assertEqual(row['item'], 'unknown item', line)
            self.assertIsNone(row['price'], line)
        rope = kit_appraise.read_items('price a rope and two torches')
        self.assertEqual(rope[0]['item'], 'unknown item')
        self.assertEqual(rope[1]['item'], 'Torch')
        self.assertEqual((rope[1]['quantity'], rope[1]['price'], rope[1]['unit']), (2, 2, 'cp'))

    def test_listed_rate_not_a_rounded_guess(self):
        one = kit_appraise.read_items('1 sling bullet')[0]
        self.assertEqual(one['item'], 'Sling bullet')
        self.assertIsNone(one['price'])
        five = kit_appraise.read_items('5 sling bullets')[0]
        self.assertEqual((five['price'], five['unit']), (1, 'cp'))

    def test_goldscale_prices_stay_put(self):
        rows = {
            'how much are 3 healing potions?': ('Potion of Healing', 3, 210),
            "what's a potion of healing worth?": ('Potion of Healing', 1, 70),
            'sell a potion of healing': ('Potion of Healing', 1, 35),
            'wand of fireballs rare wand 8d6 aoe 7 charges': ('Wand of Fireballs', 1, 157000),
            'sell qty 2 +1 sword uncommon weapon': ('+1 Sword', 2, 1200),
            'cloak of protection uncommon cloak +1': ('Cloak of Protection', 1, 1400),
        }
        for line, (item, quantity, price) in rows.items():
            got = kit_appraise.read_items(line)[0]
            self.assertEqual((got['item'], got['quantity'], got['price']), (item, quantity, price), line)
            self.assertEqual(got['source'], 'goldscale', line)


if __name__ == '__main__':
    unittest.main()
