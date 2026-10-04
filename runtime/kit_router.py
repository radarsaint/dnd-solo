"""Deterministic compute router (plan update #3, PR4). The engine, not a model, decides how
much a turn asks Kit to write: routine, normal or consequential. Same model on every tier.

Inputs, all known before Kit is called:
* action_kind: room entry, a way through, combat and table procedures are never routine;
* a pending ruling: a called check being set or rolled is quiet on its own (QUIET_EVENT_TYPES),
  so it is routine unless something else counts. A held description due this turn (a stall
  check's room, with or without the roll) is consequential;
* an important NPC: anyone present in the PC's area makes the turn at least normal; an NPC
  with a story hook here, or a card that sets speech_floor, makes it consequential. Someone
  only heard through a door counts as present only when the PC speaks (kit_agent.ADDRESSING).
  That is intended: a heard NPC can answer only what is said to them through the door, and
  listening or looking at the threshold stays routine;
* the active brief: a due hook (story_due) or open threads now due are consequential;
* a state change: any resolved event other than a rhythm beat or a cleared check
  (a move, an attitude shift, a learned claim, a threshold crossed) is consequential.

Routine turns may leave out the private bookkeeping (appraisal, mood read, player note, tone,
memory refs, turn mode, the story/actor tags); the engine fills neutral values. Kit still
writes her move, kit_choice, the brief and the speech: her judgment is never defaulted.

Effort: the host this repo uses (a ChatGPT custom GPT) exposes no reasoning-effort or model
setting to the runtime, so the router controls only what Kit must write, plus one line telling
her the turn is routine. A host that has an effort knob may map the tier onto it.
"""
import copy

TIERS = ('routine', 'normal', 'consequential')
# A social declaration with nobody here to answer it is routine; with someone here it is not.
NEVER_ROUTINE_KINDS = ('opening', 'exit', 'combat_round', 'combat_flourish', 'social_check', 'lie_read',
                       'exit_contested', 'toll_defer')
QUIET_EVENT_TYPES = ('beat', 'pending_check')
ROUTINE_DEFAULTS = {
    'appraisal': {'label': 'none', 'intensity': 0, 'cause': 'A routine turn: nothing here moves Kit.',
                  'goal_effect': 'neutral', 'target': 'scene'},
    'memory_refs': [],
    'tone': 'plain',
    'player_note': {'note': 'none', 'evidence_turns': [], 'replaces': 'none'},
    'player_mood': {'read': 'neutral', 'cue': 'none'},
}
ROUTINE_READ_DEFAULTS = {'story_anchor': 'none', 'story_basis': 'none', 'actor_ref': 'none', 'actor_basis': 'none'}


def route(kind, events, state, speakers=(), important=(), due=(), threads_due=False, held=False):
    """{'tier', 'why': [...], 'may_omit': [...]} for one turn. Pure: same inputs, same tier."""
    why = []
    if kind == 'opening':
        why.append('room entry')
    if held:
        why.append('a held description is due')
    if due:
        why.append('a due hook lands')
    if threads_due:
        why.append('open threads are due')
    changed = sorted({event.get('type') for event in events or ()} - set(QUIET_EVENT_TYPES))
    if changed:
        why.append('state changes: ' + ', '.join(changed))
    if set(important) & set(speakers):
        why.append('an important NPC is here: ' + ', '.join(sorted(set(important) & set(speakers))))
    if why:
        return {'tier': 'consequential', 'why': why, 'may_omit': []}
    if kind in NEVER_ROUTINE_KINDS:
        return {'tier': 'normal', 'why': [f'{kind} turn'], 'may_omit': []}
    if speakers:
        return {'tier': 'normal', 'why': ['someone is here: ' + ', '.join(sorted(speakers))], 'may_omit': []}
    return {'tier': 'routine', 'why': ['no one here, nothing changes, nothing due'],
            'may_omit': sorted(ROUTINE_DEFAULTS) + ['turn_mode'] + [f'improv_read.{k}' for k in ROUTINE_READ_DEFAULTS]}


def fill_routine(plan, turn_mode):
    """The neutral values a routine turn may leave out. Kit's own choices are never filled."""
    for key, value in ROUTINE_DEFAULTS.items():
        plan.setdefault(key, copy.deepcopy(value))
    plan.setdefault('turn_mode', turn_mode)
    read = plan.get('improv_read')
    if isinstance(read, dict):
        for key, value in ROUTINE_READ_DEFAULTS.items():
            read.setdefault(key, value)
    return plan
