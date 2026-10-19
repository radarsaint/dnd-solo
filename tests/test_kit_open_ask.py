"""Brendon's plan (2026-10-14), step 2: answer the open ask before reading a new deed, and commit
the engine's sentence after one failed narration.

(a) The open-ask gate at the top of RoomAdjudicator.resolve. A hit on his turn with no damage
    holds the turn: the monsters wait for the damage, and the next message (a bare Avrae damage
    field, an unlabelled dice line "1d4 (4) + 2 = 6", "4 piercing damage", "I rolled a 6", a bare
    "4") is its answer. No damage in the message, or a cancel aimed at the roll, yields the ask: the
    hit stands with no damage, it was his action, and the round runs on. A question with no damage
    in it is Kit's to answer and the ask stays open. A number is read as the damage only where it is
    plainly the roll; a check, save, natural or bare d20, a question's number, or a bare number among
    other words leaves the ask open (a missed answer only re-asks; a wrong one kills).
    A called check takes a bare roll first; a cancel calls it off.
(b) A rejected narration commits the engine's public_event sentence (no retry).
(c) A leveled spell with no slot left fizzles before any roll is asked for (Witch Bolt).

Synthetic roadcamp room (tests/fixtures/rooms), never 6c, for every fight; every die pinned
(NPC d20s 2: every monster swing misses)."""
import copy
import unittest

from runtime import kit_agent
from runtime.kit_agent import KitAgent
from test_kit_combat_checkpoints import NIK, Camp, without_shield
from test_kit_hardening import NIK_GREETING, NIK_REPLY, BridgeCase, RecordingModel

HIT = 'Initiative 25. I stab the wagon-side cutthroat with my dagger, 18 to hit.'  # AC 12: a hit, no damage


def camp(test):
    return Camp(test, roll=lambda: 2, sheet=without_shield(NIK))


class HitWithNoDamageHoldsTheTurn(unittest.TestCase):
    """The audit's High bug (main kit_combat.py:1152 and :664): the hit returned True, so the turn
    advanced and every monster acted before the damage existed; the damage paste was then a new turn."""

    def test_the_monsters_wait_for_the_damage(self):
        table = camp(self)
        result = table.act(HIT)
        fight = table.fight
        self.assertIn('Roll damage in Avrae.', result.public_event)
        self.assertNotIn('swings at you', result.public_event, 'nobody acts before the damage')
        self.assertEqual((fight['round'], fight['order'][fight['next']]), (1, 'pc'), 'still his turn')
        self.assertEqual(fight['pending']['needs'], 'damage')
        self.assertEqual(fight['hp']['cutthroat_a'], 11)

    def test_the_next_message_answers_the_damage_ask_bare_avrae_lines_included(self):
        for answer in ('**Damage**: 1d4 (2) + 2 = `4`', 'Damage: 1d4 (2) + 2 [piercing] = 4',
                       '4 piercing damage', '4', 'I attack. 4 piercing damage.'):
            with self.subTest(answer=answer):
                table = camp(self)
                table.act(HIT)
                result = table.act(answer)
                fight = table.fight
                self.assertEqual(fight['hp']['cutthroat_a'], 7, 'the 4 lands once')
                self.assertIsNone(fight.get('pending'))
                self.assertIn('swings at you', result.public_event, 'then the round runs on')
                self.assertEqual((fight['round'], fight['order'][fight['next']]), (2, 'pc'),
                                 'one round, not two')

    def test_a_message_with_no_damage_yields_the_ask(self):
        for words in ('Forget the damage.', 'I shout at them to drop their weapons.'):
            with self.subTest(words=words):
                table = camp(self)
                table.act(HIT)
                result = table.act(words)
                fight = table.fight
                self.assertIn('No damage was rolled', result.public_event)
                self.assertIsNone(fight.get('pending'))
                self.assertEqual(fight['hp']['cutthroat_a'], 11, 'the hit deals nothing')
                self.assertEqual((fight['round'], fight['order'][fight['next']]), (2, 'pc'),
                                 'the hit was his action: the round ran on')

    def test_a_new_attack_with_its_own_to_hit_is_no_answer_and_waits_for_his_next_turn(self):
        table = camp(self)
        table.act(HIT)
        result = table.act('I stab the bandit captain with my dagger, 17 to hit, 5 piercing')
        fight = table.fight
        self.assertEqual(fight['hp']['cutthroat_a'], 11, 'the 5 is not the old damage')
        self.assertIn('that waits for your next turn', result.public_event)
        self.assertEqual(fight['hp']['harl'], 25, 'it lands on his next turn')
        self.assertEqual(fight['round'], 3)

    def test_an_explicit_cancel_wins_over_a_number(self):
        table = camp(self)
        table.act(HIT)
        table.act('Never mind the damage, 4 is too low anyway.')
        self.assertEqual(table.fight['hp']['cutthroat_a'], 11)
        self.assertIsNone(table.fight.get('pending'))


