"""Kit-declared combat acts (Brendon's decision, 2026-10-13): the word-matching combat parser
ends. Kit reads the player's message and declares a structured list, one entry per clause,
in the order he said them; the engine validates each against the rules and the fight
(reach, action economy, legality, slots), commits the legal ones and refuses the rest with
a reason Kit can voice. It never guesses and never drops an entry silently; a missing roll
is an Avrae ask. The same split as #97's ``handles`` (runtime/kit_acts.py): Kit reads the
English, the engine owns the rules.

An entry::

    {"kind": "attack", "target": "ogre", "weapon": "rapier", "roll": "16 to hit, 5 piercing",
     "distance_ft": null, "order": 1, "says": "I stab the ogre"}

``kind`` is one of KINDS. ``target`` is an actor id from the offer (or null). ``weapon`` is
on the sheet; ``spell`` is a spell on the sheet; ``reaction`` a reaction id from the sheet's
inventory. ``roll`` is the player's stated roll or his Avrae paste, verbatim (null when he
gave none). ``distance_ft`` is for move. ``order`` is the clause's place in his message.
"""
import re

from . import kit_reactions
from .state_context import require

KINDS = ('attack', 'bonus_attack', 'spell', 'move', 'reaction', 'dodge', 'dash', 'disengage', 'hide',
         'help', 'grapple', 'shove', 'object')
STANDARD = ('dodge', 'dash', 'disengage', 'hide', 'help')
MOVE_WAYS = ('away', 'toward')
ENTRY_SCHEMA = {'type': 'object', 'additionalProperties': False,
                'properties': {'kind': {'type': 'string', 'enum': list(KINDS)},
                               'target': {'type': ['string', 'null']},
                               'weapon': {'type': ['string', 'null']},
                               'spell': {'type': ['string', 'null']},
                               'reaction': {'type': ['string', 'null']},
                               'roll': {'type': ['string', 'null']},
                               'distance_ft': {'type': ['integer', 'null']},
                               'way': {'type': ['string', 'null'], 'enum': list(MOVE_WAYS) + [None]},
                               'order': {'type': 'integer'},
                               'says': {'type': ['string', 'null']}},
                'required': ['kind', 'order']}
SCHEMA = {'type': 'array', 'items': ENTRY_SCHEMA, 'maxItems': 8}
RULE = ('combat_acts: one entry per thing the player does this turn, in his order (order 1, 2, ...): '
        'kind (' + ', '.join(KINDS) + '), target (an offered actor id), weapon (on his sheet) or spell '
        '(on his sheet) or reaction (an offered reaction id), roll (his stated roll or Avrae paste, '
        'verbatim; null if none), distance_ft and way (away|toward) for a move, says (his words for it). '
        'Declare what he said, not what would be wise; the engine refuses what the rules do not allow, '
        'and asks for a missing roll.')


def sheet_names(state):
    """What the sheet lets him use: weapons (gear and weapons), spells (cantrips and leveled)."""
    sheet = (state or {}).get('player_sheet') or {}
    weapons = {'unarmed strike'}
    for item in list(sheet.get('weapons') or ()) + list(sheet.get('gear') or ()):
        name = item.get('name') if isinstance(item, dict) else item
        if name:
            weapons.add(str(name).casefold())
    spells = {e['name'].casefold() for e in kit_reactions.spells(sheet).values()}
    raw = sheet.get('spells') or {}
    if isinstance(raw, dict):
        for level, names in raw.items():
            if str(level).casefold() in ('cantrips', 'cantrip', '0'):
                spells |= {str(n.get('name') if isinstance(n, dict) else n).casefold() for n in names or ()}
    return weapons, spells


def offer(source, state):
    """What Kit may declare this turn: the actor ids in the fight, the sheet's weapons, spells
    and reactions. None outside a running fight."""
    from . import kit_combat
    fight = (state or {}).get('combat') or {}
    if fight.get('status') not in ('awaiting_initiative', 'running') or not kit_combat.config(source):
        return None
    weapons, spells = sheet_names(state)
    reactions = [r['id'] for r in (kit_reactions.current(state).get('reactions') or ())]
    return {'targets': sorted(kit_combat.present(source, state)), 'weapons': sorted(weapons),
            'spells': sorted(spells), 'reactions': reactions}


def check(value, offered):
    """The declared list, shape-checked against the offer: [entry] in order. Raises
    InvalidChange (require) for what Kit can fix: an unknown kind, an id not offered, a duplicate
    order. Rules legality (reach, economy, slots) is the engine's, at resolve, and is voiced."""
    require(offered, 'No fight is running: omit combat_acts.')
    require(isinstance(value, list) and 1 <= len(value) <= 8, 'combat_acts is a list of 1-8 entries')
    seen = set()
    out = []
    for entry in value:
        require(isinstance(entry, dict) and set(entry) <= set(ENTRY_SCHEMA['properties']) and
                entry.get('kind') in KINDS and type(entry.get('order')) is int,
                f'each combat_acts entry is {{kind, order, ...}} with kind one of {", ".join(KINDS)}')
        require(entry['order'] not in seen, 'combat_acts order values are unique')
        seen.add(entry['order'])
        target = entry.get('target')
        require(target in (None, 'none') or target in offered['targets'],
                f'combat_acts target must be one of {offered["targets"]} or null')
        reaction = entry.get('reaction')
        require(entry['kind'] != 'reaction' or reaction, 'a reaction entry names its reaction id')
        if entry.get('roll') is not None:
            require(isinstance(entry['roll'], str) and len(entry['roll']) <= 2000, 'roll is the stated text')
        if entry.get('distance_ft') is not None:
            require(type(entry['distance_ft']) is int and 0 <= entry['distance_ft'] <= 200, 'distance_ft is 0-200')
        out.append({k: v for k, v in entry.items() if v is not None and v != 'none'})
    return sorted(out, key=lambda e: e['order'])


