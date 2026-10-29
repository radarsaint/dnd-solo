"""Stdlib PDF text-layer reader for adventure ingest (runtime/kit_adventure.py).

Reads a PDF's text operators with positions, so a two-column page comes back in reading
order, a vector box becomes a read-aloud line (``> ``), and running headers, footers and
page numbers drop out. FlateDecode streams, WinAnsi/Latin-1 text, UTF-16 hex strings, and
a font's ToUnicode CMap (bfchar / bfrange) are handled. No third-party imports.

A page with no text-showing operators is ``no_text_layer`` (scanned or image-only). Text
that decodes to almost no letters is ``poor`` (custom encoding this reader cannot map).
Neither path invents words.
"""
import re
import zlib

# A line this close in y (points) is the same baseline. Pinned: synthetic pages use 11 pt type.
LINE_Y = 3.5
# Gap between x-buckets (points) that separates two columns. Wider than a word space.
COLUMN_GAP = 40
# A painted rectangle covering more of the page than this is a frame, not a read-aloud box.
BOX_MAX_AREA = 0.35
# Top and bottom bands (fraction of page height) where running matter lives.
MARGIN = 0.07

_HEADING = re.compile(r'^(?:chapter|part|appendix)\b|^(?:area\s+)?[A-Z]?\d{1,3}[a-z]?\s*[.:]\s+\S', re.I)
_PAGE_NO = re.compile(r'(?:page\s+)?\d{1,4}\Z', re.I)


class Ref(object):
    def __init__(self, num, gen):
        self.num = num
        self.gen = gen

    def __repr__(self):
        return 'Ref(%s, %s)' % (self.num, self.gen)


def text_usable(text):
    """True when extracted text is real words, not an empty page or a garbled encoding.

    ``pdftotext -layout`` pads lines with spaces. The ratio is letters over non-space
    characters, so that padding does not make a readable page look empty.
    """
    raw = text or ''
    letters = sum(ch.isalpha() for ch in raw)
    body = sum(1 for ch in raw if not ch.isspace())
    return letters >= 40 and letters / max(body, 1) > 0.5


def text_readable(text):
    """False when glyphs were emitted one letter at a time ('T h e', 'F o llo wi n').

    A short page is not judged. A page of real words has few single-letter tokens.
    """
    words = re.findall(r"[A-Za-z']+", text or '')
    if len(words) < 12:
        return True
    singles = sum(1 for word in words if len(word) == 1)
    mean = sum(len(word) for word in words) / float(len(words))
    return singles / float(len(words)) < 0.22 and mean >= 2.8


def extract(data):
    """``{text, kind, pages, text_ops}``. ``kind`` is text, poor, no_text_layer, or not_pdf.

    ``text`` is UTF-8-able str with a form feed between pages. Boxed lines and italic prose
    start with ``> ``. A file that contains text operators is never ``no_text_layer``.
    """
    if not isinstance(data, (bytes, bytearray)) or not bytes(data).startswith(b'%PDF'):
        return {'text': '', 'kind': 'not_pdf', 'pages': 0, 'text_ops': 0}
    data = bytes(data)
    objects, root = _load_documents(data)
    catalog = root if isinstance(root, dict) and root.get('/Type') == '/Catalog' else None
    if catalog is None:
        catalog = next((obj for obj in objects.values()
                        if isinstance(obj, dict) and obj.get('/Type') == '/Catalog'), None)
    if catalog is None:
        seen = _text_ops_in(objects)
        kind = 'poor' if seen else 'no_text_layer'
        return {'text': '', 'kind': kind, 'pages': 0, 'text_ops': seen}
    pages, text_ops = [], 0
    for node in _walk_pages(_resolve(catalog.get('/Pages'), objects), objects):
        chunks, rects, ops, width, height = _read_page(node, objects)
        text_ops += ops
        pages.append({'chunks': chunks, 'rects': rects, 'width': width, 'height': height})
    if text_ops <= 0:
        seen = _text_ops_in(objects)
        kind = 'poor' if seen else 'no_text_layer'
        return {'text': '', 'kind': kind, 'pages': len(pages), 'text_ops': seen}
    text = _layout(pages)
    return {'text': text, 'kind': 'text' if text_usable(text) else 'poor',
            'pages': len(pages), 'text_ops': text_ops}


# ---------------------------------------------------------------- objects

def _skip(data, i):
    n = len(data)
    while i < n:
        c = data[i]
        if c in b' \t\r\n\f\0':
            i += 1
        elif c == 37:  # %
            i = data.find(b'\n', i)
            i = n if i < 0 else i + 1
        else:
            break
    return i


