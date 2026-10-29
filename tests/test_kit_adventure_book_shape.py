"""Synthetic shapes of a multi-part published starter book. Original text only.

Covers: flush-left italic-less read-aloud recovered by second-person / first-narrative
heuristic; TOC and body-bleed chapters; OCR-split PART site slugs; zero bare keys when
any PART site exists; area refs scoped to their site; PNG-predictor xref streams so a
fat linearized PDF does not fall back to a full-file scan.
"""
import json
import re
import struct
import tempfile
import time
import unittest
from unittest import mock
import warnings
import zlib
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_pdf  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import CONTEXT_BUDGET_BYTES, Runtime  # noqa: E402

SEED = 20261028
NIK = ROOT / 'tests/fixtures/characters/nik.json'

# Flush-left read-aloud (no indent, no '> ', no italic cue). Second person marks it.
FLUSH_RA = """\
PART 1: GOBLIN ARROWS

1. Cave Mouth
The trail from the ambush leads to the hideout entrance.
Following the scouts' trail, you come across a large cave in a hillside.
A shallow stream flows out of the cave mouth, screened by dense briars.
The thicket in area 2 is impassable from the west.
DEVELOPMENTS
The scouts in area 2 are supposed to watch this area.

2. Scout Blind
> Two scouts crouch behind the briars.
The thicket overlooks area 1.
"""

# TOC bleed + OCR-split PART titles + false location from a spell line + bare orphans.
HYGIENE = """\
4. Tower Room .... 9

PART 1: GOBLIN ARROWS
Part 1, "Goblin Arrows," provides the characters with a road encounter.

1. Cave Mouth
> You stand before a dark cave mouth beside a cold stream.
The path leads to area 2.

2. Scout Blind
> Briars hide two scouts.
The path leads back to area 1.

PART 2: PHANDALlN
Part 2: PHAN DALlN
PART 2: PHANDALIN

1. Town Square
> Market stalls crowd the town square.
The road leads to area 2.

2. Manor
> A stone manor overlooks the square.
The road leads back to area 1.

PART 4: WAVE ECHO CAVE

1. Cave Entrance
> Damp air rolls from the cave entrance.
The tunnel leads to area 16.

16. Booming Cavern
> Thunder echoes in the booming cavern.
The tunnel leads to area 17.

17. Old Streambed
> A dry streambed cuts the floor.
The passage leads to area 16.

appendix A). The brazier cannot be removed from the
altar without a check.

16. Fake Orphan
This should stay under Wave Echo, not go bare.

APPENDIX: SPELLS

2. Paralyzing Ray. The target must succeed on a DC 13
Wisdom saving throw or be paralyzed.
"""

# Cross-site area number reuse: hideout area 3 must not link to web area 3.
CROSS_SITE = """\
PART 1: THE HIDEOUT

1. Gate
> Rain hits the hideout gate.
The tunnel leads to area 3.

3. Kennel
> Wolves snarl in the kennel.
The chimney climbs to area 1.
No monsters dwell here, but the sentries in area 3 of the spider web are supposed to watch.

PART 3: THE SPIDER'S WEB

1. Forest Path
> A forest path winds under silk.
The trail leads to area 3.

3. Web Bridge
> A bridge of webs spans the gorge.
The trail leads back to area 1.
"""


def _png_up_rows(payload, columns):
    """PNG predictor 12 (Up) rows: 1 filter byte + ``columns`` data bytes each."""
    out = bytearray()
    prev = bytearray(columns)
    for i in range(0, len(payload), columns):
        row = bytearray(payload[i:i + columns])
        if len(row) < columns:
            row.extend(b'\x00' * (columns - len(row)))
        filt = bytearray(columns)
        for j in range(columns):
            filt[j] = (row[j] - prev[j]) & 255
        out.append(2)  # Up
        out.extend(filt)
        prev = row
    return bytes(out)


