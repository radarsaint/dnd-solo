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

# Second-person coaching to the reader or the DM, not in-world fiction.
_COACHING = re.compile(
    r"(?i)(?:\byou can\b|\byou can each\b|\byou can tell them\b|"
    r"\byou can even\b|\byou can describe\b|\btry not to\b|"
    r"\bif you want to\b|\bif you are playing\b|\bif you're playing\b|"
    r"\btell me the total\b|\bi'll tell you\b|\bi will tell you\b|"
    r"\byour character\b|\bthe characters would\b|\bthey can reveal\b|"
    r"\bcharacter death\b|\boutside help\b|\bif the attack hit\b|"
    r"\bsuccess or failure\b|\beach have one character\b|"
    r"\bone character to play\b|\bwant the excitement\b|"
    r"\bwe need perception\b|\bperception checks?\b|"
    r"\bexplain what attacks\b|\bmaybe even describe their\b)"
)

# Column-merged mid-sentence break: a new sentence capital after a lowercase word.
_COLUMN_MERGE = re.compile(
    r'(?<=[a-z,])\s+(?:The|This|It|You|If|When|Some|They|A|An|But|For|'
    r'And|We|Tell|Your|There|These|Those)\b'
)

_FRAGMENT_START = re.compile(
    r"^(?:stops?|holds?|open|opens|rake|tears?|adds?|using|including|"
    r"coming|stops and|open a)\b",
    re.I,
)

# In-world character background the section establishes (where they are from).
_CHARACTER_BACKGROUND = re.compile(
    r"(?i)\b(?:you are from|you're from|you come from|you came from|"
    r"you were born|you grew up|you live in|you hail from|"
    r"your home (?:is|was|village|town|city)|"
    r"today,? it(?:'|’)s your turn|"
    r"your patrol today)\b"
)

_KNOWLEDGE_QUESTION = re.compile(
    r"(?i)\bwhat do (?:i|we) (?:know|recall|remember) about\b|"
    r"\bwhat (?:can|do) (?:you|kit) tell (?:me|us) about\b|"
    r"\bdo i know (?:anything |something )?(?:about|of)\b|"
    r"\bwould (?:i|we) know\b|"
    r"\bhave (?:i|we) (?:heard|learned) (?:of|about)\b|"
    r"\bwhat (?:is|do i know of) this (?:village|town|city|place|area)\b"
)

_HOME_PLACE = re.compile(
    r"(?i)\b(?:from|in)\s+the\s+(?:village|town|city|settlement|hamlet)\s+of\s+([A-Z][A-Za-z']+)"
    r"|\byou (?:are|come|hail) from\s+([A-Z][A-Za-z']+)"
    r"|\byou live in\s+(?:the\s+)?([A-Z][A-Za-z']+)"
)

_ASKS_HOME = re.compile(
    r"(?i)\b(?:this|the|our|my)\s+(?:village|town|city|settlement|home|hamlet)\b"
)

_BEYOND_BASELINE = re.compile(
    r"(?i)\b(?:beyond|dungeon|lair|ruin|cave|what lies|deeper|"
    r"unexplored|old wars?|ancient|forgotten|centuries|"
    r"the mountains?(?:\s+beyond)?)\b"
)

_RULES_VOICE = re.compile(
    r"(?i)(?:\bwhen the action is\b|\bsomewhere between easy and impossible\b|"
    r"\btrying to do it could lead\b|\bopen a wound or rake\b|"
    r"\bharmlessly off armor\b|\bdamage\s*\d+\s*d\s*\d+\b|\b\d+d\d+\b|"
    r"\bdc\s*\d+\b|\bshortbow attack\b|\bmelee weapon\b|"
    r"\ba question like\b|\byou explain\b|\byou tell them\b|"
    r"\bhit points?\b|\bchallenge rating\b|\bability scores?\b|"
    r"\bor higher, you\b|\byou explain that they\b)"
)

_LATER_ENCOUNTER = re.compile(
    r'^(?:encounter|scene|section)\s+[A-Z]?\d{1,3}[a-z]?\b',
    re.I,
)

