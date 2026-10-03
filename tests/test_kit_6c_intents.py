"""Scorecard items 2-5 of the 6c variety baseline (2026-10-03): toll intent, social checks
rolled in conversation, card-table robustness, and validator noise. Every die is pinned:
the player's rolls are stated the way Avrae reports them, and Kit's own d20 is overridden."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_agent, kit_guards, kit_toll, kit_twenty_one
from runtime.kit_agent import Room6CAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_voice import HardeningGuardTests, SHOWTIME_SPEECH, VoiceTestCase

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'level_01_area_06c.json'
SHEETS = ROOT / 'tests' / 'fixtures' / 'characters'


class Room:
    def __init__(self, test, sheet='example_pc.json', toll=True, roll=lambda: 10, seed=3):
        temp = tempfile.TemporaryDirectory()
        test.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        test.addCleanup(self.runtime.close)
        with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{seed:032x}'):
            self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.runtime.set_player_sheet(json.loads((SHEETS / sheet).read_text()))
        if toll:
            revision, state = self.runtime.load()
            events = []
            for key, (config, body) in kit_toll.here(self.runtime.source(), state).items():
                body.update(status='demanded', demanded_by=config['demanded_by'])
                events.append(kit_toll.event(key, body, 'The dealer demanded the toll.'))
            self.runtime.commit('toll', revision, events)
        self.adjudicator = Room6CAdjudicator(roll=roll, source=self.runtime.source())

    def act(self, action):
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(action, revision, state)
        self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    @property
    def state(self):
        return self.runtime.load()[1]

    def toll(self):
        return self.state['tolls']['passage_toll']

    def game(self):
        return self.state['procedures']['twenty_one']['public']


class TollIntentTests(unittest.TestCase):
    DEMANDED = {'status': 'demanded', 'asked': 10, 'agreed': None}

    def intent(self, action, **body):
        return kit_toll.intent(action, {**self.DEMANDED, **body})

    def test_a_payment_made_with_a_weapon_is_a_threat(self):
        for action in ("Toll? I slam my axe into the table. 'I pay with this. Who wants change?'",
                       "'Here's your toll,' I say, and draw my sword.",
                       "I pay you with steel."):
            with self.subTest(action=action):
                self.assertEqual(self.intent(action), 'toll_threaten')

    def test_an_appeal_is_never_a_refusal(self):
        for action in ("'Our kind look after our own. No toll between family, surely?'",
                       "'Oh, the toll? Harria settled it for me at the well.'",
                       "Could you waive it, just this once?"):
            with self.subTest(action=action):
                self.assertEqual(self.intent(action), 'toll_appeal')

    def test_a_stated_social_roll_on_the_toll_is_the_contest_in_that_skill(self):
        self.assertEqual(self.intent("'You'd hate for Harria to hear of this.' [Persuasion: 1d20 (9) + 5 = 14]"),
                         'toll_appeal')
        self.assertEqual(self.intent("'Move aside.' [Intimidation: I rolled 15 + 4 = 19]"), 'toll_threaten')
        self.assertEqual(self.intent("'I'll give you three.' [Persuasion: 11]"), 'toll_haggle')

    def test_a_greeting_with_kinship_words_is_not_a_bid_on_the_toll(self):
        self.assertIsNone(kit_toll.intent("I step in. 'Cousins. Others of the blood this close to the surface.'",
                                          {**self.DEMANDED, 'status': 'not_raised'}))

    def test_a_question_ending_in_a_closing_quote_is_still_a_question(self):
        self.assertTrue(kit_toll.is_question("'No toll, surely?'"))
        self.assertNotEqual(self.intent("'Ten gold to pay? For what?' [Insight: 12]"), 'toll_refuse')

    def test_only_steering_to_the_game_defers_the_toll(self):
        self.assertEqual(self.intent("'I'll bet fifty gold.'"), 'toll_defer')
        for action in ("Dwarves? I look back at the card players, then I search the little dwarf figures. "
                       "[Perception: I rolled 13 + 4 = 17]",
                       "'Please, go on with your game. I'm only admiring the stonework.'",
                       "I pull up a chair. 'Do you lot play blackjack? I don't know your fancy games.'"):
            with self.subTest(action=action):
                self.assertIsNone(self.intent(action))

    def test_plain_payment_and_refusal_still_read(self):
        self.assertEqual(self.intent('I pay the toll.'), 'toll_pay')
        self.assertEqual(self.intent("I'm not paying."), 'toll_refuse')


class TollPlayTests(unittest.TestCase):
    def test_a_threat_that_lands_waives_the_toll_and_one_that_fails_is_a_refusal(self):
        room = Room(self, sheet='nik.json')
        result = room.act("Toll? I slam my staff on the table. 'I pay with this.' [Intimidation: I rolled 18 + 1 = 19]")
        self.assertEqual(result.kind, 'toll_threaten')
        self.assertEqual(room.toll()['status'], 'waived')
        room = Room(self, sheet='nik.json')
        result = room.act("Toll? I slam my staff on the table. 'I pay with this.' [Intimidation: I rolled 1 + 1 = 2]")
        self.assertEqual(room.toll()['status'], 'refused')
        self.assertIn('does not land', result.public_event)
        self.assertNotIn('2', result.public_event, 'no totals in public text')

    def test_an_appeal_uses_the_deception_the_player_rolled(self):
        room = Room(self, sheet='nik.json')
        result = room.act("'Our kind look after our own. No toll between family, surely?' [Deception: 1d20 (17) + 1 = 18]")
        self.assertEqual(result.kind, 'toll_appeal')
        self.assertEqual(room.toll()['status'], 'waived')
        evidence = json.dumps(result.events)
        self.assertIn('Deception d20 17 + 1 = 18', evidence)

    def test_stopping_at_the_door_to_question_the_toll_does_not_leave(self):
        room = Room(self)
        result = room.act("I stop at the door. 'Ten gold just to walk through a room? For what, exactly?'")
        self.assertNotEqual(result.kind, 'exit')
        self.assertEqual(room.state['area'], 'area_06c')


class SocialCheckTests(unittest.TestCase):
    def test_avrae_format_counts_and_the_total_is_used(self):
        room = Room(self, toll=False)
        result = room.act("'You don't want trouble with me.' [Persuasion: 1d20 (3) + 2 = 5]")
        self.assertEqual(result.kind, 'social_check')
        self.assertIn('not moved', result.public_event)
        self.assertIn('d20 3 + 2 = 5', json.dumps(result.events))

    def test_a_bare_stated_number_is_the_total_and_the_bonus_is_not_added_again(self):
        room = Room(self, sheet='nik.json', toll=False)
        bonus = json.loads((SHEETS / 'nik.json').read_text())['skills']['deception']
        result = room.act("'I'm with the Watch.' I rolled 17 for Deception.")
        self.assertIn(f'd20 {17 - bonus} + {bonus} = 17', json.dumps(result.events))
        self.assertEqual(result.public_event, 'The dealer believes you.')

    def test_each_social_skill_counts(self):
        for skill in ('Deception', 'Persuasion', 'Intimidation', 'Athletics'):
            with self.subTest(skill=skill):
                room = Room(self, toll=False)
                result = room.act(f"'Sit down.' [{skill}: 1d20 (20) + 0 = 20]")
                self.assertEqual(result.kind, 'social_check')

    def test_insight_rolled_while_talking_reads_the_group(self):
        room = Room(self, toll=False)
        result = room.act("I lean over the dealer and breathe in. 'Which nest turned you?' [Insight: 1d20 (19) + 1 = 20]")
        self.assertEqual(result.kind, 'check')
        self.assertIn('false_vampires', room.state['known_facts'])


class CardRobustnessTests(unittest.TestCase):
    def test_being_dealt_in_is_joining(self):
        room = Room(self, toll=False)
        result = room.act('I take the empty chair and ask the dealer what a lady has to do to be dealt in.')
        self.assertEqual(result.kind, 'card_offer')

    def test_a_spoken_bet_over_the_table_limit_is_capped_and_said(self):
        room = Room(self, toll=False)
        result = room.act("'I'll bet fifty gold.'")
        self.assertEqual(result.kind, 'card_offer')
        self.assertEqual(room.game()['pending_bet'], 25)
        self.assertIn('most this table plays is 25 gp', result.public_event)

    def test_a_bet_over_the_purse_is_capped_at_the_purse(self):
        room = Room(self, toll=False)
        room.act('I buy in with 12 gold.')
        result = room.act('I bet 20 gold.')
        self.assertIn('all you brought', result.public_event)
        self.assertEqual(room.game()['pending_bet'], 12)

    def test_number_words_and_a_hit_in_the_same_breath(self):
        room = Room(self, toll=False)
        room.act("'I'll bet fifty gold.'")
        result = room.act("'Fine, twenty, and I'll play it out. Hit.'")
        self.assertEqual(room.game()['round']['stake'], 20)
        self.assertIn('You take the', result.public_event)
        self.assertEqual(len(room.game()['round']['cards']), 3)

    def test_asking_whether_they_play_is_not_choosing_to_play(self):
        room = Room(self)
        result = room.act("I pull up a chair. 'Do you lot play blackjack? I don't know your fancy games.'")
        self.assertEqual(result.kind, 'social')
        self.assertNotIn('procedures', room.state)

    def test_twenty_one_is_the_game_not_a_bet(self):
        self.assertIsNone(kit_twenty_one.player_amount("Let's play twenty-one.", loose=True))
        self.assertEqual(kit_twenty_one.player_amount('Fine, twenty.', loose=True), 20)
        self.assertEqual(kit_twenty_one.player_amount('I bet twenty-five gold.'), 25)
        self.assertIsNone(kit_twenty_one.player_amount('I rolled 1 + 0 = 1.', loose=True))

    def test_mid_hand_accusations_and_talk_never_bring_back_the_menu(self):
        room = Room(self, toll=False)
        room.act('I bet 10 gold and play it out.')
        self.assertEqual(room.game()['round']['phase'], 'play')
        accused = room.act("I grab his wrist mid-deal. 'That one came from the bottom. Turn the deck over.'")
        self.assertEqual(accused.kind, 'card_accuse')
        self.assertNotIn('Which way?', accused.public_event)

    def test_just_roll_mid_hand_settles_the_hand_on_a_check(self):
        room = Room(self, toll=False)
        room.act('I bet 10 gold and play it out.')
        result = room.act("'Just roll for this one, I'm tired of counting.'")
        self.assertEqual(result.kind, 'card_mode_check')
        self.assertEqual(room.game()['round']['phase'], 'done')

    def test_joining_and_watching_in_one_breath(self):
        room = Room(self, toll=False)
        result = room.act("I sit, put down ten gold, and say I'll play. I watch the dealer's hands the whole time.")
        self.assertEqual(result.kind, 'card_watch')
        self.assertIsNotNone(room.game()['player'])
        self.assertTrue(room.game()['watch_next_deal'])
        self.assertEqual(room.game()['pending_bet'], 10)


class ValidatorNoiseTests(VoiceTestCase):
    ACTION = HardeningGuardTests.ACTION
    guarded = HardeningGuardTests.guarded
    showtime_plan = HardeningGuardTests.showtime_plan

    def test_every_problem_is_reported_at_once(self):
        speech = {'segments': SHOWTIME_SPEECH['segments'] + [
            {'speaker': 'Narrator', 'text': 'You agree to pay, and you feel terrified.'},
            {'speaker': 'Dealer', 'text': 'Uktarl never loses.'}]}
        with self.assertRaises(InvalidChange) as caught:
            self.guarded(speech, self.showtime_plan())
        message = str(caught.exception)
        self.assertRegex(message, r'^\d+ problems; fix all of them')
        self.assertIn('private fact', message)
        self.assertIn('(2)', message)

    def test_all_problems_keeps_a_single_message_as_is(self):
        self.assertEqual(kit_agent.all_problems(['One thing.', 'One thing.']), 'One thing.')

    def test_a_name_the_player_said_stays_usable_on_later_turns(self):
        phrases = {**kit_guards.leak_phrases(self.runtime.source()), 'player_said': ['harria']}
        kit_agent.check_public_content('Dealer: Harria sends nobody.', {}, 'I nod.', phrases=phrases)
        with self.assertRaises(InvalidChange):
            kit_agent.check_public_content('Dealer: Harria sends nobody.', {}, 'I nod.',
                                           phrases={**phrases, 'player_said': []})

    def test_the_turn_records_the_names_the_player_has_said(self):
        self.assertEqual(kit_agent.player_named(self.runtime, 'Harria sent me.'), ['harria'])


class GuardFalseAlarmTests(unittest.TestCase):
    def test_a_mountain_dwarf_is_a_dwarf(self):
        kit_guards.check_player_identity([{'speaker': 'Dealer', 'text': 'Sit down, dwarf.'}],
                                         {'name': 'Brakka', 'ancestry': 'Dwarf (Mountain)'})
        with self.assertRaises(InvalidChange):
            kit_guards.check_player_identity([{'speaker': 'Dealer', 'text': "You're an elf."}],
                                             {'name': 'Brakka', 'ancestry': 'Dwarf (Mountain)'})

    def test_a_speaker_label_is_not_a_leak_keyword(self):
        sets = kit_guards.leak_sets(json.loads(FIXTURE.read_text()))
        kit_guards.check_paraphrased_leaks('The Fresco-side player lifted his cup.', {}, '', sets,
                                           labels=('Fresco-side player', 'Dealer'))
        with self.assertRaises(InvalidChange):
            kit_guards.check_paraphrased_leaks('One carved dwarf lifted slightly.', {}, '', sets,
                                               labels=('Fresco-side player',))

    def test_asking_what_is_in_the_tub_reads_the_source_not_an_invention(self):
        room = Room(self, toll=False)
        result = room.act("I crouch by the stone tub. What's in it?")
        self.assertEqual(result.kind, 'inspect_tub')
        self.assertIn('tub_stash', room.state['known_facts'])


if __name__ == '__main__':
    unittest.main()
