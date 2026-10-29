"""Letter-spaced PDF text, junk chapter slugs, and an opening stub. Original synthetic only.

SEED pins the glyph map. No published book text. A per-glyph TJ array with a ToUnicode
CMap must come back as words, not 'T h e'. A letter-spaced PART title must not become a
site, and a bare Yes must not speak 'The newcomer arrives' when read-aloud exists.
"""
import re
import tempfile
import time
import unittest
import warnings
import zlib
from pathlib import Path
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_pdf  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import CONTEXT_BUDGET_BYTES, Runtime  # noqa: E402

SEED = 20261028
NIK = ROOT / 'tests/fixtures/characters/nik.json'

TRAIL = """\
4. Goblin Arrows .... 5

Part 1: The Trail

Part 1: F o llo wi n g t h e R oa d

1. Trailhead
   Rain wets the trailhead stones and the bell is still.
The path leads to area 2.
A loose stone hides a DC 11 Dexterity check.

2. Bend
> The bend is quiet.
The path leads back to area 1.

Appendix: Creatures

Appendix
Armor Class 10
Hit Points 10 (2d8)
Bite. Melee Weapon Attack: +2 to hit, reach 5 ft., one target. Hit: 3 (1d4 + 1) piercing damage.

Goblin Scout
Small humanoid (goblinoid),
neutral evil
darkvision 60 ft.
Armor Class 13
Hit Points 11 (2d8)
Speed 30 ft.
Scimitar. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.
"""

BARE = """\
Part 1: The Empty Hall

1. Empty Hall
A DC 15 check finds the latch. Nobody left a description of the room.
The door leads to area 2.

2. Empty Stair
The stair leads back to area 1.
"""


def _classic(bodies):
    out = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for num in range(1, len(bodies) + 1):
        offsets.append(len(out))
        out += ('%d 0 obj\n' % num).encode('ascii') + bodies[num - 1] + b'\nendobj\n'
    xref = len(out)
    out += ('xref\n0 %d\n0000000000 65535 f \n' % (len(bodies) + 1)).encode('ascii')
    for off in offsets[1:]:
        out += ('%010d 00000 n \n' % off).encode('ascii')
    out += ('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n'
            % (len(bodies) + 1, xref)).encode('ascii')
    return bytes(out)


def glyph_pdf():
    """Each letter is its own TJ glyph id, with a kern that is not a word space except between words."""
    assert SEED == 20261028
    sentence = 'The trail runs past the old mill and the river.'
    chars = []
    for ch in sentence:
        if ch != ' ' and ch not in chars:
            chars.append(ch)
    mapping = {ch: i + 1 for i, ch in enumerate(chars)}
    bf = '\n'.join('<%04X> <%04X>' % (gid, ord(ch)) for ch, gid in mapping.items())
    cmap = ('begincmap\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n'
            '%d beginbfchar\n%s\nendbfchar\nendcmap\n' % (len(mapping), bf)).encode('ascii')
    items = []
    for ch in sentence:
        if ch == ' ':
            items.append('-320')  # thousandths: a word space, not a letter kern
        else:
            items.append('<%04X>' % mapping[ch])
            items.append('40')  # a tight kern, well under a word space
    if items and items[-1] == '40':
        items.pop()
    stream = ('BT /F1 12 Tf 72 720 Td (1. Glyph Trail) Tj ET\n'
              'BT /F2 12 Tf 72 680 Td [%s] TJ ET\n'
              'BT /F2 12 Tf 72 640 Td (The path leads to area 2.) Tj ET\n'
              'BT /F1 12 Tf 72 600 Td (2. Glyph Bend) Tj ET\n'
              'BT /F1 12 Tf 72 560 Td (The path leads back to area 1.) Tj ET\n'
              % ' '.join(items)).encode('latin-1')
    raw = zlib.compress(stream)
    return _classic([
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [6 0 R] /Count 1 >>',
        (b'<< /Filter /FlateDecode /Length %d >>\nstream\n' % len(raw)) + raw + b'\nendstream',
        cmap and (b'<< /Length %d >>\nstream\n' % len(cmap)) + cmap + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 3 0 R '
         b'/Resources << /Font << /F1 5 0 R /F2 7 0 R >> >> >>'),
        (b'<< /Type /Font /Subtype /Type0 /BaseFont /GlyphFont /Encoding /Identity-H '
         b'/ToUnicode 4 0 R /FontDescriptor 8 0 R >>'),
        b'<< /Type /FontDescriptor /FontName /GlyphFont /Flags 64 /ItalicAngle 0 >>',
    ])


def image_and_text_pdf():
    """A fat image XObject must not be inflated on the way to the text layer."""
    payload = zlib.compress(b'\x00' * 1500000)
    text = b'BT /F1 12 Tf 72 700 Td (1. Image Gate) Tj T* (A lantern hangs above the image gate.) Tj ET'
    text_z = zlib.compress(text)
    return _classic([
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [6 0 R] /Count 1 >>',
        (b'<< /Subtype /Image /Width 10 /Height 10 /ColorSpace /DeviceGray /BitsPerComponent 8 '
         b'/Filter /FlateDecode /Length %d >>\nstream\n' % len(payload)) + payload + b'\nendstream',
        (b'<< /Filter /FlateDecode /Length %d >>\nstream\n' % len(text_z)) + text_z + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R '
         b'/Resources << /Font << /F1 5 0 R >> /XObject << /Im 3 0 R >> >> >>'),
    ])


