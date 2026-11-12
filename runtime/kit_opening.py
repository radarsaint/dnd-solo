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
    if _SCREENISH.search(text or ''):
        return False
    return skim._scene_line(text)


def place_noun(name, fiction):
    """What the place is, from the book's own words. Room only when it says room."""
    blob = '%s %s' % (name or '', fiction or '')
    for noun in _PLACE:
        if re.search(r'\b%s\b' % noun, blob, re.I):
            return noun
    return ''


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


def _goal(means, noun):
    where = noun or 'place'
    if means == 'ambush':
        return 'They want whoever comes along this %s.' % where
    if means == 'meet':
        return 'They want to meet whoever is here.'
    return ''


def _people(text, fiction):
    from .kit_adventure import _GREET, _creatures, _introduced_names, _sentence_around, _slug
    from .srd_creatures import CREATURES
    skim = _skim()
    heard = ' '.join(fiction).casefold()
    people = []
    seen = set()

    def add(key, name, hidden, kind):
        if not key or key in seen:
            return
        seen.add(key)
        people.append({
            'id': key, 'name': name, 'hidden': bool(hidden), 'kind': kind,
            'revealed': not hidden, 'addressable': not hidden,
        })

    for name in _introduced_names(text or ''):
        add(_slug(name), name, name.casefold() not in heard, 'speaker')
    if skim._CHILD.search(text or '') or skim._CHILD.search(heard):
        add('children', 'Children', not bool(skim._CHILD.search(heard)), 'speaker')
    if _GREET.search(heard) and 'greeter' not in seen:
        add('greeter', 'Greeter', False, 'speaker')
    for creature in _creatures(text or '', 0, {}):
        name = creature.get('name') or ''
        key = _slug(name)
        if name.casefold() not in CREATURES:
            continue
        sent = ''
        try:
            sent = _sentence_around(text or '', creature.get('mention_offset') or 0)
        except Exception:
            sent = ''
        if skim._WARNING.search(sent) and not skim._ARRIVAL.search(sent):
            continue
        if sent and not skim._ARRIVAL.search(sent) and not skim._NOTICE.search(sent):
            continue
        add(key, name.title(), name.casefold() not in heard, 'creature')
    return people


def fiction_lines(page_text, burst):
    """Ordered player lines. A screen sentence ends the list."""
    skim = _skim()
    lines = []

    def take(sentence):
        sentence = skim.normalize(sentence)
        if not sentence or sentence in lines:
            return
        if not player_line(sentence):
            return
        lines.append(sentence)

    for sentence in skim._sentences(burst or ''):
        take(sentence)
    for bit in skim._boxed_lines(page_text or ''):
        for sentence in skim._sentences(bit):
            if skim._go_fail(sentence) or skim._blocks_quote(sentence) or _SCREENISH.search(sentence):
                return lines
            take(sentence)
    return lines


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
    """The one record for this opening. Observed facts start empty of inferences."""
    fiction = fiction_lines(page_text, burst)
    noun = place_noun(place_name, ' '.join(fiction))
    people = _people(page_text, fiction)
    means = 'ambush' if any(person['kind'] == 'creature' and person['hidden'] for person in people) else (
        'meet' if people else 'none')
    goal = _goal(means, noun)
    find = ''
    for sentence in screen_lines(page_text, fiction) + [page_text or '']:
        find = _find_clause(sentence)
        if find:
            break
    holds = bool(means == 'ambush' or find or any(person['hidden'] for person in people)
                 or _skim()._NOTICE.search(page_text or ''))
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
        'pressure': {'goal': goal, 'means': means, 'acted': False, 'bypassed': False},
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


def fallback_titles(window):
    """A place name from the window, in Kit's voice, when no boxed fiction qualified."""
    skim = _skim()
    for line in (window or '').split('\n'):
        stripped = line.strip().lstrip('>').strip()
        if not skim._heading_line(stripped):
            continue
        if skim._bad_title(stripped) or skim._after_keyed(window, stripped) or skim._LATER.match(stripped):
            continue
        return [{'title': stripped, 'page': 1, 'quote': '', 'kit_line': kit_line(stripped)}]
    return [{'title': 'Here', 'page': 1, 'quote': '', 'kit_line': kit_line('here')}]


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
        spoken = 'They spring from cover. You are surprised. Roll initiative.'
        data['beat'] = beat
        _save(runtime, data)
        events = [
            {'type': 'beat', 'tags': ['pressure', 'ambush'],
             'evidence': 'The notice failed. The default means acts: surprise, then initiative.'},
            _clear_check(),
        ]
        events.extend(_status_events(runtime, beat, ids))
        fight = _maybe_fight(runtime, total)
        if fight is not None:
            events = [event for event in fight.events
                      if event.get('type') != 'pending_check'] + events
            if 'initiative' in (fight.public_event or '').lower():
                spoken = 'You are surprised. %s' % fight.public_event
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
