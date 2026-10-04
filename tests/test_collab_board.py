"""The live collaboration board is open work. The dated archive is the old board, verbatim."""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / 'docs/collab/board-archive'
PRE_SPLIT = (
    '2026-09-30.md',
    '2026-10-01.md',
    '2026-10-02.md',
    '2026-10-03.md',
)
# sha256 of docs/collab/BOARD.md on main immediately before the split.
PRE_SPLIT_SHA256 = '7a8cb92af8032e73f0a8ed8bdaa56577f95983c0b3354c2e91c5b495e3b71a96'


class CollabBoardTests(unittest.TestCase):
    def test_pre_split_archive_is_the_old_board_verbatim(self):
        blob = b''.join((ARCHIVE / name).read_bytes() for name in PRE_SPLIT)
        self.assertEqual(hashlib.sha256(blob).hexdigest(), PRE_SPLIT_SHA256)
        self.assertEqual(blob.count(b'\n'), 826)
        self.assertTrue(blob.startswith(b'# Kit collaboration board\n'))
        self.assertIn(b'## 2026-09-30 PT', blob)
        self.assertIn(b'## 2026-10-03 PT', blob)
        self.assertTrue(blob.endswith(b'\n'))

    def test_live_board_points_at_the_archive_and_keeps_settled_rules(self):
        text = (ROOT / 'docs/collab/BOARD.md').read_text(encoding='utf-8')
        for name in PRE_SPLIT:
            self.assertIn(f'board-archive/{name}', text)
        self.assertIn(PRE_SPLIT_SHA256, text)
        self.assertIn('## Settled rules', text)
        self.assertIn('kit_claims.default_dc', text)
        self.assertNotIn('## 2026-09-30 PT', text)
        self.assertIn('board-archive/YYYY-MM-DD.md', text)

    def test_protocol_sends_agents_to_the_live_board(self):
        protocol = (ROOT / 'docs/collab/README.md').read_text(encoding='utf-8')
        self.assertIn('open work only', protocol)
        self.assertIn('board-archive/', protocol)
        self.assertIn('Do not read `board-archive/` by default', protocol)
        note = (ROOT / 'docs/collab/README_FOR_GPT.md').read_text(encoding='utf-8')
        self.assertIn('not for play', note.lower())
        self.assertIn('board-archive/', note)
        self.assertIn('live `BOARD.md`', note)
