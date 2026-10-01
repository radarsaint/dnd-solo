"""Agendas: something in the scene wants something, and it moves when it should. Room-agnostic.

The pace decides when: ``agenda_here.must_advance`` is True once an advance is due (every
N turns, per area). When it is not due, a quiet turn is valid even with agents present, as
long as the decision says why nothing advances; it is rejected only when an advance is
overdue and the reason does not fit (only "engaged", the player dealing with that agent
right now, excuses an overdue advance).

Modeled on Dungeon World fronts and GM moves and Blades in the Dark clocks. The source
may declare one top-level ``agenda`` block. It covers every kind of room with one
mechanism, because an *agent* is anything that wants something:

    agenda:
      every: 1                      default pacing: something advances at least every N turns
      pace: {area_id: N}            a calmer area (a quiet room is valid; it just moves less often)
      agents:
        <id>:
          kind: npc | monster | faction | environment | clock
          actor: <actor id>         optional; onstage wherever that actor is (and alive)
          areas: [area ids] | "*"   where it acts without a present actor: an absent owner,
                                    a faction spanning rooms, a wandering threat, decay, a trap
          disposition: hostile | friendly | neutral
          wants: "what it wants from the PC specifically"
          roots: [fact | actor | claim ids]
          moves:
            <move id>: {does, roots, trigger: stall|elsewhere|engaged|odd|any,
                        needs: [claim ids the actor must be aware of], ticks: <pressure id>}
      pressures:
        <id>: {segments, ticks_on, when_full, roots, areas: [...] | "*"}

Clocks and 'last acted' live in state['agenda'] for the whole session, so a faction's
clock carries across areas and a revisited room remembers. A move grounded in a claim
respects that claim's knower bands: an actor unaware of a secret cannot act on it.
No model calls; deterministic Python.
"""
import re

from . import kit_claims
from .state_context import require

KINDS = ('npc', 'monster', 'faction', 'environment', 'clock')
DISPOSITIONS = ('hostile', 'friendly', 'neutral')
TRIGGERS = ('stall', 'elsewhere', 'engaged', 'odd', 'any')  # odd: the PC does something odd for the situation
# none: something advanced. engaged: the player is dealing with that agent right now, and
# that exchange IS its advance. quiet: nothing advances this turn, for the stated reason
# (valid with agents present while no advance is due). paced: the same, named for the pace.
HOLDS = ('none', 'engaged', 'quiet', 'paced')
GONE = ('fled', 'dead', 'defeated', 'gone')
TEXT_MAX = 200
MAX_SEGMENTS = 12


def _text(value, label):
    require(isinstance(value, str) and 0 < len(value.strip()) <= TEXT_MAX, f'{label}: 1-{TEXT_MAX} characters')


def _rooted(root, source, state=None):
    state = state or {}
    return (root in source.get('facts', {}) or root in (source.get('claims') or {}) or
            root.split(':', 1)[-1] in source.get('actors', {}) or root in (state.get('canon') or {}) or
            root.strip().casefold() in kit_claims.established_claims(state))


def _roots(roots, source, label, state=None):
    require(isinstance(roots, list) and roots and all(isinstance(r, str) and _rooted(r, source, state)
                                                      for r in roots),
            f'{label}: roots must cite source facts, claims, actors, or canon (nonsense is not entertaining)')


def _areas(value, source, label):
    require(value == '*' or (isinstance(value, list) and all(a in source.get('areas', {}) for a in value)),
            f'{label}: areas is a list of area ids or "*"')


