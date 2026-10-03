"""The room's story brief: what this scene is about, built from the room data. Room-agnostic.

Kit read area 6c as a list of mechanics and never worked out what the scene was for: the
vampire act exists to scare newcomers into paying the toll, yet the toll never came up.
The brief fixes that with one deterministic mechanism. On entering an area (and on every
turn there, until the scene moves on), prepare assembles from the room source:

- who is present, what each wants, and their personality traits;
- what the setup is for (the purpose behind an act, a con, a rigged game);
- the primary hooks, each flagged while it is still undelivered;
- thresholds (when an NPC's attitude turns) and the scene's possible endings.

It reaches only the private decision input (``story_brief``), beside Kit's running plan;
plan beats may cite its hooks as roots (``hook:<id>``). It is never sent to the performer.

An undelivered primary hook does not wait for the player to find it: after
``within_beats`` turns in the scene its NPC raises it in character (``raise_now``), and a
performance that lets it slide is rejected (``check_raised``) unless that NPC is gone or
a fight is running. Delivery latches in state['story'][area] via the ``story_beat`` event
each committed turn carries.

The source may declare, per area, a ``story`` block (all fields optional):

    story:
      <area id>:
        about: "what the scene is about (DM-only)"
        purposes: [{what, for, roots: [fact | claim | actor ids]}]
        hooks: [{id, text, primary: bool, by: <actor id>, within_beats: N, roots,
                 delivered_when: <condition>}]
        thresholds: [{when, then, roots}]
        endings: ["..."]

Conditions: {toll_raised: <toll id>}, {procedure_running: <procedure id>},
{fact_known: <fact id>}, {claim_learned: <claim id>},
{said: {by: [actor ids], any: [phrases]}} (an NPC line this turn), {any: [conditions]}.
A hook's ``text`` is said to the performer when it is overdue, so it must be public-safe:
it is checked against the room's leak phrases and keyword sets.

Actors may carry ``traits`` (from the source). Without a story block the brief still comes
from what the room has: actor motives and goals, agenda wants and pressures, the level's
pressure here, and retreat conditions as endings.
No model calls; deterministic Python.
"""

import re

from .state_context import InvalidChange, require

TEXT_MAX = 300
MAX_ITEMS = 6  # per list (purposes, hooks, thresholds, endings, an actor's traits): the brief stays ~5 KB
DEFAULT_WITHIN = 3
MAX_WITHIN = 12
GONE = ('dead', 'fled', 'unconscious', 'defeated', 'gone')
CONDITIONS = ('toll_raised', 'procedure_running', 'fact_known', 'claim_learned', 'said', 'any')
HOOK_ID = re.compile(r'^[a-z0-9_]{1,32}$')
BRIEF_RULE = ('Private story brief for this scene, from the room source. Play toward it every '
              'turn: the NPCs pursue what they want rather than wait to be asked; an act or con '
              'serves its purpose; a hook in raise_now is raised this turn, in character, by its '
              'NPC. Never narrate the brief itself or any secret in it.')


def _text(value, label, limit=TEXT_MAX):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, f'{label}: 1-{limit} characters')


def _roots(roots, source, label):
    require(isinstance(roots, list) and all(
        isinstance(r, str) and (r in source.get('facts', {}) or r in (source.get('claims') or {}) or
                                r in source.get('actors', {}) or r in (source.get('tolls') or {}) or
                                r in (source.get('procedures') or {}))
        for r in roots), f'{label}: roots cite facts, claims, actors, tolls, or procedures')


def _check_condition(cond, source, label):
    require(isinstance(cond, dict) and len(cond) == 1 and next(iter(cond)) in CONDITIONS,
            f'{label}: one condition of {", ".join(CONDITIONS)}')
    kind, value = next(iter(cond.items()))
    if kind == 'any':
        require(isinstance(value, list) and value, f'{label}: any lists conditions')
        for item in value:
            _check_condition(item, source, label)
    elif kind == 'said':
        require(isinstance(value, dict) and isinstance(value.get('any'), list) and value['any'] and
                all(isinstance(p, str) and p.strip() for p in value['any']) and
                isinstance(value.get('by'), list) and value['by'] and
                all(b in source.get('actors', {}) for b in value['by']),
                f'{label}: said needs by (actor ids) and any (phrases)')
    else:
        pools = {'toll_raised': source.get('tolls') or {}, 'procedure_running': source.get('procedures') or {},
                 'fact_known': source.get('facts') or {}, 'claim_learned': source.get('claims') or {}}
        require(value in pools[kind] and not str(value).startswith('_'), f'{label}: unknown {kind} {value!r}')


def _public_safe(text, source, label):
    from . import kit_guards
    folded = text.casefold()
    for phrase in kit_guards.leak_phrases(source)['phrases']:
        require(phrase not in folded, f'{label}: hook text is said to the performer; it names a secret')
    try:
        kit_guards.check_paraphrased_leaks(text, '', '', kit_guards.leak_sets(source))
    except InvalidChange as exc:
        raise InvalidChange(f'{label}: hook text is said to the performer; {exc}') from exc


