"""Equipment audit (Brendon's ruling, 2026-10-19): the sheet against the gear in use.

Kit failed an intentional test: a wizard with no shield proficiency held a shield, took its
bonuses and cast freely, and nothing flagged it. The engine now checks the loaded sheet at
session start (the sheet is loaded) and after every rest, for any class or build:

* armor and shield proficiency against the armor worn and the shield held (class table,
  multiclass gains, armor feats and a sheet's own ``armor_proficiencies``);
* the attunement limit (3 items, SRD) and an item's "requires attunement by a ..." class.

Each mismatch becomes a pending clarification (``state['gear']['clarify']``). Kit raises it
once, in voice, at a natural moment (a substantive turn, never a window or table talk), as an
in-fiction question that states the rule as written. The player's answer is game state
(``gear_state``: "stows the shield", "keeps it on his arm").

While non-proficient armor or a non-proficient shield is in use the engine enforces the SRD:
disadvantage on any ability check, saving throw or attack roll that uses Strength or
Dexterity, and no spellcasting. Donning or doffing a shield costs the action in a fight, and
every swap costs its own action (no free drop-and-ready around each cast). An item's own
advantage (a shield that grants initiative or Perception advantage) applies only while it is
in use, and advantage and disadvantage on the same roll cancel (SRD).

Nothing here knows any particular character or item beyond the SRD tables below; a sheet can
describe any item itself as a dict: {name, type: shield|light|medium|heavy, equipped,
requires_attunement, attuned, attunement_by, advantage: [initiative|<skill>], ac_bonus}.
"""
import copy
import re

from .state_context import require

ATTUNEMENT_LIMIT = 3
CATEGORIES = ('light', 'medium', 'heavy', 'shield')
# SRD armor: (category, strength needed or None). Longest names first when matching.
ARMOR = {'padded armor': ('light', None), 'padded': ('light', None), 'leather armor': ('light', None),
         'studded leather': ('light', None), 'hide armor': ('medium', None), 'chain shirt': ('medium', None),
         'scale mail': ('medium', None), 'breastplate': ('medium', None), 'half plate': ('medium', None),
         'ring mail': ('heavy', None), 'chain mail': ('heavy', 13), 'splint armor': ('heavy', 15),
         'splint mail': ('heavy', 15), 'plate armor': ('heavy', 15), 'full plate': ('heavy', 15),
         'plate mail': ('heavy', 15)}
_ARMOR = re.compile(r'\b(' + '|'.join(re.escape(n) for n in sorted(ARMOR, key=len, reverse=True)) + r')\b')
_SHIELD = re.compile(r'\bshield\b')
# SRD class armor training: a first class, and what multiclassing into it adds.
CLASS_ARMOR = {'barbarian': {'light', 'medium', 'shield'}, 'bard': {'light'},
               'cleric': {'light', 'medium', 'shield'}, 'druid': {'light', 'medium', 'shield'},
               'fighter': {'light', 'medium', 'heavy', 'shield'}, 'monk': set(),
               'paladin': {'light', 'medium', 'heavy', 'shield'}, 'ranger': {'light', 'medium', 'shield'},
               'rogue': {'light'}, 'sorcerer': set(), 'warlock': {'light'}, 'wizard': set(),
               'artificer': {'light', 'medium', 'shield'}}
MULTICLASS_ARMOR = {'barbarian': {'shield'}, 'bard': {'light'}, 'cleric': {'light', 'medium', 'shield'},
                    'druid': {'light', 'medium', 'shield'}, 'fighter': {'light', 'medium', 'shield'},
                    'monk': set(), 'paladin': {'light', 'medium', 'shield'}, 'ranger': {'light', 'medium', 'shield'},
                    'rogue': {'light'}, 'sorcerer': set(), 'warlock': {'light'}, 'wizard': set(),
                    'artificer': {'light', 'medium', 'shield'}}
FEAT_ARMOR = {'lightly armored': {'light'}, 'moderately armored': {'medium', 'shield'},
              'heavily armored': {'heavy'}}
