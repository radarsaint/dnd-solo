"""Playable scenes, scored from several signals at ingest and looked up by dict at play.

A scene is any playable unit, not a heading alone. Ingest (once) scores read-aloud,
encounter cues, headings outside the numbered key, travel or event sections, and
NPC-driven events. One signal is never enough to promote a scene and never enough
to drop it: it stays on the check list for the DM. Live play only does dict lookups
on the trigger index written at ingest.

Keyed rooms keep the book's numbers (1, 1a, A2). Lettered scenes are their own type,
``scene:<site>:A``, so a letter cannot collide with a room id, an exit, or a hash.
Letters restart in each part. Stdlib only. Python 3.8.
"""
import json
import re
import time
from pathlib import Path

WEIGHTS = {
    'read_aloud': 3,
    'encounter_cue': 3,
    'outside_heading': 2,
    'travel_event': 2,
    'npc_event': 2,
}
PROMOTE_SCORE = 5
PROMOTE_SIGNALS = 2
BODY_MIN = 40

_HEAD_WORD = re.compile(r"^[A-Z][A-Za-z'’-]{2,24}$")
# Short words that still belong in a place or encounter heading ("on the road", "of the inn").
_SMALL_WORD = frozenset('a an the of on to and in for or by at'.split())
_PREFIX = re.compile(r'^(encounter|event|travel|random encounter)\s*:\s*(.+)$', re.I)
_DM = re.compile(
    r'^(?:developments|features|treasure|creatures|tactics|roleplaying|adjusting|xp awards|'
    r'setup|background|map|introduction|glossary|rests|contents|index|credits|preface|'
    r'foreword|overview|bibliography)\b', re.I)
_YOU = re.compile(r'\b(?:you|your|yours)\b', re.I)
_CUE = re.compile(
    r"\bif the characters\b|\bwhen the (?:party|characters|heroes|adventurers)\b|"
    r"\brandom encounters?\b", re.I)
_CREATURE = re.compile(
    r'\b(?:a|an|one|two|three|four|five|six|\d+)\s+(?:\w+\s+){0,2}?'
    r'(bandits?|goblins?|wolves|wolfs?|scouts?|orcs?|zombies?|skeletons?|ogres?|'
    r'bugbears?|hobgoblins?|lurkers?|thugs?)\b', re.I)
_ATTACK = re.compile(r'\b(?:attack|attacks|attacking)\b', re.I)
_TIME = re.compile(r'\b(?:at dawn|at dusk|at night|at midnight|by morning|when night falls)\b', re.I)
_ENTER = re.compile(
    r'\b(?:when|if) the (?:party|characters|heroes).{0,60}\b(?:enter|reach|arrive|approach)\b', re.I)
_NPC = re.compile(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)?), (?:a|an|the)\b')
_NPC_ACT = re.compile(r'\b(?:asks|warns|attacks|offers|arrives|meets|demands|begs|leads)\b', re.I)
_MEET = re.compile(r'\b(?:meet|meets|meeting)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b')
_ITEM = re.compile(
    r'\b(\d+\s+gp|potions?|swords?|chests?|coins?|gems?|keys?|letters?|maps?|boxes|box|tins?|tin)\b', re.I)
_CHAPTER = re.compile(r'^(?:(?:chapter|part)\s+[\w-]+|appendix(?:\s+[\w-]+)?)\b', re.I)
_LOCATION = re.compile(r'^(?:area\s+)?([A-Z]?\d{1,3}[a-z]?)\s*[.:]\s+\S', re.I)
_OFF_SCRIPT = re.compile(
    r'\b(?:wander|wanders|skip|skips|head|heads|travel|travels|visit|visits|set out|leave for)\b', re.I)
_NOT_NAME = {'The', 'This', 'That', 'These', 'Those', 'If', 'When', 'Each', 'Any', 'Its',
             'His', 'Her', 'They', 'You', 'Your'}


def _lines(text):
    """(offset, line) treating a form feed as a line break. Both are one character."""
    flat = text.replace('\f', '\n')
    at = 0
    for line in flat.split('\n'):
        yield at, line
        at += len(line) + 1


def _core(stripped):
    kind = None
    text = stripped.strip()
    match = _PREFIX.match(text)
    if match:
        kind = match.group(1).lower()
        if kind == 'random encounter':
            kind = 'travel'
        text = match.group(2).strip()
    text = re.sub(r'\s*:\s*$', '', text).strip()
    return text, kind


def _fragment(core):
    if not core or _CHAPTER.match(core) or _LOCATION.match(core) or _DM.match(core):
        return False
    if any(ch in core for ch in '.?!;'):
        return False
    words = core.split()
    if not 1 <= len(words) <= 8 or len(core) > 60:
        return False
    real = 0
    for word in words:
        if word.casefold() in _SMALL_WORD:
            continue
        if not _HEAD_WORD.match(word):
            return False
        real += 1
    return real >= 1