def _parse_literal(data, i):
    i += 1
    out = bytearray()
    depth = 1
    while i < len(data) and depth:
        c = data[i]
        if c == 92:  # backslash
            i += 1
            if i >= len(data):
                break
            e = data[i]
            mapped = {ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('b'): 8, ord('f'): 12,
                      ord('('): 40, ord(')'): 41, ord('\\'): 92}
            if e in mapped:
                out.append(mapped[e])
                i += 1
            elif e in (10, 13):
                i += 1
                if e == 13 and i < len(data) and data[i] == 10:
                    i += 1
            elif e in b'01234567':
                octal = bytearray((e,))
                i += 1
                for _ in range(2):
                    if i < len(data) and data[i] in b'01234567':
                        octal.append(data[i])
                        i += 1
                    else:
                        break
                out.append(int(bytes(octal), 8) & 255)
            else:
                out.append(e)
                i += 1
        elif c == 40:  # (
            depth += 1
            out.append(c)
            i += 1
        elif c == 41:  # )
            depth -= 1
            if depth:
                out.append(c)
            i += 1
        else:
            out.append(c)
            i += 1
    return bytes(out), i


def _parse_hex(data, i):
    i += 1
    chars = []
    while i < len(data) and data[i] != 62:  # >
        if data[i] not in b' \t\r\n\f':
            chars.append(chr(data[i]))
        i += 1
    if i < len(data):
        i += 1
    hexstr = ''.join(chars)
    if len(hexstr) % 2:
        hexstr += '0'
    try:
        return bytes.fromhex(hexstr), i
    except ValueError:
        return b'', i


def _parse_name(data, i):
    i += 1
    start = i
    while i < len(data) and data[i] not in b' \t\r\n\f\0()<>[]{}/%':
        i += 1
    raw = data[start:i]
    name = re.sub(br'#([0-9A-Fa-f]{2})', lambda m: bytes([int(m.group(1), 16)]), raw)
    return '/' + name.decode('latin-1'), i


def _parse_number(data, i):
    match = re.match(br'[+-]?(?:\d+\.\d*|\.\d+|\d+)', data[i:])
    if not match:
        raise ValueError('number')
    token = match.group(0)
    i += len(token)
    if b'.' in token:
        return float(token), i
    return int(token), i


def _parse_value(data, i):
    i = _skip(data, i)
    if i >= len(data):
        raise ValueError('eof')
    c = data[i]
    if data.startswith(b'<<', i):
        return _parse_dict(data, i)
    if c == 91:  # [
        return _parse_array(data, i)
    if c == 40:  # (
        return _parse_literal(data, i)
    if c == 60:  # <
        return _parse_hex(data, i)
    if c == 47:  # /
        return _parse_name(data, i)
    if data.startswith(b'true', i):
        return True, i + 4
    if data.startswith(b'false', i):
        return False, i + 5
    if data.startswith(b'null', i):
        return None, i + 4
    if c in b'+-.0123456789':
        num, i = _parse_number(data, i)
        j = _skip(data, i)
        match = re.match(br'(\d+)\s+R\b', data[j:])
        if isinstance(num, int) and match:
            return Ref(num, int(match.group(1))), j + match.end()
        return num, i
    raise ValueError('bad token at %s' % i)


def _parse_dict(data, i):
    i += 2
    out = {}
    while True:
        i = _skip(data, i)
        if data.startswith(b'>>', i):
            return out, i + 2
        if i >= len(data) or data[i] != 47:
            raise ValueError('dict key')
        name, i = _parse_name(data, i)
        val, i = _parse_value(data, i)
        out[name] = val


def _parse_array(data, i):
    i += 1
    out = []
    while True:
        i = _skip(data, i)
        if i < len(data) and data[i] == 93:  # ]
            return out, i + 1
        val, i = _parse_value(data, i)
        out.append(val)


def _decode_stream(raw, filt):
    filters = [filt] if isinstance(filt, str) else list(filt or [])
    for name in filters:
        if name == '/FlateDecode':
            raw = _inflate(raw)
        elif name == '/ASCIIHexDecode':
            hexstr = re.sub(br'[^0-9A-Fa-f]', b'', raw).decode('ascii')
            if len(hexstr) % 2:
                hexstr += '0'
            raw = bytes.fromhex(hexstr)
        else:
            return raw
    return raw