ANCESTRY_ARMOR = {'mountain dwarf': {'light', 'medium'}}
# Items the SRD or the published rules name, by what matters here. Anything else describes itself.
KNOWN_ITEMS = {
    'sentinel shield': {'type': 'shield', 'advantage': ['initiative', 'perception']},
    'animated shield': {'type': 'shield', 'requires_attunement': True},
    'arrow-catching shield': {'type': 'shield', 'requires_attunement': True},
    'spellguard shield': {'type': 'shield', 'requires_attunement': True},
    'shield of missile attraction': {'type': 'shield', 'requires_attunement': True},
    'amulet of health': {'requires_attunement': True}, 'bracers of defense': {'requires_attunement': True},
    'cloak of protection': {'requires_attunement': True}, 'ring of protection': {'requires_attunement': True},
    'cloak of displacement': {'requires_attunement': True}, 'cloak of elvenkind': {'requires_attunement': True},
    'boots of speed': {'requires_attunement': True}, 'boots of elvenkind': {'requires_attunement': False},
    'gauntlets of ogre power': {'requires_attunement': True}, 'headband of intellect': {'requires_attunement': True},
    'belt of giant strength': {'requires_attunement': True}, 'pearl of power': {'requires_attunement': True},
    'ring of evasion': {'requires_attunement': True}, 'ring of free action': {'requires_attunement': True},
    'ring of spell storing': {'requires_attunement': True}, 'periapt of wound closure': {'requires_attunement': True},
    'staff of power': {'requires_attunement': True, 'attunement_by': ['sorcerer', 'warlock', 'wizard']},
    'staff of the magi': {'requires_attunement': True, 'attunement_by': ['sorcerer', 'warlock', 'wizard']},
    'robe of the archmagi': {'requires_attunement': True, 'attunement_by': ['sorcerer', 'warlock', 'wizard']},
    'holy avenger': {'requires_attunement': True, 'attunement_by': ['paladin']},
    'wand of the war mage': {'requires_attunement': True, 'attunement_by': ['spellcaster']},
    'elven chain': {'type': 'medium', 'proficient_anyway': True},
}
GEAR_KEYS = ('armor', 'equipment', 'gear', 'magic_items', 'inventory', 'items')
SPELLCASTERS = ('bard', 'cleric', 'druid', 'paladin', 'ranger', 'sorcerer', 'warlock', 'wizard', 'artificer')
CATEGORY_WORDS = {'light': 'light armor', 'medium': 'medium armor', 'heavy': 'heavy armor', 'shield': 'shields'}

RULE_ARMOR = ('SRD: wearing armor you are not proficient with gives disadvantage on any ability check, saving '
              'throw or attack roll that uses Strength or Dexterity, and you cannot cast spells.')
RULE_SHIELD = ('SRD: holding a shield you are not proficient with gives disadvantage on any ability check, '
               'saving throw or attack roll that uses Strength or Dexterity, and you cannot cast spells. '
               'Readying or stowing a shield takes your action.')
RULE_ATTUNE = 'SRD: a creature can be attuned to no more than three magic items at a time.'
RULE_ATTUNE_BY = 'SRD: an item that requires attunement by a {who} can only be attuned by one.'
CLARIFY_RULE = (
    'Equipment clarification (gear_clarify): the engine found gear on the sheet that does not fit the rules. '
    'Raise it once, now, in your own voice, as an in-fiction clarifying question at a natural point in this '
    'turn: name the item, state the rule as written (gear_clarify.rule), and ask what the character does '
    '(gear_clarify.ask). Never decide it for the player; the engine records the answer.')


def ident(name):
    return re.sub(r'[^a-z0-9]+', '_', str(name or '').casefold()).strip('_')


def _norm(name):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\' -]+', ' ', str(name or '').casefold())).strip()


def classes(sheet):
    """The sheet's classes in order: 'Fighter 3 / Wizard 2', 'Cleric (Life)', 'Wizard'."""
    text = str((sheet or {}).get('class') or '').casefold()
    found = []
    for match in re.finditer(r'[a-z]+', re.sub(r'\([^)]*\)', ' ', text)):
        word = match.group(0)
        if word in CLASS_ARMOR and word not in found:
            found.append(word)
    return found


