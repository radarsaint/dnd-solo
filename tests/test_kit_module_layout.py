"""How a published module is laid out, not any one book.

Two synthetic shapes, both original text:

- A contents list of several parts, then the real part later: prose and an encounter
  heading (a running header glued on with a bar) before the first numbered area.
- A town of named places and no numbered rooms, each heading carrying a running header.

A sheet passed to start with no --room opens that default and loads the character.
"""
import json
import tempfile
import unittest
import warnings
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure  # noqa: E402
from runtime.kit_agent import start_session  # noqa: E402
from runtime.state_context import CONTEXT_BUDGET_BYTES  # noqa: E402

NIK = ROOT / 'tests/fixtures/characters/nik.json'

# Contents cluster, then the real part after a page break. The encounter heading
# shares its line with a running part header. The read-aloud sits before that heading.
ROAD_THEN_KEY = """\
NORTH WATCH

PART 1: THE LONG ROAD
A wagon and a cave.

PART 2: THE MARKET TOWN
Stalls and a well.

PART 3: THE FAR HILLS
Old Bridge
You meet four wolves on the old bridge before the hills.
\f
PART 1: THE LONG ROAD

You have been on the wagon road for two days when the trees close in.
The horses slow as the ruts narrow.

AMBUSH ON THE ROAD | PART 1: THE LONG ROAD
Four wolves rush the wagon from the brush and the fight is on.
The track leads on toward a cave.

1. Stone Arch
You stand under a stone arch where the road ends.
The tunnel leads to area 2.

2. Inner Yard
> A yard sits past the arch.
The tunnel leads back to area 1.
\f
PART 3: THE FAR HILLS

4. Hill Gate
> A gate stands on the hill.
The path leads to area 5.

5. Hill Well
> A well sits by the gate.
The path leads back to area 4.
"""

# No area numbers. Each place heading shares a line with the part's running header.
TOWN_HUB = """\
PART 1: THE MARKET

THE RED INN | THE MARKET
> A fire burns in the common room of the red inn. Travelers sleep by the hearth.
The lane leads to the old shrine.

THE OLD SHRINE | THE MARKET
> Candles burn in the old shrine. The lane outside is quiet.
The lane leads back to the red inn.
"""


class ModuleLayout(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        self.assertEqual(CONTEXT_BUDGET_BYTES, 107000)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'

    def test_prose_before_the_first_keyed_area_is_the_opening(self):
        report = kit_adventure.ingest_adventure(self.db, text=ROAD_THEN_KEY)
        self.assertTrue(str(report['start_location']).startswith('scene:'), report['start_location'])
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        start = index['locations'][index['start']]
        self.assertEqual(start.get('type'), 'scene')
        self.assertEqual(start.get('part_n'), 1)
        self.assertGreater(start.get('page'), 1)
        self.assertIn('road', (start.get('name') or '').casefold())
        self.assertTrue(any(loc.get('name') == 'Stone Arch' for loc in index['locations'].values()))
        for item in index.get('starts') or []:
            line = item.get('line') or ''
            self.assertFalse('Part 3' in line and '(p. 1)' in line, line)
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(fact.get('text') or '' for fact in room['facts'].values() if fact.get('visible'))
        self.assertIn('wagon road', visible.casefold())
        opened = start_session(str(self.db), str(NIK))
        self.assertEqual(opened.get('stage'), 'started')
        self.assertEqual((opened.get('character') or {}).get('name'), 'Nik')
        self.assertIn('road', (opened.get('room_id') or '').casefold())

    def test_a_town_hub_with_no_numbered_rooms_still_opens(self):
        report = kit_adventure.ingest_adventure(self.db, text=TOWN_HUB)
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        names = [(loc.get('name') or '').casefold() for loc in index['locations'].values()]
        self.assertTrue(any('inn' in name for name in names), names)
        self.assertTrue(any('shrine' in name for name in names), names)
        self.assertTrue(str(report['start_location']).startswith('scene:'), report['start_location'])
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        self.assertTrue(room.get('exits'), room.get('exits'))
        visible = ' '.join(fact.get('text') or '' for fact in room['facts'].values() if fact.get('visible'))
        self.assertIn('red inn', visible.casefold())
