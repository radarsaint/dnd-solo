"""Lobby (play or build, module + character, solo or shared table) and Goldscale pricing parity."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_appraise, kit_campaign
from runtime.goldscale.clarification import PendingAppraisals, continue_appraisal, start_appraisal

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / 'tests/fixtures/goldscale/golden_replies.json').read_text(encoding='utf-8'))
SHEET = ROOT / 'tests/fixtures/characters/example_pc.json'


class GoldscaleParityTests(unittest.TestCase):
    """Numbers and replies match the Goldscale bot's own output (tests/fixtures/goldscale)."""

    def test_prices_match_goldscale(self):
        cases = {
            '+1 sword uncommon weapon': (24, 50, 1200, 1200, None),
            'wand of fireballs rare wand 8d6 aoe 7 charges': (784, 200, 157000, 157000, None),
            'potion of healing common potion 2d4+2 healing': (7, 10, 70, 70, None),
            'cloak of protection uncommon cloak +1': (24, 60, 1400, 1400, None),
            'sell qty 2 +1 sword uncommon weapon': (24, 50, 1200, 600, 1200),
            'boots of striding very rare boots broad': (8, 400, 3200, 3200, None),
            'sell +2 shield rare shield 25%': (48, 120, 5800, 1400, None),
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                got = kit_appraise.price(text)
                self.assertEqual((got['impact'], got['gpi'], got['list_price'], got['final_price'],
                                  got['transaction_total']), want)

    def test_replies_match_goldscale_verbatim(self):
        for case in GOLDEN['cases']:
            with self.subTest(inputs=case['inputs']):
                store, key = PendingAppraisals(), (None, 0, 0)
                got = [start_appraisal(case['inputs'][0], key, store, now=0)]
                got += [continue_appraisal(a, key, store, now=1) for a in case['inputs'][1:]]
                self.assertEqual(got, case['replies'])

    def test_clarification_survives_separate_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, 'pending.json')
            first = kit_appraise.appraise('cloak uncommon', state)
            self.assertIn('How useful', first)
            self.assertTrue(os.path.exists(state))
            second = kit_appraise.answer('2', state)
            self.assertIn('Final Price', second)
            self.assertFalse(os.path.exists(state))

    def test_stdlib_only(self):
        for path in (ROOT / 'runtime/goldscale').glob('*.py'):
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('import discord', text)
            self.assertNotIn('dotenv', text)


class LobbyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'kit.sqlite')
        self.modules = os.path.join(self.tmp, 'modules')
        os.mkdir(self.modules)
        self.empty = os.path.join(self.tmp, 'none')
        os.mkdir(self.empty)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _module(self):
        # A playable copy of the fixture room, outside the repo (the fixture itself is never offered).
        room = json.loads((ROOT / 'tests/fixtures/level_01_area_06c.json').read_text(encoding='utf-8'))
        room.pop('fixture_only', None)
        path = os.path.join(self.modules, 'test_module.json')
        Path(path).write_text(json.dumps(room), encoding='utf-8')
        return path

    def entry(self, **kw):
        kw.setdefault('rooms_dir', self.empty)
        return kit_campaign.campaign_entry(self.db, **kw)

    def test_greeting_asks_play_or_build_and_assumes_nothing(self):
        out = self.entry()
        self.assertEqual(out['stage'], 'greeting')
        self.assertEqual(out['choices'], ['play', 'build'])
        self.assertIn('playing', out['table_line'])
        self.assertIn('building', out['table_line'])
        self.assertNotIn('Mad Mage', out['table_line'])
        self.assertIsNone(out['opened_room'])

    def test_build_offers_design_and_goldscale(self):
        out = self.entry(intent='build')
        self.assertEqual(out['stage'], 'build')
        self.assertIn('kit_appraise', out['tools']['price_item'])
        self.assertIsNone(out['opened_room'])

    def test_play_without_module_or_sheet_asks_for_both(self):
        out = self.entry(intent='play')
        self.assertEqual(out['stage'], 'need_module')
        self.assertEqual(out['missing'], ['a module', 'your character'])
        self.assertEqual(out['modules_available'], [])

    def test_play_lists_only_real_modules_never_stubs_or_fixture(self):
        out = self.entry(intent='play', rooms_dir=ROOT / 'rooms')
        self.assertEqual(out['modules_available'], [])
        paths = [m['path'] for m in out['modules_available']]
        self.assertNotIn(kit_campaign.REGRESSION_ROOM, paths)

    def test_play_with_module_but_no_sheet_asks_for_character(self):
        self._module()
        out = self.entry(intent='play', rooms_dir=self.modules)
        self.assertEqual(out['stage'], 'need_character')
        self.assertEqual(out['missing'], ['your character'])
        self.assertEqual(len(out['modules_available']), 1)

    def test_missing_sheet_file_is_not_a_character(self):
        self._module()
        out = self.entry(intent='play', rooms_dir=self.modules, sheet_path=os.path.join(self.tmp, 'nope.json'))
        self.assertEqual(out['stage'], 'need_character')

    def test_play_ready_asks_solo_or_shared_then_records_it(self):
        self._module()
        out = self.entry(intent='play', rooms_dir=self.modules, sheet_path=str(SHEET))
        self.assertEqual(out['stage'], 'ask_table')
        self.assertEqual(out['table_modes'], ['solo', 'shared'])
        self.assertIsNone(kit_campaign.table_mode(self.db))
        out = self.entry(intent='play', rooms_dir=self.modules, sheet_path=str(SHEET), table='shared')
        self.assertEqual(out['stage'], 'ready')
        self.assertIn('basic', out['table_note'])
        self.assertEqual(kit_campaign.table_mode(self.db), 'shared')
        self.entry(intent='play', rooms_dir=self.modules, sheet_path=str(SHEET), table='solo')
        self.assertEqual(kit_campaign.table_mode(self.db), 'solo')
        self.assertIsNone(kit_campaign.saved_game(self.db))  # no game was started

    def test_cli_start_with_room_records_table_mode(self):
        module = self._module()
        run = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'start', '--db', self.db,
                              '--room', module, '--sheet', str(SHEET), '--table', 'shared'],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['table_mode'], 'shared')
        self.assertEqual(kit_campaign.table_mode(self.db), 'shared')
        self.assertEqual(kit_campaign.campaign_entry(self.db)['stage'], 'resume')


if __name__ == '__main__':
    unittest.main()