def _parse_object(data, i):
    value, i = _parse_value(data, i)
    j = _skip(data, i)
    if isinstance(value, dict) and data.startswith(b'stream', j):
        j += 6
        if data.startswith(b'\r\n', j):
            j += 2
        elif j < len(data) and data[j] in (10, 13):
            j += 1
        length = value.get('/Length')
        if isinstance(length, int) and length >= 0:
            raw = data[j:j + length]
            i = j + length
        else:
            end = data.find(b'endstream', j)
            raw = data[j:end] if end >= 0 else b''
            i = end if end >= 0 else j
        value = dict(value)
        value['_stream'] = raw
        try:
            value['_decoded'] = _decode_stream(raw, value.get('/Filter'))
        except (zlib.error, ValueError):
            value['_decoded'] = b''
    return value, i


def _scan_objects(data):
    """Fallback for PDFs with no usable xref. Stream bodies are skipped via /Length so a
    compressed page is not scanned byte by byte."""
    objects = {}
    pattern = re.compile(br'(\d+)\s+(\d+)\s+obj\b')
    i = 0
    while i < len(data):
        match = pattern.search(data, i)
        if not match:
            break
        num = int(match.group(1))
        try:
            value, end = _parse_object(data, match.end())
        except (ValueError, IndexError, KeyError):
            i = match.end() + 1
            continue
        objects[num] = value
        if isinstance(value, dict) and isinstance(value.get('/Length'), int) and b'stream' in data[match.end():end + 1]:
            i = end
            continue
        endobj = data.find(b'endobj', end)
        i = endobj + 6 if 0 <= endobj < end + 64 else end
    return objects


def _inflate(raw):
    try:
        return zlib.decompress(raw)
    except zlib.error:
        return zlib.decompress(raw.strip(b'\r\n \t'))


def _text_ops_in(objects):
    count = 0
    for obj in objects.values():
        if not isinstance(obj, dict):
            continue
        blob = obj.get('_decoded')
        if isinstance(blob, (bytes, bytearray)) and (b'Tj' in blob or b'TJ' in blob or b"'" in blob):
            count += blob.count(b'Tj') + blob.count(b'TJ')
    return count


def _expand_objstm(obj, objects):
    if not isinstance(obj, dict) or obj.get('/Type') != '/ObjStm':
        return
    data = obj.get('_decoded')
    if not isinstance(data, (bytes, bytearray)):
        return
    try:
        count = int(obj.get('/N') or 0)
        first = int(obj.get('/First') or 0)
    except (TypeError, ValueError):
        return
    if count <= 0 or first < 0 or first > len(data):
        return
    try:
        nums = [int(piece) for piece in data[:first].split()]
    except ValueError:
        return
    if len(nums) < count * 2:
        return
    pairs = [(nums[i * 2], nums[i * 2 + 1]) for i in range(count)]
    for i, (num, rel) in enumerate(pairs):
        if num in objects:
            continue
        start = first + rel
        if start < 0 or start >= len(data):
            continue
        try:
            value, _end = _parse_value(data, start)
        except (ValueError, IndexError, KeyError):
            continue
        objects[num] = value


def _expand_all_objstms(objects):
    for obj in list(objects.values()):
        _expand_objstm(obj, objects)


def _should_decode(value):
    """Image XObjects are not text. Inflating them is what made a 64-page book take 20 s."""
    if not isinstance(value, dict):
        return False
    if value.get('/Subtype') == '/Image':
        return False
    return True


def _parse_bounded(data, offset, limit):
    """The object at ``offset``, not reading past ``limit`` (the next xref offset)."""
    match = re.match(br'\s*(\d+)\s+(\d+)\s+obj\b', data[offset:offset + 64])
    start = offset + match.end() if match else offset
    region_end = limit if limit > start else len(data)
    value, end = _parse_value(data, start)
    if isinstance(value, dict):
        stream_at = data.find(b'stream', start, min(start + 900, region_end))
        if stream_at >= 0:
            j = stream_at + 6
            if data.startswith(b'\r\n', j):
                j += 2
            elif j < len(data) and data[j] in (10, 13):
                j += 1
            stop = data.find(b'endstream', j, region_end)
            value = dict(value)
            if not _should_decode(value):
                value['_decoded'] = b''
                value['_skipped'] = 'image'
            else:
                raw = data[j:stop if stop >= 0 else region_end]
                try:
                    value['_decoded'] = _decode_stream(raw, value.get('/Filter'))
                except (zlib.error, ValueError):
                    value['_decoded'] = b''
    return value


