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
# Why the PC's hands go on nothing offered, when handles is offered and Kit answers none
# (#97 review P1-B'): a bare none on a hands-on turn is no answer.
NONE_REASONS = ('blocked', 'too_heavy', 'not_the_feature', 'stopped_short', 'ooc')

HANDLES_SCHEMA = {'type': 'object', 'additionalProperties': False,
                  'properties': {'target': {'type': 'string'},
                                 'act': {'type': 'string', 'enum': list(HANDLE_ACTS) + [NONE]},
                                 # Only with none: why nothing offered is handled (none on a declaration).
                                 'reason': {'type': 'string', 'enum': list(NONE_REASONS) + [NONE]}},
                  'required': ['target', 'act']}
DOWNED_ACTS = ('attack', 'turn_away')
DOWNED_SCHEMA = {'type': 'object', 'additionalProperties': False,
                 'properties': {'act': {'type': 'string', 'enum': list(DOWNED_ACTS)}}, 'required': ['act']}
# The decision schema's act fields (PLAN_SCHEMA properties). Each is required only on a turn
# that offers it (check), so the schema keeps them optional.
SCHEMAS = {'handles': HANDLES_SCHEMA, 'downed': DOWNED_SCHEMA}  # gear joins below (GEAR_SCHEMA)

HANDLES_RULE = ('Answer handles every turn it is offered. {target, act} only when the PC physically '
                'manipulates a listed thing this turn (pries, lifts, pushes, takes, climbs, opens, stabs it; '
                '"it" or another word for it counts). Looking, examining, a step toward it, cover behind it '
                'or a question is not handling: {"target": "none", "act": "none", "reason": ...}. A none always '
                'carries a reason: blocked, too_heavy, not_the_feature (his hands go on something else), '
                'stopped_short (he does not go through with it) or ooc. With none, never narrate a listed '
                'thing moving or opening, and never narrate a hidden creature unless your handles sets it off.')
DOWNED_RULE = ('The PC is down at 0 hit points and acts.downed.foes act before his next turn. Your call, by '
               'what they want: {"act": "attack"} (a hit on him is a critical hit: two failed death saves) or '
               '{"act": "turn_away"} (they leave him be).')
RULES = {'handles': HANDLES_RULE, 'downed': DOWNED_RULE}


def _is_none(value):
    return isinstance(value, dict) and set(value) in ({'target', 'act'}, {'target', 'act', 'reason'}) and \
        str(value.get('target')).strip().casefold() == NONE and str(value.get('act')).strip().casefold() == NONE


def none_reason(plan):
    """The reason on a handles none answer, else None."""
    value = (plan or {}).get('handles')
    if not _is_none(value):
        return None
    reason = str(value.get('reason') or '').strip().casefold()
    return reason if reason in NONE_REASONS else None


def declared(plan, field):
    """The raw declaration, or None when it says none."""
    value = (plan or {}).get(field)
    if value in (None, NONE):
        return None
    if field == 'gear' and isinstance(value, dict) and str(value.get('state')).casefold() == NONE:
        return None
    if field == 'handles' and _is_none(value):
        return None
    if isinstance(value, dict) and set(value) == {'target', 'act'} and \
            str(value.get('target')).strip().casefold() == NONE and str(value.get('act')).strip().casefold() == NONE:
        return None
    return value


def check_handles(value, offer):
    """{feature, part, act} for a valid declaration (part: the part word or held id named)."""
    require(isinstance(value, dict) and set(value) - {'reason'} == {'target', 'act'},
            'handles is {target, act}, or {"target": "none", "act": "none", "reason": ...}')
    require(str(value.get('reason') or NONE).strip().casefold() == NONE,
            'handles.reason goes only with none: a declaration fires, it needs no reason.')
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


# -- react / flourish: Kit's read of the player's reply to an open window (#101) ----------------
# The offer is the open window (``body['acts']['react']`` = {'options': [reaction ids]},
# ``body['acts']['flourish']`` = {'target': id}); the engine checks the declared choice is legal
# (offered, still available) and never reads the reply's words itself.
REACT_FIXED = ('decline', 'unclear')
FLOURISH_READS = ('describe', 'new_action', 'unclear')
# Kit's ruling for a reaction the engine does not resolve itself: one effect from a closed set,
# checked against the reaction's own sheet text (kit_reactions.allowed_effects) and applied by the engine.
EFFECT_SCHEMA = {'type': 'object', 'additionalProperties': False,
                 'properties': {'type': {'type': 'string', 'enum': ['reduce_damage', 'negate_hit', 'impose_disadvantage',
                                                                    'force_reroll', 'deal_damage', 'move',
                                                                    'succeed_save', 'none']},
                                'roll': {'type': ['integer', 'null']},
                                'save': {'type': ['string', 'null']},
                                'feet': {'type': ['integer', 'null']}},
                 'required': ['type']}