def compile_story(source):
    """The checked per-area story blocks ({} when the source declares none)."""
    block = (source or {}).get('story') or {}
    stories = {}
    for area, story in block.items():
        if area.startswith('_'):
            continue
        label = f'story {area}'
        require(area in source.get('areas', {}), f'{label}: unknown area')
        require(isinstance(story, dict), f'{label}: an object')
        for key in ('purposes', 'hooks', 'thresholds', 'endings'):
            require(isinstance(story.get(key, []), list) and len(story.get(key, [])) <= MAX_ITEMS,
                    f'{label} {key}: a list of at most {MAX_ITEMS}')
        if 'about' in story:
            _text(story['about'], f'{label} about')
        for index, item in enumerate(story.get('purposes') or ()):
            _text(item.get('what'), f'{label} purpose {index} what')
            _text(item.get('for'), f'{label} purpose {index} for')
            _roots(item.get('roots', []), source, f'{label} purpose {index}')
        seen = set()
        for hook in story.get('hooks') or ():
            hid = hook.get('id')
            require(isinstance(hid, str) and HOOK_ID.match(hid) and hid not in seen, f'{label}: hook ids unique')
            seen.add(hid)
            _text(hook.get('text'), f'{label} hook {hid} text')
            require(type(hook.get('primary', False)) is bool, f'{label} hook {hid}: primary is a boolean')
            require(hook.get('by') in source.get('actors', {}), f'{label} hook {hid}: by names an actor')
            within = hook.get('within_beats', DEFAULT_WITHIN)
            require(type(within) is int and 1 <= within <= MAX_WITHIN, f'{label} hook {hid}: within_beats 1-{MAX_WITHIN}')
            _check_condition(hook.get('delivered_when'), source, f'{label} hook {hid}')
            _roots(hook.get('roots', []), source, f'{label} hook {hid}')
            _public_safe(hook['text'], source, f'{label} hook {hid}')
        for index, item in enumerate(story.get('thresholds') or ()):
            _text(item.get('when'), f'{label} threshold {index} when')
            _text(item.get('then'), f'{label} threshold {index} then')
            _roots(item.get('roots', []), source, f'{label} threshold {index}')
        for index, ending in enumerate(story.get('endings') or ()):
            _text(ending, f'{label} ending {index}')
        stories[area] = story
    for key, actor in (source.get('actors') or {}).items():
        traits = actor.get('traits')
        require(traits is None or (isinstance(traits, list) and len(traits) <= MAX_ITEMS and
                                   all(isinstance(t, str) and 0 < len(t.strip()) <= TEXT_MAX for t in traits)),
                f'Actor {key}: traits is a list of at most {MAX_ITEMS} short strings')
    return stories


def story_state(state, area):
    return ((state or {}).get('story') or {}).get(area) or {'beats': 0, 'delivered': []}


def _present(source, state):
    area = state.get('area')
    return {key: actor for key, actor in (state.get('actors') or {}).items()
            if actor.get('location') == area and actor.get('status') not in GONE}


def _spoken_by(spoken, source):
    """{actor id: [their lines]} from a turn's spoken text."""
    from .kit_agent import actor_speakers
    labels = {label: key for key, label in actor_speakers(source).items()}
    lines = {}
    for line in (spoken or '').splitlines():
        speaker, _, text = line.partition(':')
        if speaker.strip() in labels:
            lines.setdefault(labels[speaker.strip()], []).append(text)
    return lines


def holds(cond, source, state, spoken=''):
    """True when the condition is met in ``state`` or by this turn's ``spoken`` lines."""
    kind, value = next(iter(cond.items()))
    if kind == 'any':
        return any(holds(item, source, state, spoken) for item in value)
    if kind == 'said':
        lines = _spoken_by(spoken, source)
        text = ' '.join(' '.join(lines.get(who, ())) for who in value['by']).casefold()
        return any(re.search(r'\b' + re.escape(p.casefold()) + r'\b', text) for p in value['any'])
    if kind == 'toll_raised':
        from . import kit_toll
        body = (kit_toll.here(source, state).get(value) or (None, {}))[1] if state.get('area') else {}
        if body and body.get('status') != 'not_raised':
            return True
        return bool(spoken) and kit_toll.names_toll(source, value, spoken)
    if kind == 'procedure_running':
        return value in (state.get('procedures') or {})
    if kind == 'fact_known':
        return value in (state.get('known_facts') or ())
    return value in ((state.get('claims') or {}).get('learned') or ())


def _fighting(state):
    return (state.get('combat') or {}).get('status') in ('awaiting_initiative', 'running')


