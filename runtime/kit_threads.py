"""Open threads: hints and hooks Kit plants in play, tracked until paid off or cleaned up.

Watchroom playtest 2026-10-04: Kit planted "somewhere far below, something stops moving" and it
never came back. Kit records a plant explicitly in her decision (``open_threads``), never by
guessing from her prose; the engine keeps it in state and every prepare packet lists the open
ones, flagged due when the scene is ending, until a later decision pays it off or drops it.
"""
from .state_context import require

THREADS_MAX_OPEN = 8
HINT_MAX_CHARS = 200

OPEN_THREADS_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'plant': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'id': {'type': 'string'}, 'hint': {'type': 'string'}},
            'required': ['id', 'hint']}},
        'pay': {'type': 'array', 'items': {'type': 'string'}},
        'drop': {'type': 'array', 'items': {'type': 'string'}},
    },
}

RULE = ('Hints and hooks you planted and have not paid off. Pay each off (open_threads.pay, the turn it '
        'lands) or clean it up (open_threads.drop) before the scene ends; when due is true the scene is '
        'ending: pay off or clean up now. Record any new hint you plant this turn in open_threads.plant.')


def check(threads, state):
    """A decision's open_threads: new ids with a short hint; pay and drop name open threads."""
    require(isinstance(threads, dict) and set(threads) <= {'plant', 'pay', 'drop'},
            'open_threads is {plant: [{id, hint}], pay: [ids], drop: [ids]}')
    current = (state or {}).get('open_threads') or {}
    plants = threads.get('plant') or []
    require(isinstance(plants, list), 'open_threads.plant is a list of {id, hint}')
    for item in plants:
        require(isinstance(item, dict) and set(item) == {'id', 'hint'} and isinstance(item['id'], str)
                and item['id'].strip() and isinstance(item['hint'], str)
                and 0 < len(item['hint'].strip()) <= HINT_MAX_CHARS,
                f'Each planted thread needs an id and a hint of at most {HINT_MAX_CHARS} characters')
        require(item['id'] not in current, f"Thread {item['id']!r} is already open; pay or drop it instead")
    for field in ('pay', 'drop'):
        ids = threads.get(field) or []
        require(isinstance(ids, list) and all(isinstance(i, str) for i in ids), f'open_threads.{field} is a list of ids')
        unknown = [i for i in ids if i not in current]
        require(not unknown, f'open_threads.{field} names no open thread: {", ".join(unknown)} '
                             f'(open: {", ".join(current) or "none"})')
    require(len(current) + len(plants) <= THREADS_MAX_OPEN,
            f'At most {THREADS_MAX_OPEN} open threads: pay off or drop one first')


def event(threads, turn_id, area):
    return {'type': 'open_threads', 'plant': [dict(item, area=area) for item in threads.get('plant') or ()],
            'close': list(threads.get('pay') or ()) + list(threads.get('drop') or ()),
            'evidence': f'Kit recorded open threads on turn {turn_id}.', 'turn_id': turn_id}


def apply_event(state, event):
    threads = dict(state.get('open_threads') or {})
    for key in event.get('close') or ():
        threads.pop(key, None)
    for item in event.get('plant') or ():
        threads[item['id']] = {'hint': item['hint'], 'area': item.get('area'), 'planted_turn': event.get('turn_id')}
    if threads:
        state['open_threads'] = threads
    else:
        state.pop('open_threads', None)


def view(state, ending):
    """The prepare packet's list, or None when nothing is open. ``ending``: the scene is ending."""
    threads = (state or {}).get('open_threads') or {}
    if not threads:
        return None
    return {'rule': RULE, 'due': bool(ending),
            'threads': [{'id': key, 'hint': item['hint'], 'planted_turn': item.get('planted_turn')}
                        for key, item in threads.items()]}