def compile_agenda(source):
    """The checked agenda block, or None when the source declares none."""
    block = (source or {}).get('agenda')
    if not block:
        return None
    every = block.get('every', 1)
    require(type(every) is int and every >= 1, 'agenda.every is a whole number of turns, at least 1')
    for area, pace in (block.get('pace') or {}).items():
        require(area in source.get('areas', {}) and type(pace) is int and pace >= 1, f'agenda.pace {area}')
    pressures = {k: v for k, v in (block.get('pressures') or {}).items() if not k.startswith('_')}
    for key, clock in pressures.items():
        require(type(clock.get('segments')) is int and 2 <= clock['segments'] <= MAX_SEGMENTS,
                f'Pressure {key}: segments 2-{MAX_SEGMENTS}')
        _text(clock.get('ticks_on'), f'Pressure {key} ticks_on')
        _text(clock.get('when_full'), f'Pressure {key} when_full')
        _roots(clock.get('roots'), source, f'Pressure {key}')
        _areas(clock.get('areas', '*'), source, f'Pressure {key}')
    agents = {k: v for k, v in (block.get('agents') or {}).items() if not k.startswith('_')}
    for key, agent in agents.items():
        label = f'Agent {key}'
        require(agent.get('kind') in KINDS, f'{label}: kind is one of {", ".join(KINDS)}')
        require(agent.get('disposition', 'neutral') in DISPOSITIONS, f'{label}: unknown disposition')
        if agent.get('actor') is not None:
            require(agent['actor'] in source.get('actors', {}), f'{label}: unknown actor')
        else:
            require('areas' in agent, f'{label}: with no actor it needs areas (where it acts)')
        if 'areas' in agent:
            _areas(agent['areas'], source, label)
        _text(agent.get('wants'), f'{label} wants')
        _roots(agent.get('roots'), source, label)
        moves = agent.get('moves')
        require(isinstance(moves, dict) and moves, f'{label}: declare at least one move')
        for move_id, move in moves.items():
            _text(move.get('does'), f'{label} move {move_id}')
            _roots(move.get('roots'), source, f'{label} move {move_id}')
            require(move.get('trigger', 'any') in TRIGGERS, f'{label} move {move_id}: unknown trigger')
            require(all(c in (source.get('claims') or {}) for c in move.get('needs', [])),
                    f'{label} move {move_id}: needs cites claim ids')
            require(move.get('ticks') is None or move['ticks'] in pressures,
                    f'{label} move {move_id}: ticks names a pressure')
    return {'every': every, 'pace': block.get('pace') or {}, 'agents': agents, 'pressures': pressures}


def agenda_state(state):
    return state.get('agenda') or {'turn': 0, 'last_advance': 0, 'clocks': {}, 'last_acted': {}}


def _in(areas, area):
    return areas == '*' or area in (areas or ())


def presence(agent, state):
    """'onstage', 'offstage' (acting on this area from elsewhere), or None."""
    area = state['area']
    actor = (state.get('actors') or {}).get(agent.get('actor')) if agent.get('actor') else None
    if actor and actor.get('location') == area and actor.get('status') not in GONE:
        return 'onstage'
    if actor and actor.get('status') in GONE:
        return None
    if 'areas' in agent and _in(agent['areas'], area):
        return 'offstage' if agent.get('actor') else 'onstage'
    return None


def _unaware(agent, claim_ids, source, state):
    """Claims this agent's actor is unaware of: it cannot act on them."""
    if not agent.get('actor'):
        return []
    claims = kit_claims.compile_claims(source)
    actors = state.get('actors') or {}
    level = kit_claims.current_floor_level(source, state['area'])
    by_fact = {c.get('fact'): k for k, c in claims.items() if c.get('fact')}
    ids = {by_fact.get(c, c) for c in claim_ids}
    return sorted(c for c in ids if c in claims and
                  kit_claims.npc_band(claims[c], agent['actor'], actors, None, level) == 'unaware')