_FUNCTION = frozenset(
    "a an the and or but if so then of to in on at by for from with "
    "this that these those you your we they them their it its is are "
    "was were be been being do does did has have had will can "
    "may might must shall should about into over after before when "
    "where what which there than them also more some such very once "
    "here still back down away even much many well just only not no".split()
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
    """True when the line is how-to-play, a DM tip, or rules coaching."""
    return bool(text and (_HOWTO_TIP.search(text) or is_coaching(text)
                          or _RULES_VOICE.search(text)))


def is_character_background(text):
    """True when the line establishes where the characters are from, or similar."""
    return bool(text and _CHARACTER_BACKGROUND.search(text) and not is_howto_or_tip(text)
                and not is_coaching(text))


def is_coaching(text):
    """True when the line coaches the reader or the DM in the second person."""
    return bool(text and _COACHING.search(text))


def is_well_formed(text):
    """True when the line is a complete sentence, not a column-merged fragment."""
    line = _plain(text)
    if not line or len(line.split()) < 5:
        return False
    if not re.match(r"""^[\s"“'‘A-Z]""", line):
        return False
    if not re.search(r"""[.!?!”"']\s*$""", line):
        return False
    if _COLUMN_MERGE.search(line):
        return False
    stripped = line.strip().strip('"“”\'‘’')
    if _FRAGMENT_START.search(stripped):
        return False
    if not re.search(
            r"(?i)\b(?:is|are|was|were|be|been|being|am|do|does|did|"
            r"has|have|had|will|can|cannot|can't|may|might|must|"
            r"shall|should|need|know|see|sees|stand|stands|"
            r"glance|glances|nod|nods|ask|asks|say|says|tell|tells|"
            r"lead|led|live|lives|grew|come|came|step|steps|"
            r"feel|feels|want|wants|look|looks|patrol|patrolled|"
            r"arrive|arrives|enter|enters|wait|waits|check|checks|"
            r"it(?:'s|’s)|that(?:'s|’s))\b",
            line):
        return False
    return True


def is_knowledge_question(action):
    """True when the player is asking what the character knows about a topic."""
    return bool(action and _KNOWLEDGE_QUESTION.search(action))


def knowledge_tier(total):
    """Map a check total to a low / middle / high improv band. The bar is never shown."""
    try:
        score = int(total)
    except (TypeError, ValueError):
        return 'low'
    if score <= 10:
        return 'low'
    if score <= 16:
        return 'middle'
    return 'high'


def knowledge_skill(action):
    """Pick the skill that fits this question or act. Same map as every check."""
    from . import kit_skills
    return kit_skills.skill_for_intent(action)


def sheet_background_fields(sheet):
    """Player-facing background fields from the sheet. No bonuses or DCs."""
    sheet = sheet or {}
    history = (sheet.get('history') or sheet.get('backstory')
               or sheet.get('stated_history') or '')
    origin = sheet.get('origin') or sheet.get('home') or ''
    race = sheet.get('race') or sheet.get('ancestry') or sheet.get('species') or ''
    return {
        'name': sheet.get('name') or '',
        'background': sheet.get('background') or '',
        'origin': origin if isinstance(origin, str) else '',
        'class': sheet.get('class') or '',
        'race': race if isinstance(race, str) else '',
        'history': history if isinstance(history, str) else '',
    }


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


def _is_later_section_heading(line):
    """True for a later encounter or keyed-area heading, not the current title."""
    from . import kit_skim
    from . import kit_adventure
    text = (line or '').strip().lstrip('>').strip()
    if not text:
        return False
    if _LATER_ENCOUNTER.match(text):
        return True
    labeled = getattr(kit_adventure, '_LABELED_RE', None)
    if labeled is not None and labeled.match(text):
        return True
    if kit_skim._KEYED.match(text) or kit_skim._LATER.match(text):
        return True
    if re.match(r'(?i)^(?:chapter|part)\s+\d+\b', text):
        return True
    return False


def _cut_at_later_heading(text):
    """Keep the current section only; stop at the next encounter or keyed heading."""
    kept = []
    started = False
    for line in (text or '').splitlines():
        stripped = line.strip().lstrip('>').strip()
        if started and _is_later_section_heading(stripped):
            break
        if stripped:
            started = True
        kept.append(line)
    return '\n'.join(kept)


def _section_windows(db, scene_key=None):
    """(current_body, later_body, book) using the landing recorded-body bound, then a heading cut.

    Later material is everything after that cut in the same recorded span, plus later keyed areas.
    """
    from .kit_adventure import _load
    from . import kit_links, kit_skim
    try:
        index, book = _load(db)
    except Exception:
        return '', '', ''
    book = book or ''
    key = kit_links.section_key(index, scene_key or index.get('start'))
    loc = (index.get('locations') or {}).get(key) or {}
    span = kit_links._recorded_span(loc, len(book))
    if not span:
        return '', '', book
    recorded = book[span[0]:span[1]]
    lanes = []
    try:
        lanes = kit_skim._section_lanes(recorded) or []
    except Exception:
        lanes = []
    if not lanes:
        lanes = [('section', recorded)]
    current_parts = []
    later_parts = []
    for _label, stream in lanes:
        cut = _cut_at_later_heading(stream)
        current_parts.append(cut)
        if stream[len(cut):].strip():
            later_parts.append(stream[len(cut):])
        elif len(cut) < len(stream):
            later_parts.append(stream[len(cut):])
        # When the heading sits on its own line, leftover is after the break.
        if cut and cut in stream:
            rest = stream.split(cut, 1)[-1]
            # More reliable: find the heading line in the raw lane.
    # Recompute later text from the first later heading in the recorded span.
    later_from_recorded = ''
    started = False
    later_lines = []
    seen_body = False
    for line in recorded.splitlines():
        stripped = line.strip().lstrip('>').strip()
        if seen_body and _is_later_section_heading(stripped):
            started = True
        if stripped:
            seen_body = True
        if started:
            later_lines.append(line)
    later_from_recorded = '\n'.join(later_lines)
    current = '\n'.join(current_parts)
    # Later keyed locations after this span.
    later = [later_from_recorded]
    for other in (index.get('locations') or {}).values():
        other_span = kit_links._recorded_span(other, len(book))
        if not other_span:
            continue
        # Later than the current section, including areas that start inside
        # an over-wide recorded span.
        if other is not loc and other_span[0] > span[0]:
            later.append(book[other_span[0]:other_span[1]])
    return current, '\n'.join(later), book


def _is_section_fact(line, boxed=False):
    """Keep player-facing fiction and character background; drop rules, coaching, and junk.

    Dropping a good line beats keeping a how-to, a DM tip, or a merged fragment.
    boxed is accepted for compatibility; it does not relax the well-formedness gate.
    """
    from . import kit_skim
    line = _plain(line).lstrip('>').strip()
    if not line or len(line.split()) < 5:
        return False
    if is_howto_or_tip(line) or is_coaching(line) or _HOWTO.search(line):
        return False
    if _RULES_VOICE.search(line):
        return False
    if kit_skim._blocks_quote(line) or kit_skim._unsafe(line):
        return False
    if not is_well_formed(line):
        return False
    if is_character_background(line):
        return True
    # A line that is itself spoken dialogue, not a line that merely contains a quote.
    stripped = line.strip()
    if re.match(r'^[“"\'].+[”"\']$', stripped):
        return True
    # In-world second-person fiction, not an instruction to the reader.
    if re.search(
            r"(?i)\b(?:you are from|you're from|you (?:step|stand|see|follow|"
            r"enter|arrive|live|grew|come|feel|walk|look around|are on|"
            r"are from)|today,? it(?:'|’)s your turn)\b",
            line) and not re.search(r'(?i)\byou explain\b', line):
        return True
    # Third-person description of the place or a present person.
    if re.search(
            r"(?i)\b(?:stands?|glances?|nods?|hails?|waits?|led by|"
            r"patrol(?:s|ed)?|taps?|watches?)\b",
            line):
        return True
    return False


def _fiction_stream(text):
    """Drop headings and box marks so they cannot glue onto the next sentence."""
    lines = []
    for line in (text or '').splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append('')
            continue
        bare = stripped.lstrip('>').strip()
        if _is_later_section_heading(bare) or re.match(
                r'^(?:area\s+)?[A-Z]?\d{1,3}[a-z]?\s*[.:]\s+\S', bare, re.I):
            continue
        lines.append(bare)
    return '\n'.join(lines)


def _section_player_quotes(db, scene_key=None, cap=80):
    """Playable fiction and party/place facts from the current section body only.

    How-to-play, DM coaching, and malformed column fragments are dropped.
    Later encounters in the same recorded span are not included.
    """
    from . import kit_skim
    quotes = []
    current, _later, _book = _section_windows(db, scene_key)
    if not current.strip():
        return quotes

    def add(sentence):
        line = _plain(sentence)
        if not line or line in quotes:
            return
        if not _is_section_fact(line):
            return
        quotes.append(line)

    for _label, stream in (kit_skim._section_lanes(current) or [('section', current)]):
        body = _fiction_stream(_cut_at_later_heading(stream))
        for sentence in kit_skim._sentences(body) or []:
            add(sentence)
            if len(quotes) >= cap:
                return quotes[:cap]
    return quotes[:cap]


def _established_homes(section_lines):
    """Place names the current section says the characters are from or live in."""
    found = []
    for line in section_lines or []:
        hit = _HOME_PLACE.search(line or '')
        if not hit:
            continue
        name = next((g for g in hit.groups() if g), '')
        if name and name.casefold() not in found:
            found.append(name.casefold())
    return found


def _sheet_homes(sheet):
    """Place names the sheet itself gives as origin or home."""
    found = []
    fields = sheet or {}
    for key in ('origin', 'home', 'history'):
        value = fields.get(key) or ''
        if not isinstance(value, str) or not value.strip():
            continue
        hit = _HOME_PLACE.search(value)
        if hit:
            name = next((g for g in hit.groups() if g), '')
            if name and name.casefold() not in found:
                found.append(name.casefold())
        # A short proper place sitting in origin or home.
        if key in ('origin', 'home') and re.match(r"^[A-Z][A-Za-z' ]{2,30}$", value.strip()):
            folded = value.strip().casefold()
            if folded not in found:
                found.append(folded)
    return found


def _topic_tokens(question):
    """Significant words from a 'what do I know about X' question."""
    text = question or ''
    match = re.search(
        r"(?i)(?:know|recall|remember|tell (?:me|us)) about\s+(.+?)[?.!]*$",
        text)
    blob = match.group(1) if match else text
    tokens = []
    for word in re.findall(r"[A-Za-z']+", blob):
        folded = word.casefold()
        if folded in _FUNCTION or folded in _COMMON_NAMES or len(folded) < 4:
            continue
        if folded not in tokens:
            tokens.append(folded)
    return tokens


def baseline_cover(action, sheet, section_lines):
    """Why the background covers this question, or None if a check is needed.

    A local of the asked-about place, or a question the current section already
    answers about the immediate scene, is known with no roll. Settlement lore
    without that tie, or a question that goes beyond everyday knowledge,
    returns None so a check is called.
    """
    question = action or ''
    if _BEYOND_BASELINE.search(question):
        return None
    if re.search(r'(?i)\bmountains?\b', question) and not _ASKS_HOME.search(question):
        return None
    homes = _established_homes(section_lines) + _sheet_homes(sheet)
    if homes and _ASKS_HOME.search(question):
        return 'local'
    folded = question.casefold()
    if homes and any(name in folded for name in homes if len(name) > 3):
        return 'local'
    # Settlement lore without a local or sheet tie needs a check.
    if _ASKS_HOME.search(question):
        return None
    section_fold = ' '.join(section_lines or []).casefold()
    tokens = _topic_tokens(question)
    if tokens and section_fold and any(token in section_fold for token in tokens):
        return 'section'
    return None


def knowledge_decision(action, sheet, section_lines, result_tier=None):
    """Baseline versus a knowledge check, with prepared improv tiers."""
    cover = baseline_cover(action, sheet, section_lines)
    outcomes = {
        'low': 'Answer with common knowledge only. Add no new lead or hook.',
        'middle': 'You may add one useful detail consistent with the section facts.',
        'mid': 'You may add one useful detail consistent with the section facts.',
        'high': 'You may add a real lead or hook consistent with the section facts, '
                'never a fenced spoiler.',
    }
    if cover:
        return {
            'gate': 'baseline',
            'mode': 'baseline',
            'skill': None,
            'covered_by': cover,
            'result_tier': None,
            'outcomes': outcomes,
        }
    return {
        'gate': 'check',
        'mode': 'check',
        'skill': knowledge_skill(action),
        'covered_by': None,
        'result_tier': result_tier,
        'outcomes': outcomes,
    }



_FENCE_STOP = re.compile(
    r"(?i)\b(?:dc|perception|history|arcana|religion|athletics|acrobatics|"
    r"survival|medicine|investigation|insight|stealth|persuasion|"
    r"check|checks|attack|damage|wizard|wizards|tm|treasure|"
    r"healing|injured|wounds?|challenge|climbing|information|"
    r"characters?|alternatively|continue|melee|weapon|dividing|"
    r"equipment|practically|fearsome|comber|copyright|reserved)\b"
)

def _spoiler_fence(current_text, later_text, section_lines=None):
    """Names, creatures, and areas from later sections that must not be spoken."""
    current = (current_text or '') + '\n' + ' '.join(section_lines or [])
    current_fold = current.casefold()
    later = later_text or ''
    terms = []

    def keep(term):
        term = _plain(term)
        if not term or len(term) < 4:
            return
        folded = term.casefold()
        if folded in current_fold:
            return
        if folded in _FUNCTION or folded in _COMMON_NAMES:
            return
        if _FENCE_STOP.search(term):
            return
        if any(folded == existing.casefold() for existing in terms):
            return
        terms.append(term)

    for line in later.splitlines():
        stripped = line.strip().lstrip('>').strip()
        if _is_later_section_heading(stripped):
            # Keep the heading's title words, not the "Encounter 1" label alone.
            title = re.sub(r'(?i)^(?:encounter|scene|section)\s+[A-Z]?\d{1,3}[a-z]?\s*[:.\-]?\s*',
                           '', stripped).strip()
            if title:
                keep(title)
        for name in _proper_names(stripped):
            keep(name)
    # Distinctive two- or three-word phrases that never appear in the current section.
    words = re.findall(r"[A-Za-z']+", later)
    for n in (3, 2):
        for i in range(len(words) - n + 1):
            run = words[i:i + n]
            if any(w.casefold() in _FUNCTION or len(w) < 4 for w in run):
                continue
            if not any(len(w) >= 5 for w in run):
                continue
            phrase = ' '.join(run)
            if phrase.casefold() not in current_fold:
                keep(phrase)
            if len(terms) >= 40:
                break
        if len(terms) >= 40:
            break
    return terms[:40]


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
        current, later, _book = _section_windows(runtime.path, scene_key)
        section = _section_player_quotes(runtime.path, scene_key)
        sheet = {}
        result = {}
        try:
            _revision, state = runtime.load()
            sheet = sheet_background_fields((state or {}).get('player_sheet'))
        except Exception:
            sheet = {}
        try:
            from . import kit_skim
            result = (kit_skim._read(runtime.path) or {}).get('knowledge_result') or {}
        except Exception:
            result = {}
        packet['section'] = section
        established = []
        for line in list(section) + list(visible):
            if is_character_background(line) and line not in established:
                established.append(line)
        packet['party'] = established
        packet['sheet'] = sheet
        packet['spoiler_fence'] = _spoiler_fence(current, later, section + visible + established)
        decision = knowledge_decision(
            action, sheet, section + visible + established, result_tier=result.get('tier'))
        packet['knowledge'] = decision
        packet['gate'] = decision.get('gate')
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
    if kit_skim._LOOKUP.search(text) or is_knowledge_question(text):
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
        for term in (facts or {}).get('spoiler_fence') or []:
            if not term or not re.search(r'\b' + re.escape(term) + r'\b', text, re.I):
                continue
            hop = (facts or {}).get('hop') or {}
            hop_text = hop.get('spoken') or ''
            tier = ((facts or {}).get('knowledge') or {}).get('result_tier')
            if hop_text and term.casefold() in hop_text.casefold() and tier == 'high':
                continue
            problems.append('fenced spoiler')
            break
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