class DamageAnswerFormats(unittest.TestCase):
    """Nagatha's #127 review at 3a18e9b: the damage ask read only Avrae's labelled field, a stated
    "N damage" or a lone number, so a bare Avrae dice line gave the ask with 0 damage; a question
    yielded the damage and was held; a cancel word beat a stated amount. Dice pinned (NPC d20s 2)."""

    def answered(self, words):
        table = camp(self)
        table.act(HIT)
        result = table.act(words)
        return table.fight, result

    def assertLands(self, words, amount):
        fight, result = self.answered(words)
        self.assertEqual(fight['hp']['cutthroat_a'], 11 - amount, words)
        self.assertIsNone(fight.get('pending'), words)
        self.assertNotIn('No damage was rolled', result.public_event, words)
        self.assertEqual((fight['round'], fight['order'][fight['next']]), (2, 'pc'), words)
        return result

    def test_an_unlabelled_avrae_dice_line_answers_with_its_total(self):
        for words, amount in (('1d4 (4) + 2 = 6', 6), ('1d8 (5) = 5', 5), ('1d4 (2) = 2', 2),
                              ('2d6 (3, 4) + 1 = `8`', 8), ('3d4 (1, 2, 3) [piercing] = 6', 6)):
            with self.subTest(words=words):
                self.assertLands(words, amount)

    def test_numbers_that_are_no_roll_do_not_answer(self):
        for words in ('I back off 30 feet.', 'I yell at the two of them.', 'Two more rounds of this?',
                      'I look for the other one.'):
            with self.subTest(words=words):
                fight, result = self.answered(words)
                self.assertEqual(fight['hp']['cutthroat_a'], 11, words)

    def test_a_d20_line_is_no_damage(self):
        fight, result = self.answered('1d20 (14) + 4 = 18')
        self.assertEqual(fight['hp']['cutthroat_a'], 11)

    def test_a_stated_roll_answers(self):
        for words in ('I rolled a 6', 'got a 6 on that', '6!', 'six', 'I rolled a six.', 'Six!',
                      'I rolled a 1 on the die, 6 total', "It's 6.", 'damage 6'):
            with self.subTest(words=words):
                self.assertLands(words, 6)

    def assertStaysOpen(self, words):
        fight, result = self.answered(words)
        self.assertEqual(fight['hp']['cutthroat_a'], 11, words)
        self.assertEqual((fight.get('pending') or {}).get('needs'), 'damage', f'{words}: the ask stays open')
        self.assertNotIn('declared_next', fight)
        self.assertNotIn('No damage was rolled', result.public_event)
        self.assertNotIn('swings at you', result.public_event, 'nobody acts')
        self.assertEqual((fight['round'], fight['order'][fight['next']]), (1, 'pc'))
        self.assertIn('still waits for its damage roll', result.public_event)
        return result

    def assertYields(self, words):
        fight, result = self.answered(words)
        self.assertEqual(fight['hp']['cutthroat_a'], 11, words)
        self.assertIn('No damage was rolled', result.public_event, words)
        self.assertIsNone(fight.get('pending'), words)

    def test_a_check_save_or_natural_roll_is_never_damage(self):
        # Nagatha's re-review at 4e6b5ed (High): a missed answer only re-asks, a wrong one kills.
        for words in ('**Perception**: 1d20 (12) + 4 = `16`', 'Stealth check 15', 'nat 20!', '1d20 (14) + 3 = 17',
                      'Dex save 14', 'natural 1', 'Athletics: 12', 'I got a 15 on my wisdom saving throw'):
            with self.subTest(words=words):
                self.assertStaysOpen(words)

    def test_a_question_takes_only_an_explicit_roll(self):
        # The re-review (High), against the first review's item 4: with a question in the message only a
        # dice line or "N damage" answers; "Do I add my dex? 6" re-asks rather than guess.
        for words in ('Is the cutthroat down to 5 hp?', 'Do I add 2 for dex?', 'Do I add my dex? 6',
                      'Wait, how many are left standing?', 'Two more rounds of this?', 'I rolled a 6?'):
            with self.subTest(words=words):
                self.assertStaysOpen(words)
        for words, amount in (('Is that 1d4 (4) + 2 = 6 enough?', 6), ('6 damage, is it down?', 6)):
            with self.subTest(words=words):
                self.assertLands(words, amount)

    def test_a_deed_with_a_number_in_it_is_no_answer(self):
        # The re-review (Medium): a lone number counts only in a message that is just the number, or
        # right after rolled/got/damage/dmg. A deed yields the ask, as one with no number does.
        for words in ('I attack goblin 2', 'I back off 2 squares', 'I want to retreat toward the wagon, 2 steps',
                      'I drink 1 potion', 'I step back 10 feet', 'I grab the 3 gold pieces off the table',
                      'I count 4 more bandits by the wagons', 'I shove the cutthroat 5 feet away',
                      'I shout "6 of you against me? Fine!"', 'I have six darts left, I throw one at the captain',
                      'I take the Dodge action', 'I got 3 gold off him'):
            with self.subTest(words=words):
                self.assertYields(words)

    def test_a_bare_number_in_doubt_leaves_the_ask_open(self):
        for words in ('Round 2: 6', 'Never mind the captain. 6.', 'no damage to the prisoner, 5', '4 or 5',
                      'I rolled a 4 and a 2'):
            with self.subTest(words=words):
                self.assertStaysOpen(words)

    def test_an_explicit_damage_field_or_amount_beats_save_and_dc_words(self):
        # Nagatha's review at c17dc15 (High): the never-damage words must not refuse a stated damage.
        for words in ('Nik attacks with a Dagger!\nwagon-side cutthroat\n**Damage**: 1d4 (3) + 2 = `5`\n'
                      'Effect: DC 12 save or prone',
                      'Damage: 5 (they failed the save)', '5 damage, he failed his save',
                      'Nik casts Thunderwave!\n**DC**: 13\nwagon-side cutthroat: **CON Save**: 1d20 (4) + 1 = `5`; '
                      'Failure!\n**Damage**: 2d8 (3, 2) = `5`',
                      '5 damage after his Dex check'):
            with self.subTest(words=words):
                self.assertLands(words, 5)
        self.assertStaysOpen('**Perception**: 1d20 (12) + 4 = `16`')  # the d20 total stays excluded

    def test_several_stated_amounts_apply_the_first_and_say_so(self):
        # c17dc15 review (Medium): never 0 damage, held as a deed, with two rounds run.
        # A same-hit rider ('sneak attack 4 damage') sums instead: NeverForfeitStatedDamage.
        for words in ('5 damage, then 4 damage', 'Damage: 1d4 (3) + 2 = 5 Damage: 1d4 (1) + 2 = 3',
                      '5 piercing damage and 2 fire damage'):
            with self.subTest(words=words):
                result = self.assertLands(words, 5)
                self.assertIn('Only the first damage roll counts (5)', result.public_event)
                self.assertNotIn('waits for your next turn', result.public_event)

    def test_a_labelled_extra_field_in_the_block_is_the_same_hit(self):
        for words in ('**Damage**: 1d4 (3) + 2 = `5`\n**Damage (Sneak Attack)**: 1d6 (4) = `4`',
                      'Nik attacks with a Dagger!\n**Damage (CRIT!)**: 2d4 (3, 2) + 2 = `7`\n'
                      '**Damage (Sneak Attack)**: 1d6 (2) = `2`'):
            with self.subTest(words=words):
                result = self.assertLands(words, 9)
                self.assertNotIn('Only the first', result.public_event)

    def test_filler_before_a_lone_number_still_counts(self):
        for words in ('Lol okay. 5', 'ok 5', 'Haha alright, 5', 'Okay so I rolled 5', 'Rolled 5!', 'got 5 total'):
            with self.subTest(words=words):
                self.assertLands(words, 5)

    def test_nagathas_c17_cases(self):
        """/tmp/rvw127/scratch_c17.py, the cases the tests above do not already hold."""
        for words in ('Nik attacks with a Dagger!\n**Damage**: 1d4 (3) + 2 = `5`', 'Nik casts Witch Bolt!\n**Damage**: 1d12 (5) = `5`',
                      "that's 5", '5 piercing', 'Total 5.', 'Dagger damage 5'):
            with self.subTest(words=words):
                self.assertLands(words, 5)
        for words in ('Nik stabs again, 5', 'Nik runs for the wagon', 'Running to the wagon, 2 moves'):
            with self.subTest(words=words):
                self.assertYields(words)
        for words in ('Then I stab the captain', 'Stab the captain'):
            with self.subTest(words=words):
                fight, result = self.answered(words)
                self.assertEqual(fight['hp']['cutthroat_a'], 11)
                self.assertIn('that waits for your next turn', result.public_event)
        self.assertStaysOpen('5, and I yell at the captain')

    def test_hex_hunters_mark_and_any_labelled_rider_field_sum_with_the_damage(self):
        # Nagatha's e3fc5a7 round (2): a labelled extra-damage field of the same Avrae block is the same hit.
        for words, amount in (('Nik attacks with a Dagger!\n**Damage**: 1d4 (3) + 2 = `5`\n**Hex**: 1d6 (4) [necrotic] = `4`', 9),
                              ("Nik attacks with a Dagger!\n**Damage**: 1d4 (3) + 2 = `5`\n**Hunter's Mark**: 1d6 (2) = `2`", 7),
                              ('**Damage**: 1d4 (3) + 2 = `5`\n**Divine Smite**: 2d8 (1, 2) [radiant] = `3`', 8)):
            with self.subTest(words=words):
                result = self.assertLands(words, amount)
                self.assertNotIn('Only the first', result.public_event)

    def test_a_named_rider_on_the_damage_line_sums(self):
        # (3): never 4 silently.
        for words in ('Damage: 1d4 (3) + 2 = 5, plus 4 damage from hex', '5 damage plus 4 necrotic from Hex',
                      '5 piercing damage, plus 4 damage from hunters mark'):
            with self.subTest(words=words):
                result = self.assertLands(words, 9)
                self.assertNotIn('Only the first', result.public_event)

    def test_a_stray_number_after_the_damage_is_said_to_be_ignored(self):
        result = self.assertLands('Damage: 1d4 (3) + 2 = 5 (and my earlier roll was 6)', 5)
        self.assertIn('Only the first damage roll counts (5)', result.public_event)

    def test_damage_naming_another_target_leaves_the_ask_open_and_says_why(self):
        # (4): it never lands on the held target.
        for words in ('Nik attacks with a Dagger!\nbandit captain\n**Damage**: 1d4 (3) + 2 = `5`',
                      '5 damage to the bandit captain', 'Damage: 5 on the fire-side cutthroat'):
            with self.subTest(words=words):
                fight, result = self.answered(words)
                self.assertEqual((fight['hp']['cutthroat_a'], fight['hp']['harl'], fight['hp']['cutthroat_b']),
                                 (11, 30, 11), words)
                result = self.assertStaysOpen(words)
                self.assertIn('your hit was on the wagon-side cutthroat', result.public_event)
        self.assertLands('5 damage to the wagon-side cutthroat', 5)
        self.assertLands('Nik attacks with a Dagger!\nwagon-side cutthroat\n**Damage**: 1d4 (3) + 2 = `5`', 5)

    def test_a_roll_of_zero_says_so(self):
        # (5): a total of 0 (or less) is the answer, not "No damage was rolled".
        for words in ('Damage: 1d4 (1) - 1 = 0', 'Damage: 1d4 (1) - 3 = -2', '1d4 (1) - 1 = 0', '0', '0 damage', '-2'):
            with self.subTest(words=words):
                fight, result = self.answered(words)
                self.assertEqual(fight['hp']['cutthroat_a'], 11)
                self.assertIsNone(fight.get('pending'))
                self.assertNotIn('No damage was rolled', result.public_event)
                self.assertIn('Your damage roll came to 0, so your hit on the wagon-side cutthroat does no damage.',
                              result.public_event)
                self.assertEqual((fight['round'], fight['order'][fight['next']]), (2, 'pc'), 'it was the answer')

    def test_nagathas_e3_cases(self):
        """/tmp/rvw127/scratch_e3.py: those the tests above do not hold."""
        self.assertLands('**Damage (CRIT!)**: 2d4 (3, 1) + 2 = `6`', 6)
        result = self.assertLands('Nik attacks with a Dagger!\n**Damage (CRIT!)**: 2d4 (3, 1) + 2 = `6`\n**Damage**: 1d6 (4) = `4`', 6)
        self.assertIn('Only the first damage roll counts (6)', result.public_event)
        self.assertLands('Nik attacks with a Dagger!\n**Damage**: 1d4 (3) + 2 [piercing] + 1d6 (2) [necrotic] = `7`', 7)
        result = self.assertStaysOpen('Nik attacks with a Dagger!\n**Miss!**\n**Damage**: 1d4 (3) + 2 = `5`')
        self.assertIn('says it missed', result.public_event)
        fight, result = self.answered('Nik attacks with a Dagger!\nwagon-side cutthroat\n**To Hit**: 1d20 (3) + 5 = `8`; '
                                      'Miss!\n**Damage**: 1d4 (3) + 2 = `5`')
        self.assertEqual(fight['hp']['cutthroat_a'], 11)
        self.assertIn('that waits for your next turn', result.public_event)

    def test_nagathas_33_cases(self):
        """/tmp/rvw127/scratch_fp.py, every case: L n lands n, O stays open, Y yields (H: held too)."""
        cases = {'1d4 (2) = 2': 2, '1d4 (4) + 2 = 6': 6, '**Damage (CRIT!)**: 2d4 (3, 1) + 2 = `6`': 6,
                 'Damage: 1d4 (2) + 2 = 4\nDamage: 1d4 (3) + 2 = 5': 4, 'I rolled a 6': 6, 'six': 6,
                 'Wait, how many are left standing?': 'O', 'Scratch that, it was 6 damage.': 6,
                 'Do I add my dex? 6': 'O', '1d20 (14) + 3 = 17': 'O', '**Perception**: 1d20 (12) + 4 = `16`': 'O',
                 'Stealth check 15': 'O', 'I step back 10 feet': 'Y', 'I back off 2 squares': 'Y',
                 'I grab the 3 gold pieces off the table': 'Y', 'I count 4 more bandits by the wagons': 'Y',
                 'Is the cutthroat down to 5 hp?': 'O', 'Do I add 2 for dex?': 'O', 'I attack goblin 2': 'Y',
                 'I shove the cutthroat 5 feet away': 'Y', 'I shout "6 of you against me? Fine!"': 'Y',
                 'I have six darts left, I throw one at the captain': 'Y', 'Six!': 6,
                 'Cancel my concentration, 6 damage': 6, 'Never mind the captain. 6.': 'O',
                 'no damage to the prisoner, 5': 'O', 'I drink 1 potion': 'Y', 'Round 2: 6': 'O',
                 'I rolled a 1 on the die, 6 total': 6, 'nat 20!': 'O', 'I take the Dodge action': 'Y',
                 'I cast Witch Bolt at the captain': 'H', 'I want to retreat toward the wagon, 2 steps': 'Y'}
        self.assertEqual(len(cases), 33)
        for words, outcome in cases.items():
            with self.subTest(words=words):
                if outcome == 'O':
                    self.assertStaysOpen(words)
                elif outcome == 'Y':
                    self.assertYields(words)
                elif outcome == 'H':  # yielded and held for his next turn (it sets its own ask then)
                    fight, result = self.answered(words)
                    self.assertEqual(fight['hp']['cutthroat_a'], 11)
                    self.assertIn('No damage was rolled', result.public_event)
                    self.assertIn('that waits for your next turn', result.public_event)
                else:
                    self.assertLands(words, outcome)

    def test_a_stated_amount_beats_a_loose_cancel_word(self):
        for words in ('Scratch that, it was 6 damage.', 'Oops, 6 damage, never mind the earlier number',
                      'Never mind, I rolled a 6'):
            with self.subTest(words=words):
                self.assertLands(words, 6)

    def test_a_cancel_next_to_the_roll_still_cancels(self):
        for words in ('Never mind the damage, 4 is too low anyway.', 'Skip the roll, 5.', 'Forget the damage.',
                      'Never mind.'):
            with self.subTest(words=words):
                fight, result = self.answered(words)
                self.assertEqual(fight['hp']['cutthroat_a'], 11)
                self.assertIn('No damage was rolled', result.public_event)

    def test_a_second_damage_line_is_said_to_be_ignored(self):
        result = self.assertLands('Damage: 1d4 (2) + 2 = 4\nDamage: 1d4 (3) + 2 = 5', 4)
        self.assertIn('Only the first damage roll counts (4)', result.public_event)
        result = self.assertLands('1d4 (4) + 2 = 6 and 1d4 (1) + 2 = 3', 6)
        self.assertIn('Only the first damage roll counts (6)', result.public_event)

    def test_one_damage_line_says_nothing_extra(self):
        result = self.assertLands('1d4 (4) + 2 = 6', 6)
        self.assertNotIn('Only the first', result.public_event)


