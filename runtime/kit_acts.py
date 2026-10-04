"""Structured player acts Kit declares in her decision (#97 design steer).

The engine no longer reads intent out of English to change the world on its own. When a turn
offers an act field (``body['acts'][field]``), Kit's decision may declare it, the declaration
is validated against what the engine offered, and only then does the engine act on it. A
cheap regex may put a ``hint`` in the offer so Kit can confirm it; a hint never fires a
trigger or reveals anything by itself.

Every field follows one pattern, so #101's ``react`` and ``flourish`` (Kit's read of a reply
to an open reaction or flourish window) sit beside ``handles`` without a second schema style:

* the offer: ``body['acts'][field]``, built by the engine at prepare (what may be declared
  this turn: ids, plus an optional hint), shown to Kit as ``acts.<field>`` in the packet;
* the declaration: ``plan[field]``, optional; omitted or ``none`` means nothing declared;
* the check: ``FIELDS[field](value, offer)`` returns the normalized declaration or None and
  raises InvalidChange (a rejection Kit can fix) when it names something not offered.

``handles: {target, act}``: the PC's hands go on a keyed feature this turn (pry the claw,
take the orb, climb onto the carcass, stab the hide). ``target`` is a feature id, one of its
parts, or the id of what it holds, as offered; ``act`` is from HANDLE_ACTS. A look, a step
toward it, cover behind it or a question about it is no handling: omit the field.
"""
import re

from .state_context import require

HANDLE_ACTS = ('take', 'pry', 'lift', 'move', 'push', 'roll', 'pull', 'break', 'cut', 'stab', 'kick',
               'climb', 'enter', 'open', 'search', 'hook', 'touch', 'other')
# Acts that shift the whole feature (its ``move`` line) unless a part is named; a climb or
# an entry is its ``enter`` line; a search its ``look`` line; anything else is ``handle``.
MOVE_ACTS = ('move', 'push', 'roll', 'lift', 'kick')
ENTER_ACTS = ('climb', 'enter')
SEARCH_ACTS = ('search', 'open')
NONE = 'none'

HANDLES_SCHEMA = {'type': 'object', 'additionalProperties': False,
                  'properties': {'target': {'type': 'string'},
                                 'act': {'type': 'string', 'enum': list(HANDLE_ACTS) + [NONE]}},
                  'required': ['target', 'act']}
# The decision schema's act fields (PLAN_SCHEMA properties), all optional.
SCHEMAS = {'handles': HANDLES_SCHEMA}

HANDLES_RULE = ('Set handles {target, act} only if the PC puts hands on it this turn (pry, take, climb, '
                'stab, search...). A look, a step toward it, cover behind it or a question: omit handles.')


def declared(plan, field):
    """The raw declaration, or None when omitted or none."""
    value = (plan or {}).get(field)
    if value in (None, NONE):
        return None
    if isinstance(value, dict) and NONE in (value.get('target'), value.get('act')):
        return None
    return value


def check_handles(value, offer):
    """{feature, part, act} for a valid declaration (part: the part word or held id named)."""
    require(isinstance(value, dict) and set(value) == {'target', 'act'},
            'handles is {target, act} or omitted')
    require(offer, 'Nothing here can be handled this turn: omit handles.')
    act = str(value['act']).strip().casefold()
    require(act in HANDLE_ACTS, f'handles.act is one of {", ".join(HANDLE_ACTS)}')
    target = str(value['target']).strip().casefold()
    for feature, words in (offer.get('targets') or {}).items():
        if target == feature:
            return {'feature': feature, 'part': None, 'act': act}
        if target in words:
            return {'feature': feature, 'part': target, 'act': act}
    raise_names = ', '.join(sorted(offer.get('targets') or {}))
    require(False, f'handles.target {value["target"]!r} is not offered here: one of {raise_names} '
                   'or a part listed with it.')


# -- react / flourish: Kit's read of the player's reply to an open window (#101) ----------------
# The offer is the open window (``body['acts']['react']`` = {'options': [reaction ids]},
# ``body['acts']['flourish']`` = {'target': id}); the engine checks the declared choice is legal
# (offered, still available) and never reads the reply's words itself.
REACT_FIXED = ('decline', 'unclear')
FLOURISH_READS = ('describe', 'new_action', 'unclear')
REACT_SCHEMA = {'type': 'object', 'additionalProperties': False,
                'properties': {'choice': {'type': 'string'}, 'cast_in_avrae': {'type': 'boolean'},
                               'slot_level': {'type': ['integer', 'null']}},
                'required': ['choice']}
FLOURISH_SCHEMA = {'type': 'string', 'enum': list(FLOURISH_READS)}
# The window_answer packet's decision schema: one act field per window kind.
WINDOW_SCHEMAS = {'react': REACT_SCHEMA, 'flourish': FLOURISH_SCHEMA}
REACT_RULE = ('react {choice, cast_in_avrae, slot_level}: choice is an offered reaction id, decline, or unclear '
              '(then ask, one short question). cast_in_avrae true only when the reply shows the spell cast in '
              'Avrae; slot_level only when the reply names an upcast slot.')
FLOURISH_RULE = ('flourish: describe (the reply describes the kill), new_action (the player does something '
                 'else instead), or unclear (then ask, one short question).')


