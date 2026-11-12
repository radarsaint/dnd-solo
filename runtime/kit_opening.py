"""One opening beat. Every verb reads this record. Python keeps it.

The host still skims and quotes. This module does not choose an opening from the
whole book. It records, from the validated pages, what the player can hear, what
stays behind the screen, and what the people in the beat want. A failed notice
lets their default means act. Talk, stealth, or leaving changes the situation:
the goal stays, the means adapt, and a prepared fight is not dragged forward.

What the player has heard or seen is ``observed``. Kit's reading of tactics stays
in ``private`` and is never spoken as fact.
"""
import re

from .kit_plan import plan_event

_PLACE = (
    'road', 'street', 'lane', 'trail', 'path', 'clearing', 'hall', 'room',
    'bridge', 'square', 'yard', 'wood', 'forest', 'shore', 'cellar', 'cave',
)
_SCREENISH = re.compile(
    r'\b(?:seem|actually|in truth|not what they|will lie|the truth is|secretly)\b',
    re.I)
_LOOK = re.compile(r'\b(?:look|looking|glance|scan|survey|peer)\b', re.I)
_TALK = re.compile(r'\b(?:talk|speak|say|call out|hail|ask|greet)\b', re.I)
_SNEAK = re.compile(r'\b(?:sneak|hide|avoid|slip past|go around)\b', re.I)
_LEAVE = re.compile(r'\b(?:leave|turn back|go back|walk away|flee|retreat)\b', re.I)
_INITIATIVE = re.compile(r'\b(?:roll initiative|initiative)\b', re.I)
_SUCCESS_AT = 10


def _skim():
    from . import kit_skim
    return kit_skim


def player_line(text):
    """A sentence the player can be standing in. A note behind the screen is not."""
    skim = _skim()
    if skim._go_fail(text) or skim._unsafe(text) or skim._blocks_quote(text):
        return False
    if _SCREENISH.search(text or '') or _FRONT.search(text or ''):
        return False
    return skim._scene_line(text)


_FRONT = re.compile(
    r'\b(?:credits?|licen[sc]e|copyright|how to|how-to|rules|procedure|synopsis|'
    r'introduction|preface|foreword|contents|front matter|legal notice|trademark|'
    r'published by|villain|background|appendix)\b|\bDC\b',
    re.I)
_NOT_CREATURE = re.compile(
    r'^(?:wisdom|check|hour|hours|day|days|mile|miles|gold|foot|feet|word|words|'
    r'page|pages|character|characters|player|players|party|time|times|level|'
    r'section|chapter|part|area|room|dc)$',
    re.I)
_COUNT = re.compile(
    r'\b(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+'
    r'([A-Za-z][A-Za-z]+)\b',
    re.I)
_NOT_CREATURE = re.compile(
    _NOT_CREATURE.pattern[:-2] + r'|hide|hides|hiding|wait|waits|waiting|attack|attacks|'
    r'look|looks|notice|notices|come|comes|close|anyone|careful)$',
    re.I)
_ORDERS = re.compile(
    r'\b(?:wants?|wanted)\s+(?:to\s+)?([^.]{3,80})'
    r'|\b(?:has orders to|ordered to|orders to)\s+([^.]{3,80})',
    re.I)
_CUE = re.compile(
    r'\b(?:hid(?:e|es|ing|den)|wait(?:s|ing)?|ambush(?:es|ed|ing)?|attack(?:s|ed|ing)?)\b',
    re.I)


def place_noun(name, fiction):
    """The place word inside the read-aloud. A heading is not consulted."""
    return _place_in(fiction)


def _place_in(text):
    """Earliest place word in this text. Room only when the text says room."""
    found = ''
    at = None
    for noun in _PLACE:
        match = re.search(r'\b%s\b' % noun, text or '', re.I)
        if not match:
            continue
        if at is None or match.start() < at:
            at = match.start()
            found = noun
    return found


def kit_line(title):
    """Kit names a place in her own voice. The book's notes are not in the line."""
    name = (title or 'here').strip()
    folded = name.casefold()
    if folded in ('here', 'the here'):
        folded = 'the start'
    elif not folded.startswith('the '):
        folded = 'the ' + folded
    return "We'll start at %s. What do you do?" % folded


