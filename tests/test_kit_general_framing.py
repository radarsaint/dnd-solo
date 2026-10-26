"""Kit is a general DM: a non-Mad-Mage adventure's packets never mention Mad Mage, Halaster,
area 6c or Undermountain. Corpus: tests/fixtures/adventures/lantern_ferry.txt (original
synthetic) and the watchroom fixture room. The personality core (Brendon's persona files) is
checked separately and is out of scope here. The area 6c fixture keeps its Mad Mage line."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure  # noqa: E402
from runtime.state_context import source_constraint  # noqa: E402

CORPUS = ROOT / 'tests/fixtures/adventures/lantern_ferry.txt'
NIK = ROOT / 'tests/fixtures/characters/nik.json'
MAD_MAGE = re.compile(r'mad mage|halaster|undermountain|yawning portal|dotmm|\b(?:area )?6c\b', re.I)


def run(*args):
    return subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *args], cwd=ROOT,
                          capture_output=True, text=True)


def scrub_persona(node):
    """The packet without the personality core (persona files; not room framing)."""
    if isinstance(node, dict):
        return {k: scrub_persona(v) for k, v in node.items() if k != 'personality_core'}
    if isinstance(node, list):
        return [scrub_persona(v) for v in node]
    return node


class NonMadMageImport(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'
        kit_adventure.import_adventure(self.db, text=CORPUS.read_text(encoding='utf-8'))
        kit_adventure.compile_location(self.db, '1')

    def assert_clean(self, text):
        found = MAD_MAGE.search(json.dumps(scrub_persona(json.loads(text)), ensure_ascii=False))
        self.assertIsNone(found, found and found.group(0))

    def test_opening_and_later_packets_never_mention_mad_mage(self):
        room = str(kit_adventure.room_file(self.db, '1'))
        for extra in ([], ['--full']):
            db = str(self.db) if not extra else str(self.db) + '.b'
            if extra:
                kit_adventure.import_adventure(db, text=CORPUS.read_text(encoding='utf-8'))
                kit_adventure.compile_location(db, '1')
                room = str(kit_adventure.room_file(db, '1'))
            started = run('start', '--db', db, '--room', room, '--sheet', str(NIK), *extra)
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assert_clean(started.stdout)
            turn = json.loads(started.stdout)['prepared']['turn_id']
            self.assertEqual(run('abandon', '--db', db, '--turn-id', turn).returncode, 0)
            later = run('prepare', '--one-pass', '--db', db, '--action', 'I look around the landing.', *extra)
            self.assertEqual(later.returncode, 0, later.stderr)
            self.assert_clean(later.stdout)
            self.assert_clean(run('status', '--db', db).stdout)

    def test_the_source_line_names_the_adventure(self):
        line = source_constraint({'id': 'adv-1', 'source_ref': 'Chapter 1: The Lantern Ferry / 1. Ferry Landing'})
        self.assertIn('Chapter 1: The Lantern Ferry', line)
        self.assertIn('cited adventure source', line)
        self.assertNotIn('Mad Mage', source_constraint({'id': 'watchroom'}))
        self.assertIn('Mad Mage', source_constraint({'id': 'dotmm-level-01-area-06c-testbed-v1',
                                                     'source_ref': 'DotMM p.1'}))


if __name__ == '__main__':
    unittest.main()
