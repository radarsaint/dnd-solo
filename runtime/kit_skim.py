"""Host skim of the opening pages. Python only validates.

The host reads the first pages the way a human DM flips to where play starts, and
returns one JSON object. This module checks that object against the page-window
extract. It does not choose an opening, paraphrase a quote, or walk forward into
a later section when the check fails.

A window is a count of pages from the front of the extract, not a page in any book.
One expansion is allowed. The whole book is never the window.
"""
import json
import re

from .kit_adventure import folder_for

# How many pages the host reads before anyone is asked to begin. Not a page number
# in a book: the first look, then one longer look if that window has no playable start.
FIRST_WINDOW = 10
EXPAND_ONCE = 8
BURST_WORDS = 100
PICK_MAX = 4
KEYS = ('burst', 'source_quote', 'page_start', 'page_end', 'alt_starts', 'design_start_name')

LANDING = "Got it. Who's walking in? A sentence or two about them, or hand me the sheet."
READY_LINE = "We're set. Default is the book's start — Yes. begins."
MUDDY = "Opening's muddy on my copy."

# Spoken text that is still a DM instruction, a secret, or an overview, even when
# the words are copied from the page. These reject. They are not used to cut a
# quote down to an opening.
_MARK = re.compile(
    r"\bDC\s*\d+\b"
    r"|\b(?:armor|armour)\s+class\b"
    r"|\bhit points\b"
    r"|\b(?:secret|hidden|concealed)\b"
    r"|\bif the characters\b"
    r"|\bread when\b"
    r"|read the (?:following )?boxed"
    r"|when you(?:'re| are) ready"
    r"|\bskip\b[^.]{0,80}\bhook"
    r"|\bread or paraphrase\b"
    r"|\badd the following\b"
    r"|\btell the players\b"
    r"|\bdo not read\b"
    r"|\bthe dm\b"
    r"|\boverview\b"
    r"|\bin this (?:adventure|module)\b"
    r"|\badventure background\b"
    r"|\baward\b[^.]{0,50}\bxp\b"
    r"|\breward the (?:party|characters|players)\b"
    r"|\bgive the (?:characters|party|players)\b"
    r"|\bxp award\b",
    re.I)
_KEYED = re.compile(r'(?m)^(?:area\s+)?[A-Z]?\d{1,3}[a-z]?\s*[.:]\s+\S')
_GO_ON = re.compile(
    r"^\s*(?:go on|continue|keep going|read on)\s*[.!]?\s*$", re.I)
_LOOKUP = re.compile(
    r"\b(?:check the page|look that up|look up|what does the book say|on the page)\b", re.I)
_CHECKLIST = re.compile(
    r'^(?:features|treasure|developments|general features|xp awards?)\b'
    r'|\bfollowing features\b|\bhouse features?\b',
    re.I)
_SYNOPSIS = re.compile(
    r'\b(?:this (?:chapter|section|adventure|part)|in this (?:chapter|section)|'
    r'the adventure|the following|read aloud|boxed text|as the dm|'
    r'the characters (?:can|must|should|are|have)|'
    r'players (?:can|should|must)|'
    r'the party (?:can|should|must|has)|'
    r'skill checks?|saving throws?|advantage|disadvantage|'
    r'armor class|hit points|experience points)\b',
    re.I)
OPENING_PAGES = FIRST_WINDOW + EXPAND_ONCE
_MODES = ('road', 'street', 'patrol', 'trail')
_SENSORY = re.compile(
    r"\b(?:sound|sounds|smell|smells|light|shadow|cold|wind|creak|glint|mud|ruts|"
    r"dust|smoke|rain|whisper|rustle|footstep)\b", re.I)

INSTRUCTIONS = (
    'Skim the opening the way you would flip a print module to where play starts. '
    'Read the first %d PDF pages, or stop sooner at the first playable heading with '
    'player-facing boxed fiction. Do not read the rest of the book. '
    'If that window has no playable heading and no boxed fiction, expand once by the '
    'next %d pages and stop. A second expand is refused.\n'
    'Return one JSON object and nothing else. Keys: burst, source_quote, page_start, '
    'page_end, alt_starts, design_start_name.\n'
    'burst is the first player-facing sentences only, at most %d words, ending on a '
    'sentence. source_quote is the verbatim span those sentences come from, copied '
    'from those pages, with no tip, DC, secret, reward instruction, or note to the DM. '
    'page_start and page_end are inside this window. '
    'alt_starts is 2 to 4 early titles in this same window, each {"title","page"}. '
    'No later keyed room and no climax. design_start_name is the heading the book '
    'uses for this start.\n'
    'To expand once, return {"expand": true} and nothing else, then skim the longer window.\n'
    'Python checks that the quote\'s words occur in order on those pages. '
    'A column may sit between the words. A paraphrase is refused. '
    'On a refusal, say the picker. Do not open a later room.'
    % (FIRST_WINDOW, EXPAND_ONCE, BURST_WORDS))


def _path(db):
    return folder_for(db) / 'skim.json'


def _read(db):
    path = _path(db)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(db, data):
    path = _path(db)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


# Curly quotes and the like become straight marks before either side is compared.
_APOSTROPHE = {
    '\u2019': "'", '\u2018': "'", '\u2032': "'", '\u02bc': "'", '\u02bb': "'",
    '\u201c': '"', '\u201d': '"', '\u00a0': ' ', '\u2009': ' ', '\u202f': ' ',
}