def _find_clause(text):
    match = re.search(r'\b(?:notices?|spots?|finds?)\s+(.{3,})$', text or '', re.I)
    if not match:
        return ''
    clause = match.group(1).strip().rstrip('.')
    if _skim()._go_fail(clause) or _SCREENISH.search(clause):
        return ''
    if len(clause.split()) < 2:
        return ''
    return 'You notice %s.' % clause


def _goal_from(encounter, fiction, means):
    """What the encounter text says they want. The generic line is a last resort."""
    blob = encounter or ''
    match = _ORDERS.search(blob)
    if match:
        piece = (match.group(1) or match.group(2) or '').strip().rstrip('.')
        if match.group(1):
            return 'They want %s.' % piece, False
        return 'They have orders to %s.' % piece, False
    match = _CUE.search(blob)
    if match:
        sentence = _skim().normalize(match.string[max(0, match.start() - 40):match.end() + 60])
        sentence = sentence.split('.')[0].strip()
        if sentence:
            if not sentence[0].isupper():
                sentence = sentence[0].upper() + sentence[1:]
            return sentence.rstrip('.') + '.', False
    if means == 'ambush':
        return 'They are waiting in ambush.', False
    if fiction or encounter:
        return 'They want to meet whoever is here.', True
    return '', True


def _creature_name(phrase):
    words = [word for word in phrase.split() if word]
    if not words:
        return ''
    head = words[-1]
    if _NOT_CREATURE.match(head):
        return ''
    if len(head) < 3:
        return ''
    return head


def _people(fiction, encounter):
    """Creatures and NPCs the encounter puts here. Setup patrons are not among them."""
    from .kit_adventure import SEE_RE, _introduced_names, _slug
    skim = _skim()
    heard = ' '.join(fiction).casefold()
    people = []
    seen = set()

    def add(key, name, hidden, kind):
        stem = key[:-1] if key and key.endswith('s') and len(key) > 4 else key
        if not key or key in seen or stem in seen or _NOT_CREATURE.match(name or ''):
            return
        if _FRONT.search(name or ''):
            return
        seen.add(key)
        seen.add(stem)
        people.append({
            'id': key, 'name': name, 'hidden': bool(hidden), 'kind': kind,
            'revealed': not hidden, 'addressable': not hidden,
        })

    for name in _introduced_names(' '.join(fiction)):
        add(_slug(name), name, False, 'speaker')
    if skim._CHILD.search(heard):
        add('children', 'Children', False, 'speaker')
    from .kit_adventure import _GREET
    # A named person who hails is already on the list. A nameless greeting still is.
    for sentence in skim._sentences(' '.join(fiction)) or fiction:
        if _GREET.search(sentence) and not _introduced_names(sentence):
            add('greeter', 'Greeter', False, 'speaker')
            break
    for name in _introduced_names(encounter or ''):
        add(_slug(name), name, name.casefold() not in heard, 'speaker')
    blob = encounter or ''
    for match in SEE_RE.finditer(blob):
        name = _creature_name(match.group(1))
        if name:
            add(_slug(name), name.title(), name.casefold() not in heard, 'creature')
    for match in _COUNT.finditer(blob):
        name = _creature_name(match.group(1))
        if not name:
            continue
        sentence = skim.normalize(blob[max(0, match.start() - 20):match.end() + 80])
        if not _CUE.search(sentence) and 'stat' not in sentence.casefold():
            continue
        add(_slug(name), name.title(), name.casefold() not in heard, 'creature')
    return people


def _layout_stream(page_text):
    """Left column, then right column, when a wide gap splits the extract.

    pdftotext -layout puts two columns on one line. The read-aloud is down one
    side. The other side is a sidebar and is not the encounter under the box.
    """
    pages = []
    for page in (page_text or '').split('\f'):
        lefts, rights, gapped = [], [], False
        for line in page.split('\n'):
            parts = [part.strip() for part in re.split(r'\s{3,}', line.rstrip()) if part.strip()]
            if len(parts) >= 2:
                gapped = True
                lefts.append(parts[0])
                rights.append(' '.join(parts[1:]))
            elif parts:
                lefts.append(parts[0])
        if gapped:
            pages.append('\n'.join(lefts + [''] + rights))
        else:
            pages.append(page)
    return '\f'.join(pages)


