"""Room traps and hazards: the trigger schema's trap form (runtime/kit_triggers.py fires
creatures; a trap fires an effect). Data only, in the room's ``traps`` list:

    {"id": "lid_pit",
     "on": {"step": "<area>"} | {"enter": "<area>"} | {"disturb": "<fact>"} | {"open": "<fact>"},
     "feature": "<hidden fact id>",              # what the trap is (revealed when found or sprung)
     "effect": {"save": "dex" | "check": "athletics",   # optional: no roll means it just lands
                "dc": <n> | null,                # the source's DC only; null + "needs_dc": true flags it
                "damage": [{"dice": "3d6", "type": "bludgeoning"}],
                "attack": {"to_hit": <n>},       # optional: the trap attacks first (the source's bonus)
                "condition": "<text>",           # optional
                "half_on_success": true},
     "needs_dc": true,                           # only with dc null: the engine will not roll it
     "detect": {"skill": "perception", "dc": <n>},
     "disarm": [{"method": "thieves_tools", "dc": <n>}       # tools: Dexterity with thieves' tools
                | {"method": "sleight_of_hand", "dc": <n>}   # delicate hand work, no tools
                | {"method": "break", "object": {"material", "size", "resilient"}}   # no tools: SRD object AC/HP
                | {"method": "jam", "with": "<what the source says stops it>"}],
     "reset": "once" | "auto" | "manual",
     "reveal": "<public line when it goes off>", "spotted": "<public line when the PC notices it>"}

Disarming follows Brendon's ruling: delicate hand work can be Sleight of Hand; tools are
thieves' tools; with no tools the trap is broken as an object (SRD 5.1 object Armor Class
by material, hit points by size and fragile or resilient).

Running it: entering or stepping into its area, or disturbing or opening its feature, sets
it off unless it was found first (passive Perception against ``detect.dc`` on arrival, or
found by play) or disarmed. A save or check is the player's roll in Avrae through a
``roll_call`` interstitial (the engine never shows the DC); the next input carrying that
roll resolves it: the source's damage (its dice's average, the number the source prints),
half on a success where it says so. ``reset``: ``once`` and ``manual`` stay spent, ``auto``
re-arms.
"""
import re

from .state_context import InvalidChange, require

KINDS = ('step', 'enter', 'disturb', 'open')
ABILITIES = ('str', 'dex', 'con', 'int', 'wis', 'cha')
FIELDS = {'id', 'on', 'feature', 'effect', 'needs_dc', 'detect', 'disarm', 'reset', 'reveal', 'spotted'}
EFFECT_FIELDS = {'save', 'check', 'dc', 'damage', 'attack', 'condition', 'half_on_success'}
METHODS = ('thieves_tools', 'sleight_of_hand', 'break', 'jam', 'spell')
RESETS = ('once', 'auto', 'manual')
DICE = re.compile(r'^(\d+)d(\d+)(?:([+-])(\d+))?$')
# SRD 5.1 "Objects": Armor Class by substance, hit points by size (fragile / resilient).
OBJECT_AC = {'cloth': 11, 'paper': 11, 'rope': 11, 'crystal': 13, 'glass': 13, 'ice': 13, 'wood': 15, 'bone': 15,
             'stone': 17, 'iron': 19, 'steel': 19, 'mithral': 21, 'adamantine': 23}
OBJECT_HP = {'tiny': (2, 5), 'small': (3, 10), 'medium': (4, 18), 'large': (5, 27)}
OPEN_WORDS = re.compile(r'\b(open|opens|opening|lift|lifts|raise|raises|pry|pries|unlock|unlocks|pull|pulls|lever)\b', re.I)
DISARM_WORDS = re.compile(r'\b(disarm|disable|jam|jams|spike|spikes|wedge|wedges|block|break|smash|deactivate)\b', re.I)


def average(dice):
    m = DICE.match(str(dice).replace(' ', '').lower())
    if not m:
        return None
    n, size = int(m.group(1)), int(m.group(2))
    bonus = int(m.group(4) or 0) * (-1 if m.group(3) == '-' else 1)
    return n * (size + 1) // 2 + bonus


def object_stats(spec):
    """(AC, hit points) for an object by the SRD table."""
    return OBJECT_AC[spec['material']], OBJECT_HP[spec['size']][1 if spec.get('resilient') else 0]