def normalize(text):
    """Apostrophes, quotes, whitespace, and a wrapped hyphen. Both sides of a match.

    This is not a paraphrase. The words stay in order; only the ink changes.
    """
    text = text or ''
    text = text.replace('\u00ad', '')
    for src, dst in _APOSTROPHE.items():
        text = text.replace(src, dst)
    text = text.replace('>', ' ').replace('|', ' ')
    text = re.sub(r'(\w)-\s+([A-Za-z])', r'\1\2', text)
    return re.sub(r'\s+', ' ', text).strip()


def _words(text):
    return [word.casefold() for word in re.findall(r"[A-Za-z0-9']+", normalize(text))]


def _contiguous(needle, haystack):
    """True when needle's words sit in haystack in order, with nothing between them."""
    got, want = _words(haystack), _words(needle)
    if not want or len(want) > len(got):
        return False
    span = len(want)
    return any(got[i:i + span] == want for i in range(len(got) - span + 1))


def _marked(text):
    """A tip, a secret, a checklist, or a note to the DM. Not player fiction."""
    cleaned = normalize(text)
    return bool(cleaned and (_MARK.search(cleaned) or _CHECKLIST.search(cleaned)))


def _unsafe(text):
    """DM prep, secrets, a synopsis, or mechanics. Never Narrator text."""
    cleaned = normalize(text)
    if not cleaned:
        return True
    return _marked(cleaned) or bool(_SYNOPSIS.search(cleaned))


def _sentence_bounded(text):
    text = normalize(text)
    if not text or text[-1] not in '.!?':
        return False
    return True


def page_bounds(text):
    """(start, end) offsets for each form-feed page. Page 1 is the first slice."""
    parts = (text or '').split('\f')
    bounds = []
    at = 0
    for i, part in enumerate(parts):
        bounds.append((at, at + len(part)))
        at += len(part)
        if i != len(parts) - 1:
            at += 1
    return bounds or [(0, 0)]


def window_end(page_count, expanded):
    cap = FIRST_WINDOW + (EXPAND_ONCE if expanded else 0)
    if page_count < 1:
        return 1
    return min(page_count, cap)


def _window_text(text, page_start, page_end):
    bounds = page_bounds(text)
    page_start = max(1, min(page_start, len(bounds)))
    page_end = max(page_start, min(page_end, len(bounds)))
    start = bounds[page_start - 1][0]
    end = bounds[page_end - 1][1]
    return text[start:end], start, end


def request_for(db):
    """What the host skims. The book text is not copied into the packet."""
    from .kit_adventure import _load
    try:
        _index, text = _load(db)
    except Exception:
        text = ''
    data = _read(db)
    count = len(page_bounds(text)) if text else 1
    expanded = bool(data.get('expanded'))
    end = window_end(count, expanded)
    import shlex
    command = 'python3 -m runtime.kit_agent adventure skim --db %s --file skim.json' % shlex.quote(str(db))
    return {
        'stage': 'skim_request',
        'window_pages': end,
        'first_window': FIRST_WINDOW,
        'expand_pages': EXPAND_ONCE,
        'expands_left': 0 if expanded else 1,
        'page_count': count,
        'expanded': expanded,
        'burst_words': BURST_WORDS,
        'instructions': INSTRUCTIONS,
        'command': command,
    }


def _title_of(item):
    if not isinstance(item, dict):
        return None
    title = item.get('title') if isinstance(item.get('title'), str) else item.get('name')
    if not isinstance(title, str):
        return None
    title = normalize(title)
    return title or None


def _sentences(text):
    return [part.strip() for part in re.findall(r'[^.!?]+[.!?]+', normalize(text)) if part.strip()]


def column_streams(page_text):
    """The page as stored, plus each side of a mixed-column line (`left | right`).

    A printed read-aloud is contiguous on its own side even when the extract
    alternates the two columns on one line.
    """
    streams = [page_text or '']
    if ' | ' not in (page_text or ''):
        return streams
    columns = []
    for line in (page_text or '').split('\n'):
        parts = line.split(' | ')
        for index, part in enumerate(parts):
            while len(columns) <= index:
                columns.append([])
            columns[index].append(part.strip())
    for column in columns:
        if any(column):
            streams.append('\n'.join(column))
    return streams


def _word_spans(text):
    """(normalized text, [(word, start, end), ...]) after apostrophes are straightened."""
    norm = normalize(text)
    spans = [(match.group(0).casefold(), match.start(), match.end())
             for match in re.finditer(r"[A-Za-z0-9']+", norm)]
    return norm, spans


def _locate(norm, spans, start_i, end_i):
    """Character slice of a word run, extended through its closing punctuation."""
    begin = spans[start_i][1]
    cut = spans[end_i][2]
    while cut < len(norm) and norm[cut] in '.!?"\')]}':
        cut += 1
    return norm[begin:cut].strip(), begin, cut


def _ordered_span(words, want):
    """(first, last) index when want's words occur in order, gaps allowed. None otherwise."""
    pos = 0
    first = None
    last = None
    for word in want:
        found = None
        for index in range(pos, len(words)):
            if words[index] == word:
                found = index
                break
        if found is None:
            return None
        if first is None:
            first = found
        last = found
        pos = found + 1
    if first is None:
        return None
    return first, last


