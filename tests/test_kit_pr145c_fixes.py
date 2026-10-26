"""PR 145 c-run fixes: lobby question pending until delivered, general appraise phrasing,
item-name variants, real name in the stored sheet."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

from runtime import kit_agent, kit_appraise, kit_campaign, pc_sheet
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
NIK = json.loads((ROOT / 'tests/fixtures/characters/nik.json').read_text(encoding='utf-8'))


def nik(**changes):
    sheet = json.loads(json.dumps(NIK))
    sheet.update(changes)
    return sheet


class PendingQuestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'kit.sqlite')
        self.modules = os.path.join(self.tmp, 'modules')
        os.mkdir(self.modules)
        room = json.loads((ROOT / 'tests/fixtures/level_01_area_06c.json').read_text(encoding='utf-8'))
        room.pop('fixture_only', None)
        Path(self.modules, 'room.json').write_text(json.dumps(room), encoding='utf-8')
        self.sheet = os.path.join(self.tmp, 'nik.json')
        Path(self.sheet).write_text(json.dumps(nik(
            name='Copy of Nik', armor_proficiencies=['Shield'], tool_proficiencies=["Calligrapher's Supplies"],
            features=[], feats=[], background='Sage', ancestry='Harengon')), encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def check(self):
        return kit_campaign.campaign_entry(self.db, intent='play', rooms_dir=self.modules,
                                           sheet_path=self.sheet)['proficiency_check']

    def test_dropped_reply_is_asked_again(self):
        first = self.check()
        self.assertIn('table_line', first)
        self.assertFalse(kit_campaign.proficiency_question_asked(self.db, 'Nik', first['unsourced']))
        # The host dropped that reply; the next lobby calls raise it again, same id.
        for _ in range(2):
            again = self.check()
            self.assertIn('table_line', again)
            self.assertFalse(again['already_asked'])
            self.assertEqual(again['question_id'], first['question_id'])
        self.assertEqual(kit_campaign.pending_question(self.db)['shown'], 3)

    def test_host_confirmation_marks_asked(self):
        first = self.check()
        self.assertTrue(kit_campaign.confirm_question_delivered(self.db, question_id=first['question_id']))
        self.assertIsNone(kit_campaign.pending_question(self.db))
        self.assertNotIn('table_line', self.check())
        self.assertFalse(kit_campaign.confirm_question_delivered(self.db, question_id=first['question_id']))

    def test_cli_question_delivered(self):
        qid = self.check()['question_id']
        out = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'start', '--db', self.db,
                              '--question-delivered', qid], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)['confirmed'])
        self.assertTrue(self.check()['already_asked'])

    def test_play_packet_carries_it_and_commit_confirms(self):
        first = self.check()
        args = types.SimpleNamespace(command='prepare', table_talk=False, db=self.db, turn_id=None)
        packet = {'turn_id': 't1'}
        kit_agent._lobby_question_delivery(args, packet)
        self.assertEqual(packet['lobby_question']['id'], first['question_id'])
        self.assertIn('shield', packet['lobby_question']['table_line'])
        # A rejected complete does not confirm; a committed one does.
        done = types.SimpleNamespace(command='complete', table_talk=False, db=self.db, turn_id='t1')
        kit_agent._lobby_question_delivery(done, {'committed': False})
        self.assertIsNotNone(kit_campaign.pending_question(self.db))
        result = {'committed': True}
        kit_agent._lobby_question_delivery(done, result)
        self.assertTrue(result['lobby_question_delivered'])
        self.assertTrue(self.check()['already_asked'])

    def test_table_talk_does_not_carry(self):
        self.check()
        packet = {'turn_id': 't1'}
        kit_agent._lobby_question_delivery(
            types.SimpleNamespace(command='prepare', table_talk=True, db=self.db, turn_id=None), packet)
        self.assertNotIn('lobby_question', packet)

    def test_changed_sheet_replaces_pending(self):
        self.check()
        sheet = json.loads(Path(self.sheet).read_text())
        sheet['weapon_proficiencies'] = sheet.get('weapon_proficiencies', []) + ['Longsword']
        Path(self.sheet).write_text(json.dumps(sheet))
        newer = self.check()
        self.assertEqual(kit_campaign.pending_question(self.db)['id'], newer['question_id'])


class AppraisePhrasingTests(unittest.TestCase):
    def test_sell_keeps_intent_and_clean_name(self):
        for q in ('sell a potion of healing', 'I want to sell the potion of healing',
                  'how much could I sell a potion of healing for?', 'Kit, sell my potion of healing please'):
            out = kit_appraise.price(q)
            self.assertEqual(out['item'], 'Potion of Healing', q)
            self.assertEqual(out['mode'].lower(), 'sell', q)
            self.assertEqual(out['final_price'], 35, q)

    def test_possessive_and_of_phrasings(self):
        for q in ("what's the potion of healing's value?", 'what is the price of a potion of healing?',
                  'value of a potion of healing', "the potion of healing's worth?",
                  'what would a potion of healing sell for?', 'hey, how much does a potion of healing cost?'):
            out = kit_appraise.price(q)
            self.assertEqual(out['item'], 'Potion of Healing', q)
            self.assertEqual(out['mode'].lower(), 'buy', q)
            self.assertEqual(out['final_price'], 70, q)

    def test_general_not_one_off(self):
        out = kit_appraise.price('what is the price of a +1 longsword, uncommon weapon?')
        self.assertEqual(out['item'], '+1 Longsword')
        self.assertEqual(out['final_price'], kit_appraise.price('+1 longsword uncommon weapon')['final_price'])
        self.assertEqual(kit_appraise.price('sell a +1 longsword, uncommon weapon')['mode'].lower(), 'sell')


class NameVariantTests(unittest.TestCase):
    def test_variants_match_known_items(self):
        cases = {'healing potion': ('Potion of Healing', 70), 'potions of healing': ('Potion of Healing', 70),
                 'Healing Potion': ('Potion of Healing', 70),
                 "what's a greater healing potion worth?": ('Potion of Greater Healing', None),
                 'superior healing potion': ('Potion of Superior Healing', None)}
        for q, (item, price) in cases.items():
            out = kit_appraise.price(q)
            self.assertEqual(out['item'], item, q)
            if price:
                self.assertEqual(out['final_price'], price, q)
        self.assertEqual(kit_appraise.price('greater healing potion')['final_price'],
                         kit_appraise.price('potion of greater healing')['final_price'])

    def test_plural_count_becomes_quantity(self):
        out = kit_appraise.price('what are 3 healing potions worth?')
        self.assertEqual((out['item'], out['quantity'], out['transaction_total']), ('Potion of Healing', 3, 210))

    def test_variant_generator(self):
        self.assertIn('greater healing potions', kit_appraise.name_variants('potion of greater healing'))
        self.assertIn('Final Price', kit_appraise.appraise('healing potion'))


class StoredSheetNameTests(unittest.TestCase):
    def test_with_real_name(self):
        out = pc_sheet.with_real_name(nik(name='Copy of Nik'))
        self.assertEqual((out['name'], out['sheet_title']), ('Nik', 'Copy of Nik'))
        self.assertNotIn('sheet_title', pc_sheet.with_real_name(nik(name='Nik')))
        both = pc_sheet.with_real_name(nik(name='Copy of sheet', character_name='Nik'))
        self.assertEqual((both['name'], both['sheet_title']), ('Nik', 'Copy of sheet'))

    def test_stored_sheet_holds_real_name(self):
        tmp = tempfile.mkdtemp()
        try:
            ctx = Runtime(Path(tmp) / 'kit.sqlite')
            room = json.loads((ROOT / 'tests/fixtures/level_01_area_06c.json').read_text(encoding='utf-8'))
            ctx.initialize(room, 'area_06c')
            ctx.set_player_sheet(nik(name='Copy of Nik'))
            state = ctx.load()[1]
            self.assertEqual(state['player_sheet']['name'], 'Nik')
            self.assertEqual(state['player_sheet']['sheet_title'], 'Copy of Nik')
            self.assertEqual(state['player_character']['name'], 'Nik')
            ctx.close()
        finally:
            shutil.rmtree(tmp)


if __name__ == '__main__':
    unittest.main()