def _signals_in(body, heading, travel):
    found = set()
    if heading:
        found.add('outside_heading')
    if travel:
        found.add('travel_event')
    if _YOU.search(body) or '\n>' in '\n' + body or body.lstrip().startswith('>'):
        found.add('read_aloud')
    if _CUE.search(body) or _CREATURE.search(body) or (_ATTACK.search(body) and _CREATURE.search(body)):
        found.add('encounter_cue')
    elif _ATTACK.search(body) and _YOU.search(body):
        found.add('encounter_cue')
    window = body[:500]
    npc = _NPC.search(window)
    if npc and npc.group(1).split()[0] not in _NOT_NAME and (_NPC_ACT.search(window) or _MEET.search(window)):
        found.add('npc_event')
    elif _MEET.search(window):
        found.add('npc_event')
    return found


def _score(signals):
    return sum(WEIGHTS[name] for name in signals)


def _chapter_at(chapters, offset):
    current = None
    for chapter in chapters:
        if chapter['offset'] <= offset:
            current = chapter
        else:
            break
    return current


def _part_number(title):
    match = re.search(r'\b(?:part|chapter)\s+(\d+)\b', title or '', re.I)
    return int(match.group(1)) if match else 0


def _site(title):
    """Same slug a PART heading gets in the adventure index, without importing it."""
    if not title or not re.match(r'part\b', title.strip(), re.I):
        match = re.match(r'chapter\s+[\w-]+\s*[:.\-]?\s*(.*)$', (title or '').strip(), re.I)
        name = match.group(1).strip() if match else ''
    else:
        match = re.match(r'part\s+[\w-]+\s*[:.\-]?\s*(.*)$', title.strip(), re.I)
        name = match.group(1).strip() if match else ''
    name = re.sub(r'^(?:the|a|an)\s+', '', name, flags=re.I)
    slug = re.sub(r'[^a-z0-9]+', '_', name.casefold()).strip('_')[:24]
    return slug or 'book'


def _book_number(raw):
    match = re.match(r'^([A-Za-z]?)(\d+)([A-Za-z]?)$', (raw or '').strip())
    if not match:
        return (raw or '').upper()
    return match.group(1).upper() + match.group(2) + match.group(3).lower()


def _rooms_from_heads(heads):
    rooms = []
    for kind, off, key, name, chapter in heads:
        if kind != 'location':
            continue
        rooms.append({'offset': off, 'number': _book_number(key), 'name': name, 'chapter': chapter})
    return rooms


def _inside_room(offset, rooms):
    for i, room in enumerate(rooms):
        nxt = rooms[i + 1]['offset'] if i + 1 < len(rooms) else None
        if room['offset'] < offset and (nxt is None or offset < nxt):
            # Same chapter only. A later part's rooms are not this span.
            return room
    return None


def _next_boundary(offset, rows, start_i):
    for j in range(start_i, len(rows)):
        off, line = rows[j]
        if off <= offset:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith('>'):
            continue
        if _CHAPTER.match(stripped) or _LOCATION.match(stripped) or _fragment(_core(stripped)[0]):
            return off
    return None


def _heading_at(rows, index):
    """A heading starting at rows[index], possibly split across a page break. Or None."""
    off, line = rows[index]
    stripped = line.strip()
    if not stripped or stripped.startswith('>') or _CHAPTER.match(stripped) or _LOCATION.match(stripped):
        return None
    indent = len(line) - len(line.lstrip(' '))
    core, kind = _core(stripped)
    if not _fragment(core) and kind is None:
        return None
    end_off = off + len(line)
    consumed = 1
    # Join a short fragment with the next fragment (ROAD / form feed / OPENING:).
    if _fragment(core) and len(core.split()) <= 2:
        k = index + 1
        while k < len(rows) and not rows[k][1].strip():
            k += 1
        if k < len(rows):
            nxt_core, nxt_kind = _core(rows[k][1].strip())
            joined = (core + ' ' + nxt_core).strip()
            if _fragment(nxt_core) and _fragment(joined) and len(joined.split()) <= 6:
                core = joined
                kind = kind or nxt_kind
                end_off = rows[k][0] + len(rows[k][1])
                consumed = k - index + 1
    if not _fragment(core):
        return None
    return {'offset': off, 'end': end_off, 'name': core, 'kind': kind, 'indent': indent,
            'consumed': consumed}


def _body(text, start, end):
    if end is None or end <= start:
        end = min(len(text), start + 900)
    return text[start:end]


def _trigger(body, name, prev_letter, anchor, travel, npc_name):
    if npc_name:
        return {'kind': 'npc', 'name': npc_name}
    if _ENTER.search(body):
        return {'kind': 'entering', 'place': anchor.get('name') or name}
    if _CUE.search(body) and re.search(r'\bif the characters\b', body, re.I):
        return {'kind': 'action', 'text': _short(_CUE.search(body) and body[_CUE.search(body).start():] or body)}
    if _TIME.search(body):
        return {'kind': 'time', 'when': _TIME.search(body).group(0)}
    if travel:
        return {'kind': 'travel', 'place': name}
    if prev_letter:
        return {'kind': 'follows', 'scene': prev_letter}
    return {'kind': 'entering', 'place': name}


