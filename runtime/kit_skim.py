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
import unicodedata
from collections import Counter
from pathlib import Path

from .kit_adventure import folder_for

# How many pages the host reads before anyone is asked to begin. Not a page number
# in a book: the first look, then one longer look if that window has no playable start.
FIRST_WINDOW = 10
EXPAND_ONCE = 8
BURST_WORDS = 100
PICK_MAX = 4
KEYS = ('burst', 'source_quote', 'page_start', 'page_end', 'alt_starts', 'design_start_name', 'scene')

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
    r"\b(?:check the page|look that up|look up|what does the book say|on the page)\b"
    r"|\bkit\b[^?\n]{0,80}\?",
    re.I)
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
# A note to the DM that can sit in the same span as a boxed line. Player fiction
# does not instruct the table, name the patron's orders, or describe a procedure.
_DM_NOTE = re.compile(
    r'\bintroduc'
    r'|\bpatrons?\b'
    r'|\bmarching\b'
    r'|\bwatch order\b'
    r'|\btravel pace\b'
    r'|\btracking\b'
    r'|\btrack (?:the|their|a)\b'
    r'|\bprocedures?\b'
    r'|\broleplaying\b'
    r'|\bfor the dm\b'
    r'|\bbackground\b'
    r'|\byears ago\b'
    r'|\blong ago\b'
    r'|\byou (?:should|must|need to|decide)\b'
    r'|\byou (?:may|might) (?:want|decide|award|give|tell)\b'
    r'|\b(?:ask|tell|have|let|allow|determine|establish)\s+'
    r'(?:the\s+)?(?:players|characters|party|each)\b'
    r'|\b(?:each|the)\s+players\b'
    r'|\beach (?:character|player)\b'
    r'|\binitiative\b'
    r'|\b(?:if|when)\s+(?:a\s+|the\s+)?(?:fight|combat|battle)\b'
    r'|\bon a (?:success|failure|hit|miss)\b'
    r'|\blater in the (?:adventure|chapter|module)\b'
    r'|\bforeshadow'
    r'|\b(?:ability|skill|group) checks?\b'
    r'|\(\s*(?:perception|investigation|survival|insight|athletics|acrobatics|stealth)\s*\)'
    r"|\b(?:do not|don't)\s+(?:tell|reveal|share|read)\b"
    r'|\bunknown to\b'
    r'|\bsecretly\b'
    r"|\bwhat they (?:don't|do not) know\b"
    r'|\bin reality\b'
    r'|\bthe truth is\b'
    r'|\badventure hooks?\b'
    r'|\bthis encounter\b'
    r'|\bbelow is\b'
    r'|\bsee (?:area|chapter|page)\b'
    r'|\bnpcs?\b',
    re.I)
# Go on only. A street box may say "you may" or "long ago". These still end a read.
_GO_EXTRA = re.compile(
    r'\bplayers?\b'
    r'|\btheir own\b'
    r'|\bconcoct'
    r'|\bbackstor'
    r'|\bcome up with\b'
    r'|\bmake up (?:a |an |their )'
    r'|\bcharacter (?:creation|setup|background)'
    r'|\bsurprise round\b'
    r'|\bcombat\b'
    r'|\btracking\b'
    r'|\b(?:attack|damage) rolls?\b'
    r'|\bhit points\b',
    re.I)
_META = re.compile(
    r'\b(?:trademark|copyright|synopsis|credits?|legal notice|published by|'
    r'level advancement|levels? up|experience points|\bxp\b)\b',
    re.I)
_QUOTE_HARD = re.compile(
    r'\bDC\s*\d+\b'
    r'|\bhit points\b'
    r'|\bthe players\b'
    r'|\bplayers?\b'
    r'|\bsecret\b'
    r'|\bintroduc'
    r'|\bpatrons?\b'
    r'|\bmarching\b'
    r'|\btracking\b'
    r'|\bprocedures?\b'
    r'|\b(?:ability|skill|group) checks?\b'
    r'|\(\s*(?:perception|investigation|survival|insight|athletics|acrobatics|stealth)\s*\)'
    r'|\bif the characters\b'
    r'|\bsecretly\b'
    r'|\bthe truth is\b'
    r'|\bxp\b',
    re.I)
_SCENE_VERB = re.compile(
    r'\b(?:stops?|stands?|walks?|sits?|lies?|rises?|falls?|hangs?|glows?|creaks?|'
    r'waits?|waves?|steps?|hears?|sees?|rains?|gutters?|closes?|opens?|leads?|'
    r'calls?|bumps?|rolls?|rides?|goes|flies|circles)\b',
    re.I)
_NOT_A_START = re.compile(
    r'\b(?:this (?:adventure|module|book)|trademark|copyright|credits|synopsis|'
    r'level|advancement|experience|backstory|designed for|published|'
    r'a party of|character levels?)\b',
    re.I)
_LATER = re.compile(r'(?m)^(?:area\s+)?[A-Z]?\d{1,3}[a-z]?\s*[.:]\s+\S')
_NOTICE = re.compile(r'\b(?:perception|notice|notices|spot(?:s|ted)?|stealth)\b', re.I)
_ARRIVAL = re.compile(
    r'\b(?:wait(?:s|ing)?|ambush(?:es|ed)?|hid(?:e|es|ing)|step(?:s|ped)?|'
    r'attack(?:s|ed|ing)?|bar(?:s|red)?|surround(?:s|ed)?|leap(?:s|ed)?|spring(?:s|ing)?)\b',
    re.I)
_WARNING = re.compile(
    r'\b(?:common|sometimes|may be|might be|are known|in general|other monsters|beware)\b',
    re.I)
_CHILD = re.compile(r'\b(?:child|children|boys?|girls?)\b', re.I)
_FORK_STOP = frozenset(
    'that this with from they have been were when your into over under after before where '
    'what which there their about would could should then than them these those only just '
    'also more some such very once here still back down away even much many well'.split())
