"""PR 145 re-run fixes: in-play real name, appraise phrasing + SRD defaults, unsourced question once and all at once."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime import kit_appraise, kit_campaign, kit_chargen, pc_sheet

ROOT = Path(__file__).resolve().parents[1]
NIK = json.loads((ROOT / 'tests/fixtures/characters/nik.json').read_text(encoding='utf-8'))


def nik(**changes):
    sheet = json.loads(json.dumps(NIK))
    sheet.update(changes)
    return sheet


class InPlayNameTests(unittest.TestCase):
    def test_identity_and_private_summary_use_real_name(self):
        sheet = nik(name='Copy of Nik')
        self.assertEqual(pc_sheet.identity(sheet)['name'], 'Nik')
        self.assertEqual(pc_sheet.private_summary(sheet)['name'], 'Nik')

    def test_character_name_field_wins(self):
        sheet = nik(name='Copy of sheet', character_name='Nik')
        self.assertEqual(pc_sheet.identity(sheet)['name'], 'Nik')


class AppraiseTests(unittest.TestCase):
    def test_question_phrasing_is_stripped(self):
        for q in ("what's a potion of healing worth?", 'How much is a potion of healing?',
                  'price a potion of healing', 'what would a potion of healing cost?', 'potion of healing'):
            out = kit_appraise.price(q)
            self.assertEqual(out['item'], 'Potion of Healing', q)
            self.assertEqual(out['final_price'], 70, q)

    def test_srd_potion_defaults_to_2d4_plus_2(self):
        self.assertIn('2d4+2', kit_appraise._command('potion of healing'))
        self.assertIn('Final Price', kit_appraise.appraise("what's a potion of healing worth?"))
        self.assertIn('70 gp', kit_appraise.appraise("what's a potion of healing worth?"))

    def test_user_dice_and_rarity_are_kept(self):
        cmd = kit_appraise._command('potion of healing uncommon potion 4d4+4')
        self.assertNotIn('2d4+2', cmd)
        self.assertNotIn('common potion 2d4', cmd)

    def test_sell_mode_survives_stripping(self):
        self.assertEqual(kit_appraise.price('sell potion of healing')['mode'].lower(), 'sell')


class UnsourcedQuestionTests(unittest.TestCase):
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

    def entry(self):
        return kit_campaign.campaign_entry(self.db, intent='play', rooms_dir=self.modules, sheet_path=self.sheet)

    def test_all_unsourced_in_one_natural_question(self):
        out = kit_chargen.proficiency_sources(json.loads(Path(self.sheet).read_text()))
        self.assertEqual(len(out['unsourced']), 2)
        line = out['table_line']
        self.assertIn("where did Nik learn to use a shield and calligrapher's supplies?", line)
        self.assertNotIn('pick up', line)
        self.assertEqual(line.count('?'), 1)

    def test_natural_wording(self):
        self.assertEqual(kit_chargen.natural_proficiency('Shields'), 'a shield')
        self.assertEqual(kit_chargen.natural_proficiency('Heavy Armor'), 'heavy armor')
        self.assertEqual(kit_chargen.natural_proficiency('Longsword'), 'a longsword')
        self.assertEqual(kit_chargen.natural_proficiency("Herbalism Kit"), 'a herbalism kit')
        self.assertEqual(kit_chargen.natural_list(['a', 'b', 'c']), 'a, b, and c')

    def test_raised_once_per_save(self):
        first = self.entry()['proficiency_check']
        self.assertIn('table_line', first)
        self.assertFalse(first['already_asked'])
        for _ in range(2):
            again = self.entry()['proficiency_check']
            self.assertNotIn('table_line', again)
            self.assertTrue(again['already_asked'])
            self.assertEqual(len(again['unsourced']), 2)  # still reported, just not re-asked
        self.assertTrue(kit_campaign.proficiency_question_asked(
            self.db, 'Nik', first['unsourced']))

    def test_new_unsourced_item_is_asked(self):
        self.entry()
        sheet = json.loads(Path(self.sheet).read_text())
        sheet['weapon_proficiencies'] = sheet.get('weapon_proficiencies', []) + ['Longsword']
        Path(self.sheet).write_text(json.dumps(sheet))
        self.assertIn('table_line', self.entry()['proficiency_check'])


if __name__ == '__main__':
    unittest.main()
