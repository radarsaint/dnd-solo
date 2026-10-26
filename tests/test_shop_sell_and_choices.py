"""Brendon's rulings for the appraisal tool: selling mundane gear is half the listed
SRD price (Goldscale's own 50% for magic items), and a name that fits a few listed
entries asks which one instead of dead-ending. An unlisted name never guesses."""
import unittest

from runtime import kit_appraise

# (player line, exact reply the player sees)
REPLIES = [
    ('a rope', 'Which one: hempen rope (50 feet) (1 gp) or silk rope (50 feet) (10 gp)?'),
    ('how much is a rope', 'Which one: hempen rope (50 feet) (1 gp) or silk rope (50 feet) (10 gp)?'),
    ('sell my rope', 'Which one: hempen rope (50 feet) (5 sp) or silk rope (50 feet) (5 gp)?'),
    ('can i buy a lantern', 'Which one: bullseye lantern (10 gp) or hooded lantern (5 gp)?'),
    ('hooded lantern', 'hooded lantern costs 5 gp.'),
    ('3 torches', '3 x torch costs 3 cp.'),
    ('sell 5 torches', '5 x torch sells for 2 cp.\nSelling is half the listed price.'),
    ('sell a torch', 'torch sells for less than 1 cp.\nSelling is half the listed price.'),
    ('sell my longsword', 'longsword sells for 7 gp 5 sp.\nSelling is half the listed price.'),
    ('can I sell my dagger', 'dagger sells for 1 gp.\nSelling is half the listed price.'),
    ('three javelins and a dozen arrows', '3 x javelin costs 1 gp 5 sp.\n12 x arrow costs 6 sp.'),
    ('price a rope and two torches',
     'Which one: hempen rope (50 feet) (1 gp) or silk rope (50 feet) (10 gp)?\n2 x torch costs 2 cp.'),
]

# Magic items still go to Goldscale, and sell at Goldscale's own 50%.
GOLDSCALE = [
    ('+1 longsword uncommon weapon', 1200),
    ('sell +1 longsword uncommon weapon', 600),
    ('sell +2 shield rare armor', 2900),
    ('sell potion of healing', 35),
    ('sell qty 3 potion of greater healing', 600),
]


class SellAndChoiceTests(unittest.TestCase):
    def test_player_replies(self):
        for line, want in REPLIES:
            self.assertEqual(kit_appraise.appraise(line), want, line)

    def test_magic_selling_is_goldscale(self):
        for line, total in GOLDSCALE:
            row = kit_appraise.read_items(line)[0]
            self.assertEqual((row['source'], row['price']), ('goldscale', total), line)

    def test_unlisted_name_still_reaches_goldscale(self):
        # Could be homebrew magic: Goldscale asks for the description, nothing is guessed.
        for line in ('potion of vigor', 'a zorb', 'blorbo'):
            self.assertIn('item description', kit_appraise.appraise(line), line)
            self.assertEqual(kit_appraise.read_items(line)[0]['item'], 'unknown item', line)

    def test_vague_word_is_not_a_menu(self):
        # "armor" fits many rows: no list of a dozen choices, no guess.
        self.assertEqual(kit_appraise.read_items('armor')[0]['item'], 'unknown item')

    def test_choices_never_priced_as_one(self):
        row = kit_appraise.read_items('a rope')[0]
        self.assertIsNone(row['price'])
        self.assertEqual([c['item'] for c in row['choices']],
                         ['Rope, hempen (50 feet)', 'Rope, silk (50 feet)'])


if __name__ == '__main__':
    unittest.main()