def _short(text):
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text[:80]


def _npc_name(body):
    meet = _MEET.search(body)
    if meet:
        return meet.group(1)
    found = _NPC.search(body[:500])
    if found and found.group(1).split()[0] not in _NOT_NAME:
        return found.group(1)
    return None


def _items(body):
    found = []
    for match in _ITEM.finditer(body):
        word = match.group(1).lower()
        if word not in found:
            found.append(word)
    return found[:8]


def _relation(scene_off, indent, body, rooms, chapter, travel):
    same = [room for room in rooms if room.get('chapter') == chapter]
    prev = None
    nxt = None
    for room in same:
        if room['offset'] < scene_off:
            prev = room
        elif nxt is None:
            nxt = room
    mentioned = []
    for match in re.finditer(r'\b(?:areas?|rooms?)\s+([A-Z]?\d{1,3}[a-z]?)\b', body or '', re.I):
        number = _book_number(match.group(1))
        room = next((item for item in same if item['number'] == number), None)
        if room and room not in mentioned:
            mentioned.append(room)
    if indent >= 2 and prev is not None:
        return prev, 'in'
    if travel and re.search(r'\baround\b', body or '', re.I):
        anchor = mentioned[0] if mentioned else (prev or nxt)
        if anchor:
            return anchor, 'around'
    if prev is None and nxt is not None:
        return nxt, 'before'
    if prev is not None:
        return prev, 'after'
    return None, None


def _prompt(letter, name, page, relation, number):
    title = (name or 'passage').strip()
    title = re.sub(r'\s+', ' ', title)
    if len(title) > 40:
        title = title[:40].rsplit(' ', 1)[0]
    where = ('%s Room %s' % (relation, number)) if number else relation or 'in this part'
    return 'I think Scene %s is the %s on p.%s, %s. Right?' % (
        letter, title.casefold(), page, where)


