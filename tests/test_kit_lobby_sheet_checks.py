"""PR 145 playtest fixes: proficiency sources, solo persisted early, lobby loads the sheet, manifest skipped."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_campaign, kit_chargen

ROOT = Path(__file__).resolve().parents[1]
NIK = json.loads((ROOT / 'tests/fixtures/characters/nik.json').read_text(encoding='utf-8'))


def nik(**changes):
    sheet = json.loads(json.dumps(NIK))
    sheet.update(changes)
    return sheet


class ProficiencySourceTests(unittest.TestCase):
    def test_wizard_shield_with_no_source_is_flagged_not_ruled(self):
        out = kit_chargen.proficiency_sources(nik(armor_proficiencies=['Shield'], feats=['War Caster'],
                                                  features=['Arcane Recovery']))
        self.assertEqual([u['proficiency'] for u in out['unsourced']], ['Shield'])
        self.assertFalse(out['auto_ruled'])
        self.assertTrue(out['raise_once'])
        self.assertIn('asking, not ruling', out['table_line'])
        self.assertIn('shield', out['table_line'])

    def test_class_feat_and_settled_sources_count(self):
        out = kit_chargen.proficiency_sources(nik(
            armor_proficiencies=['Light Armor', 'Medium Armor', 'Shields'],
            weapon_proficiencies=['Simple Weapons', 'Dagger'], tool_proficiencies=["Thieves' Tools"],
            feats=['Moderately Armored'], features=[],
            proficiency_sources={'Light Armor': 'Kit ruling 2026-10-25', "Thieves' Tools": 'background'}))
        self.assertEqual(out['unsourced'], [])
        by = {c['proficiency']: c['source'] for c in out['checked']}
        self.assertTrue(by['Dagger'].startswith('class: wizard'))
        self.assertTrue(by['Shields'].startswith('feat:'))
        self.assertTrue(by['Light Armor'].startswith('settled:'))

    def test_fighter_needs_nothing_and_unknown_class_is_noted(self):
        self.assertEqual(kit_chargen.proficiency_sources(
            nik(**{'class': 'Fighter 3', 'armor_proficiencies': ['Heavy Armor', 'Shields']}))['unsourced'], [])
        out = kit_chargen.proficiency_sources(nik(**{'class': 'Artificer', 'armor_proficiencies': ['Shields']}))
        self.assertIn('note', out)
        self.assertEqual(len(out['unsourced']), 1)

    def test_cli_check_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 's.json')
            Path(path).write_text(json.dumps(nik(armor_proficiencies=['Shield'], features=[], feats=[])))
            run = subprocess.run([sys.executable, '-m', 'runtime.kit_chargen', '--check-sheet', path],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['stage'], 'proficiency_check')

    def test_real_name_not_file_title(self):
        for title in ('Copy of Nik', 'Copy of Copy of Nik', 'Nik (2)', 'Nik'):
            self.assertEqual(kit_chargen.character_name({'name': title}), 'Nik')


class LobbyFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'kit.sqlite')
        self.modules = os.path.join(self.tmp, 'modules')
        os.mkdir(self.modules)
        self.sheet = os.path.join(self.tmp, 'nik.json')
        Path(self.sheet).write_text(json.dumps(nik(name='Copy of Nik', armor_proficiencies=['Shield'],
                                                   features=[], feats=[])), encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _module(self):
        room = json.loads((ROOT / 'tests/fixtures/level_01_area_06c.json').read_text(encoding='utf-8'))
        room.pop('fixture_only', None)
        Path(self.modules, 'room.json').write_text(json.dumps(room), encoding='utf-8')

    def entry(self, **kw):
        return kit_campaign.campaign_entry(self.db, intent='play', rooms_dir=self.modules, **kw)

    def test_solo_persists_while_waiting_for_module_and_character(self):
        out = self.entry(table='solo')
        self.assertEqual(out['stage'], 'need_module')
        self.assertEqual(kit_campaign.table_mode(self.db), 'solo')
        self.assertEqual(out['table_mode'], 'solo')
        self._module()
        out = self.entry()  # not re-passed
        self.assertEqual(out['stage'], 'need_character')
        out = self.entry(sheet_path=self.sheet)
        self.assertEqual(out['stage'], 'ready')
        self.assertEqual(out['table_mode'], 'solo')

    def test_lobby_loads_sheet_uses_real_name_and_checks_sources(self):
        self._module()
        out = self.entry(sheet_path=self.sheet)
        self.assertTrue(out['sheet_loaded'])
        self.assertTrue(out['character_loaded'])
        self.assertEqual(out['character']['name'], 'Nik')
        self.assertEqual(out['character']['sheet_title'], 'Copy of Nik')
        self.assertEqual([u['proficiency'] for u in out['proficiency_check']['unsourced']], ['Shield'])
        self.assertFalse(out['proficiency_check']['auto_ruled'])

    def test_lobby_reports_a_bad_sheet(self):
        self._module()
        Path(self.sheet).write_text('{"schema": "nope"}', encoding='utf-8')
        out = self.entry(sheet_path=self.sheet)
        self.assertEqual(out['stage'], 'need_character')
        self.assertFalse(out['sheet_loaded'])
        self.assertTrue(out['sheet_problems'])

    def test_pack_manifest_is_not_listed_as_a_room(self):
        self._module()
        Path(self.modules, 'manifest.json').write_text('{"pack": "x", "rooms": ["room.json"]}', encoding='utf-8')
        executable, blocked = kit_campaign.inspect_rooms(self.modules)
        self.assertEqual(len(executable), 1)
        self.assertFalse(any(b['path'].endswith('manifest.json') for b in blocked))


if __name__ == '__main__':
    unittest.main()
