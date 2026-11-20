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
    r'\bto hit\b|\bchallenge rating\b|\b\d+\s*\(\d+d\d+|'
    r'\bsucceed(?:s|ed)?\s+on\s+a\s+DC\b|\b(?:strength|dexterity|constitution|'
    r'intelligence|wisdom|charisma|athletics|acrobatics|stealth|perception|'
    r'investigation|insight|survival)\s+check\b',
    re.I)
_DM_IMPERATIVE = re.compile(
    r'(?i)\b(?:review|refer(?:\s+the|\s+to)?|consult|see(?:\s+the|\s+appendix|'
    r'\s+page|\s+chapter|\s+stat)|as described(?:\s+in|\s+on)?|'
    r'described (?:in|on)|turn to|look up|stat blocks?)\b')
_APPENDIX_PAGE = re.compile(
    r'(?i)\bappendix\b|\bpage\s+\d+\b|\bpp?\.\s*\d+\b|\bon page\b|'
    r'\bsee page\b')
_FOOTER = re.compile(
    r'(?i)(?:©|\(c\)|copyright|\ball rights reserved\b|\breproduced\b|'
    r'\bpermission to (?:copy|photocopy|reproduce)\b|\bisbn\b|'
    r'\bwizards of the coast\b|\btrademark|all rights reserved)')
_BULLET_LEAD = re.compile(
    r'^(?:[\u2022\u2023\u25E6\u2043\u2219•●○►▸\-–—*]+|\d+[.)])\s+')
_BULLET_MID = re.compile(r'[\u2022\u2023\u25E6\u2043\u2219•●○►▸]')
_DM_ADVICE = re.compile(
    r'(?i)\b(?:you can have|you may want|you should|suggest that|'
    r'remind the|tell the players|for the dm|the dungeon master|'
    r'proceed to|go on to|move on to (?:chapter|part|section)|'
    r'character sheets?|try something unexpected|'
    r"skill that isn'?t on|say through the action|the best way to)\b")
_OUTCOME_IMPERATIVE = re.compile(
    r'(?i)^(?:use|have|suggest|remind|tell|proceed|make|let|'
    r'give|ask the players|add|roll|head back)\b')