def check_react(value, offer):
    """{'react': id|decline|unclear, 'cast_in_avrae': bool, 'slot_level'?} for a legal read."""
    require(offer, 'No reaction window is open: omit react.')
    require(isinstance(value, dict) and 'choice' in value and set(value) <= {'choice', 'cast_in_avrae', 'slot_level'},
            'react is {choice, cast_in_avrae?, slot_level?}')
    allowed = list(offer.get('options') or ()) + list(REACT_FIXED)
    require(value['choice'] in allowed, f'react.choice must be one of {allowed}')
    out = {'react': value['choice'], 'cast_in_avrae': value.get('cast_in_avrae') is True}
    level = value.get('slot_level')
    if level is not None:
        require(type(level) is int and 1 <= level <= 9, 'react.slot_level is 1-9 or null')
        out['slot_level'] = level
    return out


def check_flourish(value, offer):
    require(offer, 'No flourish window is open: omit flourish.')
    require(value in FLOURISH_READS, f'flourish must be one of {", ".join(FLOURISH_READS)}')
    return {'flourish': value}


FIELDS = {'handles': check_handles, 'react': check_react, 'flourish': check_flourish}


def check(plan, body):
    """Every act field the decision declares, validated against this turn's offers:
    {field: normalized} (only the declared ones)."""
    offers = (body or {}).get('acts') or {}
    out = {}
    for field, checker in FIELDS.items():
        value = declared(plan, field)
        if value is None:
            continue
        require(not (plan or {}).get('ask_player'), f'A question to the player declares no {field}.')
        out[field] = checker(value, offers.get(field))
    return out


def model_view(offers):
    """The packet's private ``acts`` block (each field's one-line rule is a first_try line)."""
    view = {}
    for field, offer in (offers or {}).items():
        if field == 'handles' and offer:
            view['handles'] = {'targets': offer['targets'], **({'hint': offer['hint']} if offer.get('hint') else {})}
    return view


def handle_line(handling, decl):
    """The room file's line for a declared handling, else None."""
    act, part = decl['act'], decl.get('part')
    if act in ENTER_ACTS:
        order = ('enter', 'handle', 'move')
    elif act in SEARCH_ACTS:
        order = ('look', 'handle', 'move')
    elif act in MOVE_ACTS and not part:
        order = ('move', 'handle', 'look')
    else:
        order = ('handle', 'move', 'look')
    return next((handling[key] for key in order if handling.get(key)), None)


# -- the regex hint (never acts by itself) ---------------------------------------------------
HINT_VERBS = {
    'pry': 'pry|pries|prise|prises|prize|lever|levers|wrench|wrenches|force|forces|unclench|unclenches',
    'take': 'take|takes|grab|grabs|snatch|snatches|pluck|plucks|pick up|picks up|remove|removes|'
            'extract|extracts',
    'pull': 'pull|pulls|yank|yanks|tug|tugs|drag|drags|twist|twists',
    'lift': 'lift|lifts|raise|raises|heave|heaves',
    'move': 'move|moves|shift|shifts|nudge|nudges|tip|tips|flip|flips|overturn|overturns',
    'push': 'push|pushes|shove|shoves|prod|prods|poke|pokes',
    'roll': 'roll|rolls',
    'break': 'break|breaks|snap|snaps|smash|smashes|crack|cracks',
    'cut': 'cut|cuts|saw|saws|slice|slices|carve|carves|peel|peels',
    'stab': 'stab|stabs|hit|hits|strike|strikes|hack|hacks|slash|slashes|whack|whacks',
    'kick': 'kick|kicks|stomp|stomps',
    'climb': 'climb|climbs|clamber|clambers|scramble|scrambles|mount|mounts|stand on|stands on|sit on|sits on',
    'search': 'search|searches|rummage|rummages|examine|examines|inspect|inspects|check|checks|feel|feels',
    'open': 'open|opens|unseal|unseals',
    'hook': 'hook|hooks|fish|fishes|lever out',
    'touch': 'touch|touches|tap|taps|stroke|strokes|rub|rubs|grip|grips|grasp|grasps',
}
# Words between the verb and the noun that mean it is not the verb's own object: a step
# toward it, cover behind it, a look at it, a path around it ('take a step toward the claw').
NOT_OBJECT = re.compile(r"\b(?:toward|towards|to|at|near|by|beside|behind|around|past|from|away|wide|of|"
                        r"over|under|along|with|step|steps|look|looks|glance|cover|line|sight|breath|"
                        r"spot|way|path|run|back|closer|far|myself|lantern|torch|light|nothing)\b")


def hint(words, nouns):
    """{act, word} when a hands-on verb's own object is one of ``nouns`` (word -> any), else None.
    Questions and quoted speech are stripped by the caller."""
    best = None
    for act, verbs in HINT_VERBS.items():
        for match in re.finditer(r'\b(?:' + verbs + r')\b', words):
            tail = words[match.end():match.end() + 60]
            for noun in nouns:
                found = re.search(r"^((?:\s+[\w'-]+){0,4}?)\s+" + re.escape(noun) + r's?\b', tail)
                if not found or NOT_OBJECT.search(found.group(1)):
                    continue
                at = match.start()
                if best is None or at < best[0] or (at == best[0] and found.end() < best[3]):
                    best = (at, act, noun, found.end())
    return {'act': best[1], 'word': best[2]} if best else None