REACT_SCHEMA = {'type': 'object', 'additionalProperties': False,
                'properties': {'choice': {'type': 'string'}, 'cast_in_avrae': {'type': 'boolean'},
                               'slot_level': {'type': ['integer', 'null']},
                               'roll': {'type': ['integer', 'null']},
                               'effect': EFFECT_SCHEMA},
                'required': ['choice']}
FLOURISH_SCHEMA = {'type': 'string', 'enum': list(FLOURISH_READS)}
# The slot ask (Brendon, 2026-10-19): no slot at the spell's level, a higher one free. Kit reads
# the reply: yes (at the offered level, or a free higher one the player names), no, or unclear.
UPCAST_READS = ('yes', 'no', 'unclear')
UPCAST_SCHEMA = {'type': 'object', 'additionalProperties': False,
                 'properties': {'choice': {'type': 'string', 'enum': list(UPCAST_READS)},
                                'slot_level': {'type': ['integer', 'null']}},
                 'required': ['choice']}
# The window_answer packet's decision schema: one act field per window kind.
WINDOW_SCHEMAS = {'react': REACT_SCHEMA, 'flourish': FLOURISH_SCHEMA, 'upcast': UPCAST_SCHEMA}
REACT_RULE = ('react {choice, cast_in_avrae, slot_level, roll, effect}: choice is an offered reaction id, decline, '
              'or unclear (then ask, one short question). cast_in_avrae true only when the reply shows the spell cast '
              'in Avrae; slot_level only when the reply names an upcast slot. roll: the number the player rolled for '
              'the reaction in Avrae (Deflect Missiles, Parry, Hellish Rebuke damage, a Counterspell check), copied '
              'from the reply, never made up. effect, only for a reaction marked "Kit declares the effect": one of '
              'reduce_damage (roll), negate_hit, impose_disadvantage, force_reroll, deal_damage (roll, save), move '
              '(feet), succeed_save, none, as its sheet text says; the engine applies it. Anything else he says with '
              'the answer is resolved as his act after the window.')
FLOURISH_RULE = ('flourish: describe (the reply describes the kill), new_action (the player does something '
                 'else instead), or unclear (then ask, one short question).')
UPCAST_RULE = ('upcast {choice, slot_level}: yes (he casts it with the offered higher slot; slot_level only when '
               'he names another free higher level), no (he does not cast it: nothing is spent), or unclear (then '
               'ask, one short question).')


def check_react(value, offer):
    """{'react': id|decline|unclear, 'cast_in_avrae': bool, 'slot_level'?} for a legal read."""
    require(offer, 'No reaction window is open: omit react.')
    require(isinstance(value, dict) and 'choice' in value and set(value) <= set(REACT_SCHEMA['properties']),
            'react is {choice, cast_in_avrae?, slot_level?, roll?, effect?}')
    allowed = list(offer.get('options') or ()) + list(REACT_FIXED)
    require(value['choice'] in allowed, f'react.choice must be one of {allowed}')
    out = {'react': value['choice'], 'cast_in_avrae': value.get('cast_in_avrae') is True}
    level = value.get('slot_level')
    if level is not None:
        require(type(level) is int and 1 <= level <= 9, 'react.slot_level is 1-9 or null')
        out['slot_level'] = level
    roll = value.get('roll')
    if roll is not None:
        require(type(roll) is int and 0 <= roll <= 200, 'react.roll is the Avrae total (0-200) or null')
        out['roll'] = roll
    effect = value.get('effect')
    if effect is not None:
        types = EFFECT_SCHEMA['properties']['type']['enum']
        require(isinstance(effect, dict) and effect.get('type') in types and
                set(effect) <= set(EFFECT_SCHEMA['properties']), f'react.effect.type is one of {types}')
        out['effect'] = {k: v for k, v in effect.items() if v is not None}
    return out


