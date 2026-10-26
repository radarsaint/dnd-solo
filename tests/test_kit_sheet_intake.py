"""P5 of the campaign-record design: sheet intake, light.

A D&D Beyond PDF is read from its form fields with the standard library and checked as
character_sheet_v1. A PDF without fields falls back to Kit with the text and the template.
A sheet loads whenever the player brings one; hand edits are noted, unsourced proficiencies asked.
The greeting asks a new campaign what the master sheet is. Synthetic PDFs only.
"""

import ast
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

from runtime import kit_agent, kit_campaign, kit_save, sheet_intake
from runtime.state_context import Runtime
from tests import sheet_pdf
from tests.test_kit_player_save import ROOMS, runtime_zip

ROOT = Path(__file__).resolve().parents[1]


def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
            unittest.mock.patch.object(sys, 'argv', ['kit_agent', *argv]):
        code = kit_agent.main()
    return code, json.loads(out.getvalue() or err.getvalue())


class Intake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def pdf(self, name='tamsin.pdf', **kw):
        path = self.dir / name
        path.write_bytes(sheet_pdf.build(**kw))
        return path


class ReadFields(Intake):
    def test_literal_hex_indirect_and_object_stream_fields(self):
        fields = sheet_intake.pdf_fields(self.pdf())
        self.assertEqual(fields['CharacterName'], 'Tamsin Reed')
        self.assertEqual(fields['EXPERIENCE POINTS'], '(Milestone)')
        self.assertIn('* Cunning Action', fields['FeaturesTraits1'])
        self.assertEqual(fields['BACKGROUND2'], 'Criminal')
        self.assertEqual((fields['GP'], fields['spellName2']), ('42', 'Charm Person'))
        self.assertEqual(fields['Stealth'], '+7')  # names trimmed

    def test_not_a_pdf_is_a_clear_error(self):
        path = self.dir / 'x.pdf'
        path.write_text('hello', encoding='utf-8')
        with self.assertRaises(sheet_intake.IntakeError):
            sheet_intake.pdf_fields(path)


class MapToSheet(Intake):
    def sheet(self, **kw):
        return sheet_intake.from_ddb_fields(sheet_intake.pdf_fields(self.pdf(**kw)))

    def test_a_ddb_export_becomes_a_valid_character_sheet(self):
        sheet, problems = self.sheet()
        self.assertIsNone(sheet_intake.check(sheet))
        self.assertEqual((sheet['name'], sheet['class'], sheet['level'], sheet['ancestry']),
                         ('Tamsin Reed', 'Rogue', 3, 'Halfling'))
        self.assertEqual(sheet['abilities'], {'str': 8, 'dex': 17, 'con': 13, 'int': 12, 'wis': 14, 'cha': 10})
        self.assertEqual((sheet['ac'], sheet['hp'], sheet['speed_ft'], sheet['proficiency_bonus']), (14, 21, 25, 2))
        self.assertEqual(sheet['skills']['stealth'], 7)
        self.assertEqual(sorted(sheet['expertise']), ['sleight_of_hand', 'stealth'])
        self.assertEqual(sheet['gold_gp'], 52)  # 42 gp + 1 pp
        self.assertEqual(sheet['coins'], {'cp': 3, 'gp': 42, 'pp': 1})
        self.assertEqual(sheet['languages'], ['Common', 'Halfling'])
        self.assertEqual(sheet['proficiencies']['armor'], ['Light Armor'])
        self.assertEqual(sheet['spells'], {'cantrips': ['Minor Illusion'], '1': ['Disguise Self', 'Charm Person']})
        self.assertEqual(sheet['slots'], {'1': 2})
        self.assertEqual(sheet['features'][:2], ['Sneak Attack', 'Cunning Action (1/short rest)'])
        self.assertEqual(sheet['attacks'], [{'name': 'Shortsword', 'attack_bonus': 5, 'damage': '1d6+3 Piercing',
                                             'notes': 'Finesse'}])
        self.assertEqual(sheet['subclass'], 'Thief')
        self.assertEqual([e['name'] for e in sheet['equipment']], ['Shortsword', "Thieves' Tools", 'Rope'])

    def test_a_passive_that_does_not_match_its_skill_is_left_out_and_named(self):
        sheet, problems = self.sheet()
        self.assertEqual(sheet['passives'], {'perception': 14, 'insight': 14})
        self.assertTrue(any('passive investigation' in p for p in problems))

    def test_proficiency_lists_are_read_as_printed_with_no_special_cases(self):
        fields = dict(sheet_pdf.HEX_FIELDS)
        fields['ProficienciesLang'] = '=== ARMOR === \nShield, Heavy Armor \n\n=== LANGUAGES === \nCommon'
        sheet, _ = self.sheet(hex_fields=fields)
        self.assertEqual(sheet['proficiencies'], {'armor': ['Shield', 'Heavy Armor']})

    def test_multiclass_levels_add_up(self):
        fields = dict(sheet_pdf.FIELDS, **{'CLASS  LEVEL': 'Rogue 3 / Wizard 2'})
        sheet, _ = self.sheet(fields=fields)
        self.assertEqual((sheet['class'], sheet['level']), ('Rogue 3 / Wizard 2', 5))


