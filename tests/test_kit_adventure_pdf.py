"""PDF adventure ingest: stdlib text layer -> index -> first scene (runtime/kit_pdf.py).

Corpus is original synthetic text generated in this file. No published adventure is read
or committed. Layout coordinates are pinned (SEED); there is no RNG.

The PDF is written in stream order top-to-bottom, left column then right column on each
baseline, which is the mess a position-blind reader interleaves. The reader must put the
left column ahead of the right, mark boxed lines as read-aloud, drop the running header
and page numbers, keep the stat block and the keyed rooms (A1, 12, Area 3), and refuse a
PDF that has no text layer.
"""
import json
import subprocess
import sys
import tempfile
import unittest
import warnings
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_lifecycle, kit_pdf  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import CONTEXT_BUDGET_BYTES, Runtime  # noqa: E402

# Pinned. Every coordinate below is fixed; do not draw from an unseeded RNG.
SEED = 20261028
NIK = ROOT / 'tests/fixtures/characters/nik.json'

PASTED = (
    'Chapter 1: Pasted Post\n\n'
    'This short adventure is original synthetic test text written for Kit. '
    'It is not from any published book.\n\n'
    '1. Pasted Post\n'
    '> A chalk mark points down a lane.\n'
    'The lane runs to area 2.\n'
    'A loose stone hides a DC 9 Dexterity check.\n\n'
    '2. Pasted Shed\n'
    '> The shed smells of wet rope.\n'
    'The lane back leads to area 1.\n'
)


def _escape(text):
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


class _Pdf(object):
    def __init__(self):
        self.bodies = []

    def add(self, body):
        self.bodies.append(body)
        return len(self.bodies)

    def save(self):
        out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = [0]
        for i, body in enumerate(self.bodies, 1):
            offsets.append(len(out))
            out += ('%d 0 obj\n' % i).encode('ascii') + body + b'\nendobj\n'
        xref = len(out)
        out += ('xref\n0 %d\n' % (len(self.bodies) + 1)).encode('ascii')
        out += b'0000000000 65535 f \n'
        for off in offsets[1:]:
            out += ('%010d 00000 n \n' % off).encode('ascii')
        out += ('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%EOF\n'
                % (len(self.bodies) + 1, xref)).encode('ascii')
        return bytes(out)


def _stream(content, compress):
    raw = zlib.compress(content) if compress else content
    filt = '/Filter /FlateDecode ' if compress else ''
    return ('<< %s/Length %d >>\nstream\n' % (filt, len(raw))).encode('ascii') + raw + b'\nendstream'


def _text_ops(ops):
    parts = []
    for op in ops:
        if op[0] == 'rect':
            _, x, y, w, h = op
            parts.append('%s %s %s %s re 0.93 0.90 0.82 rg f\n' % (x, y, w, h))
    texts = [op for op in ops if op[0] == 'text']
    # Stream order is by baseline, left then right: a position-blind reader interleaves columns.
    texts.sort(key=lambda op: (-op[2], op[1], op[3]))
    for _, x, y, text, size in texts:
        parts.append('BT /F1 %s Tf 1 0 0 1 %s %s Tm (%s) Tj ET\n' % (size, x, y, _escape(text)))
    return ''.join(parts).encode('latin-1')


def make_pdf(pages, compress=True):
    """pages: list of op lists. Object 1 is the catalog."""
    doc = _Pdf()
    font_id = 3
    next_id = 4
    content_ids, page_ids = [], []
    for _ in pages:
        content_ids.append(next_id)
        page_ids.append(next_id + 1)
        next_id += 2
    bodies = {i: None for i in range(1, next_id)}
    kids = ' '.join('%d 0 R' % i for i in page_ids)
    bodies[1] = b'<< /Type /Catalog /Pages 2 0 R >>'
    bodies[2] = ('<< /Type /Pages /Kids [%s] /Count %d >>' % (kids, len(pages))).encode('ascii')
    bodies[3] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
    for content_id, page_id, ops in zip(content_ids, page_ids, pages):
        bodies[content_id] = _stream(_text_ops(ops), compress)
        bodies[page_id] = (
            '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R '
            '/Resources << /Font << /F1 %d 0 R >> >> >>' % (content_id, font_id)
        ).encode('ascii')
    for i in range(1, next_id):
        doc.add(bodies[i])
    return doc.save()


