"""The one bootstrap command any AI host runs first (AGENTS.md): start."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_agent, pc_sheet
from runtime.state_context import InvalidChange, Runtime

ROOT = Path(__file__).resolve().parents[1]


class StartSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'kit.sqlite')

    def tearDown(self):
        self.tmp.cleanup()

    def test_example_sheet_is_a_valid_generic_pc(self):
        sheet = json.loads(kit_agent.EXAMPLE_SHEET.read_text(encoding='utf-8'))
        pc_sheet.check_sheet(sheet)
        self.assertNotEqual(sheet['name'], 'Nik')

    def test_start_initializes_loads_example_sheet_and_stages_opening(self):
        result = kit_agent.start_session(self.db)
        self.assertEqual(result['stage'], 'started')
        self.assertTrue(result['example_sheet'])
        self.assertEqual(result['character']['name'], 'Wren')
        prepared = result['prepared']
        self.assertEqual(prepared['stage'], 'one_pass')
        self.assertIn('instructions', prepared)
        self.assertIn('schema', prepared)
        self.assertIn(prepared['turn_id'], result['next_step'])
        self.assertIn('complete', result['next_step'])
        runtime = Runtime(self.db)
        try:
            self.assertIsNotNone(runtime.pending_kit_turn(prepared['turn_id']))
        finally:
            runtime.close()

    def test_start_loads_a_given_sheet(self):
        sheet = json.loads(kit_agent.EXAMPLE_SHEET.read_text(encoding='utf-8'))
        sheet['name'] = 'Pip'
        path = Path(self.tmp.name) / 'pip.json'
        path.write_text(json.dumps(sheet), encoding='utf-8')
        result = kit_agent.start_session(self.db, str(path))
        self.assertFalse(result['example_sheet'])
        self.assertEqual(result['character']['name'], 'Pip')

    def test_start_refuses_a_database_with_a_game(self):
        kit_agent.start_session(self.db)
        with self.assertRaisesRegex(InvalidChange, 'new --db'):
            kit_agent.start_session(self.db)

    def test_cli_start_prints_the_first_packet(self):
        out = io.StringIO()
        with mock.patch.object(sys, 'argv', ['kit_agent', 'start', '--db', self.db]), \
                contextlib.redirect_stdout(out):
            self.assertEqual(kit_agent.main(), 0)
        printed = json.loads(out.getvalue())
        self.assertEqual(printed['stage'], 'started')
        self.assertIn('turn_id', printed['prepared'])


if __name__ == '__main__':
    unittest.main()
