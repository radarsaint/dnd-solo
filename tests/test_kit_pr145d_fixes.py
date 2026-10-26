"""PR 145 retest (pr145d) fixes: the lobby question rides the opening, is confirmed only when the
reply really asks it, is exempt from the length caps; appraise keeps quantities after
question words and reads written numbers."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

from runtime import kit_agent, kit_appraise, kit_campaign, kit_voice
from runtime.state_context import InvalidChange

ROOT = Path(__file__).resolve().parents[1]
NIK = json.loads((ROOT / 'tests/fixtures/characters/nik.json').read_text(encoding='utf-8'))
ASKS = "One thing, Nik: where did you pick up a shield and calligraphy? Pitch me the story."


class QuestionBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'kit.sqlite')
        self.modules = os.path.join(self.tmp, 'modules')
        os.mkdir(self.modules)
        room = json.loads((ROOT / 'tests/fixtures/level_01_area_06c.json').read_text(encoding='utf-8'))
        room.pop('fixture_only', None)
        self.room = os.path.join(self.modules, 'room.json')
        Path(self.room).write_text(json.dumps(room), encoding='utf-8')
        sheet = json.loads(json.dumps(NIK))
        sheet.update(name='Copy of Nik', armor_proficiencies=['Shield'],
                     tool_proficiencies=["Calligrapher's Supplies"], features=[], feats=[],
                     background='Sage', ancestry='Harengon')
        self.sheet = os.path.join(self.tmp, 'nik.json')
        Path(self.sheet).write_text(json.dumps(sheet), encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def check(self):
        return kit_campaign.campaign_entry(self.db, intent='play', rooms_dir=self.modules,
                                           sheet_path=self.sheet)['proficiency_check']

    def key(self):
        return json.loads(json.dumps(kit_campaign._asked_key(
            'Nik', [{'proficiency': 'Shield'}, {'proficiency': "Calligrapher's Supplies"}])))


class OpeningCarriesQuestionTests(QuestionBase):
    def test_start_room_packet_carries_it(self):
        first = self.check()
        result = {'stage': 'started', 'prepared': {'turn_id': 'open1'}}
        kit_agent._lobby_question_delivery(
            types.SimpleNamespace(command='start', db=self.db, table_talk=False, turn_id=None), result)
        self.assertEqual(result['prepared']['lobby_question']['id'], first['question_id'])
        self.assertEqual(kit_campaign.carried_question(self.db, 'open1')['id'], first['question_id'])

    def test_start_cli_opening_carries_it(self):
        self.check()
        out = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'start', '--db', self.db,
                              '--room', self.room, '--sheet', self.sheet, '--table', 'solo'],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        prepared = json.loads(out.stdout)['prepared']
        self.assertIn('shield', prepared['lobby_question']['table_line'])
        self.assertIsNotNone(kit_campaign.carried_question(self.db, prepared['turn_id']))


class DeliveryVerifiedTests(QuestionBase):
    def carry(self, turn='t1'):
        self.check()
        kit_agent._lobby_question_delivery(
            types.SimpleNamespace(command='prepare', table_talk=False, db=self.db, turn_id=None), {'turn_id': turn})

    def commit(self, spoken, turn='t1'):
        result = {'committed': True, 'spoken': spoken}
        kit_agent._lobby_question_delivery(
            types.SimpleNamespace(command='complete', table_talk=False, db=self.db, turn_id=turn), result)
        return result

    def test_reply_without_question_stays_pending(self):
        self.carry()
        result = self.commit("You're in, Nik, and the room is very politely ignoring you. Where do you look?")
        self.assertFalse(result['lobby_question_delivered'])
        self.assertIsNotNone(kit_campaign.pending_question(self.db))

    def test_naming_only_one_item_is_not_enough(self):
        self.carry()
        self.assertFalse(self.commit('A shield hangs on the wall. Where did you learn to use one?')
                         ['lobby_question_delivered'])

    def test_reply_in_kits_own_words_confirms(self):
        self.carry()
        self.assertTrue(self.commit(ASKS)['lobby_question_delivered'])
        self.assertIsNone(kit_campaign.pending_question(self.db))
        self.assertTrue(self.check()['already_asked'])

    def test_no_ask_signal_is_not_asking(self):
        self.assertFalse(kit_campaign.question_asked_in(self.key(), 'Shield and calligrapher kit on the table.'))
        self.assertTrue(kit_campaign.question_asked_in(self.key(), "Shields and calligrapher's supplies: where from?"))

    def test_unconfirmed_rides_next_turn(self):
        self.carry('t1')
        self.commit('Nothing here.', 't1')
        packet = {'turn_id': 't2'}
        kit_agent._lobby_question_delivery(
            types.SimpleNamespace(command='prepare', table_talk=False, db=self.db, turn_id=None), packet)
        self.assertIn('lobby_question', packet)


class LengthCapExemptionTests(QuestionBase):
    def segments(self, extra):
        return [{'speaker': 'Narrator', 'text': ' '.join(['word'] * 145) + '.'},
                {'speaker': 'Kit', 'text': extra}]

    def plan(self, scope='feature'):
        return {'public_brief': {'scope': scope, 'mirror': 'steady energy, tight, dry humor: keep it moving'}}

    def test_cap_still_applies_without_question(self):
        with self.assertRaises(InvalidChange):
            kit_voice.check_voice_style(self.segments('Something long and chatty about nothing at all.'), self.plan())

    def test_question_words_are_exempt(self):
        self.check()
        kit_campaign.carry_question(self.db, 't9')
        segs = self.segments(ASKS)
        with kit_voice.question_allowance(lambda s: kit_campaign.question_word_allowance(self.db, 't9', s)):
            kit_voice.check_voice_style(segs, self.plan())
        with self.assertRaises(InvalidChange):
            kit_voice.check_voice_style(segs, self.plan())

    def test_allowance_only_when_asked(self):
        self.check()
        kit_campaign.carry_question(self.db, 't9')
        self.assertGreater(kit_campaign.question_word_allowance(self.db, 't9', ASKS), 20)
        self.assertEqual(kit_campaign.question_word_allowance(self.db, 't9', 'Where now?'), 0)
        self.assertEqual(kit_campaign.question_word_allowance(self.db, 'other', ASKS), 0)


class AppraiseQuantityTests(unittest.TestCase):
    def test_aux_after_question_word_keeps_quantity(self):
        for q in ('how much are 3 healing potions?', 'what are 3 healing potions worth?',
                  'how much do 3 potions of healing cost?', 'what would 3 healing potions go for?'):
            out = kit_appraise.price(q)
            self.assertEqual(out['item'], 'Potion of Healing', q)
            self.assertEqual(out['quantity'], 3, q)
            self.assertEqual(out['transaction_total'], 210, q)

    def test_single_item_questions_unchanged(self):
        for q in ('how much is a potion of healing?', "what's a potion of healing worth?",
                  'what does a potion of healing cost?'):
            out = kit_appraise.price(q)
            self.assertEqual((out['item'], out['final_price']), ('Potion of Healing', 70), q)

    def test_written_numbers(self):
        cases = {'two potions of greater healing': 2, 'how much are twelve healing potions?': 12,
                 'a dozen potions of healing': 12, 'a pair of healing potions': 2,
                 'a couple of healing potions': 2, 'twenty potions of healing': 20}
        for q, n in cases.items():
            out = kit_appraise.price(q)
            self.assertEqual(out['quantity'], n, q)
        self.assertEqual(kit_appraise.price('two potions of greater healing')['item'], 'Potion of Greater Healing')

    def test_a_or_an_is_one(self):
        self.assertEqual(kit_appraise.leading_count('a potion of healing'), (1, 'potion of healing'))
        self.assertEqual(kit_appraise.leading_count('an elixir'), (1, 'elixir'))
        self.assertIsNone(kit_appraise.leading_count('potion of healing'))
        self.assertEqual(kit_appraise.leading_count('seven healing potions')[0], 7)


if __name__ == '__main__':
    unittest.main()