def collect(text, heads, chapters, page_of, listed=None):
    """Playable scene heads, low-confidence checks, and the front-matter hook.

    ``heads`` is the chapter/location list build_index already found. Scenes are
    not locations yet. A check is never inserted as a location here.
    """
    rooms = _rooms_from_heads(heads)
    rows = list(_lines(text))
    raw = []
    seen = []
    listed = listed or []

    def _listed(offset):
        return any(start <= offset < end for start, end in listed)

    def _pre_key(offset):
        """A heading in the prose before this part's first numbered area. One scene covers that gap."""
        chapter = _chapter_at(chapters, offset)
        if not chapter:
            return False
        title = chapter['title']
        later = [room['offset'] for room in rooms
                 if room.get('chapter') == title and room['offset'] > chapter['offset']]
        if not later:
            return False
        return chapter['offset'] <= offset < min(later)

    i = 0
    while i < len(rows):
        found = _heading_at(rows, i)
        if not found:
            i += 1
            continue
        if _listed(found['offset']) or _pre_key(found['offset']):
            i += found['consumed']
            continue
        # One word is a stat block or a section label, not a place you can enter.
        if len(found['name'].split()) < 2:
            i += found['consumed']
            continue
        chapter = _chapter_at(chapters, found['offset'])
        # Front matter before the first part is not a scene.
        if chapters and found['offset'] < chapters[0]['offset']:
            i += found['consumed']
            continue
        title = chapter['title'] if chapter else ''
        if title and 'appendix' in title.casefold():
            i += found['consumed']
            continue
        boundary = None
        for j in range(i + found['consumed'], len(rows)):
            off, line = rows[j]
            stripped = line.strip()
            if not stripped or stripped.startswith('>'):
                continue
            core, _kind = _core(stripped)
            if _CHAPTER.match(stripped) or _LOCATION.match(stripped) or (_fragment(core) and off > found['end']):
                boundary = off
                break
        body = _body(text, found['end'], boundary)
        if len(re.sub(r'\s+', '', body)) < 20:
            i += found['consumed']
            continue
        signals = _signals_in(body, True, found['kind'] in ('travel', 'event', 'encounter'))
        if found['kind'] in ('travel', 'event'):
            signals.add('travel_event')
        room = _inside_room(found['offset'], [item for item in rooms if item.get('chapter') == title or True])
        # Inside a numbered room only when the heading is nested (indented) or the
        # offset sits strictly after that room's heading and this heading is not
        # its own block. An outside heading between rooms is not "inside".
        inside = False
        if found['indent'] >= 2:
            inside = room is not None
        own = 'outside_heading' in signals or 'travel_event' in signals
        score = _score(signals)
        playable = (len(signals) >= PROMOTE_SIGNALS and score >= PROMOTE_SCORE
                    and len(body.strip()) >= BODY_MIN and (not inside or own or found['indent'] >= 2))
        # A heading with read-aloud is two signals. A heading alone is a check.
        if len(signals) < PROMOTE_SIGNALS or score < PROMOTE_SCORE or len(body.strip()) < BODY_MIN:
            playable = False
        if playable and inside and found['indent'] < 2 and 'outside_heading' not in signals:
            playable = False
        anchor, relation = _relation(found['offset'], found['indent'], body, rooms, title, 'travel_event' in signals)
        raw.append({
            'offset': found['offset'], 'body_at': found['end'] + 1 if found['end'] < len(text) else found['end'],
            'end': boundary if boundary is not None else min(len(text), found['end'] + len(body) + 1),
            'name': found['name'], 'indent': found['indent'], 'signals': sorted(signals),
            'score': score, 'playable': playable, 'chapter': title,
            'part': _part_number(title), 'site': _site(title), 'page': page_of(found['offset']),
            'body': body, 'anchor_room': anchor, 'relation': relation or 'before',
            'travel': 'travel_event' in signals, 'npc': _npc_name(body),
        })
        seen.append(found['offset'])
        i += found['consumed']

    raw.extend(_preamble_scenes(text, chapters, rooms, seen, page_of))

    # Body signals with no heading: encounter or NPC text before the first room,
    # or a lone cue. One signal stays a check. Two signals before the first key promote.
    first_room = min((room['offset'] for room in rooms), default=None)
    for match in _CUE.finditer(text):
        if any(abs(match.start() - off) < 80 for off in seen):
            continue
        if _inside_room(match.start(), rooms) and not (first_room and match.start() < first_room):
            chapter = _chapter_at(chapters, match.start())
            title = chapter['title'] if chapter else ''
            if title and 'appendix' in title.casefold():
                continue
            snippet = text[match.start():match.start() + 180]
            name = _short(snippet)
            name = name.split(',')[0]
            raw.append({
                'offset': match.start(), 'body_at': match.start(), 'end': match.start() + len(snippet),
                'name': name, 'indent': 0, 'signals': ['encounter_cue'], 'score': WEIGHTS['encounter_cue'],
                'playable': False, 'chapter': title, 'part': _part_number(title), 'site': _site(title),
                'page': page_of(match.start()), 'body': snippet, 'anchor_room': _inside_room(match.start(), rooms),
                'relation': 'in', 'travel': False, 'npc': _npc_name(snippet), 'cue_only': True,
            })
            seen.append(match.start())

    # Letters restart in each part, across playable scenes and checks together,
    # so a check keeps a stable letter the DM can answer.
    by_part = {}
    for item in raw:
        by_part.setdefault((item['site'], item['part']), []).append(item)
    for group in by_part.values():
        group.sort(key=lambda item: item['offset'])
        prev = None
        for n, item in enumerate(group):
            item['letter'] = chr(ord('A') + n) if n < 26 else 'Z%d' % n
            anchor = item.get('anchor_room') or {}
            item['trigger'] = _trigger(item['body'], item['name'], prev if item['playable'] else prev,
                                        {'name': (anchor or {}).get('name'), 'number': (anchor or {}).get('number')},
                                        item['travel'], item.get('npc'))
            if item['playable']:
                prev = item['letter']
            number = (anchor or {}).get('number')
            item['check_line'] = _prompt(item['letter'], item['name'], item['page'], item['relation'], number)

    scene_heads = []
    checks = []
    for item in raw:
        anchor = item.get('anchor_room') or {}
        record = {
            'letter': item['letter'], 'part': item['chapter'], 'part_n': item['part'],
            'page': item['page'], 'name': item['name'], 'site': item['site'],
            'relation': item['relation'],
            'anchor': {'number': anchor.get('number'), 'name': anchor.get('name'),
                       'relation': item['relation']},
            'trigger': item['trigger'], 'signals': item['signals'], 'score': item['score'],
            'confidence': 'high' if item['playable'] else 'low',
            'span': [item['body_at'], item['end']], 'offset': item['offset'],
            'body_at': item['body_at'], 'indent': item['indent'],
        }
        if item['playable']:
            scene_heads.append(('scene', item['offset'], record, item['name'], item['chapter']))
        else:
            record['status'] = 'check'
            record['answer'] = None
            record['line'] = item['check_line']
            checks.append(record)
    checks.sort(key=lambda item: item['offset'])
    front = _front(text, chapters)
    return scene_heads, checks, front