_LIGATURE = {
    '\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi', '\ufb04': 'ffl',
    '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2013': '-', '\u2014': '-',
}
OPENING_DONE = "That's the opening — what do you do?"
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
    'page_end, alt_starts, design_start_name, scene.\n'
    'burst is the first player-facing sentences only, at most %d words, ending on a '
    'sentence. source_quote is the verbatim span those sentences come from, copied '
    'from those pages, with no tip, DC, secret, reward instruction, or note to the DM. '
    'page_start and page_end are inside this window. '
    'alt_starts is 2 to 4 early titles in this same window, each {"title","page"}. '
    'No later keyed room and no climax. design_start_name is the heading the book '
    'uses for this start.\n'
    'scene is required for playable host interpretation: '
    '{"place":{"name":word_in_read_aloud,"quote":verbatim_read_aloud},'
    '"people":[{"id":lowercase_id,"name":literal_name,"quote":verbatim_presence,'
    '"visibility":"visible|hidden","kind":"person|creature",'
    '"goal":{"quote":verbatim_goal,"status":"established|conditional|inferred"}|null,'
    '"knowledge":[]}],"discoveries":[],"pressures":[]}. '
    'Each quote must be contiguous within this opening, not the book setup or later room. '
    'For a pressure use {"kind":"ambush|conversation|hazard|none",'
    '"quote":verbatim_encounter,"status":"conditional|established|inferred",'
    '"actors":[person_id],"activation":"entry|disturb|deferred"}. Do not choose DCs, damage, surprise, initiative, '
    'or player outcomes: those belong to the existing rules engine.\n'
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


def _match_tokens(text):
    """Words for a proof. Ligatures, marks, and hyphens fold the same way on both sides.

    The spoken line is not these tokens. A hyphen is a break, so a line-break hyphen
    does not glue two words into one token the quote does not have.
    """
    text = text or ''
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    for src, dst in _LIGATURE.items():
        text = text.replace(src, dst)
    text = re.sub(r'-+', ' ', text)
    text = normalize(text)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return [word.casefold() for word in re.findall(r"[A-Za-z0-9']+", text)]


def _ordered_ratio(have, want):
    """Most of the quote's content words, in order. A few extract mismatches still count."""
    content = [word for word in want if len(word) > 3]
    if len(content) < 6:
        return False
    pos = 0
    hit = 0
    for word in content:
        for index in range(pos, len(have)):
            if have[index] == word:
                hit += 1
                pos = index + 1
                break
    return hit >= 6 and hit * 5 >= len(content) * 4


def _ordered_near(have, want):
    """Content words in order, allowing one of them to be missing from the extract."""
    content = [word for word in want if len(word) > 3]
    if len(content) < 6:
        return False
    if _ordered_flex(have, content):
        return True
    for skip in range(len(content)):
        trial = content[:skip] + content[skip + 1:]
        if len(trial) >= 6 and _ordered_flex(have, trial):
            return True
    return False


def _ordered_loose(have, want):
    """Content words in order. One missing short word does not refuse a real line."""
    content = [word for word in want if len(word) > 3]
    if len(content) < 8 or content == list(want):
        return False
    return _ordered_flex(have, content)


def _ordered_flex(have, want):
    """True when want's words occur in order. A hyphen may join or split a word. Gaps allowed."""
    if not want:
        return False
    i = 0
    j = 0
    while i < len(want) and j < len(have):
        if have[j] == want[i]:
            i += 1
            j += 1
            continue
        acc = ''
        k = i
        joined = False
        while k < len(want) and len(acc) < len(have[j]):
            acc += want[k]
            k += 1
            if acc == have[j]:
                i, j, joined = k, j + 1, True
                break
        if joined:
            continue
        acc = ''
        k = j
        while k < len(have) and len(acc) < len(want[i]):
            acc += have[k]
            k += 1
            if acc == want[i]:
                i, j, joined = i + 1, k, True
                break
        if joined:
            continue
        j += 1
    return i == len(want)


def _local_cover(have, want):
    """True when every quote word sits in one short stretch of this extract.

    Column reading order and extract order can cross. The words still have to be
    here, and close together. A line from later pages is not in this stretch.
    """
    if len(want) < 6:
        return False
    if not any(len(word) >= 6 for word in want):
        return False
    need = Counter(want)
    if any(Counter(have)[word] < count for word, count in need.items()):
        return False
    got = Counter()
    missing = len(need)
    left = 0
    best = None
    for right, word in enumerate(have):
        if word in need:
            got[word] += 1
            if got[word] == need[word]:
                missing -= 1
        while missing == 0 and left <= right:
            width = right - left + 1
            best = width if best is None else min(best, width)
            old = have[left]
            if old in need:
                if got[old] == need[old]:
                    missing += 1
                got[old] -= 1
            left += 1
    if best is None:
        return False
    return best <= max(len(want) * 3, len(want) + 24)


def _reading_orders(page):
    """The page, each marked column, and a left-then-right read of a wide gap."""
    streams = list(column_streams(page))
    lefts, rights = [], []
    gapped = False
    for line in (page or '').split('\n'):
        parts = [part.strip() for part in re.split(r'\s{3,}|\t+', line.strip()) if part.strip()]
        if len(parts) >= 2:
            gapped = True
            lefts.append(parts[0])
            rights.append(' '.join(parts[1:]))
        elif parts:
            lefts.append(parts[0])
    if gapped:
        streams.append('\n'.join(lefts))
        streams.append('\n'.join(rights))
        streams.append('\n'.join(lefts + rights))
        streams.append('\n'.join(rights + lefts))
    return streams


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
    return _marked(cleaned) or bool(_SYNOPSIS.search(cleaned) or _DM_NOTE.search(cleaned))


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
    """(how) on one column or one page. Ordered is enough. A column may reorder the
    extract; the words still have to sit in this stream. Nothing is invented."""
    flex = _match_tokens(stream)
    width = len(want)
    if width and any(flex[index:index + width] == want for index in range(max(0, len(flex) - width + 1))):
        return 'contiguous'
    if _ordered_flex(flex, want) or _ordered_loose(flex, want) or _ordered_near(flex, want) or _ordered_ratio(flex, want):
        return 'ordered'
    if _local_cover(flex, want):
        return 'covered'
    return None


