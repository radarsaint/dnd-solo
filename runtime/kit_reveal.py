"""Progressive reveal on room entry (PR-H).

The first look into an area gives the obvious, decision-relevant layer first: who is here,
the ways on, and the things that invite a decision. The rest of what is plainly visible is
held for when the player looks, and Kit hands the floor back in her own voice ("Where do you
look first?"). Nothing is hidden by this: the held layer is visible and becomes the answer to
wherever the player looks next.

The layers come from the room data alone. A fact is in the obvious layer when it says
``"layer": "obvious"``, or has ``handling`` (it invites a decision), or is named elsewhere in
the room (an alarm, a hook, an exit, an actor, a trigger: it matters to what happens next).
``"layer": "detail"`` holds a fact back whatever else is true. An area with nothing to hold
gets no reveal turn.
"""
import json
import re

from .state_context import require

LAYERS = ('obvious', 'detail')
ENTRY_KINDS = ('opening', 'exit')
REVEAL_RULE = ('Room entry, progressive reveal: give the obvious layer first (reveal.obvious, who is here, the '
               'ways on), in a few lines. Hold the rest (reveal.hold) for when the player looks; it is visible, '
               'not secret, and becomes the answer to where they look. End with Kit handing the floor back in '
               'her own voice, a short question such as "Where do you look first?"')
HANDOFF = re.compile(r"\?|\b(?:your move|your call|over to you|what do you do|you tell me)\b", re.I)
HELD_CUES_FOR_REJECT = 2
_STOP = frozenset('''about above after again along also around away back been before behind being below beside
between beyond both down each from have here into just like more most near none only other over past same some
still such than that their them then there these they this those through under very what when where which while
with within without would your stands sits hangs lies'''.split())


def check_layer(source):
    """Room-load problems for ``layer`` on facts."""
    return [f'fact {key} layer must be obvious or detail' for key, fact in (source.get('facts') or {}).items()
            if isinstance(fact, dict) and fact.get('layer') is not None and fact['layer'] not in LAYERS]


def _referenced(source, key):
    rest = {k: v for k, v in source.items() if k != 'facts'}
    return re.search(r'"' + re.escape(key) + r'"', json.dumps(rest)) is not None


def layers(source, state):
    """{'obvious': [fact ids], 'detail': [fact ids]} for the PC's area (visible facts only)."""
    area = state.get('area')
    out = {'obvious': [], 'detail': []}
    for key, fact in (source.get('facts') or {}).items():
        if not isinstance(fact, dict) or fact.get('area') != area or not fact.get('visible'):
            continue
        layer = fact.get('layer') or ('obvious' if fact.get('handling') or _referenced(source, key) else 'detail')
        out[layer].append(key)
    return out


def view(source, state, kind, table_talk=False, held=False):
    """The reveal block for this turn's packet, or None. Only on the first look into an area
    (room entry), never at an approach, during a fight, or while a held description is owed."""
    from . import kit_rooms
    if kind not in ENTRY_KINDS or table_talk or held:
        return None
    if kit_rooms.stage(source, state) != 'first_look':
        return None
    if ((state.get('combat') or {}).get('status')) in ('awaiting_initiative', 'running'):
        return None
    split = layers(source, state)
    if not split['detail']:
        return None
    facts = source['facts']
    return {'rule': REVEAL_RULE, 'area': state.get('area'),
            'obvious': [facts[k]['text'] for k in split['obvious']],
            'hold': [_gist(facts[k]['text']) for k in split['detail']],
            'hold_ids': split['detail']}


def _gist(text):
    words = text.split()
    return ' '.join(words[:6]) + ('...' if len(words) > 6 else '')


def _cues(text):
    return {w for w in re.findall(r"[a-z]{5,}", text.casefold()) if w not in _STOP}


def check_spoken(reveal, segments, source=None):
    """Structural: the reveal turn ends with Kit handing the floor back, and the narration
    does not pour out the held layer (cue words of two or more held facts)."""
    if not reveal:
        return
    last = segments[-1] if segments else {}
    # Kit's own handoff, or an NPC who puts a question to the PC (the challenge is the decision).
    npc_asks = last.get('speaker') not in ('Kit', 'Narrator', None) and '?' in (last.get('text') or '')
    require(npc_asks or (last.get('speaker') == 'Kit' and HANDOFF.search(last.get('text') or '')),
            'Room entry, progressive reveal: end with Kit handing the floor back, a short question in her voice '
            '(e.g. "Where do you look first?")')
    if not source:
        return
    facts = source.get('facts') or {}
    shown = set(_cues(' '.join(f.get('text') or '' for k, f in facts.items()
                               if f.get('area') == reveal['area'] and k not in reveal['hold_ids'])))
    narration = _cues(' '.join(s.get('text') or '' for s in segments))
    poured = [k for k in reveal['hold_ids'] if (_cues(facts[k]['text']) - shown) & narration]
    require(len(poured) < HELD_CUES_FOR_REJECT,
            'Room entry, progressive reveal: the narration gives the held layer (' + ', '.join(poured) +
            '); give the obvious layer and hold the rest for where the player looks')