def _search_stream(stream, want):
    """(spoken, how) on one column or one page. Contiguous wins. Ordered is the proof
    when the other column sits between the words. The spoken line never adds those words."""
    norm, spans = _word_spans(stream)
    words = [item[0] for item in spans]
    width = len(want)
    for index in range(max(0, len(words) - width + 1)):
        if words[index:index + width] == want:
            spoken, _b, _e = _locate(norm, spans, index, index + width - 1)
            return spoken, 'contiguous'
    hit = _ordered_span(words, want)
    if hit is None:
        return None
    return None, 'ordered'


def find_quote(page_text, quote):
    """(clean text, how) when the quote's words are on these pages.

    Each page and each column is tried on its own. Words must occur in order.
    A paraphrase, or a line from a later page, is not a match. Nothing is invented.
    """
    want = _words(quote)
    if not want:
        return None
    pages = [page for page in (page_text or '').split('\f')] or ['']
    ordered = None
    streams = []
    for page in pages:
        streams.extend(column_streams(page))
    streams.append(page_text or '')
    for stream in streams:
        found = _search_stream(stream, want)
        if not found:
            continue
        _spoken, how = found
        if how == 'contiguous':
            return _spoken, how
        if ordered is None:
            ordered = (normalize(quote), how)
    return ordered


def _fiction_after(window, title):
    """Player sentences under a heading. Empty when the heading only leads into a secret."""
    want = _words(title)
    if not want:
        return ''
    for stream in column_streams(window):
        norm, spans = _word_spans(stream)
        words = [item[0] for item in spans]
        width = len(want)
        at = next((i for i in range(max(0, len(words) - width + 1)) if words[i:i + width] == want), None)
        if at is None:
            continue
        _spoken, _b, end = _locate(norm, spans, at, at + width - 1)
        kept = []
        for sentence in _sentences(norm[end:]):
            if _KEYED.match(sentence) or _unsafe(sentence):
                break
            if len(sentence.split()) <= 2 and sentence[:1].isupper() and not sentence.endswith('.'):
                break
            kept.append(sentence)
            if len(kept) >= 2:
                break
        if kept:
            return ' '.join(kept)
    return ''


def _filter_alts(alts, window, end_page):
    """Early titles inside the window that open onto player fiction, not a secret."""
    kept = []
    seen = set()
    for item in alts or []:
        title = _title_of(item)
        page = item.get('page') if isinstance(item, dict) else None
        if not title or not isinstance(page, int) or isinstance(page, bool):
            continue
        if page < 1 or page > end_page:
            continue
        if not _contiguous(title, window) and find_quote(window, title) is None:
            continue
        quote = _fiction_after(window, title)
        if not quote or _unsafe(quote):
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append({'title': title, 'page': page, 'quote': quote})
    kept.sort(key=lambda item: (item['page'], item['title'].casefold()))
    return kept[:PICK_MAX]


def picker_line(alts):
    titles = [item['title'] for item in alts or [] if item.get('title')][:PICK_MAX]
    if len(titles) >= 2:
        listed = ', '.join(titles[:-1]) + ', or ' + titles[-1]
        return "%s Pick: %s, or describe how you arrive." % (MUDDY, listed)
    if len(titles) == 1:
        return "%s Pick: %s, or describe how you arrive." % (MUDDY, titles[0])
    return "%s Describe how you arrive." % MUDDY


def _split_burst(quote, burst):
    """(book wording of the burst, remainder). The burst keeps its closing punctuation."""
    norm = normalize(quote)
    want = _words(burst)
    got = _words(norm)
    if not want:
        return '', norm
    span = len(want)
    start = next((i for i in range(len(got) - span + 1) if got[i:i + span] == want), None)
    if start is None:
        return normalize(burst), ''
    starts, ends = [], []
    for match in re.finditer(r"[A-Za-z0-9']+", norm):
        starts.append(match.start())
        ends.append(match.end())
    begin = starts[start]
    cut = ends[start + span - 1]
    while cut < len(norm) and norm[cut] in '.!?"\')]}':
        cut += 1
    return norm[begin:cut].strip(), norm[cut:].strip()


def _handoff(text, name):
    blob = '%s %s' % (name or '', text or '')
    for mode in _MODES:
        if re.search(r'\b%s\b' % mode, blob, re.I):
            return "You're on the %s. Go on for the rest, or say what you do." % mode
    return "That's the book's start. Go on for the rest, or say what you do."


def _take(text, limit):
    """The next sentence-bounded chunk, at most `limit` words, and what stays frozen."""
    text = normalize(text)
    if not text:
        return '', ''
    sentences = [part.strip() for part in re.findall(r'[^.!?]+[.!?]+', text) if part.strip()]
    if not sentences:
        return '', text
    chunk = []
    count = 0
    for sentence in sentences:
        words = len(_words(sentence))
        if chunk and count + words > limit:
            break
        chunk.append(sentence)
        count += words
        if count >= limit:
            break
    used = ' '.join(chunk).strip()
    rest = text[len(used):].strip() if text.startswith(used) else ''
    if not rest:
        # The join may have collapsed spaces the source still has.
        idx = text.find(chunk[-1])
        if idx >= 0:
            rest = text[idx + len(chunk[-1]):].strip()
    return used, rest


def _reject(db, problems, alts, expanded):
    data = _read(db)
    # A failed check never becomes the start, and never walks into the next section.
    # A skim that already passed stays the start.
    line = picker_line(alts)
    if data.get('status') != 'accepted':
        data.update({
            'status': 'rejected',
            'problems': list(problems),
            'alt_starts': alts,
            'expanded': bool(expanded or data.get('expanded')),
            'table_line': line,
        })
        _write(db, data)
    return {
        'stage': 'skim_rejected',
        'problems': list(problems),
        'alt_starts': alts,
        'start_picker': {'table_line': line, 'places': [
            {'pick': item['title'], 'line': item['title'], 'page': item['page']} for item in alts]},
        'table_line': line,
        'opened_room': None,
        'advanced': False,
    }