def agenda_here(source, state):
    """Private prepare packet: who here wants what, their moves, clock states, pacing."""
    block = compile_agenda(source)
    if not block:
        return None
    mem = agenda_state(state)
    area = state['area']
    agents = {}
    for key, agent in block['agents'].items():
        where = presence(agent, state)
        if not where:
            continue
        moves, blocked = {}, {}
        for move_id, move in agent['moves'].items():
            unaware = _unaware(agent, list(move.get('needs', [])) + list(move['roots']), source, state)
            if unaware:
                blocked[move_id] = f'unaware of {", ".join(unaware)}'
                continue
            moves[move_id] = {k: move[k] for k in ('does', 'trigger', 'ticks') if k in move}
        agents[key] = {'kind': agent['kind'], 'presence': where, 'disposition': agent.get('disposition', 'neutral'),
                       'wants': agent['wants'], 'moves': moves,
                       'turns_since_acted': mem['turn'] - mem['last_acted'].get(key, 0)}
        if blocked:
            agents[key]['blocked_moves'] = blocked
    pressures = {}
    for key, clock in block['pressures'].items():
        if _in(clock.get('areas', '*'), area):
            filled = mem['clocks'].get(key, 0)
            pressures[key] = {'filled': filled, 'segments': clock['segments'], 'ticks_on': clock['ticks_on'],
                              'when_full': clock['when_full'], 'full': filled >= clock['segments']}
    every = block['pace'].get(area, block['every'])
    since = mem['turn'] - mem['last_advance']
    live = bool(agents) or any(not p['full'] for p in pressures.values())
    return {'every': every, 'turns_since_advance': since, 'must_advance': live and since + 1 >= every,
            'agents': agents, 'pressures': pressures}


_LINE = {'type': 'string'}
AGENDA_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'advances': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'agent': _LINE, 'move': _LINE,   # a declared move id, or "new"
                           'does': _LINE, 'roots': {'type': 'array', 'items': _LINE}, 'why': _LINE},
            'required': ['agent', 'move', 'does', 'roots', 'why']}},
        'ticks': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'pressure': _LINE, 'by': {'type': 'integer'}, 'why': _LINE},
            'required': ['pressure', 'by', 'why']}},
        'hold': {'type': 'object', 'additionalProperties': False,
                 'properties': {'reason': {'type': 'string', 'enum': list(HOLDS)}, 'agent': _LINE, 'why': _LINE},
                 'required': ['reason', 'agent', 'why']}},
    'required': ['advances', 'ticks', 'hold']}
NO_AGENDA = {'advances': [], 'ticks': [], 'hold': {'reason': 'quiet', 'agent': 'none', 'why': 'No agenda here.'}}