def find_quote(page_text, quote):
    """(clean text, how) when the quote's words are in this extract.

    Each page, each column, and a left-then-right reading are tried. Words in order
    are enough. A column may put the printed order and the extract order out of step;
    the words still have to sit together in this window. Nothing is invented.
    The spoken line is the quote, not the words that sat between its tokens.
    """
    want = _match_tokens(quote)
    if not want:
        return None
    pages = [page for page in (page_text or '').split('\f')] or ['']
    ordered = None
    streams = []
    for page in pages:
        streams.extend(_reading_orders(page))
    streams.append(page_text or '')
    for stream in streams:
        how = _search_stream(stream, want)
        if not how:
            continue
        if how == 'contiguous':
            return normalize(quote), how
        if ordered is None or (ordered[1] != 'ordered' and how == 'ordered'):
            ordered = (normalize(quote), how)
    return ordered


def _fiction_after(window, title):
    """Boxed player sentences under a heading. Unmarked prose is not a start."""
    want = _match_tokens(title)
    if not want:
        return ''
    lines = []
    for stream in _reading_orders(window):
        lines.append(stream.split('\n'))
    lines.append((window or '').split('\n'))
    for stream_lines in lines:
        started = False
        kept = []
        for line in stream_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if not started:
                if _ordered_flex(_match_tokens(stripped), want):
                    started = True
                continue
            if _heading_line(stripped):
                break
            if not stripped.startswith('>'):
                continue
            for sentence in _sentences(stripped.lstrip('>').strip()):
                from .kit_opening import player_line
                if not player_line(sentence):
                    continue
                kept.append(sentence)
                if len(kept) >= 2:
                    return ' '.join(kept)
        if kept:
            return ' '.join(kept)
    return ''


def _harvest_starts(window):
    """Early titles that open onto a safe sentence, when the host's list did not."""
    found = []
    seen = set()
    page = 1
    title = None
    for raw in re.split(r'(\f)', window or ''):
        if raw == '\f':
            page += 1
            title = None
            continue
        for line in raw.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            if _LATER.match(stripped.lstrip('>').strip()):
                title = None
                continue
            if _heading_line(stripped):
                title = stripped.lstrip('>').strip()
                if _bad_title(title) or _after_keyed(window, title):
                    title = None
                continue
            if not title or title.casefold() in seen or not stripped.startswith('>'):
                continue
            piece = stripped.lstrip('>').strip()
            for sentence in _sentences(piece):
                from .kit_opening import player_line
                if not player_line(sentence):
                    continue
                found.append({'title': title, 'page': page, 'quote': sentence})
                seen.add(title.casefold())
                title = None
                break
            if len(found) >= PICK_MAX:
                return found
    return found


def _filter_alts(alts, window, end_page):
    """Read-aloud blocks in the window. Front matter and later rooms are not starts."""
    from .kit_opening import read_aloud_picks
    return read_aloud_picks(window)[:PICK_MAX]


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


def _clauses(text):
    return [part.strip() for part in re.split(r'[.!?;:\n]+', text or '') if part.strip()]


def _headerish(text):
    """A running header glued into a line, not a sentence of the scene."""
    words = re.findall(r"[A-Za-z']+", text or '')
    if not words or len(words) > 8:
        return False
    caps = sum(1 for word in words if word.isupper() and len(word) > 1)
    return caps >= 2 and caps * 2 >= len(words)


def _blocks_quote(text):
    """Hard prep in most of the quote. One atmospheric word does not refuse a street line."""
    cleaned = normalize(text)
    if not cleaned:
        return True
    sentences = _sentences(cleaned) or [cleaned]
    bad = [sentence for sentence in sentences if _META.search(sentence) or _QUOTE_HARD.search(sentence)]
    if not bad:
        return False
    return len(bad) * 2 >= len(sentences)


def _playerish(text):
    """A sentence a player can be standing in. Synopsis, credits, and level notes are not."""
    cleaned = normalize(text)
    if not cleaned or _blocks_quote(cleaned) or _go_fail(cleaned):
        return False
    if len(_words(cleaned)) < 6:
        return False
    if _NOT_A_START.search(cleaned):
        return False
    if re.search(r'\byou\b', cleaned, re.I):
        return True
    return bool(_SCENE_VERB.search(cleaned))


def _bad_title(title):
    """A credit line, a level note, or a numbered later room is not a start."""
    text = (title or '').strip()
    if not text or _KEYED.match(text) or _LATER.match(text):
        return True
    return bool(_META.search(text) or _NOT_A_START.search(text) or re.search(r'\blevel\b', text, re.I))


def _after_keyed(window, title):
    """True when this title is a numbered room, or sits after one."""
    want = (title or '').strip().lower()
    if not want:
        return False
    seen_keyed = False
    for line in (window or '').split('\n'):
        stripped = line.strip()
        if _LATER.match(stripped):
            seen_keyed = True
            if want in stripped.lower():
                return True
        elif seen_keyed and want in stripped.lower() and _heading_line(stripped):
            return True
    return False


def _unread(rest, burst):
    """Sentences the opening has not already spoken."""
    kept = []
    burst_words = _words(burst)
    for sentence in _sentences(rest):
        if _contiguous(sentence, burst) or _contiguous(burst, sentence):
            continue
        words = _words(sentence)
        if len(words) >= 6 and len(burst_words) >= 6:
            span = 6
            if any(words[i:i + span] == burst_words[j:j + span]
                   for i in range(len(words) - span + 1)
                   for j in range(len(burst_words) - span + 1)):
                continue
        kept.append(sentence)
    return ' '.join(kept)


def _go_fail(text):
    """True when this next read is prep, a procedure, a header, or a rule."""
    cleaned = normalize(text)
    if not cleaned or _unsafe(cleaned) or _headerish(cleaned):
        return True
    if _GO_EXTRA.search(cleaned) or _META.search(cleaned):
        return True
    for clause in _clauses(cleaned):
        if _unsafe(clause) or _headerish(clause) or _GO_EXTRA.search(clause) or _META.search(clause):
            return True
    # A long block that never puts anyone in the scene is a note, not a box.
    # A named introduction of ordinary length is the scene, not that note.
    named = re.search(
        r'\b(?:Captain|Sergeant|Lieutenant|Commander|Lady|Lord|Sir|Dame|Master|Mistress)\s+[A-Z]',
        text or '')
    if len(_words(cleaned)) > 90 and not re.search(r'\byou\b', cleaned, re.I) and not named:
        return True
    return False


