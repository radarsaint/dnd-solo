"""Prep-time section links: a small graph. Destination assumes origin.

Built during index finish, not on the landing path. A section's own text
is handed over immediately at play. One hop of linked material loads only
when play touches the subject, or as a confirmed prefetch after the
opening is already up. Python validates every quote drawn from linked
text word for word. The model cannot assert a link as fact.
"""
import re

CONFIRMED = 'confirmed'
LIKELY = 'likely'

_POINTER = re.compile(
    r'\bsee(?:\s+the)?\s+'
    r'(appendix(?:\s+[a-z0-9]+)?|area\s+[a-z]?\d+[a-z]?|chapter\s+[\w-]+|'
    r'page\s+\d+|(?:the\s+)?[^.]{2,60}?(?:stat block|statistics))\b',
    re.I)
_PAGE_REF = re.compile(r'\bon\s+page\s+(\d+)\b|\bpage\s+(\d+)\b', re.I)
_BOX_HEAD = re.compile(
    r'^(?:sidebar|handout|rumou?rs?|npc notes?)\s*[:.\-]?\s*(.*)$',
    re.I)
_TRIGGER = re.compile(
    r'\bif the characters?\s+'
    r'(ask|asks|search|searches|touch|touches|look|looks|listen|listens|'
    r'examine|examines|check|checks)\b',
    re.I)
_MECHANICS = re.compile(
    r'\b(?:armor|armour)\s+class\b|\bhit points?\b|\bDC\s*\d+\b|'
    r'\bto hit\b|\bchallenge rating\b|\b\d+\s*\(\d+d\d+',
    re.I)
_HEADING = re.compile(
    r'^(?:(?:chapter|part)\s+[\w-]+|appendix(?:\s+[\w-]+)?|'
    r'(?:area\s+)?[A-Z]?\d{1,3}[a-z]?\s*[.:]\s+\S)',
    re.I)


def counts(index):
    """Structural tallies only: confirmed, likely, and unlinked boxes."""
    confirmed = likely = 0
    for link in index.get('links') or []:
        if link.get('confidence') == CONFIRMED:
            confirmed += 1
        elif link.get('confidence') == LIKELY:
            likely += 1
    unlinked = sum(1 for box in index.get('boxes') or [] if box.get('unlinked'))
    return {'confirmed': confirmed, 'likely': likely, 'unlinked': unlinked}


def links_from(index, key):
    """One-hop links already recorded from this section. No target text."""
    if not key:
        return []
    return [dict(link) for link in (index.get('links') or [])
            if link.get('from') == key]


def summary_for(index, key=None):
    """Packet-safe one-hop metadata, or book-wide counts when key is omitted."""
    out = dict(counts(index))
    if key:
        hops = []
        for link in links_from(index, key):
            hops.append({
                'kind': link.get('kind'),
                'confidence': link.get('confidence'),
                'subject': link.get('subject') or '',
                'subject_words': len(str(link.get('subject') or '').split()),
            })
        out['hops'] = hops
    return out


def build(index, text):
    """Record each section's links on the index. Mutates ``index``. Cheap."""
    text = text or ''
    locations = index.get('locations') or {}
    links = []
    seen = set()

    def add(link):
        key = (link.get('from'), link.get('kind'), link.get('to_kind'),
               link.get('to_key'), tuple(link.get('to_span') or ()))
        if key in seen:
            return
        seen.add(key)
        links.append(link)

    for loc in locations.values():
        _continuation_links(add, loc, text, index)
        _pointer_links(add, loc, text, index)
    _opening_name_links(add, index, text)
    boxes = _collect_boxes(text, index)
    _anchor_boxes(add, boxes, locations, text, index)
    index['links'] = links
    index['boxes'] = boxes
    index['link_counts'] = counts(index)
    return index


def load_hop(index, text, link):
    """The target span for one recorded hop. Empty when the span is missing."""
    if not isinstance(link, dict) or not text:
        return ''
    span = link.get('to_span') or [0, 0]
    if not isinstance(span, (list, tuple)) or len(span) < 2:
        return ''
    start, end = int(span[0]), int(span[1])
    if end <= start or start < 0 or end > len(text):
        return ''
    return text[start:end]