def _xref_table(data, offset):
    """Classic xref table at ``offset``. Returns (entries, root_ref, prev) or None."""
    if not data.startswith(b'xref', offset):
        return None
    i = offset + 4
    entries = {}
    while True:
        i = _skip(data, i)
        head = re.match(br'(\d+)\s+(\d+)\s*', data[i:])
        if not head:
            break
        start, count = int(head.group(1)), int(head.group(2))
        i += head.end()
        for n in range(count):
            line = data[i:i + 20]
            m = re.match(br'(\d{10})\s+(\d{5})\s+([nf])', line)
            if not m:
                break
            if m.group(3) == b'n':
                entries[start + n] = (1, int(m.group(1)), int(m.group(2)))
            else:
                entries[start + n] = (0, 0, 65535)
            i += 20
    i = _skip(data, i)
    if not data.startswith(b'trailer', i):
        return entries, None, None
    trailer, _end = _parse_value(data, i + len(b'trailer'))
    root = trailer.get('/Root') if isinstance(trailer, dict) else None
    prev = trailer.get('/Prev') if isinstance(trailer, dict) else None
    return entries, root, prev


def _xref_stream_entries(value):
    if not isinstance(value, dict) or value.get('/Type') != '/XRef':
        return None
    decoded = value.get('_decoded')
    if not isinstance(decoded, (bytes, bytearray)):
        return None
    widths = value.get('/W') or [1, 2, 1]
    if not (isinstance(widths, list) and len(widths) == 3):
        return None
    w1, w2, w3 = (int(widths[0]), int(widths[1]), int(widths[2]))
    span = w1 + w2 + w3
    if span <= 0:
        return None
    index = value.get('/Index')
    if not (isinstance(index, list) and len(index) >= 2):
        size = int(value.get('/Size') or 0)
        index = [0, size]
    entries = {}
    pos = 0

    def field(blob):
        return int.from_bytes(blob, 'big') if blob else 0

    for i in range(0, len(index) - 1, 2):
        start, count = int(index[i]), int(index[i + 1])
        for n in range(count):
            if pos + span > len(decoded):
                break
            chunk = decoded[pos:pos + span]
            pos += span
            typ = field(chunk[:w1]) if w1 else 1
            a = field(chunk[w1:w1 + w2])
            b = field(chunk[w1 + w2:w1 + w2 + w3])
            entries[start + n] = (typ, a, b)
    return entries, value.get('/Root'), value.get('/Prev')


def _read_xref_chain(data):
    positions = [int(m.group(1)) for m in re.finditer(br'startxref\s+(\d+)', data)]
    if not positions:
        return {}, None
    entries = {}
    root = None
    pending = [positions[-1]]
    seen = set()
    while pending:
        pos = pending.pop()
        if pos in seen or pos < 0 or pos >= len(data):
            continue
        seen.add(pos)
        if data.startswith(b'xref', pos):
            found = _xref_table(data, pos)
            if not found:
                continue
            got, got_root, prev = found
        else:
            try:
                value = _parse_bounded(data, pos, len(data))
            except (ValueError, IndexError, KeyError):
                continue
            found = _xref_stream_entries(value)
            if not found:
                continue
            got, got_root, prev = found
        for num, item in got.items():
            entries.setdefault(num, item)
        if root is None and got_root is not None:
            root = got_root
        if isinstance(prev, int):
            pending.append(prev)
    return entries, root


def _load_via_xref(data):
    entries, root_ref = _read_xref_chain(data)
    if not entries:
        return None
    offsets = sorted((off, num) for num, (typ, off, _gen) in entries.items() if typ == 1 and off > 0)
    limits = {}
    offs = [off for off, _num in offsets]
    for i, (off, num) in enumerate(offsets):
        limits[num] = offs[i + 1] if i + 1 < len(offs) else len(data)
    objects = {}
    for off, num in offsets:
        try:
            objects[num] = _parse_bounded(data, off, limits[num])
        except (ValueError, IndexError, KeyError):
            continue
    _expand_all_objstms(objects)
    root = _resolve(root_ref, objects) if isinstance(root_ref, Ref) else None
    return objects, root


def _has_pages(objects, root):
    catalog = root if isinstance(root, dict) and root.get('/Type') == '/Catalog' else None
    if catalog is None:
        catalog = next((obj for obj in objects.values()
                        if isinstance(obj, dict) and obj.get('/Type') == '/Catalog'), None)
    if not isinstance(catalog, dict):
        return False
    return any(True for _ in _walk_pages(_resolve(catalog.get('/Pages'), objects), objects))


def _load_documents(data):
    """Objects via the xref (including object streams), else a direct scan."""
    loaded = _load_via_xref(data)
    if loaded and _has_pages(loaded[0], loaded[1]):
        return loaded
    objects = _scan_objects(data)
    _expand_all_objstms(objects)
    return objects, None


def _resolve(value, objects):
    if isinstance(value, Ref):
        return objects.get(value.num)
    return value


