"""Failures from a real multi-site adventure PDF, reproduced with original synthetic text.

No published book is read or committed. Layout numbers are pinned (SEED). Each case is the
shape that broke ingest: reused area numbers across two maps, an object-stream text layer,
padded pdftotext output, an italic read-aloud with no box, a repeated running part header,
a stat block with more than two lines before Armor Class, two-column word order, and a
bare "Yes." while the opening is pending.
"""
import json
import tempfile
import time
import unittest
import warnings
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_lifecycle, kit_pdf  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import CONTEXT_BUDGET_BYTES, Runtime  # noqa: E402

SEED = 20261028
NIK = ROOT / 'tests/fixtures/characters/nik.json'

TWO_SITES = """\
4. Tower Room .... 9

PART 1: THE HIDEOUT
\f
PART 1: THE HIDEOUT

Part 2: The Castle

4. Tower
> A high tower overlooks the valley from the castle.
The stair leads to area 1.

1. Hall
> Banners hang in the castle hall.
The stair leads to area 4.
\f
PART 1: THE HIDEOUT

Part 1: The Hideout

1. Gate
   Rain hits the hideout gate and the bell is still.
The tunnel leads to area 4.
A loose chain wants a DC 13 Dexterity check.

4. Cellar
> Barrels stand in the dark of the hideout.
The ladder leads to area 1.
Two goblin scouts wait behind the barrels.

Appendix: Creatures

Goblin Scout
Small humanoid (goblinoid),
neutral evil
darkvision 60 ft.
Armor Class 15
Hit Points 7 (2d6)
Speed 30 ft.
Scimitar. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.
"""


def _escape(text):
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _pdf(objects, root=b'1 0 R'):
    """objects: list of (number, body_bytes) in file order. Appends an xref stream? No: classic
    writer is separate. This writes traditional objects only."""
    out = bytearray(b'%PDF-1.4\n')
    offsets = {}
    for num, body in objects:
        offsets[num] = len(out)
        out += ('%d 0 obj\n' % num).encode('ascii') + body + b'\nendobj\n'
    return bytes(out), offsets