def _best_stream(page_text, burst):
    """The extract order in which the host's read-aloud is one contiguous span."""
    skim = _skim()
    burst_norm = skim.normalize(burst or '')
    layout = _layout_stream(page_text)
    for stream in (layout, page_text or ''):
        if not burst_norm or skim._contiguous(burst_norm, skim.normalize(stream)):
            return stream
    return page_text or ''


def _stops_unit(plain):
    """A new location or an appendix ends this opening. A sidebar does not."""
    skim = _skim()
    if not plain:
        return False
    if skim._LATER.match(plain) or skim._KEYED.match(plain):
        return True
    if re.match(r'^appendix\b', plain, re.I):
        return True
    return False


def _sidebar_line(plain):
    """How-to, a procedure, or a contents line sitting in the other column."""
    if not plain:
        return False
    if re.match(
            r'^(?:how to|how-to|procedure|contents|credits|synopsis|sidebar)\b',
            plain, re.I):
        return True
    if _skim()._heading_line(plain) and (_FRONT.search(plain) or re.search(r'\bDC\b', plain)):
        return True
    return False


def _encounter_sentence(sentence):
    """A creature, an order, or a notice in the text under the read-aloud."""
    from .kit_adventure import SEE_RE
    if SEE_RE.search(sentence or ''):
        return True
    if _ORDERS.search(sentence or ''):
        return True
    if _COUNT.search(sentence or '') and _CUE.search(sentence or ''):
        return True
    if re.search(r'\b(?:notices?|spots?|finds?)\b', sentence or '', re.I) and not _skim()._SCENE_VERB.search(
            re.sub(r'\b(?:notices?|spots?|finds?)\b', '', sentence or '', flags=re.I)):
        return True
    return False


def _split_opening(page_text, burst):
    """The read-aloud that holds the burst, and the encounter text after it.

    Works on a boxed extract and on pdftotext -layout, which does not write ``>``.
    Setup before the read-aloud, and a sidebar in the other column, are not the beat.
    """
    skim = _skim()
    stream = _best_stream(page_text, burst).replace('\f', '\n')
    lines = stream.split('\n')
    burst_norm = skim.normalize(burst or '')
    start = None
    for index, line in enumerate(lines):
        plain = skim.normalize(line.strip().lstrip('>').strip())
        if burst_norm and skim._contiguous(burst_norm, plain):
            start = index
            break
    if start is None:
        for index, line in enumerate(lines):
            if line.strip().startswith('>'):
                start = index
                break
    if start is None:
        return [], ''
    while start > 0 and lines[start - 1].strip().startswith('>'):
        start -= 1
    fiction = []
    encounter = []
    fiction_closed = False
    index = start
    while index < len(lines):
        raw = lines[index].strip()
        index += 1
        if not raw:
            continue
        plain = raw.lstrip('>').strip()
        if _stops_unit(plain) or (skim._heading_line(plain) and not raw.startswith('>')
                                  and not _sidebar_line(plain)):
            if fiction or encounter:
                break
            continue
        if _sidebar_line(plain):
            continue
        for sentence in skim._sentences(plain) or ([skim.normalize(plain)] if skim.normalize(plain) else []):
            if not sentence:
                continue
            # Prep ends the read-aloud. A later player line is not this opening.
            # The encounter can still sit past a sidebar, on the next page.
            if skim._go_fail(sentence) or _SCREENISH.search(sentence):
                fiction_closed = True
                continue
            if skim._blocks_quote(sentence) and not _encounter_sentence(sentence):
                continue
            if _encounter_sentence(sentence) and not skim._contiguous(burst_norm, skim.normalize(sentence)):
                if skim._blocks_quote(sentence) and not _COUNT.search(sentence) and 'stat' not in sentence.casefold():
                    continue
                encounter.append(sentence)
            elif not fiction_closed and (
                    player_line(sentence) or skim._contiguous(burst_norm, skim.normalize(sentence))):
                if sentence not in fiction:
                    fiction.append(skim.normalize(sentence))
    return fiction, '\n'.join(encounter)


def fiction_lines(page_text, burst):
    """Player lines from this opening, in order. A later location is not included."""
    fiction, _encounter = _split_opening(page_text, burst)
    return fiction