def _inherited(node, key, objects):
    seen = set()
    while isinstance(node, dict) and id(node) not in seen:
        seen.add(id(node))
        if key in node:
            return _resolve(node[key], objects)
        node = _resolve(node.get('/Parent'), objects)
    return None


def _walk_pages(node, objects):
    node = _resolve(node, objects)
    if not isinstance(node, dict):
        return
    kids = node.get('/Kids')
    if node.get('/Type') == '/Pages' or (isinstance(kids, list) and node.get('/Type') != '/Page'):
        for kid in kids or []:
            for page in _walk_pages(kid, objects):
                yield page
        return
    if node.get('/Type') == '/Page' or '/Contents' in node:
        yield node


# ---------------------------------------------------------------- content stream

def _content_tokens(data):
    i, n = 0, len(data)
    while i < n:
        c = data[i]
        if c in b' \t\r\n\f\0':
            i += 1
            continue
        if c == 37:
            i = data.find(b'\n', i)
            i = n if i < 0 else i + 1
            continue
        if c == 40:
            raw, i = _parse_literal(data, i)
            yield ('str', raw)
            continue
        if c == 60:
            if data.startswith(b'<<', i):
                val, i = _parse_dict(data, i)
                yield ('dict', val)
                continue
            raw, i = _parse_hex(data, i)
            yield ('str', raw)
            continue
        if c == 91:
            val, i = _parse_array(data, i)
            yield ('arr', val)
            continue
        if c == 47:
            name, i = _parse_name(data, i)
            yield ('name', name)
            continue
        if c in b'+-.0123456789':
            num, i = _parse_number(data, i)
            yield ('num', num)
            continue
        j = i + 1
        while j < n and data[j] not in b' \t\r\n\f\0()<>[]{}/%':
            j += 1
        yield ('op', data[i:j].decode('latin-1'))
        i = j