def check_upcast(value, offer):
    """{'upcast': yes|no|unclear, 'slot_level'?} for a legal read of the slot ask."""
    require(offer, 'No slot ask is open: omit upcast.')
    require(isinstance(value, dict) and value.get('choice') in UPCAST_READS and set(value) <= {'choice', 'slot_level'},
            'upcast is {choice: yes|no|unclear, slot_level?}')
    out = {'upcast': value['choice']}
    level = value.get('slot_level')
    if level is not None:
        free = list(offer.get('free') or [offer.get('level')])
        require(value['choice'] == 'yes' and type(level) is int and level in free,
                f'upcast.slot_level is a free higher slot ({", ".join(str(n) for n in free)}) with yes, or null')
        if level != offer.get('level'):
            out['slot_level'] = level
    return out


# -- gear: the player's answer to an equipment clarification Kit raised (runtime/kit_gear.py) ----
GEAR_STATES = ('held', 'stowed', 'none')
GEAR_SCHEMA = {'type': 'object', 'additionalProperties': False,
               'properties': {'item': {'type': 'string'}, 'state': {'type': 'string', 'enum': list(GEAR_STATES)}},
               'required': ['item', 'state']}
GEAR_RULE = ('gear {item, state}: only when the player answers the equipment question you raised (acts.gear): '
             'held (he keeps it in use: on his arm, worn) or stowed (he puts it away). Not answered this turn: '
             '{"item": "none", "state": "none"}. Never answer it for him.')


def check_gear(value, offer):
    """{'item', 'in_use'} for the player's answer to a raised equipment clarification."""
    require(offer, 'No equipment question is open: omit gear.')
    require(isinstance(value, dict) and set(value) == {'item', 'state'} and value.get('state') in GEAR_STATES[:2],
            'gear is {item, state: held|stowed}, or {"item": "none", "state": "none"}')
    require(value['item'] in (offer.get('items') or ()), f"gear.item is one of {', '.join(offer.get('items') or ())}")
    return {'item': value['item'], 'in_use': value['state'] == 'held'}


SCHEMAS['gear'] = GEAR_SCHEMA
RULES['gear'] = GEAR_RULE


def check_flourish(value, offer):
    require(offer, 'No flourish window is open: omit flourish.')
    require(value in FLOURISH_READS, f'flourish must be one of {", ".join(FLOURISH_READS)}')
    return {'flourish': value}




def check_downed(value, offer):
    """{act, foes} for Kit's call on foes acting while the PC is down."""
    require(isinstance(value, dict) and set(value) == {'act'} and value.get('act') in DOWNED_ACTS,
            'downed is {"act": "attack"} or {"act": "turn_away"}')
    require(offer, 'Nobody is acting on a downed PC this turn: leave downed out.')
    return {'act': value['act'], 'foes': list(offer.get('foes') or ())}


FIELDS = {'handles': check_handles, 'react': check_react, 'flourish': check_flourish,
          'downed': check_downed, 'upcast': check_upcast, 'gear': check_gear}
# Offered, but Kit may leave it out (the player's reply may not answer it this turn).
OPTIONAL_FIELDS = ('gear',)


def check(plan, body):
    """Every act field the decision declares, validated against this turn's offers:
    {field: normalized} (only the declared ones). An offered field must be answered (a
    question to the player answers none of them and declares nothing)."""
    offers = (body or {}).get('acts') or {}
    asked = bool((plan or {}).get('ask_player'))
    out = {}
    for field, checker in FIELDS.items():
        if offers.get(field) and not asked and field not in OPTIONAL_FIELDS:
            require(field in (plan or {}),
                    f'acts.{field} is offered this turn: answer it'
                    + (' ({target, act}, or {"target": "none", "act": "none", "reason": ...} when his hands go on nothing '
                       'listed).' if field == 'handles' else ' ({"act": "attack"} or {"act": "turn_away"}).'))
        value = declared(plan, field)
        if value is None:
            if field == 'handles' and offers.get(field) and not asked and \
                    (plan or {}).get(field) not in (None,) and none_reason(plan) is None:
                require(False, 'acts.handles none needs a reason: {"target": "none", "act": "none", "reason": '
                               f'one of {", ".join(NONE_REASONS)}}}. If his hands go on a listed thing, '
                               'declare it instead.')
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
        elif field == 'gear' and offer:
            view['gear'] = {'items': list(offer.get('items') or ()), 'names': list(offer.get('names') or ()),
                            'rule': GEAR_RULE}
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