def opening_text(page_text, burst):
    """The read-aloud plus the encounter under it. Setup before the box is left out."""
    box, encounter = _split_opening(page_text, burst)
    return '\n'.join(box + ([encounter] if encounter else []))


def screen_lines(page_text, fiction):
    skim = _skim()
    heard = {line.casefold() for line in fiction}
    out = []
    for sentence in skim._sentences(page_text or ''):
        if not sentence or sentence.casefold() in heard:
            continue
        if player_line(sentence):
            continue
        out.append(skim.normalize(sentence))
    return out


def build_beat(page_text, burst, place_name):
    """The one record for this opening, read from the box and the encounter under it.

    An empty location index does not matter. The text is enough.
    """
    _box, encounter = _split_opening(page_text, burst)
    fiction = fiction_lines(page_text, burst)
    noun = _place_in(' '.join(fiction))
    people = _people(fiction, encounter)
    means = 'ambush' if any(person['kind'] == 'creature' and person['hidden'] for person in people) else (
        'meet' if people else 'none')
    goal, generic = _goal_from(encounter, fiction, means)
    find = _find_clause(encounter)
    holds = any(person.get('hidden') for person in people)
    for person in people:
        person['goal'] = goal or 'They are in this scene.'
        person['motive'] = person['goal']
    return {
        'fiction': fiction,
        'heard': 0,
        'place_noun': noun,
        'place_name': (place_name or '').strip(),
        'screen': screen_lines(page_text, fiction),
        'notice': {
            'holds': holds, 'pending': False, 'resolved': False, 'find': find,
        },
        'people': people,
        'pressure': {
            'goal': goal, 'means': means, 'acted': False, 'bypassed': False,
            'goal_generic': bool(generic),
        },
        'private': {
            'tactics': 'from cover' if means == 'ambush' else '',
            'intent': goal,
        },
        'observed': {
            'heard': [],
            'seen': [person['id'] for person in people if not person['hidden']],
            'find': '',
        },
    }


def _scrub_place(beat, text):
    """An open road is not called a room."""
    noun = (beat or {}).get('place_noun') or ''
    if noun and noun != 'room':
        return re.sub(r'\bthe room\b', 'the %s' % noun, text or '', flags=re.I)
    return text or ''


def look_line(beat):
    noun = (beat or {}).get('place_noun') or ''
    name = (beat or {}).get('place_name') or ''
    if noun == 'room':
        return 'You look around the room.'
    if noun in ('road', 'street', 'lane', 'trail', 'path', 'track'):
        return 'You look along the %s.' % noun
    if noun:
        return 'You look around the %s.' % noun
    if name:
        return 'You look around %s.' % name
    return 'You look around.'


def _title_for(heading, sentences):
    """A read-aloud's title: a clean place heading, else the place word, else first words."""
    if heading and not _FRONT.search(heading) and not _skim()._bad_title(heading):
        return heading
    noun = _place_in(' '.join(sentences))
    if noun:
        return 'The %s' % noun
    words = (sentences[0] if sentences else '').split()[:6]
    title = ' '.join(words).rstrip(' ,.;:')
    return title or 'Here'