class CalledCheckAnswersFirst(unittest.TestCase):
    def called(self):
        table = camp(self)
        revision, _ = table.runtime.load()
        table.runtime.commit('call', revision, [{'type': 'pending_check', 'evidence': 'Kit called Perception (test setup).',
                                                 'check': {'skill': 'perception', 'ability': 'wis', 'target': 'none',
                                                           'called_turn': 'call'}}])
        return table

    def test_a_bare_roll_answers_the_called_check(self):
        table = self.called()
        result = table.act('15')
        self.assertEqual(result.kind, 'called_check')
        self.assertNotIn('pending_check', table.state)

    def test_a_cancel_calls_the_check_off_and_the_words_resolve(self):
        table = self.called()
        result = table.act('Never mind the roll. I look around the camp.')
        self.assertNotEqual(result.kind, 'called_check')
        self.assertTrue(any(e.get('type') == 'pending_check' and e.get('check') is None for e in result.events))
        self.assertNotIn('pending_check', table.state)


class NoSlotFizzlesBeforeTheAsk(unittest.TestCase):
    """Nagatha's #123 review: Witch Bolt with no slot left asked for its attack roll first."""

    def spent(self):
        table = camp(self)
        revision, state = table.runtime.load()
        resources = copy.deepcopy(state['pc_resources'])
        for slot in resources['slots'].values():
            slot['used'] = slot['max']
        table.runtime.commit('spent', revision, [{'type': 'pc_resources', 'resources': resources,
                                                  'evidence': 'every slot spent (test setup)'}])
        return table

    def test_witch_bolt_with_no_slot_fizzles_before_the_attack_roll(self):
        table = self.spent()
        result = table.act('Initiative 25. I cast Witch Bolt at the wagon-side cutthroat.')
        self.assertIn('fizzles', result.public_event)
        self.assertNotIn('Roll the attack', result.public_event)
        self.assertFalse((table.fight.get('pending') or {}).get('needs'), 'no roll asked for')

    def test_a_cantrip_still_asks_for_its_attack(self):
        table = self.spent()
        result = table.act('Initiative 25. I cast Fire Bolt at the wagon-side cutthroat.')
        self.assertIn('Roll the attack', result.public_event)
        self.assertNotIn('fizzles', result.public_event)


