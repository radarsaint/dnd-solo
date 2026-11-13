"""Facts the host needs to write Look and NPC lines, and checks on what it wrote.

Python does not recast book sentences into speech or glue fiction
fragments into a description. The packet hands the host source-quoted
facts; the host writes in its own words. Python only checks that
claimed book facts are attested, that no DC or bonus shows, that
instruction vocabulary is absent, and that the speaker is present.
"""
import re

from . import kit_opening

# Kit's private staging vocabulary. An NPC must not say these.
_INSTRUCTION = re.compile(
    r"(?i)\b(?:this beat|the beat|off-?stage|off the page|off-?page|"
    r"invent(?:s|ed|ing)?|on this beat|this beat's stage|"
    r"the packet|the host|hand ?off|behind the screen|"
    r"source span|scene form|do not invent)\b"
)

_DC_OR_BONUS = re.compile(
    r"(?i)\bDC\s*\d+\b|\bdifficulty class\b|\b[+-]\s*\d+\s*"
    r"(?:bonus|penalty|to hit|to the (?:roll|check|save))\b"
)

_HOWTO = kit_opening._FRONT

# Words that may appear capitalized without being a book name.
_COMMON_NAMES = frozenset("""
    i you your yours we they them their the a an and or but if so then
    now here there this that these those what who whom whose which when
    where why how kit narrator dm dungeon master captain sergeant sir
    madam miss mister lady lord yes no well just still all any some
    none one two three four five six he she it his her its our
""".split())


def instruction_vocab(text):
    """True when the line uses Kit's instruction language."""
    return bool(_INSTRUCTION.search(text or ''))


def shows_dc_or_bonus(text):
    """True when a DC or a numeric bonus/penalty is spoken."""
    return bool(_DC_OR_BONUS.search(text or ''))


def _norm(text):
    return re.sub(r'[^a-z0-9]+', ' ', (text or '').casefold()).strip()