def read_aloud_picks(window):
    """Picker entries are read-aloud blocks only. Front matter is not a start."""
    skim = _skim()
    picks = []
    seen = set()
    heading = ''
    page = 1
    stopped = False
    for raw in re.split(r'(\f)', window or ''):
        if raw == '\f':
            page += 1
            heading = ''
            continue
        if stopped:
            continue
        lines = raw.split('\n')
        index = 0
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                continue
            plain = stripped.lstrip('>').strip()
            if skim._LATER.match(plain) or skim._KEYED.match(plain):
                stopped = True
                break
            if skim._heading_line(plain):
                heading = '' if _FRONT.search(plain) else plain
                index += 1
                continue
            if not stripped.startswith('>'):
                index += 1
                continue
            block = []
            while index < len(lines) and lines[index].strip().startswith('>'):
                block.append(lines[index].strip().lstrip('>').strip())
                index += 1
            sentences = []
            for bit in block:
                for sentence in skim._sentences(bit):
                    if player_line(sentence):
                        sentences.append(skim.normalize(sentence))
            if not sentences:
                heading = ''
                continue
            title = _title_for(heading, sentences)
            heading = ''
            if not title or title.casefold() in seen or _FRONT.search(title):
                continue
            seen.add(title.casefold())
            picks.append({'title': title, 'page': page, 'quote': ' '.join(sentences[:2])})
            if len(picks) >= 4:
                return picks
    if picks:
        return picks
    # pdftotext -layout does not write ">". A player sentence is still a read-aloud.
    stream = _layout_stream(window or '')
    bucket = []
    skipping = False
    for line in stream.split('\n'):
        plain = line.strip().lstrip('>').strip()
        if not plain:
            continue
        if skim._LATER.match(plain) or skim._KEYED.match(plain) or re.match(
                r'^(?:appendix|contents)\b', plain, re.I):
            break
        if _FRONT.search(plain) and skim._heading_line(plain):
            skipping = True
            continue
        if skipping and skim._heading_line(plain):
            skipping = False
        if skipping:
            continue
        for sentence in skim._sentences(plain):
            if _encounter_sentence(sentence) or not player_line(sentence):
                continue
            if not re.search(r'\byou\b', sentence, re.I) and not re.search(
                    r'\b(?:Captain|Sergeant)\s+[A-Z]', sentence):
                continue
            bucket.append(skim.normalize(sentence))
    if bucket:
        title = _title_for('', bucket)
        return [{'title': title, 'page': 1, 'quote': ' '.join(bucket[:2])}]
    for line in (window or '').split('\n'):
        plain = line.strip().lstrip('>').strip()
        if not skim._heading_line(plain):
            continue
        if _FRONT.search(plain) or skim._bad_title(plain) or skim._LATER.match(plain) or skim._KEYED.match(plain):
            continue
        return [{'title': plain, 'page': 1, 'quote': '', 'kit_line': kit_line(plain)}]
    noun = _place_in(window or '')
    if noun:
        return [{'title': 'The %s' % noun, 'page': 1, 'quote': '', 'kit_line': kit_line('the %s' % noun)}]
    return [{'title': 'Here', 'page': 1, 'quote': '', 'kit_line': kit_line('here')}]


def letter_slot(alts, token):
    """A one-letter pick matches a slot on the picker. Nothing else."""
    if not re.fullmatch(r'[A-Za-z]', (token or '').strip()):
        return None
    letter = token.strip().casefold()
    for alt in alts or []:
        title = (alt.get('title') or '').strip()
        if title.casefold() == letter:
            return alt
        if re.match(r'^%s[.)](?:\s|$)' % letter, title, re.I):
            return alt
    return None


def fallback_titles(window):
    """One Kit-voiced start when no read-aloud qualified."""
    return read_aloud_picks(window)[:1]


def _load(runtime):
    skim = _skim()
    try:
        path = runtime.path
    except Exception:
        return None, None
    data = skim._read(path)
    beat = data.get('beat')
    if not isinstance(beat, dict):
        return data, None
    return data, beat


def _save(runtime, data):
    _skim()._write(runtime.path, data)


def _mark_heard(beat, sentences):
    observed = beat.setdefault('observed', {'heard': [], 'seen': [], 'find': ''})
    heard = observed.setdefault('heard', [])
    for sentence in sentences:
        if sentence and sentence not in heard:
            heard.append(sentence)
    beat['heard'] = max(int(beat.get('heard') or 0), len(heard))


def note_spoken(runtime, text):
    """Record fiction the player was just given. Private tactics are not facts."""
    data, beat = _load(runtime)
    if not beat:
        return
    skim = _skim()
    _mark_heard(beat, [line for line in skim._sentences(text or '') if player_line(line)])
    data['beat'] = beat
    _save(runtime, data)


def _commit(runtime, tag, events, spoken, public):
    revision, _state = runtime.load()
    committed = runtime.commit('%s-%s' % (tag, revision), revision, events)
    return {
        'stage': tag, 'committed': True, 'calls': 1, 'spoken': spoken,
        'public_event': public, 'revision': committed,
    }


def _plan(beat, why):
    who = 'kit'
    people = beat.get('people') or []
    if people and people[0].get('id'):
        who = people[0]['id']
    toward = (beat.get('pressure') or {}).get('goal') or 'They keep their aim.'
    return plan_event({
        'beats': [{
            'id': 'pressure', 'who': who, 'toward': toward[:160], 'when': 'later',
            'why': why[:160], 'roots': ['kit'], 'change': 'revise', 'reason': why[:120],
        }],
        'dropped': [],
    }, 'opening')


