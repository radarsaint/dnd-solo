"""Room triggers: monster-initiated combat from room data alone (PR-M).

A room's ``triggers`` list says what wakes something up. Each entry is data:

    {"id": "carcass_disturbed",
     "on": {"disturb": "<fact id>"} | {"enter": "<area id>"},
     "starts_combat": true,                       # default true
     "actors": ["<actor id>", ...],               # status "hidden" until it fires
     "surprise": {"stealth": <bonus>} | {"stealth": null} | {"dc": <n>},   # optional
     "reveal": "<public line when they show themselves>"}

``disturb`` fires when the PC moves, searches, or gets into the feature (the room's handled
fact), or puts hands on one of its ``parts`` or takes what it ``holds`` ('I pry the claw open',
'I take the orb from the claw'); ``enter`` fires when the PC arrives in the area. A trigger fires once. Firing commits a
``trigger_fired`` event (the actors go from hidden to alive and visible) and, with
``starts_combat``, the fight starts awaiting initiative with the reveal line read first.

Surprise follows the SRD: each ambusher's Dexterity (Stealth) check (a seeded d20 plus the
bonus given, else the stat block's ``stealth``, else Dex 0) against the PC's passive
Perception; the PC is surprised only if he notices none of them (passive below every total).
A flat ``dc`` stands in for the group's check. The ambushers are never surprised. A PC already
in a fight is never surprised.

Hidden actors (``status: "hidden"``) are in dm_only and nowhere else Kit or the player can see
until their trigger fires (state_context, kit_brief, kit_agenda, kit_attitude, kit_claims,
scene_discernment and the bridge's speakers all skip them).
"""
import hashlib

from .state_context import InvalidChange, require

KINDS = ('disturb', 'enter')
FEATURE_KINDS = ('move_feature', 'inspect_feature', 'enter_feature', 'handle_feature')
FIELDS = {'id', 'on', 'starts_combat', 'actors', 'surprise', 'reveal'}


def compile_triggers(source):
    """The room's triggers, checked against its facts, areas and actors (InvalidChange names
    the first problem)."""
    triggers = source.get('triggers') or []
    require(isinstance(triggers, list), 'triggers must be a list')
    seen = set()
    for trigger in triggers:
        require(isinstance(trigger, dict), 'each trigger is an object')
        tid = trigger.get('id')
        require(isinstance(tid, str) and tid.strip() and tid not in seen, 'each trigger needs a unique id')
        seen.add(tid)
        extra = set(trigger) - FIELDS - {k for k in trigger if str(k).startswith('_')}
        require(not extra, f'trigger {tid}: unknown fields {sorted(extra)}')
        on = trigger.get('on')
        require(isinstance(on, dict) and len(on) == 1 and next(iter(on)) in KINDS,
                f'trigger {tid}: on must be one of {{"disturb": fact}} or {{"enter": area}}')
        kind, target = next(iter(on.items()))
        if kind == 'disturb':
            fact = (source.get('facts') or {}).get(target)
            require(isinstance(fact, dict), f'trigger {tid}: unknown fact {target!r}')
            require(bool(fact.get('handling')), f'trigger {tid}: fact {target!r} has no handling to disturb')
        else:
            require(target in (source.get('areas') or {}), f'trigger {tid}: unknown area {target!r}')
        actors = trigger.get('actors')
        require(isinstance(actors, list) and actors, f'trigger {tid}: actors must list who it wakes')
        for key in actors:
            require(key in (source.get('actors') or {}), f'trigger {tid}: unknown actor {key!r}')
        require(isinstance(trigger.get('starts_combat', True), bool), f'trigger {tid}: starts_combat is true or false')
        surprise = trigger.get('surprise')
        if surprise is not None:
            require(isinstance(surprise, dict) and len(surprise) == 1 and (
                ('stealth' in surprise and (surprise['stealth'] is None or type(surprise['stealth']) is int)) or
                ('dc' in surprise and type(surprise['dc']) is int)),
                f'trigger {tid}: surprise is {{"stealth": bonus or null}} or {{"dc": n}}')
        reveal = trigger.get('reveal')
        require(reveal is None or (isinstance(reveal, str) and 0 < len(reveal) <= 300),
                f'trigger {tid}: reveal is one public line (up to 300 characters)')
    return triggers


