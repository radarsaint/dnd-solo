"""Turn roles (PR-H): every committed turn is substantive or interstitial.

An interstitial turn stops before an outcome and waits on the player. It carries a typed
kind, a ``deferred_action_id`` (the action it holds) and what it ``awaits``. The deferred
action is an obligation: its resolution is owed when the input arrives, and an interstitial
never chains onto another for the same action.

    kind              raised by  awaits              the deferred action
    roll_call         Kit        player_roll         the check Kit called (pending_check)
    clarify           Kit        player_answer       the action, re-prepared with the answer (ask_player)
    risk_confirm      Kit        confirmation        the risky act, once the player confirms
    reaction_window   engine     player_answer       the attack (or flight) the reaction could change
    flourish_window   engine     player_description  the rest of the round, after the kill

Kit-raised interstitials get structural checks only (the call cap, a question for the
player, no repeat of a confirmed risk). No style or floor check rejects them. The engine's
are committed without a model turn (kit_agent.commit_interstitial).
"""
import hashlib
import re

from .state_context import require

_LINE = {'type': 'string', 'minLength': 1, 'maxLength': 200}
RISK_CONFIRM_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'description': ('Before a risky act: state the perceptible fact that makes it risky and ask "are you '
                    'sure?" (scope call). Recorded; never warn about the same fact twice.'),
    'properties': {'fact': _LINE, 'action': _LINE}, 'required': ['fact', 'action']}
RISKS_KEPT = 12


def _id(turn_id, kind):
    return hashlib.sha256(f'{turn_id}:{kind}'.encode()).hexdigest()[:12]


def kit_kind(plan):
    """(kind, awaits) for a Kit-raised interstitial, or None for a substantive turn."""
    plan = plan or {}
    if plan.get('ask_player'):
        return 'clarify', 'player_answer'
    if plan.get('risk_confirm'):
        return 'risk_confirm', 'confirmation'
    if (plan.get('public_brief') or {}).get('scope') == 'call' and plan.get('roll_call'):
        return 'roll_call', 'player_roll'
    return None


def describe(plan, turn_id):
    found = kit_kind(plan)
    if not found:
        return {'turn_role': 'substantive'}
    kind, awaits = found
    return {'turn_role': 'interstitial',
            'interstitial': {'kind': kind, 'awaits': awaits, 'deferred_action_id': _id(turn_id, kind)}}


def _norm(text):
    return ' '.join(re.findall(r"[a-z0-9']+", str(text).casefold()))


def check_plan(plan, state):
    """Structure only. One interstitial per turn (no chaining), and a confirmed risk is never
    warned about again."""
    kinds = [key for key in ('ask_player', 'risk_confirm') if plan.get(key)]
    require(len(kinds) <= 1, 'One interstitial per turn: ask_player or risk_confirm, not both')
    block = plan.get('risk_confirm')
    if not block:
        return
    require(isinstance(block, dict) and set(block) == {'fact', 'action'} and
            all(isinstance(block[k], str) and 0 < len(block[k].strip()) <= 200 for k in block),
            'risk_confirm is {fact, action}: the perceptible fact and the act it makes risky')
    require(plan['public_brief']['scope'] == 'call', 'risk_confirm is a short beat: scope call')
    warned = {_norm(risk['fact']) for risk in (state or {}).get('risks_warned') or ()}
    require(_norm(block['fact']) not in warned,
            'That risk was already stated and the player chose; resolve the act now, do not warn again')


def check_spoken(segments, plan):
    """A Kit-raised interstitial ends on the player: it asks (clarify, risk_confirm) or calls
    the roll (roll_call is checked by kit_agenda's carrier check)."""
    found = kit_kind(plan)
    if found and found[0] in ('clarify', 'risk_confirm'):
        require(any('?' in segment['text'] for segment in segments),
                f'A {found[0]} turn asks the player; end on the question')


def risk_event(block, turn_id):
    return {'type': 'risk_warned', 'risk': {'fact': block['fact'].strip(), 'action': block['action'].strip(),
                                            'warned_turn': turn_id},
            'evidence': f"Kit stated the risk before the act: {block['fact'].strip()}"}


def apply(state, event):
    risk = event.get('risk')
    require(isinstance(risk, dict) and set(risk) == {'fact', 'action', 'warned_turn'} and
            all(isinstance(v, str) and v.strip() for v in risk.values()), 'risk_warned needs fact, action, turn')
    state['risks_warned'] = ((state.get('risks_warned') or []) + [risk])[-RISKS_KEPT:]