def _anchor(page_text, quote):
    """Offset of the quote in the raw page, apostrophes allowed to curl."""
    words = _words(quote)
    if not words:
        return 0
    parts = []
    for word in words:
        pieces = [re.escape(piece) for piece in word.split("'")]
        parts.append("['\u2019\u2018]?".join(pieces))
    match = re.search(r'\W+'.join(parts), page_text or '', re.I)
    if match:
        return match.start()
    first = re.search(r'\b' + parts[0], page_text or '', re.I)
    return first.start() if first else 0


def _clip(text, quote_end, page_end_off):
    """Stop the opening body at the next numbered heading. Do not swallow a later room."""
    if page_end_off <= quote_end:
        return quote_end
    chunk = text[quote_end:page_end_off]
    match = _KEYED.search(chunk)
    if match and match.start() > 0:
        return quote_end + match.start()
    return page_end_off


def _containing(index, offset):
    """The scene whose own body holds this offset. A later room's body does not count
    when the offset sits before that room's heading."""
    hits = []
    for key, loc in (index.get('locations') or {}).items():
        body = loc.get('body') or (0, 0)
        if not (body[0] <= offset < body[1]):
            continue
        if offset < (loc.get('offset') or 0) and loc.get('type') != 'scene':
            continue
        hits.append((key, loc))
    scenes = [item for item in hits if item[1].get('type') == 'scene']
    pool = scenes or hits
    if not pool:
        return None
    return max(pool, key=lambda item: item[1].get('offset') or 0)[0]


def _emit_scene(index, text, name, span, letter):
    from .kit_adventure import _creatures, _creature_belongs_here, _sentence_around
    start, end = span
    key = 'scene:skim:%s' % letter
    page = 1
    for item in index.get('pages') or []:
        if item.get('start', 0) <= start <= item.get('end', start):
            page = item.get('page') or page
    loc = {
        'key': key, 'bare': letter, 'name': name, 'offset': start, 'body': [start, end],
        'page': page, 'chapter': None, 'site': 'skim', 'type': 'scene', 'letter': letter,
        'part_n': 1, 'relation': 'before', 'anchor': {}, 'connections': [], 'npcs': [],
        'read_aloud': '>' in text[start:end], 'creatures': [],
    }
    span_text = text[start:end]
    kept = []
    for creature in _creatures(span_text, start, index.get('stat_blocks') or {}):
        rel = creature['mention_offset'] - start
        if _creature_belongs_here(_sentence_around(span_text, rel), loc, index):
            kept.append(creature)
    loc['creatures'] = kept
    index.setdefault('locations', {})[key] = loc
    return key


def _pressure(page_slice, book_quote):
    """Creature sentences in this span that are not the spoken box and not a secret."""
    from .kit_adventure import _creatures, _sentence_around
    found = []
    for creature in _creatures(page_slice or '', 0, {}):
        sent = normalize(_sentence_around(page_slice, creature['mention_offset']))
        if sent and not _unsafe(sent) and not _contiguous(sent, book_quote) and sent not in found:
            found.append(sent)
    return found


def _visible_blob(room):
    return normalize(' '.join(
        fact.get('text') or '' for fact in (room.get('facts') or {}).values()
        if isinstance(fact, dict) and fact.get('visible')))


def _playable(room, burst):
    """The room can be spoken, and what it shows is the burst rather than a secret."""
    blob = _visible_blob(room)
    if not blob or not _contiguous(burst, blob):
        return False
    sentences = _sentences(blob) or [blob]
    player = [line for line in sentences if not _unsafe(line)]
    return bool(player)


