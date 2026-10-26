"""Lobby (play or build, module + character, solo or shared table) and Goldscale pricing parity."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_appraise, kit_campaign, kit_chargen
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
        self.assertEqual(out['table_line'], kit_campaign.GREETING)
        self.assertIn('rolling dice', out['table_line'])
        self.assertIn('building', out['table_line'])
        self.assertNotIn('Mad Mage', out['table_line'])
        self.assertIsNone(out['opened_room'])

    def test_build_offers_design_and_goldscale(self):
        out = self.entry(intent='build')
        self.assertEqual(out['stage'], 'build')
        self.assertIn('kit_appraise', out['tools']['price_item'])
        self.assertIn('kit_chargen', out['tools']['character_building'])
        self.assertIn('core rules', out['table_line'])
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

    def test_attached_modules_ride_along_on_every_retry(self):
        self._module()
        out = self.entry(intent='play', rooms_dir=self.modules)
        self.assertIn(f'--modules {self.modules}', out['next_step'])
        out = self.entry(intent='play', rooms_dir=self.modules, sheet_path=str(SHEET))
        self.assertEqual(out['stage'], 'ask_table')
        self.assertIn(f'--modules {self.modules}', out['next_step'])
        self.assertEqual(out['modules'], self.modules)
        out = self.entry(intent='play', rooms_dir=self.modules, sheet_path=str(SHEET), table='solo')
        self.assertEqual(out['stage'], 'ready')
        self.assertEqual(len(out['modules_available']), 1)

    def test_cli_retry_with_modules_keeps_the_module(self):
        self._module()
        base = [sys.executable, '-m', 'runtime.kit_agent', 'start', '--db', self.db, '--intent', 'play',
                '--sheet', str(SHEET), '--modules', self.modules]
        first = json.loads(subprocess.run(base, cwd=ROOT, capture_output=True, text=True).stdout)
        self.assertIn('--modules', first['next_step'])
        second = json.loads(subprocess.run(base + ['--table', 'solo'], cwd=ROOT, capture_output=True,
                                           text=True).stdout)
        self.assertEqual(second['stage'], 'ready')
        self.assertEqual(len(second['modules_available']), 1)


class LineTests(unittest.TestCase):
    def test_lines_are_short_and_in_voice_not_system_talk(self):
        lines = [kit_campaign.GREETING, kit_campaign.TABLE_LINE, kit_campaign.SOLO_LINE, kit_campaign.SHARED_LINE,
                 kit_campaign.BUILD_LINE, *kit_campaign.PLAY_NEEDS_LINES.values()]
        for line in lines:
            with self.subTest(line=line):
                self.assertLess(len(line), 170)
                for banned in ('Goldscale', 'formula', "won't make", 'guesswork', 'module and your character',
                               'arena', 'DM assistant', "DM's assistant"):
                    self.assertNotIn(banned, line)


class NeverGuessChargenTests(unittest.TestCase):
    def test_non_srd_options_ask_for_rules_or_sheet(self):
        for text in ('help me build a Twilight cleric', 'build a battle master fighter',
                     'create an Oath of Vengeance paladin', 'make a Hexblade warlock',
                     'I want to make a character with the Eldritch Adept feat',
                     "which feat should my rogue take from Tasha's",
                     'build an Astral Elf from Monsters of the Multiverse',
                     'make a level 5 wizard using the 2024 rules'):
            with self.subTest(text=text):
                out = kit_chargen.chargen(text)
                self.assertEqual(out['stage'], 'chargen')
                self.assertFalse(out['srd_only'])
                self.assertTrue(out['never_guess'])
                self.assertIn("won't guess", out['table_line'])
                self.assertIn('paste me the exact rules', out['table_line'].lower())
                self.assertIn('sheet', out['table_line'])

    def test_srd_options_are_fine(self):
        for text in ('build a fighter champion', 'make a level 3 wizard, school of evocation',
                     "let's build a hill dwarf cleric with the life domain", 'build a 5th level human fighter'):
            with self.subTest(text=text):
                out = kit_chargen.chargen(text)
                self.assertTrue(out['srd_only'], out)
                self.assertTrue(out['never_guess'])

    def test_named_option_appears_in_line(self):
        self.assertIn('Twilight Cleric', kit_chargen.chargen('help me build a Twilight cleric')['table_line'])

    def test_not_chargen(self):
        for text in ("what's in this room", 'I attack the goblin', 'price a +1 sword'):
            self.assertIsNone(kit_chargen.chargen(text))

    def test_rule_is_in_persona_and_agents(self):
        core = (ROOT / 'docs/personality/dm-personality-core.md').read_text(encoding='utf-8')
        agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('never guesses at character generation', core)
        self.assertIn('Never guess at character generation', agents)


if __name__ == '__main__':
    unittest.main()


class PlaytestFixTests(unittest.TestCase):
    """Bugs found in the PR 145 playtest (2026-10-25)."""

    def test_chargen_catches_option_asks_without_build_verb(self):
        cases = {
            "I want to play a Gloom Stalker ranger from Xanathar's": 'gloom stalker',
            'can I take the Sharpshooter feat': 'sharpshooter',
            'can I take Sharpshooter': 'sharpshooter',
            'can my wizard learn Silvery Barbs': 'silvery barbs',
            'can I learn the Frost Lance spell': 'frost lance',
            "I'd like to play an Aasimar paladin": 'aasimar',
            'I want to play a Moonblade species': 'moonblade',
            'should I pick Fey Touched at level 4': 'fey touched',
        }
        for text, name in cases.items():
            with self.subTest(text=text):
                out = kit_chargen.chargen(text)
                self.assertIsNotNone(out, text)
                self.assertFalse(out['srd_only'], out)
                self.assertTrue(any(name in u for u in out['unknown_options']), out)
                self.assertIn("won't guess", out['table_line'])

    def test_chargen_cli_reports_chargen(self):
        run = subprocess.run([sys.executable, '-m', 'runtime.kit_chargen', 'can I take the Sharpshooter feat'],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(json.loads(run.stdout)['stage'], 'chargen')

    def test_chargen_srd_asks_and_table_talk_stay_put(self):
        for text in ('can I take the grappler feat', 'can I play a hill dwarf cleric'):
            self.assertTrue(kit_chargen.chargen(text)['srd_only'], text)
        for text in ('I attack the goblin', 'can I take the sword', 'is the goblin dead',
                     'can I use my action to hide', 'I want to play'):
            self.assertIsNone(kit_chargen.chargen(text), text)

    def test_description_answer_keeps_the_item_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, 'pending.json')
            self.assertIn('item description', kit_appraise.appraise('potion of healing', state))
            self.assertTrue(os.path.exists(state))
            second = kit_appraise.answer('common potion', state)
            self.assertIn('Potion of Healing', second)
            self.assertTrue(os.path.exists(state), 'a still-missing item must stay pending')
            third = kit_appraise.answer('2d4+2 healing', state)
            self.assertIn('**70 gp**', third)
            self.assertFalse(os.path.exists(state))

    def test_two_clarifications_move_forward_not_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, 'pending.json')
            kit_appraise.appraise('ring', state)
            kit_appraise.answer('rare', state)  # description: adds rarity, then asks for impact
            first_q = json.loads(Path(state).read_text())['question_kind']
            nxt = kit_appraise.answer('4' if first_q == 'item_type' else '2', state)
            if 'Final Price' not in nxt:
                self.assertNotEqual(json.loads(Path(state).read_text())['question_kind'], first_q)
                nxt = kit_appraise.answer('2', state)
            self.assertIn('**900 gp**', nxt)

    def test_closed_answers_accumulate(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, 'pending.json')
            Path(state).write_text(json.dumps({'raw': '?gs buy amulet', 'question_kind': 'rarity',
                                               'created_at': 10**12, 'answers': []}))
            r1 = kit_appraise.answer('3', state, now=10**12)  # rare
            self.assertNotIn('Final Price', r1)
            saved = json.loads(Path(state).read_text())
            self.assertNotEqual(saved['question_kind'], 'rarity')
            self.assertEqual(saved['answers'][0], ['rarity', '3'])

    def test_cli_answer_reads_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, 'p.json')
            run = lambda *a: subprocess.run([sys.executable, '-m', 'runtime.kit_appraise', '--state', state, *a],
                                            cwd=ROOT, capture_output=True, text=True).stdout
            run('cloak uncommon')
            self.assertIn('Final Price', run('--answer', '2'))
            self.assertIn('no pending appraisal', run('--answer', '2'))

    def test_script_form_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run([sys.executable, str(ROOT / 'runtime/kit_agent.py'), 'start', '--db',
                                  os.path.join(tmp, 'k.db')], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['stage'], 'greeting')
