"""Progressive reveal on room entry (PR-H).

The first look into an area gives the obvious, decision-relevant layer first: who is here,
the ways on, and the things that invite a decision. The rest of what is plainly visible is
held for when the player looks, and Kit hands the floor back in her own voice (her own words; no
stock line). When the player's entry already directs an action ("I go in and grab the orb"), the
action is honored: Kit marks the entry ``directed`` in her decision, gives what the action touches
and answers it, and no handoff question is required. Nothing is hidden by this: the held layer is visible and becomes the answer to
wherever the player looks next.

The layers come from the room data alone. A fact is in the obvious layer when it says
``"layer": "obvious"``, or has ``handling`` (it invites a decision), or a trigger, a story
hook, a claim or a held item names it in a field that holds fact ids (never a
word match: a fact called ``fire`` is not named by a fire damage type). The area's exits are
always in the obvious layer (the way on).
``"layer": "detail"`` holds a fact back whatever else is true. An area with nothing to hold
gets no reveal turn.
"""
import re

from .state_context import require

LAYERS = ('obvious', 'detail')
ENTRY_KINDS = ('opening', 'exit')
REVEAL_RULE = ('Room entry, progressive reveal: give the obvious layer first (reveal.obvious, who is here, the '
               'ways on: reveal.exits), in a few lines. Hold the rest (reveal.hold) for when the player looks; it '
               'is visible, not secret, and becomes the answer to where they look. If the player gave no directed '
               'action, end with Kit handing the floor back in her own words, a short question (example only, '
               'not a line to use: asking where they look). If their entry directs an action (they go in and do '
               'something), honor it: decision.reveal_entry {"mode": "directed", "relevant": [held fact ids the '
               'action touches]}, give those and answer the action; no handoff question is needed. Otherwise '
               'decision.reveal_entry {"mode": "handoff"} (or leave it out).')
HANDOFF = re.compile(r"\?|\b(?:your move|your call|over to you|what do you do|you tell me)\b", re.I)
# A held fact counts as poured out when the narration uses this many of its own cue words (the
# words no shown fact has), or all of them when it has fewer.
HELD_CUES_PER_FACT = 2
FACT_ID_FIELDS = ('fact', 'facts', 'disturb', 'holds', 'about_fact', 'reveals_fact', 'fact_id')
_STOP = frozenset('''about above after again along also around away back been before behind being below beside
between beyond both down each from have here into just like more most near none only other over past same some
still such than that their them then there these they this those through under very what when where which while
with within without would your stands sits hangs lies'''.split())


def check_layer(source):
    """Room-load problems for ``layer`` on facts."""
    return [f'fact {key} layer must be obvious or detail' for key, fact in (source.get('facts') or {}).items()
            if isinstance(fact, dict) and fact.get('layer') is not None and fact['layer'] not in LAYERS]


def _named_ids(value, out, field=None):
    """Every string held in a fact-id field (FACT_ID_FIELDS) anywhere in ``value``."""
    if isinstance(value, dict):
        for key, item in value.items():
            _named_ids(item, out, key)
    elif isinstance(value, list):
        for item in value:
            _named_ids(item, out, field)
    elif isinstance(value, str) and field in FACT_ID_FIELDS:
        out.add(value)
    return out


def _referenced(source, key):
    """Named as a fact by a trigger, hook, claim, toll or a feature that holds it."""
    named = _named_ids({k: v for k, v in source.items() if k != 'facts'}, set())
    for other in (source.get('facts') or {}).values():
        if isinstance(other, dict) and isinstance(other.get('handling'), dict):
            _named_ids(other['handling'], named)
    return key in named


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
    area = state.get('area')
    exits = [str(((edge or {}).get('labels') or {}).get(area) or edge.get('name') or key)
             for key, edge in (source.get('exits') or {}).items()
             if isinstance(edge, dict) and area in (edge.get('areas') or ()) and not edge.get('secret')]
    return {'rule': REVEAL_RULE, 'area': state.get('area'), 'exits': exits,
            'obvious': [facts[k]['text'] for k in split['obvious']],
            'hold': [_gist(facts[k]['text']) for k in split['detail']],
            'hold_ids': split['detail']}


def _gist(text):
    words = text.split()
    return ' '.join(words[:6]) + ('...' if len(words) > 6 else '')


def _cues(text):
    return {w for w in re.findall(r"[a-z]{5,}", text.casefold()) if w not in _STOP}


def entry_mode(plan):
    """Kit's read of the entry: 'directed' (the player's entry directs an action; honor it) or
    'handoff' (the default)."""
    entry = (plan or {}).get('reveal_entry') or {}
    return entry.get('mode') if entry.get('mode') in ('directed', 'handoff') else 'handoff'


def check_entry(plan, reveal):
    entry = (plan or {}).get('reveal_entry')
    if entry is None:
        return
    require(isinstance(entry, dict) and entry.get('mode') in ('directed', 'handoff'),
            'reveal_entry.mode must be directed or handoff')
    relevant = entry.get('relevant', [])
    require(isinstance(relevant, list) and all(isinstance(k, str) for k in relevant),
            'reveal_entry.relevant is a list of held fact ids')
    unknown = [k for k in relevant if k not in (reveal or {}).get('hold_ids', ())]
    require(not unknown, f'reveal_entry.relevant names facts that are not held here: {", ".join(unknown)}')


def check_spoken(reveal, segments, source=None, plan=None):
    """Structural: unless Kit marked the entry directed, the reveal turn ends with Kit handing the
    floor back; and the narration does not pour out the held layer (any held fact whose own cue
    words the narration uses, beyond the ones the action made relevant)."""
    if not reveal:
        return
    check_entry(plan, reveal)
    directed = entry_mode(plan) == 'directed'
    if not directed:
        last = segments[-1] if segments else {}
        # Kit's own handoff, or an NPC who puts a question to the PC (the challenge is the decision).
        npc_asks = last.get('speaker') not in ('Kit', 'Narrator', None) and '?' in (last.get('text') or '')
        require(npc_asks or (last.get('speaker') == 'Kit' and HANDOFF.search(last.get('text') or '')),
                'Room entry, progressive reveal: end with Kit handing the floor back, a short question in her own '
                'words (or mark decision.reveal_entry directed when the player already directed an action)')
    if not source:
        return
    facts = source.get('facts') or {}
    relevant = set(((plan or {}).get('reveal_entry') or {}).get('relevant') or ())
    # What the obvious layer may name: the shown facts, who is here, the area and its ways on.
    here = [' '.join(str(a.get(k) or '') for k in ('name', 'label', 'title'))
            for a in (source.get('actors') or {}).values()
            if isinstance(a, dict) and a.get('location') == reveal['area'] and a.get('status') != 'hidden']
    area = (source.get('areas') or {}).get(reveal['area']) or {}
    shown = set(_cues(' '.join([f.get('text') or '' for k, f in facts.items()
                                if f.get('area') == reveal['area'] and k not in reveal['hold_ids']] + here +
                               [str(area.get('name') or ''), str(area.get('called') or '')] +
                               list(reveal.get('exits') or ()))))
    narration = _cues(' '.join(s.get('text') or '' for s in segments))
    poured = []
    for key in reveal['hold_ids']:
        if key in relevant:
            continue
        own = _cues(facts[key]['text']) - shown
        if own and len(own & narration) >= min(HELD_CUES_PER_FACT, len(own)):
            poured.append(key)
    require(not poured,
            'Room entry, progressive reveal: the narration gives the held layer (' + ', '.join(poured) +
            '); give the obvious layer and hold the rest for where the player looks')
