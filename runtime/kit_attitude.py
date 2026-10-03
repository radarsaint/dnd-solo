"""NPC attitudes, behind-the-screen NPC checks, and the social-roll hook. Room-agnostic.

Brendon's live 6c notes (2026-10-03): the dealer need not be oblivious to the PC reading the
backs ("a behind the screen perception check on the dealer's part could change his
attitude"); a PC holding odd gear for a hidden edge invites a contested roll; a failed
social roll should change the pace. This module gives every NPC an attitude that moves:

- an attitude per actor (DMG scale: hostile, unfriendly, indifferent, friendly, helpful),
  from the source's ``attitudes.start``, else indifferent;
- hidden NPC checks: when a declared trigger fires, the first present NPC in ``by`` rolls a
  d20 + their skill behind the screen against the PC's passive ``vs`` skill (or the PC's
  stated roll in it); a success shifts attitudes. Neither the roll nor the result is public;
- the social-roll hook (``social_roll``): a resolved social check against an NPC moves that
  NPC's attitude, and their group's when the group follows. When to call for such a roll
  is the voice side's call; this is the engine hook it lands on.

Every change is one ``attitude_shift`` event (cause, per-actor from/to, and the hidden check
behind it, if any). Kit sees ``attitudes_here`` in the private context; the performer never
does. The source may declare one top-level ``attitudes`` block (all optional):

    attitudes:
      start: {<actor id>: <level>}
      groups: {<group id>: {members: [actor ids], follows: true}}
      social: {failure: -1, success: {<skill>: N}}       (defaults: failure -1, persuasion +1)
      npc_checks:
        <id>: {trigger: card_read | held_edge, by: [actor ids], skill: <npc skill>,
               vs: <pc skill>, shift: -1, actors: [actor ids] (default: the roller),
               note: "what they now believe (DM-only)"}

Triggers: card_read, the PC reads the marks, the backs, or the top card at a card game in
play; held_edge, at a card game in play the PC holds an item that gives them advantage
while held (the situation would have set it aside), so its edge has to be hidden. Each
check runs once per scene (area). No model calls; deterministic Python (seeded dice).
"""
import hashlib
import re

from .state_context import require

LEVELS = ('hostile', 'unfriendly', 'indifferent', 'friendly', 'helpful')
DEFAULT = 'indifferent'
TRIGGERS = ('card_read', 'held_edge')
TEXT_MAX = 200
GONE = ('dead', 'fled', 'unconscious', 'defeated', 'gone')
HISTORY = 4
# Reading the marked backs, the pinpricks, or the next card on the deck.
CARD_READ = re.compile(
    r"\b(read|reads|reading|count|counts|counting|eyes?|eyeing|glance\w*|drift\w*|stud(?:y|ies|ying)|watch\w*|"
    r"peek\w*|check\w*)\b[^.?!\"]{0,60}\b(pricks?|pinpricks?|marks|markings|backs?|the top card|top card|"
    r"the next card|corner of)\b")
# Saying it quietly, for one person: a private word is not a public scene.
QUIET = re.compile(r"\b(quietly|quiet|low voice|low,|under (?:his|her|their|my) breath|whisper\w*|leans? in|"
                   r"so only (?:he|she|they|the dealer) (?:can )?hears?|nobody else (?:needs to )?hears?|"
                   r"for (?:his|her|their) ears only|between us)\b")


def _text(value, label):
    require(isinstance(value, str) and 0 < len(value.strip()) <= TEXT_MAX, f'{label}: 1-{TEXT_MAX} characters')