def trap_problems(source):
    """Every problem in the room's ``traps`` list (empty when it is sound)."""
    from . import pc_sheet
    traps = source.get('traps')
    if traps is None:
        return []
    if not isinstance(traps, list):
        return ['traps must be a list']
    problems, seen = [], set()
    facts, areas = source.get('facts') or {}, source.get('areas') or {}
    for i, trap in enumerate(traps):
        if not isinstance(trap, dict):
            problems.append(f'trap {i}: each trap is an object')
            continue
        tid = trap.get('id')
        if not (isinstance(tid, str) and tid.strip()) or tid in seen:
            problems.append(f'trap {i}: needs a unique id')
        seen.add(tid)
        extra = set(trap) - FIELDS - {k for k in trap if str(k).startswith('_')}
        if extra:
            problems.append(f'trap {tid}: unknown fields {sorted(extra)}')
        on = trap.get('on')
        if not (isinstance(on, dict) and len(on) == 1 and next(iter(on)) in KINDS):
            problems.append(f'trap {tid}: on is one of {{"step"|"enter": area}} or {{"disturb"|"open": fact}}')
        else:
            kind, target = next(iter(on.items()))
            if kind in ('step', 'enter') and target not in areas:
                problems.append(f'trap {tid}: unknown area {target!r}')
            if kind in ('disturb', 'open') and not (isinstance(facts.get(target), dict) and facts[target].get('handling')):
                problems.append(f'trap {tid}: {kind} needs a fact with handling (got {target!r})')
        if trap.get('feature') is not None and trap['feature'] not in facts:
            problems.append(f'trap {tid}: feature {trap["feature"]!r} is not a fact')
        effect = trap.get('effect')
        if not isinstance(effect, dict):
            problems.append(f'trap {tid}: needs an effect')
        else:
            if set(effect) - EFFECT_FIELDS:
                problems.append(f'trap {tid}: unknown effect fields {sorted(set(effect) - EFFECT_FIELDS)}')
            if 'save' in effect and 'check' in effect:
                problems.append(f'trap {tid}: effect is a save or a check, not both')
            if 'save' in effect and effect['save'] not in ABILITIES:
                problems.append(f'trap {tid}: save is one of {", ".join(ABILITIES)}')
            if 'check' in effect and effect['check'] not in pc_sheet.SKILLS:
                problems.append(f'trap {tid}: check {effect["check"]!r} is not a skill')
            rolled = 'save' in effect or 'check' in effect
            if rolled and effect.get('dc') is None and trap.get('needs_dc') is not True:
                problems.append(f'trap {tid}: a save or check needs the source\'s dc, or "dc": null with '
                                '"needs_dc": true when the source gives none (never invent one)')
            if effect.get('dc') is not None and type(effect['dc']) is not int:
                problems.append(f'trap {tid}: dc is a number or null')
            damage = effect.get('damage')
            if not (isinstance(damage, list) and damage and all(
                    isinstance(d, dict) and average(d.get('dice')) is not None and isinstance(d.get('type'), str)
                    for d in damage)):
                problems.append(f'trap {tid}: damage is a list of {{"dice": "XdY[+Z]", "type"}}')
            attack = effect.get('attack')
            if attack is not None and not (isinstance(attack, dict) and type(attack.get('to_hit')) is int):
                problems.append(f'trap {tid}: attack is {{"to_hit": n}}')
            if effect.get('half_on_success') and not rolled:
                problems.append(f'trap {tid}: half_on_success needs a save or check')
        detect = trap.get('detect')
        if detect is not None and not (isinstance(detect, dict) and detect.get('skill') in pc_sheet.SKILLS and
                                       (detect.get('dc') is None or type(detect.get('dc')) is int)):
            problems.append(f'trap {tid}: detect is {{"skill", "dc"}}')
        for way in trap.get('disarm') or ():
            method = way.get('method') if isinstance(way, dict) else None
            if method not in METHODS:
                problems.append(f'trap {tid}: disarm method is one of {", ".join(METHODS)}')
            elif method in ('thieves_tools', 'sleight_of_hand') and not (way.get('dc') is None or type(way['dc']) is int):
                problems.append(f'trap {tid}: disarm dc is a number or null')
            elif method == 'break':
                spec = way.get('object')
                if not (isinstance(spec, dict) and spec.get('material') in OBJECT_AC and spec.get('size') in OBJECT_HP):
                    problems.append(f'trap {tid}: break needs object {{material ({", ".join(OBJECT_AC)}), size '
                                    f'({", ".join(OBJECT_HP)}), resilient}} (SRD object AC and hit points)')
        if trap.get('reset', 'once') not in RESETS:
            problems.append(f'trap {tid}: reset is one of {", ".join(RESETS)}')
        for field in ('reveal', 'spotted'):
            text = trap.get(field)
            if text is not None and not (isinstance(text, str) and 0 < len(text) <= 300):
                problems.append(f'trap {tid}: {field} is one public line (up to 300 characters)')
    return problems