def numbered_camp(test):
    """Roadcamp with its foes relabelled Bandit 1-3 (every pack room numbers its foes)."""
    import json
    import tempfile
    from pathlib import Path
    from unittest import mock
    import test_kit_combat_checkpoints as checkpoints
    source = json.loads(checkpoints.CAMP.read_text())
    for number, key in enumerate(('harl', 'cutthroat_a', 'cutthroat_b'), 1):
        source['actors'][key]['name'] = f'Bandit {number}'
    temp = tempfile.TemporaryDirectory()
    test.addCleanup(temp.cleanup)
    path = Path(temp.name) / 'numbered.json'
    path.write_text(json.dumps(source))
    with mock.patch.object(checkpoints, 'CAMP', path):
        return Camp(test, roll=lambda: 2, sheet=without_shield(NIK))


NUMBERED_HIT = 'Initiative 25. I stab Bandit 2 with my dagger, 18 to hit.'  # cutthroat_a, AC 12


class NumberedFoesDamage(unittest.TestCase):
    """Nagatha's #127 review at 79196b5 (High): a bare number read as a numbered foe ('**Damage**:
    1d6 (6) = `6`' named 'giant rat 6'), so a hit on a numbered pack could never be answered.
    A foe is named only by a word of its name; dice terms and bare numbers never name one."""

    def answered(self, words):
        table = numbered_camp(self)
        table.act(NUMBERED_HIT)
        self.assertEqual(table.fight['pending']['target'], 'cutthroat_a')
        result = table.act(words)
        return table.fight, result

    def test_a_number_in_the_roll_names_no_foe(self):
        for words, amount in (('2 piercing', 2), ('3 piercing damage', 3), ('**Damage**: 1d6 (3) = `3`', 3),
                              ('Damage: 1d4 (1) + 2 = 3', 3), ('1d4 (1) = 1', 1), ('1', 1), ('I rolled a 3', 3),
                              ('Nik attacks with a Dagger!\n**Damage**: 1d4 (1) + 2 = `3`\n**Hex**: 1d6 (1) = `1`', 4)):
            with self.subTest(words=words):
                fight, result = self.answered(words)
                self.assertEqual(fight['hp']['cutthroat_a'], 11 - amount, result.public_event)
                self.assertIsNone(fight.get('pending'), words)
                self.assertNotIn('names the', result.public_event)

    def test_a_typed_out_numbered_foe_still_names_it(self):
        for words in ('4 damage to Bandit 3', 'Bandit 1 takes 4 damage', 'Damage: 4 on bandit 3'):
            with self.subTest(words=words):
                fight, result = self.answered(words)
                self.assertEqual(fight['hp']['cutthroat_a'], 11, words)
                self.assertEqual((fight.get('pending') or {}).get('needs'), 'damage', words)
                self.assertRegex(result.public_event, r'names Bandit [13], but your hit was on Bandit 2')
        for words in ('4 damage to Bandit 2', 'Bandit 2 takes 4 damage', '4 damage to the bandit'):
            with self.subTest(words=words):
                fight, _ = self.answered(words)
                self.assertEqual(fight['hp']['cutthroat_a'], 7, words)


