"""Player-input router: object- and idiom-aware intent (Claude's router audit, re-probed by GPT
on 9b9d6e70; BOARD #70 entry). A verb acts on its own object: a violent verb is a strike only
when aimed at someone, a room feature is moved only when it is the verb's object, the PC's own
body at rest is a gesture, and words the player quoted stay speech. One rule set, no phrase
list; a regression test per reported phrase, with literal controls that must still route."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from runtime import kit_combat
from runtime.kit_agent import KitChatBridge, PendingRuling, Room6CAdjudicator, room_intent, social_event
from runtime.state_context import Runtime
from test_kit_agent import FIXTURE

NIK = Path(__file__).parent / 'fixtures/characters/nik.json'


class SixCRouting(unittest.TestCase):
    """The reported phrases, through the 6c room's adjudicator and bridge."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.runtime.set_player_sheet(json.loads(NIK.read_text()))
        self.adjudicator = Room6CAdjudicator(perception=0, insight=0, roll=lambda: 10)
        self.adjudicator.source = self.runtime.source()

    def kind(self, line):
        revision, state = self.runtime.load()
        try:
            return self.adjudicator.resolve(line, revision, state).kind
        except PendingRuling as exc:
            return f'pending: {exc}'

    def assertTalk(self, line):
        self.assertEqual(self.kind(line), 'social', line)

    def test_shoot_the_breeze_is_talk_not_an_attack(self):
        self.assertTalk('I shoot the breeze with the dealer.')

    def test_kill_time_is_not_combat(self):
        kind = self.kind('I kill time watching the cards.')
        self.assertFalse(kind.startswith('pending') or kind.startswith('combat'), kind)

    def test_thrust_my_chin_is_a_gesture(self):
        self.assertTalk('I thrust my chin at the dealer. "Your deal."')

    def test_question_their_fangs_is_talk(self):
        self.assertTalk('I question their fangs.')

    def test_a_chair_toward_the_tub_is_not_tipping_the_tub(self):
        for line in ('I move my chair closer to the tub.', 'I move my chair toward the tub.'):
            with self.subTest(line=line):
                self.assertTalk(line)

    def test_pocketing_a_coin_covertly_is_a_covert_take(self):
        for line in ("I pocket a coin from the pile while nobody's looking.", 'I pocket a coin covertly.'):
            with self.subTest(line=line):
                revision, state = self.runtime.load()
                result = self.adjudicator.resolve(line, revision, state)
                self.assertEqual(result.kind, 'physical_act')  # no fight: nobody saw it
                self.assertIn('take coins', result.events[0]['evidence'])

    def test_harmless_gestures_are_table_business(self):
        for line in ('I raise a toast to the table.', 'I kick back in my chair.', 'I clean my nails with a knife.',
                     'I lean back and kick my feet up.', 'I crack my knuckles.', 'I stretch and yawn.'):
            with self.subTest(line=line):
                self.assertTalk(line)

    def test_quoted_speech_is_recorded_once_as_speech(self):
        line = '"Deal me in," I say.'
        self.assertEqual(self.kind(line), 'social')
        bridge = KitChatBridge(self.runtime, self.adjudicator)
        event = bridge.prepare(line, 'quoted')['input']['accepted_public_event']
        self.assertEqual(event, 'You declare: "\'Deal me in,\' I say."')
        self.assertEqual(event.count('"'), 2)

    def test_literal_acts_still_route(self):
        self.assertIn('attack', self.kind('I attack the dealer.'))
        self.assertIn('crossbow', self.kind('I shoot the dealer with my crossbow.'))
        self.assertIn('attack', self.kind('I kick him in the gut.'))
        self.assertIn('dagger', self.kind('I thrust my dagger at the dealer.'))
        self.assertEqual(self.kind('I tip the tub over.'), 'tip_tub')
        self.assertEqual(self.kind('I grab a coin from the pile.'), 'combat_round')  # seen: the fight starts
        self.assertEqual(room_intent('I attack Uktarl in the middle of the game.'), 'combat')


class AnyRoomRouting(unittest.TestCase):
    """General engine, no room data: the verb-object rules on their own."""

    def aimed(self, text, names=()):
        verb = kit_combat.ATTACK.search(text)
        return kit_combat.aimed_attack(text, verb, names)

    def test_a_violent_verb_is_a_strike_only_when_aimed_at_someone(self):
        for text in ('i shoot the breeze with the guard', 'i kill time by the fire', 'i thrust my chin at her',
                     'i kick back on the bench', 'i kick my feet up', 'i cut the cards'):
            with self.subTest(text=text):
                self.assertFalse(self.aimed(text), text)
        for text in ('i attack the guard', 'i shoot at the captain', 'i kick him', 'i stab the innkeeper',
                     "i cut the guard's throat", 'i thrust my spear at the troll', 'i attack!'):
            with self.subTest(text=text):
                self.assertTrue(self.aimed(text, ('innkeeper', 'troll')), text)

    def test_a_named_person_is_a_target_and_an_idiom_is_talk(self):
        self.assertEqual(room_intent('I attack Morwen at the bar.'), 'combat')
        self.assertEqual(room_intent('I shoot the breeze with Morwen.'), 'social')
        self.assertEqual(room_intent('I kill some time by the hearth.'), 'social')

    def test_quoted_speech_keeps_one_pair_of_quotes(self):
        self.assertEqual(social_event('She says "fine" and sits.'), 'You declare: "She says \'fine\' and sits."')

    def test_a_covert_clause_marks_a_take_covert(self):
        for text in ("while nobody's looking", 'while no one is watching', 'when their backs are turned',
                     'while the others are distracted', 'covertly'):
            with self.subTest(text=text):
                self.assertTrue(kit_combat.COVERT.search(f'i pocket a coin {text}'))
        self.assertFalse(kit_combat.COVERT.search('i pocket a coin while everyone watches'))


if __name__ == '__main__':
    unittest.main()