def _label(entry, labels):
    if entry.get('says'):
        words = re.sub(r'^\s*(?:and|then|so)\s+', '', entry['says'].strip(' .,;'), flags=re.I)
        return f'"{words[:1].upper() + words[1:]}"'
    who = labels.get(entry.get('target'), entry.get('target'))
    what = entry.get('weapon') or entry.get('spell') or entry.get('reaction') or entry['kind'].replace('_', ' ')
    return f'The {what}' + (f' at the {str(who).lower()}' if who else '')


def to_act(entries, source, state):
    """The engine's multi act for the declared entries (kit_combat.Fight.run_clauses): every
    entry a step, in order. Nothing is guessed: a value the sheet or the fight does not have
    becomes a refusal the engine voices."""
    from . import kit_combat
    labels = kit_combat.labels(source)
    weapons, spells = sheet_names(state)
    reactions = {r['id']: r for r in (kit_reactions.current(state).get('reactions') or ())}
    steps = []
    for entry in entries:
        kind, target = entry['kind'], entry.get('target')
        text = entry.get('roll') or ''
        act = None
        refuse = None
        if kind in ('attack', 'bonus_attack'):
            weapon = str(entry.get('weapon') or 'unarmed strike').casefold()
            listed = weapons - {'unarmed strike'}
            if listed and weapon != 'unarmed strike' and not any(weapon == w or weapon in w for w in listed):
                # A sheet that lists no gear says nothing either way: the weapon stands.
                refuse = f'there is no {weapon} on your sheet'
            else:
                act = {'kind': 'attack', 'weapon': weapon, 'target': target, 'area': False,
                       'unarmed': weapon == 'unarmed strike', 'thrown': kit_combat.sheet_thrown(state, weapon),
                       'declared_bonus': kind == 'bonus_attack'}
        elif kind == 'spell':
            spell = str(entry.get('spell') or '').casefold()
            if spell not in spells:
                refuse = f'{spell.title() or "that spell"} is not on your sheet'
            else:
                area = spell in kit_combat.SPELL_SAVE and kit_combat.SPELL_SAVE[spell][2]
                act = {'kind': 'attack', 'spell': spell, 'weapon': spell, 'area': bool(area),
                       'target': None if area else target}
        elif kind == 'move':
            if entry.get('way') == 'toward' or (target and entry.get('way') != 'away'):
                act = {'kind': 'approach', 'target': target}
            else:
                act = {'kind': 'withdraw', 'target': None, 'disengage': False}
        elif kind == 'disengage':
            act = {'kind': 'withdraw', 'target': None, 'disengage': True, 'standard': 'disengage'}
        elif kind == 'reaction':
            key = entry.get('reaction')
            if key not in reactions:
                act = {'kind': 'missing_reaction', 'target': None, 'name': str(key).replace('_', ' ').title()}
            elif key == 'shield':
                act = {'kind': 'own_shield', 'target': None, 'avrae': '!cast' in text.casefold()}
            else:
                found = reactions[key]
                names = sorted({found.get('name', '').casefold(), key.replace('_', ' ')} - {''}, key=len, reverse=True)
                events = [e for e in ((state.get('combat') or {}).get('unprompted') or ()) if key in e['options']]
                event = next((e for e in events if e.get('attacker') == target), events[0] if events else None)
                act = {'kind': 'late_reaction', 'target': (event or {}).get('attacker', target), 'react': key,
                       'event': event, 'names': names, 'avrae': bool(re.search(r'!cast|\bcasts\b', text, re.I))}
                text = text or ' '.join(names)
        elif kind == 'grapple':
            act = {'kind': 'grab', 'target': target, 'contest': True, 'teeth': False, 'wrist': False}
        elif kind in ('dodge', 'dash', 'hide', 'help'):
            act = {'kind': 'standard', 'standard': kind, 'target': target}
        elif kind == 'shove':
            refuse = 'shoving is the DM\'s call for now: say how you go about it'
        elif kind == 'object':
            refuse = "that's my call, not the fight's: tell me how you go about it and I'll rule on it"
        if act is None:
            act = {'kind': 'refused', 'target': target, 'because': refuse}
        act['declared'] = True
        steps.append({'start': 0, 'end': len(text), 'act': act, 'block': False, 'bound': target,
                      'text': text, 'label': _label(entry, labels)})
    first = next((s['act'] for s in steps if s['act'].get('target')), steps[0]['act'] if steps else {})
    return {'kind': 'multi', 'target': first.get('target'), 'steps': steps, 'declared': True}