def valid_quote(span, quote):
    """True when the quote occurs word for word in the linked span."""
    if not span or not quote or not str(quote).strip():
        return False
    from .kit_skim import _contiguous, find_quote
    return bool(_contiguous(quote, span) or find_quote(span, quote) is not None)



def _entry_span(text, entry, cap=700):
    """Mechanical block plus a short flavor run, stopped at the next heading."""
    from .kit_adventure import stat_block_span, LOCATION_RE, CHAPTER_RE
    try:
        lo, hi = stat_block_span(text, entry)
    except Exception:
        lo = entry.get('offset') or 0
        hi = min(len(text), lo + 1600)
    pos = hi
    end = min(len(text), hi + cap)
    while pos < end:
        nl = text.find('\n', pos)
        if nl < 0 or nl >= end:
            return lo, end if text[hi:end].strip() else hi
        line = text[pos:nl].strip()
        if line and (
                LOCATION_RE.match(line) or CHAPTER_RE.match(line) or _BOX_HEAD.match(line)
                or (_creature_heading(line) and pos > hi)):
            return lo, pos if text[hi:pos].strip() else hi
        pos = nl + 1
    return lo, end if text[hi:end].strip() else hi


def _creature_heading(line):
    from .kit_adventure import _creature_name_line
    return bool(_creature_name_line(line))


def match_touch(action, links):
    """The first one-hop link whose subject is touched by the player line."""
    blob = ' '.join(str(action or '').split()).casefold()
    if not blob:
        return None
    kind_rank = {'name': 0, 'box': 1, 'continuation': 2, 'pointer': 3}
    conf_rank = {CONFIRMED: 0, LIKELY: 1}
    ranked = []
    for link in links or []:
        subject = (link.get('subject') or '').strip()
        if len(subject) < 3:
            continue
        if subject.casefold() in blob:
            ranked.append((
                conf_rank.get(link.get('confidence'), 2),
                kind_rank.get(link.get('kind'), 9),
                -len(subject),
                link,
            ))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return ranked[0][3]


def answer(db, action, scene_key=None):
    """Attested one-hop answer when play touches a linked subject, or None.

    Loads only that hop. Never walks further. Never invents a fact.
    """
    from .kit_adventure import _load
    try:
        index, text = _load(db)
    except Exception:
        return None
    key = scene_key or index.get('start')
    link = match_touch(action, links_from(index, key))
    if link is None:
        # A confirmed hop from the start opening may still be the subject
        # when the session key is a derived skim scene covering the same body.
        if key != index.get('start'):
            link = match_touch(action, links_from(index, index.get('start')))
        if link is None:
            return None
    span = load_hop(index, text, link)
    if not span:
        return None
    spoken = _safe_line(span, link)
    return {
        'link': {
            'kind': link.get('kind'),
            'confidence': link.get('confidence'),
            'subject_words': len(str(link.get('subject') or '').split()),
        },
        'span_chars': len(span),
        'spoken': spoken,
        'source_verified': True,
    }


def _safe_line(span, link):
    """One Kit line from attested non-mechanical text, or a short handoff."""
    from .kit_skim import _unsafe, _blocks_quote, _sentences
    picked = ''
    for sentence in _sentences(span):
        text = sentence.strip()
        if len(text.split()) < 4:
            continue
        if _MECHANICS.search(text) or _unsafe(text) or _blocks_quote(text):
            continue
        if not valid_quote(span, text):
            continue
        picked = text
        break
    if picked:
        return 'Kit: %s' % picked
    # A mechanics-only hop (a stat block) is attested, but numbers stay off the table.
    return 'Kit: I have that entry. What do you do?'


def _recorded_span(loc, text_len):
    body = loc.get('body') or [0, 0]
    if not isinstance(body, (list, tuple)) or len(body) < 2:
        return None
    start = body[0]
    off = loc.get('offset')
    if off is not None and 0 <= off <= start:
        start = off
    end = min(body[1], text_len)
    if end <= start or start < 0:
        return None
    return start, end


def _page_of(index, offset):
    page = 1
    for item in index.get('pages') or []:
        if item.get('start', 0) <= offset <= item.get('end', offset):
            page = item.get('page') or page
    return page


