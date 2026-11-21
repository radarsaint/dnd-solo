"""Adventure PDF readers behind one interface.

Kit does not hand-build PDF layout analysis when a proven library exists. The first
reader is pdfplumber (MIT licence, built on pdfminer.six): it hands back every word with
its position and font, and this module only decides reading order from those positions
(full-width bands in place, a two-column band left column then right column) and marks
italic or boxed prose as read-aloud (``> ``), the same text contract as the stdlib reader.

When pdfplumber is not installed, or fails on a file, the stdlib text-layer reader
(``runtime/kit_pdf.py``) and the host tools in ``kit_adventure`` still run. Nothing here
imports a third-party package at module load.

Extending (co-writer ingest for other book layouts): subclass ``PdfReader``, give it a
``name``, ``available()`` and ``read(path, max_pages)`` returning text (form feed between
pages) or ``None``, then ``register(MyReader(), first=True)``. ``read_with_readers`` tries
registered readers in order and returns the first usable text with the reader's name.
"""
import re
import warnings

from . import kit_pdf

# A word straddling the gutter on this share of lines or fewer still counts as a gutter.
GUTTER_CROSS_MAX = 0.1
# Gutter search window (fraction of page width).
GUTTER_WINDOW = (0.33, 0.67)
# Gap (points) that splits two words. pdfplumber's default (3) glues tightly set words.
X_TOLERANCE = 1.5


class PdfReader(object):
    """One way to turn a PDF into Kit's text contract."""
    name = 'reader'

    def available(self):
        return True

    def read(self, path, max_pages=None):
        raise NotImplementedError


def _plumber():
    """pdfplumber, imported quietly (an old interpreter's deprecation warning from its
    crypto dependency must not reach the host's stderr, which carries JSON)."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        import pdfplumber
    return pdfplumber


def _italic(fontname):
    return bool(re.search(r'italic|oblique', fontname or '', re.I))


def _gutter(chunks, width):
    """x of the column gutter, or None for a single-column page."""
    if len(chunks) < 6:
        return None
    lo, hi = int(width * GUTTER_WINDOW[0]), int(width * GUTTER_WINDOW[1])
    counts = [(x, sum(1 for c in chunks if c['x'] < x < c['x'] + c['w'])) for x in range(lo, hi + 1, 2)]
    if not counts:
        return None
    best_cross = min(n for _x, n in counts)
    # The middle of the widest run of least-crossed x is the gutter, not its ragged edge.
    spans, cur = [], []
    for x, n in counts:
        if n == best_cross:
            cur.append(x)
        elif cur:
            spans.append(cur)
            cur = []
    if cur:
        spans.append(cur)
    widest = max(spans, key=len)
    best = widest[len(widest) // 2]
    lines = kit_pdf._cluster(chunks)
    left = sum(1 for line in lines if any(c['x'] + c['w'] <= best for c in line))
    right = sum(1 for line in lines if any(c['x'] >= best for c in line))
    if left < 3 or right < 3:
        return None
    if best_cross > max(2, GUTTER_CROSS_MAX * len(lines)):
        return None
    return best


def order_page(chunks, width):
    """Lines of one page in reading order.

    A line with a word across the gutter is full width and stays where it is. Between
    full-width lines, the left column is read top to bottom, then the right column.
    """
    gutter = _gutter(chunks, width)
    lines = kit_pdf._cluster(chunks)
    if gutter is None:
        return [kit_pdf._join(line) for line in lines]
    out, left, right = [], [], []

    def flush():
        for group in kit_pdf._cluster(left) + kit_pdf._cluster(right):
            out.append(kit_pdf._join(group))
        del left[:], right[:]

    for line in lines:
        if any(c['x'] < gutter < c['x'] + c['w'] for c in line):
            flush()
            out.append(kit_pdf._join(line))
            continue
        for c in line:
            (left if c['x'] + c['w'] <= gutter else right).append(c)
    flush()
    return [line for line in out if line]


# Words closer than this (times the type size) on one baseline are one run of text.
RUN_GAP = 0.9


def runs(words):
    """Words -> runs: neighbouring words on one baseline joined, so a gutter (a wide gap)
    splits two columns while a full-width line stays one run across the middle."""
    out = []
    for line in kit_pdf._cluster(words):
        line = sorted(line, key=lambda c: c['x'])
        cur = dict(line[0])
        for word in line[1:]:
            gap = word['x'] - (cur['x'] + cur['w'])
            if gap <= max(4.0, cur['size'] * RUN_GAP) and word['italic'] == cur['italic']:
                cur['text'] += ' ' + word['text']
                cur['w'] = word['x'] + word['w'] - cur['x']
            else:
                out.append(cur)
                cur = dict(word)
        out.append(cur)
    return out


class PdfplumberReader(PdfReader):
    name = 'pdfplumber'

    def available(self):
        try:
            _plumber()
        except Exception:
            return False
        return True

    def read(self, path, max_pages=None):
        try:
            pdfplumber = _plumber()
        except Exception:
            return None
        pages = []
        try:
            with pdfplumber.open(str(path)) as pdf:
                for index, page in enumerate(pdf.pages):
                    if max_pages and index >= int(max_pages):
                        break
                    height = float(page.height)
                    chunks = []
                    for word in page.extract_words(x_tolerance=X_TOLERANCE, extra_attrs=['fontname', 'size']):
                        chunks.append({
                            'text': word['text'],
                            'x': float(word['x0']),
                            'w': float(word['x1']) - float(word['x0']),
                            'y': height - float(word['bottom']),
                            'size': float(word.get('size') or 11),
                            'italic': _italic(word.get('fontname')),
                        })
                    rects = []
                    for rect in page.rects:
                        if rect.get('fill'):
                            rects.append((float(rect['x0']), height - float(rect['bottom']),
                                          float(rect['x1']), height - float(rect['top'])))
                    pages.append({'chunks': runs(chunks) if chunks else [], 'rects': rects,
                                  'width': float(page.width), 'height': height})
        except Exception:
            return None
        if not pages:
            return None
        kit_pdf._drop_margins(pages)
        bodies = []
        for page in pages:
            area = page['width'] * page['height']
            for chunk in page['chunks']:
                chunk['boxed'] = kit_pdf._boxed(chunk, page['rects'], area)
            bodies.append('\n'.join(order_page(page['chunks'], page['width'])))
        return '\f'.join(bodies)


READERS = [PdfplumberReader()]


def register(reader, first=False):
    """Add a reader. ``first`` puts it ahead of the others."""
    if first:
        READERS.insert(0, reader)
    else:
        READERS.append(reader)
    return reader


# Bump when a reader's output changes, so prep caches made by the old output are not reused.
READER_REVISION = 1


def cache_tag():
    """Which reader would read a book now, as a cache key part ('pdfplumber-r1', 'stdlib-r1')."""
    names = available_readers()
    return '%s-r%d' % (names[0] if names else 'stdlib', READER_REVISION)


def available_readers():
    return [r.name for r in READERS if r.available()]


def read_with_readers(path, max_pages=None, names=None):
    """``(text, name)`` from the first registered reader that yields usable text, else
    ``(None, None)``. A reader that raises is skipped (the caller's fallback runs)."""
    for reader in READERS:
        if names and reader.name not in names:
            continue
        try:
            if not reader.available():
                continue
            text = reader.read(path, max_pages=max_pages)
        except Exception:
            continue
        if text and kit_pdf.text_usable(text):
            return text, reader.name
    return None, None