def proficiencies(sheet):
    """The armor categories (light, medium, heavy, shield) the sheet is trained in, or None when
    the sheet gives no way to tell (an unknown class and no explicit list): never guessed."""
    sheet = sheet or {}
    explicit = sheet.get('armor_proficiencies')
    if explicit is None and isinstance(sheet.get('proficiencies'), dict):
        explicit = sheet['proficiencies'].get('armor')
    out = set()
    if explicit is not None:
        for word in explicit if isinstance(explicit, (list, tuple)) else [explicit]:
            word = str(word).casefold()
            if 'all' in word:
                out |= {'light', 'medium', 'heavy'}
            out |= {cat for cat in CATEGORIES if cat in word}
        return out
    found = classes(sheet)
    if not found:
        return None
    out |= CLASS_ARMOR[found[0]]
    for extra in found[1:]:
        out |= MULTICLASS_ARMOR[extra]
    texts = [str(f.get('name') if isinstance(f, dict) else f).casefold()
             for f in list(sheet.get('features') or ()) + list(sheet.get('feats') or ())]
    for feat, cats in FEAT_ARMOR.items():
        if any(feat in text for text in texts):
            out |= cats
    ancestry = str(sheet.get('ancestry') or '').casefold()
    for name, cats in ANCESTRY_ARMOR.items():
        if name in ancestry:
            out |= cats
    return out


def items(sheet):
    """Every armor, shield or attunement item on the sheet:
    [{id, name, type (light|medium|heavy|shield|None), equipped, requires_attunement, attuned,
      attunement_by, advantage, ac_bonus, str_needed, proficient_anyway}]"""
    out, seen = [], set()
    for key in GEAR_KEYS:
        value = (sheet or {}).get(key)
        if isinstance(value, (str, dict)):
            value = [value]
        for entry in value or ():
            detail = dict(entry) if isinstance(entry, dict) else {'name': entry}
            name = str(detail.get('name') or '').strip()
            if not name or ident(name) in seen:
                continue
            folded = _norm(name)
            known = next((v for k, v in KNOWN_ITEMS.items() if k in folded), {})
            kind = detail.get('type') or detail.get('kind') or known.get('type')
            armor = _ARMOR.search(folded)
            if kind not in CATEGORIES:
                kind = 'shield' if _SHIELD.search(folded) else ARMOR[armor.group(1)][0] if armor else None
            needs = detail.get('requires_attunement', detail.get('attunement', known.get('requires_attunement', False)))
            if not kind and not needs:
                continue
            seen.add(ident(name))
            by = detail.get('attunement_by', known.get('attunement_by'))
            out.append({'id': ident(name), 'name': name, 'type': kind,
                        'equipped': detail.get('equipped', True) is not False,
                        'requires_attunement': bool(needs),
                        'attuned': bool(needs) and detail.get('attuned', True) is not False,
                        'attunement_by': [str(b).casefold() for b in (by if isinstance(by, list) else [by] if by else [])],
                        'advantage': [str(a).casefold() for a in detail.get('advantage', known.get('advantage', ()))],
                        'ac_bonus': int(detail.get('ac_bonus', 2 if kind == 'shield' else 0)),
                        'str_needed': ARMOR[armor.group(1)][1] if armor and kind == ARMOR[armor.group(1)][0] else None,
                        'proficient_anyway': bool(detail.get('proficient_anyway', known.get('proficient_anyway')))})
    return out


def _proficient(item, trained):
    return trained is None or item['proficient_anyway'] or item['type'] in trained