def object_stream_pdf():
    """A text-layer page that exists only inside an ObjStm, found via an xref stream.

    A scanner that only looks for 'N G obj' never sees the page, so it reports no text layer.
    The content stream's /Length is an indirect object, the way published files write it.
    """
    content = b'BT /F1 12 Tf 72 700 Td (1. Obj Gate) Tj T* (A post stands by the obj gate.) Tj ET'
    compressed = zlib.compress(content)
    page = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R '
            b'/Resources << /Font << /F1 5 0 R >> >> >>')
    header = b'3 0\n'
    objstm_plain = header + page
    objstm = zlib.compress(objstm_plain)
    # Build the file, then the xref stream whose own offset we know before writing it.
    parts = []
    def add(blob):
        parts.append(blob)
        return sum(len(p) for p in parts) - len(blob)

    chunks = [b'%PDF-1.5\n']
    def here():
        return sum(len(c) for c in chunks)

    def obj(num, body):
        off = here()
        chunks.append(('%d 0 obj\n' % num).encode('ascii') + body + b'\nendobj\n')
        return off

    off = {0: 0}
    off[1] = obj(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    off[2] = obj(2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    off[8] = obj(8, str(len(compressed)).encode('ascii'))
    off[4] = obj(4, (b'<< /Filter /FlateDecode /Length 8 0 R >>\nstream\n' + compressed + b'\nendstream'))
    off[5] = obj(5, b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    off[6] = obj(6, (b'<< /Type /ObjStm /N 1 /First %d /Filter /FlateDecode /Length %d >>\nstream\n'
                     % (len(header), len(objstm))) + objstm + b'\nendstream')
    # xref stream is object 7. Its offset is the current end.
    size = 9
    xref_off = here()
    entries = {0: (0, 0, 65535)}
    for num, file_off in off.items():
        if num == 0:
            continue
        entries[num] = (1, file_off, 0)
    entries[7] = (1, xref_off, 0)
    entries[3] = (2, 6, 0)  # object 3 is index 0 inside object stream 6
    row = b''
    for n in range(size):
        typ, a, b = entries.get(n, (0, 0, 65535))
        row += bytes([typ]) + int(a).to_bytes(4, 'big') + int(b).to_bytes(2, 'big')
    xref_raw = zlib.compress(row)
    xref_body = (b'<< /Type /XRef /Size %d /W [1 4 2] /Root 1 0 R /Index [0 %d] '
                 b'/Filter /FlateDecode /Length %d >>\nstream\n' % (size, size, len(xref_raw))
                 + xref_raw + b'\nendstream')
    obj(7, xref_body)
    chunks.append(('startxref\n%d\n%%%%EOF\n' % xref_off).encode('ascii'))
    return b''.join(chunks)


def italic_box_pdf():
    """Read-aloud set in an italic font, with no vector rectangle and no '>'."""
    stream = (
        'BT /F1 12 Tf 1 0 0 1 72 700 Tm (1. Italic Gate) Tj ET\n'
        'BT /F2 12 Tf 1 0 0 1 72 676 Tm (Rain hits the italic gate and the bell is still.) Tj ET\n'
        'BT /F1 12 Tf 1 0 0 1 72 650 Tm (The tunnel leads to area 2.) Tj ET\n'
        'BT /F1 12 Tf 1 0 0 1 72 620 Tm (2. Italic Yard) Tj ET\n'
        'BT /F1 12 Tf 1 0 0 1 72 596 Tm (The tunnel leads back to area 1.) Tj ET\n'
    ).encode('latin-1')
    raw = zlib.compress(stream)
    objects = []
    # built below with a tiny classic PDF so the existing scanner can read it; the italic
    # flag is the part under test, not object streams.
    out = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    bodies = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: b'<< /Type /Pages /Kids [4 0 R] /Count 1 >>',
        3: (b'<< /Filter /FlateDecode /Length %d >>\nstream\n' % len(raw)) + raw + b'\nendstream',
        4: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 3 0 R '
            b'/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>'),
        5: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        6: b'<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic >>',
    }
    for num in range(1, 7):
        offsets.append(len(out))
        out += ('%d 0 obj\n' % num).encode('ascii') + bodies[num] + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 7\n0000000000 65535 f \n'
    for off in offsets[1:]:
        out += ('%010d 00000 n \n' % off).encode('ascii')
    out += ('trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % xref).encode('ascii')
    return bytes(out)


def two_column_words_pdf():
    """Same baseline, two columns, one word per Tj. A position-blind join drops 'door'."""
    left = ['The', 'door', 'of', 'bronze-covered', 'wood', 'stands', 'shut.']
    right = ['A', 'torch', 'burns', 'in', 'a', 'sconce.']
    y = 500
    ops = []
    x = 36
    for word in left:
        ops.append((x, word))
        x += 8 + len(word) * 5
    x = 340
    for word in right:
        ops.append((x, word))
        x += 8 + len(word) * 5
    # A location heading above, full left column, so the page is an adventure page.
    lines = ['BT /F1 12 Tf 1 0 0 1 36 640 Tm (1. Bronze Door) Tj ET\n']
    for x, word in ops:
        lines.append('BT /F1 11 Tf 1 0 0 1 %s %s Tm (%s) Tj ET\n' % (x, y, _escape(word)))
    lines.append('BT /F1 12 Tf 1 0 0 1 36 460 Tm (The path leads to area 2.) Tj ET\n')
    lines.append('BT /F1 12 Tf 1 0 0 1 340 640 Tm (2. Sconce) Tj ET\n')
    lines.append('BT /F1 12 Tf 1 0 0 1 340 460 Tm (The path leads back to area 1.) Tj ET\n')
    stream = ''.join(lines).encode('latin-1')
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


def padded_layout_text():
    """pdftotext -layout padding: letter ratio of the whole string is under 0.5."""
    prose = (
        'Chapter 1: Padded Post\n\n'
        '1. Padded Gate\n'
        '   Rain hits the padded gate and the bell is still.\n'
        'The lane leads to area 2.\n\n'
        '2. Padded Shed\n'
        '   The shed smells of rope.\n'
        'The lane leads back to area 1.\n'
    )
    pad = ' ' * 400 + '\n'
    text = (pad * 8) + prose + (pad * 8)
    letters = sum(ch.isalpha() for ch in text)
    assert letters / len(text) < 0.5
    assert letters / sum(1 for ch in text if not ch.isspace()) > 0.5
    return text


class PublishedShape(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        self.assertEqual(SEED, 20261028)
        self.assertEqual(CONTEXT_BUDGET_BYTES, 107000)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = self.folder / 'kit.sqlite'

    def test_reused_area_numbers_stay_in_their_site_and_part_1_starts(self):
        text = kit_adventure.prepare_source(TWO_SITES)
        index = kit_adventure.build_index(text, title='Two Sites')
        keys = set(index['locations'])
        self.assertIn('hideout-1', keys)
        self.assertIn('hideout-4', keys)
        self.assertIn('castle-1', keys)
        self.assertIn('castle-4', keys)
        self.assertEqual(index['start'], 'hideout-1')
        self.assertEqual(index['locations']['hideout-1']['name'], 'Gate')
        self.assertNotEqual(index['locations']['hideout-4']['name'], 'Tower')
        gate = index['locations']['hideout-1']
        tos = {c['to'] for c in gate['connections']}
        self.assertIn('hideout-4', tos)
        self.assertNotIn('castle-4', tos)
        self.assertNotIn('castle-1', tos)
        # The running part header is one chapter, not one per page.
        titles = [c['title'] for c in index['chapters']]
        self.assertEqual(sum(1 for t in titles if 'hideout' in t.casefold()), 1)
        self.assertLess(len(index['chapters']), 6)
        # The contents line is not a room.
        self.assertNotIn('Tower Room', [loc['name'] for loc in index['locations'].values()])
        report = kit_adventure.ingest_adventure(self.db, text=TWO_SITES, title='Two Sites')
        self.assertEqual(report['start_location'], 'hideout-1')
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        hidden = ' '.join(f['text'] for f in room['facts'].values() if not f['visible'])
        self.assertIn('hideout gate', visible.lower())
        self.assertNotIn('DC 13', visible)
        self.assertIn('DC 13', hidden)
        targets = [(a.get('room_link') or {}).get('adventure', {}).get('location')
                   for a in room['areas'].values()]
        self.assertIn('hideout-4', targets)
        self.assertNotIn('castle-4', targets)
        self.assertNotIn('castle-1', targets)

    def test_stat_block_with_a_long_preamble_is_indexed_and_stays_hidden(self):
        kit_adventure.import_adventure(self.db, text=TWO_SITES, title='Two Sites')
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        self.assertIn('goblin scout', index['stat_blocks'])
        text = (kit_adventure.folder_for(self.db) / 'source.txt').read_text(encoding='utf-8')
        block, prov, _ = kit_adventure.parse_stat_block(text, index['stat_blocks']['goblin scout'])
        self.assertEqual(block['ac'], 15)
        self.assertEqual(block['hp'], 7)
        self.assertEqual(prov['ac']['quote'], 'Armor Class 15')
        out = kit_adventure.compile_location(self.db, 'hideout-4', neighbours=False)
        room = json.loads(Path(out['room']).read_text(encoding='utf-8'))
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        self.assertNotIn('Armor Class', visible)
        self.assertNotIn('15', visible)
        self.assertEqual(room['actors']['goblin_scout_1']['visible'], False)

    def test_object_stream_text_layer_is_not_a_scan(self):
        data = object_stream_pdf()
        self.assertNotIn(b'3 0 obj', data)  # the page is not a top-level object
        clock = time.perf_counter()
        found = kit_pdf.extract(data)
        elapsed = time.perf_counter() - clock
        self.assertNotEqual(found['kind'], 'no_text_layer', found)
        self.assertGreater(found['text_ops'], 0)
        self.assertGreater(found['pages'], 0)
        self.assertIn('Obj Gate', found['text'])
        self.assertLess(elapsed, 1.0, elapsed)

    def test_padded_pdftotext_layout_ingests_in_one_step(self):
        text = padded_layout_text()
        self.assertFalse(kit_pdf.text_usable(text) if False else
                         sum(ch.isalpha() for ch in text) / len(text) > 0.5)
        self.assertTrue(kit_pdf.text_usable(text))
        path = self.folder / 'pad.pdf'
        path.write_bytes(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF\n')

        def fake(pdf_path):
            return text

        with mock.patch('runtime.kit_adventure._pdftotext', fake):
            report = kit_adventure.ingest_adventure(self.db, pdf=path, reader='pdftotext', title='Padded Post')
        self.assertEqual(report['reader'], 'pdftotext')
        self.assertEqual(report['start_location'], '1')
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        self.assertIn('padded gate', visible.lower())

    def test_italic_read_aloud_is_player_visible_without_a_box(self):
        found = kit_pdf.extract(italic_box_pdf())
        self.assertEqual(found['kind'], 'text', found['text'])
        self.assertIn('> Rain hits the italic gate', found['text'])
        path = self.folder / 'italic.pdf'
        path.write_bytes(italic_box_pdf())
        report = kit_adventure.ingest_adventure(self.db, pdf=path, reader='stdlib', title='Italic Gate')
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        self.assertIn('italic gate', visible.lower())
        self.assertGreater(sum(1 for f in room['facts'].values() if f['visible']), 0)

    def test_two_columns_keep_door_of_bronze_covered_wood(self):
        found = kit_pdf.extract(two_column_words_pdf())
        text = found['text'].lower()
        self.assertIn('door of bronze-covered wood', text)
        self.assertNotIn('the of bronze', text)
        self.assertIn('torch burns', text)

    def test_yes_commits_the_pending_opening(self):
        report = kit_adventure.ingest_adventure(self.db, text=TWO_SITES, title='Two Sites')
        self.assertEqual(report['start_location'], 'hideout-1')
        started = start_session(self.db, NIK, room=report['start_room'])
        self.assertTrue(started.get('committed'))
        self.assertTrue(started.get('character_loaded'))
        self.assertEqual(started.get('opened_room'), started.get('room_id'))
        self.assertIn('hideout gate', (started.get('spoken') or '').lower())
        self.assertNotIn('DC 13', started.get('spoken') or '')
        self.assertNotIn('Armor Class', started.get('spoken') or '')
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        status = kit_lifecycle.status(self.db)
        self.assertEqual(status['state'], 'playing')
        self.assertEqual(status['committed_turns'], 1)
        self.assertEqual(runtime.load()[1]['area'], 'here')
        self.assertIn('Gate', runtime.source()['areas']['here']['name'])


if __name__ == '__main__':
    unittest.main()
