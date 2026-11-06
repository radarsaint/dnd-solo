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
    'Python checks the quote as a contiguous substring of its own page extract. '
    'A paraphrase is refused. On a refusal, say the picker. Do not open a later room.'
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


def normalize(text):
    """Whitespace, soft hyphens, and a wrapped hyphen. Not a paraphrase."""
    text = (text or '').replace('\u00ad', '')
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('>', ' ')
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
    return bool(_MARK.search(normalize(text)))


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


def _filter_alts(alts, window, end_page):
    """Early titles whose page is inside the window and whose words are in that extract."""
    kept = []
    seen = set()
    for item in alts or []:
        title = _title_of(item)
        page = item.get('page') if isinstance(item, dict) else None
        if not title or not isinstance(page, int) or isinstance(page, bool):
            continue
        if page < 1 or page > end_page:
            continue
        if not _contiguous(title, window):
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append({'title': title, 'page': page})
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


def _bind(db, index, text, name, span, alts):
    """Attach the accepted quote to a scene id. Numbered places are optional."""
    from . import kit_scenes
    from .kit_adventure import _write_json, compile_location, folder_for
    key = _containing(index, span[0])
    numbered = [loc for loc in (index.get('locations') or {}).values() if loc.get('type') != 'scene']
    if key is not None:
        body = (index['locations'][key].get('body') or span)
        span = (max(span[0], body[0]), min(span[1], body[1]))
        if span[1] <= span[0]:
            span = (body[0], body[1])
    if key is None:
        used = {loc.get('letter') for loc in (index.get('locations') or {}).values()}
        letter = next((ch for ch in 'ABCDEFGH' if ch not in used), 'A')
        key = _emit_scene(index, text, name, span, letter)
    if not numbered:
        used = {loc.get('letter') for loc in index['locations'].values()}
        for item in alts:
            if item['title'].casefold() == name.casefold():
                continue
            letter = next((ch for ch in 'ABCDEFGH' if ch not in used), None)
            if letter is None:
                break
            # A sibling scene named by the host, not compiled and not opened.
            offset = text.casefold().find(item['title'].casefold())
            if offset < 0:
                continue
            _emit_scene(index, text, item['title'], (offset, offset + len(item['title'])), letter)
            used.add(letter)
    index['start'] = key
    kit_scenes.finish(index, text)
    for item in index.get('starts') or []:
        item['default'] = item.get('id') == key
    _write_json(folder_for(db) / 'index.json', index)
    compiled = compile_location(db, key, neighbours=False, span=span)
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
    words = _words(quote)
    if not words:
        return _reject(db, ['source_quote is not in the page extract'], alts, expanded)
    pattern = r'\W+'.join(re.escape(word) for word in words)
    match = re.search(pattern, page_text, re.I)
    if match is None:
        return _reject(db, ['source_quote is not a contiguous substring of the page extract'], alts, expanded)
    end = match.end()
    while end < len(page_text) and page_text[end] in '.!?"\')]}':
        end += 1
    book_quote = normalize(page_text[match.start():end])
    if not _contiguous(burst, book_quote):
        return _reject(db, ['burst is not a contiguous substring of source_quote'], alts, expanded)
    if not _contiguous(name, window):
        return _reject(db, ['design_start_name is not in the skim window'], alts, expanded)
    if _marked(burst) or _marked(book_quote):
        return _reject(db, ['the burst quotes a tip, a secret, or a note to the DM'], alts, expanded)
    spoken, _rest = _split_burst(book_quote, burst)
    if len(_words(spoken)) > BURST_WORDS:
        return _reject(db, ['burst is over %d words' % BURST_WORDS], alts, expanded)
    if not _sentence_bounded(spoken):
        return _reject(db, ['burst must end on a sentence'], alts, expanded)
    abs_quote_end = page_at + match.end()
    span_start = page_at + match.start()
    # Keep the line's read-aloud mark. Starting mid-line drops it and the
    # following DM notes get spoken as if they were the box.
    line_at = text.rfind('\n', 0, span_start)
    span_start = 0 if line_at < 0 else line_at + 1
    span_end = _clip(text, abs_quote_end, page_to)
    if span_end < abs_quote_end:
        span_end = abs_quote_end
    try:
        key, compiled = _bind(db, index, text, normalize(name), (span_start, span_end), alts)
    except Exception as exc:
        return _reject(db, ['the opening could not be bound: %s' % exc], alts, expanded)
    handoff = _handoff(spoken + ' ' + book_quote, name)
    stored = {
        'status': 'accepted', 'burst': spoken, 'source_quote': book_quote,
        'remainder': _split_burst(book_quote, spoken)[1], 'page_start': page_start,
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
    if not burst:
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
    if not _GO_ON.match(str(action or '')):
        return None
    try:
        path = runtime.path
        revision, state = runtime.load()
    except Exception:
        return None
    if (state.get('combat') or {}).get('status') == 'running':
        return None
    data = _read(path)
    if data.get('status') != 'accepted' or not data.get('burst_spoken'):
        return None
    rest = (data.get('remainder') or '').strip()
    if not rest:
        return None
    chunk, left = _take(rest, BURST_WORDS)
    if not chunk:
        return None
    data['remainder'] = left
    _write(path, data)
    if left:
        hand = 'Go on for the rest, or say what you do.'
    else:
        hand = data.get('handoff') or 'Say what you do.'
    spoken = 'Narrator: %s\nKit: %s' % (chunk, hand)
    events = [{'type': 'beat', 'tags': ['read_on'],
               'evidence': 'The next sentences of the validated opening span.'}]
    committed = runtime.commit('read-%s' % revision, revision, events)
    return {'stage': 'read_on', 'committed': True, 'calls': 1, 'spoken': spoken,
            'public_event': chunk, 'revision': committed}


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


def success_line(source, area, skill_name, cited):
    """A high check speaks a crumb or a fork from this span. Never a bare 'comes up clean'."""
    cited = normalize(cited)
    if cited and not _marked(cited):
        line = 'The %s check turns up this: %s' % (skill_name, cited)
    else:
        line = _sensory_or_fork(source, area, skill_name)
    if line.strip().casefold() in (
            'the %s check comes up clean.' % skill_name, 'comes up clean'):
        line = 'The %s check adds nothing new on the page. Which part of this are you on?' % skill_name
    if 'comes up clean' in line.casefold() and cited.casefold() not in line.casefold():
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
    visible = _area_facts(source, area, True)
    sensory = [text for text in visible if _SENSORY.search(text)]
    if sensory:
        return 'The %s check turns up this: %s' % (skill_name, sensory[0])
    hidden = _area_facts(source, area, False)
    sensory = [text for text in hidden if _SENSORY.search(text)]
    if sensory:
        return 'The %s check turns up this: %s' % (skill_name, sensory[0])
    if len(visible) >= 2:
        return '%s — or %s. Which do you mean?' % (visible[0], visible[1])
    return 'The %s check adds nothing new on the page. Which part of this are you on?' % skill_name