def _preamble_scenes(text, chapters, rooms, seen, page_of):
    """A fight told before the first numbered room, with no heading of its own.

    Two signals promote it (read-aloud plus the creatures). One signal stays out.
    Book apparatus (Introduction, Glossary, Rests) is not a scene.
    """
    by_chapter = {}
    for room in rooms:
        by_chapter.setdefault(room.get('chapter') or '', []).append(room)
    titled = {chapter['title']: chapter for chapter in chapters}
    found = []
    for title, group in by_chapter.items():
        group.sort(key=lambda room: room['offset'])
        first = group[0]
        chapter = titled.get(title)
        start = chapter['offset'] if chapter else 0
        if any(start <= off < first['offset'] for off in seen):
            continue
        body = text[start:first['offset']]
        body = re.sub(r'^[^\n]*', '', body, count=1)
        if len(re.sub(r'\s+', '', body)) < BODY_MIN:
            continue
        if _DM.match(body.strip()):
            continue
        has_head = any(
            _fragment(_core(line.strip().lstrip('>').strip())[0])
            for line in body.splitlines() if line.strip())
        signals = _signals_in(body, has_head, False)
        if len(signals) < PROMOTE_SIGNALS or _score(signals) < PROMOTE_SCORE:
            continue
        name = 'Opening'
        for line in body.splitlines():
            core, _kind = _core(line.strip().lstrip('>').strip())
            if core and _fragment(core) and not _DM.match(core):
                name = core
                break
        at = start + (text[start:first['offset']].find(body.lstrip()[:12]) if body.strip() else 0)
        if at < start:
            at = start
        found.append({
            'offset': at, 'body_at': at, 'end': first['offset'],
            'name': name, 'indent': 0, 'signals': sorted(signals),
            'score': _score(signals), 'playable': True, 'chapter': title,
            'part': _part_number(title), 'site': _site(title), 'page': page_of(at),
            'body': body, 'anchor_room': first, 'relation': 'before',
            'travel': False, 'npc': _npc_name(body),
        })
    return found


def _front(text, chapters):
    end = min((chapter['offset'] for chapter in chapters), default=min(len(text), 1500))
    front = text[:end]
    hook = ''
    for para in re.split(r'\n\s*\n', front):
        clean = re.sub(r'\s+', ' ', para).strip()
        if len(clean) >= 40 and not _CHAPTER.match(clean):
            hook = clean[:400]
            break
    said = re.search(r'(?:play|the adventure|the game)\s+begins\b[^.!\n]{0,140}', front, re.I)
    return {'hook': hook, 'book_says': re.sub(r'\s+', ' ', said.group(0)).strip() if said else ''}


def finish(index, text):
    """Fill scene contents, human labels, and the trigger dicts. Mutates ``index``."""
    locations = index['locations']
    multi = len({loc.get('part_n') for loc in locations.values() if loc.get('part_n')}) > 1
    order = []
    for key, loc in locations.items():
        if loc.get('type') != 'scene':
            loc.setdefault('type', 'room')
            loc.setdefault('number', loc.get('bare'))
        anchor = loc.get('anchor') or {}
        number = anchor.get('number')
        relation = loc.get('relation')
        part_n = loc.get('part_n') or 0
        if loc.get('type') == 'scene':
            qual = 'Part %s, ' % part_n if multi and part_n > 1 else ''
            letter = loc.get('letter')
            room = 'Room %s' % number if number else 'the first room'
            rel = relation or 'before'
            loc['label'] = '%sScene %s: plays %s %s (p. %s)' % (qual, letter, rel, room, loc.get('page'))
            loc['banner'] = 'Starting at %sScene %s, %s %s (p. %s)' % (qual, letter, rel, room, loc.get('page'))
            loc['pick'] = letter if not (multi and part_n > 1) else 'Part %s, Scene %s' % (part_n, letter)
            span = text[loc['body'][0]:loc['body'][1]]
            read = [re.sub(r'\s+', ' ', line.strip().lstrip('>').strip())
                    for line in span.split('\n') if line.strip().startswith('>')]
            loc['contents'] = {
                'read_aloud': [line for line in read if line][:8],
                'creatures': [c.get('name') for c in loc.get('creatures') or []],
                'npcs': list(loc.get('npcs') or []),
                'items': _items(span),
            }
            loc['leads_to'] = []
            for link in loc.get('connections') or []:
                other = locations.get(link['to']) or {}
                loc['leads_to'].append(other.get('name') or link['to'])
        else:
            qual = 'Part %s, ' % part_n if multi and part_n > 1 else ''
            number = loc.get('number') or loc.get('bare')
            loc['label'] = '%sRoom %s (p. %s)' % (qual, number, loc.get('page'))
            loc['banner'] = 'Starting at %sRoom %s (p. %s)' % (qual, number, loc.get('page'))
            loc['pick'] = number if not (multi and part_n > 1) else 'Part %s, Room %s' % (part_n, number)
        order.append(loc)
    order.sort(key=lambda loc: loc.get('offset') or 0)
    index['starts'] = [{'pick': loc.get('pick'), 'line': loc.get('label'), 'id': loc.get('key'),
                        'type': loc.get('type'), 'default': loc.get('key') == index.get('start')}
                       for loc in order if loc.get('pick')]
    for item in index.get('checks') or []:
        if not item.get('line'):
            anchor = item.get('anchor') or {}
            item['line'] = _prompt(item.get('letter'), item.get('name'), item.get('page'),
                                   item.get('relation'), anchor.get('number'))
    index['triggers'] = _triggers(index)
    index['by_slug'] = {_slug(key): key for key in locations}
    return index


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '_', str(text).casefold()).strip('_')[:40] or 'x'