def _write_source(db, index, text):
    import hashlib
    from .kit_adventure import _write_json, folder_for
    folder = folder_for(db)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'source.txt').write_text(text, encoding='utf-8')
    index['sha256'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
    index['chars'] = len(text)
    _write_json(folder / 'index.json', index)


def _clean_body(player_quote):
    """Boxed player sentences only. A secret or a synopsis is left out, not spoken."""
    lines = []
    for sentence in _sentences(player_quote) or [normalize(player_quote)]:
        if sentence and not _unsafe(sentence):
            lines.append('> ' + sentence)
    if not lines and player_quote and not _unsafe(player_quote):
        lines.append('> ' + normalize(player_quote))
    return '\n'.join(lines) + ('\n' if lines else '')


def _boxed_lines(page_text):
    """Read-aloud lines on this page, each column on its own."""
    bits = []
    for line in (page_text or '').split('\n'):
        pieces = line.split(' | ') if ' | ' in line else [line]
        for piece in pieces:
            piece = piece.strip()
            if piece.startswith('>'):
                bits.append(piece.lstrip('>').strip())
    return bits


def _heading_line(line):
    """A title or a keyed room, not a sentence of fiction."""
    text = (line or '').strip().lstrip('>').strip()
    if not text or text.endswith(('.', '!', '?')):
        return False
    if _KEYED.match(text):
        return True
    words = text.split()
    return 1 <= len(words) <= 8 and text[:1].isupper()


def _opening_span(page_text, book_quote):
    """The printed player passage that contains the quote, through the next heading.

    Later boxed sentences of this opening stay for Go on. The next title, a secret,
    a synopsis, or a mechanics line does not.
    """
    base = [sentence for sentence in (_sentences(book_quote) or [normalize(book_quote)])
            if sentence and not _unsafe(sentence)]
    want = _words(book_quote)[:4]
    started = False
    extra = []
    held = ' '.join(base)
    for line in (page_text or '').split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        words = _words(stripped)
        if not started:
            head = _ordered_span(words, want) if want else None
            if head is None and not _contiguous(book_quote, normalize(stripped)):
                continue
            started = True
        elif _heading_line(stripped):
            break
        # Only a boxed line is player text. The other column, and a creature
        # sentence under the box, stay out of what Go on will speak.
        if not stripped.startswith('>'):
            continue
        piece = stripped.lstrip('>').strip()
        for sentence in _sentences(piece):
            if _unsafe(sentence) or _contiguous(sentence, held):
                continue
            extra.append(sentence)
            held = (held + ' ' + sentence).strip()
    return ' '.join(base + extra).strip()


def _append_body(db, index, text, block):
    """Put a clean copy of the validated quote where the compiler can read it.

    The words were already found in the skim window. The copy is those words in
    order, so a mixed column or an empty front-matter scene cannot erase them.
    """
    if not block.strip():
        return text, (len(text), len(text))
    if text and not text.endswith('\n'):
        text += '\n'
    start = len(text)
    text = text + block
    _write_source(db, index, text)
    return text, (start, len(text))


def _bind(db, index, text, name, span, alts, burst, book_quote):
    """Attach the accepted quote to a scene that has player text to compile."""
    from . import kit_scenes
    from .kit_adventure import IngestError, _write_json, compile_location, folder_for
    key = _containing(index, span[0])
    compiled = None
    if key is not None:
        body = (index['locations'][key].get('body') or span)
        narrowed = (max(span[0], body[0]), min(span[1], body[1]))
        if narrowed[1] <= narrowed[0]:
            narrowed = (body[0], body[1])
        try:
            compiled = compile_location(db, key, neighbours=False, span=narrowed)
            room = json.loads(open(compiled['room'], encoding='utf-8').read())
            page_slice = text[span[0]:span[1]]
            # A playable box with no trigger, while this span names a creature, is hollow.
            # Rebuild so the designed pressure is in the scene and still not spoken.
            if not _playable(room, burst) or (not room.get('triggers') and _pressure(page_slice, book_quote)):
                compiled = None
        except (IngestError, OSError, ValueError, KeyError):
            compiled = None
    if compiled is None:
        block = _clean_body(book_quote)
        page_slice = text[span[0]:span[1]]
        from .kit_adventure import _creatures, _sentence_around
        seen_extra = set()
        for creature in _creatures(page_slice, 0, index.get('stat_blocks') or {}):
            sent = normalize(_sentence_around(page_slice, creature['mention_offset']))
            if not sent or _unsafe(sent) or _contiguous(sent, book_quote) or sent in seen_extra:
                continue
            seen_extra.add(sent)
            block += sent + '\n'
        text, span = _append_body(db, index, text, block)
        used = {loc.get('letter') for loc in (index.get('locations') or {}).values()}
        letter = next((ch for ch in 'ABCDEFGH' if ch not in used), 'A')
        key = _emit_scene(index, text, name, span, letter)
        _write_json(folder_for(db) / 'index.json', index)
        compiled = compile_location(db, key, neighbours=False, span=span)
        room = json.loads(open(compiled['room'], encoding='utf-8').read())
        if not _playable(room, burst):
            raise IngestError(['the opening has no player text to compile'])
    numbered = [loc for loc in (index.get('locations') or {}).values() if loc.get('type') != 'scene']
    if not numbered:
        used = {loc.get('letter') for loc in index['locations'].values()}
        for item in alts:
            if item['title'].casefold() == name.casefold() or item.get('quote') and _marked(item.get('quote')):
                continue
            letter = next((ch for ch in 'ABCDEFGH' if ch not in used), None)
            if letter is None:
                break
            quote = item.get('quote') or ''
            if not quote:
                continue
            block = _clean_body(quote)
            text, sib = _append_body(db, index, text, block)
            _emit_scene(index, text, item['title'], sib, letter)
            used.add(letter)
    index['start'] = key
    kit_scenes.finish(index, text)
    for item in index.get('starts') or []:
        item['default'] = item.get('id') == key
        if _marked(item.get('line') or ''):
            item['default'] = False
    _write_json(folder_for(db) / 'index.json', index)
    return key, compiled


def accept(db, reply):
    """Validate one skim. Failure returns the early-title picker and opens nothing."""
    from .kit_adventure import _load
    index, text = _load(db)
    data = _read(db)
    expanded = bool(data.get('expanded'))
    bounds = page_bounds(text)
    count = len(bounds)
    if not isinstance(reply, dict):
        return _reject(db, ['the skim reply must be one JSON object'], [], expanded)
    if reply.get('expand') is True and not str(reply.get('burst') or '').strip():
        if expanded:
            wider, _at, _to = _window_text(text, 1, window_end(count, True))
            return _reject(db, ['the skim window expands once'], _filter_alts(
                reply.get('alt_starts'), wider, window_end(count, True)), True)
        data['expanded'] = True
        data['status'] = 'expanded'
        _write(db, data)
        return {
            'stage': 'skim_expanded', 'expanded': True, 'skim_request': request_for(db),
            'table_line': LANDING, 'opened_room': None, 'advanced': False,
        }
    extra = set(reply) - set(KEYS) - {'expand'}
    problems = []
    if extra:
        problems.append('skim reply has keys Python did not ask for')
    end_page = window_end(count, expanded)
    # A quote past the first window consumes the one expansion. Past that, refuse.
    page_end = reply.get('page_end')
    page_start = reply.get('page_start')
    if isinstance(page_end, int) and not isinstance(page_end, bool) and page_end > FIRST_WINDOW:
        if expanded and page_end > FIRST_WINDOW + EXPAND_ONCE:
            problems.append('the skim window expands once')
        elif not expanded and page_end > FIRST_WINDOW + EXPAND_ONCE:
            problems.append('the skim window expands once')
        elif not expanded:
            expanded = True
            end_page = window_end(count, True)
    window, win_at, _win_to = _window_text(text, 1, end_page)
    alts = _filter_alts(reply.get('alt_starts'), window, end_page)
    burst = reply.get('burst')
    quote = reply.get('source_quote')
    name = reply.get('design_start_name')
    if not isinstance(burst, str) or not burst.strip():
        problems.append('burst is missing')
    if not isinstance(quote, str) or not quote.strip():
        problems.append('source_quote is missing')
    if not isinstance(name, str) or not normalize(name):
        problems.append('design_start_name is missing')
    if not isinstance(page_start, int) or isinstance(page_start, bool) or page_start < 1:
        problems.append('page_start is outside the skim window')
    if not isinstance(page_end, int) or isinstance(page_end, bool) or page_end < 1:
        problems.append('page_end is outside the skim window')
    if problems:
        return _reject(db, problems, alts, expanded)
    if page_start > page_end or page_end > end_page or page_start > end_page:
        return _reject(db, ['pages are outside the skim window'], alts, expanded)
    page_text, page_at, page_to = _window_text(text, page_start, page_end)
    found = find_quote(page_text, quote)
    if found is None:
        return _reject(db, ['source_quote is not in the skim window'], alts, expanded)
    book_quote, how = found
    if not _contiguous(burst, book_quote) and find_quote(book_quote, burst) is None:
        return _reject(db, ['burst is not in source_quote'], alts, expanded)
    if find_quote(window, name) is None and not _contiguous(name, window):
        return _reject(db, ['design_start_name is not in the skim window'], alts, expanded)
    if _unsafe(burst) or _unsafe(book_quote):
        return _reject(db, ['the burst quotes a tip, a secret, or a note to the DM'], alts, expanded)
    span_text = _opening_span(page_text, book_quote) or book_quote
    spoken, remainder = _split_burst(span_text, burst)
    if not spoken:
        spoken = normalize(burst)
        remainder = _split_burst(span_text, spoken)[1]
    if len(_words(spoken)) > BURST_WORDS:
        return _reject(db, ['burst is over %d words' % BURST_WORDS], alts, expanded)
    if not _sentence_bounded(spoken):
        return _reject(db, ['burst must end on a sentence'], alts, expanded)
    # Anchor on the quote, not the top of the page, so a credits scene in front
    # of the read-aloud is not the scene we try to compile.
    span_start = page_at + _anchor(page_text, book_quote)
    # Keep a leading "> " on that line. Starting at the first word drops the mark
    # and the next DM sentence is spoken as if it were the box.
    line_at = text.rfind('\n', 0, span_start)
    span_start = 0 if line_at < 0 else line_at + 1
    span_end = _clip(text, span_start + 1, page_to)
    if span_end <= span_start:
        span_end = page_to
    try:
        key, compiled = _bind(db, index, text, normalize(name), (span_start, span_end), alts, spoken, book_quote)
    except Exception as exc:
        return _reject(db, ['the opening could not be bound: %s' % exc], alts, expanded)
    handoff = _handoff(spoken + ' ' + book_quote, name)
    stored = {
        'status': 'accepted', 'burst': spoken, 'source_quote': book_quote,
        'remainder': remainder, 'match': how, 'page_start': page_start,
        'page_end': page_end, 'alt_starts': alts, 'design_start_name': normalize(name),
        'scene_key': key, 'room': compiled.get('room'), 'room_id': compiled.get('room_id'),
        'handoff': handoff, 'expanded': expanded, 'burst_spoken': False,
        'table_line': READY_LINE,
    }
    if data.get('sheet'):
        stored['sheet'] = data['sheet']
    _write(db, stored)
    return {
        'stage': 'skim_accepted', 'table_line': READY_LINE, 'design_start_name': stored['design_start_name'],
        'scene_key': key, 'room': compiled.get('room'), 'room_id': compiled.get('room_id'),
        'page_start': page_start, 'page_end': page_end, 'burst_words': len(_words(spoken)),
        'alt_starts': alts, 'expanded': expanded, 'advanced': False,
        'handoff': handoff,
    }


def peek_burst(db):
    return (_read(db).get('burst') or '').strip()


def opening_screen(db, source, *, honor_burst=True):
    """A reason the opening must not be spoken, or None when player fiction is there.

    A safe validated burst may be spoken. A room whose text is only DM prep, secrets,
    a synopsis, or mechanics may not, and loading a character does not make it a pass.
    """
    if honor_burst:
        burst = peek_burst(db)
        if burst and not _unsafe(burst):
            return None
        if burst and _unsafe(burst):
            return 'burst'
    texts = []
    safe = False
    for fact in ((source or {}).get('facts') or {}).values():
        if not isinstance(fact, dict):
            continue
        text = fact.get('text')
        if not isinstance(text, str) or not text.strip():
            continue
        texts.append(text)
        if fact.get('visible') and not _unsafe(text):
            safe = True
    if texts and not safe:
        return 'room'
    return None


def screen_failed(db):
    return bool(_read(db).get('screen_failed'))


def refused_start(db):
    """The sheet can stay noted. The opening is not committed, and the picker stays.

    A safe burst that was already accepted is left alone. Naming a DM title does not
    erase it and does not speak that title.
    """
    data = _read(db)
    alts = [item for item in (data.get('alt_starts') or [])
            if item.get('quote') and not _unsafe(item.get('quote') or '')]
    safe_burst = data.get('status') == 'accepted' and bool(data.get('burst')) and not _unsafe(data.get('burst'))
    if not safe_burst:
        data['status'] = 'rejected'
        data['screen_failed'] = True
        data['burst_spoken'] = False
        data['table_line'] = picker_line(alts)
        data['alt_starts'] = alts
        _write(db, data)
    elif alts != (data.get('alt_starts') or []):
        data['alt_starts'] = alts
        _write(db, data)
    line = picker_line(alts) or data.get('table_line') or ''
    return {
        'stage': 'pick_start', 'committed': False, 'opened_room': None,
        'character_loaded': False, 'sheet': data.get('sheet'), 'sheet_kept': bool(data.get('sheet')),
        'places': [{'pick': item.get('title'), 'line': item.get('title'), 'page': item.get('page')}
                   for item in alts],
        'start_picker': {'table_line': line, 'places': alts},
        'table_line': line,
        'spoken': None,
        'screen_failed': True,
    }


def awaits_yes(db, room_id):
    data = _read(db)
    return bool(data.get('status') == 'accepted' and data.get('room_id') == room_id
                and not data.get('burst_spoken'))


def opening_line(db):
    """The validated burst plus a mode handoff. The rest of the quote stays frozen."""
    data = _read(db)
    if data.get('status') != 'accepted':
        return None
    burst = (data.get('burst') or '').strip()
    if not burst or _unsafe(burst):
        data['screen_failed'] = True
        _write(db, data)
        return None
    handoff = data.get('handoff') or "Say what you do."
    data['burst_spoken'] = True
    _write(db, data)
    spoken = 'Narrator: %s' % burst
    if '?' not in spoken:
        spoken += '\nKit: %s' % handoff
    return spoken


def release(runtime, action):
    """'Go on' speaks the next chunk of the same validated span. It does not echo the player."""
    if not _GO_ON.match(normalize(action)):
        return None
    try:
        path = runtime.path
        revision, state = runtime.load()
    except Exception:
        return None
    if (state.get('combat') or {}).get('status') == 'running':
        return None
    data = _read(path)
    if data.get('status') != 'accepted':
        return None
    if not data.get('burst_spoken'):
        # The burst was never shown. Speaking it is the first chunk, not a social line.
        spoken = opening_line(path)
        if not spoken:
            return None
        events = [{'type': 'beat', 'tags': ['read_on'],
                   'evidence': 'The validated opening, spoken because they said go on.'}]
        committed = runtime.commit('read-%s' % revision, revision, events)
        return {'stage': 'read_on', 'committed': True, 'calls': 1, 'spoken': spoken,
                'public_event': data.get('burst') or '', 'revision': committed}
    rest = (data.get('remainder') or '').strip()
    if not rest or _unsafe(rest):
        spoken = "Kit: That's the span. What do you do?"
        chunk = ''
        data['remainder'] = ''
    else:
        chunk, left = _take(rest, BURST_WORDS)
        while chunk and _unsafe(chunk) and left:
            chunk, left = _take(left, BURST_WORDS)
        if _unsafe(chunk):
            chunk, left = '', ''
        data['remainder'] = left
        if not chunk:
            spoken = "Kit: That's the span. What do you do?"
        else:
            hand = 'Go on for the rest, or say what you do.' if left else (
                data.get('handoff') or 'Say what you do.')
            spoken = 'Narrator: %s\nKit: %s' % (chunk, hand)
    _write(path, data)
    events = [{'type': 'beat', 'tags': ['read_on'],
               'evidence': 'The next sentences of the validated opening span.'}]
    committed = runtime.commit('read-%s' % revision, revision, events)
    return {'stage': 'read_on', 'committed': True, 'calls': 1, 'spoken': spoken,
            'public_event': chunk or "That's the span.", 'revision': committed}


def lookup_beat(runtime, action):
    """A page lookup is one Kit line, not the player's words said back."""
    if not _LOOKUP.search(str(action or '')):
        return None
    try:
        path = runtime.path
        revision, _state = runtime.load()
    except Exception:
        return None
    if not _path(path).is_file() and not ( _read(path) ):
        return None
    spoken = 'Kit: Give me a second, checking the page.'
    events = [{'type': 'beat', 'tags': ['lookup'],
               'evidence': 'The player asked for the page. Nothing in the fiction changed.'}]
    committed = runtime.commit('look-%s' % revision, revision, events)
    return {'stage': 'lookup', 'committed': True, 'calls': 1, 'spoken': spoken,
            'public_event': 'Checking the page.', 'revision': committed}


def take_speak_now(db):
    """True once, when a picked title should be spoken immediately."""
    data = _read(db)
    if not data.get('speak_now'):
        return False
    data['speak_now'] = False
    _write(db, data)
    return True


def open_title(db, token):
    """A picker title becomes that scene's player fiction. Secrets are not a start."""
    from .kit_adventure import IngestError
    data = _read(db)
    want = normalize(token).casefold()
    if not want:
        return None
    chosen = None
    for alt in data.get('alt_starts') or []:
        title = normalize(alt.get('title') or '').casefold()
        if title == want or title.endswith(' ' + want):
            chosen = alt
            break
    if chosen is None:
        return None
    quote = chosen.get('quote') or ''
    if not quote or _unsafe(quote):
        raise IngestError(['%s is not player fiction' % chosen.get('title')])
    page = chosen.get('page') or 1
    done = accept(db, {
        'burst': quote, 'source_quote': quote, 'page_start': page, 'page_end': page,
        'alt_starts': data.get('alt_starts') or [],
        'design_start_name': chosen.get('title'),
    })
    if done.get('stage') != 'skim_accepted':
        raise IngestError(done.get('problems') or ['that title did not open'])
    fresh = _read(db)
    fresh['speak_now'] = True
    _write(db, fresh)
    return {
        'room': done['room'], 'room_id': done['room_id'], 'location': done['scene_key'],
        'pick': chosen.get('title'), 'line': chosen.get('title'), 'starts': [],
        'speak_now': True,
    }


def _note_sheet(db, sheet_path):
    if not sheet_path:
        return
    data = _read(db)
    data['sheet'] = str(sheet_path)
    _write(db, data)


def player_start(db, sheet_path=None, table=None):
    """After a PDF this session, never the empty lobby. A sheet stays with the save."""
    _note_sheet(db, sheet_path)
    data = _read(db)
    sheet = str(sheet_path) if sheet_path else data.get('sheet')
    if data.get('status') == 'accepted' and data.get('room') and sheet:
        from .kit_agent import start_session
        opened = start_session(str(db), sheet, room=data['room'], table=table)
        opened['table_line'] = READY_LINE
        opened['awaiting_yes'] = True
        return opened
    if data.get('status') == 'accepted':
        return {
            'stage': 'awaiting_sheet', 'committed': False, 'opened_room': None,
            'character_loaded': False, 'sheet': sheet, 'sheet_kept': bool(sheet),
            'table_line': "We're set. Default is the book's start. Hand me the sheet, then Yes. begins.",
            'design_start_name': data.get('design_start_name'), 'scene_key': data.get('scene_key'),
        }
    if data.get('status') == 'rejected':
        alts = data.get('alt_starts') or []
        from .kit_campaign import book_starts
        return {
            'stage': 'pick_start', 'committed': False, 'opened_room': None,
            'character_loaded': False, 'sheet': sheet, 'sheet_kept': bool(sheet),
            'places': [{'pick': item.get('title'), 'line': item.get('title'), 'page': item.get('page')}
                       for item in alts],
            'start_picker': {'table_line': data.get('table_line') or picker_line(alts), 'places': alts},
            'table_line': data.get('table_line') or picker_line(alts),
            'executable_starts': book_starts(db),
        }
    from .kit_campaign import book_starts
    return {
        'stage': 'awaiting_skim', 'committed': False, 'opened_room': None,
        'character_loaded': False, 'sheet': sheet, 'sheet_kept': bool(sheet),
        'table_line': LANDING, 'skim_request': request_for(db),
        'executable_starts': book_starts(db),
    }


def _replay(source, area, text):
    """True when this sentence is the opening line, not a later Check row."""
    folded = normalize(text).casefold()
    visible = _area_facts(source, area, True)
    if not folded or not visible:
        return False
    opener = visible[0].casefold()
    return folded == opener or folded in opener


def _crumb_rows(source, area):
    rows = []
    for fact in ((source or {}).get('facts') or {}).values():
        if not isinstance(fact, dict) or fact.get('area') != area:
            continue
        if not str(fact.get('row') or '').startswith(('check', 'find')):
            continue
        text = normalize(fact.get('text') or '')
        if text and not _marked(text) and not _replay(source, area, text):
            rows.append(text)
    return rows


def success_line(source, area, skill_name, cited):
    """A high check speaks a new crumb or a fork. Never the opening, a tip, or 'comes up clean'."""
    rows = _crumb_rows(source, area)
    cited = normalize(cited)
    if cited and not _marked(cited) and not _replay(source, area, cited) and cited not in rows:
        rows.insert(0, cited)
    if rows:
        line = 'The %s check turns up this: %s' % (skill_name, rows[0])
    else:
        line = _sensory_or_fork(source, area, skill_name)
    if 'comes up clean' in line.casefold():
        line = 'The %s check adds nothing new on the page. Which part of this are you on?' % skill_name
    return line


def _area_facts(source, area, visible):
    out = []
    for fact in ((source or {}).get('facts') or {}).values():
        if not isinstance(fact, dict) or fact.get('area') != area:
            continue
        if bool(fact.get('visible')) != visible:
            continue
        text = normalize(fact.get('text') or '')
        if text and not _marked(text):
            out.append(text)
    return out


def _sensory_or_fork(source, area, skill_name):
    # Hidden sensory text is new. Visible lines are the opening, so they are not a crumb.
    hidden = [text for text in _area_facts(source, area, False) if not _marked(text)]
    sensory = [text for text in hidden if _SENSORY.search(text)]
    if sensory:
        return 'The %s check turns up this: %s' % (skill_name, sensory[0])
    if len(hidden) >= 2:
        return '%s — or %s. Which do you mean?' % (hidden[0], hidden[1])
    return 'The %s check adds nothing new on the page. Which part of this are you on?' % skill_name