def _scene_line(text):
    """Unread player fiction. Prep fails. A named person in the scene does not."""
    if _go_fail(text):
        return False
    if _playerish(text):
        return True
    if re.search(
            r'\b(?:Captain|Sergeant|Lieutenant|Commander|Lady|Lord|Sir|Dame|Master|Mistress)\s+[A-Z]',
            text or ''):
        return True
    return bool(re.search(
        r'\b[A-Z][a-z]{2,}\s+(?:is|stands|steps|waits|says|calls|raises|greets|watches)\b',
        text or ''))


def _safe_box(text):
    """A boxed sentence that can be a start. Not a synopsis, a credit, or a rule."""
    cleaned = normalize(text)
    if not cleaned or _go_fail(cleaned) or _blocks_quote(cleaned):
        return False
    if _NOT_A_START.search(cleaned) or _META.search(cleaned):
        return False
    return len(_words(cleaned)) >= 6


def _player_sentences(text):
    """Sentences a player can hear. A DM note in the same span is dropped."""
    return [sentence for sentence in _sentences(text) if sentence and not _go_fail(sentence)]


def _read_on(text, limit):
    """(chunk, rest, stopped). The first line that fails the gate ends the read.

    Later player lines after that failure are not spoken. Skipping them was how
    a prep note and the header after it still reached the table.
    """
    sentences = _sentences(text)
    if not sentences and normalize(text):
        sentences = [normalize(text)]
    kept = []
    count = 0
    index = 0
    while index < len(sentences):
        sentence = sentences[index]
        if _go_fail(sentence) or not _scene_line(sentence):
            return ' '.join(kept).strip(), '', True
        words = len(_words(sentence))
        if kept and count + words > limit:
            break
        kept.append(sentence)
        count += words
        index += 1
        if count >= limit:
            break
    return ' '.join(kept).strip(), ' '.join(sentences[index:]).strip(), False


