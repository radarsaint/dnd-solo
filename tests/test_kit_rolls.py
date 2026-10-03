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



class AvraeOutputTests(unittest.TestCase):
    """Avrae's real output shapes (6c rerun 2026-10-03): one parse for every field line."""
    GREATAXE = ('I swing my greataxe at the dealer.\n'
                'Brakka attacks with a Greataxe!\n'
                '**To Hit**: 1d20 (11) + 7 = `18`\n'
                '**Damage**: 1d12 (5) + 6 [slashing] = `11`')
    FIREBALL = ('I cast Fireball at the table.\n'
                'Nik casts Fireball!\n'
                '**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 3) [fire] = `28`')
    MULTI = ('Nik casts Fireball!\n'
             '**DC**: 15\n'
             'Dealer\n'
             '**DEX Save**: 1d20 (3) + 2 = `5`; Failure!\n'
             '**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 3) [fire] = `28`\n'
             'Door-side player\n'
             '**DEX Save**: 1d20 (17) + 1 = `18`; Success!\n'
             '**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 3) [fire] / 2 = `14`')

    def test_to_hit_and_damage_are_separate(self):
        self.assertEqual(kit_rolls.attack_total(self.GREATAXE), 18)
        self.assertEqual(kit_rolls.damage_total(self.GREATAXE), (11, 'slashing'))
        self.assertEqual([r.label for r in kit_rolls.rolls(self.GREATAXE)], ['attack'],
                         'the damage line is never a check or attack roll')
        self.assertIsNone(kit_rolls.check_roll(self.GREATAXE))

    def test_crit_damage_field(self):
        text = ('**To Hit**: 1d20 (20) + 5 = `25`\n'
                '**Damage (CRIT!)**: 2d4 (3, 4) + 3 [piercing] = `10`')
        self.assertEqual(kit_rolls.attack_total(text), 25)
        self.assertEqual(kit_rolls.rolls(text)[0].die, 20)
        self.assertEqual(kit_rolls.damage_total(text), (10, 'piercing'))

    def test_fireball_damage_total(self):
        self.assertEqual(kit_rolls.damage_total(self.FIREBALL), (28, 'fire'))
        self.assertEqual(kit_rolls.rolls(self.FIREBALL), [])

    def test_multi_target_saves_dc_and_damage(self):
        posted = kit_rolls.avrae(self.MULTI)
        self.assertEqual(posted['dc'], 15)
        self.assertEqual(posted['targets']['dealer']['save'], ('dex', 5, False))
        self.assertEqual(posted['targets']['dealer']['damage'], (28, 'fire'))
        self.assertEqual(posted['targets']['door-side player']['save'], ('dex', 18, True))
        self.assertEqual(posted['targets']['door-side player']['damage'], (14, 'fire'))
        self.assertEqual(kit_rolls.damage_total(self.MULTI), (28, 'fire'))

    def test_check_header_names_the_skill(self):
        for line, skill, total in (
                ("'You don't have to take my word.'\nSela makes a Persuasion check! 1d20 (12) + 10 = `22`",
                 'persuasion', 22),
                ('Wren makes an Investigation check! 1d20 (12) + 3 = `15`', 'investigation', 15),
                ('Wren makes a Sleight of Hand check! 2d20kh1 (13, ~~4~~) + 7 = `20`', 'sleight_of_hand', 20)):
            with self.subTest(skill=skill):
                roll = kit_rolls.check_roll(line, skill)
                self.assertEqual((roll.label, roll.total), (skill, total))
                self.assertEqual(kit_rolls.stated_skill(line), skill)
                self.assertEqual(kit_cards.supplied_roll(line, 0, skill)[0] + kit_cards.supplied_roll(line, 0, skill)[1],
                                 total)

    def test_initiative_field(self):
        self.assertEqual(kit_rolls.initiative('Rolling initiative.\n**Initiative**: 1d20 (12) + 2 = `14`'), 14)
        text = ('**Initiative**: 1d20 (7) + 1 = `8`\n' + self.GREATAXE)
        self.assertEqual((kit_rolls.initiative(text), kit_rolls.attack_total(text)), (8, 18))
        self.assertEqual(kit_rolls.damage_total(text), (11, 'slashing'))

if __name__ == '__main__':
    unittest.main()