def _triggers(index):
    """place → scenes, npc → scenes, event → scenes. Values are id lists, book order."""
    by_place, by_npc, by_event = {}, {}, {}
    order = {}
    entries = {}
    n = 0
    locs = sorted(index['locations'].values(), key=lambda loc: loc.get('offset') or 0)
    for loc in locs:
        key = loc.get('key')
        if not key:
            continue
        order[key] = n
        n += 1
        names = [loc.get('name') or '']
        if loc.get('type') == 'room':
            names.append('room %s' % (loc.get('number') or ''))
            names.append(str(loc.get('number') or ''))
        else:
            names.append('scene %s' % (loc.get('letter') or ''))
            anchor = loc.get('anchor') or {}
            if anchor.get('name'):
                names.append(anchor['name'])
            if anchor.get('number'):
                names.append('room %s' % anchor['number'])
        part = loc.get('part') or ''
        part_name = re.sub(r'^(?:part|chapter)\s+[\w-]+\s*[:.\-]?\s*', '', part, flags=re.I)
        if part_name:
            names.append(part_name)
        for name in names:
            _add(by_place, name, key)
            for word in re.findall(r"[a-z0-9']{4,}", name.casefold()):
                _add(by_place, word, key)
        for npc in (loc.get('contents') or {}).get('npcs') or loc.get('npcs') or []:
            _add(by_npc, npc, key)
        trigger = loc.get('trigger') or {}
        if trigger.get('name'):
            _add(by_npc, trigger['name'], key)
        if trigger.get('kind'):
            _add(by_event, trigger['kind'], key)
        if loc.get('type') == 'scene':
            entries[key] = _entry(loc)
        # A room is the place an off-script move can land, even when it is not a scene.
        if loc.get('type') == 'room':
            entries.setdefault(key, _entry(loc))
    return {'by_place': by_place, 'by_npc': by_npc, 'by_event': by_event,
            'order': order, 'entries': entries,
            'scene_of': {loc.get('key'): loc.get('key') for loc in locs if loc.get('type') == 'scene'}}


def _add(table, name, key):
    token = re.sub(r'\s+', ' ', str(name or '').casefold()).strip()
    if len(token) < 2:
        return
    bucket = table.setdefault(token, [])
    if key not in bucket:
        bucket.append(key)


def _entry(loc):
    contents = loc.get('contents') or {}
    return {
        'id': loc.get('key'), 'label': loc.get('label'), 'banner': loc.get('banner'),
        'part': loc.get('part'), 'page': loc.get('page'), 'anchor': loc.get('anchor'),
        'trigger': loc.get('trigger'), 'read_aloud': contents.get('read_aloud') or [],
        'creatures': contents.get('creatures') or [], 'npcs': contents.get('npcs') or [],
        'items': contents.get('items') or [], 'leads_to': loc.get('leads_to') or [],
        'span': loc.get('body'), 'confidence': loc.get('confidence') or 'high',
        'signals': loc.get('signals') or [], 'type': loc.get('type'), 'name': loc.get('name'),
    }


def lookup(triggers, action, current_id=None):
    """Dict lookups on the action's own words. No scan of the book."""
    triggers = triggers or {}
    by_place = triggers.get('by_place') or {}
    by_npc = triggers.get('by_npc') or {}
    by_event = triggers.get('by_event') or {}
    words = re.findall(r"[a-z0-9']+", (action or '').casefold())
    phrases = list(words)
    phrases += [' '.join(words[i:i + 2]) for i in range(len(words) - 1)]
    phrases += [' '.join(words[i:i + 3]) for i in range(len(words) - 2)]
    hits = []
    for phrase in phrases:
        for table in (by_place, by_npc, by_event):
            for key in table.get(phrase) or ():
                if key not in hits:
                    hits.append(key)
    order = triggers.get('order') or {}
    current_at = order.get(current_id)
    resolved = None
    if hits:
        if current_at is None:
            resolved = hits[0]
        else:
            resolved = min(hits, key=lambda key: abs(order.get(key, 0) - current_at))
    off = bool(_OFF_SCRIPT.search(action or ''))
    unscripted = bool(off and not hits)
    return {'hits': hits, 'resolved': resolved, 'unscripted': unscripted, 'current': current_id}


def turn(folder, action, room_id=None):
    """One prepare's scene lookup. ``lookup_ms`` is the dict lookup, not file IO."""
    folder = Path(folder)
    path = folder / 'triggers.json'
    if not path.is_file():
        return {'active': False, 'lookup_ms': 0.0}
    try:
        triggers = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'active': False, 'lookup_ms': 0.0}
    current = _current(triggers, room_id)
    started = time.perf_counter()
    found = lookup(triggers, action, current)
    elapsed = (time.perf_counter() - started) * 1000.0
    entries = triggers.get('entries') or {}
    send = found['resolved'] if found['resolved'] and found['resolved'] != current else None
    # The scene the party is already in is delivered once, then as a delta.
    if send is None and current and action in (None, '', '[scene entry]'):
        send = current
    return {'active': True, 'lookup_ms': round(elapsed, 3), 'current': current,
            'current_entry': entries.get(current) if current else None,
            'triggers': [entries[key]['label'] for key in found['hits'] if key in entries],
            'trigger_ids': found['hits'], 'resolved': found['resolved'],
            'unscripted': found['unscripted'], 'send': send,
            'entry': entries.get(send) if send else None}