def check_agenda(block, packet, source, state, reactors=()):
    """Structure plus the hard pacing rule. Returns the ticks this decision implies.
    reactors: agents reacting to a pc_oddity this turn; that reaction is their advance."""
    if packet is None:
        return {}
    require(isinstance(block, dict) and set(block) == set(AGENDA_SCHEMA['required']),
            'This scene has an agenda: the decision needs agenda {advances, ticks, hold}')
    agents, pressures = packet['agents'], packet['pressures']
    ticks = {}
    require(isinstance(block['advances'], list) and len(block['advances']) <= 3, 'agenda.advances: at most 3')
    for item in block['advances']:
        require(isinstance(item, dict) and set(item) == set(AGENDA_SCHEMA['properties']['advances']['items']['required']),
                'Each advance needs agent, move, does, roots, why')
        require(item['agent'] in agents, f'Unknown or absent agent {item["agent"]!r}; use an agenda_here agent')
        for key in ('does', 'why'):
            _text(item[key], f'advance {key}')
        agent = agents[item['agent']]
        if item['move'] == 'new':
            _roots(item['roots'], source, 'A new move', state)
            unaware = _unaware(compile_agenda(source)['agents'][item['agent']], item['roots'], source, state)
            require(not unaware, f'{item["agent"]} is unaware of {", ".join(unaware)}: it cannot act on it')
        else:
            require(item['move'] in agent['moves'],
                    f'{item["agent"]} has no available move {item["move"]!r}'
                    + (f' ({agent["blocked_moves"][item["move"]]})' if item['move'] in agent.get('blocked_moves', {})
                       else '; use a declared move or "new" with roots'))
            require(agent['moves'][item['move']].get('trigger') != 'odd' or item['agent'] in reactors,
                    f'{item["move"]} fires when the PC does something odd for the situation: record it in '
                    f'pc_oddity with {item["agent"]}\'s actor in noticed_by')
            if agent['moves'][item['move']].get('ticks'):
                ticks[agent['moves'][item['move']]['ticks']] = ticks.get(agent['moves'][item['move']]['ticks'], 0) + 1
    require(isinstance(block['ticks'], list), 'agenda.ticks is a list')
    for item in block['ticks']:
        require(isinstance(item, dict) and item.get('pressure') in pressures,
                'Each tick names an agenda_here pressure')
        require(type(item.get('by')) is int and item['by'] >= 1, 'A tick advances a clock by at least 1')
        _text(item.get('why'), 'tick why')
        ticks[item['pressure']] = ticks.get(item['pressure'], 0) + item['by']
    for key, by in ticks.items():
        clock = pressures.get(key)
        require(clock is not None, f'Pressure {key} is not in play here')
        require(not clock['full'], f'Pressure {key} is full: play its when_full, do not tick it')
    hold = block['hold']
    require(isinstance(hold, dict) and hold.get('reason') in HOLDS, 'agenda.hold.reason: ' + ', '.join(HOLDS))
    _text(hold.get('why'), 'agenda.hold.why')
    reacting = [r for r in reactors if r in agents]
    moved = bool(block['advances'] or ticks or reacting)
    require(hold['reason'] != 'none' or moved, 'hold none means something advanced: list the advance or tick')
    if hold['reason'] == 'engaged':
        require(hold.get('agent') in agents and agents[hold['agent']]['presence'] == 'onstage',
                'An engaged hold names the onstage agent the player is dealing with right now')
        require(len(hold['why'].split()) >= 4, 'Say how this exchange advances what that agent wants')
    if packet['must_advance'] and not moved:
        require(hold['reason'] == 'engaged',
                'Something here wants something and has waited long enough: advance an agent\'s move or '
                'tick a pressure, or hold as engaged when the player is dealing with that agent now')
    if hold['reason'] in ('quiet', 'paced') and not moved:
        require(not packet['must_advance'], 'An advance is due this turn: a quiet hold does not fit')
        live = bool(agents) or any(not p['full'] for p in pressures.values())
        require(not live or len(hold['why'].split()) >= 4,
                'A quiet turn with agents present says why nothing advances (who is waiting, and why now)')
    return ticks


def agenda_event(block, packet, turn_id, ticks, reactors=()):
    """Commit record: turn count, who acted on their want, clock ticks."""
    acted = [item['agent'] for item in block.get('advances', [])] + \
        [r for r in reactors if r in packet['agents']]
    if block.get('hold', {}).get('reason') == 'engaged':
        acted.append(block['hold']['agent'])
    moves = [f'{i["agent"]}:{i["move"]}' for i in block.get('advances', [])]
    return {'type': 'agenda_turn', 'acted': sorted(set(acted)), 'ticks': ticks,
            'evidence': f'Agenda with turn {turn_id}: ' + (', '.join(moves + [f'{k}+{v}' for k, v in ticks.items()])
                                                          or block.get('hold', {}).get('reason', 'hold'))}


def apply_event(state, source, event):
    block = compile_agenda(source)
    require(block is not None, 'agenda_turn needs a source agenda')
    mem = state.setdefault('agenda', agenda_state({}))
    mem['turn'] += 1
    for agent in event.get('acted') or ():
        require(agent in block['agents'], f'Unknown agent {agent!r}')
        mem['last_acted'][agent] = mem['turn']
    for key, by in (event.get('ticks') or {}).items():
        require(key in block['pressures'] and type(by) is int and by >= 1, f'Bad tick {key!r}')
        mem['clocks'][key] = min(block['pressures'][key]['segments'], mem['clocks'].get(key, 0) + by)
    if event.get('acted') or event.get('ticks'):
        mem['last_advance'] = mem['turn']


