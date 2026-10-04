"""One handoff rule (#102 review, unifying PR-F's functional floors with PR-H's reveal handoff).

A turn ends by giving the player the floor. Kit declares how in her decision, the same way she
declares ``handles`` on #97 (runtime/kit_acts.py there): an optional structured field the engine
validates, never English it guesses at to change the world.

``hands_off: {kind, reason}``, kind one of:

* ``question``: the turn ends on a question put to the PC: its last sentence ends with "?"
  and speaks to the PC (you/your), or is a short narrowing question ("Left or right?").
* ``check_call``: the last segment names a check (a skill or ability from the rules, initiative,
  a saving throw or an attack roll): "Roll Perception." "Make a Constitution saving throw."
* ``npc_challenge``: the focus actor speaks last outside Kit's remarks. Declared, any line of
  theirs counts ("Sit."); Kit has said it is a challenge. Undeclared, the engine only sees a
  line, not a sound ("Stay down." "Who sent you?"; not "Hm."), from any NPC; the exchange check
  still wants the focus actor's own move.
* ``combat_prompt``: the last sentence is a short address to the PC ("Your move.").
* ``none``: the floor passes without a prompt; ``reason`` says why (it answers the player's own
  look, a beat that needs no prompt). Never on a turn that must hand off (a room entry with a
  progressive reveal, PR-H).

Omitted, the engine accepts any of the four prompts it can see in the speech, or, on a turn
that answers the player's own look or inquiry (a reply_to quote on a look-type event), the
answer itself. Nothing here counts words or matches mood vocabulary: the checks read the
structure of the last segments and the rules' own check names.
"""
import re

from . import kit_guards, pc_sheet
from .state_context import InvalidChange, require

KINDS = ('question', 'check_call', 'npc_challenge', 'combat_prompt', 'none')
PROMPTS = KINDS[:-1]
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'properties': {'kind': {'type': 'string', 'enum': list(KINDS)},
                         'reason': {'type': 'string'}},
          'required': ['kind', 'reason']}
REASON_MAX_CHARS = 160
RULE = ('hands_off {kind, reason}: how this turn gives the player the floor. question (end on a question '
        'to the PC), check_call (name the check), npc_challenge (the focus NPC speaks last, something to '
        'answer), combat_prompt ("Your move."), or none with a reason (e.g. it answers their own look). '
        'Short is fine when it does the job; never pad.')
# Event kinds where the engine resolved the player's own look or inquiry: the answer hands the
# floor back by itself.
ANSWER_KINDS = ('observe', 'inspect_feature', 'threshold_look', 'check', 'called_check', 'knowledge',
                'lie_read')
SHORT_WORDS = 4      # a narrowing question or a combat prompt is a few words ("Left or right?", "Your move.")
_ABILITY_NAMES = ('strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma')
CHECK_NAMES = tuple(sorted({name.replace('_', ' ') for name in pc_sheet.SKILLS} | set(_ABILITY_NAMES) |
                           {'initiative', 'saving throw', 'death save', 'attack roll'}, key=len, reverse=True))
_CHECK = re.compile(r'\b(?:' + '|'.join(re.escape(name) for name in CHECK_NAMES) + r')\b', re.I)
_SECOND_PERSON = re.compile(r"\b(?:you|your|yours|yourself|you're|you'll|you'd)\b", re.I)
_WORD = re.compile(r"[\w’']+")


def _last_sentence(text):
    return (kit_guards.sentences(text) or [''])[-1]


def _words(text):
    return len(_WORD.findall(text or ''))


def is_question(segment):
    last = _last_sentence(segment.get('text'))
    return last.rstrip().rstrip('"”’\'').endswith('?') and \
        (bool(_SECOND_PERSON.search(last)) or _words(last) <= SHORT_WORDS)


def is_check_call(segment):
    return bool(_CHECK.search(segment.get('text') or ''))


def is_npc_line(segment, actor=None):
    """Undeclared (no actor): an NPC's line, not a sound. Declared (actor): the actor spoke."""
    speaker, text = segment.get('speaker'), (segment.get('text') or '').strip()
    if not kit_guards.is_npc(speaker) or (actor and speaker != actor) or not _WORD.search(text):
        return False
    return bool(actor) or _words(text) >= 2 or text.rstrip('"”’\'').endswith(('?', '!'))


def is_combat_prompt(segment):
    last = _last_sentence(segment.get('text'))
    return _words(last) <= SHORT_WORDS and bool(_SECOND_PERSON.search(last))


def _tail(segments):
    """The last segment, and the last segment outside Kit's remarks when Kit reacts after it."""
    if not segments:
        return []
    tail = [segments[-1]]
    others = [segment for segment in segments if segment.get('speaker') != 'Kit']
    if others and others[-1] is not segments[-1]:
        tail.append(others[-1])
    return tail


def shows(kind, segments, actor=None):
    tail = _tail(segments)
    if kind == 'question':
        return any(is_question(s) for s in tail)
    if kind == 'check_call':
        return bool(tail) and is_check_call(tail[0])
    if kind == 'npc_challenge':
        last_other = next((s for s in reversed(segments) if s.get('speaker') != 'Kit'), None)
        return last_other is not None and is_npc_line(last_other, actor)
    if kind == 'combat_prompt':
        return any(is_combat_prompt(s) for s in tail)
    return False


def declared(plan):
    value = (plan or {}).get('hands_off')
    if value is None:
        return None
    require(isinstance(value, dict) and set(value) == {'kind', 'reason'} and value.get('kind') in KINDS and
            isinstance(value.get('reason'), str) and len(value['reason']) <= REASON_MAX_CHARS,
            f'hands_off is {{kind, reason}}, kind one of {", ".join(KINDS)}, reason at most '
            f'{REASON_MAX_CHARS} characters')
    return value


def _fail(scope, detail=''):
    raise InvalidChange(
        f'{scope} scope does not end with handing the floor back to the player{detail}. End on a question '
        'to them, a check call that names the check, the focus NPC\'s line to answer, or a combat prompt; '
        'or declare hands_off none with a reason.')


def function(segments, plan, guards=None, required=False, scope=None):
    """(kind, reason) of how this turn gives the player the floor; raises InvalidChange when it
    does not. ``required``: a prompt is needed (none is refused), e.g. a progressive reveal."""
    guards = guards or {}
    scope = (scope or (plan.get('public_brief') or {}).get('scope') or 'This').capitalize()
    actor = guards.get('focus')
    value = declared(plan)
    if value and value['kind'] != 'none':
        if not shows(value['kind'], segments, actor if value['kind'] == 'npc_challenge' else None):
            _fail(scope, f' (hands_off says {value["kind"]}, and the last lines are not one)')
        return value['kind'], value['reason']
    if value:
        require(value['reason'].strip(), 'hands_off none needs a reason')
        if required:
            _fail(scope, ' (this turn must hand off: none is not enough)')
        return 'none', value['reason']
    for kind in PROMPTS:
        # Undeclared, any NPC's line to the PC hands over (check_scope still wants the focus
        # actor's own move); declared npc_challenge means the focus actor.
        if shows(kind, segments):
            return kind, 'seen in the speech'
    reply = str((plan.get('public_brief') or {}).get('reply_to') or 'none').strip().casefold()
    if not required and reply not in ('', 'none') and guards.get('kind') in ANSWER_KINDS:
        return 'none', 'answers the player\'s own look or inquiry'
    _fail(scope)
