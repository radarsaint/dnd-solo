"""Stated rolls from Avrae (runtime/kit_rolls.py): the total counts, never the bonus twice."""
import unittest

from runtime import kit_cards, kit_rolls
from runtime.state_context import InvalidChange


class RollParsingTests(unittest.TestCase):
    def test_avrae_line_uses_the_total(self):
        roll = kit_rolls.check_roll('Deception check: 1d20 (12) + 10 = 22')
        self.assertEqual((roll.total, roll.die, roll.modifier, roll.label), (22, 12, 10, 'deception'))
        roll = kit_rolls.check_roll('**Insight**: 2d20kh1 (5, 14) + 4 = `18`')
        self.assertEqual((roll.total, roll.die, roll.label), (18, 14, 'insight'))

    def test_bare_number_is_the_total_and_bonus_is_not_added_twice(self):
        self.assertEqual(kit_cards.supplied_roll('I rolled 17', 4), (13, 4))
        self.assertEqual(kit_cards.supplied_roll('Persuasion 22', 4, 'persuasion'), (18, 4))
        # over 20 is a legal total, not an error
        self.assertEqual(kit_cards.supplied_roll('I rolled 23', 5), (18, 5))

    def test_natural_is_the_die_alone(self):
        self.assertEqual(kit_cards.supplied_roll('natural 17'), (17, None))
        with self.assertRaises(InvalidChange):
            kit_rolls.rolls('nat 25')

    def test_sum_must_add_up(self):
        self.assertEqual(kit_cards.supplied_roll('I rolled 14 + 3 = 17'), (14, 3))
        with self.assertRaises(InvalidChange):
            kit_rolls.rolls('I rolled 14 + 3 = 19')

    def test_labels_attack_initiative_damage(self):
        text = 'Rolling initiative if it comes to that: 8. I rage. Greataxe, 20 to hit, 14 slashing.'
        self.assertEqual(kit_rolls.initiative(text), 8)
        self.assertEqual(kit_rolls.attack_total(text), 20)
        self.assertEqual(kit_rolls.damage(text), [(14, 'slashing')])
        self.assertIsNone(kit_rolls.check_roll(text))
        line = 'I rage and swing my greataxe at the dealer. I rolled 18 to hit, 11 slashing damage.'
        self.assertEqual(kit_rolls.attack_total(line), 18)
        self.assertEqual(kit_rolls.damage(line), [(11, 'slashing')])
        self.assertEqual(kit_rolls.damage('I cast Fireball at the table. 28 fire damage.'), [(28, 'fire')])
        self.assertEqual(kit_rolls.initiative('Initiative 1d20 (12) + 5 = 17'), 17)

    def test_skill_label_before_or_after(self):
        self.assertEqual(kit_rolls.stated_skill('[Deception: I rolled 12 + 10 = 22]'), 'deception')
        self.assertEqual(kit_rolls.stated_skill('I get a 9 on persuasion'), 'persuasion')
        self.assertEqual(kit_rolls.stated_skill('[Sleight Of Hand: I rolled 14 + 7 = 21]'), 'sleight_of_hand')
        self.assertIsNone(kit_rolls.stated_skill('What does the initiative order look like?'))


if __name__ == '__main__':
    unittest.main()