class ImportPdf(Intake):
    def test_import_writes_the_sheet_and_says_what_it_read(self):
        result = sheet_intake.import_pdf(self.pdf(), out=self.dir / 'tamsin.json')
        self.assertEqual(result['stage'], 'sheet_imported')
        self.assertEqual(result['summary'], {'name': 'Tamsin Reed', 'class': 'Rogue', 'level': 3, 'hp': 21, 'ac': 14})
        written = json.loads((self.dir / 'tamsin.json').read_text(encoding='utf-8'))
        self.assertEqual(written['schema'], 'character_sheet_v1')

    def test_no_form_fields_falls_back_to_kit_with_the_template(self):
        with unittest.mock.patch.object(sheet_intake.shutil, 'which', return_value=None):
            result = sheet_intake.import_pdf(self.pdf(with_fields=False))
        self.assertEqual(result['stage'], 'needs_kit')
        self.assertIsNone(result['text'])
        self.assertEqual(result['template'], 'tests/fixtures/characters/example_pc.json')
        self.assertIn('pypdf', result['next_step'])
        self.assertTrue(result['player_confirms'])
        for rule in ('only values printed', 'Never fill a blank', 'unread', 'after they confirm'):
            self.assertIn(rule, result['next_step'])

    def test_a_blank_ability_asks_kit_about_just_that(self):
        fields = dict(sheet_pdf.FIELDS, STR='')
        result = sheet_intake.import_pdf(self.pdf(fields=fields))
        self.assertEqual(result['stage'], 'needs_kit')
        self.assertTrue(any('ability str' in p for p in result['problems']))
        self.assertIsNone(result['sheet']['abilities']['str'])  # left blank, not guessed
        self.assertIn('Ask the player', result['next_step'])
        self.assertTrue(result['player_confirms'])