def _continuation_links(add, loc, text, index):
    """A recorded body that already crossed a page or column gap."""
    span = _recorded_span(loc, len(text))
    if not span:
        return
    start, end = span
    piece = text[start:end]
    break_at = piece.find('\f')
    if break_at < 0:
        if _page_of(index, start) == _page_of(index, max(start, end - 1)):
            return
        # Page changed without a form feed in the extract; treat the body end as the bound.
        mid = (start + end) // 2
        to_start, to_end = mid, end
    else:
        to_start = start + break_at + 1
        to_end = end
    if to_end <= to_start:
        return
    add({
        'from': loc.get('key'),
        'kind': 'continuation',
        'confidence': CONFIRMED,
        'subject': (loc.get('name') or loc.get('key') or '').strip(),
        'to_kind': 'section',
        'to_key': loc.get('key'),
        'to_span': [to_start, to_end],
        'offset': to_start,
    })


def _pointer_links(add, loc, text, index):
    span = _recorded_span(loc, len(text))
    if not span:
        return
    start, end = span
    piece = text[start:end]
    from .kit_adventure import AREA_REF_RE, SEE_RE
    for match in list(_POINTER.finditer(piece)) + list(SEE_RE.finditer(piece)):
        target = _resolve_pointer(match.group(0), match.group(1) if match.lastindex else '',
                                  loc, index, text)
        if not target:
            continue
        add({
            'from': loc.get('key'),
            'kind': 'pointer',
            'confidence': target.get('confidence') or (CONFIRMED if target.get('to_key') or target.get('to_span') else LIKELY),
            'subject': (target.get('subject') or match.group(0)).strip(),
            'to_kind': target.get('to_kind') or 'pointer',
            'to_key': target.get('to_key'),
            'to_span': target.get('to_span'),
            'offset': start + match.start(),
        })
    # "see area N" already covered if it matched _POINTER; AREA_REF without "see"
    # is a likely pointer only when the area resolves uniquely.
    for match in AREA_REF_RE.finditer(piece):
        target = _resolve_area_token(match.group(1), loc, index)
        if not target:
            continue
        add({
            'from': loc.get('key'),
            'kind': 'pointer',
            'confidence': LIKELY,
            'subject': (target.get('subject') or match.group(0)).strip(),
            'to_kind': 'section',
            'to_key': target.get('to_key'),
            'to_span': target.get('to_span'),
            'offset': start + match.start(),
        })


def _opening_name_links(add, index, text):
    """Creatures present in the opening section only, matched to a book entry."""
    start_key = index.get('start')
    loc = (index.get('locations') or {}).get(start_key) or {}
    if not loc:
        return
    blocks = index.get('stat_blocks') or {}
    for creature in loc.get('creatures') or []:
        name = (creature.get('name') or '').strip()
        if not name:
            continue
        entry = blocks.get(name.casefold())
        if not entry:
            continue
        lo, hi = _entry_span(text, entry)
        how = creature.get('resolved')
        if how == 'in_book' and _explicit_see(loc, text, name):
            confidence = CONFIRMED
        elif how == 'in_book':
            confidence = LIKELY
        else:
            continue
        add({
            'from': loc.get('key'),
            'kind': 'name',
            'confidence': confidence,
            'subject': name,
            'to_kind': 'stat_block',
            'to_key': name.casefold(),
            'to_span': [lo, hi],
            'offset': creature.get('mention_offset') or loc.get('offset') or 0,
        })


def _explicit_see(loc, text, name):
    span = _recorded_span(loc, len(text))
    if not span:
        return False
    piece = text[span[0]:span[1]]
    pattern = r'\b' + re.escape(name) + r'e?s?\b[^.\n]{0,80}\bsee\b'
    if re.search(pattern, piece, re.I):
        return True
    from .kit_adventure import SEE_RE
    fold = name.casefold()
    for match in SEE_RE.finditer(piece):
        captured = re.sub(r'^(?:a|an|the)\s+', '', (match.group(1) or '').strip(), flags=re.I)
        if captured.casefold() == fold:
            return True
    return False