def pending(source, state):
    """Triggers that have not fired yet."""
    fired = set(state.get('triggers_fired') or ())
    return [t for t in (source.get('triggers') or []) if t['id'] not in fired]


def apply_event(state, source, event):
    key = event.get('trigger')
    trigger = next((t for t in (source.get('triggers') or []) if t.get('id') == key), None)
    require(trigger is not None, 'Unknown trigger')
    fired = state.setdefault('triggers_fired', [])
    require(key not in fired, 'That trigger has already fired')
    for actor_key in trigger['actors']:
        actor = state['actors'].get(actor_key)
        require(actor is not None, 'Unknown actor')
        if actor.get('status') == 'hidden':
            actor['status'] = 'alive'
            actor['visible'] = True
    fired.append(key)


def disturbed(source, state, result, action):
    """The fact this resolution handled (moved, searched, entered), or None."""
    if result.kind not in FEATURE_KINDS:
        return None
    from .kit_agent import QUOTED_SPEECH, feature_owner, room_words  # local: kit_agent imports this module
    words = room_words(source, state)
    found = words.feature_in(QUOTED_SPEECH.sub(' ', action).lower()) or words.feature_in(action.lower())
    # A part names its feature; an item it holds (the claw's orb) disturbs the feature holding it.
    return feature_owner(source, found[1]) if found else None


def arrived(source, state, result):
    """The area a move in this resolution lands in, or None."""
    area = state.get('area')
    for event in result.events:
        if event.get('type') == 'move':
            edge = (source.get('exits') or {}).get(event.get('exit')) or {}
            area = next((a for a in edge.get('areas', ()) if a != area), area)
            return area
    return None


def matching(source, state, result, action):
    """(trigger, area it fires in) for the first pending trigger this resolution sets off."""
    triggers = pending(source, state)
    if not triggers:
        return None
    fact = disturbed(source, state, result, action)
    landed = arrived(source, state, result)
    for trigger in triggers:
        kind, target = next(iter(trigger['on'].items()))
        if kind == 'disturb' and fact == target:
            return trigger, state.get('area')
        if kind == 'enter' and landed == target:
            return trigger, landed
    return None


def surprise_roll(source, state, revision, trigger, actor_key, npc_roll=None):
    if npc_roll:
        return npc_roll()
    material = f"{state.get('roll_seed', '')}:{revision}:trigger:{trigger['id']}:{actor_key}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], 'big') % 20 + 1


def pc_surprised(source, state, revision, trigger, passive, npc_roll=None):
    """(surprised?, trace) by the SRD: the PC is surprised if his passive Perception is below
    every ambusher's Stealth total (he notices none of them)."""
    rule = trigger.get('surprise')
    if not rule or (state.get('combat') or {}).get('status') in ('awaiting_initiative', 'running'):
        return False, 'no surprise'
    if 'dc' in rule:
        return passive < rule['dc'], f"surprise: stealth DC {rule['dc']} vs passive Perception {passive}"
    from . import kit_combat
    stats = kit_combat.config(source).get('actors') or {}
    totals = []
    for key in trigger['actors']:
        bonus = rule.get('stealth')
        if bonus is None:
            bonus = (stats.get(key) or {}).get('stealth', 0)
        die = surprise_roll(source, state, revision, trigger, key, npc_roll)
        totals.append((key, die, bonus, die + bonus))
    surprised = all(total > passive for *_, total in totals)
    trace = 'surprise: ' + ', '.join(f'{k} stealth d20 {d} + {b} = {t}' for k, d, b, t in totals) + \
        f' vs passive Perception {passive}: {"surprised" if surprised else "noticed"}'
    return surprised, trace


def handoff_trace(trigger, surprised):
    """The seam for PR-H's per-turn handoff log: what fired and why. Telemetry only."""
    return {'type': 'monster_initiative', 'trigger': trigger['id'], 'on': dict(trigger['on']),
            'starts_combat': trigger.get('starts_combat', True), 'pc_surprised': bool(surprised)}
