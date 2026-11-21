"""The adventure PDF reader interface (runtime/kit_readers.py).

Synthetic PDFs only: every word here is invented for the test. No book text.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_adventure, kit_agent, kit_readers

try:
    import pdfplumber  # noqa: F401
    HAVE_PLUMBER = True
except Exception:
    HAVE_PLUMBER = False


def _esc(text):
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def make_pdf(pages):
    """pages: list of {'lines': [(x, y, text, font)], 'rects': [(x, y, w, h)]}.

    font is 'R' (Helvetica) or 'I' (Helvetica-Oblique). Uncompressed, classic xref.
    """
    bodies = {1: b'<< /Type /Catalog /Pages 2 0 R >>',
              3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
              4: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>'}
    kids = []
    num = 5
    for page in pages:
        ops = []
        for x, y, w, h in page.get('rects', ()):
            ops.append('0.9 g %s %s %s %s re f 0 g\n' % (x, y, w, h))
        for x, y, text, font in page['lines']:
            ops.append('BT /F%s 10 Tf 1 0 0 1 %s %s Tm (%s) Tj ET\n' % (font, x, y, _esc(text)))
        stream = ''.join(ops).encode('latin-1')
        bodies[num] = (b'<< /Length %d >>\nstream\n' % len(stream)) + stream + b'\nendstream'
        bodies[num + 1] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R '
                           b'/Resources << /Font << /FR 3 0 R /FI 4 0 R >> >> >>' % num)
        kids.append(num + 1)
        num += 2
    bodies[2] = ('<< /Type /Pages /Kids [%s] /Count %d >>' % (
        ' '.join('%d 0 R' % k for k in kids), len(kids))).encode('ascii')
    out = bytearray(b'%PDF-1.4\n')
    offsets = {}
    for n in sorted(bodies):
        offsets[n] = len(out)
        out += ('%d 0 obj\n' % n).encode('ascii') + bodies[n] + b'\nendobj\n'
    xref = len(out)
    size = max(bodies) + 1
    out += ('xref\n0 %d\n0000000000 65535 f \n' % size).encode('ascii')
    for n in range(1, size):
        out += ('%010d 00000 n \n' % offsets[n]).encode('ascii')
    out += ('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, xref)).encode('ascii')
    return bytes(out)


def column(x, top, prefix, count, step=14, font='R'):
    return [(x, top - i * step, '%s line %d of the lane goes on here.' % (prefix, i + 1), font)
            for i in range(count)]


def _write(tmp, pages, name='book.pdf'):
    path = Path(tmp) / name
    path.write_bytes(make_pdf(pages))
    return path


def _order(text, labels):
    return [text.index(label) for label in labels]


@unittest.skipUnless(HAVE_PLUMBER, 'pdfplumber not installed (the stdlib reader is the fallback)')
class LayoutReaderOrder(unittest.TestCase):
    def read(self, pages):
        with tempfile.TemporaryDirectory() as tmp:
            text, name = kit_readers.read_with_readers(_write(tmp, pages))
        self.assertEqual(name, 'pdfplumber')
        return text

    def test_two_columns_on_shared_baselines_read_left_then_right(self):
        lines = column(40, 700, 'Westlane', 12) + column(320, 700, 'Eastlane', 12)
        text = self.read([{'lines': lines}])
        self.assertLess(text.index('Westlane line 12'), text.index('Eastlane line 1 '))
        self.assertNotIn('goes on here. Eastlane', text)  # never spliced across the gutter

    def test_full_width_break_stays_in_place_between_column_bands(self):
        lines = [(40, 720, 'A Synthetic Heading Set Across The Whole Page For Readers To See It First', 'R')]
        lines += column(40, 700, 'Upleft', 6) + column(320, 700, 'Upright', 6)
        lines += [(40, 600, 'This full width sentence crosses the middle gutter of the page and keeps going to the far right edge of it.', 'R')]
        lines += column(40, 570, 'Downleft', 6) + column(320, 570, 'Downright', 6)
        text = self.read([{'lines': lines}])
        order = _order(text, ['A Synthetic Heading', 'Upleft line 6', 'Upright line 1 ',
                              'Upright line 6', 'This full width', 'Downleft line 1 ',
                              'Downleft line 6', 'Downright line 1 '])
        self.assertEqual(order, sorted(order))

    def test_uneven_columns_and_a_single_column_page(self):
        pages = [{'lines': column(40, 700, 'Shortleft', 4) + column(320, 700, 'Longright', 14)},
                 {'lines': column(60, 700, 'Solo', 10)}]
        text = self.read(pages)
        first, second = text.split('\f')
        self.assertLess(first.index('Shortleft line 4'), first.index('Longright line 1 '))
        order = _order(second, ['Solo line %d ' % i for i in range(1, 11)])
        self.assertEqual(order, sorted(order))

    def test_italic_and_boxed_prose_become_read_aloud(self):
        lines = column(40, 700, 'Plainleft', 6) + column(320, 700, 'Plainright', 6)
        lines += [(330, 560, 'You smell rain on warm stone here.', 'I')]
        lines += [(50, 520, 'A lantern swings above the quiet door.', 'R')]
        text = self.read([{'lines': lines, 'rects': [(44, 512, 220, 22)]}])
        self.assertIn('> You smell rain on warm stone here.', text)
        self.assertIn('> A lantern swings above the quiet door.', text)
        self.assertNotIn('> Plainleft', text)

    def test_read_pdf_uses_the_layout_reader_and_stdlib_on_request(self):
        lines = column(40, 700, 'Westlane', 12) + column(320, 700, 'Eastlane', 12)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, [{'lines': lines}])
            _text, name = kit_adventure.read_pdf(path)
            self.assertEqual(name, 'pdfplumber')
            _text, name = kit_adventure.read_pdf(path, reader='stdlib')
            self.assertEqual(name, 'stdlib')
            _text, name = kit_adventure.read_opening(path)
            self.assertEqual(name, 'pdfplumber')


class FallbackAndExtension(unittest.TestCase):
    def pages(self):
        return [{'lines': column(40, 700, 'Westlane', 12) + column(320, 700, 'Eastlane', 12)}]

    def test_missing_library_falls_back_to_the_stdlib_reader(self):
        with mock.patch.object(kit_readers.PdfplumberReader, 'available', return_value=False), \
                tempfile.TemporaryDirectory() as tmp:
            text, name = kit_adventure.read_pdf(_write(tmp, self.pages()), reader='stdlib')
            self.assertEqual(name, 'stdlib')
            self.assertIn('Westlane line 1 ', text)
            self.assertEqual(kit_readers.read_with_readers(Path(tmp) / 'book.pdf'), (None, None))
            self.assertTrue(kit_readers.cache_tag().startswith('stdlib-r'))

    def test_a_reader_that_raises_is_skipped(self):
        class Broken(kit_readers.PdfReader):
            name = 'broken'

            def read(self, path, max_pages=None):
                raise RuntimeError('cannot parse')

        with mock.patch.object(kit_readers, 'READERS', [Broken()]), tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(kit_readers.read_with_readers(_write(tmp, self.pages())), (None, None))
            _text, name = kit_adventure.read_pdf(Path(tmp) / 'book.pdf')
            self.assertNotEqual(name, 'broken')

    def test_registered_reader_runs_first_and_is_nameable(self):
        class Fixed(kit_readers.PdfReader):
            name = 'fixed'

            def read(self, path, max_pages=None):
                return 'A Room\nThe fixed reader returns these plain words for the test.\n' * 4

        with mock.patch.object(kit_readers, 'READERS', list(kit_readers.READERS)):
            kit_readers.register(Fixed(), first=True)
            self.assertEqual(kit_readers.available_readers()[0], 'fixed')
            with tempfile.TemporaryDirectory() as tmp:
                path = _write(tmp, self.pages())
                self.assertEqual(kit_adventure.read_pdf(path)[1], 'fixed')
                self.assertEqual(kit_adventure.read_pdf(path, reader='fixed')[1], 'fixed')


class ScanIsALook(unittest.TestCase):
    def test_scanning_for_watchers_is_a_look_not_talk(self):
        for line in ('I scan the thickets for anyone watching.',
                     'I look over the brush for anyone watching us.',
                     'I keep an eye out for anyone hiding.',
                     'I peer into the trees for signs of an ambush.'):
            self.assertEqual(kit_agent.room_intent(line), 'observe', line)

    def test_talk_stays_talk(self):
        for line in ('I ask the guard about the road.', 'I watch the dealer.'):
            self.assertEqual(kit_agent.room_intent(line), 'social', line)


if __name__ == '__main__':
    unittest.main()