def audit(sheet):
    """The sheet's mismatches, for any build: [{id, item, issue, rule, ask}] (empty: nothing to ask)."""
    trained = proficiencies(sheet)
    found = []
    for item in items(sheet):
        if item['type'] and item['equipped'] and not _proficient(item, trained):
            shield = item['type'] == 'shield'
            found.append({'id': f"{'shield' if shield else 'armor'}_proficiency:{item['id']}", 'item': item['id'],
                          'name': item['name'], 'issue': 'shield_proficiency' if shield else 'armor_proficiency',
                          'rule': RULE_SHIELD if shield else RULE_ARMOR,
                          'ask': (f"Is the {item['name']} on your arm, or stowed? You are not trained with "
                                  f"{CATEGORY_WORDS[item['type']]}." if shield else
                                  f"Are you wearing the {item['name']}, or have you taken it off? You are not "
                                  f"trained with {CATEGORY_WORDS[item['type']]}.")})
    attuned = [item for item in items(sheet) if item['attuned']]
    who = classes(sheet)
    for item in attuned:
        if item['attunement_by'] and not any(b in who or (b == 'spellcaster' and any(c in SPELLCASTERS for c in who))
                                             for b in item['attunement_by']):
            label = ' or '.join(item['attunement_by'])
            found.append({'id': f"attunement_class:{item['id']}", 'item': item['id'], 'name': item['name'],
                          'issue': 'attunement_class', 'rule': RULE_ATTUNE_BY.format(who=label),
                          'ask': f"The {item['name']} only answers to a {label}. What is it doing for you now?"})
    if len(attuned) > ATTUNEMENT_LIMIT:
        names = ', '.join(item['name'] for item in attuned)
        found.append({'id': 'attunement_limit', 'item': None, 'name': names, 'issue': 'attunement_limit',
                      'rule': RULE_ATTUNE,
                      'ask': f'You are attuned to {len(attuned)} items ({names}); which three keep the bond?'})
    return found


# -- state: state['gear'] = {'in_use': {item id: bool}, 'clarify': [...], 'audits': n} ------------
def before_audit(sheet):
    """A copy of the sheet without the gear its audit flags, for fixtures and replays recorded
    before the audit existed. Only items the audit names are dropped; nothing is chosen by name."""
    flagged = {entry['item'] for entry in audit(sheet) if entry.get('item')}
    out = copy.deepcopy(sheet or {})
    for key in GEAR_KEYS:
        value = out.get(key)
        if isinstance(value, list):
            out[key] = [entry for entry in value
                        if ident(entry.get('name') if isinstance(entry, dict) else entry) not in flagged]
        elif value and ident(value.get('name') if isinstance(value, dict) else value) in flagged:
            out.pop(key)
    return out


def gear(state):
    return copy.deepcopy((state or {}).get('gear') or {'in_use': {}, 'clarify': [], 'audits': 0})


def run_audit(state, why):
    """Re-audit the loaded sheet into ``state`` (in place): a new mismatch is a pending
    clarification; one already raised or answered is never raised twice."""
    sheet = (state or {}).get('player_sheet')
    if not sheet:
        return state
    body = gear(state)
    known = {entry['id'] for entry in body['clarify']}
    for issue in audit(_with_use(sheet, body)):
        if issue['id'] not in known:
            body['clarify'].append({**issue, 'status': 'pending', 'found': why})
    body['clarify'] = body['clarify'][-12:]
    body['audits'] = int(body.get('audits') or 0) + 1
    state['gear'] = body
    return state


def _with_use(sheet, body):
    """The sheet with each item's recorded in-use state as its ``equipped`` flag."""
    sheet = copy.deepcopy(sheet)
    recorded = body.get('in_use') or {}
    for key in GEAR_KEYS:
        value = sheet.get(key)
        if isinstance(value, (str, dict)):
            value = [value]
            sheet[key] = value
        for index, entry in enumerate(value or ()):
            name = entry.get('name') if isinstance(entry, dict) else entry
            if ident(name) in recorded:
                detail = dict(entry) if isinstance(entry, dict) else {'name': entry}
                detail['equipped'] = bool(recorded[ident(name)])
                value[index] = detail
    return sheet


def in_use(state, item, fight=None):
    """Is this armor worn / shield held now? The player's recorded word, else the sheet (an item
    listed is in use unless it says equipped false), except a shield at a card table (seated)."""
    recorded = ((state or {}).get('gear') or {}).get('in_use') or {}
    if item['id'] in recorded:
        return bool(recorded[item['id']])
    if not item['equipped']:
        return False
    if item['type'] == 'shield' and not fight and (state or {}).get('procedures'):
        return False  # seated at cards: a shield is set aside (pc_sheet situation 'seated')
    return True


def stowed_names(state):
    """Names of sheet items the player has recorded as not in use (pc_sheet drops them from held)."""
    sheet = (state or {}).get('player_sheet') or {}
    recorded = ((state or {}).get('gear') or {}).get('in_use') or {}
    return [item['name'] for item in items(sheet) if recorded.get(item['id']) is False]


