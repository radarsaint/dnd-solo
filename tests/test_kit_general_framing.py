"""Kit is a general DM: a non-Mad-Mage adventure's packets never mention Mad Mage, Halaster,
area 6c or Undermountain, personality core included: Brendon's Halaster and Mad Mage persona
lines live in docs/personality/dm-personality-mad-mage.md and load only for dotmm rooms, verbatim.
Corpus: tests/fixtures/adventures/lantern_ferry.txt (original synthetic) and the area 6c fixture."""
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


MOVED = (  # verbatim from the core; only Mad Mage rooms get them
    "Keep the named campaign's through-line alive without forcing it; Halaster belongs to Mad Mage, "
    "not every conversation.",
    '- She does not make every floor about Halaster.',
    'Dungeon of the Mad Mage is a campaign she can be asked to run. It is not her only job, and she does '
    'not open it unless they asked for it.',
    "Halaster's presence growing through legitimate contact with the campaign.",
)


class NonMadMageImport(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'
        kit_adventure.import_adventure(self.db, text=CORPUS.read_text(encoding='utf-8'))
        kit_adventure.compile_location(self.db, '1')

    def assert_clean(self, text):
        found = MAD_MAGE.search(json.dumps(json.loads(text), ensure_ascii=False))
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
            self.assertIn('personality_core', started.stdout)   # the core was checked, not skipped
        self.assertIsNone(MAD_MAGE.search(run('persona').stdout))

    def test_the_source_line_names_the_adventure(self):
        line = source_constraint({'id': 'adv-1', 'source_ref': 'Chapter 1: The Lantern Ferry / 1. Ferry Landing'})
        self.assertIn('Chapter 1: The Lantern Ferry', line)
        self.assertIn('cited adventure source', line)
        self.assertNotIn('Mad Mage', source_constraint({'id': 'watchroom'}))
        self.assertIn('Mad Mage', source_constraint({'id': 'dotmm-level-01-area-06c-testbed-v1',
                                                     'source_ref': 'DotMM p.1'}))



class MadMageRoomKeepsTheLines(unittest.TestCase):
    def test_a_dotmm_room_gets_every_moved_line_verbatim(self):
        from runtime.kit_agent import start_session
        from runtime.state_context import Runtime, personality_core_text
        room = ROOT / 'tests/fixtures/level_01_area_06c.json'
        with tempfile.TemporaryDirectory() as folder, warnings.catch_warnings():
            warnings.simplefilter('ignore')
            db = Path(folder) / 'k.sqlite'
            started = start_session(db, NIK, room=room)
            runtime = Runtime(db)
            try:
                self.assertTrue(runtime.source()['id'].startswith('dotmm'))
                core = runtime.context()['personality_core']
            finally:
                runtime.close()
            sent = json.dumps(started, ensure_ascii=False)   # the opening packet as sent
            for line in MOVED:
                self.assertIn(line, core)
                self.assertIn(json.dumps(line, ensure_ascii=False)[1:-1], sent)
            generic = personality_core_text()
            for line in MOVED:
                self.assertNotIn(line, generic)
            self.assertTrue(core.startswith(generic.split('\n\n# Voice files')[0].rstrip('\n')))


if __name__ == '__main__':
    unittest.main()