def _take(text, limit):
    """The next player-fiction chunk, at most `limit` words, and what stays frozen."""
    text = normalize(text)
    if not text:
        return '', ''
    sentences = _player_sentences(text)
    if not sentences:
        return '', ''
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
    # Drop the used sentences and any DM notes in front of what remains.
    rest_sentences = sentences[len(chunk):]
    return used, ' '.join(rest_sentences).strip()


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
            if sentence and not _go_fail(sentence) and not _blocks_quote(sentence)]
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
            if _go_fail(sentence) or _blocks_quote(sentence):
                # Prep ends the read. A named introduction is not prep.
                return ' '.join(base + extra).strip()
            if not _scene_line(sentence) or _contiguous(sentence, held):
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
            room = json.loads(Path(compiled['room']).read_text(encoding='utf-8'))
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
        room = json.loads(Path(compiled['room']).read_text(encoding='utf-8'))
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
        # The declared pages can be off by a blank or a cover. The words still
        # have to be in the skim window. Later pages are not searched.
        found = find_quote(window, quote)
        if found is not None:
            page_text = window
            page_at = win_at
            page_to = win_at + len(window)
    if found is None:
        return _reject(db, ['source_quote is not in the skim window'], alts, expanded)
    book_quote, how = found
    if not _contiguous(burst, book_quote) and find_quote(book_quote, burst) is None:
        return _reject(db, ['burst is not in source_quote'], alts, expanded)
    if find_quote(window, name) is None and not _contiguous(name, window):
        return _reject(db, ['design_start_name is not in the skim window'], alts, expanded)
    if _blocks_quote(burst):
        return _reject(db, ['the burst quotes a tip, a secret, or a note to the DM'], alts, expanded)
    span_text = _opening_span(page_text, book_quote) or book_quote
    spoken, remainder = _split_burst(span_text, burst)
    remainder = _unread(remainder, spoken)
    kept_rest = []
    for sentence in _sentences(remainder):
        if _go_fail(sentence):
            break
        if not _scene_line(sentence):
            continue
        kept_rest.append(sentence)
    remainder = ' '.join(kept_rest)
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
    from .kit_opening import build_beat, opening_text, _layout_stream
    if 'scene' in reply:
        from . import kit_scene_contract
        scoped = text[span_start:span_end]
        scene_problems = kit_scene_contract.validate(
            reply['scene'], scoped, spoken, _layout_stream(scoped))
        if scene_problems:
            return _reject(db, scene_problems, alts, expanded)
        from .kit_opening import fiction_lines
        beat = kit_scene_contract.build_beat(
            reply['scene'], spoken, name, fiction=fiction_lines(page_text, spoken))
    else:
        # Backward compatibility for existing host tests. The real host instruction
        # requires a scene: lexical inference is not an accepted new design.
        beat = build_beat(page_text, spoken, name)
    try:
        key, compiled = _bind(db, index, text, normalize(name), (span_start, span_end), alts, spoken, book_quote)
    except Exception as exc:
        return _reject(db, ['the opening could not be bound: %s' % exc], alts, expanded)
    handoff = _handoff(spoken + ' ' + book_quote, name)
    if not beat.get('source_verified'):
        _cast_people(compiled.get('room'), opening_text(page_text, spoken) or spoken)
    _stamp_beat(compiled.get('room'), beat)
    stored = {
        'status': 'accepted', 'burst': spoken, 'source_quote': book_quote,
        'remainder': remainder, 'match': how, 'page_start': page_start,
        'page_end': page_end, 'alt_starts': alts, 'design_start_name': normalize(name),
        'scene_key': key, 'room': compiled.get('room'), 'room_id': compiled.get('room_id'),
        'handoff': handoff, 'expanded': expanded, 'burst_spoken': False,
        'table_line': READY_LINE, 'beat': beat,
        **({'scene': reply['scene']} if beat.get('source_verified') else {}),
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


def _boxed_player(db, source):
    """Safe boxed lines in this room's source span. None when the span cannot be read.

    An empty list means the span has no player box. Promoted prose is not a box.
    """
    try:
        from .kit_labels import section_for_room
        from .kit_adventure import _load
        key = section_for_room(db, (source or {}).get('id'))
        if not key:
            return None
        index, text = _load(db)
        loc = (index.get('locations') or {}).get(key) or {}
        body = loc.get('body') or [0, 0]
        raw = text[int(body[0]):int(body[1])]
    except Exception:
        return None
    lines = []
    for line in raw.split('\n'):
        stripped = line.strip()
        if not stripped.startswith('>'):
            continue
        piece = stripped.lstrip('>').strip()
        if piece and not _blocks_quote(piece) and not _META.search(piece):
            lines.append(piece)
    return lines


def opening_screen(db, source, *, honor_burst=True):
    """A reason the opening must not be spoken, or None when player fiction is there.

    A validated burst may be spoken only in the room that contains it. Another scene
    whose text is DM prep, a secret, or unmarked prose is not an opening. Loading a
    character does not make it one.
    """
    visible = []
    for fact in ((source or {}).get('facts') or {}).values():
        if isinstance(fact, dict) and fact.get('visible') and isinstance(fact.get('text'), str):
            visible.append(fact['text'])
    safe = [line for line in visible if not _unsafe(line)]
    burst = peek_burst(db) if honor_burst else ''
    if burst and (_blocks_quote(burst) or _META.search(burst)):
        return 'burst'
    blob = ' '.join(safe or visible)
    if burst and blob and (_contiguous(burst, blob) or _contiguous(blob, burst)):
        return None
    boxed = _boxed_player(db, source)
    if boxed is not None and not boxed:
        return 'room'
    if visible and not safe:
        return 'room'
    return None


def landing_holds(db):
    """True while a skim is in hand and the opening has not been spoken.

    The rest of the book, and a label pass, wait. The landing does not.
    """
    data = _read(db)
    if not data or data.get('burst_spoken'):
        return False
    return data.get('status') in ('accepted', 'rejected', 'expanded')


def _stamp_beat(room_path, beat):
    """Goals and who may be spoken to, on the room. Tactics stay off this file."""
    path = Path(room_path) if room_path else None
    if path is None or not path.is_file() or not isinstance(beat, dict):
        return
    try:
        room = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return
    noun = beat.get('place_noun') or ''
    room['_opening_place'] = noun
    areas = room.setdefault('areas', {})
    here = room.get('starting_area') or 'here'
    if noun and noun != 'room' and isinstance(areas.get(here), dict):
        areas[here]['called'] = 'the ' + noun
    actors = room.setdefault('actors', {})
    ids = []
    verified = bool(beat.get('source_verified'))
    def stem(value):
        value = re.sub(r'\s+\d+$', '', str(value or '').casefold())
        value = re.sub(r'[^a-z0-9]+', '_', value).strip('_')
        return value[:-1] if value.endswith('s') else value
    unresolved = []
    for person in beat.get('people') or []:
        pid = person.get('id')
        if not pid:
            continue
        matches = ([key for key, actor in actors.items()
                    if key == pid or (verified and stem(actor.get('name')) == stem(person.get('name')))]
                   if verified else [pid] if pid in actors else [])
        # Source-attested speakers may be represented without a combat stat block.
        # Source-attested creatures without any book/SRD stat must not be invented.
        if verified and not matches and person.get('kind') == 'speaker':
            actors[pid] = {
                'name': person['name'], 'location': here,
                'status': 'hidden' if person.get('hidden') else 'alive',
                'visible': not person.get('hidden'), 'role': 'speaker',
            }
            matches = [pid]
        if verified and not matches:
            unresolved.append(pid)
        for key in matches:
            if key not in ids:
                ids.append(key)
            actor = actors.get(key)
            if not isinstance(actor, dict):
                continue
            if verified and actor.get('status') in ('alive', 'hidden'):
                actor['status'] = 'hidden' if person.get('hidden') else 'alive'
                actor['visible'] = not person.get('hidden')
            if person.get('goal'):
                actor['immediate_goal'] = person['goal']
                actor['motive'] = person.get('motive') or person['goal']
    room['_opening_people'] = ids
    if verified:
        room['_opening_unresolved_people'] = unresolved
    # A patron named only in the setup is not this beat's person.
    if ids:
        drop = [key for key, actor in actors.items()
                if key not in ids and isinstance(actor, dict) and not actor.get('stat_block')]
        for key in drop:
            actors.pop(key, None)
        kept = []
        for item in room.get('triggers') or []:
            if not isinstance(item, dict):
                continue
            waking = [key for key in item.get('actors') or [] if key in actors]
            if not waking:
                continue
            item = dict(item)
            item['actors'] = waking
            kept.append(item)
        if room.get('triggers') is not None:
            room['triggers'] = kept
    if verified:
        # A host-attested prospect is not an on-entry attack unless the source
        # interpretation explicitly supports that timing. Defer the existing
        # trigger instead of deleting its actors or inventing an outcome.
        room['_opening_verified'] = True
        room['_opening_pressures'] = list(beat.get('source_contract', {}).get('pressures') or ())
        room['_opening_discoveries'] = list(beat.get('discoveries') or ())
        immediate = any(p.get('activation') == 'entry' and p.get('kind') == 'ambush'
                        for p in room['_opening_pressures'])
        for trigger in room.get('triggers') or []:
            if isinstance(trigger, dict) and 'enter' in (trigger.get('on') or {}) and not immediate:
                trigger['_deferred'] = True
                trigger['starts_combat'] = False
                trigger['notice'] = False
    elif (beat.get('notice') or {}).get('holds'):
        for item in room.get('triggers') or []:
            if isinstance(item, dict) and 'enter' in (item.get('on') or {}):
                item['notice'] = True
    path.write_text(json.dumps(room, ensure_ascii=False), encoding='utf-8')


def _cast_people(room_path, text):
    """People, greeters, and creatures in this span become actors on the room."""
    from .kit_adventure import _GREET, _creatures, _introduced_names, _slug
    from .srd_creatures import CREATURES
    path = Path(room_path) if room_path else None
    if path is None or not path.is_file() or not text:
        return
    try:
        room = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return
    actors = room.setdefault('actors', {})
    here = room.get('starting_area') or 'here'
    changed = False
    for name in _introduced_names(text):
        key = _slug(name)
        if key in actors:
            actor = actors[key]
            if isinstance(actor, dict):
                actor.setdefault('immediate_goal', 'Answer whoever speaks to them here.')
                actor.setdefault('motive', 'They are in this scene.')
                changed = True
            continue
        actors[key] = {
            'name': name, 'location': here, 'status': 'alive', 'visible': True, 'role': 'speaker',
            'immediate_goal': 'Answer whoever speaks to them here.',
            'motive': 'They are in this scene.',
        }
        changed = True
    if _GREET.search(text or '') and not any(
            'greet' in (actor.get('name') or '').casefold()
            for actor in actors.values() if isinstance(actor, dict)):
        actors['greeter'] = {
            'name': 'Greeter', 'location': here, 'status': 'alive', 'visible': True,
            'role': 'speaker',
            'immediate_goal': 'Answer whoever speaks to them here.',
            'motive': 'They are in this scene.',
        }
        changed = True
    triggers = room.setdefault('triggers', [])
    have_trigger = {item.get('id') for item in triggers if isinstance(item, dict)}
    for creature in _creatures(text or '', 0, {}):
        name = creature.get('name') or ''
        key = _slug(name)
        if not key:
            continue
        sent = ''
        try:
            from .kit_adventure import _sentence_around
            sent = _sentence_around(text or '', creature.get('mention_offset') or 0)
        except Exception:
            sent = ''
        if _WARNING.search(sent) and not _ARRIVAL.search(sent):
            continue
        if sent and not _ARRIVAL.search(sent):
            continue
        if any(name.casefold() in (actor.get('name') or '').casefold()
               for actor in actors.values() if isinstance(actor, dict)):
            continue
        if key not in actors and name.casefold() in CREATURES:
            actors[key] = {
                'name': name.title(), 'location': here, 'status': 'hidden', 'visible': False,
                'stat_block': {'srd': name.casefold()},
                'immediate_goal': 'They are the pressure in this opening.',
                'motive': 'They are in this scene.',
            }
            changed = True
        trig = 'reveal_%s' % key
        if trig not in have_trigger and key in actors:
            triggers.append({
                'id': trig, 'on': {'enter': here}, 'actors': [key],
                'reveal': '%s reveals itself.' % name.title(),
            })
            have_trigger.add(trig)
            changed = True
        if _NOTICE.search(text or '') and trig in have_trigger:
            for item in triggers:
                if isinstance(item, dict) and item.get('id') == trig:
                    item['notice'] = True
    if _CHILD.search(text or '') and not any(
            'child' in (actor.get('name') or '').casefold()
            for actor in actors.values() if isinstance(actor, dict)):
        actors['children'] = {
            'name': 'Children', 'location': here, 'status': 'alive', 'visible': True,
            'role': 'speaker',
            'immediate_goal': 'Answer whoever speaks to them here.',
            'motive': 'They are in this scene.',
        }
        changed = True
    if changed:
        path.write_text(json.dumps(room, ensure_ascii=False), encoding='utf-8')


def _note_people(runtime, chunk):
    """A person named in the chunk just spoken is on stage for the next line."""
    data = _read(runtime.path)
    _cast_people(data.get('room'), chunk)
    from .kit_adventure import _introduced_names, _slug
    try:
        source = runtime.source()
    except Exception:
        return
    actors = source.setdefault('actors', {})
    here = None
    try:
        here = runtime.load()[1].get('area')
    except Exception:
        here = source.get('starting_area')
    for name in _introduced_names(chunk):
        key = _slug(name)
        if key not in actors:
            actors[key] = {
                'name': name, 'location': here or 'here', 'status': 'alive',
                'visible': True, 'role': 'speaker',
                'immediate_goal': 'Answer whoever speaks to them here.',
                'motive': 'They are in this scene.',
            }
    try:
        state_actors = runtime.load()[1].setdefault('actors', {})
    except Exception:
        state_actors = None
    if isinstance(state_actors, dict):
        for name in _introduced_names(chunk):
            key = _slug(name)
            state_actors.setdefault(key, {
                'name': name, 'location': here or 'here', 'status': 'alive', 'visible': True,
                'role': 'speaker',
                'immediate_goal': 'Answer whoever speaks to them here.',
                'motive': 'They are in this scene.',
            })


def fork_check(runtime, body):
    """A look or a search with no Check speaks the fork. It does not call a roll."""
    if (body or {}).get('kind') != 'check_request':
        return None
    try:
        source = runtime.source()
        revision, state = runtime.load()
    except Exception:
        return None
    if not str((source or {}).get('id') or '').startswith('adv-'):
        return None
    if any(event.get('type') in ('combat_state', 'trigger_fired') for event in body.get('events') or []):
        return None
    area = ((body.get('public_view') or {}).get('area')) or state.get('area')
    if _crumb_rows(source, area):
        return None
    hidden = [text for text in _area_facts(source, area, False) if not _unsafe(text) and _SENSORY.search(text)]
    if hidden:
        return None
    question = _fork_question(source, area)
    spoken = 'Kit: %s' % question
    events = [{'type': 'beat', 'tags': ['clarify'],
               'evidence': 'No Check or Find in this span. One question, no roll.'}]
    committed = runtime.commit('fork-%s' % revision, revision, events)
    return {'stage': 'clarify', 'committed': True, 'calls': 1, 'spoken': spoken,
            'public_event': question, 'revision': committed}


def rescue_roll(runtime, action):
    """A strong roll with no call waiting speaks a crumb or the fork. It does not stall."""
    text = str(action or '')
    if not re.search(r'\b\d{1,2}\b', text):
        return None
    if not re.search(r'\b(?:perception|investigation|insight|survival|check|search|look|roll)\b', text, re.I):
        return None
    try:
        source = runtime.source()
        revision, state = runtime.load()
    except Exception:
        return None
    if not str((source or {}).get('id') or '').startswith('adv-'):
        return None
    if state.get('pending_check') or (state.get('combat') or {}).get('status') == 'running':
        return None
    area = state.get('area')
    rows = _crumb_rows(source, area)
    hidden = [line for line in _area_facts(source, area, False) if not _unsafe(line) and _SENSORY.search(line)]
    if rows or hidden:
        spoken = 'Kit: %s' % success_line(source, area, 'perception', (rows or hidden)[0])
        public = (rows or hidden)[0]
    else:
        public = _fork_question(source, area)
        spoken = 'Kit: %s' % public
    events = [{'type': 'beat', 'tags': ['clarify'],
               'evidence': 'A roll arrived with no check waiting. The page answers or asks which part.'}]
    committed = runtime.commit('roll-%s' % revision, revision, events)
    return {'stage': 'clarify', 'committed': True, 'calls': 1, 'spoken': spoken,
            'public_event': public, 'revision': committed}


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
    if not burst or _blocks_quote(burst) or _META.search(burst):
        data['screen_failed'] = True
        _write(db, data)
        return None
    handoff = data.get('handoff') or "Say what you do."
    data['burst_spoken'] = True
    beat = data.get('beat')
    if isinstance(beat, dict):
        from .kit_opening import player_line, _mark_heard
        if beat.get('source_verified'):
            # This burst was source-checked; it need not match the old pattern
            # recognizer's idea of a 'scene line' to count as spoken.
            initial = [_norm for _norm in _sentences(burst) if _norm]
            fiction = beat.get('fiction') or []
            beat['heard'] = len([line for line in fiction if normalize(line) in
                                 {normalize(item) for item in initial}])
            beat.setdefault('observed', {}).setdefault('heard', []).extend(initial)
        else:
            _mark_heard(beat, [sentence for sentence in _sentences(burst) if player_line(sentence)])
        data['beat'] = beat
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
    if isinstance(data.get('beat'), dict):
        return _release_beat(runtime, data, revision)
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
    rest = _unread((data.get('remainder') or '').strip(), data.get('burst') or '')
    chunk, left, stopped = _read_on(rest, BURST_WORDS)
    if chunk and _go_fail(chunk):
        chunk, left, stopped = '', '', True
    data['remainder'] = '' if stopped else left
    if not chunk:
        spoken = 'Kit: %s' % OPENING_DONE
    else:
        hand = 'Go on for the rest, or say what you do.' if left else (
            data.get('handoff') or 'Say what you do.')
        spoken = 'Narrator: %s\nKit: %s' % (chunk, hand)
        _note_people(runtime, chunk)
    _write(path, data)
    events = [{'type': 'beat', 'tags': ['read_on'],
               'evidence': 'The next player sentences of the validated opening span.'}]
    committed = runtime.commit('read-%s' % revision, revision, events)
    return {'stage': 'read_on', 'committed': True, 'calls': 1, 'spoken': spoken,
            'public_event': chunk or OPENING_DONE, 'revision': committed}


def _release_beat(runtime, data, revision):
    """Go on reads the fiction cursor. Heard lines are not read again. Screen lines are not in it."""
    from .kit_opening import player_line
    beat = data['beat']
    lines = (list(beat.get('fiction') or []) if beat.get('source_verified')
             else [sentence for sentence in (beat.get('fiction') or []) if player_line(sentence)])
    if not data.get('burst_spoken'):
        spoken = opening_line(runtime.path)
        if not spoken:
            return None
        events = [{'type': 'beat', 'tags': ['read_on'],
                   'evidence': 'The validated opening, spoken because they said go on.'}]
        committed = runtime.commit('read-%s' % revision, revision, events)
        fresh = _read(runtime.path)
        return {'stage': 'read_on', 'committed': True, 'calls': 1, 'spoken': spoken,
                'public_event': fresh.get('burst') or '', 'revision': committed}
    heard = int(beat.get('heard') or 0)
    verified = beat.get('source_verified') is True
    if verified:
        # SQLite is the authority after a crash between commit and sidecar cache.
        _revision, state = runtime.load()
        cursor = state.get('opening_cursor') or {}
        if cursor.get('room_id') == runtime.source().get('id'):
            heard = max(heard, int(cursor.get('heard', 0)))
    if heard == 0 and data.get('burst_spoken'):
        heard = len([sentence for sentence in _sentences(data.get('burst') or '') if player_line(sentence)])
    chunk_lines = []
    count = 0
    for sentence in lines[heard:]:
        words = len(_words(sentence))
        if chunk_lines and count + words > BURST_WORDS:
            break
        chunk_lines.append(sentence)
        count += words
        if count >= BURST_WORDS:
            break
    beat['heard'] = heard + len(chunk_lines)
    observed = beat.setdefault('observed', {'heard': [], 'seen': [], 'find': ''})
    heard_lines = observed.setdefault('heard', [])
    for sentence in chunk_lines:
        if sentence not in heard_lines:
            heard_lines.append(sentence)
    data['beat'] = beat
    data['remainder'] = ' '.join(lines[beat['heard']:])
    if not chunk_lines:
        spoken = 'Kit: %s' % OPENING_DONE
        public = OPENING_DONE
    else:
        chunk = ' '.join(chunk_lines)
        left = lines[beat['heard']:]
        hand = 'Go on for the rest, or say what you do.' if left else (data.get('handoff') or 'Say what you do.')
        spoken = 'Narrator: %s\nKit: %s' % (chunk, hand)
        public = chunk
        if not verified:
            _note_people(runtime, chunk)
    events = [{'type': 'beat', 'tags': ['read_on'],
               'evidence': 'Unread player lines from the opening beat. Screen text stays back.'}]
    if verified:
        events.append({'type': 'opening_cursor', 'room_id': runtime.source().get('id'),
                       'heard': int(beat['heard']),
                       'evidence': 'The accepted opening read-aloud cursor advances with the turn.'})
    committed = runtime.commit('read-%s' % revision, revision, events)
    # This file is only a convenience cache. A failed commit must never advance
    # it, and a successful commit survives losing the cache write.
    try:
        _write(runtime.path, data)
    except OSError:
        if not verified:
            raise
    return {'stage': 'read_on', 'committed': True, 'calls': 1, 'spoken': spoken,
            'public_event': public, 'revision': committed}


def opening_turn(runtime, action):
    from .kit_opening import opening_turn as turn
    return turn(runtime, action)


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


def _open_named(db, chosen):
    """A place name with no safe box. Kit starts there. The notes under it are not spoken."""
    from .kit_adventure import IngestError
    title = chosen.get('title') or 'Here'
    line = chosen.get('kit_line') or ''
    data = _read(db)
    page = chosen.get('page') or 1
    try:
        done = accept(db, {
            'burst': title if str(title).endswith('.') else '%s.' % title,
            'source_quote': title,
            'page_start': page, 'page_end': page,
            'alt_starts': data.get('alt_starts') or [],
            'design_start_name': title,
        })
    except IngestError:
        done = {'stage': 'skim_rejected'}
    if done.get('stage') == 'skim_accepted':
        fresh = _read(db)
        fresh['speak_now'] = True
        fresh['kit_line'] = line
        fresh['handoff'] = line or fresh.get('handoff')
        beat = fresh.get('beat') if isinstance(fresh.get('beat'), dict) else {}
        beat['fiction'] = [sentence for sentence in (beat.get('fiction') or [])
                           if sentence and 'seem' not in sentence.casefold() and 'will lie' not in sentence.casefold()]
        fresh['beat'] = beat
        _write(db, fresh)
        return {
            'room': done.get('room'), 'room_id': done.get('room_id'), 'location': done.get('scene_key'),
            'pick': title, 'line': title, 'starts': [], 'speak_now': True,
            'spoken': 'Kit: %s' % line if line else None,
        }
    data['kit_line'] = line
    data['table_line'] = line
    data['status'] = 'rejected'
    _write(db, data)
    return {
        'stage': 'kit_named', 'committed': False, 'opened_room': None, 'spoken': 'Kit: %s' % line,
        'pick': title, 'line': title, 'table_line': line,
    }


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
    if not quote and chosen.get('kit_line'):
        return _open_named(db, chosen)
    from .kit_opening import player_line
    if not quote or not player_line(quote):
        raise IngestError(['%s is not player fiction' % chosen.get('title')])
    page = chosen.get('page') or 1
    done = accept(db, {
        'burst': quote, 'source_quote': quote, 'page_start': page, 'page_end': page,
        'alt_starts': data.get('alt_starts') or [],
        'design_start_name': chosen.get('title'),
    })
    if done.get('stage') != 'skim_accepted' or not done.get('room'):
        from .kit_opening import kit_line
        return _open_named(db, {
            'title': chosen.get('title') or 'Here',
            'kit_line': chosen.get('kit_line') or kit_line(chosen.get('title') or 'here'),
            'page': page,
        })
    fresh = _read(db)
    fresh['speak_now'] = True
    _write(db, fresh)
    return {
        'room': done.get('room'), 'room_id': done.get('room_id'), 'location': done.get('scene_key'),
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
        kind = str(fact.get('row') or '')
        text = normalize(fact.get('text') or '')
        if text and not _marked(text) and not _replay(source, area, text):
            rows.append((0 if kind.startswith('find') else 1, text))
    rows.sort(key=lambda item: item[0])
    return [text for _order, text in rows]


def _fork_question(source, area):
    """A move from who is here. Not a list of words cut from the opening line."""
    names = []
    for actor in ((source or {}).get('actors') or {}).values():
        if not isinstance(actor, dict):
            continue
        if actor.get('status') in ('dead', 'fled', 'hidden'):
            continue
        if area and actor.get('location') not in (area, None, 'here'):
            continue
        name = (actor.get('name') or '').strip()
        if name and name.casefold() not in {item.casefold() for item in names}:
            names.append(name)
    if names:
        return '%s is here. Speak to them, or look again.' % names[0]
    rows = [row for row in _crumb_rows(source, area) if row and not _go_fail(row)]
    if rows:
        return rows[0]
    return 'Look again, or speak to someone here.'


def success_line(source, area, skill_name, cited):
    """A high check speaks a new crumb or a fork from this scene."""
    rows = [row for row in _crumb_rows(source, area) if not _unsafe(row)]
    cited = normalize(cited)
    if cited and not _unsafe(cited) and not _marked(cited) and not _replay(source, area, cited) and cited not in rows:
        rows.insert(0, cited)
    finds = [row for row in rows if row.lower().startswith('find')]
    if finds:
        return finds[0]
    if rows:
        return rows[0]
    hidden = [text for text in _area_facts(source, area, False)
              if text and not _unsafe(text) and _SENSORY.search(text)]
    if hidden:
        return hidden[0]
    return _fork_question(source, area)


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


def named_start(runtime, action):
    """A title typed before the opening is a start command, not a ruling."""
    text = normalize(action or '').strip(' .!')
    if not text or len(text.split()) > 8:
        return None
    try:
        path = runtime.path
    except Exception:
        return None
    data = _read(path)
    if data.get('burst_spoken'):
        return None
    folded = text.casefold()
    if re.fullmatch(r'[a-z]', folded):
        from .kit_opening import letter_slot
        slot = letter_slot(data.get('alt_starts'), folded)
        if not slot:
            return {
                'stage': 'pick_start', 'committed': False, 'spoken': None,
                'character_loaded': False,
                'table_line': 'That letter is not on the picker.',
                'places': [{'pick': item.get('title'), 'line': item.get('title')}
                           for item in data.get('alt_starts') or []],
            }
        titles = [slot.get('title')]
    else:
        titles = []
        for alt in data.get('alt_starts') or []:
            if alt.get('title'):
                titles.append(alt['title'])
        try:
            from .kit_adventure import _load
            index, _text = _load(path)
        except Exception:
            index = {}
        for item in index.get('starts') or []:
            for key in ('pick', 'line'):
                if item.get(key):
                    titles.append(item[key])
        if index.get('title'):
            titles.append(index['title'])
    hit = None
    for title in titles:
        candidate = normalize(title).casefold()
        if candidate and (folded == candidate or candidate.endswith(' ' + folded)):
            hit = title
            break
    if hit is None:
        return None
    import shlex
    return {
        'stage': 'use_start', 'committed': False, 'spoken': None, 'character_loaded': False,
        'start_title': hit,
        'table_line': 'That is a start, not a turn. Nothing is committed until the opening is player fiction.',
        'next_command': 'python3 -m runtime.kit_agent start --db %s --sheet <sheet> --start %s' % (
            shlex.quote(str(path)), shlex.quote(str(hit))),
    }


def host_before_session(db, action):
    """No scene yet. A typed title is a start command, and the picker stays usable."""
    class _Save(object):
        def __init__(self, path):
            self.path = path
    hinted = named_start(_Save(db), action)
    if hinted:
        return hinted
    data = _read(db)
    alts = [item for item in (data.get('alt_starts') or []) if item.get('title') and item.get('quote')]
    if not data and not alts:
        return None
    import shlex
    return {
        'stage': 'use_start', 'committed': False, 'spoken': None, 'character_loaded': False,
        'places': [{'pick': item.get('title'), 'line': item.get('title'), 'page': item.get('page')}
                   for item in alts],
        'start_picker': {'table_line': data.get('table_line') or picker_line(alts), 'places': alts},
        'table_line': data.get('table_line') or picker_line(alts),
        'next_command': 'python3 -m runtime.kit_agent start --db %s --sheet <sheet> --start "<title>"' % (
            shlex.quote(str(db))),
    }