_GENERIC_HP = re.compile(
    r'(?i)\b(?:subtract (?:that )?damage from|they are (?:unconscious|defeated)|'
    r"(?:a character'?s |the character'?s |their )?hit points? reach(?:es)? 0|"
    r'reaches 0 hit points)\b')
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
    """Structural tallies only: confirmed, likely, and junk dropped."""
    confirmed = likely = 0
    for ruling in index.get('rulings') or []:
        if ruling.get('confidence') == CONFIRMED:
            confirmed += 1
        elif ruling.get('confidence') == LIKELY:
            likely += 1
    dropped = int(index.get('ruling_dropped') or 0)
    return {
        'confirmed': confirmed,
        'likely': likely,
        'dropped': dropped,
        'candidates': confirmed + likely + dropped,
    }


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
    dropped = 0
    for loc in locations.values():
        span = _recorded_span(loc, len(text))
        if not span:
            continue
        start, end = span
        piece = text[start:end]
        for match in _IF.finditer(piece):
            raw = match.group('full')
            quote = re.sub(r'\s+', ' ', raw).strip()
            dropped += 1
            if len(quote.split()) < 6:
                continue
            if not _is_real_ruling(quote, raw):
                continue
            offset = start + match.start()
            key = (loc.get('key'), offset, quote.casefold())
            if key in seen:
                continue
            seen.add(key)
            condition, outcome = _clauses(quote)
            trigger = _attach_trigger(index, loc, quote, offset, start, end)
            kind = (trigger or {}).get('kind') or _infer_kind(quote, condition)
            classic = bool(_LEAD.match(quote) and re.match(r'(?i)if\s+', quote))
            if not kind:
                # A real conditional with no classifiable trigger is only likely,
                # and only kept if we can still name a generic act.
                kind = 'act'
                confidence = LIKELY
            else:
                confidence = CONFIRMED if (trigger or classic) else LIKELY
                if not trigger and kind == 'act':
                    confidence = LIKELY
            dropped -= 1
            found.append({
                'from': loc.get('key'),
                'confidence': confidence,
                'condition': condition,
                'outcome': outcome,
                'quote': quote,
                'span': [start + match.start(), start + match.end()],
                'offset': offset,
                'trigger_kind': kind,
                'trigger': (trigger or {}).get('name') or '',
                'has_mechanics': bool(_MECHANICS.search(quote)),
            })
    index['rulings'] = found
    index['ruling_dropped'] = dropped
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
    stashed, stash_hit = _stashed_match(db, action, key)
    hit = stash_hit if stash_hit is not None else match_action(action, rulings_from(index, key))
    if hit is None:
        return None
    span = _span_text(text, hit.get('span'))
    quote = hit.get('quote') or ''
    if not quote or not valid_quote(span or quote, quote):
        return None
    kind = hit.get('trigger_kind') or ''
    if not kind:
        return None
    out = {
        'source_verified': True,
        'confidence': hit.get('confidence'),
        'quote': quote,
        'quote_words': len(quote.split()),
        'condition_words': len(str(hit.get('condition') or '').split()),
        'outcome_words': len(str(hit.get('outcome') or '').split()),
        'trigger_kind': kind,
        'has_mechanics': bool(hit.get('has_mechanics') or _MECHANICS.search(quote)),
        'prefetched': bool(stashed and stash_hit is not None),
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



def _stashed_match(db, action, key):
    """A ruling already sitting on next-move prep, if the action matches it."""
    try:
        from . import kit_skim
        stash = (kit_skim._read(db).get('next_move_prep') or {}).get('ruling_records') or []
    except Exception:
        return False, None
    if not stash:
        return False, None
    hit = match_action(action, stash)
    return True, hit


def _is_real_ruling(quote, raw=''):
    """A player- or world-facing if/when with a condition and an outcome.

    DM instructions, bullets, appendix or page pointers, copyright and
    footer lines, and formulas whose outcome is boilerplate are refused.
    """
    text = (quote or '').strip()
    lead = (raw or text).lstrip()
    if _BULLET_LEAD.search(lead) or _BULLET_MID.search(text):
        return False
    if _FOOTER.search(text):
        # A real sentence may sit beside a footer; only refuse when the
        # outcome (or the whole line) is the boilerplate itself.
        condition, outcome = _clauses(text)
        if not outcome or _FOOTER.search(outcome) or _FOOTER.search(condition):
            return False
        # Strip a trailing footer sentence and re-check later clauses.
        text = re.sub(r'(?i)(?:©|\(c\)|copyright|all rights reserved).*$', '', text).strip()
    condition, outcome = _clauses(text)
    if not condition or not outcome:
        return False
    if len(condition.split()) < 2 or len(outcome.split()) < 2:
        return False
    if _DM_IMPERATIVE.search(outcome) or _DM_IMPERATIVE.search(text):
        # "they must succeed on a check" is an outcome, not a DM "see/review".
        if _DM_IMPERATIVE.search(outcome):
            return False
        # Imperative in the condition ("if the DM reviews") is also junk.
        if _DM_IMPERATIVE.search(condition):
            return False
    if _APPENDIX_PAGE.search(text):
        return False
    if _FOOTER.search(outcome):
        return False
    if _DM_ADVICE.search(text) or _DM_ADVICE.search(outcome):
        return False
    lead = re.sub(r'(?i)^then\s+', '', (outcome or '').strip())
    if _OUTCOME_IMPERATIVE.search(lead):
        return False
    if re.search(r"(?i)\b(?:read each other|haven'?t done so already|introduce your characters?)\b", text):
        return False
    # A mid-sentence box mark is typography junk, not a ruling.
    if '>' in text:
        return False
    # Generic hit-point procedure with no local world outcome is a rules reminder.
    if _GENERIC_HP.search(text) and _GENERIC_HP.search(outcome or text):
        # Keep it only when the outcome is a local world change, not unconscious/defeated/subtract.
        if re.search(r'(?i)\b(?:unconscious|defeated|subtract)\b', outcome or ''):
            return False
        if re.search(r'(?i)reaches? 0 hit points', condition or '') and not re.search(
                r'(?i)\b(?:opens?|closes?|collapses?|flees?|reveals?|stops?|triggers?|'
                r'drops?|falls?|appears?|vanishes?|unlocks?|locks?)\b', outcome or ''):
            return False
    return True


def _clauses(quote):
    text = (quote or '').strip()
    # Prefer an explicit then / comma split after the condition lead.
    match = re.split(r'\s+then\s+|,\s+', text, maxsplit=1, flags=re.I)
    if len(match) == 2 and match[0].strip() and match[1].strip():
        head, tail = match[0].strip(), match[1].strip()
        return _condition_clause(head) or head, tail.rstrip('.!?')
    # "Creatures that drink X grow still." — predicate after the that-clause.
    that = re.match(
        r'(?is)(creatures?\s+that\b[^.!?,]{3,120}?)\s+((?:grow|become|are|take|fall|die|flee|suffer|remain|turn|gain|lose)\b[^.!?]*)',
        text)
    if that:
        return that.group(1).strip(), that.group(2).strip().rstrip('.!?')
    # Fallback: condition is the lead, outcome is the rest of the sentence after the verb phrase.
    condition = _condition_clause(text)
    rest = text
    if condition and condition.casefold() in text.casefold():
        at = text.casefold().find(condition.casefold())
        rest = text[at + len(condition):].strip(' ,.')
    return condition, rest.rstrip('.!?') if rest != text else ''


def _infer_kind(quote, condition):
    blob = '%s %s' % (condition or '', quote or '')
    if _TALK.search(blob):
        return 'npc'
    if _LOOK.search(blob):
        return 'search'
    if _TRAP.search(blob):
        return 'trap'
    if _ITEM.search(blob):
        return 'item'
    if _CHECK.search(blob) or re.search(
            r'(?i)\b(?:drink|pry|force|climb|open|sneak|listen|jump|hide|steal|'
            r'lift|push|search|searches|examine)\b', blob):
        return 'check'
    if re.search(r'(?i)creatures?\s+that\b', blob):
        return 'hazard'
    return ''


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
    if word.endswith('ies') and len(word) > 4:
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
