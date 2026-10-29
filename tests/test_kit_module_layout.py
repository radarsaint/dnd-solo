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
import zlib
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_pdf  # noqa: E402
from runtime.kit_agent import _spoken_sentence, start_session  # noqa: E402
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

# Numbered encounters, no "1. Room" keys.
ENCOUNTERS = """\
PART 1: THE LESSON

Encounter 1: The Gate
A guard waits at a wooden gate. The path leads to encounter 2.

Encounter 2: The Yard
A clerk sits in the yard. The path leads back to encounter 1.

Encounter 3: The Hall
Benches line the hall. The path leads to encounter 4.

Encounter 4: The Cellar
A stair drops under the hall. The path leads back to encounter 3.
"""

# Travel and talk, in order, with no numbered places.
JOURNEY = """\
PART 1: THE JOURNEY

The North Road
The wagon rolls north along a rutted track. The track leads on to the river ferry.

The River Ferry
A ferryman waits at the bank. The track leads back to the north road.

The Far Bank
The far bank is quiet moss and stone. The track leads back to the river ferry.
"""

BLANK = """\
PART 1: THE BLANK

2. Bare Room
"""

# A wrapped sentence, a hyphenated word, and a soft hyphen. The opening must stay whole.
WRAPPED = """\
PART 1: THE ARMORY

The Broken Sword
You find a broken sword-
hand in the ruts, and the wagon
rolls on toward the trees with a soft\u00adwood staff.
The path leads to area 1.

1. Stone Arch
You stand under a stone arch where the road ends and the light fails.
The tunnel leads to area 2.

2. Inner Yard
A yard sits past the arch in the quiet. The path leads back to area 1.
"""

# The road names bandits that belong to a later keyed area. That area has its own fight.
BLEED = """\
PART 1: THE ROAD

Ambush on the Road
You walk the wagon road as the trees close in and the light fails around you.
Four bandits wait in area 2, and they are not on this road at all.
The track leads on toward a cave in the hill.

1. Stone Arch
You stand under a stone arch where the road ends and the air is cold.
The tunnel leads to area 2.

2. Inner Yard
Four bandits wait in the yard with weapons drawn and ready.
The tunnel leads back to area 1.
"""

# Headed scenes in a line: an ellipsis, one word, then two words. No area numbers.
MARCH = """\
PART 1: THE MARCH

First Light...
The camp stirs as first light reaches the trees and the wagon is packed for the day.

Camp
A cookfire burns low beside the wagon and the track leads on toward the road.

The Road
The road runs east through open country and the track leads back to camp.
"""

# A village heading before the first numbered area, with no second-person lead.
STREET = """\
PART 1: THE TOWN

Market Street
Stalls line the lane and the shops are shuttered for the night. The lane leads to area 1.

1. The Gate
The gate is shut tight against the dark. The path leads to area 2.

2. The Yard
A yard sits past the gate in the quiet. The path leads back to area 1.
"""

# A rules section before the first encounter. The host labels it; Python does not guess.
LESSON = """\
PART 1: THE LESSON

How to Play
This section explains how a session is run before any scene begins.
If the players ask, tell them the rules live in this front section.
A guard is not waiting in this section at all.

Encounter 1: The Gate
A guard waits at a wooden gate. The path leads to encounter 2.
The guard's orders are secret and must not be read aloud to the players.

Encounter 2: The Yard
A clerk sits in the yard past the gate. The path leads back to encounter 1.
"""