def _collect_boxes(text, index):
    boxes = []
    n = 0
    pos = 0
    for line in text.splitlines(True):
        stripped = line.strip()
        match = _BOX_HEAD.match(stripped)
        if match:
            title = (match.group(1) or stripped).strip()
            start = pos
            end = _box_end(text, pos + len(line), index)
            n += 1
            boxes.append({
                'id': 'box:%s' % n,
                'kind': _box_kind(stripped),
                'title': title or stripped,
                'span': [start, end],
                'unlinked': True,
                'anchor': None,
            })
        pos += len(line)
    return boxes


def _box_kind(heading):
    low = heading.casefold()
    if 'handout' in low:
        return 'handout'
    if 'rumor' in low or 'rumour' in low:
        return 'rumor'
    if 'npc' in low:
        return 'npc_note'
    return 'sidebar'


def _box_end(text, after, index):
    rel = after
    while rel < len(text):
        nl = text.find('\n', rel)
        if nl < 0:
            return len(text)
        line = text[rel:nl].strip()
        if rel > after and line and (
                _BOX_HEAD.match(line) or _HEADING.match(line) or _is_keyed(line, index)):
            return rel
        rel = nl + 1
    return len(text)


def _is_keyed(line, index):
    from .kit_adventure import LOCATION_RE
    if LOCATION_RE.match(line or ''):
        return True
    for loc in (index.get('locations') or {}).values():
        name = (loc.get('name') or '').strip()
        if name and line == name:
            return True
    return False


def _anchor_boxes(add, boxes, locations, text, index):
    order = sorted(locations.values(), key=lambda loc: loc.get('offset') or 0)
    for box in boxes:
        span = box.get('span') or [0, 0]
        start, end = span[0], span[1]
        piece = text[start:end]
        trigger = _TRIGGER.search(piece)
        prev = None
        for loc in order:
            off = loc.get('offset') or 0
            if off <= start:
                prev = loc
            else:
                break
        if trigger:
            box['unlinked'] = False
            box['anchor'] = {'kind': 'trigger', 'quote_words': len(trigger.group(0).split())}
            if prev:
                add({
                    'from': prev.get('key'),
                    'kind': 'box',
                    'confidence': CONFIRMED,
                    'subject': (box.get('title') or 'box').strip(),
                    'to_kind': box.get('kind') or 'sidebar',
                    'to_key': box.get('id'),
                    'to_span': [start, end],
                    'offset': start + trigger.start(),
                })
            continue
        # A nearby keyed area immediately before the box is a likely anchor.
        if prev:
            prev_end = (prev.get('body') or [0, 0])[1] if prev.get('body') else (prev.get('offset') or 0)
            if start - prev_end <= 800 or (prev.get('offset') or 0) <= start:
                # Only treat it as anchored when the box sits close after that area.
                gap = start - (prev_end or (prev.get('offset') or 0))
                if 0 <= gap <= 1200:
                    box['unlinked'] = False
                    box['anchor'] = {'kind': 'keyed_area', 'key': prev.get('key')}
                    add({
                        'from': prev.get('key'),
                        'kind': 'box',
                        'confidence': LIKELY,
                        'subject': (box.get('title') or 'box').strip(),
                        'to_kind': box.get('kind') or 'sidebar',
                        'to_key': box.get('id'),
                        'to_span': [start, end],
                        'offset': start,
                    })
                    continue
        box['unlinked'] = True
        box['anchor'] = None