class RiderRules(unittest.TestCase):
    """Nagatha's #127 review at 79196b5 (Low): riders of one name do not stack, and a rider alone
    is not the hit's damage."""

    answered = DamageAnswerFormats.answered
    assertLands = DamageAnswerFormats.assertLands
    assertStaysOpen = DamageAnswerFormats.assertStaysOpen

    def test_a_same_named_rider_counts_once_and_the_other_is_said(self):
        for words in ('**Damage**: 1d4 (3) + 2 = `5`\n**Hex**: 1d6 (4) = `4`\n**Hex**: 1d6 (6) = `6`',
                      'Damage: 1d4 (3) + 2 = 5, plus 4 damage from hex, plus 6 damage from hex',
                      '**Damage**: 1d4 (3) + 2 = `5`\n**Hex**: 1d6 (4) = `4`, plus 6 damage from Hex'):
            with self.subTest(words=words):
                result = self.assertLands(words, 9)
                self.assertIn("Hex doesn't stack: one Hex roll counts (4); the other is ignored.", result.public_event)
        result = self.assertLands("**Damage**: 1d4 (3) + 2 = `5`\n**Hex**: 1d6 (4) = `4`\n**Hunter's Mark**: 1d6 (1) = `1`", 10)
        self.assertNotIn('stack', result.public_event)

    def test_a_rider_alone_leaves_the_ask_open(self):
        for words in ('**Hex**: 1d6 (4) [necrotic] = `4`', "Hunter's Mark: 1d6 (3) = 3", 'plus 4 damage from hex',
                      '**Damage (Sneak Attack)**: 2d6 (3, 4) = `7`'):
            with self.subTest(words=words):
                result = self.assertStaysOpen(words)
                # e486b18 re-probe: the reply invites the main roll ("Got Hex 4. What's the dagger's damage?").
                self.assertIn("What's the dagger's damage?", result.public_event)