def predictor_xref_pdf():
    """A tiny linearized-style PDF whose xref stream needs Predictor 12 to parse.

    Without undoing the predictor the loader falls back to a full scan. With it, the
    catalog and page resolve through the xref in well under a second.
    """
    assert SEED == 20261028
    content = b'BT /F1 12 Tf 72 700 Td (1. Predictor Gate) Tj T* (> A lantern hangs at the predictor gate.) Tj ET'
    content_z = zlib.compress(content)
    # Object layout: 1 catalog, 2 pages, 3 font, 4 contents, 5 page, 6 xref stream
    chunks = [b'%PDF-1.5\n']
    offsets = {}

    def obj(num, body):
        offsets[num] = sum(len(c) for c in chunks)
        chunks.append(('%d 0 obj\n' % num).encode('ascii') + body + b'\nendobj\n')

    obj(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    obj(2, b'<< /Type /Pages /Kids [5 0 R] /Count 1 >>')
    obj(3, b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    obj(4, (b'<< /Filter /FlateDecode /Length %d >>\nstream\n' % len(content_z)) + content_z + b'\nendstream')
    obj(5, (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R '
            b'/Resources << /Font << /F1 3 0 R >> >> >>'))
    # W = [1, 4, 0]; entries for objs 1..5 as type 1 with 4-byte offsets
    cols = 5
    payload = bytearray()
    for num in range(1, 6):
        payload.append(1)
        payload.extend(struct.pack('>I', offsets[num]))
    predicted = _png_up_rows(bytes(payload), cols)
    xref_raw = zlib.compress(predicted)
    xref_body = (
        b'<< /Type /XRef /Index [1 5] /W [1 4 0] /Size 7 /Root 1 0 R '
        b'/DecodeParms << /Columns 5 /Predictor 12 >> /Filter /FlateDecode /Length %d >>\n'
        b'stream\n' % len(xref_raw)
    ) + xref_raw + b'\nendstream'
    xref_at = sum(len(c) for c in chunks)
    chunks.append(b'6 0 obj\n' + xref_body + b'\nendobj\n')
    chunks.append(('startxref\n%d\n%%%%EOF\n' % xref_at).encode('ascii'))
    return b''.join(chunks)


class BookShape(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        self.assertEqual(SEED, 20261028)
        self.assertEqual(CONTEXT_BUDGET_BYTES, 107000)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = self.folder / 'kit.sqlite'

    def test_flush_left_second_person_becomes_read_aloud(self):
        prepared = kit_adventure.prepare_source(FLUSH_RA)
        self.assertIn('> Following the scouts', prepared)
        self.assertNotIn('> The trail from the ambush', prepared)
        self.assertNotIn('> The thicket in area 2', prepared)
        report = kit_adventure.ingest_adventure(self.db, text=FLUSH_RA)
        self.assertEqual(report['start_location'], 'goblin_arrows-1')
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        self.assertIn('you come across', visible.lower())
        self.assertNotIn('DC ', visible)
        self.assertNotIn('impassable', visible.lower())
        started = start_session(self.db, NIK, room=report['start_room'])
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        held = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10)).try_prepare('Yes.', one_pass=True)
        self.assertTrue(held.get('committed'))
        spoken = held.get('spoken') or ''
        self.assertIn('cave', spoken.lower())
        self.assertNotIn('The newcomer arrives', spoken)
        self.assertGreaterEqual(len(re.findall(r"[A-Za-z']+", spoken)), 12)

    def test_chapter_site_hygiene_and_zero_bare_keys(self):
        index = kit_adventure.build_index(kit_adventure.prepare_source(HYGIENE))
        keys = set(index['locations'])
        self.assertTrue(all('-' in k for k in keys), keys)
        self.assertNotIn('1', keys)
        self.assertNotIn('16', keys)
        self.assertNotIn('2', keys)
        sites = {k.split('-')[0] for k in keys}
        self.assertIn('goblin_arrows', sites)
        self.assertIn('phandalin', sites)
        self.assertIn('wave_echo_cave', sites)
        self.assertFalse(any('phan_dalln' == s or 'phan_da' in s for s in sites), sites)
        titles = [c['title'] for c in index['chapters']]
        self.assertFalse(any('provides the characters' in t for t in titles), titles)
        self.assertFalse(any('brazier cannot' in t for t in titles), titles)
        # Spell-line "2. Paralyzing Ray..." is not a room.
        self.assertFalse(any('paralyzing' in (index['locations'][k].get('name') or '').lower()
                             for k in keys))
        self.assertEqual(index['start'], 'goblin_arrows-1')
        report = kit_adventure.ingest_adventure(self.db, text=HYGIENE)
        self.assertEqual(report['start_location'], 'goblin_arrows-1')

    def test_area_refs_stay_inside_their_site(self):
        index = kit_adventure.build_index(kit_adventure.prepare_source(CROSS_SITE))
        kennel = index['locations']['hideout-3']
        targets = {c['to'] for c in kennel['connections']}
        self.assertIn('hideout-1', targets)
        self.assertTrue(all(t.startswith('hideout-') for t in targets), targets)
        web_keys = [k for k in index['locations'] if k.endswith('-3') and k.startswith('spider')]
        self.assertEqual(len(web_keys), 1, sorted(index['locations']))
        web = index['locations'][web_keys[0]]
        web_targets = {c['to'] for c in web['connections']}
        self.assertTrue(all(t.startswith(web['site'] + '-') for t in web_targets), web_targets)
        self.assertNotIn('hideout-3', web_targets)

    def test_png_predictor_xref_loads_without_full_scan(self):
        data = predictor_xref_pdf()
        clock = time.perf_counter()
        loaded = kit_pdf._load_via_xref(data)
        elapsed = time.perf_counter() - clock
        self.assertIsNotNone(loaded)
        objects, root = loaded
        self.assertTrue(kit_pdf._has_pages(objects, root))
        self.assertLess(elapsed, 1.0, elapsed)
        # extract must not need the scan fallback
        with mock.patch.object(kit_pdf, '_scan_objects', side_effect=AssertionError('scan')):
            found = kit_pdf.extract(data)
        self.assertEqual(found['kind'], 'text')
        self.assertIn('Predictor Gate', found['text'])
        self.assertIn('> A lantern hangs', found['text'])


if __name__ == '__main__':
    unittest.main()