def penalties(state, fight=None):
    """{'gear': [names], 'no_casting': bool, 'str_dex_disadvantage': bool}: non-proficient armor or
    shield in use now (SRD), for any sheet."""
    sheet = (state or {}).get('player_sheet') or {}
    trained = proficiencies(sheet)
    names = [item['name'] for item in items(sheet)
             if item['type'] and in_use(state, item, fight) and not _proficient(item, trained)]
    return {'gear': names, 'no_casting': bool(names), 'str_dex_disadvantage': bool(names)}


def why(state, fight=None):
    """'the Sentinel Shield you are not proficient with', or '' when nothing applies."""
    names = penalties(state, fight)['gear']
    if not names:
        return ''
    return f"the {' and the '.join(names)} you are not proficient with"


def advantage_from(state, what, fight=None):
    """Names of in-use items whose own text grants advantage on ``what`` (initiative, a skill)."""
    sheet = (state or {}).get('player_sheet') or {}
    return [item['name'] for item in items(sheet) if what in item['advantage'] and in_use(state, item, fight)]


def roll_mode(state, ability, what=None, fight=None):
    """('advantage'|'disadvantage'|'normal', reason) for a PC roll using ``ability`` (str/dex/...),
    and ``what`` (initiative, a skill) for an item's own advantage. Both apply: they cancel (SRD)."""
    disadvantage = ability in ('str', 'dex') and penalties(state, fight)['str_dex_disadvantage']
    advantage = advantage_from(state, what, fight) if what else []
    if advantage and disadvantage:
        return 'normal', (f"advantage from the {' and '.join(advantage)} and disadvantage from "
                          f"{why(state, fight)} cancel out")
    if advantage:
        return 'advantage', f"the {' and '.join(advantage)}"
    if disadvantage:
        return 'disadvantage', why(state, fight)
    return 'normal', ''


def initiative_prompt(state):
    """'Roll initiative.' with the mode the gear in use sets (a Dexterity check)."""
    mode, reason = roll_mode(state, 'dex', 'initiative', fight=True)
    if mode == 'normal' and not reason:
        return 'Roll initiative.'
    if mode == 'normal':
        return f'Roll initiative, a straight roll: {reason}.'
    return f'Roll initiative with {mode} ({reason}).'


def shield_ac(state, fight=None):
    """The AC the sheet's shields add that is not in use now (the sheet's AC counts its listed
    shield): subtract it. 0 when every listed shield is in use."""
    sheet = (state or {}).get('player_sheet') or {}
    return sum(item['ac_bonus'] for item in items(sheet)
               if item['type'] == 'shield' and item['equipped'] and not in_use(state, item, fight))


# -- swaps and answers -------------------------------------------------------------------
_OFF = (r"stow|stows|sling|slings|put away|puts away|set aside|sets aside|set down|sets down|drop|drops|"
        r"doff|doffs|take off|takes off|unstrap|unstraps|remove|removes|lower|lowers|shrug off|shrugs off|"
        r"hang|hangs|strap\s+\w+\s+(?:to|on)\s+my\s+back")
_ON = r"ready|readies|don|dons|put on|puts on|strap on|straps on|take up|takes up|pick up|picks up|grab|grabs|wield|wields|hold up|heft|hefts"