def cinder_keep_pages():
    """The Cinder Keep, three pages. Original. Coordinates are the pinned layout."""
    assert SEED == 20261028
    left, right = 48, 330
    page1 = [
        ('text', left, 768, 'THE CINDER KEEP', 11),
        ('text', 300, 28, '1', 10),
        ('text', left, 720, 'Chapter 1: The Gate Road', 13),
        ('text', left, 704, 'This page is original synthetic test text written for Kit and is not from any published book.', 9),
        ('text', left, 690, 'A1. Gatehouse', 12),
        ('rect', 40, 656, 250, 28),
        ('text', left, 668, 'Torches spit along a blackened arch. A cracked bell hangs over the gate.', 11),
        ('text', left, 636, 'The road through the arch leads to area 12.', 11),
        ('text', left, 616, 'Mira Quell, a tired gate clerk, will not open the book after dusk.', 11),
        ('text', left, 596, 'The bell chain is trapped; a DC 14 Dexterity check frees it.', 11),
        ('text', right, 690, '12. Ash Court', 12),
        ('rect', 318, 656, 260, 28),
        ('text', right, 668, 'Cinders drift across cracked flagstones. A well stands in the middle of the court.', 11),
        ('text', right, 636, 'Two bandits crouch behind the well and attack anyone who touches the well.', 11),
        ('text', right, 616, 'The archway back leads to area A1.', 11),
        ('text', right, 596, 'A hidden stair in the well drops to area 3.', 11),
        ('text', right, 572, 'Finds', 11),
        ('text', right, 552, 'cinder glass', 11),
        ('text', 470, 552, '5 gp', 11),
        ('text', right, 532, 'iron spike', 11),
        ('text', 470, 532, '1 gp', 11),
    ]
    page2 = [
        ('text', left, 768, 'THE CINDER KEEP', 11),
        ('text', 300, 28, '2', 10),
        ('text', left, 720, 'Chapter 2: Under the Court', 13),
        ('text', left, 690, 'Area 3: Well Shaft', 12),
        ('rect', 40, 656, 250, 28),
        ('text', left, 668, 'The shaft drops into cold dark. Rungs glisten with damp.', 11),
        ('text', left, 636, 'A cinder wretch (see the Cinder Wretch stat block) clings to the rungs.', 11),
        ('text', left, 616, 'The ladder climbs back to area 12.', 11),
        ('text', right, 720, 'Appendix: Creatures', 13),
        ('text', right, 690, 'Cinder Wretch', 12),
        ('text', right, 674, 'Medium undead', 11),
        ('text', right, 658, 'Armor Class 14', 11),
        ('text', right, 642, 'Hit Points 22 (5d8)', 11),
        ('text', right, 626, 'Speed 20 ft.', 11),
        ('text', right, 600, 'Claw. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 6 (1d6 + 3) fire damage.', 9),
    ]
    page3 = [
        ('text', left, 768, 'THE CINDER KEEP', 11),
        ('text', 300, 28, '3', 10),
        ('rect', 36, 80, 540, 640),  # a page-sized frame must not mark the map line as read-aloud
        ('text', left, 400, 'MAP: Cinder Keep', 12),
    ]
    return [page1, page2, page3]


def no_text_layer_pdf():
    return make_pdf([[('rect', 80, 80, 200, 200)]])


def poor_encoding_pdf():
    ops = [('text', 72, 700 - 16 * i, '@@@@ #### $$$$ %%%% ~~~~', 12) for i in range(8)]
    return make_pdf([ops])