def compile_traps(source):
    problems = trap_problems(source)
    require(not problems, '; '.join(problems))
    return source.get('traps') or []


def status(state, tid):
    return ((state.get('traps') or {}).get(tid) or {}).get('status', 'armed')


def apply_event(state, source, event):
    tid = event.get('trap')
    trap = next((t for t in (source.get('traps') or []) if t.get('id') == tid), None)
    require(trap is not None, 'Unknown trap')
    new = event.get('status')
    require(new in ('armed', 'found', 'sprung', 'disarmed', 'spent'), 'Unknown trap status')
    entry = state.setdefault('traps', {}).setdefault(tid, {'status': 'armed'})
    entry['status'] = new
    if type(event.get('dealt')) is int:
        entry['dealt'] = entry.get('dealt', 0) + event['dealt']
        state['hazard_damage'] = state.get('hazard_damage', 0) + event['dealt']
    if event.get('awaiting'):
        state['trap_save'] = {'trap': tid, **{k: event['awaiting'][k] for k in ('save', 'check') if k in event['awaiting']}}
    elif 'trap_save' in state and state['trap_save'].get('trap') == tid:
        state.pop('trap_save')
    feature = trap.get('feature')
    went_off = new in ('found', 'sprung') or 'dealt' in event   # an auto-reset trap re-arms, but it was felt
    if feature and went_off and feature not in state.get('known_facts', []):
        state.setdefault('known_facts', []).append(feature)


def _fires(trap, source, state, result, action):
    from . import kit_triggers
    kind, target = next(iter(trap['on'].items()))
    if kind in ('step', 'enter'):
        return kit_triggers.arrived(source, state, result) == target
    if kit_triggers.disturbed(source, state, result, action) != target:
        return False
    return kind == 'disturb' or bool(OPEN_WORDS.search(action or ''))


def matching(source, state, result, action):
    for trap in source.get('traps') or ():
        if status(state, trap['id']) in ('armed', 'found') and _fires(trap, source, state, result, action):
            if status(state, trap['id']) == 'found' and next(iter(trap['on'])) in ('step', 'enter'):
                continue  # spotted: the PC steps around it
            return trap
    return None


def prompt(effect):
    from .kit_combat import save_prompt
    if 'save' in effect:
        return save_prompt({'save': effect['save']})
    return f"Make a {effect['check'].replace('_', ' ').title()} check."


def spring(trap, passive=None):
    """(public line, events, awaiting?) when the trap goes off (or is spotted first)."""
    detect = trap.get('detect') or {}
    kind = next(iter(trap['on']))
    if kind in ('step', 'enter') and passive is not None and type(detect.get('dc')) is int and passive >= detect['dc']:
        line = trap.get('spotted') or 'You notice something wrong ahead and stop short.'
        return line, [{'type': 'trap_state', 'trap': trap['id'], 'status': 'found',
                       'evidence': f'Passive Perception {passive} vs detect DC {detect["dc"]}: spotted.'}], False
    effect = trap['effect']
    reveal = trap.get('reveal') or 'Something gives way.'
    if 'save' in effect or 'check' in effect:
        require(effect.get('dc') is not None, 'This trap needs a DC ruling (needs_dc): no DC was invented')
        waiting = {'kind': 'roll_call', 'awaits': 'player_roll', 'trigger': f"trap:{trap['id']}",
                   **{k: effect[k] for k in ('save', 'check') if k in effect}}
        return f'{reveal} {prompt(effect)}', [{'type': 'trap_state', 'trap': trap['id'], 'status': 'sprung',
                                               'awaiting': waiting,
                                               'evidence': f'Trap {trap["id"]} sprung; the player rolls.'}], True
    dealt, line = land(trap, saved=False)
    return f'{reveal} {line}', [{'type': 'trap_state', 'trap': trap['id'], 'status': after_status(trap),
                                 'dealt': dealt, 'evidence': f'Trap {trap["id"]} sprung: {dealt} damage.'}], False


def after_status(trap):
    return 'armed' if trap.get('reset') == 'auto' else 'spent'