def _street_pdf():
    """Left column is the street. Right column is the keyed crawl. Same baseline."""
    def esc(text):
        return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    rows = [
        (36, 700, 'You stand on the village street as the shops close.'),
        (36, 676, 'The inn is dark and the lane leads to area 1.'),
        (340, 700, '1. The Gate'),
        (340, 676, 'The gate is shut. The path leads to area 2.'),
        (340, 640, '2. The Yard'),
        (340, 616, 'A yard sits past the gate. The path leads back to area 1.'),
    ]
    stream = ''.join(
        'BT /F1 12 Tf 1 0 0 1 %s %s Tm (%s) Tj ET\n' % (x, y, esc(text)) for x, y, text in rows
    ).encode('latin-1')
    raw = zlib.compress(stream)
    out = bytearray(b'%PDF-1.4\n')
    bodies = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: b'<< /Type /Pages /Kids [4 0 R] /Count 1 >>',
        3: (b'<< /Filter /FlateDecode /Length %d >>\nstream\n' % len(raw)) + raw + b'\nendstream',
        4: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 3 0 R '
            b'/Resources << /Font << /F1 5 0 R >> >> >>'),
        5: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    }
    offsets = [0]
    for num in range(1, 6):
        offsets.append(len(out))
        out += ('%d 0 obj\n' % num).encode('ascii') + bodies[num] + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 6\n0000000000 65535 f \n'
    for off in offsets[1:]:
        out += ('%010d 00000 n \n' % off).encode('ascii')
    out += ('trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % xref).encode('ascii')
    return bytes(out)


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
        self.assertTrue(opened.get('character_loaded'))
        self.assertEqual(opened.get('opened_room'), opened.get('room_id'))
        self.assertTrue(opened.get('committed'))
        self.assertIn('wagon', (opened.get('spoken') or '').casefold())
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

    def test_numbered_encounters_open_without_keyed_rooms(self):
        report = kit_adventure.ingest_adventure(self.db, text=ENCOUNTERS)
        self.assertIn('1', str(report['start_location']))
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        names = [(loc.get('name') or '').casefold() for loc in index['locations'].values()]
        for place in ('gate', 'yard', 'hall', 'cellar'):
            self.assertTrue(any(place in name for name in names), names)
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        self.assertTrue(room.get('facts'))
        self.assertTrue(room.get('exits'))
        opened = start_session(str(self.db), str(NIK))
        self.assertEqual(opened.get('stage'), 'started')
        self.assertTrue(opened.get('character_loaded'))
        self.assertEqual(opened.get('opened_room'), opened.get('room_id'))
        self.assertTrue(opened.get('committed'))
        self.assertIn('gate', (opened.get('spoken') or '').casefold())

    def test_a_linear_chain_of_scenes_opens(self):
        report = kit_adventure.ingest_adventure(self.db, text=JOURNEY)
        self.assertTrue(str(report['start_location']).startswith('scene:'), report['start_location'])
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        names = [(loc.get('name') or '').casefold() for loc in index['locations'].values()]
        self.assertTrue(any('north road' in name for name in names), names)
        self.assertTrue(any('ferry' in name for name in names), names)
        self.assertTrue(any('far bank' in name for name in names), names)
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        self.assertTrue(room.get('exits'))
        opened = start_session(str(self.db), str(NIK))
        self.assertTrue(opened.get('committed'))
        self.assertTrue(opened.get('character_loaded'))
        self.assertIn('wagon', (opened.get('spoken') or '').casefold())

    def test_two_columns_keep_the_street_ahead_of_the_crawl(self):
        data = _street_pdf()
        text = kit_pdf.extract(data)['text']
        self.assertLess(text.find('village street'), text.find('1. The Gate'))
        self.assertNotIn('village street 1.', text.replace('\n', ' '))
        path = self.db.parent / 'street.pdf'
        path.write_bytes(data)
        report = kit_adventure.ingest_adventure(self.db, pdf=path, reader='stdlib')
        self.assertFalse(str(report.get('start_location') or '').endswith('-2'), report.get('start_location'))
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(fact.get('text') or '' for fact in room['facts'].values() if fact.get('visible'))
        self.assertIn('village street', visible.casefold())
        self.assertTrue(room.get('facts'))
        opened = start_session(str(self.db), str(NIK))
        self.assertEqual(opened.get('opened_room'), opened.get('room_id'))
        self.assertTrue(opened.get('character_loaded'))
        self.assertTrue(opened.get('committed'))
        self.assertIn('village street', (opened.get('spoken') or '').casefold())

    def test_an_empty_room_is_never_staged(self):
        report = kit_adventure.ingest_adventure(self.db, text=BLANK)
        self.assertIsNone(report.get('start_room'))
        self.assertTrue(report.get('places') or report.get('starts'))
        opened = start_session(str(self.db), str(NIK))
        self.assertEqual(opened.get('stage'), 'pick_start')
        self.assertIsNone(opened.get('opened_room'))
        self.assertFalse(opened.get('character_loaded'))
        self.assertIn('places', (opened.get('table_line') or '').casefold())
        self.assertTrue(opened.get('places'))

    def test_a_wrapped_sentence_is_joined_and_not_cut_off(self):
        long_sentence = 'You walk ' + ' '.join(['onward'] * 90) + ' until the gate appears.'
        self.assertGreater(len(long_sentence), 400)
        self.assertEqual(kit_adventure._cut(long_sentence), long_sentence)
        self.assertEqual(kit_adventure._cut('The gate is shut. ' + ('More text ' * 80)), 'The gate is shut.')
        self.assertEqual(_spoken_sentence('The gate is shut. Then the hinge'), 'The gate is shut.')
        report = kit_adventure.ingest_adventure(self.db, text=WRAPPED)
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(fact.get('text') or '' for fact in room['facts'].values() if fact.get('visible'))
        self.assertIn('swordhand', visible.casefold())
        self.assertIn('wagon rolls', visible.casefold())
        self.assertIn('softwood', visible.casefold())
        self.assertNotIn('sword-', visible)
        self.assertNotIn('…', visible)
        self.assertTrue(visible.rstrip()[-1] in '.!?')
        opened = start_session(str(self.db), str(NIK))
        spoken = opened.get('spoken') or ''
        body = spoken.split('\nKit:')[0].rstrip()
        self.assertTrue(body[-1] in '.!?')
        self.assertIn('swordhand', spoken.casefold())
        self.assertIn('start_picker', opened)
        request = report['label_request']
        self.assertEqual(request['section'], report['start_location'])
        self.assertTrue(request.get('blocks'))
        self.assertGreaterEqual(len(request['instructions'].encode('utf-8')), 1000)
        self.assertLessEqual(len(request['instructions'].encode('utf-8')), 1600)

    def test_a_later_areas_creatures_do_not_arm_this_scene(self):
        report = kit_adventure.ingest_adventure(self.db, text=BLEED)
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        self.assertFalse(room.get('actors'))
        self.assertFalse(room.get('triggers'))
        self.assertNotIn('weapons drawn', json.dumps(room).casefold())
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        yard = next(key for key, loc in index['locations'].items()
                    if 'yard' in (loc.get('name') or '').casefold())
        kit_adventure.compile_location(self.db, yard, neighbours=False)
        yard_room = json.loads(kit_adventure.room_file(self.db, yard).read_text(encoding='utf-8'))
        self.assertTrue(any('bandit' in key for key in yard_room.get('actors') or {}))
        road = ' '.join(fact.get('text') or '' for fact in room['facts'].values())
        self.assertNotIn('weapons drawn', road.casefold())

    def test_a_linear_chain_of_headed_scenes_becomes_places(self):
        report = kit_adventure.ingest_adventure(self.db, text=MARCH)
        self.assertTrue(str(report['start_location']).startswith('scene:'), report['start_location'])
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        names = [(loc.get('name') or '').casefold() for loc in index['locations'].values()]
        self.assertTrue(any(name.startswith('first light') for name in names), names)
        self.assertIn('camp', names)
        self.assertTrue(any(name == 'the road' for name in names), names)
        self.assertIn('light', (index['locations'][index['start']].get('name') or '').casefold())
        self.assertGreaterEqual(len(report['start_picker']['places']), 3)

    def test_a_village_heading_before_area_one_is_the_opening(self):
        report = kit_adventure.ingest_adventure(self.db, text=STREET)
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        start = index['locations'][index['start']]
        self.assertIn('street', (start.get('name') or '').casefold())
        self.assertEqual(start.get('type'), 'scene')
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(fact.get('text') or '' for fact in room['facts'].values() if fact.get('visible'))
        self.assertIn('stalls', visible.casefold())
        self.assertNotIn('shut tight', visible.casefold())
        opened = start_session(str(self.db), str(NIK))
        self.assertIn('stalls', (opened.get('spoken') or '').casefold())
        self.assertIn('start_picker', opened)

    def test_labeling_stays_in_the_host_process(self):
        text = (ROOT / 'runtime' / 'kit_labels.py').read_text(encoding='utf-8')
        for banned in ('urllib', 'openai', 'requests', 'http.client'):
            self.assertNotIn(banned, text)
        card = (ROOT / 'docs' / 'PLAY_CARD.md').read_text(encoding='utf-8')
        self.assertIn('word for word', card)
        self.assertIn('accepted_public_event', card)
        self.assertIn('Case and punctuation may differ', card)
        self.assertIn('player_hears', card)
        self.assertIn('same exchange', card.casefold())
        self.assertIn('give me a second, checking the page', card.casefold())
        self.assertIn('same line', card.casefold())

    def test_missing_labels_keep_the_heuristic_opening_and_the_picker(self):
        report = kit_adventure.ingest_adventure(self.db, text=LESSON)
        self.assertIsNotNone(report['label_request'])
        self.assertGreaterEqual(len(report['start_picker']['places']), 2)
        opened = start_session(str(self.db), str(NIK))
        self.assertEqual(opened.get('stage'), 'started')
        self.assertTrue(opened.get('committed'))
        self.assertIn('start_picker', opened)
        self.assertTrue(opened['start_picker']['places'])
        self.assertIn('places', opened['start_picker']['table_line'].casefold())