def compile_attitudes(source):
    """The checked attitudes block ({} when the source declares none)."""
    from . import pc_sheet
    block = (source or {}).get('attitudes') or {}
    actors = (source or {}).get('actors') or {}
    require(isinstance(block, dict), 'attitudes: an object')
    for key, level in (block.get('start') or {}).items():
        require(key in actors and level in LEVELS, f'attitudes.start {key}: an actor and one of {", ".join(LEVELS)}')
    for gid, group in (block.get('groups') or {}).items():
        require(isinstance(group, dict) and isinstance(group.get('members'), list) and group['members'] and
                all(m in actors for m in group['members']) and type(group.get('follows', True)) is bool,
                f'attitudes.groups {gid}: members are actor ids; follows is a boolean')
    social = block.get('social') or {}
    require(type(social.get('failure', -1)) is int and -4 <= social.get('failure', -1) <= 0 and
            all(type(v) is int and -4 <= v <= 4 for v in (social.get('success') or {}).values()),
            'attitudes.social: failure -4..0, success {skill: -4..4}')
    for cid, check in (block.get('npc_checks') or {}).items():
        label = f'attitudes.npc_checks {cid}'
        require(isinstance(check, dict) and check.get('trigger') in TRIGGERS, f'{label}: trigger is one of {TRIGGERS}')
        require(isinstance(check.get('by'), list) and check['by'] and all(b in actors for b in check['by']),
                f'{label}: by lists actor ids')
        require(check.get('skill') in pc_sheet.SKILLS and check.get('vs') in pc_sheet.SKILLS,
                f'{label}: skill and vs are skills')
        require(type(check.get('shift', -1)) is int and -4 <= check.get('shift', -1) <= 4, f'{label}: shift -4..4')
        require(all(a in actors for a in check.get('actors', [])), f'{label}: actors are actor ids')
        _text(check.get('note'), f'{label} note')
    return block


def level(source, state, actor):
    held = ((state or {}).get('attitudes') or {}).get(actor)
    if held:
        return held['level']
    return (compile_attitudes(source).get('start') or {}).get(actor, DEFAULT)


def moved(current, by=0, to=None):
    if to:
        return to
    return LEVELS[max(0, min(len(LEVELS) - 1, LEVELS.index(current) + by))]


def _present(state):
    area = (state or {}).get('area')
    return {key for key, actor in ((state or {}).get('actors') or {}).items()
            if actor.get('location') == area and actor.get('status') not in GONE}


def shift_event(source, state, changes, cause, evidence, check=None):
    """One attitude_shift event for ``changes`` ({actor: by} or {actor: level name}), or None
    when nothing would change and no hidden check needs recording."""
    shifts = []
    for actor, by in changes.items():
        before = level(source, state, actor)
        after = moved(before, to=by) if isinstance(by, str) else moved(before, by)
        if after != before:
            shifts.append({'actor': actor, 'from': before, 'to': after})
    if not shifts and not check:
        return None
    event = {'type': 'attitude_shift', 'cause': cause[:TEXT_MAX], 'shifts': shifts, 'evidence': evidence}
    if check:
        event['check'] = check
    return event


def apply_event(state, source, event):
    actors = (source or {}).get('actors') or {}
    shifts = event.get('shifts')
    require(isinstance(shifts, list) and all(isinstance(s, dict) and s.get('actor') in actors and
                                             s.get('to') in LEVELS for s in shifts),
            'attitude_shift: shifts name actors and levels')
    require(isinstance(event.get('cause'), str) and event['cause'].strip(), 'attitude_shift: a cause')
    held = state.setdefault('attitudes', {})
    for item in shifts:
        entry = held.setdefault(item['actor'], {'level': level(source, state, item['actor']), 'history': []})
        entry['level'] = item['to']
        entry['history'] = (entry['history'] + [event['cause']])[-HISTORY:]
    check = event.get('check')
    if check:
        require(isinstance(check, dict) and check.get('id') in (compile_attitudes(source).get('npc_checks') or {}),
                'attitude_shift: check names a declared npc check')
        done = state.setdefault('npc_checks', {}).setdefault(state.get('area') or '', [])
        if check['id'] not in done:
            done.append(check['id'])


def attitudes_here(source, state):
    """DM-only: each present NPC's attitude and what last moved it, when anything is declared
    or has moved."""
    block = compile_attitudes(source)
    held = (state or {}).get('attitudes') or {}
    if not block and not held:
        return {}
    out = {}
    for actor in sorted(_present(state)):
        entry = {'attitude': level(source, state, actor)}
        if (held.get(actor) or {}).get('history'):
            entry['moved_by'] = held[actor]['history'][-1]
        out[actor] = entry
    return out


# -- the social-roll hook ------------------------------------------------------------
def group_of(source, actor):
    for group in (compile_attitudes(source).get('groups') or {}).values():
        if actor in group['members'] and group.get('follows', True):
            return [m for m in group['members'] if m != actor]
    return []