def _reveal(beat, person_ids):
    observed = beat.setdefault('observed', {'heard': [], 'seen': [], 'find': ''})
    seen = observed.setdefault('seen', [])
    for person in beat.get('people') or []:
        if person['id'] in person_ids or not person_ids:
            if person.get('hidden') and person['id'] not in person_ids and person_ids:
                continue
        if person_ids and person['id'] not in person_ids:
            continue
        person['revealed'] = True
        person['addressable'] = True
        person['hidden'] = False
        if person['id'] not in seen:
            seen.append(person['id'])


def _status_events(runtime, beat, ids):
    try:
        _revision, state = runtime.load()
    except Exception:
        return []
    events = []
    area = state.get('area')
    for key in ids:
        live = (state.get('actors') or {}).get(key) or {}
        if not live or live.get('location') != area:
            continue
        if live.get('status') == 'hidden':
            events.append({
                'type': 'actor_status', 'actor': key, 'status': 'alive',
                'evidence': 'The player has met them. This is observed, not inferred.',
            })
    return events


def _clear_check():
    return {'type': 'pending_check', 'check': None,
            'evidence': 'The notice is no longer waiting.'}


def _bypass(runtime, data, beat, why, spoken):
    """The player changed the situation. The goal stands. The fight does not start."""
    pressure = beat.setdefault('pressure', {})
    pressure['bypassed'] = True
    pressure['acted'] = False
    notice = beat.setdefault('notice', {})
    notice['pending'] = False
    notice['resolved'] = True
    _reveal(beat, [person['id'] for person in beat.get('people') or []])
    data['beat'] = beat
    _save(runtime, data)
    public = spoken
    events = [
        {'type': 'beat', 'tags': ['bypass'],
         'evidence': 'Bypass is a resolution. ' + why},
        _clear_check(),
    ]
    try:
        events.append(_plan(beat, why))
    except Exception:
        pass
    events.extend(_status_events(runtime, beat, [person['id'] for person in beat.get('people') or []]))
    return _commit(runtime, 'bypass', events, 'Kit: %s' % spoken, public)


def _answer_roll(runtime, data, beat, total):
    notice = beat.setdefault('notice', {})
    notice['pending'] = False
    notice['resolved'] = True
    pressure = beat.setdefault('pressure', {})
    people = beat.get('people') or []
    ids = [person['id'] for person in people]
    if total >= _SUCCESS_AT:
        find = notice.get('find') or ''
        if find:
            beat.setdefault('observed', {}).setdefault('find', find)
            beat['observed']['find'] = find
        _reveal(beat, ids)
        names = [person['name'] for person in people]
        bits = []
        if find:
            bits.append(find)
        if names:
            bits.append('%s %s here.' % (
                ', '.join(names), 'are' if len(names) > 1 else 'is'))
        if not bits:
            bits.append('You notice what this place was holding.')
        bits.append('What do you do?')
        spoken = ' '.join(bits)
        data['beat'] = beat
        _save(runtime, data)
        events = [
            {'type': 'beat', 'tags': ['notice', 'success'],
             'evidence': 'A successful notice. The Find and the people are now observed.'},
            _clear_check(),
        ]
        events.extend(_status_events(runtime, beat, ids))
        return _commit(runtime, 'notice', events, 'Kit: %s' % spoken, spoken)
    # Failure: the default means acts, unless the player already changed the situation.
    if pressure.get('bypassed'):
        data['beat'] = beat
        _save(runtime, data)
        spoken = 'That moment has passed. What do you do?'
        return _commit(runtime, 'notice', [_clear_check()], 'Kit: %s' % spoken, spoken)
    pressure['acted'] = True
    if pressure.get('means') == 'ambush':
        _reveal(beat, ids)
        names = [person['name'] for person in people]
        arrival = ''
        if names:
            arrival = '%s %s here. ' % (', '.join(names), 'are' if len(names) != 1 else 'is')
        spoken = _scrub_place(
            beat, 'They spring from cover. %sYou are surprised. Roll initiative. What do you do?' % arrival)
        data['beat'] = beat
        _save(runtime, data)
        events = [
            {'type': 'beat', 'tags': ['pressure', 'ambush'],
             'evidence': 'The notice failed. The default means acts: surprise, then initiative.'},
            _clear_check(),
        ]
        events.extend(_status_events(runtime, beat, ids))
        fight = _maybe_fight(runtime, total)
        fight_events = []
        if fight is not None:
            fight_events = [event for event in fight.events if event.get('type') != 'pending_check']
        try:
            return _commit(runtime, 'pressure', fight_events + events, 'Kit: %s' % spoken, spoken)
        except Exception:
            return _commit(runtime, 'pressure', events, 'Kit: %s' % spoken, spoken)
    data['beat'] = beat
    _save(runtime, data)
    spoken = 'Nothing shows itself. What do you do?'
    return _commit(runtime, 'notice', [_clear_check()], 'Kit: %s' % spoken, spoken)