class EngineLineAfterOneFailedNarration(BridgeCase):
    """The audit (kit_agent.py:2247 and :4759): rejected narrations walked to degraded mode, then
    abandon and prepare again, each another model call. Nagatha's #127 review: the engine's
    sentence commits after ONE failed narration (ENGINE_LINE_AFTER_REJECTIONS = 1). Nagatha's
    e3fc5a7 playtest: a style-only miss keeps one retry (STYLE_RETRIES = 1); secrecy and agency
    failures still commit at once (tests/test_kit_engine_line_policy.py)."""

    def test_the_default_is_one_failed_narration(self):
        self.assertEqual(kit_agent.ENGINE_LINE_AFTER_REJECTIONS, 1)

    def test_a_style_miss_commits_the_engine_sentence_on_its_second_failure(self):
        self.staged(NIK_GREETING, 'once', reply_to='Whats going on here?')
        with self.assertRaises(kit_agent.PerformanceRejected):
            self.bridge.finish('once', NIK_REPLY)
        result = self.bridge.finish('once', NIK_REPLY)
        self.assertTrue(result['engine_line'])
        self.assertEqual(result['revision'], 1, 'committed, no further retry asked for')
        record = self.runtime.recent_kit_turns()[-1]
        self.assertEqual(record['spoken'], f"Narrator: {record['public_event']}")
        self.assertEqual(record['engine_line']['after_rejections'], 2)
        self.assertEqual(record['engine_line']['kinds'], ['style'])
        self.assertIn('Exchange scope', record['engine_line']['last_rejection'], 'the real validator fired')
        self.assertEqual(self.runtime.kit_timing('once')['rejected_attempts'], 2)

    def test_a_hard_check_failure_also_falls_back_to_the_engine_sentence(self):
        self.staged('I take a seat.', 'hard')
        leaky = {'segments': [{'speaker': 'Narrator', 'text': 'The doppelganger smiles.'},
                              {'speaker': 'Dealer', 'text': 'Sit.'}]}
        result = self.bridge.finish('hard', leaky)
        self.assertTrue(result['engine_line'])
        self.assertNotIn('doppelganger', result['spoken'].casefold())
        self.assertIn('private fact', self.runtime.recent_kit_turns()[-1]['engine_line']['last_rejection'])

    def test_a_resubmission_after_the_engine_line_returns_what_was_committed(self):
        self.staged(NIK_GREETING, 'lost', reply_to='Whats going on here?')
        with self.assertRaises(kit_agent.PerformanceRejected):
            self.bridge.finish('lost', NIK_REPLY)
        first = self.bridge.finish('lost', NIK_REPLY)
        again = self.bridge.finish('lost', {'segments': [{'speaker': 'Narrator',
                                                          'text': first['spoken'][len('Narrator: '):]}]})
        self.assertTrue(again.get('already_committed'))
        self.assertEqual(again['revision'], first['revision'])

    def test_the_api_turn_commits_the_engine_sentence_after_one_failed_narration(self):
        class AlwaysLeaky(RecordingModel):
            def plan(inner, payload):
                return {**super().plan(payload), 'move': 'npc_reply', 'table_presence': 'quiet'}

            def perform(inner, payload, performance_variant='current'):
                return {'segments': [{'speaker': 'Narrator', 'text': 'The doppelganger smiles.'},
                                     {'speaker': 'Dealer', 'text': 'Sit.'}]}

        result = KitAgent(self.runtime, AlwaysLeaky(), self.adjudicator).turn('I take a seat.', 'api-leak')
        self.assertEqual(result['timing']['model_calls'], 1 + 1, 'one plan and one narration, no retry')
        self.assertTrue(result['timing']['engine_line'])
        self.assertEqual(result['spoken'], f"Narrator: {result['public_event']}")


if __name__ == '__main__':
    unittest.main()


def named_camp(test, names):
    """Roadcamp with its foes relabelled (synthetic; every die pinned)."""
    import json
    import tempfile
    from pathlib import Path
    from unittest import mock
    import test_kit_combat_checkpoints as checkpoints
    source = json.loads(checkpoints.CAMP.read_text())
    for key, name in names.items():
        source['actors'][key]['name'] = name
    temp = tempfile.TemporaryDirectory()
    test.addCleanup(temp.cleanup)
    path = Path(temp.name) / 'named.json'
    path.write_text(json.dumps(source))
    with mock.patch.object(checkpoints, 'CAMP', path):
        return Camp(test, roll=lambda: 2, sheet=without_shield(NIK))


