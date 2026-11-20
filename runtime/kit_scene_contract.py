"""A bounded, source-attested interpretation of an adventure opening.

The chat host interprets people, place, goals, and candidate pressure from the
opening's read-aloud plus its adjacent encounter text. Python verifies the
*evidence* and permitted shape, not the host's literary judgment. It does not
invent creatures, set DCs, reveal secrets, or decide what the player succeeds at.

Inferred motives and prospective pressure remain private, nonbinding readings.
The authoritative state and action results belong to the existing Kit engine.
"""
import json
import re
import unicodedata

MAX_BYTES = 10000
MAX_PEOPLE = 16
MAX_DISCOVERIES = 8
MAX_PRESSURES = 8
STATUSES = ('established', 'conditional', 'inferred', 'unsupported')
KINDS = ('person', 'creature')
PRESSURE_KINDS = ('ambush', 'conversation', 'hazard', 'none')
ACTIVATIONS = ('entry', 'disturb', 'deferred', 'failed_notice')
_ID = re.compile(r'^[a-z][a-z0-9_]{0,30}$')


def _norm(text):
    if not isinstance(text, str):
        return ''
    text = unicodedata.normalize('NFKC', text)
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'),
                 ("\u201d", '"'), ("\u00ad", ''), ('>', ' ')):
        text = text.replace(a, b)
    return ' '.join(text.casefold().split())


def _valid_quote(quote, sources):
    """Require a contiguous quotation, allowing typography and whitespace only.

    This is deliberately NOT the opening picker's fuzzy column-order matcher.
    A few words from different unrelated sentences are not a source quotation.
    """
    needle = _norm(quote)
    return bool(needle) and len(needle) <= 1000 and any(needle in _norm(src) for src in sources)


def _whole_sentence(quote, sources):
    """Do not strip 'if', 'unless', or any other governing clause.

    Source facts must quote a complete sentence rather than a conveniently
    selected substring. Speaker names and area words have separate rules.
    """
    proposed = _norm(quote).strip(' .!?')
    if not proposed:
        return False
    for source in sources:
        # Print layout has independent headings and boxed paragraphs. Preserve
        # source line boundaries before normalizing whitespace; otherwise a
        # location header can be glued to the following complete sentence.
        for line in source.splitlines():
            for sentence in re.split(r'(?<=[.!?])\s+', _norm(line)):
                if proposed == sentence.strip(' .!?'):
                    return True
        # Wrapped sentences may span multiple lines. If a source sentence is
        # intact after joining, accept it only when it starts at a real sentence
        # boundary, not midway through a governing conditional clause.
        for sentence in re.split(r'(?<=[.!?])\s+', _norm(source)):
            if proposed == sentence.strip(' .!?'):
                return True
    return False


def _evidence(item, label, sources, allowed, problems):
    if not isinstance(item, dict) or set(item) != set(allowed):
        problems.append('%s has invalid fields' % label)
        return False
    if not _valid_quote(item.get('quote'), sources):
        problems.append('%s quote is not contiguous within this opening' % label)
        return False
    if item.get('status') not in STATUSES:
        problems.append('%s has invalid evidence status' % label)
        return False
    if item.get('status') in ('established', 'conditional') and not _whole_sentence(item['quote'], sources):
        problems.append('%s must quote the entire source sentence, including its conditions' % label)
        return False
    return True