def social_roll(source, state, actor, skill, success, evidence, cause=None):
    """THE HOOK: a resolved social check against ``actor`` moves attitudes. A failure moves
    the actor and the present members of a following group (they watched it go wrong); a
    success moves only the actor, by the skill's success value (persuasion +1 by default).
    Returns a list of events (empty when nothing moves)."""
    social = compile_attitudes(source).get('social') or {}
    if success:
        by = (social.get('success') or {'persuasion': 1}).get(skill, 0)
        changes = {actor: by} if by else {}
    else:
        by = social.get('failure', -1)
        present = _present(state)
        changes = {who: by for who in [actor] + group_of(source, actor) if who in present} if by else {}
    name = skill.replace('_', ' ')
    event = shift_event(source, state, changes,
                        cause or f'the visitor\'s {name} {"worked on" if success else "failed against"} {actor}',
                        evidence)
    return [event] if event else []


# -- hidden NPC checks ------------------------------------------------------------------
def _card_game_running(state):
    return any(body.get('public', {}).get('player') is not None
               for body in ((state or {}).get('procedures') or {}).values() if isinstance(body, dict))


def _held_edges(state):
    """Items the PC holds that give advantage while held (by the PC's own word: the seated
    situation sets held gear aside)."""
    from . import pc_sheet
    sheet = pc_sheet.sheet_now(state)
    if not sheet:
        return []
    return sorted({e['source'] for e in sheet.get('advantage_on', [])
                   if isinstance(e, dict) and e.get('while') == 'held' and
                   pc_sheet.condition_true(sheet, e['source'], 'held')})


def triggered(trigger, action, state):
    """The trigger's subject (truthy) when it fires for this action in this state."""
    if not _card_game_running(state):
        return None
    if trigger == 'card_read':
        return 'card reading' if CARD_READ.search((action or '').casefold().replace('\u2019', "'")) else None
    if trigger == 'held_edge':
        return ', '.join(_held_edges(state)) or None
    return None


def npc_die(state, revision, label, action):
    material = f"{(state or {}).get('roll_seed', '')}:{revision}:npc:{label}:{(action or '').casefold()}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], 'big') % 20 + 1


def check_events(source, state, action, revision, pc_score, roll=None):
    """Behind-the-screen NPC checks this action triggers: a list of attitude_shift events.
    ``pc_score(skill, action)`` is the PC's number to beat (their stated roll in that skill,
    else their passive); ``roll()`` overrides the NPC's d20 (tests)."""
    from . import kit_claims
    block = compile_attitudes(source)
    done = ((state or {}).get('npc_checks') or {}).get((state or {}).get('area') or '', [])
    present = _present(state)
    events = []
    for cid, check in (block.get('npc_checks') or {}).items():
        if cid in done:
            continue
        subject = triggered(check['trigger'], action, state)
        roller = next((who for who in check['by'] if who in present), None)
        if not subject or roller is None:
            continue
        dc = pc_score(check['vs'], action)
        if dc is None:
            continue  # no PC number to beat (no sheet, no stated roll): no hidden check
        bonus = kit_claims.npc_skill(state['actors'][roller], check['skill'])
        die = roll() if roll else npc_die(state, revision, cid, action)
        total = die + bonus
        success = total >= dc
        skill, vs = check['skill'].replace('_', ' '), check['vs'].replace('_', ' ')
        evidence = (f'Behind the screen ({cid}, {subject}): {roller} {skill} d20 {die} + {bonus} = {total} vs '
                    f'the visitor\'s {vs} {dc}: {"noticed" if success else "missed it"}. Hidden; the NPC acts on it.')
        changes = {who: check.get('shift', -1) for who in (check.get('actors') or [roller]) if who in present} \
            if success else {}
        cause = check['note'] if success else f'missed: {check["note"]}'
        events.append(shift_event(source, state, changes, cause, evidence,
                                  check={'id': cid, 'by': roller, 'die': die, 'total': total, 'dc': dc,
                                         'success': success}))
    return events


def quiet(action):
    return bool(QUIET.search((action or '').casefold().replace('\u2019', "'")))