class AskHelpers:

    def answered(self, words, table=None, target='cutthroat_a', hit=HIT):
        table = table or camp(self)
        table.act(hit)
        self.assertEqual(table.fight['pending']['target'], target)
        return table, table.act(words)

    def assertLands(self, words, amount, **kw):
        table, result = self.answered(words, **kw)
        fight = table.fight
        target = kw.get('target', 'cutthroat_a')
        self.assertEqual(fight['hp'][target], 11 - amount, f'{words}: {result.public_event}')
        self.assertIsNone(fight.get('pending'), words)
        self.assertNotIn('No damage was rolled', result.public_event, words)
        self.assertEqual((fight['round'], fight['order'][fight['next']]), (2, 'pc'), words)
        return result

    def assertHeld(self, words, **kw):
        table, result = self.answered(words, **kw)
        fight = table.fight
        target = kw.get('target', 'cutthroat_a')
        self.assertEqual(fight['hp'][target], fight['max_hp'][target], words)
        self.assertEqual((fight.get('pending') or {}).get('needs'), 'damage', f'{words}: {result.public_event}')
        self.assertNotIn('No damage was rolled', result.public_event, words)
        self.assertEqual(fight['round'], 1, words)
        return result



class NeverForfeitStatedDamage(AskHelpers, unittest.TestCase):
    """Nagatha's #127 re-probe at 3f6f0de: a missed answer only re-asks, a wrong one kills monsters,
    and a lost damage roll is also wrong. A correction, a number with the target's name, or a
    number word with 'damage' is the answer or held, never forfeited."""

    def test_a_correction_during_the_ask_lands_its_amount(self):
        for words in ('Actually it was 6 not 5 lol', 'Actually it was 6', 'actually 6 not 5', 'correction: 6',
                      'oh wait 6 not 5', '6 not 5', 'Scratch that, it was 6 damage.', 'Oops, 6.', 'wait, six',
                      'my bad, it was 6'):
            with self.subTest(words=words):
                self.assertLands(words, 6)

    def test_a_correction_with_no_clear_amount_is_held_never_forfeited(self):
        for words in ('Actually wait', 'actually it was 6 or 7', 'oops'):
            with self.subTest(words=words):
                self.assertHeld(words)

    def test_a_correction_after_the_damage_landed_is_a_graceful_reply(self):
        table = camp(self)
        table.act(HIT)
        table.act('5')
        self.assertEqual(table.fight['hp']['cutthroat_a'], 6)
        for words in ('Actually it was 6 not 5', 'correction: 6', 'oh wait 6 not 5'):
            with self.subTest(words=words):
                result = table.act(words)
                self.assertEqual(table.fight['hp']['cutthroat_a'], 6, 'never silently re-applied')
                self.assertIn('already landed', result.public_event)

    def test_the_targets_own_name_and_a_number_land(self):
        for words, amount in (('6 to the cutthroat', 6), ('cutthroat 3', 3), ('wagon-side cutthroat takes 6', 6),
                              ('6 to the wagon-side cutthroat', 6)):
            with self.subTest(words=words):
                self.assertLands(words, amount)

    def test_a_numbered_targets_name_never_counts_as_the_damage(self):
        for words, amount in (('Bandit 2 takes 6', 6), ('3 to bandit 2', 3), ('6 to bandit 2', 6),
                              ('bandit 2 6', 6), ('2 to bandit 2', 2)):
            with self.subTest(words=words):
                self.assertLands(words, amount, table=numbered_camp(self), hit=NUMBERED_HIT)

    def test_the_targets_name_alone_or_another_foe_holds_the_ask(self):
        self.assertHeld('bandit 2', table=numbered_camp(self), hit=NUMBERED_HIT)
        result = self.assertHeld('3 to bandit 3', table=numbered_camp(self), hit=NUMBERED_HIT)
        self.assertIn('Bandit 3', result.public_event)

    def test_a_foe_named_with_a_number_word_is_never_damage(self):
        names = {'harl': 'Seven', 'cutthroat_b': 'Six-Fingered Jack'}
        for words, amount in (('Six damage', 6), ('seven damage', 7), ('six', 6), ('6', 6)):
            with self.subTest(words=words):
                self.assertLands(words, amount, table=named_camp(self, names))
        self.assertHeld('Seven', table=named_camp(self, names))

    def test_a_same_hit_rider_in_prose_sums(self):
        for words, amount in (('Dagger 5 damage, sneak attack 4 damage', 9),
                              ('5 piercing damage and 3 from sneak attack', 8)):
            with self.subTest(words=words):
                self.assertLands(words, amount)
        result = self.assertLands('5 damage, then 4 damage', 5)
        self.assertIn('Only the first damage roll counts', result.public_event)

    def test_a_numbered_foe_reads_as_a_name_in_the_line(self):
        table, result = self.answered('3', table=numbered_camp(self), hit=NUMBERED_HIT)
        self.assertIn('Bandit 2 is hurt', result.public_event)
        self.assertNotIn('The bandit 2', result.public_event)


RATS_1_6_3 = {'harl': 'Giant rat 1', 'cutthroat_a': 'Giant rat 6', 'cutthroat_b': 'Giant rat 3'}


def stab(label):
    return f'Initiative 25. I stab the {label} with my dagger, 18 to hit.'