def _plain(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


# A want, duty, order, or purpose — not a description of what someone is doing.
_GOAL_MARK = re.compile(
    r"(?i)\b(?:orders?|ordered|commanded|instructed|"
    r"tasked with|charged with|charge is|duty is|mission is|"
    r"wants?|wanted|wishes?|intends?|intended|"
    r"means to|meant to|purpose is|aim is|aims to|"
    r"has been told|have been told|"
    r"must (?:hold|keep|guard|wait|stay|protect|stop|cover|watch)|"
    r"is to (?:hold|keep|guard|wait|stay|protect|cover|watch))\b"
)

# Observed bodily or spoken action: a stage direction, not a goal.
_STAGE_ACTION = re.compile(
    r"(?i)\b(?:glances?|glanced|nods?|nodded|stands?|stood|"
    r"hails?|hailed|leans?|leaned|smiles?|smiled|"
    r"turns?|turned|waves?|waved|gestures?|gestured|"
    r"points?|pointed|peers?|peered|paces?|paced|"
    r"steps?|stepped|sits?|sat|kneels?|knelt|"
    r"looks? (?:at|toward|towards|around|down|up|over)|"
    r"watches?|watched|calls? out|called out|"
    r"raises? (?:a |an |the |her |his |their )|"
    r"asks?|asked|says?|said|tells?|told)\b"
)

# How-to-play and DM-tip voice. These are not section facts.
_HOWTO_TIP = re.compile(
    r"(?i)\b(?:dm tip|dungeon master tip|tip for the dm|for the dm|"
    r"how to play|how-to-play|fun of playing|spoiled for you|"
    r"for instance|for example|"
    r"this reflects|this is the number|"
    r"your character can|character sheets?|"
    r"rolls? to use skills?|ability scores?|"
    r"communicating with monsters|"
    r"can you (?:hit|balance|convince|sneak|hide|climb|jump|cast|roll))\b"
    r"|^\s*can you\b"
)

# In-world character background the section establishes (where they are from).
_CHARACTER_BACKGROUND = re.compile(
    r"(?i)\b(?:you are from|you're from|you come from|you came from|"
    r"you were born|you grew up|you live in|you hail from|"
    r"your home (?:is|was|village|town|city)|"
    r"today,? it(?:'|’)s your turn)\b"
)


def is_attested_goal(text):
    """True when the quote states a want, duty, order, or purpose."""
    return bool(text and _GOAL_MARK.search(text))


def is_visible_action(text):
    """True when the quote describes an observed action, not a purpose."""
    if not text or is_attested_goal(text):
        return False
    return bool(_STAGE_ACTION.search(text))


def is_howto_or_tip(text):
    """True when the line is how-to-play or a DM tip, not playable fiction."""
    return bool(text and _HOWTO_TIP.search(text))


def is_character_background(text):
    """True when the line establishes where the characters are from, or similar."""
    return bool(text and _CHARACTER_BACKGROUND.search(text) and not is_howto_or_tip(text))


def _goal_text(person):
    goal = (person or {}).get('goal') or (person or {}).get('motive') or ''
    if isinstance(goal, dict):
        if goal.get('status') and goal.get('status') != 'established':
            return ''
        goal = goal.get('quote') or ''
    goal = _plain(goal)
    if goal.casefold() in (
            'answer whoever speaks to them here.',
            'they are in this scene.',
            'they are here.',
            'they keep their aim.',
    ):
        return ''
    return goal


def _knowledge_quotes(person):
    found = []
    for item in (person or {}).get('knowledge') or (person or {}).get('knowledge_evidence') or []:
        quote = item.get('quote') if isinstance(item, dict) else item
        status = item.get('status') if isinstance(item, dict) else 'established'
        if status and status != 'established':
            continue
        if quote and _plain(quote):
            found.append(_plain(quote))
    return found


def _visible_state(person):
    for key in ('quote', 'visible', 'visible_state', 'appearance'):
        value = (person or {}).get(key)
        if isinstance(value, dict):
            value = value.get('quote') or ''
        if _plain(value):
            return _plain(value)
    return ''


def _person_ready(person, kind):
    """Whether this person belongs on a fact packet for this kind of turn."""
    if not person or not person.get('name'):
        return False
    hidden = bool(person.get('hidden') and not person.get('revealed'))
    if kind == 'look' and hidden:
        return False
    if hidden and not person.get('addressable') and not person.get('revealed'):
        return False
    return True


def link_notes_for(index, person):
    """Link-web notes whose subject is this person."""
    from . import kit_links
    name = (person or {}).get('name') or ''
    if not name:
        return []
    notes = []
    if not index:
        return notes
    key = kit_links.section_key(index, index.get('start'))
    for link in kit_links.links_from(index, key):
        subject = (link.get('subject') or '').strip()
        kind = link.get('kind') or ''
        if not subject:
            continue
        if subject.casefold() == name.casefold() or name.casefold() in subject.casefold():
            if kind in ('npc', 'name', 'npc_note', 'pointer') or link.get('quote'):
                if link.get('quote'):
                    notes.append(_plain(link.get('quote')))
    return notes


def _is_section_fact(line, boxed=False):
    """Playable fiction or a character-background line, never a how-to or DM tip.

    Uses the same gates the picker uses (player_line, and _safe_box for unboxed
    lines), plus an explicit keep for section-established background.
    """
    from . import kit_skim
    line = _plain(line)
    if not line or len(line.split()) < 4:
        return False
    if is_howto_or_tip(line) or _HOWTO.search(line):
        return False
    if kit_skim._blocks_quote(line) or kit_skim._unsafe(line):
        return False
    if is_character_background(line):
        return True
    if not kit_opening.player_line(line):
        return False
    if boxed:
        return True
    return bool(kit_skim._safe_box(line))


def _section_player_quotes(db, scene_key=None, cap=80):
    """Playable fiction and player-facing facts from the current section.

    How-to-play and DM-tip fragments are dropped. Character-background
    lines the section establishes (where the characters are from) are kept,
    so a question about the home place can be answered from the packet.
    """
    from .kit_adventure import _load
    from . import kit_links, kit_skim
    quotes = []
    try:
        index, book = _load(db)
    except Exception:
        return quotes
    key = kit_links.section_key(index, scene_key or index.get('start'))
    loc = (index.get('locations') or {}).get(key) or {}
    span = kit_links._recorded_span(loc, len(book or ''))
    boxed = []
    try:
        boxed = [ _plain(line) for line in kit_opening._boxed_lines(loc, book) if _plain(line)]
    except Exception:
        boxed = []
    boxed_set = set(boxed)

    def add(sentence, from_box=False):
        line = _plain(sentence)
        if not line or line in quotes:
            return
        if not _is_section_fact(line, boxed=from_box or line in boxed_set):
            return
        quotes.append(line)

    for line in boxed:
        add(line, from_box=True)
    if span:
        body = book[span[0]:span[1]]
        for sentence in kit_skim._sentences(body) or []:
            add(sentence, from_box=False)
            if len(quotes) >= cap:
                break
    return quotes[:cap]


def _heard_quotes(beat, burst=None):
    """What the player has already heard, plus visible fiction already marked heard."""
    from . import kit_skim
    seen = []

    def add(sentence):
        text = _plain(sentence)
        if not text:
            return
        if _HOWTO.search(text) or not kit_opening.player_line(text):
            return
        if text not in seen:
            seen.append(text)

    observed = (beat or {}).get('observed') or {}
    for item in observed.get('heard') or []:
        add(item)
    heard_n = int((beat or {}).get('heard') or 0)
    fiction = list((beat or {}).get('fiction') or [])
    if heard_n and fiction:
        for item in fiction[:heard_n]:
            add(item)
    if not seen and burst:
        for item in kit_skim._sentences(burst) or [burst]:
            add(item)
    if not seen:
        for item in fiction:
            add(item)
    hidden_names = [person.get('name') for person in (beat or {}).get('people') or []
                    if person.get('name') and person.get('hidden') and not person.get('revealed')]
    if hidden_names:
        kept = []
        for sentence in seen:
            if any(re.search(r'\b%s\b' % re.escape(name), sentence, re.I) for name in hidden_names):
                continue
            kept.append(sentence)
        return kept
    return seen


def _person_facts(person, index=None):
    goal = _goal_text(person)
    knowledge = _knowledge_quotes(person)
    visible = _visible_state(person)
    action = _plain((person or {}).get('action') or '')
    # A stage direction or description must never sit in goal.
    if goal and not is_attested_goal(goal):
        if not visible:
            visible = goal
        if is_visible_action(goal) and not action:
            action = goal
        goal = ''
    if not action and is_visible_action(visible):
        action = visible
    notes = link_notes_for(index, person) if index is not None else []
    return {
        'id': person.get('id') or '',
        'name': person.get('name') or '',
        'goal': goal,
        'knowledge': knowledge,
        'visible_state': visible,
        'action': action,
        'addressable': bool(person.get('addressable') or person.get('revealed')
                            or not person.get('hidden')),
        'link_notes': notes,
    }


def host_facts_for(runtime, action=None, kind=None, hop=None):
    """The fact packet for a Look, an NPC reply, or a section-backed lookup."""
    data, beat = kit_opening._load(runtime)
    if not beat:
        return None
    text = str(action or '')
    if kind is None:
        kind = infer_kind(beat, text)
    if not kind:
        return None
    burst = (data or {}).get('burst') or ''
    visible = _heard_quotes(beat, burst)
    index = None
    try:
        from .kit_adventure import _load
        index, _text = _load(runtime.path)
    except Exception:
        index = None
    people = []
    for person in beat.get('people') or []:
        if not _person_ready(person, kind):
            continue
        people.append(_person_facts(person, index))
    notes = []
    for person in people:
        for note in person.get('link_notes') or []:
            if note not in notes:
                notes.append(note)
    packet = {
        'kind': kind,
        'visible': visible,
        'people': people,
        'link_notes': notes,
    }
    if kind == 'lookup':
        scene_key = (data or {}).get('scene_key') or (data or {}).get('design_start_name')
        section = _section_player_quotes(runtime.path, scene_key)
        packet['section'] = section
        if hop:
            packet['hop'] = {
                'kind': (hop.get('link') or {}).get('kind') if isinstance(hop.get('link'), dict)
                else hop.get('kind'),
                'span_chars': hop.get('span_chars'),
                'spoken': hop.get('spoken') or '',
            }
    return packet


def infer_kind(beat, action):
    text = str(action or '')
    if not text.strip():
        return None
    from . import kit_skim
    if kit_skim._LOOKUP.search(text):
        return 'lookup'
    talking = bool(kit_opening._TALK.search(text) or kit_opening._named(beat, text))
    if talking:
        return 'npc_reply'
    if kit_opening._LOOK.search(text):
        return 'look'
    return None


def attested_corpus(facts, beat=None, action=None):
    """All source-quoted text the host may draw a book fact from."""
    parts = []
    if action:
        parts.append(str(action))
    facts = facts or {}
    for key in ('visible', 'section', 'link_notes'):
        for item in facts.get(key) or []:
            parts.append(item)
    for person in facts.get('people') or []:
        for key in ('goal', 'visible_state', 'action'):
            if person.get(key):
                parts.append(person[key])
        for item in (person.get('knowledge') or []) + (person.get('link_notes') or []):
            parts.append(item)
        if person.get('name'):
            parts.append(person['name'])
    hop = facts.get('hop') or {}
    if hop.get('spoken'):
        parts.append(hop['spoken'])
    if beat:
        place = beat.get('place') or {}
        if isinstance(place, dict) and place.get('name'):
            parts.append(place.get('name'))
        elif isinstance(place, str):
            parts.append(place)
        if beat.get('place_noun'):
            parts.append(beat.get('place_noun'))
        for person in beat.get('people') or []:
            if person.get('name'):
                parts.append(person['name'])
    return ' '.join(_plain(part) for part in parts if _plain(part))


def hidden_names(beat):
    names = []
    for person in (beat or {}).get('people') or []:
        if person.get('name') and person.get('hidden') and not person.get('revealed'):
            names.append(person['name'])
    return names


def present_speakers(beat, facts=None):
    names = set()
    for person in (facts or {}).get('people') or []:
        if person.get('addressable') and person.get('name'):
            names.add(person['name'].casefold())
            if person.get('id'):
                names.add(person['id'].casefold())
    for person in (beat or {}).get('people') or []:
        if not person.get('name'):
            continue
        if person.get('addressable') or person.get('revealed') or not person.get('hidden'):
            names.add(person['name'].casefold())
            if person.get('id'):
                names.add(person['id'].casefold())
    return names


def _proper_names(text):
    """Capitalized names in speech, skipping ordinary sentence starts."""
    found = []
    for raw in re.split(r'[.!?]+', text or ''):
        words = re.findall(r"[A-Za-z][A-Za-z']*", raw)
        i = 0
        while i < len(words):
            word = words[i]
            # Skip the first word of a sentence unless it continues a multi-word name.
            if i == 0 and (i + 1 >= len(words) or not words[i + 1][:1].isupper()):
                i += 1
                continue
            if not word[:1].isupper():
                i += 1
                continue
            if word.casefold() in _COMMON_NAMES:
                i += 1
                continue
            run = [word]
            j = i + 1
            while j < len(words) and words[j][:1].isupper() and words[j].casefold() not in _COMMON_NAMES:
                run.append(words[j])
                j += 1
            found.append(' '.join(run))
            i = j
    return found


def performance_problems(performance, facts, beat=None, action=None):
    """Reasons the host's Look or NPC line must not be committed. Empty means clean."""
    if not isinstance(performance, dict):
        return ['performance is missing']
    segments = list(performance.get('segments') or [])
    problems = []
    corpus = attested_corpus(facts, beat=beat, action=action).casefold()
    allowed = present_speakers(beat, facts)
    hidden = hidden_names(beat)
    kind = (facts or {}).get('kind')
    for segment in segments:
        speaker = (segment.get('speaker') or '').strip()
        text = segment.get('text') or ''
        if instruction_vocab(text):
            problems.append('instruction vocabulary in %s' % (speaker or 'a line'))
        if shows_dc_or_bonus(text):
            problems.append('a DC or bonus was spoken')
        if speaker and speaker not in ('Narrator', 'Kit'):
            key = speaker.casefold()
            if allowed and key not in allowed and not any(
                    key in name or name in key for name in allowed):
                problems.append('%s is not present' % speaker)
        if kind == 'look' or speaker == 'Narrator':
            for name in hidden:
                if re.search(r'\b%s\b' % re.escape(name), text, re.I):
                    problems.append('an unrevealed person was named')
                    break
        for name in _proper_names(text):
            if name.casefold() in _COMMON_NAMES:
                continue
            if name.casefold() in corpus or all(
                    part.casefold() in corpus for part in name.split()):
                continue
            # A name the player just used is not an invented book fact.
            if action and name.casefold() in (action or '').casefold():
                continue
            problems.append('unattested name %s' % name)
    # Unique, stable order.
    seen = set()
    out = []
    for item in problems:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# Legacy pasted-text Look only. Source-verified play does not speak this.
def visible_description(beat, burst=None):
    """What is already visible, from the scene's player-facing fiction.

    Kept for the legacy pasted-text opening path. Source-verified Look
    does not assemble or commit this string.
    """
    sentences = [re.sub(r'\s+', ' ', str(item)).strip()
                 for item in (beat or {}).get('fiction') or [] if str(item).strip()]
    if not sentences and burst:
        from . import kit_skim
        sentences = [re.sub(r'\s+', ' ', item).strip()
                     for item in kit_skim._sentences(burst) if item]
    kept = []
    hidden_names_ = [person.get('name') for person in (beat or {}).get('people') or []
                     if person.get('name') and person.get('hidden') and not person.get('revealed')]
    for sentence in sentences:
        if not sentence or _HOWTO.search(sentence) or not kit_opening.player_line(sentence):
            continue
        if any(re.search(r'\b%s\b' % re.escape(name), sentence, re.I) for name in hidden_names_):
            continue
        if sentence not in kept:
            kept.append(sentence)
    if kept:
        return ' '.join(kept)
    return kit_opening.look_line(beat)
