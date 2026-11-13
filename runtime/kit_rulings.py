"""Prep-time section rulings: destination assumes origin.

Conditional sentences in a recorded section are indexed at finish, not
on the landing path. At play, a matching player action hands the host
the book's own wording, validated word for word. The model does not
invent a ruling when the book has one. Each ruling is confirmed or
likely, the same way links are. Player-facing lines never show a DC
or a bonus.
"""
import re

from .kit_links import CONFIRMED, LIKELY, section_key, valid_quote, links_from, _recorded_span

_IF = re.compile(
    r'(?is)(?P<full>'
    r'(?:if|when)\s+(?:a|an|the|any|each|this)?\s*'
    r'(?:characters?|party|pcs?|adventurers?|creatures?|heroes?|'
    r'they|someone|anybody|anyone)\b'
    r'[^.!?]{0,240}[.!?]'
    r'|creatures?\s+that\b[^.!?]{0,240}[.!?]'
    r'|a\s+characters?\s+who\b[^.!?]{0,240}[.!?]'
    r')'
)
_LEAD = re.compile(
    r'(?i)^(?:if|when)\s+(?:a|an|the|any|each|this)?\s*'
    r'(?:characters?|party|pcs?|adventurers?|creatures?|heroes?|'
    r'they|someone|anybody|anyone)\s+'
    r'(?:who\s+|that\s+)?'
    r'|^creatures?\s+that\s+'
    r'|^a\s+characters?\s+who\s+'
)
_MECHANICS = re.compile(
    r'\b(?:armor|armour)\s+class\b|\bhit points?\b|\bDC\s*\d+\b|'
    r'\b(?:\+|-)\s*\d+\s+(?:bonus|penalty|to hit|to the)\b|'
    r'\bto hit\b|\bchallenge rating\b|\b\d+\s*\(\d+d\d+',
    re.I)
_STOP = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'they', 'them',
    'their', 'a', 'an', 'of', 'to', 'in', 'on', 'at', 'as', 'or', 'by',
    'if', 'when', 'who', 'which', 'into', 'onto', 'then', 'than', 'but',
    'not', 'can', 'may', 'must', 'will', 'would', 'should', 'do', 'does',
    'is', 'are', 'be', 'been', 'it', 'its', 'his', 'her',
}
_TRAP = re.compile(r'\b(?:trap|snare|pit|pressure plate|alarm|glyph)\b', re.I)
_ITEM = re.compile(r'\b(?:potion|scroll|key|amulet|ring|wand|item|blade|token)\b', re.I)
_LOOK = re.compile(r'\b(?:look|search|searches|examine|examin|listen|peer|inspect)\b', re.I)
_TALK = re.compile(r'\b(?:talks?|asks?|speaks?|spoke|hail|questions?|tells?)\b', re.I)
_CHECK = re.compile(
    r'\b(?:sneak|climb|jump|force|disarm|hide|steal|lift|push|open|pick)\b', re.I)


def counts(index):
    """Structural tallies only: confirmed and likely."""
    confirmed = likely = 0
    for ruling in index.get('rulings') or []:
        if ruling.get('confidence') == CONFIRMED:
            confirmed += 1
        elif ruling.get('confidence') == LIKELY:
            likely += 1
    return {'confirmed': confirmed, 'likely': likely}


def rulings_from(index, key):
    """Rulings already recorded on this section. No extra text walk."""
    key = section_key(index, key)
    if not key:
        return []
    return [dict(item) for item in (index.get('rulings') or [])
            if section_key(index, item.get('from')) == key]


def summary_for(index, key=None):
    """Packet-safe ruling metadata, or book-wide counts when key is omitted."""
    out = dict(counts(index))
    if key:
        items = []
        for item in rulings_from(index, key):
            items.append({
                'confidence': item.get('confidence'),
                'trigger_kind': item.get('trigger_kind') or '',
                'condition_words': len(str(item.get('condition') or '').split()),
                'quote_words': len(str(item.get('quote') or '').split()),
                'has_mechanics': bool(item.get('has_mechanics')),
            })
        out['items'] = items
    return out


def build(index, text):
    """Record each section's if-sentences on the index. Mutates ``index``. Cheap."""
    text = text or ''
    locations = index.get('locations') or {}
    found = []
    seen = set()
    for loc in locations.values():
        span = _recorded_span(loc, len(text))
        if not span:
            continue
        start, end = span
        piece = text[start:end]
        for match in _IF.finditer(piece):
            quote = re.sub(r'\s+', ' ', match.group('full')).strip()
            if len(quote.split()) < 6:
                continue
            offset = start + match.start()
            key = (loc.get('key'), offset, quote.casefold())
            if key in seen:
                continue
            seen.add(key)
            condition = _condition_clause(quote)
            trigger = _attach_trigger(index, loc, quote, offset, start, end)
            classic = bool(_LEAD.match(quote) and re.match(r'(?i)if\s+', quote))
            confidence = CONFIRMED if (trigger or classic) else LIKELY
            found.append({
                'from': loc.get('key'),
                'confidence': confidence,
                'condition': condition,
                'quote': quote,
                'span': [start + match.start(), start + match.end()],
                'offset': offset,
                'trigger_kind': (trigger or {}).get('kind') or '',
                'trigger': (trigger or {}).get('name') or '',
                'has_mechanics': bool(_MECHANICS.search(quote)),
            })
    index['rulings'] = found
    index['ruling_counts'] = counts(index)
    return index


