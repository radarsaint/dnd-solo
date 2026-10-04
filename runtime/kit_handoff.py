"""Per-turn handoff trace (PR-H): one JSONL line per committed turn, plus one per input the
engine held, in the session dir (``<db stem>.handoff.jsonl`` next to the session database).

A turn line says whether that turn handed the floor to the player, which kind of handoff it
was, what triggered it, how long the turn took (from the timing stamps), and, for the handoff
before it, whether the floor actually went to the player: the next input came from the player
and resolved the awaited action. Dump it with ``scripts/handoff_trace.py``.

    type                raised by   trigger                         awaited / resolved when
    stall_check         Kit         a heavy turn (entry, a way on)  the player's roll
    roll_call           Kit/engine  Kit's check call / a save rider the player's roll
    reaction_window     engine      a hit / a foe leaving reach     a yes, no, or a choice
    flourish            engine      an important or last kill       the player's description
    progressive_reveal  engine      first look into an area         where the player looks
    clarify             Kit         ask_player                      the player's answer
    narrowing_question  Kit         a short beat ending on a question the player's answer
    risk_confirm        Kit         a risky act                     confirm or change

Telemetry only: nothing here changes a turn.
"""
import json
import time
from pathlib import Path

TYPES = ('stall_check', 'reaction_window', 'flourish', 'narrowing_question', 'progressive_reveal', 'clarify',
         'risk_confirm', 'roll_call')
SUFFIX = '.handoff.jsonl'
ENGINE_TYPES = ('reaction_window', 'flourish')
ROLL_TYPES = ('stall_check',)
INPUT_CHARS = 160


def trace_path(runtime):
    """``<session dir>/<db stem>.handoff.jsonl``: one trace per session database."""
    path = getattr(runtime, 'path', None)
    if not path or str(path) == ':memory:':
        return None
    path = Path(path).resolve()
    return path.parent / f'{path.stem}{SUFFIX}'