def _current(triggers, room_id):
    if not room_id:
        return None
    match = re.match(r'^adv-([0-9a-f]{8})-(.+)$', str(room_id))
    if not match:
        return None
    slug = match.group(2)
    # by_slug is stored beside entries' ids; the slug map is on the index, copied here.
    return (triggers.get('slug_to_id') or {}).get(slug)


def write_side(folder, index):
    """The small trigger file prepare reads. The full index stays private next to the save."""
    folder = Path(folder)
    triggers = dict(index.get('triggers') or {})
    triggers['slug_to_id'] = {}
    for key in index.get('locations') or {}:
        triggers['slug_to_id'][_slug(key)] = key
    (folder / 'triggers.json').write_text(
        json.dumps(triggers, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    sent = folder / 'scenes_sent.json'
    if not sent.is_file():
        sent.write_text('[]', encoding='utf-8')


def take_entry(folder, scene_id):
    """Full entry the first time this scene is sent, then None (the caller sends a delta)."""
    folder = Path(folder)
    path = folder / 'scenes_sent.json'
    try:
        sent = set(json.loads(path.read_text(encoding='utf-8'))) if path.is_file() else set()
    except (OSError, ValueError):
        sent = set()
    if scene_id in sent:
        return None
    sent.add(scene_id)
    path.write_text(json.dumps(sorted(sent)), encoding='utf-8')
    triggers = {}
    try:
        triggers = json.loads((folder / 'triggers.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return (triggers.get('entries') or {}).get(scene_id)


def log_unscripted(folder, turn_id, action):
    path = Path(folder) / 'unscripted.jsonl'
    line = json.dumps({'turn_id': turn_id, 'action': action}, ensure_ascii=False)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(line + '\n')


def mark_scene_lines(text):
    """Prefix second-person lines under an unnumbered scene heading with ``> ``.

    Numbered rooms are already marked. This only touches the span after a scene
    heading and before the next numbered key, so a flush read-aloud still mounts.
    """
    rows = list(_lines(text))
    if not rows:
        return text
    mark_at = set()
    i = 0
    while i < len(rows):
        found = _heading_at(rows, i)
        if not found:
            i += 1
            continue
        j = i + found['consumed']
        while j < len(rows):
            _off, line = rows[j]
            stripped = line.strip()
            if stripped and (_CHAPTER.match(stripped) or _LOCATION.match(stripped)):
                break
            core, _kind = _core(stripped)
            if stripped and _fragment(core) and rows[j][0] > found['end']:
                break
            if stripped and not stripped.startswith('>') and _YOU.search(stripped):
                mark_at.add(j)
            j += 1
        i += found['consumed']
    # An unnumbered fight before the first key has no heading. Its second-person lines
    # are still the read-aloud, or the opening compiles as an empty room.
    in_preamble = False
    for n, (_off, line) in enumerate(rows):
        stripped = line.strip()
        if _CHAPTER.match(stripped):
            in_preamble = True
            continue
        if _LOCATION.match(stripped) or (_fragment(_core(stripped)[0]) if stripped else False):
            in_preamble = False
            continue
        if in_preamble and stripped and not stripped.startswith('>') and _YOU.search(stripped):
            mark_at.add(n)
    if not mark_at:
        return text
    out = []
    for n, (off, line) in enumerate(rows):
        # Rebuild with the original break: a form feed was normalized to a newline
        # in _lines, so the source still has whichever break was there. Copy source
        # slices instead of rejoining, so page breaks stay put.
        if n in mark_at:
            stripped = line.strip()
            pad = line[:len(line) - len(line.lstrip(' '))]
            line = pad + '> ' + stripped
        out.append(line)
    # Restore form feeds: _lines turned them into newlines, so compare lengths.
    # Walk the original and emit marked lines.
    return _restore(text, out)


def _restore(text, lines):
    """Put marked lines back. Form feeds and newlines stay where they were."""
    parts = re.split(r'(\n|\f)', text)
    # parts alternate line, break, line, break...
    li = 0
    built = []
    i = 0
    while i < len(parts):
        if li < len(lines):
            built.append(lines[li])
            li += 1
        else:
            built.append(parts[i])
        if i + 1 < len(parts):
            built.append(parts[i + 1])
        i += 2
    return ''.join(built)


CHANGE_KINDS = ('dead', 'fled', 'loot', 'door', 'trap', 'npc', 'fire', 'moved', 'freed')
_REPEAT = re.compile(r'\b(?:each time|whenever|every time)\b', re.I)


def _blank(repeatable=False):
    return {'status': 'unvisited', 'changes': [], 'actors': {}, 'trigger_spent': False,
            'repeatable': bool(repeatable)}


def enter_place(state, place_id, repeatable=False):
    """Mark a scene or room active. A spent trigger does not fire again."""
    if not place_id:
        return {'revisit': False, 'trigger_fires': False, 'record': None}
    places = state.setdefault('places', {})
    rec = places.get(place_id)
    if rec is None:
        rec = _blank(repeatable)
        places[place_id] = rec
    if repeatable:
        rec['repeatable'] = True
    spent = bool(rec.get('trigger_spent')) and not rec.get('repeatable')
    rec['returned'] = bool(spent)
    rec['status'] = 'active'
    return {'revisit': bool(spent), 'trigger_fires': not spent, 'record': rec}


def leave_place(state, place_id):
    """Leaving spends the trigger. Changes keep the status 'changed'; otherwise 'resolved'."""
    rec = (state.get('places') or {}).get(place_id)
    if not rec or rec.get('repeatable'):
        if rec:
            rec['status'] = 'changed' if rec.get('changes') else 'active'
        return
    rec['trigger_spent'] = True
    rec['status'] = 'changed' if rec.get('changes') else 'resolved'


def log_change(state, place_id, kind, what, detail=''):
    """One small line on this room's change log. Dead stays dead. Fled is a relocation."""
    if not place_id or kind not in CHANGE_KINDS:
        return None
    places = state.setdefault('places', {})
    rec = places.setdefault(place_id, _blank())
    change = {'kind': kind, 'what': str(what or '')[:80], 'detail': str(detail or '')[:120]}
    if change not in rec['changes']:
        rec['changes'].append(change)
        rec['changes'] = rec['changes'][-24:]
    if kind == 'dead':
        rec['actors'][change['what']] = 'dead'
    elif kind == 'fled':
        rec['actors'][change['what']] = 'fled'
    elif kind in ('freed', 'npc'):
        rec['actors'][change['what']] = change['detail'] or kind
    rec['status'] = 'changed'
    rec['trigger_spent'] = True if not rec.get('repeatable') else rec.get('trigger_spent')
    return change


def apply_actors(state, source):
    """Monsters the log says are dead or fled are not the book's living copies."""
    rec = (state.get('places') or {}).get((source or {}).get('id')) or {}
    actors = (state.get('actors') or {})
    by_name = {}
    for key, actor in actors.items():
        if isinstance(actor, dict):
            by_name.setdefault(actor.get('name') or key, key)
    for name, status in (rec.get('actors') or {}).items():
        key = by_name.get(name)
        if key and status in ('dead', 'fled'):
            actors[key]['status'] = status
            if status == 'dead':
                actors[key]['visible'] = True


def revisit_view(state, place_id):
    """The room's current state for a return: book base stays cached; this is the change log."""
    rec = (state.get('places') or {}).get(place_id)
    if not rec or not rec.get('returned'):
        return None
    lines = []
    for change in rec.get('changes') or []:
        kind, what, detail = change.get('kind'), change.get('what') or '', change.get('detail') or ''
        if kind == 'dead':
            lines.append('%s is dead.' % what)
        elif kind == 'fled':
            lines.append('%s fled%s.' % (what, (' ' + detail) if detail else ''))
        elif kind == 'loot':
            lines.append('%s is gone, taken.' % what)
        elif kind == 'door':
            lines.append('The %s is %s.' % (what, detail or 'open'))
        elif kind == 'trap':
            lines.append('The %s is disarmed.' % what)
        elif kind == 'fire':
            lines.append('%s.' % (detail or (what + ' has burned')))
        elif kind == 'moved':
            lines.append('%s has been moved.' % what)
        elif kind == 'freed':
            lines.append('%s is free.' % what)
        else:
            lines.append('%s %s.' % (what, detail or kind))
    narration = "You're back. " + (' '.join(lines) if lines else 'It is as you left it.')
    return {'id': place_id, 'status': rec.get('status'), 'changes': list(rec.get('changes') or []),
            'actors': dict(rec.get('actors') or {}), 'trigger_fires': bool(rec.get('repeatable')),
            'narration': narration, 'read_aloud': False}


def score_key(found, gold):
    """Recall and precision of detected scene names against a private answer key.

    ``found`` and ``gold`` are iterables of scene names. The key stays out of git;
    this only does the arithmetic.
    """
    found_set = {re.sub(r'\s+', ' ', str(name).casefold()).strip() for name in found if name}
    gold_set = {re.sub(r'\s+', ' ', str(name).casefold()).strip() for name in gold if name}
    if not gold_set and not found_set:
        return {'available': True, 'recall': 1.0, 'precision': 1.0, 'hit': 0, 'gold': 0, 'found': 0}
    hit = len(found_set & gold_set)
    recall = (hit / float(len(gold_set))) if gold_set else 0.0
    precision = (hit / float(len(found_set))) if found_set else 0.0
    return {'available': True, 'recall': recall, 'precision': precision,
            'hit': hit, 'gold': len(gold_set), 'found': len(found_set)}