def call_check(table, skill='perception'):
    """Kit calls a check (her roll_call), as the bridge commits it."""
    revision, _ = table.runtime.load()
    plan = {'roll_call': {'skill': skill, 'mode': 'normal', 'target': 'none',
                          'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}}
    table.runtime.commit('t-call', revision, kit_agent.turn_events(
        table.runtime, {'events': [{'type': 'beat', 'tags': ['call'], 'evidence': 'Call.'}]}, plan, 't-call'))


class E486Reprobe(AskHelpers, unittest.TestCase):
    """Nagatha's re-probe at e486b18 (pinned dice, synthetic roadcamp copies)."""

    def rats(self):
        return dict(table=named_camp(self, RATS_1_6_3), hit=stab('Giant rat 6'))

    def test_short_forms_of_a_numbered_name_are_names_never_damage(self):
        for words in ('rat 6', 'the rat 6', 'giant rat 6'):
            with self.subTest(words=words):
                self.assertIn('names your target but no damage', self.assertHeld(words, **self.rats()).public_event)
        for words in ('rat 3', 'rat 1', 'giant rat 3 takes 6'):
            with self.subTest(words=words):
                self.assertRegex(self.assertHeld(words, **self.rats()).public_event, r'names Giant rat [13], but')
        for words, amount in (('rat 6 takes 6', 6), ('6 to rat 6', 6), ('3 to rat 6', 3), ('rat 6 takes it, 6', 6),
                              ('Giant rat 6: 6', 6)):
            with self.subTest(words=words):
                self.assertLands(words, amount, **self.rats())

    def test_a_number_that_is_no_deed_never_forfeits(self):
        for words in ('Make it 6', 'oops, make that 6', 'Ugh, 6. Not 5.', 'Dagger: 6', '6 (not 5)'):
            with self.subTest(words=words):
                self.assertLands(words, 6)
        for words in ('not 5', 'b2 6'):
            with self.subTest(words=words):
                self.assertHeld(words)
        for words in ('Bandit-3 takes 5', 'bandit 12 takes 5'):
            with self.subTest(words=words):
                self.assertHeld(words, table=numbered_camp(self), hit=NUMBERED_HIT)
        said = self.assertHeld('bandit 12 takes 5', table=numbered_camp(self), hit=NUMBERED_HIT).public_event
        self.assertIn('no Bandit 12', said)

    def test_a_one_line_labelled_roll_is_the_main_damage(self):
        for words in ('Dagger: 1d4 (4) + 2 = 6', '**Result**: 1d4 (4) + 2 = `6`', 'Total: 1d4 (4) + 2 = 6',
                      'Dmg: 1d4 (4) + 2 = 6', 'Piercing: 1d4 (4) + 2 = 6', 'dagger dmg: 1d4 (4) + 2 = 6',
                      '**Dagger**: 1d4 (4) + 2 = `6`'):
            with self.subTest(words=words):
                self.assertLands(words, 6)
        for words in ('Perception: 16', 'Round 2: 6'):
            with self.subTest(words=words):
                self.assertHeld(words)

    def test_a_rider_alone_invites_the_main_roll(self):
        for words in ('Hex 4 necrotic', '**Hex**: 1d6 (4) = `4`'):
            with self.subTest(words=words):
                self.assertIn("Got Hex 4. What's the dagger's damage?", self.assertHeld(words).public_event)

    def test_a_number_word_in_the_targets_name_is_still_the_amount(self):
        names = {'harl': 'Seven', 'cutthroat_a': 'Six-Fingered Jack', 'cutthroat_b': 'Bandit scout'}
        for words, amount in (('Six damage', 6), ('Jack takes 6', 6)):
            with self.subTest(words=words):
                self.assertLands(words, amount, table=named_camp(self, names), hit=stab('Six-Fingered Jack'))
        said = self.assertHeld('captain 3').public_event
        self.assertIn('names the bandit captain', said)

    def test_an_ambiguous_name_says_so(self):
        names = {'harl': 'Hobgoblin', 'cutthroat_a': 'Goblin 2', 'cutthroat_b': 'Goblin 3'}
        said = self.assertHeld('6 to the goblin', table=named_camp(self, names), hit=stab('Hobgoblin'),
                               target='harl').public_event
        self.assertIn('could be Goblin 2 or Goblin 3', said)

    def test_a_bare_number_after_the_damage_landed_says_it_landed(self):
        table = camp(self)
        table.act(HIT)
        table.act('5')
        result = table.act('6')
        self.assertIn('already landed', result.public_event)
        self.assertEqual(table.fight['hp']['cutthroat_a'], 6)


class TwoOpenAsks(unittest.TestCase):
    """A held damage ask and a called Perception check at once: each roll answers its own ask, and
    a roll that could be either holds both (never lands damage and clears the check)."""

    def both(self):
        table = camp(self)
        table.act(HIT)
        call_check(table)
        self.assertEqual(table.state['pending_check']['skill'], 'perception')
        return table

    def test_a_named_check_roll_answers_the_check_and_the_damage_waits(self):
        table = self.both()
        table.act('Perception 16')
        self.assertIsNone(table.state.get('pending_check'))
        self.assertEqual(table.fight['pending']['needs'], 'damage')
        self.assertEqual(table.fight['hp']['cutthroat_a'], 11)

    def test_a_roll_that_could_be_either_holds_both(self):
        for words in ('16 not 6', '6', 'actually 6'):
            with self.subTest(words=words):
                table = self.both()
                result = table.act(words)
                self.assertEqual(table.fight['hp']['cutthroat_a'], 11, words)
                self.assertEqual(table.fight['pending']['needs'], 'damage', words)
                self.assertEqual((table.state.get('pending_check') or {}).get('skill'), 'perception', words)
                self.assertIn('Two rolls are open', result.public_event)

    def test_a_stated_damage_answers_the_damage(self):
        table = self.both()
        table.act('6 damage')
        self.assertEqual(table.fight['hp']['cutthroat_a'], 5)


class CalledCheckCorrections(unittest.TestCase):
    """On main: a correction on a called check was refused, and a refused attempt cleared the call."""

    def test_a_correction_answers_the_called_check(self):
        for words in ('actually 6', 'oops, 16', '16 not 6', 'Actually it was 16 not 6'):
            with self.subTest(words=words):
                table = camp(self)
                call_check(table)
                table.act(words)
                self.assertIsNone(table.state.get('pending_check'), words)

    def test_a_refused_attempt_never_clears_an_open_ask(self):
        table = camp(self)
        call_check(table)
        table.runtime.record_refused_attempt('I do something odd.', 'needs a ruling')
        self.assertEqual(table.state['pending_check']['skill'], 'perception')