def for_action(db, action, scene_key=None):
    """The book's own ruling when the action matches a recorded condition.

    The quote is for the host and is validated word for word. Player-facing
    spoken is omitted when the sentence carries a DC or a bonus.
    """
    from .kit_adventure import _load
    try:
        index, text = _load(db)
    except Exception:
        return None
    key = section_key(index, scene_key or index.get('start'))
    hit = match_action(action, rulings_from(index, key))
    if hit is None:
        return None
    span = _span_text(text, hit.get('span'))
    quote = hit.get('quote') or ''
    if not quote or not valid_quote(span or quote, quote):
        return None
    out = {
        'source_verified': True,
        'confidence': hit.get('confidence'),
        'quote': quote,
        'quote_words': len(quote.split()),
        'condition_words': len(str(hit.get('condition') or '').split()),
        'trigger_kind': hit.get('trigger_kind') or '',
        'has_mechanics': bool(hit.get('has_mechanics') or _MECHANICS.search(quote)),
        'prefetched': False,
    }
    return out


def match_action(action, rulings):
    """The first recorded ruling whose condition is touched by the player line."""
    terms = _content_terms(action)
    if not terms:
        return None
    ranked = []
    for item in rulings or []:
        cond = _content_terms(item.get('condition') or item.get('quote') or '')
        if not cond:
            continue
        overlap = terms & cond
        if not overlap:
            continue
        # A real match needs the verb-or-noun meat of the condition, not a lone stopword leftover.
        if len(overlap) < min(2, len(cond)):
            continue
        ranked.append((
            0 if item.get('confidence') == CONFIRMED else 1,
            -len(overlap),
            -len(cond),
            item,
        ))
    if not ranked:
        return None
    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    return ranked[0][3]


def obvious_kinds(ruling):
    """Which obvious next move this ruling is for: look, talk, or check."""
    blob = '%s %s %s' % (
        ruling.get('condition') or '', ruling.get('quote') or '',
        ruling.get('trigger_kind') or '')
    kinds = []
    if _LOOK.search(blob) or (ruling.get('trigger_kind') or '') in ('search',):
        kinds.append('look')
    if _TALK.search(blob) or (ruling.get('trigger_kind') or '') == 'npc':
        kinds.append('talk')
    if _CHECK.search(blob) or (ruling.get('trigger_kind') or '') in ('check', 'trap'):
        kinds.append('check')
    return kinds


def _condition_clause(quote):
    text = (quote or '').strip()
    split = re.split(r'\s*,\s*|\s+then\s+', text, maxsplit=1, flags=re.I)
    head = split[0] if split else text
    stripped = _LEAD.sub('', head).strip()
    return stripped or head


def _content_terms(text):
    words = re.findall(r"[A-Za-z][A-Za-z']{2,}", str(text or '').casefold())
    terms = set()
    for word in words:
        if word in _STOP:
            continue
        terms.add(_stem(word))
    return terms


def _stem(word):
    if word.endswith('ing') and len(word) > 6:
        return word[:-3]
    if word.endswith('ers') and len(word) > 6:
        return word[:-3]
    if word.endswith('ies') and len(word) > 5:
        return word[:-3] + 'y'
    if word.endswith('es') and len(word) > 4:
        if word[:-2].endswith(('ch', 'sh')) or word[-3] in 'sxz':
            return word[:-2]
    if word.endswith('ed') and len(word) > 5:
        return word[:-2]
    if word.endswith('s') and not word.endswith('ss') and len(word) > 3:
        return word[:-1]
    return word


def _attach_trigger(index, loc, quote, offset, start, end):
    """Attach a check, trap, NPC, or item already known in this section's web."""
    for check in index.get('checks') or []:
        span = check.get('span') or [0, 0]
        if len(span) >= 2 and span[0] <= offset <= span[1]:
            return {'kind': 'check', 'name': check.get('name') or check.get('letter') or ''}
        trigger = str(check.get('trigger') or '')
        if trigger and trigger.casefold() in quote.casefold():
            return {'kind': 'check', 'name': check.get('name') or check.get('letter') or ''}
    blob = quote.casefold()
    for npc in index.get('npcs') or []:
        name = (npc.get('name') if isinstance(npc, dict) else str(npc or '')).strip()
        if name and len(name) > 2 and name.casefold() in blob:
            return {'kind': 'npc', 'name': name}
    for actor in (loc.get('npcs') or loc.get('creatures') or []):
        name = (actor.get('name') if isinstance(actor, dict) else str(actor or '')).strip()
        if name and len(name) > 2 and name.casefold() in blob:
            return {'kind': 'npc', 'name': name}
    for link in links_from(index, loc.get('key')):
        subject = (link.get('subject') or '').strip()
        if subject and len(subject) > 2 and subject.casefold() in blob:
            kind = link.get('kind') or 'link'
            if kind == 'name':
                kind = 'npc'
            return {'kind': kind, 'name': subject}
    addressed = re.search(
        r"(?i)\b(?:talks?|speaks?|asks?)\s+(?:to|with)\s+(?:the\s+)?([A-Za-z][A-Za-z'-]{2,})",
        quote)
    if addressed:
        return {'kind': 'npc', 'name': addressed.group(1)}
    if _TRAP.search(quote):
        return {'kind': 'trap', 'name': ''}
    if _ITEM.search(quote):
        return {'kind': 'item', 'name': ''}
    return None


def _span_text(text, span):
    if not text or not isinstance(span, (list, tuple)) or len(span) < 2:
        return ''
    start, end = int(span[0]), int(span[1])
    if end <= start or start < 0 or end > len(text):
        return ''
    return text[start:end]