class WhenToImport(Intake):
    """No timing gate: the player manages their own sheet (Brendon, 2026-10-26)."""

    def started(self, room=None):
        self.db = self.dir / 'kit.sqlite'
        code, out = cli('import-sheet', '--pdf', str(self.pdf()), '--out', str(self.dir / 't.json'))
        self.assertEqual(code, 0)
        kit_agent.start_session(str(self.db), str(self.dir / 't.json'), room=room or str(ROOMS / 'watchroom.json'))

    def reimport(self, fields=None, hex_fields=None, **changes):
        fields = dict(fields or sheet_pdf.FIELDS, **changes)
        return cli('import-sheet', '--db', str(self.db), '--pdf',
                   str(self.pdf('again.pdf', fields=fields, hex_fields=hex_fields)),
                   '--out', str(self.dir / 'again.json'), '--master-sheet', 'D&D Beyond')

    def gold(self):
        runtime = Runtime(str(self.db))
        try:
            return runtime.load()[1]['player_sheet']['gold_gp']
        finally:
            runtime.close()

    def test_a_sheet_mid_room_loads_and_the_gold_edit_is_noted_not_questioned(self):
        self.started()
        code, out = self.reimport(GP='99')
        self.assertEqual((out['stage'], out['at']), ('sheet_loaded', 'mid_game'))
        self.assertEqual(self.gold(), 109)
        self.assertEqual(out['sheet_changes'], [{'what': 'gold (gp)', 'was': 52, 'now': 109}])
        self.assertIn('do not question', out['next_step'])
        code, again = self.reimport(GP='120')
        self.assertEqual(again['stage'], 'sheet_loaded')  # no once-per-rest limit
        self.assertEqual(self.gold(), 130)

    def test_hp_xp_and_ammo_edits_are_noted(self):
        self.started()
        fields = dict(sheet_pdf.FIELDS, **{'Eq Name3': 'Arrows', 'Eq Qty3': '20', 'Eq Name4': ''})
        self.reimport(fields=fields)
        fields.update({'Eq Qty3': '14', 'MaxHP': '25', 'EXPERIENCE POINTS': '900'})
        code, out = self.reimport(fields=fields)
        whats = {c['what']: (c['was'], c['now']) for c in out['sheet_changes']}
        self.assertEqual(whats, {'HP': (21, 25), 'XP': (None, 900), 'Arrows': (20, 14)})
        self.assertNotIn('proficiency_check', out)

    def test_a_proficiency_with_no_source_is_asked_once_not_ruled(self):
        self.started()
        hexf = dict(sheet_pdf.HEX_FIELDS)
        hexf['ProficienciesLang'] = hexf['ProficienciesLang'].replace('Light Armor', 'Light Armor, Heavy Armor')
        code, out = self.reimport(hex_fields=hexf)
        self.assertEqual(out['stage'], 'sheet_loaded')  # loaded anyway: asking, not ruling
        check = out['proficiency_check']
        self.assertEqual([u['proficiency'] for u in check['unsourced']], ['Heavy Armor'])
        self.assertFalse(check['auto_ruled'])
        self.assertIn('asking, not ruling', check['table_line'])

    def test_a_long_rest_offers_a_sheet_and_a_short_rest_does_not(self):
        self.started()
        code, rest = cli('rest', '--db', str(self.db), '--kind', 'short')
        self.assertNotIn('offer_sheet', rest)
        code, rest = cli('rest', '--db', str(self.db), '--kind', 'long')
        self.assertIn('fresh sheet', rest['offer_sheet'])
        code, out = self.reimport()
        self.assertEqual(out['at'], 'long_rest')

    def test_a_level_up_loads_and_save_records_the_source(self):
        self.started()
        code, out = self.reimport(**{'CLASS  LEVEL': 'Rogue 4', 'MaxHP': '27'})
        self.assertEqual((out['stage'], out['at']), ('sheet_loaded', 'level_up'))
        saved = kit_save.save(str(self.db))
        campaign = json.loads((Path(saved['folder']) / 'campaign.json').read_text(encoding='utf-8'))
        source = campaign['sheet_source']
        self.assertEqual((source['kind'], source['at'], source['named_by_player']), ('pdf', 'level_up', 'D&D Beyond'))
        self.assertTrue(source['imported_at'].endswith('Z'))

    def test_character_sheet_json_mid_game_notes_edits_too(self):
        self.started()
        sheet = json.loads((self.dir / 't.json').read_text(encoding='utf-8'))
        sheet['gold_gp'] = 60
        (self.dir / 'edit.json').write_text(json.dumps(sheet), encoding='utf-8')
        code, out = cli('character', '--db', str(self.db), '--sheet', str(self.dir / 'edit.json'))
        self.assertEqual(out['sheet_changes'], [{'what': 'gold (gp)', 'was': 52, 'now': 60}])

    def test_an_imported_adventure_takes_a_sheet_mid_room_and_saves_cleanly(self):
        from runtime import kit_adventure
        from tests.test_kit_player_save import FERRY
        self.db = self.dir / 'kit.sqlite'
        kit_adventure.import_adventure(self.db, text=FERRY.read_text(encoding='utf-8'))
        kit_adventure.compile_location(self.db, '1')
        cli('import-sheet', '--pdf', str(self.pdf()), '--out', str(self.dir / 't.json'))
        kit_agent.start_session(str(self.db), str(self.dir / 't.json'),
                                room=str(kit_adventure.room_file(self.db, '1')))
        code, out = self.reimport(GP='99')
        self.assertEqual((out['stage'], self.gold()), ('sheet_loaded', 109))
        saved = kit_save.save(str(self.db))
        campaign = json.loads((Path(saved['folder']) / 'campaign.json').read_text(encoding='utf-8'))
        self.assertTrue(campaign['location']['room_id'].startswith('adv-'))
        self.assertEqual(campaign['sheet_source']['kind'], 'pdf')


class Questions(unittest.TestCase):
    def test_new_campaign_asks_journal_then_master_sheet_then_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            greeting = kit_campaign.campaign_entry(str(Path(tmp) / 'kit.sqlite'))
        keys = [q['key'] for q in greeting['new_campaign']['ask']]
        self.assertEqual(keys, ['journal_mode', 'master_sheet', 'sheet_upload'])
        master = greeting['new_campaign']['ask'][1]
        self.assertEqual(master['question'], "What's your master sheet?")
        self.assertEqual(master['options'], ['D&D Beyond', 'Avrae GSheet', 'paper', 'JSON'])


class Portable(unittest.TestCase):
    def test_new_runtime_modules_import_only_the_standard_library(self):
        allowed = set(sys.stdlib_module_names) | {'runtime'}
        for name in ('sheet_intake', 'kit_save', 'kit_resume'):
            tree = ast.parse((ROOT / 'runtime' / f'{name}.py').read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name.split('.')[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    mods = [node.module.split('.')[0]]
                else:
                    continue
                for mod in mods:
                    self.assertIn(mod, allowed, f'{name} imports {mod}')

    def test_import_sheet_from_the_bare_runtime_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with zipfile.ZipFile(runtime_zip(tmp / 'runtime.zip')) as z:
                z.extractall(tmp / 'box')
            pdf = tmp / 'sheet.pdf'
            pdf.write_bytes(sheet_pdf.build())
            done = subprocess.run(['env', '-i', 'python3', '-m', 'runtime.kit_agent', 'import-sheet', '--pdf', str(pdf)],
                                  cwd=tmp / 'box' / 'dnd-solo-main', capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(done.stdout)['stage'], 'sheet_imported')


if __name__ == '__main__':
    unittest.main()
