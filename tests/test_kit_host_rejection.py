"""A command that is missing a field tells the host which field, as JSON, and exits 2."""
import json
import subprocess
import sys
import unittest

from runtime.state_context import PROJECT_ROOT

ROOT = PROJECT_ROOT


def _run(*args):
    return subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *args],
                          cwd=ROOT, capture_output=True, text=True, check=False)


class HostRejectionTests(unittest.TestCase):
    def test_prepare_without_an_action_names_both_fields(self):
        proc = _run('prepare', '--one-pass', '--db', '/tmp/does-not-need-to-exist.sqlite')
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, '')
        self.assertNotIn('usage:', proc.stderr)
        body = json.loads(proc.stderr)
        self.assertEqual(body['stage'], 'rejected')
        self.assertFalse(body['committed'])
        self.assertIn('--action', body['message'])
        self.assertIn('--action-file', body['message'])
        self.assertEqual(body['missing'], ['action', 'action-file'])

    def test_complete_names_only_the_flags_that_are_absent(self):
        proc = _run('complete', '--db', '/tmp/does-not-need-to-exist.sqlite', '--turn-id', 't')
        body = json.loads(proc.stderr)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(body['missing'], ['input-file'])
        self.assertIn('--input-file', body['message'])
        self.assertIn('--turn-id', body['message'])

    def test_finish_names_both_when_both_are_absent(self):
        proc = _run('finish', '--db', '/tmp/does-not-need-to-exist.sqlite')
        body = json.loads(proc.stderr)
        self.assertEqual(body['missing'], ['turn-id', 'input-file'])
        self.assertIn('finish requires', body['message'])

    def test_character_names_the_sheet_or_the_name(self):
        proc = _run('character', '--db', '/tmp/does-not-need-to-exist.sqlite')
        body = json.loads(proc.stderr)
        self.assertEqual(body['missing'], ['sheet', 'name', 'ancestry'])
        self.assertIn('--sheet', body['message'])
        self.assertIn('--name', body['message'])
        self.assertIn('--ancestry', body['message'])


if __name__ == '__main__':
    unittest.main()