def validate(scene, raw_span, read_aloud, layout_span=None):
    """Return all defects, never a partially accepted authoritative scene."""
    problems = []
    if not isinstance(scene, dict) or set(scene) != {
            'place', 'people', 'discoveries', 'pressures'}:
        return ['scene must have place, people, discoveries and pressures only']
    try:
        if len(json.dumps(scene, ensure_ascii=False).encode('utf-8')) > MAX_BYTES:
            problems.append('scene exceeds the size limit')
    except (TypeError, ValueError):
        return ['scene must be JSON-serializable']
    extras = []
    if isinstance(layout_span, (list, tuple)):
        extras = [item for item in layout_span if item]
    elif layout_span:
        extras = [layout_span]
    sources = (raw_span,) + tuple(extras)
    place = scene['place']
    if not isinstance(place, dict) or set(place) != {'name', 'quote'}:
        problems.append('place needs name and source quote')
    else:
        if not isinstance(place['name'], str) or not place['name'].strip() or len(place['name']) > 80:
            problems.append('place name must be short and nonempty')
        if not _valid_quote(place['quote'], (read_aloud,)):
            problems.append('place must quote the player-visible opening')
        if place.get('name') and not re.search(r'\b' + re.escape(_norm(place['name'])) + r'\b',
                                                _norm(place.get('quote'))):
            problems.append('place name is not in its quoted player-visible words')
    people = scene['people']
    if not isinstance(people, list) or len(people) > MAX_PEOPLE:
        problems.append('people must be a bounded list')
        people = []
    known = set()
    for i, person in enumerate(people):
        label = 'people[%d]' % i
        fields = {'id', 'name', 'quote', 'visibility', 'kind', 'goal', 'knowledge'}
        if not isinstance(person, dict) or set(person) != fields:
            problems.append('%s has invalid fields' % label)
            continue
        identity = person.get('id')
        if not isinstance(identity, str) or not _ID.fullmatch(identity) or identity in known:
            problems.append('%s id must be a unique short lowercase identifier' % label)
        else:
            known.add(identity)
        name = person.get('name')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            problems.append('%s has invalid name' % label)
        if not _valid_quote(person['quote'], sources):
            problems.append('%s presence quote is outside the bounded encounter' % label)
        if not name or not re.search(r'\b' + re.escape(_norm(name)) + r'\b', _norm(person['quote'])):
            problems.append('%s name is absent from its source quote' % label)
        if person.get('visibility') not in ('visible', 'hidden', 'staged'):
            problems.append('%s visibility is invalid' % label)
        else:
            in_read_aloud = bool(name and re.search(
                r'\b' + re.escape(_norm(name)) + r'\b', _norm(read_aloud)))
            if person['visibility'] == 'visible' and not in_read_aloud:
                problems.append('%s claims player visibility absent from the read-aloud' % label)
            if person['visibility'] == 'hidden' and in_read_aloud:
                problems.append('%s hides a character the player-facing text already names' % label)
            if person['visibility'] == 'staged':
                # A person first introduced by Go on is not on stage when the
                # opening burst is spoken. Only explicit later read-aloud text
                # can certify this staging, not a DM-only narrative sentence.
                marked = any(line.strip().startswith('>') and re.search(
                    r'\b' + re.escape(_norm(name or '')) + r'\b', _norm(line))
                    for line in raw_span.splitlines())
                if in_read_aloud or not marked:
                    problems.append('%s staged actor needs later marked player read-aloud' % label)
        if person.get('kind') not in KINDS:
            problems.append('%s kind is invalid' % label)
        goal = person.get('goal')
        if goal is not None:
            _evidence(goal, label + '.goal', sources, ('quote', 'status'), problems)
            if isinstance(goal, dict) and goal.get('status') == 'unsupported':
                problems.append('%s unsupported goal cannot become a scene fact' % label)
        knowledge = person.get('knowledge')
        if not isinstance(knowledge, list) or len(knowledge) > 8:
            problems.append('%s knowledge is not a bounded list' % label)
        else:
            for j, item in enumerate(knowledge):
                _evidence(item, '%s.knowledge[%d]' % (label, j), sources,
                          ('quote', 'status'), problems)
    discoveries = scene['discoveries']
    if not isinstance(discoveries, list) or len(discoveries) > MAX_DISCOVERIES:
        problems.append('discoveries must be a bounded list')
        discoveries = []
    for i, discovery in enumerate(discoveries):
        _evidence(discovery, 'discoveries[%d]' % i, sources, ('quote', 'status'), problems)
        if isinstance(discovery, dict) and discovery.get('status') == 'unsupported':
            problems.append('unsupported discovery cannot be inserted')
    pressures = scene['pressures']
    if not isinstance(pressures, list) or len(pressures) > MAX_PRESSURES:
        problems.append('pressures must be a bounded list')
        pressures = []
    for i, pressure in enumerate(pressures):
        label = 'pressures[%d]' % i
        if not isinstance(pressure, dict) or set(pressure) != {'kind', 'quote', 'status', 'actors', 'activation'}:
            problems.append('%s has invalid fields' % label)
            continue
        if pressure.get('kind') not in PRESSURE_KINDS:
            problems.append('%s kind is invalid' % label)
        if pressure.get('activation') not in ACTIVATIONS:
            problems.append('%s activation is invalid' % label)
        elif pressure['activation'] == 'entry' and pressure.get('status') not in ('established', 'conditional'):
            problems.append('%s entry trigger requires explicit source support' % label)
        if pressure.get('activation') == 'failed_notice':
            # In particular, the presence of a hidden enemy is not proof that
            # they attack after a missed check. That consequence needs an
            # explicit conditional statement from the book, not a guess.
            condition = _norm(pressure.get('quote'))
            if pressure.get('kind') != 'ambush' or pressure.get('status') not in ('conditional', 'established'):
                problems.append('%s failed notice requires a source-attested ambush' % label)
            if not re.search(r'\b(?:if|unless|when|should|upon)\b', condition) or not re.search(
                    r'\b(?:unnoticed|undetected|unseen|unaware|fail|fails|failed|miss|misses|missed|'
                    r'notice|noticed|detect|detected|spot|spotted|see|sees|saw)\b', condition):
                problems.append('%s failed notice needs the full conditional source sentence' % label)
        if pressure.get('status') not in STATUSES or pressure.get('status') == 'unsupported':
            problems.append('%s status is invalid or unsupported' % label)
        if not _valid_quote(pressure.get('quote'), sources):
            problems.append('%s quote is outside the bounded encounter' % label)
        elif pressure.get('status') in ('established', 'conditional') and not _whole_sentence(pressure['quote'], sources):
            problems.append('%s must preserve the whole source condition' % label)
        actors = pressure.get('actors')
        if not isinstance(actors, list) or not actors or not all(a in known for a in actors):
            problems.append('%s actors must name people in this scene' % label)
    return problems