# ---------------------------------------------------------------------------
# Salience and conditioned advantage: say why, and only what is true now
# ---------------------------------------------------------------------------
ATTENTION = re.compile(r"\b(catch\w*|caught|draw\w*|drew|pull\w*|grab\w*|hold\w*|snag\w*)\s+(your|the|his|her|their)?"
                       r"\s*(eye|eyes|attention|gaze|notice)\b|\bstands? out\b", re.I)
SALIENCE_SCHEMA = {'type': 'array', 'items': {
    'type': 'object', 'additionalProperties': False,
    'properties': {'thing': _LINE, 'reason': _LINE, 'roots': {'type': 'array', 'items': _LINE}},
    'required': ['thing', 'reason', 'roots']}}


def check_salience(items, source, state):
    """Each attention claim names a concrete observable reason rooted in what the PC can see."""
    require(isinstance(items, list) and len(items) <= 3, 'salience: at most 3 entries')
    area = state.get('area')
    visible = {k for k, f in source.get('facts', {}).items() if f.get('area') == area and f.get('visible')}
    visible |= set(state.get('known_facts') or ())
    onstage = {k for k, a in (state.get('actors') or {}).items() if a.get('location') == area and a.get('visible', True)}
    for item in items:
        require(isinstance(item, dict) and set(item) == {'thing', 'reason', 'roots'}, 'salience needs thing, reason, roots')
        _text(item['thing'], 'salience thing')
        _text(item['reason'], 'salience reason')
        require(len(item['reason'].split()) >= 4 and item['reason'].strip().casefold() != item['thing'].strip().casefold(),
                'salience reason names the concrete, observable detail that makes it stand out')
        require(isinstance(item['roots'], list) and item['roots'] and all(
            r in visible or r.split(':', 1)[-1] in onstage or r in (state.get('canon') or {}) or
            r.strip().casefold() in kit_claims.established_claims(state) for r in item['roots']),
            'salience roots cite what the player character can see (a visible fact, a present actor, canon): '
            'never a secret they have not found')


def check_attention_spoken(text, plan):
    if ATTENTION.search(text or ''):
        require(plan.get('salience'), 'The performance says something draws attention: the decision\'s salience '
                'must name the concrete observable reason')


ROLL_MODES = ('normal', 'advantage', 'disadvantage')
CAUSE_KINDS = ('item', 'spell', 'condition', 'feature', 'position')
ROLL_CALL_SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'skill': _LINE, 'mode': {'type': 'string', 'enum': list(ROLL_MODES)},
    'cause': {'type': 'object', 'additionalProperties': False,
              'properties': {'kind': {'type': 'string', 'enum': list(CAUSE_KINDS)}, 'ref': _LINE,
                             'roots': {'type': 'array', 'items': _LINE}},
              'required': ['kind', 'ref', 'roots']}},
    'required': ['skill', 'mode', 'cause']}
CALLED_MODE = re.compile(r"\broll\b[^.]{0,40}\bwith (advantage|disadvantage)\b|"
                         r"\b(advantage|disadvantage) on (your|the|this|that|a)\b", re.I)


def check_roll_call(call, source, state):
    """Advantage or disadvantage cites a condition that is true in state right now."""
    from . import pc_sheet
    require(isinstance(call, dict) and set(call) == {'skill', 'mode', 'cause'} and call['mode'] in ROLL_MODES,
            'roll_call needs skill, mode, cause')
    if call['mode'] == 'normal':
        return
    cause = call['cause']
    require(isinstance(cause, dict) and cause.get('kind') in CAUSE_KINDS and isinstance(cause.get('ref'), str),
            f'{call["mode"].title()} needs a cause: kind ({", ".join(CAUSE_KINDS)}) and ref')
    sheet = state.get('player_sheet') or {}
    kind, ref = cause['kind'], cause['ref']
    if kind == 'item':
        require(pc_sheet.condition_true(sheet, ref, 'held') or pc_sheet.condition_true(sheet, ref, 'equipped'),
                f'{ref} is not held or equipped right now; owning it is not holding it')
    elif kind in ('spell', 'condition'):
        require(pc_sheet.condition_true(sheet, ref, 'active'), f'{ref} is not active right now')
    elif kind == 'feature':
        require(ref.casefold() in {f.casefold() for f in sheet.get('features', [])} or
                'always' in pc_sheet.advantage_sources(sheet, call['skill']),
                f'{ref} is not a feature on the loaded sheet')
    else:
        _roots(cause.get('roots'), source, f'{call["mode"].title()} from position', state)