def land(trap, saved):
    effect = trap['effect']
    parts = [(average(d['dice']), d['type']) for d in effect['damage']]
    if saved:
        parts = [(n // 2, t) for n, t in parts] if effect.get('half_on_success') else []
    dealt = sum(n for n, _ in parts)
    if not dealt:
        return 0, 'You avoid the worst of it and take no damage.'
    detail = ' and '.join(f'{n} {t}' for n, t in parts if n)
    tail = f" You are {effect['condition']}." if effect.get('condition') and not saved else ''
    return dealt, f'You take {dealt} damage ({detail}).{tail}'


def resume(source, state, action):
    """The player's roll answering a trap's roll call: (public line, events), or None when the
    input carries no roll (the caller holds it)."""
    from .kit_combat import save_total
    from . import kit_rolls
    waiting = state.get('trap_save') or {}
    trap = next((t for t in source.get('traps') or () if t.get('id') == waiting.get('trap')), None)
    if trap is None:
        return None
    effect = trap['effect']
    if 'save' in effect:
        total = save_total(action, effect['save'])
    else:
        found = [r for r in kit_rolls.rolls(action or '')] if action else []
        total = found[0].total if found else None
        if total is None:
            bare = re.match(r'^\s*(\d{1,2})\s*$', action or '')
            total = int(bare.group(1)) if bare else None
    if total is None:
        return None
    saved = total >= int(effect['dc'])
    dealt, line = land(trap, saved)
    return line, [{'type': 'trap_state', 'trap': trap['id'], 'status': after_status(trap), 'dealt': dealt,
                   'evidence': f"Player rolled {total} vs DC {effect['dc']}: {'success' if saved else 'failure'}, "
                               f'{dealt} damage.'}]


def handoff_trace(trap):
    return {'type': 'trap', 'trap': trap['id'], 'on': dict(trap['on'])}


def disarm_attempt(source, state, action):
    """(trap, method) when the action works on a known trap ('I hammer spikes into the lid',
    'I disarm it with thieves' tools'), else None."""
    if not DISARM_WORDS.search(action or ''):
        return None
    text = (action or '').lower()
    for trap in source.get('traps') or ():
        if status(state, trap['id']) not in ('found', 'armed'):
            continue
        if status(state, trap['id']) == 'armed' and trap.get('feature') not in state.get('known_facts', []):
            continue  # nobody knows it is there
        target = next(iter(trap['on'].values()))
        nouns = set()
        for key in (trap.get('feature'), target):
            nouns |= set(((source.get('facts') or {}).get(key) or {}).get('handling', {}).get('nouns') or ())
        if not ('trap' in text or any(re.search(rf'\b{re.escape(n)}\b', text) for n in nouns)):
            continue
        ways = {w.get('method'): w for w in trap.get('disarm') or () if isinstance(w, dict)}
        if 'jam' in ways and re.search(r'\b(jam|spike|spikes|wedge|wedges|block|hammer)\b', text):
            return trap, ways['jam']
        if 'thieves_tools' in ways and re.search(r"\b(tools?|thieves|lockpicks?|picks?)\b", text):
            return trap, ways['thieves_tools']
        if 'sleight_of_hand' in ways:
            return trap, ways['sleight_of_hand']
        if 'thieves_tools' in ways:
            return trap, ways['thieves_tools']
        return trap, None
    return None


def disarm(trap, way, action):
    """(public line, events) or raises InvalidChange-free PendingRuling text via ValueError."""
    from . import kit_rolls
    if way is None:
        raise ValueError('How do you go about it? The trap needs a way the room gives (tools, careful hands, '
                         'or something to jam it). No turn was committed.')
    if way['method'] == 'jam':
        return (f"You {('jam it with ' + way['with']) if way.get('with') else 'jam it'}; it will not go off now.",
                [{'type': 'trap_state', 'trap': trap['id'], 'status': 'disarmed',
                  'evidence': f'The PC jammed trap {trap["id"]} as the source allows.'}])
    label = "Dexterity check with thieves' tools" if way['method'] == 'thieves_tools' else 'Dexterity (Sleight of Hand) check'
    found = kit_rolls.rolls(action or '')
    if not found:
        raise ValueError(f'Roll a {label} in Avrae first. No turn was committed.')
    total = found[0].total
    if way.get('dc') is None:
        raise ValueError('That trap needs a DC ruling (the source gives none). No turn was committed.')
    if total >= way['dc']:
        return 'You work it loose; the trap is disarmed.', [
            {'type': 'trap_state', 'trap': trap['id'], 'status': 'disarmed',
             'evidence': f'{label} {total} vs DC {way["dc"]}: disarmed.'}]
    return 'It does not give; the trap is still armed.', [
        {'type': 'trap_state', 'trap': trap['id'], 'status': 'found',
         'evidence': f'{label} {total} vs DC {way["dc"]}: failed.'}]