def glyph_pdf():
    """Identity-H font whose glyph ids are NOT the Unicode code points. ToUnicode is required."""
    lines = [
        (72, 700, '1. Glyph Yard'),
        (72, 676, 'A blue post stands in the yard and the lane leads to area 2.'),
        (72, 640, '2. Glyph Shed'),
        (72, 616, 'The lane back leads to area 1.'),
    ]
    chars = []
    for _, _, text in lines:
        for ch in text:
            if ch not in chars:
                chars.append(ch)
    mapping = {ch: i + 1 for i, ch in enumerate(chars)}
    bfchar = '\n'.join('<%04X> <%04X>' % (gid, ord(ch)) for ch, gid in mapping.items())
    cmap = ('begincmap\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n'
            '%d beginbfchar\n%s\nendbfchar\nendcmap\n' % (len(mapping), bfchar)).encode('ascii')
    content = []
    for x, y, text in lines:
        hexstr = ''.join('%04X' % mapping[ch] for ch in text)
        content.append('BT /F1 12 Tf 1 0 0 1 %s %s Tm <%s> Tj ET\n' % (x, y, hexstr))
    content = ''.join(content).encode('ascii')
    doc = _Pdf()
    # 1 catalog, 2 pages, 3 font, 4 tounicode, 5 content, 6 page
    doc.add(b'<< /Type /Catalog /Pages 2 0 R >>')
    doc.add(b'<< /Type /Pages /Kids [6 0 R] /Count 1 >>')
    doc.add(b'<< /Type /Font /Subtype /Type0 /BaseFont /GlyphFont /Encoding /Identity-H /ToUnicode 4 0 R >>')
    doc.add(_stream(cmap, compress=False))
    doc.add(_stream(content, compress=True))
    doc.add(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R '
            b'/Resources << /Font << /F1 3 0 R >> >> >>')
    return doc.save()