def read_swap(text, state):
    """{'item', 'name', 'in_use'} when the player readies or stows a listed armor or shield in so
    many words ('I stow my shield', 'I ready the Sentinel Shield'), else None. A question, or
    the Shield spell ('I cast Shield', 'I raise a shield'), is never a swap."""
    sheet = (state or {}).get('player_sheet') or {}
    words = _norm(text)
    if '?' in str(text) or re.search(r'\bcast\w*\s+(?:a\s+|the\s+|my\s+)?shield\b|\braises?\s+(?:a\s+|my\s+)?shield\b',
                                     words) or re.search(r'!cast\s+shield\b', str(text).casefold()):
        return None  # the Shield spell, or a question
    for item in items(sheet):
        if not item['type']:
            continue
        nouns = [re.escape(_norm(item['name']))]
        nouns.append(r'(?:my|the|his|her|that)\s+shield' if item['type'] == 'shield' else
                     r'(?:my|the|his|her)\s+(?:armor|armour|' + re.escape(_norm(item['name'])) + ')')
        noun = '(?:' + '|'.join(nouns) + ')'
        for verbs, use in ((_OFF, False), (_ON, True)):
            if re.search(r'\b(?:' + verbs + r')\b(?:\s+\w+){0,3}?\s+' + noun + r'\b', words) or \
                    re.search(r'\b' + noun + r'\s+(?:\w+\s+){0,2}?(?:' + ('off|away|aside|down' if not use else 'on|up') + r')\b',
                              words) and re.search(r'\b(?:' + verbs + r'|put|puts|take|takes|strap|straps)\b', words):
                return {'item': item['id'], 'name': item['name'], 'in_use': use, 'type': item['type']}
    return None


def change_event(state, item, in_use_now, why_text, answer=None):
    """The gear_state event: the item's in-use state, and the clarification it answers."""
    return {'type': 'gear_state', 'item': item, 'in_use': bool(in_use_now),
            **({'answers': answer} if answer else {}), 'evidence': why_text[:300]}


def raised_event(clarification_id, turn_id):
    return {'type': 'gear_state', 'raised': clarification_id, 'turn': str(turn_id),
            'evidence': f'Kit raised the equipment clarification {clarification_id} in voice.'}


def apply_event(state, event):
    """state['gear'] after a gear_state event (an item's use, a clarification raised or answered)."""
    body = gear(state)
    sheet = state.get('player_sheet') or {}
    if 'item' in event:
        known = {item['id'] for item in items(sheet)}
        require(event['item'] in known, f"gear_state names an item not on the sheet: {event['item']}")
        body['in_use'][event['item']] = bool(event.get('in_use'))
        for entry in body['clarify']:
            if entry.get('item') == event['item'] and entry['status'] != 'answered':
                entry.update(status='answered', answer='in use' if event.get('in_use') else 'stowed')
    if event.get('answers'):
        for entry in body['clarify']:
            if entry['id'] == event['answers']:
                entry.update(status='answered', answer=entry.get('answer') or str(event.get('evidence'))[:120])
    if event.get('raised'):
        entry = next((e for e in body['clarify'] if e['id'] == event['raised']), None)
        require(entry is not None, 'gear_state raises a clarification that is not pending')
        if entry['status'] == 'pending':
            entry.update(status='raised', raised_turn=str(event.get('turn') or ''))
    state['gear'] = body
    return state


def pending(state):
    """The next clarification to raise, or None."""
    return next((e for e in gear(state)['clarify'] if e['status'] == 'pending'), None)


def raised(state):
    """Clarifications Kit raised that the player has not answered yet."""
    return [e for e in gear(state)['clarify'] if e['status'] == 'raised']


def clarify_view(entry):
    """What Kit sees for the one clarification to raise this turn."""
    return {'id': entry['id'], 'item': entry['name'], 'issue': entry['issue'], 'rule': entry['rule'],
            'ask': entry['ask'], 'how': CLARIFY_RULE}


def answer_offer(state):
    """The ``gear`` act offer while a raised clarification waits on the player's answer."""
    open_ = [e for e in raised(state) if e.get('item')]
    if not open_:
        return None
    return {'items': [e['item'] for e in open_], 'names': [e['name'] for e in open_]}


def check_spoken_clarify(entry, segments):
    """Kit raised it: the item named (attunement: the bond named) and a question asked, in this
    turn's performance. ``entry`` is the clarify_view Kit was given."""
    text = ' '.join(str(s.get('text') or '') for s in segments or ())
    folded = text.casefold()
    name = str(entry.get('item') or '')
    if entry.get('issue') == 'attunement_limit':
        named = 'attun' in folded or 'bond' in folded
    else:
        words = [w for w in re.findall(r"[a-z]+", name.casefold()) if len(w) > 3]
        named = any(w in folded for w in words)
    require(named and '?' in text,
            f"gear_clarify is due this turn: ask about the {name} in your own voice, as an in-fiction "
            f"question that names it and states the rule ({entry['rule']}). For example: {entry['ask']}")