def _maybe_fight(runtime, total):
    try:
        from .kit_agent import RoomAdjudicator
        adjudicator = RoomAdjudicator()
        adjudicator.mount(runtime.source())
        revision, state = runtime.load()
        return adjudicator.resolve('I look around.\nperception %s' % total, revision, state)
    except Exception:
        return None


def _ask_notice(runtime, data, beat):
    beat.setdefault('notice', {})['pending'] = True
    data['beat'] = beat
    _save(runtime, data)
    line = look_line(beat)
    spoken = '%s You might not be alone. Roll Perception.' % line
    events = [
        {'type': 'beat', 'tags': ['check_called', 'notice'],
         'evidence': 'The beat holds something to perceive. Initiative waits on the roll.'},
        {'type': 'pending_check', 'check': {
            'skill': 'perception', 'ability': 'wis', 'target': 'none',
            'called_turn': 'opening', 'action': 'I look around.',
        }, 'evidence': 'Perception, before anything shows itself. The DC stays back here.'},
    ]
    return _commit(runtime, 'notice', events, 'Kit: %s' % spoken, spoken)


def _named(beat, action):
    folded = (action or '').casefold()
    found = []
    for person in beat.get('people') or []:
        name = (person.get('name') or '').casefold()
        if name and name in folded:
            found.append(person)
    return found


def opening_turn(runtime, action):
    """Look, roll, talk, sneak, or leave, answered from the beat. None if this is not one."""
    if not action or not str(action).strip():
        return None
    data, beat = _load(runtime)
    if not beat or data.get('status') != 'accepted':
        return None
    if beat.get('source_verified'):
        # All player deeds enter the general adjudicator, never the opening's
        # old fixed notice threshold, auto-bypass, or forced-initiative path.
        return None
    try:
        runtime.load()
    except Exception:
        return None
    text = str(action)
    notice = beat.get('notice') or {}
    pressure = beat.get('pressure') or {}
    number = re.search(r'\b(\d{1,2})\b', text)
    if notice.get('pending') and number and not _LOOK.search(text):
        return _answer_roll(runtime, data, beat, int(number.group(1)))
    if pressure.get('bypassed') or pressure.get('acted'):
        if _LOOK.search(text) and not notice.get('pending'):
            line = look_line(beat) + ' What do you do?'
            return _commit(runtime, 'look', [{
                'type': 'beat', 'tags': ['observe'],
                'evidence': 'The pressure is already resolved. A look does not restart it.',
            }], 'Kit: %s' % line, line)
    if notice.get('holds') and not notice.get('resolved') and not pressure.get('bypassed'):
        if _TALK.search(text) or _named(beat, text):
            goal = pressure.get('goal') or 'They keep their aim.'
            return _bypass(
                runtime, data, beat,
                'The player spoke to them before the notice. The goal stands and the means change.',
                'You call out. %s They answer instead of springing. What do you say?' % goal)
        if _SNEAK.search(text):
            goal = pressure.get('goal') or 'They keep their aim.'
            return _bypass(
                runtime, data, beat,
                'The player slipped past. The goal stands. The ambush does not spring.',
                'You slip past. %s They do not spring. What do you do?' % goal)
        if _LEAVE.search(text):
            goal = pressure.get('goal') or 'They keep their aim.'
            where = beat.get('place_noun') or 'place'
            return _bypass(
                runtime, data, beat,
                'The player left the beat. That is a resolution. The fight is not dragged forward.',
                'You leave the %s. %s The beat is behind you.' % (where, goal))
        if _LOOK.search(text):
            return _ask_notice(runtime, data, beat)
    elif not pressure.get('bypassed') and not pressure.get('acted'):
        # Visible people are already on stage. Look, sneak, and leave still use the beat.
        goal = pressure.get('goal') or 'They keep their aim.'
        where = beat.get('place_noun') or 'place'
        if _SNEAK.search(text):
            return _bypass(
                runtime, data, beat,
                'The player slipped past. The goal stands. The means change.',
                'You slip past. %s They do not spring. What do you do?' % goal)
        if _LEAVE.search(text):
            return _bypass(
                runtime, data, beat,
                'The player left the beat. That is a resolution. The fight is not dragged forward.',
                'You leave the %s. %s The beat is behind you.' % (where, goal))
        if _LOOK.search(text):
            line = '%s What do you do?' % look_line(beat)
            return _commit(runtime, 'look', [{
                'type': 'beat', 'tags': ['observe'],
                'evidence': 'A look at a beat whose people are already on stage. No notice roll is owed.',
            }], 'Kit: %s' % line, line)
    if _TALK.search(text):
        named = _named(beat, text)
        if not named:
            named = [person for person in beat.get('people') or [] if person.get('addressable')][:1]
        if named:
            person = named[0]
            if not person.get('addressable') and not person.get('revealed'):
                return None
            goal = person.get('goal') or pressure.get('goal') or 'They are here.'
            spoken = 'You speak to %s. %s What do you say?' % (person['name'], goal)
            return _commit(runtime, 'talk', [{
                'type': 'beat', 'tags': ['talk'],
                'evidence': 'Talk to someone the beat has already shown. No scope floor.',
            }], 'Kit: %s' % spoken, spoken)
    return None