def build_beat(scene, burst, place_heading, fiction=None):
    """Convert validated host analysis to an evidence-rooted, nonadjudicating brief."""
    from . import kit_skim
    people = []
    for person in scene['people']:
        hidden = person['visibility'] != 'visible'
        staged = person['visibility'] == 'staged'
        goal = person.get('goal') or {}
        # A conditional or inferred motive is not a new authoritative world fact.
        accepted_goal = goal.get('quote', '') if goal.get('status') == 'established' else ''
        quote = ''
        raw_quote = person.get('quote')
        if isinstance(raw_quote, dict):
            quote = (raw_quote.get('quote') or '').strip()
        elif raw_quote:
            quote = str(raw_quote).strip()
        people.append({
            'id': person['id'], 'name': person['name'], 'hidden': hidden,
            'kind': 'creature' if person['kind'] == 'creature' else 'speaker',
            'revealed': not hidden, 'addressable': not hidden, 'staged': staged,
            'quote': quote, 'visible_state': quote,
            'goal': accepted_goal, 'motive': accepted_goal,
            'knowledge_evidence': person['knowledge'],
        })
    goals = [p.get('goal') for p in people if p.get('goal')]
    ambush = any(p['kind'] == 'ambush' and p['status'] != 'unsupported'
                 for p in scene['pressures'])
    return {
        'source_verified': True,
        'fiction': list(fiction) if fiction is not None else [
            sentence for sentence in kit_skim._sentences(burst) if sentence],
        'heard': 0,
        'place_noun': scene['place']['name'], 'place_name': place_heading,
        'screen': [],
        'notice': {'holds': bool(ambush) or bool(scene.get('discoveries')),
                   'pending': False, 'resolved': False,
                   'find': ((scene.get('discoveries') or [{}])[0].get('quote')
                            if scene.get('discoveries') and isinstance(scene['discoveries'][0], dict)
                            else '')},
        'people': people,
        'pressure': {'goal': goals[0] if goals else '',
                     'means': 'ambush' if ambush else 'none',
                     'acted': False, 'bypassed': False,
                     'goal_generic': not bool(goals)},
        'private': {'tactics': '', 'intent': goals[0] if goals else '',
                    'unverified_hypotheses': [p for p in scene['pressures']
                                              if p['status'] in ('inferred', 'conditional')]},
        'observed': {'heard': [], 'seen': [p['id'] for p in people if not p['hidden']],
                     'find': ''},
        'discoveries': scene['discoveries'],
        'source_contract': scene,
    }
