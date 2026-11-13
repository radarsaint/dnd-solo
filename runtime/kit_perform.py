"""Source-grounded Look descriptions and in-character NPC replies.

Python assembles these from the validated scene form and any link-web
NPC notes. Book facts in a line must already be quoted in that
material. Kit's instruction vocabulary never appears in an NPC's mouth.
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

_HOWTO = kit_opening._FRONT

# Closed first-person tissue used to turn a third-person quote into speech.
_TISSUE = frozenset("""
    i i'm i've i'd i'll me my mine myself we we're we've our you your
    am is are was were be been being have has had do does did will would
    can could shall should may might must to of the a an and or but if
    in on at for with from that this it its as not no yes here there
    what who whom whose which when where why how about just still now
    then well so all any some that that's that's
    have has
""".split())

_GENERIC = (
    "I'm right here. Say what you need.",
    "You've got my attention. What's this about?",
    "I can hear you. Make it plain.",
)


def instruction_vocab(text):
    """True when the line uses Kit's instruction language."""
    return bool(_INSTRUCTION.search(text or ''))


def visible_description(beat, burst=None):
    """What is already visible, from the scene's player-facing fiction.

    How-to-play lines, DM notes, and examples are left out. Hidden or
    still-staged people are not described.
    """
    sentences = [re.sub(r'\s+', ' ', str(item)).strip()
                 for item in (beat or {}).get('fiction') or [] if str(item).strip()]
    if not sentences and burst:
        from . import kit_skim
        sentences = [re.sub(r'\s+', ' ', item).strip()
                     for item in kit_skim._sentences(burst) if item]
    kept = []
    hidden_names = [person.get('name') for person in (beat or {}).get('people') or []
                    if person.get('name') and person.get('hidden') and not person.get('revealed')]
    for sentence in sentences:
        if not sentence or _HOWTO.search(sentence) or not kit_opening.player_line(sentence):
            continue
        if any(re.search(r'\b%s\b' % re.escape(name), sentence, re.I) for name in hidden_names):
            continue
        if sentence not in kept:
            kept.append(sentence)
    if kept:
        return ' '.join(kept)
    fallback = kit_opening.look_line(beat)
    return fallback


def look_spoken(beat, burst=None):
    """Kit speaks the visible description and hands the turn back."""
    description = visible_description(beat, burst)
    if not description.endswith(('.', '!', '?')):
        description = description + '.'
    return 'Kit: %s What do you do?' % description


def npc_answer(person, action, beat=None, prior=None, notes=None):
    """An in-character line from what the book says this person knows or wants.

    When the book gives no established fact, the line is short, plausible,
    and consistent with their stated goal. Identical repeats are refused.
    """
    sources = fact_sources(person, notes)
    prior = [re.sub(r'\s+', ' ', str(item)).strip() for item in (prior or []) if item]
    line = _from_sources(sources, action)
    if not line:
        line = _generic_line(action, _goal_text(person), prior)
    if instruction_vocab(line):
        line = _generic_line(action, '', prior)
    line = _avoid_repeat(line, action, sources, prior)
    if instruction_vocab(line):
        line = _unused_generic(prior)
    return line


def talk_spoken(person, action, beat=None, prior=None, notes=None):
    """Named speaker line, then a short Kit handoff."""
    name = (person or {}).get('name') or 'They'
    line = npc_answer(person, action, beat=beat, prior=prior, notes=notes)
    return '%s: %s\nKit: What do you say back?' % (name, line)


def fact_sources(person, notes=None):
    """Established quotes this person may speak from."""
    found = []
    goal = _goal_text(person)
    if goal:
        found.append(goal)
    for item in (person or {}).get('knowledge_evidence') or []:
        quote = item.get('quote') if isinstance(item, dict) else item
        if quote and str(quote).strip():
            found.append(re.sub(r'\s+', ' ', str(quote)).strip())
    for note in notes or []:
        text = note.get('quote') if isinstance(note, dict) else note
        if text and str(text).strip():
            found.append(re.sub(r'\s+', ' ', str(text)).strip())
    return found


def repair_npc_text(text, person, action, beat=None, prior=None, notes=None):
    """Replace an instruction-flavored or empty NPC line with a sourced one."""
    body = text or ''
    if (not body.strip() or instruction_vocab(body)
            or _same_as_prior(body, prior)):
        return npc_answer(person, action, beat=beat, prior=prior, notes=notes)
    return body


