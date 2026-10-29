"""Block labels for one section. Synthetic layouts only. No published names.

Four shapes: a road scene whose boxed text opens before room 1, a social beat
sharing a page with room 1, a two-column page, and a soft DM line marked player.
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

from runtime import kit_adventure, kit_labels  # noqa: E402
from runtime.kit_agent import start_session  # noqa: E402

NIK = ROOT / 'tests/fixtures/characters/nik.json'

ROAD = """\
PART 1: THE NORTH ROAD

Tips for the road
Keep the wagon moving and leave the next room for later.

The North Road
> Arrows whisper out of the brush and the wagon lurches to a stop.

1. Cave Mouth
You stand at a dark cave mouth where the hill opens.
The track leads to area 2.

2. Inner Yard
A yard sits past the mouth. The track leads back to area 1.
"""

SOCIAL = """\
PART 1: THE MARKET

The square is full of talk and the baker waves you over to the stall.
1. The Gate
The gate is shut tight against the dark. The path leads to area 2.

2. The Yard
A yard sits past the gate in the quiet. The path leads back to area 1.
"""

CART = """\
PART 1: THE CART

The Cart
> The cart sits in the ruts with its canvas tied down.
If the characters search the cart, they find a sealed letter under the board.
The track leads to area 1.

1. The Shed
You stand in a shed off the track. The path leads back to the cart.
"""


def _answer(request, audience, mode):
    opening = request['opening_block']
    blocks = {}
    for block in request['blocks']:
        blocks[block['id']] = {
            'audience': audience(block),
            'kind': block['kind'],
            'scene': block['scene'],
            'opening': block['id'] == opening,
        }
    return {
        'section': request['section'],
        'section_mode': mode,
        'opening_block': opening,
        'blocks': blocks,
    }


def _column_pdf():
    def esc(text):
        return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    rows = [
        (36, 700, 'You stand on the village street'),
        (36, 676, 'as the shops close for the night.'),
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


class LabelPass(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'

    def _ingest(self, text):
        report = kit_adventure.ingest_adventure(self.db, text=text)
        self.assertIn('landing', report)
        self.assertIn('who\'s walking in', report['landing']['table_line'].casefold())
        self.assertEqual(report['landing']['opening_after'], 'their answer')
        return report

    def test_boxed_road_text_opens_ahead_of_tips_and_room_one(self):
        report = self._ingest(ROAD)
        request = report['label_request']
        self.assertGreaterEqual(len(request['instructions'].encode('utf-8')), 1000)
        self.assertLessEqual(len(request['instructions'].encode('utf-8')), 1600)
        joined = ' '.join(block['text'] for block in request['blocks'])
        self.assertIn('arrows whisper', joined.casefold())
        self.assertNotIn('cave mouth', joined.casefold())
        reply = _answer(request, lambda block: 'player' if block['kind'] == 'read_aloud' else 'dm', 'regional')
        done = kit_labels.accept(self.db, reply)
        self.assertEqual(done['stage'], 'labels_frozen', done)
        heard = ' '.join(done['player_hears']).casefold()
        self.assertIn('arrows whisper', heard)
        self.assertNotIn('leave the next room', heard)
        self.assertNotIn('cave mouth', heard)
        opened = start_session(str(self.db), str(NIK))
        spoken = (opened.get('spoken') or '').casefold()
        self.assertIn('arrows whisper', spoken)
        self.assertNotIn('leave the next room', spoken)
        self.assertEqual(opened.get('player_hears'), done['player_hears'])

    def test_a_social_beat_on_room_ones_page_comes_first(self):
        report = self._ingest(SOCIAL)
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        start = index['locations'][index['start']]
        gate = next(loc for loc in index['locations'].values() if 'gate' in (loc.get('name') or '').casefold())
        self.assertEqual(start.get('page'), gate.get('page'))
        self.assertLess(start.get('offset'), gate.get('offset'))
        self.assertIn('baker', (start.get('name') or report['start_location'] or '').casefold()
                      + ' '.join(block['text'] for block in report['label_request']['blocks']).casefold())
        reply = _answer(report['label_request'],
                        lambda block: 'player' if block['kind'] in ('prose', 'read_aloud') else 'dm',
                        'town_social')
        done = kit_labels.accept(self.db, reply)
        self.assertEqual(done['stage'], 'labels_frozen', done)
        self.assertIn('baker', ' '.join(done['player_hears']).casefold())
        self.assertNotIn('shut tight', ' '.join(done['player_hears']).casefold())

    def test_two_columns_stay_separate_blocks(self):
        path = self.db.parent / 'street.pdf'
        path.write_bytes(_column_pdf())
        report = kit_adventure.ingest_adventure(self.db, pdf=path, reader='stdlib')
        request = report['label_request']
        for block in request['blocks']:
            text = block['text'].casefold()
            self.assertFalse('village street' in text and 'the gate' in text, text)
        blob = ' '.join(block['text'] for block in request['blocks']).casefold()
        self.assertIn('village street', blob)
        self.assertIn('shops close', blob)
        self.assertNotIn('the gate', blob)

    def test_a_soft_dm_line_marked_player_is_not_spoken(self):
        report = self._ingest(CART)
        request = report['label_request']
        reply = _answer(request, lambda block: 'player', 'crawl')
        done = kit_labels.accept(self.db, reply)
        self.assertEqual(done['stage'], 'labels_frozen', done)
        heard = ' '.join(done['player_hears']).casefold()
        self.assertIn('cart sits', heard)
        self.assertNotIn('if the characters', heard)
        self.assertNotIn('sealed letter', heard)
        opened = start_session(str(self.db), str(NIK))
        spoken = (opened.get('spoken') or '').casefold()
        self.assertIn('cart sits', spoken)
        self.assertNotIn('sealed letter', spoken)

    def test_an_unknown_block_id_speaks_nothing_from_that_section(self):
        report = self._ingest(CART)
        request = report['label_request']
        reply = _answer(request, lambda block: 'player', 'crawl')
        reply['blocks']['b99'] = {
            'audience': 'player', 'kind': 'prose', 'scene': request['section'], 'opening': False,
        }
        done = kit_labels.accept(self.db, reply)
        self.assertEqual(done['stage'], 'labels_rejected', done)
        self.assertEqual(done['player_hears'], [])
        self.assertTrue(done.get('start_picker') or done.get('soft_start'))
        opened = start_session(str(self.db), str(NIK))
        spoken = (opened.get('spoken') or opened.get('table_line') or '').casefold()
        self.assertNotIn('cart sits', spoken)

    def test_a_sidebar_stays_dm(self):
        text = """\
PART 1: THE HALL

The Hall
> A long hall runs to a pair of doors.
Sidebar: the patrol changes at dusk and the password is ash.
The doors lead to area 1.

1. The Doors
The doors are shut. The hall leads back.
"""
        report = self._ingest(text)
        sidebar = [block for block in report['label_request']['blocks'] if block.get('kind') == 'sidebar']
        self.assertTrue(sidebar, report['label_request']['blocks'])
        self.assertEqual(sidebar[0].get('audience'), 'dm')
        reply = _answer(report['label_request'], lambda block: 'player', 'crawl')
        done = kit_labels.accept(self.db, reply)
        self.assertEqual(done['stage'], 'labels_frozen', done)
        heard = ' '.join(done['player_hears']).casefold()
        self.assertIn('long hall', heard)
        self.assertNotIn('password', heard)
