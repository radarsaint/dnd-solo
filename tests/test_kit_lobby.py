"""The lobby: what plain `start` does on every host before any room is mounted.

No room file and no book text are needed. Kit greets and asks how the player wants to use her
this session (play, design or debrief talk, a test run), and lists only what really exists:
attached rooms packs and their rooms, saved games, and character sheets. Nothing falls back
to Area 6c. Packs here are synthetic (tests/test_kit_room_pack.build_pack).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_campaign
from runtime.state_context import PROJECT_ROOT

from test_kit_room_pack import NIK, _cli, build_pack, zip_pack

SIXC = 'tests/fixtures/level_01_area_06c.json'


class LobbyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = str(self.dir / 'kit.sqlite')

    def tearDown(self):
        self.tmp.cleanup()

    def lobby(self, cwd=None):
        code, out = _cli(['start', '--db', self.db], cwd=cwd or self.dir)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['stage'], 'lobby')
        return out

    def test_bare_start_is_the_lobby_and_mounts_nothing(self):
        out = self.lobby()
        self.assertFalse(out['committed'])
        self.assertIsNone(out['opened_room'])
        self.assertFalse(Path(self.db).exists())
        self.assertNotIn('prepared', out)
        self.assertEqual({c['choice'] for c in out['choices']}, {'play', 'talk', 'test_run'})

    def test_kit_asks_how_the_player_wants_to_use_her(self):
        line = self.lobby()['table_line']
        self.assertTrue(line.startswith("I'm Kit."))
        self.assertIn('this session', line)
        for word in ('play', 'design', 'debrief', 'test run'):
            self.assertIn(word, line)
        self.assertNotIn('mad mage', line.casefold())
        self.assertNotIn('wren', line.casefold())

    def test_lists_only_what_exists_with_nothing_attached(self):
        out = self.lobby()
        self.assertEqual(out['available']['packs'], [])
        self.assertEqual(out['available']['saved_games'], [])
        self.assertNotIn('pack', out['table_line'])
        self.assertNotIn('saved game', out['table_line'])
        sheets = {s['path']: s for s in out['available']['character_sheets']}
        self.assertIn(NIK, sheets)
        self.assertEqual(sheets[NIK]['name'], 'Nik')
        self.assertTrue(sheets[str(kit_campaign.EXAMPLE_SHEET)]['example_only_if_asked'])
        for sheet in sheets:
            self.assertTrue((PROJECT_ROOT / sheet).is_file() or Path(sheet).is_file(), sheet)

    def test_lists_an_attached_pack_and_its_rooms(self):
        zip_pack(build_pack(self.dir / 'src'), self.dir / 'kit-rooms-test.zip')
        out = self.lobby()
        packs = out['available']['packs']
        self.assertEqual(len(packs), 1)
        self.assertEqual(packs[0]['pack'], 'kit-rooms')
        self.assertEqual(packs[0]['path'], str(self.dir / 'kit-rooms-test.zip'))
        self.assertEqual(packs[0]['first_room'], 'synthetic-pack-watchroom')
        self.assertEqual(packs[0]['rooms'], ['synthetic-pack-watchroom', 'synthetic-pack-kiln'])
        self.assertNotIn('summary', json.dumps(packs))
        self.assertIn('rooms pack', out['table_line'])
        play = next(c for c in out['choices'] if c['choice'] == 'play')
        self.assertIn('--room', play['command'])
        self.assertIn('--sheet', play['command'])

    def test_lists_a_saved_game_and_offers_resume(self):
        save = self.dir / 'old' / 'kit.sqlite'
        save.parent.mkdir()
        code, out = _cli(['start', '--db', str(save), '--pack', str(build_pack(self.dir / 'p')),
                          '--sheet', NIK], cwd=self.dir / 'old')
        self.assertEqual(code, 0, out)
        shutil.copy(save, self.dir / 'kit-save.sqlite')
        out = self.lobby()
        saves = out['available']['saved_games']
        self.assertEqual([s['path'] for s in saves], [str(self.dir / 'kit-save.sqlite')])
        self.assertEqual(saves[0]['character'], 'Nik')
        self.assertIn('resume', {c['choice'] for c in out['choices']})
        self.assertIn('saved game', out['table_line'])

    def test_a_db_that_already_holds_a_game_is_still_a_resume(self):
        code, _ = _cli(['start', '--db', self.db, '--pack', str(build_pack(self.dir / 'p')), '--sheet', NIK],
                       cwd=self.dir)
        self.assertEqual(code, 0)
        code, out = _cli(['start', '--db', self.db], cwd=self.dir)
        self.assertEqual(out['stage'], 'resume')

    def test_picking_a_pack_room_from_the_lobby_mounts_it(self):
        build_pack(self.dir)
        out = self.lobby()
        room = out['available']['packs'][0]['rooms'][1]
        code, started = _cli(['start', '--db', self.db, '--room', room, '--sheet', NIK], cwd=self.dir)
        self.assertEqual(code, 0, started)
        self.assertEqual(started['stage'], 'started')
        self.assertEqual(started['room_id'], 'synthetic-pack-kiln')

    def test_test_runs_are_synthetic_and_never_6c(self):
        out = self.lobby()
        paths = [r['path'] for r in out['available']['test_rooms']]
        self.assertTrue(paths)
        self.assertNotIn(SIXC, paths)
        self.assertTrue(all(p.startswith('tests/fixtures/rooms/') for p in paths), paths)
        self.assertNotIn('06c', json.dumps(out['choices']))

    def test_python_start_without_a_room_never_opens_6c(self):
        result = kit_agent.start_session(self.db)
        self.assertEqual(result['stage'], 'lobby')
        self.assertFalse(Path(self.db).exists())


if __name__ == '__main__':
    unittest.main()
