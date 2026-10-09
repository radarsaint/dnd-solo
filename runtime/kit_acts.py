"""Structured player acts Kit declares in her decision (#97 design steer).

The engine no longer reads intent out of English to change the world on its own. When a turn
offers an act field (``body['acts'][field]``), Kit's decision may declare it, the declaration
is validated against what the engine offered, and only then does the engine act on it. A
cheap regex may put a ``hint`` in the offer so Kit can confirm it; a hint never fires a
trigger or reveals anything by itself.

Every field follows one pattern, so later fields (#101's ``react``) slot in beside
``handles`` without a second schema style:

* the offer: ``body['acts'][field]``, built by the engine at prepare (what may be declared
  this turn: ids, plus an optional hint), shown to Kit as ``acts.<field>`` in the packet;
* the declaration: ``plan[field]``. When a field is offered the decision must answer it
  (#97 review B): a declaration, or ``none`` for handles. Kit cannot leave it out and still
  narrate the thing happening. A field not offered must not be declared;
* the check: ``FIELDS[field](value, offer)`` returns the normalized declaration or None and
  raises InvalidChange (a rejection Kit can fix) when it names something not offered.

``handles: {target, act}``: the PC's hands go on a keyed feature this turn (pry the claw,
take the orb, climb onto the carcass, stab the hide). ``target`` is a feature id, one of its
parts, or the id of what it holds, as offered; ``act`` is from HANDLE_ACTS. A look, a step
toward it, cover behind it, a look at it, examining it, or a question about it is no
handling: ``{"target": "none", "act": "none"}``. The offer comes on every physical turn in an
area with a pending disturb trigger on a feature the PC knows about, so a pronoun ("I push it
open") or another word for it ("the stone slab") is Kit's to resolve.

``downed: {act}``: the PC is down at 0 hit points and foes act before his next turn. Kit says
whether they attack him (``attack``) or leave him be (``turn_away``); the engine runs their
turns on that call.
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
# Mid-fight, a light touch is the turn's one free object interaction (SRD); the rest take the action.
OBJECT_ACTS = ('take', 'open', 'pull', 'hook', 'touch')
NONE = 'none'

HANDLES_SCHEMA = {'type': 'object', 'additionalProperties': False,
                  'properties': {'target': {'type': 'string'},
                                 'act': {'type': 'string', 'enum': list(HANDLE_ACTS) + [NONE]}},
                  'required': ['target', 'act']}
DOWNED_ACTS = ('attack', 'turn_away')
DOWNED_SCHEMA = {'type': 'object', 'additionalProperties': False,
                 'properties': {'act': {'type': 'string', 'enum': list(DOWNED_ACTS)}}, 'required': ['act']}
# The decision schema's act fields (PLAN_SCHEMA properties). Each is required only on a turn
# that offers it (check), so the schema keeps them optional.
SCHEMAS = {'handles': HANDLES_SCHEMA, 'downed': DOWNED_SCHEMA}

HANDLES_RULE = ('Answer handles every turn it is offered. {target, act} only when the PC physically '
                'manipulates a listed thing this turn (pries, lifts, pushes, takes, climbs, opens, stabs it; '
                '"it" or another word for it counts). Looking, examining, a step toward it, cover behind it '
                'or a question is not handling: {"target": "none", "act": "none"}. Never narrate a hidden '
                'creature unless your handles sets it off.')
DOWNED_RULE = ('The PC is down at 0 hit points and acts.downed.foes act before his next turn. Your call, by '
               'what they want: {"act": "attack"} (a hit on him is a critical hit: two failed death saves) or '
               '{"act": "turn_away"} (they leave him be).')
RULES = {'handles': HANDLES_RULE, 'downed': DOWNED_RULE}


def declared(plan, field):
    """The raw declaration, or None when it says none."""
    value = (plan or {}).get(field)
    if value in (None, NONE):
        return None
    if isinstance(value, dict) and set(value) == {'target', 'act'} and \
            str(value.get('target')).strip().casefold() == NONE and str(value.get('act')).strip().casefold() == NONE:
        return None
    return value


def check_handles(value, offer):
    """{feature, part, act} for a valid declaration (part: the part word or held id named)."""
    require(isinstance(value, dict) and set(value) == {'target', 'act'},
            'handles is {target, act}, or {"target": "none", "act": "none"}')
    require(NONE not in (str(value['target']).strip().casefold(), str(value['act']).strip().casefold()),
            'handles says none with both: {"target": "none", "act": "none"}')
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


def check_downed(value, offer):
    """{act, foes} for Kit's call on foes acting while the PC is down."""
    require(isinstance(value, dict) and set(value) == {'act'} and value.get('act') in DOWNED_ACTS,
            'downed is {"act": "attack"} or {"act": "turn_away"}')
    require(offer, 'Nobody is acting on a downed PC this turn: leave downed out.')
    return {'act': value['act'], 'foes': list(offer.get('foes') or ())}


FIELDS = {'handles': check_handles, 'downed': check_downed}


def check(plan, body):
    """Every act field the decision declares, validated against this turn's offers:
    {field: normalized} (only the declared ones). An offered field must be answered (a
    question to the player answers none of them and declares nothing)."""
    offers = (body or {}).get('acts') or {}
    asked = bool((plan or {}).get('ask_player'))
    out = {}
    for field, checker in FIELDS.items():
        if offers.get(field) and not asked:
            require(field in (plan or {}),
                    f'acts.{field} is offered this turn: answer it'
                    + (' ({target, act}, or {"target": "none", "act": "none"} when his hands go on nothing '
                       'listed).' if field == 'handles' else ' ({"act": "attack"} or {"act": "turn_away"}).'))
        value = declared(plan, field)
        if value is None:
            continue
        require(not asked, f'A question to the player declares no {field}.')
        out[field] = checker(value, offers.get(field))
    return out


def model_view(offers):
    """The packet's private ``acts`` block (each field's one-line rule is a first_try line)."""
    view = {}
    for field, offer in (offers or {}).items():
        if field == 'handles' and offer:
            view['handles'] = {'targets': offer['targets'], **({'hint': offer['hint']} if offer.get('hint') else {})}
        elif field == 'downed' and offer:
            view['downed'] = {'foes': list(offer.get('names') or offer.get('foes') or ())}
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
    # Not examine, inspect or check: looking closely is not handling (#97 review).
    'search': 'search|searches|rummage|rummages|feel|feels',
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