class Glyphs(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        self.assertEqual(SEED, 20261028)
        self.assertEqual(CONTEXT_BUDGET_BYTES, 107000)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = self.folder / 'kit.sqlite'

    def test_per_glyph_tj_and_tounicode_join_into_words(self):
        found = kit_pdf.extract(glyph_pdf())
        text = found['text']
        self.assertEqual(found['kind'], 'text', text)
        self.assertIn('The trail runs past the old mill', text)
        self.assertNotIn('T h e', text)
        self.assertNotIn('F o ', text)
        words = re.findall(r"[A-Za-z']+", text)
        singles = [word for word in words if len(word) == 1]
        self.assertLess(len(singles), 3, text)
        self.assertTrue(kit_pdf.text_readable(text), text)
        # The italic face on F2 marks the sentence as read-aloud.
        self.assertIn('> The trail runs', text)

    def test_weak_stdlib_text_falls_back_to_pdftotext(self):
        weak = 'T h e t r a i l r u n s p a s t t h e o l d m i l l a n d t h e r i v e r a n d t h e g a t e.'
        self.assertFalse(kit_pdf.text_readable(weak))
        clean = ('Part 1: The Trail\n\n1. Trailhead\n> Rain wets the trailhead stones.\n'
                 'The path leads to area 2.\n\n2. Bend\n> The bend is quiet.\n')
        path = self.folder / 'weak.pdf'
        path.write_bytes(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n')

        def fake_extract(data):
            return {'text': weak, 'kind': 'text', 'pages': 1, 'text_ops': 40}

        with mock.patch('runtime.kit_pdf.extract', fake_extract):
            with mock.patch('runtime.kit_adventure._pdftotext', return_value=clean):
                text, how = kit_adventure.read_pdf(path, reader='auto')
        self.assertEqual(how, 'pdftotext')
        self.assertIn('Trailhead', text)
        self.assertNotIn('T h e', text)

    def test_letter_spaced_chapter_is_not_a_site_and_part_keys_are_not_bare(self):
        index = kit_adventure.build_index(kit_adventure.prepare_source(TRAIL))
        keys = set(index['locations'])
        self.assertIn('trail-1', keys)
        self.assertIn('trail-2', keys)
        self.assertNotIn('1', keys)
        self.assertNotIn('2', keys)
        self.assertTrue(all(not re.fullmatch(r'\d+', key) for key in keys))
        self.assertFalse(any('llo' in key or key.startswith('f_') for key in keys))
        self.assertNotIn('....', index['title'])
        self.assertIn('Trail', index['title'])
        self.assertEqual(index['start'], 'trail-1')
        titles = [c['title'] for c in index['chapters']]
        self.assertFalse(any('llo' in t for t in titles))
        scout = index['stat_blocks'].get('goblin scout')
        self.assertIsNotNone(scout)
        self.assertEqual(scout['stat_block']['ac'], 13)
        self.assertEqual(scout['stat_block']['hp'], 11)
        self.assertEqual(scout['stat_block']['attacks'][0]['name'], 'scimitar')
        self.assertNotIn('appendix', index['stat_blocks'])
        report = kit_adventure.ingest_adventure(self.db, text=TRAIL)
        self.assertLess(report['ingest_ms'], 5000, report['ingest_ms'])
        self.assertLess(report['first_scene_ms'], 5000)
        room = __import__('json').loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        self.assertIn('trailhead', visible.lower())
        self.assertNotIn('DC 11', visible)
        started = start_session(self.db, NIK, room=report['start_room'])
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        held = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10)).try_prepare('Yes.', one_pass=True)
        self.assertTrue(held.get('committed'))
        self.assertIn('trailhead', held.get('spoken', '').lower())
        self.assertNotIn('The newcomer arrives', held.get('spoken', ''))
        self.assertNotIn('DC 11', held.get('spoken', ''))
        self.assertNotIn('Armor Class', held.get('spoken', ''))

    def test_a_start_with_no_read_aloud_is_refused(self):
        with self.assertRaises(kit_adventure.IngestError) as caught:
            kit_adventure.ingest_adventure(self.folder / 'bare.sqlite', text=BARE)
        self.assertIn('no player-visible read-aloud', ' '.join(caught.exception.problems))

    def test_an_image_stream_is_not_inflated_on_the_way_to_the_text(self):
        data = image_and_text_pdf()
        clock = time.perf_counter()
        found = kit_pdf.extract(data)
        elapsed = time.perf_counter() - clock
        self.assertIn('Image Gate', found['text'])
        self.assertNotEqual(found['kind'], 'no_text_layer')
        self.assertLess(elapsed, 2.0, elapsed)


if __name__ == '__main__':
    unittest.main()