def _overlap(sentence, other):
    skim = _skim()
    words = skim._words(sentence)
    have = skim._words(other)
    if len(words) < 6 or len(have) < 6:
        return False
    span = 6
    return any(words[i:i + span] == have[j:j + span]
               for i in range(len(words) - span + 1)
               for j in range(len(have) - span + 1))


def guard_spoken(beat, text):
    """Correct a host line that speaks the screen, jumps the notice, or names the unrevealed.

    Observed facts may stay. Kit's private tactics may not be said as if the player knew them.
    """
    if not beat or not text:
        return text
    skim = _skim()
    notice = beat.get('notice') or {}
    pressure = beat.get('pressure') or {}
    pending = bool(notice.get('pending') and not notice.get('resolved') and not pressure.get('bypassed'))
    seen = {item.casefold() for item in (beat.get('observed') or {}).get('seen') or []}
    hidden_names = []
    for person in beat.get('people') or []:
        if person.get('id', '').casefold() in seen or person.get('revealed'):
            continue
        if person.get('name'):
            hidden_names.append(person['name'])
    private = ' '.join(
        part for part in ((beat.get('private') or {}).get('tactics'),) if part)
    kept = []
    for sentence in skim._sentences(text) or [text]:
        if any(_overlap(sentence, screen) for screen in beat.get('screen') or []):
            continue
        if private and private.casefold() in sentence.casefold() and private.casefold() not in (
                (beat.get('observed') or {}).get('find') or '').casefold():
            continue
        if pending and _INITIATIVE.search(sentence):
            continue
        if pending and any(re.search(r'\b%s\b' % re.escape(name), sentence, re.I) for name in hidden_names):
            continue
        kept.append(sentence)
    cleaned = ' '.join(kept).strip()
    noun = beat.get('place_noun') or ''
    if noun and noun != 'room':
        cleaned = re.sub(r'\bthe room\b', 'the %s' % noun, cleaned, flags=re.I)
    if pending and _INITIATIVE.search(text or '') and 'perception' not in cleaned.casefold():
        cleaned = (cleaned + ' Roll Perception.').strip()
    if not cleaned:
        cleaned = "That's as far as the page goes. What do you do?"
    return cleaned


def guard_runtime(runtime, text):
    _data, beat = _load(runtime)
    return guard_spoken(beat, text)