def check_roll_spoken(text, plan):
    found = CALLED_MODE.search(text or '')
    if not found:
        return
    mode = (found.group(1) or found.group(2)).casefold()
    call = plan.get('roll_call') or {}
    require(call.get('mode') == mode, f'The performance calls {mode}: the decision\'s roll_call must too, with its cause')
    require(call['cause']['ref'].casefold() in text.casefold(), f'Say why: name {call["cause"]["ref"]} when calling {mode}')


# ---------------------------------------------------------------------------
# PC state follows the situation; the player's word wins; odd is a scene event
# ---------------------------------------------------------------------------
# What the PC holds, wears, or has running is not a sheet default. The situation sets it
# (pc_sheet.situated: seated at cards, hands on the cards and a shield set aside; a fight or
# on guard, weapon, shield, or focus in hand) and anything the player says overrides it.
# A declared state or habit that is odd for the situation (a shield at the card table, a
# blade drawn at dinner) stands, advantage included when it is really met: the people present
# notice and react from their wants (pc_oddity). Kit just plays. She asks (ask_player) only
# when neither the situation nor the player settles something that would change an outcome;
# that is rare, never about a list the situation already settles, and that turn commits
# nothing mechanical. No roll ever waits on an unset sheet list.
PC_STATE_SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'held': {'type': 'array', 'items': _LINE}, 'equipped': {'type': 'array', 'items': _LINE},
    'active': {'type': 'array', 'items': _LINE}, 'why': _LINE},
    'required': ['held', 'equipped', 'active', 'why']}
ASK_PLAYER_SCHEMA = {'type': 'object', 'additionalProperties': False,
                     'properties': {'about': _LINE, 'question': _LINE}, 'required': ['about', 'question']}
PC_ODDITY_SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'what': _LINE, 'noticed_by': {'type': 'array', 'items': _LINE}, 'reaction': _LINE},
    'required': ['what', 'noticed_by', 'reaction']}
ASK_MAX_WORDS = 25
PC_STATE_ITEMS = 12


def check_pc_state(block):
    """The PC's full in-force picture now, with the fiction or player words behind it."""
    from . import pc_sheet
    require(isinstance(block, dict) and set(block) == set(PC_STATE_SCHEMA['required']),
            'pc_state needs held, equipped, active, why')
    for key in pc_sheet.CONDITIONS:
        require(isinstance(block[key], list) and len(block[key]) <= PC_STATE_ITEMS and
                all(isinstance(v, str) and 0 < len(v.strip()) <= 60 for v in block[key]),
                f'pc_state {key} lists up to {PC_STATE_ITEMS} names')
    _text(block['why'], 'pc_state why')
    require(len(block['why'].split()) >= 4, 'pc_state why names the situation or the player\'s words that set it')


def with_pc_state(state, block, fight=False):
    """A copy of state whose sheet stands as it is now, for this turn's roll_call: the
    decision's pc_state (the player's word this turn) over the committed lists, over the
    situation's default (a fight when fight is true)."""
    from . import pc_sheet
    if not state.get('player_sheet'):
        return state
    sheet = dict(state['player_sheet'], **({k: list(block[k]) for k in pc_sheet.CONDITIONS} if block else {}))
    return {**state, 'player_sheet': pc_sheet.situated(sheet, pc_sheet.situation_of(state, fight))}


