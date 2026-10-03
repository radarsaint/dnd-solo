"""Kit's running plan: a few private beats she carries from turn to turn. Room-agnostic.

The decision may carry a ``plan`` block: the whole current plan, at most MAX_BEATS beats,
each one who is building toward what, roughly when, and why (from wants, agenda, claims),
with roots like an agenda move (or a story brief hook, ``hook:<id>``). Each beat says how it changed this turn: new, keep,
advance, or revise (revise gives a reason). A prior beat left out must be dropped with a
reason. Leaving the block out carries the stored plan unchanged.

The plan lives in state['kit_plan'] and reaches only the private decision input (prepare's
kit_plan). It is never sent to the performer as its own text and never shown to the player:
it changes play only through the choices the decision makes from it. A beat for an actor
respects knower bands: nobody builds toward a secret they are unaware of.
No model calls; deterministic Python.
"""

import re

from . import kit_agenda
from .state_context import require

MAX_BEATS = 5
TEXT_MAX = 160
WHEN = ('now', 'soon', 'later')
CHANGES = ('new', 'keep', 'advance', 'revise')
BEAT_ID = re.compile(r'^[a-z0-9_-]{1,24}$')
FIELDS = ('id', 'who', 'toward', 'when', 'why', 'roots', 'change', 'reason')

_LINE = {'type': 'string'}
PLAN_SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'beats': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'properties': {
        'id': _LINE, 'who': _LINE, 'toward': _LINE, 'when': {'type': 'string', 'enum': list(WHEN)},
        'why': _LINE, 'roots': {'type': 'array', 'items': _LINE},
        'change': {'type': 'string', 'enum': list(CHANGES)}, 'reason': _LINE},
        'required': list(FIELDS)}},
    'dropped': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                'properties': {'id': _LINE, 'reason': _LINE}, 'required': ['id', 'reason']}}},
    'required': ['beats', 'dropped']}


def current(state):
    """The stored beats (without the per-turn change fields)."""
    return list(((state or {}).get('kit_plan') or {}).get('beats') or [])


def _text(value, label, limit=TEXT_MAX):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, f'plan {label}: 1-{limit} characters')


def _agents(source):
    return (kit_agenda.compile_agenda(source) or {}).get('agents', {})


def _who(who, source):
    """The actor id a beat's owner stands for (None for kit or an actorless agent)."""
    if who == 'kit':
        return None
    if who in (source.get('actors') or {}):
        return who
    agents = _agents(source)
    require(who in agents, f'plan who {who!r}: an actor id, an agenda agent id, or kit')
    return agents[who].get('actor')


def _rooted(root, source, state):
    agents = _agents(source)
    pressures = ((kit_agenda.compile_agenda(source) or {}).get('pressures') or {})
    agent, _, move = root.partition(':')
    if agent == 'hook':
        # A hook of this scene's story brief (runtime/kit_brief.py).
        from . import kit_brief
        story = kit_brief.compile_story(source).get((state or {}).get('area')) or {}
        return any(hook['id'] == move for hook in story.get('hooks') or ())
    return (kit_agenda._rooted(root, source, state) or root in agents or root in pressures or
            (move and agent in agents and move in agents[agent]['moves']))


def check_plan_block(block, source, state):
    """Structure, roots, knower bands, and carry-over against the stored plan."""
    source, state = source or {}, state or {}
    require(isinstance(block, dict) and set(block) == {'beats', 'dropped'}, 'plan needs {beats, dropped}')
    beats, dropped = block['beats'], block['dropped']
    require(isinstance(beats, list) and len(beats) <= MAX_BEATS, f'plan.beats: at most {MAX_BEATS}')
    require(isinstance(dropped, list), 'plan.dropped is a list')
    prior = {beat['id']: beat for beat in current(state)}
    seen = set()
    for beat in beats:
        require(isinstance(beat, dict) and set(beat) == set(FIELDS), 'Each beat needs ' + ', '.join(FIELDS))
        bid = beat['id']
        require(isinstance(bid, str) and BEAT_ID.match(bid) and bid not in seen,
                f'plan beat id {bid!r}: unique, lowercase, up to 24 characters')
        seen.add(bid)
        for key in ('toward', 'why'):
            _text(beat[key], f'{bid} {key}')
        require(beat['when'] in WHEN, f'plan {bid} when: ' + ', '.join(WHEN))
        require(beat['change'] in CHANGES, f'plan {bid} change: ' + ', '.join(CHANGES))
        actor = _who(beat['who'], source)
        roots = beat['roots']
        require(isinstance(roots, list) and 1 <= len(roots) <= 4 and
                all(isinstance(r, str) and _rooted(r, source, state) for r in roots),
                f'plan {bid}: 1-4 roots citing source facts, claims, actors, canon, or agenda agents/moves')
        if actor:
            unaware = kit_agenda._unaware({'actor': actor}, roots, source, state)
            require(not unaware, f'plan {bid}: {actor} is unaware of {", ".join(unaware)}; '
                    'they cannot build toward it')
        old = prior.get(bid)
        if beat['change'] == 'new':
            require(old is None, f'plan {bid} already exists: keep, advance, or revise it')
        else:
            require(old is not None, f'plan {bid} is not in the current plan: mark it new')
        if beat['change'] == 'keep':
            require(all(beat[k] == old[k] for k in ('who', 'toward', 'when')),
                    f'plan {bid} changed: advance or revise it instead of keep')
        if beat['change'] == 'advance':
            require(beat['who'] == old['who'] and beat['toward'] == old['toward'],
                    f'plan {bid}: a new owner or goal is a revise')
        if beat['change'] == 'revise':
            _text(beat['reason'], f'{bid} reason', 120)
    gone = set()
    for item in dropped:
        require(isinstance(item, dict) and item.get('id') in prior and item['id'] not in seen,
                'plan.dropped names a current beat that is not kept')
        _text(item.get('reason'), f'{item["id"]} drop reason', 120)
        gone.add(item['id'])
    missing = sorted(set(prior) - seen - gone)
    require(not missing, f'plan: carry {", ".join(missing)} (keep) or drop it with a reason')


def plan_event(block, turn_id):
    beats = [{k: beat[k] for k in ('id', 'who', 'toward', 'when', 'why', 'roots')} for beat in block['beats']]
    return {'type': 'kit_plan', 'beats': beats,
            'evidence': f'Kit plan with turn {turn_id}: ' + (', '.join(
                f'{b["id"]}:{b["change"]}' for b in block['beats']) or 'cleared')}


def apply_event(state, event):
    beats = event.get('beats')
    require(isinstance(beats, list) and len(beats) <= MAX_BEATS, 'kit_plan beats')
    state['kit_plan'] = {'beats': [dict(beat) for beat in beats]}