def brief(source, state):
    """The private story brief for the current area (always a dict; sparse rooms give a
    sparse brief)."""
    from .kit_agent import actor_speakers
    source, state = source or {}, state or {}
    area = state.get('area')
    story = compile_story(source).get(area) or {}
    labels = actor_speakers(source)
    present = _present(source, state)
    agents = ((source.get('agenda') or {}).get('agents') or {})
    wants_by_actor = {agent.get('actor'): agent.get('wants') for agent in agents.values()
                      if isinstance(agent, dict) and agent.get('actor')}
    people = []
    for key, actor in present.items():
        traits = list(actor.get('traits') or [])
        if not traits:
            profile = actor.get('communication_profile') or {}
            traits = [f'{k}: {v}' for k, v in profile.items() if isinstance(v, str) and v != 'Unestablished']
        wants = [w for w in (actor.get('motive'), actor.get('immediate_goal'), wants_by_actor.get(key)) if w]
        people.append({'actor': key, 'label': labels.get(key) or actor.get('name') or key,
                       'wants': wants or ['Unstated in the source: infer from the room, never invent a secret.'],
                       'traits': traits})
    mem = story_state(state, area)
    hooks, raise_now = [], []
    for hook in story.get('hooks') or ():
        delivered = hook['id'] in mem['delivered'] or holds(hook['delivered_when'], source, state)
        within = hook.get('within_beats', DEFAULT_WITHIN)
        entry = {'id': hook['id'], 'text': hook['text'], 'primary': hook.get('primary', False),
                 'by': labels.get(hook['by'], hook['by']), 'delivered': delivered}
        if not delivered:
            entry['beats_waiting'] = mem['beats']
            entry['raise_by_beat'] = within
            if hook.get('primary') and mem['beats'] >= within and hook['by'] in present and not _fighting(state):
                raise_now.append(hook['id'])
        hooks.append(entry)
    thresholds = [{'when': t['when'], 'then': t['then']} for t in story.get('thresholds') or ()]
    for key, clock in ((source.get('agenda') or {}).get('pressures') or {}).items():
        if isinstance(clock, dict) and clock.get('when_full'):
            thresholds.append({'when': f'{key} fills: {clock.get("ticks_on", "")}'.strip(), 'then': clock['when_full']})
    endings = list(story.get('endings') or ())
    if not endings:
        endings = ['The player leaves the scene.'] + [
            f'{labels.get(key) or actor.get("name") or key}: {actor["retreat_condition"]}'
            for key, actor in present.items() if actor.get('retreat_condition')]
    about = story.get('about') or (source.get('level_context') or {}).get('pressure_here') or \
        ((source.get('areas') or {}).get(area) or {}).get('name')
    return {'rule': BRIEF_RULE, 'area': area, 'about': about, 'beats_in_scene': mem['beats'],
            'present': people,
            'purposes': [{'what': p['what'], 'for': p['for']} for p in story.get('purposes') or ()],
            'hooks': hooks, 'raise_now': raise_now, 'thresholds': thresholds, 'endings': endings}


def due_hooks(source, state):
    """The hooks an NPC must raise this turn: [{id, text, by (label)}]."""
    made = brief(source, state)
    return [{'id': h['id'], 'text': h['text'], 'by': h['by']} for h in made['hooks'] if h['id'] in made['raise_now']]


def check_raised(due, source, state, spoken):
    """HARD: an overdue primary hook is raised this turn by its NPC, in character."""
    story = compile_story(source).get((state or {}).get('area')) or {}
    by_id = {hook['id']: hook for hook in story.get('hooks') or ()}
    for item in due or ():
        hook = by_id.get(item['id'])
        if hook and not holds(hook['delivered_when'], source, state, spoken):
            raise InvalidChange(
                f'Story hook overdue: the {item["by"]} raises it this turn, in character, as their own '
                f'move (not the Narrator): {item["text"]}')


def beat_event(source, state, spoken, turn_id):
    """The per-turn record for an area with a story block: one more beat, and the hooks
    delivered by now (latched). None when the area has no story block."""
    area = (state or {}).get('area')
    story = compile_story(source).get(area)
    if not story:
        return None
    mem = story_state(state, area)
    delivered = [hook['id'] for hook in story.get('hooks') or ()
                 if hook['id'] in mem['delivered'] or holds(hook['delivered_when'], source, state, spoken)]
    return {'type': 'story_beat', 'area': area, 'delivered': delivered,
            'evidence': f'Story beat in {area} with turn {turn_id}; delivered: '
                        f'{", ".join(delivered) or "none"}.'}


def apply_event(state, source, event):
    area = event.get('area')
    story = compile_story(source).get(area)
    require(story is not None, 'story_beat needs a story block for its area')
    hooks = {hook['id'] for hook in story.get('hooks') or ()}
    delivered = event.get('delivered')
    require(isinstance(delivered, list) and set(delivered) <= hooks, 'story_beat delivered names hook ids')
    mem = state.setdefault('story', {}).setdefault(area, {'beats': 0, 'delivered': []})
    mem['beats'] += 1
    mem['delivered'] = sorted(set(mem['delivered']) | set(delivered))