def pc_state_event(block, turn_id):
    from . import pc_sheet
    return {'type': 'pc_state', **{k: list(block[k]) for k in pc_sheet.CONDITIONS},
            'evidence': f'Set with turn {turn_id}: {block["why"][:TEXT_MAX]}'}


def check_ask_player(block, plan, state):
    """The rare short plain question: neither the situation nor the player settles something
    that would change an outcome. Nothing else rides on it."""
    from . import pc_sheet
    require(isinstance(block, dict) and set(block) == {'about', 'question'}, 'ask_player needs about, question')
    _text(block['about'], 'ask_player about')
    question = block['question'].strip()
    require(question.endswith('?') and 0 < len(question.split()) <= ASK_MAX_WORDS,
            f'ask_player.question is one short plain question (at most {ASK_MAX_WORDS} words, ending "?")')
    settled = pc_sheet.settled_by(state.get('player_sheet') or {}, block['about'])
    require(settled != 'player',
            f'{block["about"]}: the player already said, so do not ask. If it is odd for the situation, '
            'let the people present notice it (pc_oddity)')
    require(settled != 'situation',
            f'{block["about"]}: the situation sets it (seated at cards: hands on the cards, shield set '
            'aside; a fight: weapon, shield, or focus in hand). Do not ask; play it, and record a '
            'change in pc_state')
    require(plan['move'] == 'ask_clarification' and plan['public_brief']['scope'] == 'call',
            'ask_player is an ask_clarification move with call scope')
    require(plan['table_presence'] != 'quiet', 'Kit asks the question herself: table_presence cannot be quiet')
    busy = [key for key in ('pc_state', 'roll_call', 'salience', 'pc_oddity') if plan.get(key)]
    busy += ['claims'] if plan.get('claims') else []
    busy += ['detail.inventions'] if (plan.get('detail') or {}).get('inventions') else []
    require(not busy, 'An ask_player turn commits nothing mechanical; drop ' + ', '.join(busy))


def check_ask_spoken(segments, block):
    words = ' '.join(block['question'].casefold().split())
    require(any(segment['speaker'] == 'Kit' and words in ' '.join(segment['text'].casefold().split())
                for segment in segments),
            'Kit asks ask_player.question in her own segment, in those words, and resolves nothing')


def check_pc_oddity(block, plan, state):
    """The PC's declared state or habit is odd for the situation: present people notice."""
    from . import kit_voice
    require(isinstance(block, dict) and set(block) == set(PC_ODDITY_SCHEMA['required']),
            'pc_oddity needs what, noticed_by, reaction')
    _text(block['what'], 'pc_oddity what')
    _text(block['reaction'], 'pc_oddity reaction')
    require(len(block['what'].split()) >= 3, 'pc_oddity.what names the odd thing and the situation it jars with')
    require(len(block['reaction'].split()) >= 4,
            'pc_oddity.reaction says how they react and which of their wants drives it')
    area = state.get('area')
    present = {k for k, a in (state.get('actors') or {}).items()
               if a.get('location') == area and a.get('status') not in GONE}
    require(isinstance(block['noticed_by'], list) and 1 <= len(block['noticed_by']) <= 3 and
            all(n in present for n in block['noticed_by']),
            'pc_oddity.noticed_by lists 1-3 actor ids present in this area')
    notice = kit_voice.parse_npc_notice(plan['public_brief'].get('npc_notice', ''))
    require(notice is not None and notice[0] in ('gear', 'stunt'),
            'A pc_oddity reaches the table through the brief: npc_notice "gear: ..." or "stunt: ..."')


def oddity_reactors(block, source):
    """Agenda agents whose actor noticed the oddity: their reaction is their advance."""
    agenda = compile_agenda(source)
    if not block or not agenda:
        return []
    return sorted(k for k, a in agenda['agents'].items() if a.get('actor') in block['noticed_by'])
