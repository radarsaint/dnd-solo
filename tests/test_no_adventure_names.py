"""Runtime and ingest code must not name a published adventure's places.

The list lives here, in the test, so the scan can see the names. The code under
test must not.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Published-adventure names. A hit in runtime means the ingest was fitted to one book.
NAMES = (
    'phandalin',
    'phan dalln',
    'phandalln',
    'wave echo',
    'waveechocave',
    'goblin arrows',
    'goblinarrows',
    'cragmaw',
    'redbrand',
    'thundertree',
    'tresendar',
    'gundren',
    'sildar',
    'neverwinter',
    'triboar',
    'venomfang',
    'glasstaff',
    'glassstaff',
    'wyvern tor',
    'lost mine of phandelver',
)


class NoAdventureNames(unittest.TestCase):
    def test_runtime_and_ingest_code_has_no_adventure_proper_nouns(self):
        roots = [ROOT / 'runtime']
        hits = []
        for root in roots:
            for path in sorted(root.rglob('*.py')):
                text = path.read_text(encoding='utf-8').casefold()
                for name in NAMES:
                    if name in text:
                        hits.append('%s: %s' % (path.relative_to(ROOT), name))
        self.assertFalse(hits, hits)