def _resolve_pointer(raw, captured, loc, index, text):
    blob = (captured or raw or '').strip()
    if not blob:
        return None
    low = blob.casefold()
    # Stat block / named appendix entry.
    name = re.sub(r"^(?:the\s+)?|\s+(?:'s\s+)?(?:stat block|statistics|appendix.*)$", '', blob, flags=re.I)
    name = name.strip()
    blocks = index.get('stat_blocks') or {}
    fold = name.casefold()
    if fold in blocks:
        entry = blocks[fold]
        lo, hi = _entry_span(text, entry)
        return {'to_kind': 'stat_block', 'to_key': fold, 'to_span': [lo, hi],
                'subject': name, 'confidence': CONFIRMED}
    area = re.search(r'(?:area|room|section|encounter)\s+([A-Z]?\d{1,3}[a-z]?)\b', blob, re.I)
    if area:
        return _resolve_area_token(area.group(1), loc, index)
    appendix = re.search(r'appendix(?:\s+([a-z0-9]+))?', blob, re.I)
    if appendix and 'stat' not in low:
        return _resolve_chapter(index, text, 'appendix', appendix.group(1))
    chapter = re.search(r'chapter\s+([\w-]+)', blob, re.I)
    if chapter:
        return _resolve_chapter(index, text, 'chapter', chapter.group(1))
    page = _PAGE_REF.search(blob) or _PAGE_REF.search(raw or '')
    if page:
        number = int(page.group(1) or page.group(2))
        return _resolve_page(index, number)
    return None


def _resolve_area_token(token, loc, index):
    from .kit_adventure import _resolve_area
    locations = index.get('locations') or {}
    by_site = {(item.get('site') or '', item['bare']): key
               for key, item in locations.items() if item.get('bare')}
    unique = {}
    bare_keys = {}
    for key, item in locations.items():
        bare_keys.setdefault(item.get('bare'), []).append(key)
    unique = {bare: keys[0] for bare, keys in bare_keys.items() if len(keys) == 1}
    try:
        target = _resolve_area(token, loc, '', by_site, unique)
    except Exception:
        target = unique.get(str(token)) or unique.get(str(token).upper()) or unique.get(str(token).lower())
    if not target:
        # Bare number as unique location id or "site-N".
        for key, item in locations.items():
            if str(item.get('bare') or '') == str(token) or str(item.get('number') or '') == str(token):
                if target and target != key:
                    return None
                target = key
    other = locations.get(target) if target else None
    if not other:
        return None
    span = other.get('body') or [other.get('offset') or 0, other.get('offset') or 0]
    return {'to_kind': 'section', 'to_key': target, 'to_span': [span[0], span[1]],
            'subject': other.get('name') or target, 'confidence': CONFIRMED}


def _resolve_chapter(index, text, kind, token):
    for chapter in index.get('chapters') or []:
        title = (chapter.get('title') or '').casefold()
        if kind == 'appendix' and 'appendix' in title:
            if token and token.casefold() not in title and not title.startswith('appendix'):
                continue
            start = chapter.get('offset') or 0
            end = chapter.get('end') or min(len(text), start + 4000)
            return {'to_kind': 'chapter', 'to_key': chapter.get('title') or 'appendix',
                    'to_span': [start, end], 'subject': chapter.get('title') or 'appendix',
                    'confidence': CONFIRMED}
        if kind == 'chapter' and token and token.casefold() in title:
            start = chapter.get('offset') or 0
            end = chapter.get('end') or min(len(text), start + 4000)
            return {'to_kind': 'chapter', 'to_key': chapter.get('title'),
                    'to_span': [start, end], 'subject': chapter.get('title'),
                    'confidence': CONFIRMED}
    return {'to_kind': kind, 'to_key': None, 'to_span': None,
            'subject': (token or kind), 'confidence': LIKELY}


def _resolve_page(index, number):
    for item in index.get('pages') or []:
        if item.get('page') == number:
            return {'to_kind': 'page', 'to_key': 'page-%s' % number,
                    'to_span': [item.get('start') or 0, item.get('end') or 0],
                    'subject': 'page %s' % number, 'confidence': CONFIRMED}
    return {'to_kind': 'page', 'to_key': 'page-%s' % number, 'to_span': None,
            'subject': 'page %s' % number, 'confidence': LIKELY}


def prefetch_confirmed(db, scene_key=None):
    """Load confirmed one-hop spans after the opening is up. Not for landing."""
    from .kit_adventure import _load
    try:
        index, text = _load(db)
    except Exception:
        return []
    key = scene_key or index.get('start')
    found = []
    for link in links_from(index, key):
        if link.get('confidence') != CONFIRMED:
            continue
        span = load_hop(index, text, link)
        if span:
            found.append({'kind': link.get('kind'), 'chars': len(span),
                          'subject_words': len(str(link.get('subject') or '').split())})
    return found