class PdfCase(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        self.assertEqual(SEED, 20261028)
        self.assertEqual(CONTEXT_BUDGET_BYTES, 107000)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.pdf_path = self.folder / 'cinder-keep.pdf'
        self.pdf_path.write_bytes(make_pdf(cinder_keep_pages()))
        self.db = self.folder / 'kit.sqlite'

    def extract(self):
        found = kit_pdf.extract(self.pdf_path.read_bytes())
        self.assertEqual(found['kind'], 'text', found['text'][:400])
        return found['text']


class Layout(PdfCase):
    def test_two_columns_read_left_then_right_and_boxes_are_read_aloud(self):
        text = self.extract()
        self.assertIn('original synthetic test text', text)
        self.assertNotIn('THE CINDER KEEP', text)
        self.assertNotRegex(text, r'(?m)^[123]$')
        self.assertIn('> Torches spit along a blackened arch. A cracked bell hangs over the gate.', text)
        self.assertIn('> Cinders drift across cracked flagstones.', text)
        self.assertLess(text.index('A1. Gatehouse'), text.index('blackened arch'))
        self.assertLess(text.index('blackened arch'), text.index('12. Ash Court'))
        self.assertLess(text.index('12. Ash Court'), text.index('Chapter 2: Under the Court'))
        self.assertLess(text.index('Area 3: Well Shaft'), text.index('Appendix: Creatures'))
        self.assertLess(text.index('Appendix: Creatures'), text.index('Armor Class 14'))
        row = next(line for line in text.split('\n') if 'cinder glass' in line)
        self.assertIn('5 gp', row)
        pages = text.split('\f')
        self.assertEqual(len(pages), 3)
        self.assertIn('MAP: Cinder Keep', pages[2])
        self.assertNotIn('> MAP', pages[2])

    def test_index_keys_chapters_stat_block_and_map_page(self):
        text = self.extract()
        kit_adventure.import_adventure(self.db, text=text, title='The Cinder Keep')
        index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        self.assertEqual(list(index['locations']), ['A1', '12', '3'])
        self.assertEqual(index['locations']['A1']['name'], 'Gatehouse')
        self.assertEqual(index['locations']['12']['name'], 'Ash Court')
        self.assertEqual(index['locations']['3']['name'], 'Well Shaft')
        self.assertEqual(index['locations']['A1']['page'], 1)
        self.assertEqual(index['locations']['12']['page'], 1)
        self.assertEqual(index['locations']['3']['page'], 2)
        self.assertEqual(len(index['chapters']), 3)
        self.assertIn('Mira Quell', index['npcs'])
        self.assertIn('cinder wretch', index['stat_blocks'])
        self.assertEqual(index['map_pages'], [3])
        links = {k: {c['to']: c['secret'] for c in v['connections']} for k, v in index['locations'].items()}
        self.assertEqual(links['A1'].get('12'), False)
        self.assertEqual(links['12'].get('3'), True)
        self.assertIn('A1', links['12'])
        how = {c['name']: c['resolved'] for c in index['locations']['3']['creatures']}
        self.assertEqual(how.get('cinder wretch'), 'in_book')
        how = {c['name']: c['resolved'] for c in index['locations']['12']['creatures']}
        self.assertEqual(how.get('bandit'), 'srd')
        span = text[index['locations']['A1']['body'][0]:index['locations']['A1']['body'][1]]
        self.assertIn('blackened arch', span)
        self.assertNotIn('flagstones', span)
        self.assertNotIn('THE CINDER KEEP', span)
        self.assertNotIn('Armor Class', span)

    def test_glyph_ids_need_tounicode(self):
        found = kit_pdf.extract(glyph_pdf())
        self.assertEqual(found['kind'], 'text', found['text'])
        self.assertIn('1. Glyph Yard', found['text'])
        self.assertIn('2. Glyph Shed', found['text'])
        self.assertNotIn('\x00', found['text'])

    def test_no_text_layer_is_refused_and_not_called_a_bad_encoding(self):
        path = self.folder / 'scan.pdf'
        path.write_bytes(no_text_layer_pdf())
        found = kit_pdf.extract(path.read_bytes())
        self.assertEqual(found['kind'], 'no_text_layer')
        with mock.patch('runtime.kit_adventure.optional_pdf_text', return_value=(None, None)):
            with self.assertRaises(kit_adventure.IngestError) as caught:
                kit_adventure.ingest_adventure(self.db, pdf=path, reader='auto')
        problem = ' '.join(caught.exception.problems)
        self.assertIn('no text layer', problem)
        self.assertIn('--text-file', problem)
        self.assertNotIn('could not read', problem)

    def test_poor_encoding_names_the_text_layer_and_can_fall_back(self):
        path = self.folder / 'poor.pdf'
        path.write_bytes(poor_encoding_pdf())
        self.assertEqual(kit_pdf.extract(path.read_bytes())['kind'], 'poor')
        with mock.patch('runtime.kit_adventure.optional_pdf_text', return_value=(None, None)):
            with self.assertRaises(kit_adventure.IngestError) as caught:
                kit_adventure.read_pdf(path, reader='auto')
        problem = ' '.join(caught.exception.problems)
        self.assertIn('has a text layer', problem)
        self.assertNotIn('no text layer', problem)
        self.assertIn('pdftotext', problem)

        def fake(path, reader='auto'):
            return PASTED, 'pdftotext'

        with mock.patch('runtime.kit_adventure.optional_pdf_text', fake):
            report = kit_adventure.ingest_adventure(self.folder / 'fallback.sqlite', pdf=path, reader='auto')
        self.assertEqual(report['reader'], 'pdftotext')
        self.assertEqual(report['start_location'], '1')
        self.assertGreater(report['first_scene_bytes'], 0)

    def test_not_a_pdf(self):
        path = self.folder / 'notes.txt'
        path.write_text('1. Not a pdf\n', encoding='utf-8')
        with self.assertRaises(kit_adventure.IngestError) as caught:
            kit_adventure.read_pdf(path, reader='stdlib')
        self.assertIn('not a PDF', ' '.join(caught.exception.problems))


class Ingest(PdfCase):
    def test_one_step_compiles_only_the_first_scene_with_timings(self):
        def boom(*args, **kwargs):
            raise AssertionError('optional reader must not run when the text layer reads')

        with mock.patch('runtime.kit_adventure.optional_pdf_text', boom):
            report = kit_adventure.ingest_adventure(
                self.db, pdf=self.pdf_path, title='The Cinder Keep', reader='stdlib')
        self.assertEqual(report['stage'], 'adventure_ingested')
        self.assertEqual(report['reader'], 'stdlib')
        self.assertEqual(report['title'], 'The Cinder Keep')
        self.assertEqual(report['start_location'], 'A1')
        self.assertEqual(report['locations'], 3)
        self.assertEqual(report['first_scene_page'], 1)
        self.assertEqual(report['adventure_readiness'], 'location_executable')
        self.assertIsInstance(report['ingest_ms'], float)
        self.assertIsInstance(report['first_scene_ms'], float)
        self.assertGreaterEqual(report['ingest_ms'], 0)
        self.assertGreaterEqual(report['first_scene_ms'], 0)
        self.assertLess(report['ingest_ms'], 5000, report)
        self.assertLess(report['first_scene_ms'], 5000, report)
        self.assertGreater(report['source_bytes'], 400)
        self.assertGreater(report['index_bytes'], 100)
        self.assertGreater(report['first_scene_bytes'], 200)
        self.assertLess(report['first_scene_bytes'], 30000)
        self.assertEqual(report['first_scene_bytes'], Path(report['start_room']).stat().st_size)
        self.assertFalse(kit_adventure.room_file(self.db, '12').is_file())
        self.assertFalse(kit_adventure.room_file(self.db, '3').is_file())
        self.assertEqual(kit_lifecycle.status(self.db)['next_command'], report['next_command'])
        self.assertIn('--room', report['next_command'])
        self.assertIn('--sheet', report['next_command'])
        self.assertNotIn('adventure compile', report['next_command'])

        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        side = json.loads(Path(report['start_room']).with_suffix('.provenance.json').read_text(encoding='utf-8'))
        source = (kit_adventure.folder_for(self.db) / 'source.txt').read_text(encoding='utf-8')
        self.assertIn('(p. 1)', room['source_ref'])
        self.assertEqual(side['page'], 1)
        self.assertEqual(side['scene_bytes'], report['first_scene_bytes'])
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        hidden = ' '.join(f['text'] for f in room['facts'].values() if not f['visible'])
        self.assertIn('blackened arch', visible)
        self.assertNotIn('DC 14', visible)
        self.assertNotIn('Mira', visible)
        self.assertNotIn('Armor Class', visible)
        self.assertNotIn('flagstones', visible)
        self.assertIn('DC 14', hidden)
        self.assertNotIn('cold dark', visible + hidden)
        self.assertNotIn('Cinder Wretch', json.dumps(room))
        for key in room['facts']:
            entry = side['fields']['facts.%s' % key]
            self.assertEqual(source[entry['offset']:entry['offset'] + len(entry['quote'])], entry['quote'])

    def test_stat_block_stays_off_the_player_page(self):
        kit_adventure.ingest_adventure(self.db, pdf=self.pdf_path, title='The Cinder Keep', reader='stdlib')
        out = kit_adventure.compile_location(self.db, '3', neighbours=False)
        self.assertEqual(out['page'], 2)
        path = kit_adventure.room_file(self.db, '3')
        room = json.loads(path.read_text(encoding='utf-8'))
        side = json.loads(path.with_suffix('.provenance.json').read_text(encoding='utf-8'))
        self.assertEqual(room['actors']['cinder_wretch']['stat_block'],
                         {'ac': 14, 'hp': 22, 'attacks': [{'name': 'claw', 'to_hit': 4, 'damage': 6, 'type': 'fire'}]})
        self.assertEqual(room['actors']['cinder_wretch']['visible'], False)
        self.assertEqual(side['fields']['actors.cinder_wretch.stat_block.ac']['quote'], 'Armor Class 14')
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        self.assertIn('cold dark', visible)
        self.assertNotIn('cinder', visible.lower())
        self.assertNotIn('Armor Class', visible)
        self.assertNotIn('+4', visible)
        self.assertTrue(room['exits']['way_12']['secret'] is False)
        kit_adventure.compile_location(self.db, '12', neighbours=False)
        court = json.loads(kit_adventure.room_file(self.db, '12').read_text(encoding='utf-8'))
        self.assertTrue(court['exits']['way_3']['secret'])
        self.assertEqual(sorted(court['actors']), ['bandit_1', 'bandit_2'])
        self.assertTrue(all(not actor['visible'] for actor in court['actors'].values()))
        shown = ' '.join(f['text'] for f in court['facts'].values() if f['visible'])
        self.assertNotIn('bandit', shown.lower())
        self.assertNotIn('5 gp', shown)
        self.assertNotIn('hidden stair', shown.lower())

    def test_pasted_text_is_the_same_one_step(self):
        report = kit_adventure.ingest_adventure(self.db, text=PASTED, title='Pasted Post')
        self.assertEqual(report['reader'], 'text')
        self.assertEqual(report['start_location'], '1')
        room = json.loads(Path(report['start_room']).read_text(encoding='utf-8'))
        visible = ' '.join(f['text'] for f in room['facts'].values() if f['visible'])
        hidden = ' '.join(f['text'] for f in room['facts'].values() if not f['visible'])
        self.assertIn('chalk mark', visible)
        self.assertNotIn('DC 9', visible)
        self.assertIn('DC 9', hidden)

    def test_cli_ingest_then_begin_command(self):
        run = lambda *args: subprocess.run(  # noqa: E731
            [sys.executable, '-m', 'runtime.kit_agent', *args], cwd=ROOT, capture_output=True, text=True)
        out = json.loads(run('ingest', str(self.pdf_path), '--db', str(self.db),
                             '--title', 'The Cinder Keep', '--reader', 'stdlib').stdout)
        self.assertEqual(out['stage'], 'adventure_ingested')
        self.assertEqual(out['reader'], 'stdlib')
        self.assertIn('start', out['next_command'])
        status = json.loads(run('status', '--db', str(self.db)).stdout)
        self.assertEqual(status['next_command'], out['next_command'])
        scan = self.folder / 'scan.pdf'
        scan.write_bytes(no_text_layer_pdf())
        bad = run('ingest', str(scan), '--db', str(self.folder / 'scan.sqlite'))
        self.assertEqual(bad.returncode, 2)
        self.assertIn('no text layer', ' '.join(json.loads(bad.stderr)['problems']))


class Play(PdfCase):
    """Begin on the compiled gatehouse. The Ash Court is not a file until the PC goes there."""

    def test_begin_hides_the_dc_and_the_next_scene_compiles_on_arrival(self):
        report = kit_adventure.ingest_adventure(
            self.db, pdf=self.pdf_path, title='The Cinder Keep', reader='stdlib')
        self.assertFalse(kit_adventure.room_file(self.db, '12').is_file())
        started = start_session(self.db, NIK, room=report['start_room'])
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        view = json.dumps(runtime.player_view())
        self.assertIn('blackened arch', view)
        for secret in ('DC 14', 'Mira', 'Armor Class', 'to_hit', 'cinder', 'bandit', '5 gp'):
            self.assertNotIn(secret.lower(), view.lower(), secret)
        packet = json.loads(json.dumps(started))
        packet['prepared']['input']['private'].pop('dm_context', None)
        public = json.dumps(packet)
        for secret in ('DC 14', 'Armor Class', 'to_hit', '"ac"'):
            self.assertNotIn(secret, public)

        adjudicator = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10)
        bridge = KitChatBridge(runtime, adjudicator)
        if not started.get('committed'):
            bridge.abandon(started['prepared']['turn_id'])
        sha = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text())['sha256'][:8]

        def step(line):
            revision, _ = runtime.load()
            packet = bridge.prepare(line, one_pass=True)
            body = runtime.pending_kit_turn(packet['turn_id'])['body']
            bridge.abandon(packet['turn_id'])
            runtime.commit(packet['turn_id'], revision, body['events'])
            return runtime.source()['id'], runtime.load()[1]['area']

        clock = __import__('time').perf_counter()
        self.assertEqual(step('I go to the Ash Court.'), ('adv-%s-12' % sha, 'to_a1'))
        jit_ms = (__import__('time').perf_counter() - clock) * 1000
        self.assertLess(jit_ms, 5000)
        self.assertTrue(kit_adventure.room_file(self.db, '12').is_file())
        side = json.loads(kit_adventure.room_file(self.db, '12').with_suffix('.provenance.json').read_text())
        self.assertEqual(side['compiled_by'], 'deterministic')
        self.assertEqual(side['page'], 1)
        self.assertGreaterEqual(side['scene_ms'], 0)
        self.assertLess(side['scene_ms'], 5000)
        source = (kit_adventure.folder_for(self.db) / 'source.txt').read_text(encoding='utf-8')
        named = side['fields']['areas.here.name']
        self.assertIn(named['quote'], source[named['offset']:].split('\n')[0])
        seen = next(key for key, fact in json.loads(
            kit_adventure.room_file(self.db, '12').read_text())['facts'].items() if fact['visible'])
        entry = side['fields']['facts.%s' % seen]
        self.assertEqual(source[entry['offset']:entry['offset'] + len(entry['quote'])], entry['quote'])
        self.assertEqual(step('I go into the Ash Court.'), ('adv-%s-12' % sha, 'here'))
        arrived = json.dumps(runtime.player_view()).lower()
        self.assertIn('flagstones', arrived)
        for secret in ('bandit', 'dc 14', 'armor class', '5 gp', 'hidden stair', 'to_hit'):
            self.assertNotIn(secret, arrived)
        # The stair is a secret exit: it is not a way the PC can take by naming it.
        self.assertEqual(step('I take the way to the Well Shaft.'), ('adv-%s-12' % sha, 'here'))


if __name__ == '__main__':
    unittest.main()