def _goal_text(person):
    goal = (person or {}).get('goal') or (person or {}).get('motive') or ''
    if isinstance(goal, dict):
        if goal.get('status') and goal.get('status') != 'established':
            return ''
        goal = goal.get('quote') or ''
    goal = re.sub(r'\s+', ' ', str(goal)).strip()
    # A generic compiled default is not a book fact.
    if goal.casefold() in (
            'answer whoever speaks to them here.',
            'they are in this scene.',
            'they are here.',
            'they keep their aim.',
    ):
        return ''
    return goal


def _from_sources(sources, action):
    if not sources:
        return ''
    terms = _terms(action)
    ranked = sorted(sources, key=lambda quote: -len(_terms(quote) & terms))
    quote = ranked[0]
    return _in_character(quote)


def _in_character(quote):
    text = re.sub(r'\s+', ' ', quote or '').strip()
    if not text:
        return ''
    # Drop a leading name so "Mara has orders to hold the road" becomes first person.
    text = re.sub(
        r"^(?:[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+"
        r"(?:has |have |had |wants? |wanted |is |are |was |were )",
        '',
        text, count=1)
    text = re.sub(r"^(?:has orders to|have orders to|orders to|ordered to)\s+",
                  'I have orders to ', text, flags=re.I)
    text = re.sub(r"^(?:wants? to|wanted to)\s+", 'I mean to ', text, flags=re.I)
    if not re.match(r"(?i)^i\b", text):
        if re.match(r"(?i)^(?:to|hold|keep|watch|guard|stay|wait|answer)\b", text):
            text = 'I ' + text[0].lower() + text[1:] if text else text
        else:
            text = 'I know this: ' + text[0].lower() + text[1:] if text else text
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    if text and text[-1] not in '.!?':
        text = text + '.'
    if instruction_vocab(text):
        return ''
    return text


def _generic_line(action, goal, prior):
    if goal:
        line = _in_character(goal)
        if line and not _same_as_prior(line, prior) and not instruction_vocab(line):
            return line
    return _unused_generic(prior, action)


def _unused_generic(prior, action=None):
    used = {_norm(item) for item in (prior or [])}
    # Prefer a generic that shares a question word with the action, else the first unused.
    terms = _terms(action)
    ranked = list(_GENERIC)
    if terms & {'who', 'name'}:
        ranked = ["You've got my attention. What's this about?"] + ranked
    elif terms & {'do', 'next', 'should', 'what'}:
        ranked = ["I'm right here. Say what you need."] + ranked
    for line in ranked:
        if _norm(line) not in used:
            return line
    # Last resort: lean on a word from the question so the line is not identical.
    hook = next(iter(terms), 'this')
    return "I'm still here. Ask me plainly about %s." % hook


def _avoid_repeat(line, action, sources, prior):
    if not _same_as_prior(line, prior):
        return line
    for quote in sources[1:]:
        alt = _in_character(quote)
        if alt and not _same_as_prior(alt, prior) and not instruction_vocab(alt):
            return alt
    return _generic_line(action, '', prior)


def _same_as_prior(line, prior):
    key = _norm(line)
    if not key:
        return False
    return any(_norm(item) == key for item in (prior or []))


def _norm(text):
    return re.sub(r'[^a-z0-9]+', ' ', (text or '').casefold()).strip()


def _terms(text):
    return set(re.findall(r"[a-z][a-z']{2,}", (text or '').casefold()))


def link_notes_for(index, person):
    """Link-web notes whose subject is this person."""
    from . import kit_links
    name = (person or {}).get('name') or ''
    if not name:
        return []
    notes = []
    key = None
    if index:
        key = kit_links.section_key(index, index.get('start'))
        for link in kit_links.links_from(index, key):
            subject = (link.get('subject') or '').strip()
            kind = link.get('kind') or ''
            if not subject:
                continue
            if subject.casefold() == name.casefold() or name.casefold() in subject.casefold():
                if kind in ('npc', 'name', 'npc_note', 'pointer') or link.get('quote'):
                    if link.get('quote'):
                        notes.append(link.get('quote'))
    return notes