def read(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append(runtime, line):
    path = trace_path(runtime)
    if path is None:
        return None
    with path.open('a') as out:
        out.write(json.dumps(line, sort_keys=True) + '\n')
    return line


def classify(kind, body, plan, record, state_after):
    """{'type', 'trigger', 'awaits', 'deferred_action_id'} for the handoff this turn made, or None."""
    from .kit_agent import stall_check
    from . import kit_interstitial
    body, plan, record = body or {}, plan or {}, record or {}
    awaiting = (state_after.get('combat') or {}).get('awaiting')
    if awaiting:
        found = {'flourish_window': 'flourish'}.get(awaiting['kind'], awaiting['kind'])
        trigger = awaiting.get('trigger') or (f"kill:{awaiting.get('target')}" if found == 'flourish' else None)
        return {'type': found, 'trigger': trigger, 'awaits': awaiting.get('awaits'),
                'deferred_action_id': awaiting.get('deferred_action_id'), 'raised_by': 'engine'}
    if plan and stall_check(plan, kind):
        return {'type': 'stall_check', 'trigger': f"heavy {kind} turn: {plan['roll_call'].get('skill')} call",
                'awaits': 'player_roll', 'deferred_action_id': (record.get('interstitial') or {}).get('deferred_action_id'),
                'raised_by': 'kit'}
    interstitial = record.get('interstitial')
    if interstitial:
        trigger = {'clarify': 'ask_player', 'risk_confirm': f"risk: {(plan.get('risk_confirm') or {}).get('fact')}",
                   'roll_call': f"check call: {(plan.get('roll_call') or {}).get('skill')}"}.get(interstitial['kind'])
        return {'type': interstitial['kind'], 'trigger': trigger, 'awaits': interstitial['awaits'],
                'deferred_action_id': interstitial.get('deferred_action_id'), 'raised_by': 'kit'}
    if body.get('progressive_reveal'):
        return {'type': 'progressive_reveal', 'trigger': f"first look: {body['progressive_reveal']['area']}",
                'awaits': 'player_choice', 'deferred_action_id': None, 'raised_by': 'engine'}
    segments = [line for line in (record.get('spoken') or '').splitlines() if line.strip()]
    if plan and (plan.get('public_brief') or {}).get('scope') == 'call' and segments and \
            segments[-1].startswith('Kit:') and '?' in segments[-1]:
        return {'type': 'narrowing_question', 'trigger': 'short beat ending on a question',
                'awaits': 'player_answer', 'deferred_action_id': None, 'raised_by': 'kit'}
    del kit_interstitial
    return None


def latency(timing):
    """(seconds, source) from the timing stamps: end to end when the host stamped it, else
    prepare to commit, else the runtime's own prepare time."""
    from .kit_agent import turn_latency
    timing = timing or {}
    end = turn_latency(timing).get('end_to_end_s')
    if end is not None and (timing.get('host_stamps') or {}).get('shown_at') is not None:
        return end, 'host_stamps (received to shown)'
    if end is not None:
        return end, 'host_stamps (no shown_at)'
    if timing.get('prepare_to_commit_s') is not None:
        return timing['prepare_to_commit_s'], 'prepare_to_commit only (no shown_at)'
    if timing.get('runtime_prepare_ms') is not None:
        return round(timing['runtime_prepare_ms'] / 1000, 3), 'runtime_prepare only (no shown_at)'
    return None, None


def _open_handoff(lines):
    """The last committed turn's handoff, if no committed turn has followed it."""
    for line in reversed(lines):
        if line.get('event') == 'turn':
            return line if line.get('handoff') else None
    return None


def _answer(open_line, committed, action, kind, by_player, state_after, reason=None):
    """One input after a handoff. ``closes``: it settles the handoff (a committed turn that is not a
    re-ask of the same window); ``resolves``: it is the awaited answer from the player. A barge-in
    (held, or committed without the awaited thing) never counts as answering; the verdict is the
    input that closes the handoff."""
    from . import kit_rolls
    handoff = open_line['handoff']
    found = handoff['type']
    base = {'turn_id': open_line['turn_id'], 'type': found}
    if not committed:
        return {**base, 'floor_to_player': False, 'closes': False, 'resolves': False,
                'how': f'barge-in held, not committed: {reason}'[:200]}
    if not by_player:
        return {**base, 'floor_to_player': False, 'closes': True, 'resolves': False,
                'how': 'the next input was not the player\'s'}
    if handoff.get('raised_by') == 'engine' and handoff.get('deferred_action_id'):
        still = ((state_after.get('combat') or {}).get('awaiting') or {}).get('deferred_action_id')
        ok = still != handoff['deferred_action_id']
        if not ok:
            return {**base, 'floor_to_player': False, 'closes': False, 'resolves': False,
                    'how': f'window still open ({kind}: Kit asked again)'}
        return {**base, 'floor_to_player': True, 'closes': True, 'resolves': True, 'how': 'answered the window'}
    if found in ('stall_check', 'roll_call'):
        try:
            rolled = bool(kit_rolls.rolls(action or ''))
        except Exception:
            rolled = False
        return {**base, 'floor_to_player': rolled, 'closes': True, 'resolves': rolled,
                'how': 'rolled' if rolled else f'barged in without the roll ({kind}): not an answer'}
    return {**base, 'floor_to_player': True, 'closes': True, 'resolves': True, 'how': f'answered with a {kind} turn'}


def log_turn(runtime, turn_id, action, kind, body=None, plan=None, record=None, by_player=True):
    path = trace_path(runtime)
    if path is None:
        return None
    revision, state_after = runtime.load()
    lines = read(path)
    open_line = _open_handoff(lines)
    seconds, source = latency(runtime.kit_timing(turn_id))
    events = (body or {}).get('events') or []
    line = {'v': 1, 'event': 'turn', 'turn_id': turn_id, 'revision': revision, 'at': round(time.time(), 3),
            'input': (action or '')[:INPUT_CHARS], 'kind': kind, 'by_player': bool(by_player),
            'handoff': classify(kind, body, plan, record, state_after),
            'latency_s': seconds, 'latency_from': source,
            'answers': _answer(open_line, True, action, kind, by_player, state_after) if open_line else None}
    if line['answers'] and not line['answers']['closes'] and open_line.get('handoff'):
        # Kit re-asked inside the same window: the open handoff stays the original one.
        line['handoff'] = dict(open_line['handoff'], reasked=True)
        line['reasks'] = open_line['turn_id']
    fired = [e.get('trigger') for e in events if e.get('type') == 'trigger_fired']
    if fired:
        line['engine'] = {'monster_initiative': fired}
    return _append(runtime, line)


def log_held(runtime, action, reason):
    """An input the engine held (a pending ruling: nothing committed)."""
    path = trace_path(runtime)
    if path is None:
        return None
    open_line = _open_handoff(read(path))
    line = {'v': 1, 'event': 'held_input', 'at': round(time.time(), 3), 'input': (action or '')[:INPUT_CHARS],
            'reason': str(reason)[:200],
            'answers': _answer(open_line, False, action, None, True, {}, reason) if open_line else None}
    return _append(runtime, line)


def summary(lines, timings=None):
    """One row per committed turn, its handoff closed by what followed: floor_to_player is the
    verdict of the input that closed it (barge-ins and re-asks are attempts, never the answer);
    attempts counts every input until then."""
    rows, by_id = [], {}
    for line in lines:
        if line.get('event') == 'turn':
            seconds, source = line.get('latency_s'), line.get('latency_from')
            if timings and timings.get(line['turn_id']):
                fresh = latency(timings[line['turn_id']])
                if fresh[0] is not None:
                    seconds, source = fresh
            row = {'turn_id': line['turn_id'], 'input': line['input'], 'kind': line['kind'],
                   'handoff': (line.get('handoff') or {}).get('type'),
                   'trigger': (line.get('handoff') or {}).get('trigger'),
                   'latency_s': seconds, 'latency_from': source, 'floor_to_player': None, 'how': None,
                   'attempts': 0, **({'engine': line['engine']} if line.get('engine') else {})}
            rows.append(row)
            by_id[line['turn_id']] = row
        answer = line.get('answers')
        if answer and answer['turn_id'] in by_id:
            target = by_id[answer['turn_id']]
            while target.get('reasks') and target['reasks'] in by_id:  # a re-ask: the original window
                target = by_id[target['reasks']]
            target['attempts'] += 1
            if target['floor_to_player'] is None and answer.get('closes', True):
                target['floor_to_player'], target['how'] = answer['floor_to_player'], answer['how']
        if line.get('event') == 'turn' and line.get('reasks'):
            by_id[line['turn_id']]['reasks'] = line['reasks']
    return rows
