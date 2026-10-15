"""Player-facing start must not open Area 6c or load Wren."""
import contextlib
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import kit_agent, kit_campaign
from runtime.state_context import PROJECT_ROOT, Runtime

ROOT = PROJECT_ROOT
SIXC = 'tests/fixtures/level_01_area_06c.json'


class CampaignEntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'kit.sqlite')

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_room_does_not_launch_or_create_a_save(self):
        result = kit_agent.start_session(self.db)
        self.assertEqual(result['stage'], 'campaign_entry')
        self.assertFalse(result['committed'])
        self.assertIsNone(result['opened_room'])
        self.assertFalse(result['character_loaded'])
        self.assertEqual(result['executable_starts'], [])
        self.assertEqual(result['blocker']['code'], 'no_executable_campaign_start')
        self.assertEqual(result['campaign']['id'], 'dotmm')
        self.assertFalse(Path(self.db).exists())
        self.assertNotIn('6c', result['table_line'].casefold())
        self.assertNotIn('wren', result['table_line'].casefold())
        self.assertIn('Yawning Portal', result['table_line'])
        paths = [item['path'] for item in result['do_not_start']]
        self.assertIn(SIXC, paths)
        self.assertIn('rooms/level_01_area_17a.json', paths)

    def test_a_sheet_alone_still_does_not_open_a_room(self):
        result = kit_agent.start_session(self.db, str(kit_agent.EXAMPLE_SHEET))
        self.assertEqual(result['stage'], 'campaign_entry')
        self.assertFalse(result['sheet_loaded'])
        self.assertFalse(Path(self.db).exists())

    def test_explicit_regression_room_still_stages_the_fixture(self):
        result = kit_agent.start_session(self.db, room=kit_agent.DEFAULT_ROOM)
        self.assertEqual(result['stage'], 'started')
        self.assertEqual(result['room_id'], 'dotmm-level-01-area-06c-testbed-v1')
        self.assertTrue(result['example_sheet'])
        self.assertEqual(result['character']['name'], 'Wren')
        runtime = Runtime(self.db)
        try:
            self.assertEqual(runtime.source()['id'], 'dotmm-level-01-area-06c-testbed-v1')
        finally:
            runtime.close()

    def test_a_save_resumes_instead_of_opening_another_room(self):
        kit_agent.start_session(self.db, room=kit_agent.DEFAULT_ROOM)
        again = kit_agent.start_session(self.db)
        self.assertEqual(again['stage'], 'resume')
        self.assertEqual(again['room_id'], 'dotmm-level-01-area-06c-testbed-v1')
        self.assertIn('pending_turn', again)
        self.assertFalse(again['committed'])

    def test_cli_without_a_room_prints_campaign_entry(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = _argv(['kit_agent', 'start', '--db', self.db])
        self.assertEqual(code, 0)
        printed = json.loads(out.getvalue())
        self.assertEqual(printed['stage'], 'campaign_entry')
        self.assertFalse(Path(self.db).exists())

    def test_cli_refuses_the_fixture_without_regression(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = _argv(['kit_agent', 'start', '--db', self.db, '--room', SIXC])
        self.assertEqual(code, 2)
        refused = json.loads(err.getvalue())
        self.assertEqual(refused['error'], 'not_a_campaign_room')
        self.assertEqual(refused['why'], 'regression_fixture')
        self.assertFalse(Path(self.db).exists())
        self.assertNotIn('6c', refused['table_line'].casefold())

    def test_cli_regression_flag_mounts_the_fixture(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = _argv(['kit_agent', 'start', '--regression', '--db', self.db, '--room', SIXC])
        self.assertEqual(code, 0)
        printed = json.loads(out.getvalue())
        self.assertEqual(printed['stage'], 'started')
        self.assertEqual(printed['room_id'], 'dotmm-level-01-area-06c-testbed-v1')

    def test_cli_refuses_the_stub(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = _argv(['kit_agent', 'start', '--db', self.db, '--room', 'rooms/level_01_area_17a.json'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(err.getvalue())['why'], 'stub')
        self.assertFalse(Path(self.db).exists())

    def test_init_without_a_room_does_not_create_a_save(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = _argv(['kit_agent', 'init', '--db', self.db])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())['stage'], 'campaign_entry')
        self.assertFalse(Path(self.db).exists())

    def test_one_real_room_is_offered_and_not_auto_opened(self):
        folder = Path(self.tmp.name) / 'rooms'
        folder.mkdir()
        body = {
            'id': 'dotmm-level-01-area-01-test',
            'starting_area': 'area_1',
            'areas': {'area_1': {'name': 'The entrance'}},
            'exits': {},
            'facts': {},
            'actors': {},
        }
        (folder / 'area_1.json').write_text(json.dumps(body), encoding='utf-8')
        report = kit_campaign.campaign_entry(self.db, rooms_dir=folder)
        self.assertEqual(report['stage'], 'campaign_entry')
        self.assertIsNone(report['blocker'])
        self.assertEqual(len(report['executable_starts']), 1)
        self.assertEqual(report['executable_starts'][0]['room_id'], 'dotmm-level-01-area-01-test')
        self.assertEqual(report['executable_starts'][0]['starting_area'], 'area_1')
        self.assertNotIn('6c', report['table_line'].casefold())
        self.assertFalse(Path(self.db).exists())

    def test_subprocess_start_matches_the_host_command(self):
        proc = subprocess.run(
            [sys.executable, '-m', 'runtime.kit_agent', 'start', '--db', self.db],
            cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result['stage'], 'campaign_entry')
        self.assertEqual(result['executable_starts'], [])
        self.assertFalse(Path(self.db).exists())


def _argv(argv):
    with patch.object(sys, 'argv', argv):
        return kit_agent.main()


class _SqliteLeftBehind(unittest.TestCase):
    def test_saved_game_reader_does_not_treat_an_empty_file_as_a_game(self):
        folder = tempfile.TemporaryDirectory()
        try:
            path = Path(folder.name) / 'empty.sqlite'
            path.write_bytes(b'')
            self.assertIsNone(kit_campaign.saved_game(path))
            path.write_bytes(b'not a database')
            self.assertIsNone(kit_campaign.saved_game(path))
            real = Path(folder.name) / 'bare.sqlite'
            con = sqlite3.connect(real)
            con.execute('CREATE TABLE source (id INTEGER, body TEXT)')
            con.commit()
            con.close()
            self.assertIsNone(kit_campaign.saved_game(real))
        finally:
            folder.cleanup()


if __name__ == '__main__':
    unittest.main()