def _mm(m1, m2):
    """Matrix product m1 × m2. A point is a column; m2 is applied first."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


_IDENT = (1, 0, 0, 1, 0, 0)


def _parse_cmap(data):
    text = data.decode('latin-1', errors='replace')
    width = 2
    space = re.search(r'begincodespacerange(.*?)endcodespacerange', text, re.S)
    if space:
        codes = re.findall(r'<([0-9A-Fa-f]+)>', space.group(1))
        if codes:
            width = max(1, len(codes[0]) // 2)
    mapping = {}

    def dest(hexstr):
        raw = bytes.fromhex(hexstr if len(hexstr) % 2 == 0 else hexstr + '0')
        if len(raw) >= 2 and len(raw) % 2 == 0:
            return raw.decode('utf-16-be', errors='replace')
        return raw.decode('latin-1', errors='replace')

    for block in re.finditer(r'beginbfchar(.*?)endbfchar', text, re.S):
        for src, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block.group(1)):
            mapping[int(src, 16)] = dest(dst)
    for block in re.finditer(r'beginbfrange(.*?)endbfrange', text, re.S):
        for match in re.finditer(
                r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(?:<([0-9A-Fa-f]+)>|\[([^\]]*)\])',
                block.group(1)):
            start, end = int(match.group(1), 16), int(match.group(2), 16)
            if match.group(3):
                base = dest(match.group(3))
                for n, code in enumerate(range(start, end + 1)):
                    if not base:
                        mapping[code] = ''
                        continue
                    last = ord(base[-1]) + n
                    mapping[code] = base[:-1] + chr(last) if last <= 0x10FFFF else ''
            else:
                dests = re.findall(r'<([0-9A-Fa-f]+)>', match.group(4) or '')
                for code, item in zip(range(start, end + 1), dests):
                    mapping[code] = dest(item)
    return {'width': width, 'map': mapping}


def _decode_text(raw, cmap):
    if cmap:
        width = cmap['width'] or 1
        out = []
        i = 0
        while i + width <= len(raw):
            code = int.from_bytes(raw[i:i + width], 'big')
            out.append(cmap['map'].get(code, ''))
            i += width
        return ''.join(out)
    if raw.startswith(b'\xfe\xff') or raw.startswith(b'\xff\xfe'):
        return raw.decode('utf-16', errors='replace').lstrip('\ufeff')
    return raw.decode('latin-1', errors='replace')


def _face_italic(font, objects):
    if not isinstance(font, dict):
        return False
    base = str(font.get('/BaseFont') or '')
    if 'italic' in base.lower() or 'oblique' in base.lower():
        return True
    desc = _resolve(font.get('/FontDescriptor'), objects) if font.get('/FontDescriptor') is not None else None
    if isinstance(desc, dict):
        try:
            angle = float(desc.get('/ItalicAngle') or 0)
        except (TypeError, ValueError):
            angle = 0
        try:
            flags = int(desc.get('/Flags') or 0)
        except (TypeError, ValueError):
            flags = 0
        if angle or flags & 64:
            return True
    kids = font.get('/DescendantFonts')
    if isinstance(kids, list) and kids:
        return _face_italic(_resolve(kids[0], objects), objects)
    return False


def _font_face(font, objects):
    """(cmap, italic). The CMap is cached on the font object so 64 pages parse it once."""
    if not isinstance(font, dict):
        return None, False
    italic = _face_italic(font, objects)
    if '_cmap' in font:
        return font.get('_cmap'), italic
    cmap = None
    if font.get('/ToUnicode') is not None:
        uni = _resolve(font.get('/ToUnicode'), objects)
        if isinstance(uni, dict) and isinstance(uni.get('_decoded'), (bytes, bytearray)) and uni['_decoded']:
            cmap = _parse_cmap(uni['_decoded'])
    font['_cmap'] = cmap
    return cmap, italic


def _fonts(page, objects):
    resources = _inherited(page, '/Resources', objects) or {}
    if not isinstance(resources, dict):
        return {}
    font_dict = _resolve(resources.get('/Font'), objects) or {}
    if not isinstance(font_dict, dict):
        return {}
    fonts = {}
    for name, ref in font_dict.items():
        if not isinstance(name, str):
            continue
        font = _resolve(ref, objects)
        cmap, italic = _font_face(font, objects)
        fonts[name] = (cmap, italic)
        fonts[name[1:]] = (cmap, italic)
    return fonts


def _contents(page, objects):
    contents = _resolve(page.get('/Contents'), objects)
    streams = contents if isinstance(contents, list) else [contents]
    parts = []
    for item in streams:
        obj = _resolve(item, objects)
        if isinstance(obj, dict) and isinstance(obj.get('_decoded'), (bytes, bytearray)):
            parts.append(obj['_decoded'])
        elif isinstance(obj, (bytes, bytearray)):
            parts.append(bytes(obj))
    return b'\n'.join(parts)


def _read_page(page, objects):
    box = _inherited(page, '/MediaBox', objects) or [0, 0, 612, 792]
    if not (isinstance(box, list) and len(box) >= 4):
        box = [0, 0, 612, 792]
    width = float(box[2]) - float(box[0])
    height = float(box[3]) - float(box[1])
    fonts = _fonts(page, objects)
    data = _contents(page, objects)
    return _interpret(data, fonts, width, height)


class _Text(object):
    def __init__(self):
        self.ctm = _IDENT
        self.font = None
        self.font_size = 12
        self.char_space = 0
        self.word_space = 0
        self.hscale = 100
        self.leading = 0
        self.rise = 0
        self.tm = _IDENT
        self.tlm = _IDENT
        self.in_text = False
        self.word_break = False

    def copy(self):
        other = _Text()
        other.__dict__.update(self.__dict__)
        return other

    def origin(self):
        return _apply(_mm(self.ctm, self.tm), 0, self.rise)

    def advance(self, tx):
        self.tm = _mm(self.tm, (1, 0, 0, 1, tx, 0))


def _interpret(data, fonts, width, height):
    state = _Text()
    stack = []
    saved = []
    chunks = []
    rects = []
    pending = None
    text_ops = 0

    def nums():
        found = [val for kind, val in stack if kind == 'num']
        return found

    # One run is a line of glyphs. A TJ number that moves right by more than a fraction of
    # the font size is a word space; a smaller kern stays inside the word. One token per
    # glyph is what produced 'Th e trail' and 'F o llo wi n'.
    run = {'text': '', 'x': 0.0, 'y': 0.0, 'end': 0.0, 'size': 12.0, 'italic': False}

    def flush():
        if run['text']:
            chunks.append({'x': run['x'], 'y': run['y'], 'text': run['text'], 'size': run['size'],
                           'w': max(run['end'] - run['x'], 0.0), 'italic': run['italic']})
        run['text'] = ''

    def show(raw):
        info = fonts.get(state.font)
        cmap, italic = info if isinstance(info, tuple) else (None, False)
        text = _decode_text(raw, cmap)
        if not text:
            state.word_break = False
            return
        x, y = state.origin()
        size = state.font_size or 12.0
        spaces = text.count(' ')
        tx = ((0.45 * size * len(text)) + state.char_space * len(text)
              + state.word_space * spaces) * (state.hscale / 100.0)
        if run['text']:
            same = abs(y - run['y']) <= max(LINE_Y, size * 0.35)
            gap = x - run['end']
            if not same or gap > max(14.0, size * 1.15):
                flush()
            elif state.word_break or gap > size * 0.17:
                run['text'] += ' '
        state.word_break = False
        if not run['text']:
            run['x'], run['y'], run['size'], run['italic'] = x, y, size, bool(italic)
            run['text'] = text
        else:
            run['text'] += text
            run['italic'] = run['italic'] and bool(italic)
        state.advance(tx)
        run['end'] = state.origin()[0]

    def show_item(item):
        if isinstance(item, (bytes, bytearray)):
            show(bytes(item))
        elif isinstance(item, str):
            show(item.encode('latin-1'))
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            size = state.font_size or 12.0
            shift = (-float(item) / 1000.0) * size * (state.hscale / 100.0)
            # PDF subtracts the TJ number from x. A large negative number is a word space.
            if shift > size * 0.17:
                state.word_break = True
            state.advance(shift)

    for kind, val in _content_tokens(data):
        if kind != 'op':
            stack.append((kind, val))
            continue
        op = val
        if op == 'q':
            saved.append(state.copy())
        elif op == 'Q' and saved:
            state = saved.pop()
        elif op == 'cm':
            values = nums()
            if len(values) >= 6:
                state.ctm = _mm(tuple(values[-6:]), state.ctm)
        elif op == 'BT':
            state.in_text = True
            state.tm = _IDENT
            state.tlm = _IDENT
        elif op == 'ET':
            flush()
            state.in_text = False
        elif op == 'Tf':
            names = [v for k, v in stack if k == 'name']
            values = nums()
            if names:
                state.font = names[-1]
            if values:
                state.font_size = float(values[-1])
        elif op == 'Tm':
            values = nums()
            if len(values) >= 6:
                state.tm = tuple(values[-6:])
                state.tlm = state.tm
        elif op == 'Td':
            values = nums()
            if len(values) >= 2:
                state.tm = _mm(state.tlm, (1, 0, 0, 1, values[-2], values[-1]))
                state.tlm = state.tm
        elif op == 'TD':
            values = nums()
            if len(values) >= 2:
                state.leading = -float(values[-1])
                state.tm = _mm(state.tlm, (1, 0, 0, 1, values[-2], values[-1]))
                state.tlm = state.tm
        elif op == 'T*':
            state.tm = _mm(state.tlm, (1, 0, 0, 1, 0, -state.leading))
            state.tlm = state.tm
        elif op == 'Tc':
            values = nums()
            if values:
                state.char_space = float(values[-1])
        elif op == 'Tw':
            values = nums()
            if values:
                state.word_space = float(values[-1])
        elif op == 'Tz':
            values = nums()
            if values:
                state.hscale = float(values[-1])
        elif op == 'TL':
            values = nums()
            if values:
                state.leading = float(values[-1])
        elif op == 'Ts':
            values = nums()
            if values:
                state.rise = float(values[-1])
        elif op in ('Tj', "'", '"'):
            text_ops += 1
            if op == "'":
                state.tm = _mm(state.tlm, (1, 0, 0, 1, 0, -state.leading))
                state.tlm = state.tm
            if op == '"':
                values = nums()
                if len(values) >= 2:
                    state.word_space = float(values[-2])
                    state.char_space = float(values[-1])
                state.tm = _mm(state.tlm, (1, 0, 0, 1, 0, -state.leading))
                state.tlm = state.tm
            strings = [v for k, v in stack if k == 'str']
            if strings:
                show(strings[-1])
        elif op == 'TJ':
            text_ops += 1
            arrays = [v for k, v in stack if k == 'arr']
            if arrays:
                for item in arrays[-1]:
                    show_item(item)
        elif op == 're':
            values = nums()
            if len(values) >= 4:
                x, y, w, h = values[-4:]
                x0, y0 = _apply(state.ctm, x, y)
                x1, y1 = _apply(state.ctm, x + w, y + h)
                pending = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        elif op in ('f', 'F', 'f*', 'S', 's', 'B', 'b', 'b*', 'B*'):
            if pending:
                rects.append(pending)
            pending = None
        elif op == 'n':
            pending = None
        stack = []
    flush()
    return chunks, rects, text_ops, width, height


# ---------------------------------------------------------------- reading order

def _norm_margin(text):
    return re.sub(r'\d+', '#', re.sub(r'\s+', ' ', text).strip().casefold())


def _keep_margin(text):
    return bool(_HEADING.match(text.strip()))


def _drop_margins(pages):
    counts = {}
    for page in pages:
        height = page['height'] or 792
        seen = set()
        for chunk in page['chunks']:
            zone = _zone(chunk['y'], height)
            if not zone:
                continue
            key = (zone, _norm_margin(chunk['text']))
            if key not in seen:
                counts[key] = counts.get(key, 0) + 1
                seen.add(key)
    for page in pages:
        height = page['height'] or 792
        kept = []
        for chunk in page['chunks']:
            text = chunk['text'].strip()
            zone = _zone(chunk['y'], height)
            if zone and not _keep_margin(text):
                repeated = counts.get((zone, _norm_margin(text)), 0) >= 2
                page_no = bool(_PAGE_NO.match(text))
                running = text.isupper() and 0 < len(text) <= 48
                if repeated or page_no or running:
                    continue
            kept.append(chunk)
        page['chunks'] = kept


def _zone(y, height):
    if y > height * (1 - MARGIN):
        return 'top'
    if y < height * MARGIN:
        return 'bottom'
    return None


def _boxed(chunk, rects, area):
    for x0, y0, x1, y1 in rects:
        if (x1 - x0) * (y1 - y0) > BOX_MAX_AREA * max(area, 1):
            continue
        if (x0 - 3) <= chunk['x'] <= (x1 + 3) and (y0 - 3) <= chunk['y'] <= (y1 + 3):
            return True
    return False


def _split_columns(chunks):
    """Split on the gutter a column gap repeats along, not on a long word's width.

    Word starts inside one sentence are not a second column. A gap that shows up at
    the same x on several lines is the gutter, so 'the door of bronze-covered wood'
    stays one phrase and the facing column stays on its own side.
    """
    if len(chunks) < 4:
        return [chunks]
    # The right column starts at nearly the same x on each line. That x, not the
    # midpoint of a long word, is the gutter.
    starts = []
    for group in _cluster(chunks):
        ordered = sorted(group, key=lambda c: c['x'])
        for prev, cur in zip(ordered, ordered[1:]):
            gap = cur['x'] - (prev['x'] + max(prev.get('w') or 0, 0))
            if gap >= 20:
                starts.append(cur['x'])
    if len(starts) < 2:
        return [chunks]
    starts.sort()
    bands = []
    for x in starts:
        if bands and abs(x - bands[-1][0]) <= 18:
            bands[-1][1].append(x)
        else:
            bands.append([x, [x]])
    bands.sort(key=lambda band: len(band[1]), reverse=True)
    if len(bands[0][1]) < 2:
        return [chunks]
    boundary = min(bands[0][1]) - 4
    left = [c for c in chunks if c['x'] < boundary]
    right = [c for c in chunks if c['x'] >= boundary]
    if len(left) < 2 or len(right) < 2:
        return [chunks]
    columns = [left, right]
    columns.sort(key=lambda col: min(c['x'] for c in col))
    return columns


def _cluster(chunks):
    chunks = sorted(chunks, key=lambda c: (-c['y'], c['x']))
    lines = []
    for chunk in chunks:
        if lines and abs(lines[-1][0]['y'] - chunk['y']) <= max(LINE_Y, chunk['size'] * 0.35):
            lines[-1].append(chunk)
        else:
            lines.append([chunk])
    return lines


def _join(chunks):
    chunks = sorted(chunks, key=lambda c: c['x'])
    text = chunks[0]['text']
    boxed = bool(chunks[0].get('boxed'))
    italic = bool(chunks[0].get('italic'))
    for prev, cur in zip(chunks, chunks[1:]):
        gap = cur['x'] - (prev['x'] + prev.get('w', 0))
        if gap > max(18, prev['size'] * 1.5):
            text += ' | ' + cur['text']
        elif gap > -1.5:
            text += ' ' + cur['text']
        else:
            text += cur['text']
        boxed = boxed and bool(cur.get('boxed'))
        italic = italic and bool(cur.get('italic'))
    text = re.sub(r'[ \t]+', ' ', text).strip()
    prose = ('.' in text or '?' in text or '!' in text) and len(text) > 12
    stat = re.match(r'(?:armor|armour)\s+class\b|hit points\b|speed\s+\d', text, re.I)
    if text and not text.startswith('>') and not stat and (boxed or (italic and prose)):
        text = '> ' + text
    return text


def _layout(pages):
    _drop_margins(pages)
    bodies = []
    for page in pages:
        area = (page['width'] or 612) * (page['height'] or 792)
        for chunk in page['chunks']:
            chunk['boxed'] = _boxed(chunk, page['rects'], area)
        lines = []
        for column in _split_columns(page['chunks']):
            for group in _cluster(column):
                line = _join(group)
                if line:
                    lines.append(line)
        bodies.append('\n'.join(lines))
    return '\f'.join(bodies)
