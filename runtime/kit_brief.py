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
a fight is running. Delivery latches in state['story'][area] for the open scene (scene_key) via the ``story_beat`` event
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

A threshold may also carry a machine ``trigger`` (a condition) and a ``shift`` ({actors,
by: N} or {actors, to: <attitude>}): when the trigger holds after a turn the threshold is
crossed (``threshold_crossed``, latched once per scene), the shift moves those NPCs'
attitudes (runtime/kit_attitude.py), and the brief marks it ``crossing_now`` the turn it
holds so Kit plays toward its ``then`` from this turn on: an agenda transition, not an
automatic outcome. State-only conditions for triggers:
{net_at_least: {procedure, gp}} (the PC is up that much at that table),
{wins_running: {procedure, count}}, {won_round: {procedure, gp}} (the last round settled
was a win of at least gp), {since_noticed: {procedure, check, wins, net_gp}} (since that
hidden NPC check noticed the PC this scene: at least ``wins`` wins with a net gain, or a net
gain of ``net_gp``; one win does not do it), {broke: <procedure>} (the buy-in, else the
sheet's gold_gp, is gone), {toll_refused: <toll id>}, {exposed: <procedure>} (a cheat called out with proof, in front of
the table), {actor_damaged: <actor id>}, {attitude_at_most: {actor, level}}.

Conditions: {toll_raised: <toll id>}, {procedure_running: <procedure id>},
{fact_known: <fact id>}, {claim_learned: <claim id>},
{said: {by: [actor ids], any: [phrases], game: <procedure id>}} (an NPC line this turn; a
phrase "a + b" needs both in the same line; game adds that procedure's own names: its
``called`` list, else its name up to "(" or ","; a ``paired`` phrase ("a hand", "want in")
counts only when the rest of the line has a game word or the game's name: "join us for a
hand" counts, "give me a hand with this lantern" does not), {any: [conditions]}.
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
BRIEF_MAX_BYTES = 5000  # the compiled brief; longer lists are trimmed from the end
MAX_ITEMS = 6  # per list (purposes, hooks, thresholds, endings, an actor's traits): the brief stays ~5 KB
DEFAULT_WITHIN = 3
MAX_WITHIN = 12
GONE = ('dead', 'fled', 'unconscious', 'defeated', 'gone')
CONDITIONS = ('toll_raised', 'procedure_running', 'fact_known', 'claim_learned', 'said', 'any',
              # state-only conditions for thresholds (never speakable):
              'net_at_least', 'broke', 'toll_refused', 'exposed', 'actor_damaged', 'attitude_at_most',
              'wins_running', 'won_round', 'since_noticed')
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
                all(b in source.get('actors', {}) for b in value['by']) and
                all(part.strip() for p in value['any'] for part in p.split('+')) and
                isinstance(value.get('paired', []), list) and
                all(isinstance(p, str) and p.strip() for p in value.get('paired', [])) and
                set(value) <= {'by', 'any', 'game', 'paired', 'challenge'} and
                value.get('challenge', False) in (True, False) and
                ('game' not in value or value['game'] in (source.get('procedures') or {})),
                f'{label}: said needs by (actor ids) and any (phrases; "a + b" both in one line), '
                'game names a procedure, and challenge is true or false')
    elif kind == 'net_at_least':
        require(isinstance(value, dict) and value.get('procedure') in (source.get('procedures') or {}) and
                type(value.get('gp')) is int and value['gp'] > 0, f'{label}: net_at_least needs procedure and gp')
    elif kind == 'wins_running':
        require(isinstance(value, dict) and value.get('procedure') in (source.get('procedures') or {}) and
                type(value.get('count')) is int and value['count'] >= 2, f'{label}: wins_running needs procedure and count (2+)')
    elif kind == 'won_round':
        require(isinstance(value, dict) and set(value) == {'procedure', 'gp'} and
                value['procedure'] in (source.get('procedures') or {}) and
                type(value['gp']) is int and value['gp'] > 0, f'{label}: won_round needs procedure and gp')
    elif kind == 'since_noticed':
        from .kit_attitude import compile_attitudes
        require(isinstance(value, dict) and value.get('procedure') in (source.get('procedures') or {}) and
                value.get('check') in (compile_attitudes(source).get('npc_checks') or {}) and
                type(value.get('wins')) is int and value['wins'] >= 2 and
                type(value.get('net_gp')) is int and value['net_gp'] > 0,
                f'{label}: since_noticed needs procedure, check (an npc check), wins (2+), and net_gp')
    elif kind in ('broke', 'exposed'):
        require(value in (source.get('procedures') or {}), f'{label}: {kind} names a procedure')
    elif kind == 'toll_refused':
        require(value in (source.get('tolls') or {}), f'{label}: toll_refused names a toll')
    elif kind == 'actor_damaged':
        require(value in source.get('actors', {}), f'{label}: actor_damaged names an actor')
    elif kind == 'attitude_at_most':
        from .kit_attitude import LEVELS
        require(isinstance(value, dict) and value.get('actor') in source.get('actors', {}) and
                value.get('level') in LEVELS, f'{label}: attitude_at_most needs actor and level')
    else:
        pools = {'toll_raised': source.get('tolls') or {}, 'procedure_running': source.get('procedures') or {},
                 'fact_known': source.get('facts') or {}, 'claim_learned': source.get('claims') or {}}
        require(value in pools[kind] and not str(value).startswith('_'), f'{label}: unknown {kind} {value!r}')


SPOKEN_CONDITIONS = ('said', 'toll_raised')


def speakable(cond):
    """True when an NPC line alone can meet the condition (said or toll_raised, directly or
    inside any): the only kind a hook forced through raise_now can be held to."""
    kind, value = next(iter(cond.items()))
    if kind == 'any':
        return any(speakable(item) for item in value)
    return kind in SPOKEN_CONDITIONS


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
            # An NPC raises an overdue primary hook by speaking; a condition speech cannot meet
            # (only fact_known, claim_learned, procedure_running) would reject every turn.
            require(not hook.get('primary') or speakable(hook['delivered_when']),
                    f'{label} hook {hid}: a primary hook is delivered by what an NPC says '
                    '(said or toll_raised, directly or inside any)')
            _roots(hook.get('roots', []), source, f'{label} hook {hid}')
            _public_safe(hook['text'], source, f'{label} hook {hid}')
        for index, item in enumerate(story.get('thresholds') or ()):
            _text(item.get('when'), f'{label} threshold {index} when')
            _text(item.get('then'), f'{label} threshold {index} then')
            _roots(item.get('roots', []), source, f'{label} threshold {index}')
            if 'trigger' in item:
                _check_condition(item['trigger'], source, f'{label} threshold {index} trigger')
            if 'shift' in item:
                from .kit_attitude import LEVELS
                shift = item['shift']
                require(isinstance(shift, dict) and isinstance(shift.get('actors'), list) and shift['actors'] and
                        all(a in source.get('actors', {}) for a in shift['actors']) and
                        ((type(shift.get('by')) is int and -4 <= shift['by'] <= 4) != (shift.get('to') in LEVELS)),
                        f'{label} threshold {index} shift: actors and one of by (-4..4) or to (an attitude)')
                require('trigger' in item, f'{label} threshold {index}: a shift needs a trigger')
        for index, ending in enumerate(story.get('endings') or ()):
            _text(ending, f'{label} ending {index}')
        stories[area] = story
    for key, actor in (source.get('actors') or {}).items():
        traits = actor.get('traits')
        require(traits is None or (isinstance(traits, list) and len(traits) <= MAX_ITEMS and
                                   all(isinstance(t, str) and 0 < len(t.strip()) <= TEXT_MAX for t in traits)),
                f'Actor {key}: traits is a list of at most {MAX_ITEMS} short strings')
    return stories


from .state_context import FIRST_SCENE  # noqa: E402  (the first scene, KRABS §8)


def scene_key(state):
    """The open scene (state_context.current_scene, KRABS §8). Story memory (beats, delivered
    hooks, crossed thresholds) and hidden NPC checks belong to one scene: after scene_close a
    later scene in the same area starts fresh, so its hooks and checks re-arm."""
    from .state_context import current_scene
    return current_scene(state)


def story_state(state, area):
    mem = ((state or {}).get('story') or {}).get(area)
    if not mem or mem.get('scene', FIRST_SCENE) != scene_key(state):
        return {'beats': 0, 'delivered': []}
    return mem


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
        said = [line.casefold().replace('\u2019', "'") for who in value['by'] for line in lines.get(who, ())]
        names = game_names((source.get('procedures') or {}).get(value['game'])) if value.get('game') else []
        # challenge: any question the actor puts to the PC is the challenge, however it is
        # worded ("Who goes there?"), as the room's hook says (watchroom playtest).
        return any(_says(line, phrase) for line in said for phrase in said_phrases(value, source)) or \
            any(_paired(line, phrase, names) for line in said for phrase in value.get('paired', ())) or \
            bool(value.get('challenge')) and any('?' in line for line in said)
    if kind == 'toll_raised':
        from . import kit_toll
        body = (kit_toll.here(source, state).get(value) or (None, {}))[1] if state.get('area') else {}
        if body and body.get('status') != 'not_raised':
            return True
        return bool(spoken) and kit_toll.names_toll(source, value, spoken)
    if kind == 'procedure_running':
        return value in (state.get('procedures') or {})
    if kind in ('wins_running', 'won_round'):
        public = ((state.get('procedures') or {}).get(value['procedure']) or {}).get('public') or {}
        if kind == 'wins_running':
            return (public.get('player') or {}).get('streak', 0) >= value['count']
        last = public.get('last_result') or {}
        return last.get('outcome') == 'win' and (last.get('stake') or 0) >= value['gp']
    if kind == 'since_noticed':
        from . import kit_attitude
        since = kit_attitude.since_noticed(state, value['check'], value['procedure'])
        if since is None:
            return False
        wins, net = since
        return (wins >= value['wins'] and net > 0) or net >= value['net_gp']
    if kind in ('net_at_least', 'broke', 'exposed'):
        key = value['procedure'] if kind == 'net_at_least' else value
        public = ((state.get('procedures') or {}).get(key) or {}).get('public') or {}
        player = public.get('player') or {}
        if kind == 'net_at_least':
            return player.get('net', 0) >= value['gp']
        if kind == 'broke':
            # The buy-in, else the gold on the PC's sheet when no buy-in was declared.
            purse = player.get('purse')
            if purse is None:
                gold = (state.get('player_sheet') or {}).get('gold_gp')
                purse = gold if type(gold) is int else None
            return bool(player) and purse is not None and purse + player.get('net', 0) <= 0
        return any(item.get('backed') for item in public.get('accusations') or ())
    if kind == 'toll_refused':
        from . import kit_toll
        body = (kit_toll.here(source, state).get(value) or (None, {}))[1] if state.get('area') else {}
        return (body or {}).get('status') == 'refused'
    if kind == 'actor_damaged':
        fight = state.get('combat') or {}
        hp, full = fight.get('hp') or {}, fight.get('max_hp') or {}
        return value in hp and hp[value] < full.get(value, hp[value]) or \
            ((state.get('actors') or {}).get(value) or {}).get('status') in ('dead', 'unconscious')
    if kind == 'attitude_at_most':
        from . import kit_attitude
        from .kit_attitude import LEVELS
        return LEVELS.index(kit_attitude.level(source, state, value['actor'])) <= LEVELS.index(value['level'])
    if kind == 'fact_known':
        return value in (state.get('known_facts') or ())
    return value in ((state.get('claims') or {}).get('learned') or ())


def game_names(config):
    """A procedure's own names, as an NPC would say them (kit_cards.game_names: its ``called``
    list, else its name up to "(" or ",")."""
    from . import kit_cards
    return list(kit_cards.game_names(config))


def said_phrases(value, source):
    """The phrases a said condition accepts: its own plus the named game's names."""
    game = value.get('game')
    return list(value['any']) + (game_names((source.get('procedures') or {}).get(game)) if game else [])


def _paired(line, phrase, names=()):
    """The phrase is in the line and the rest of the line has a game word or the game's name."""
    from .kit_toll import TOLL_GAME_WORDS  # the shared game-word list
    pattern = r'\b' + re.escape(phrase.strip().casefold()) + r'\b'
    if not re.search(pattern, line):
        return False
    rest = re.sub(pattern, ' ', line)
    return bool(TOLL_GAME_WORDS.search(rest)) or any(re.search(r'\b' + re.escape(n) + r'\b', rest) for n in names)


def _says(line, phrase):
    """One line says the phrase; "a + b" needs each part in that same line."""
    return all(re.search(r'\b' + re.escape(part.strip().casefold()) + r'\b', line) for part in phrase.split('+'))


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
    from .kit_rooms import resolution, stage
    where = stage(source, state)
    tease = ((source.get('areas') or {}).get(area) or {}).get('tease') if where == 'approach' else None
    live = state.get('actors') or {}
    heard = heard_here(source, state)
    present = {**present, **{key: live[key] for key in heard if key not in present}}
    people = []
    for key, actor in present.items():
        if key in heard and key not in _present(source, state):
            # Tease-only approach (Brendon, 2026-10-04): someone inside is only what reaches
            # the doorway, never their card, wants, or secrets.
            people.append({'actor': key, 'label': labels.get(key) or actor.get('name') or key, 'heard': heard[key]})
            continue
        traits = list(actor.get('traits') or [])
        if not traits:
            profile = actor.get('communication_profile') or {}
            traits = [f'{k}: {v}' for k, v in profile.items() if isinstance(v, str) and v != 'Unestablished']
        wants = [w for w in (actor.get('motive'), actor.get('immediate_goal'), wants_by_actor.get(key)) if w]
        people.append({'actor': key, 'label': labels.get(key) or actor.get('name') or key,
                       'wants': wants or ['Unstated in the source: infer from the room, never invent a secret.'],
                       'traits': traits, **({'heard': heard[key]} if key in heard else {})})
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
    thresholds = []
    for index, item in enumerate(story.get('thresholds') or ()):
        entry = {'when': item['when'], 'then': item['then']}
        if index in mem.get('crossed', ()):
            entry['crossed'] = True
        elif item.get('trigger') and holds(item['trigger'], source, state):
            entry['crossing_now'] = True  # Kit plays toward its then, starting this turn
        thresholds.append(entry)
    for key, clock in ((source.get('agenda') or {}).get('pressures') or {}).items():
        if isinstance(clock, dict) and clock.get('when_full'):
            thresholds.append({'when': f'{key} fills: {clock.get("ticks_on", "")}'.strip(), 'then': clock['when_full']})
    endings = list(story.get('endings') or ())
    if (source.get('areas') or {}).get(area, {}).get('outside') and not story:
        # Outside the room (stage approach or resolution): going in and going past are both
        # ways this ends (ROOM_LOADER.md: a bypass is a resolution).
        endings = ['The player goes in.', 'The player goes past without going in.']
    if not endings:
        endings = ['The player leaves the scene.'] + [
            f'{labels.get(key) or actor.get("name") or key}: {actor["retreat_condition"]}'
            for key, actor in present.items() if actor.get('retreat_condition')]
    about = (tease or {}).get('text') or story.get('about') or \
        (source.get('level_context') or {}).get('pressure_here') or ((source.get('areas') or {}).get(area) or {}).get('name')
    if tease:
        # The doorway (Brendon's ruling): what reaches the PC from outside, pointing at the hook
        # inside, and who is heard there. Kit plays toward the hook from out here.
        pointed = next((hook for story_area in compile_story(source).values() for hook in story_area.get('hooks') or ()
                        if hook['id'] == tease.get('points_to')), None)
        # Tease-only (Brendon, 2026-10-04): the hook is named by id, never by its inside text.
        tease = {'text': tease['text'], 'points_to': tease.get('points_to') if pointed else None}
    frame = approach_frame(source, state, story) if where == 'approach' else {}
    made = {'rule': BRIEF_RULE, 'area': area, 'stage': where, 'about': about,
            **({'tease': tease} if tease else {}), **frame,
            **({'resolved': resolution(source, state)} if where == 'resolution' else {}),
            'beats_in_scene': mem['beats'],
            'present': people,
            'purposes': [{'what': p['what'], 'for': p['for']} for p in story.get('purposes') or ()]
            or ([APPROACH_PURPOSE] if where == 'approach' else []),
            'hooks': hooks, 'raise_now': raise_now, 'thresholds': thresholds, 'endings': endings}
    return _capped(made)


# The approach is tease-only (Brendon, 2026-10-04), but never empty (watchroom T0: a thin doorway
# brief): what is plainly visible here, the ways on from here, what the approach is for, and the
# hook waiting inside, named by id and speaker only.
APPROACH_PURPOSE = {'what': 'Frame the threshold from outside: what is seen and heard from here, nothing from inside.',
                    'for': 'A choice at the way in: go in, look or listen, knock or call out, or go past.'}
THRESHOLD_RULE = ('Tease-only: what reaches the PC through this way from where they stand. Describe only '
                  'this; the first look and anything inside begin on entry. A check you call can sharpen '
                  'what is heard or noticed here, never reveal what is inside.')


def _visible_here(source, state, area):
    seen = set((state or {}).get('visible_facts') or ())
    return [fact['text'] for key, fact in (source.get('facts') or {}).items()
            if isinstance(fact, dict) and fact.get('area') == area and (fact.get('visible') or key in seen)]


def _ways_on(source, state, area):
    exits = source.get('exits') or {}
    known = (state or {}).get('known_exits') or [key for key, edge in exits.items() if not edge.get('secret')]
    return [((exits[key].get('labels') or {}).get(area) or exits[key].get('name') or key)
            for key in known if area in (exits.get(key) or {}).get('areas', ())]


def approach_frame(source, state, story=None):
    """The approach brief's frame: visible, ways_on, hooks_waiting (ids and speakers only)."""
    from .kit_agent import actor_speakers
    area = (state or {}).get('area')
    labels = actor_speakers(source)
    inside = compile_story(source)
    waiting = []
    for story_area, body in inside.items():
        if story_area == area:
            continue
        mem = story_state(state, story_area)
        for hook in body.get('hooks') or ():
            if hook['id'] not in mem['delivered']:
                waiting.append({'id': hook['id'], 'by': labels.get(hook['by'], hook['by']), 'inside': True})
    pointed = (((source.get('areas') or {}).get(area) or {}).get('tease') or {}).get('points_to')
    waiting.sort(key=lambda item: item['id'] != pointed)
    visible = _visible_here(source, state, area) or [((source.get('areas') or {}).get(area) or {}).get('name') or area]
    return {'visible': visible, 'ways_on': _ways_on(source, state, area), 'hooks_waiting': waiting}


def threshold_view(source, state, exit_key):
    """What a look or listen through ``exit_key`` gives from the PC's area: the next area's
    approach-stage view, tease-only (watchroom T2), without moving the PC. None if the exit is
    not here."""
    from .kit_agent import actor_speakers
    from .kit_rooms import outside
    source, state = source or {}, state or {}
    area = state.get('area')
    edge = (source.get('exits') or {}).get(exit_key) or {}
    if area not in edge.get('areas', ()):
        return None
    other = next((a for a in edge['areas'] if a != area), area)
    areas = source.get('areas') or {}
    # The tease belongs to the outside (approach) side of the way in: from out here it is
    # this area's own tease; from inside looking out, the outside area's.
    side = other if outside(source, other) and (areas.get(other) or {}).get('tease') else area
    tease = (areas.get(side) or {}).get('tease') or {}
    labels = actor_speakers(source)
    live = state.get('actors') or {}
    heard = [{'speaker': labels.get(item['actor'], item['actor']), 'heard': item['sound']}
             for item in tease.get('heard') or ()
             if (live.get(item.get('actor')) or {}).get('location', (source.get('actors') or {}).get(
                 item.get('actor'), {}).get('location')) == other
             and (live.get(item.get('actor')) or {}).get('status') not in GONE]
    return {'rule': THRESHOLD_RULE, 'through': edge.get('name') or exit_key,
            'into': (areas.get(other) or {}).get('called') or (areas.get(other) or {}).get('name') or other,
            'label': (edge.get('labels') or {}).get(area) or edge.get('name') or exit_key,
            'tease': tease.get('text') or (edge.get('labels') or {}).get(area) or '', 'heard': heard}


def _size(made):
    import json
    return len(json.dumps(made, ensure_ascii=False).encode())


def _capped(made):
    """The brief within BRIEF_MAX_BYTES: trim endings, thresholds, purposes, then each person's
    traits and wants from the end. Hooks and raise_now are never trimmed."""
    while _size(made) > BRIEF_MAX_BYTES:
        for key in ('endings', 'thresholds', 'purposes'):
            # A threshold crossing now is never trimmed: drop the last one that is not.
            spare = [i for i, item in enumerate(made[key])
                     if not (key == 'thresholds' and item.get('crossing_now'))]
            if len(made[key]) > 1 and spare:
                made[key].pop(spare[-1])
                made['trimmed'] = True
                break
        else:
            longest = max(made['present'], key=lambda p: len(p.get('traits', ())) + len(p.get('wants', ())),
                          default=None)
            if longest and len(longest.get('traits', ())) > 1:
                longest['traits'].pop()
            elif longest and len(longest.get('wants', ())) > 1:
                longest['wants'].pop()
            else:
                break
            made['trimmed'] = True
    return made


def due_hooks(source, state):
    """The hooks an NPC must raise this turn: [{id, text, by (label)}]."""
    made = brief(source, state)
    return [{'id': h['id'], 'text': h['text'], 'by': h['by']} for h in made['hooks'] if h['id'] in made['raise_now']]


def _needs(cond, source):
    """Plain words for what a spoken line must contain to meet ``cond``."""
    kind, value = next(iter(cond.items()))
    if kind == 'any':
        return ' or '.join(_needs(item, source) for item in value if speakable(item))
    if kind == 'said':
        said = ', '.join('"' + '" with "'.join(part.strip() for part in p.split('+')) + '"'
                         for p in said_phrases(value, source))
        paired = ', '.join(f'"{p}"' for p in value.get('paired', ()))
        return 'says one of: ' + said + (f', or {paired} together with a game word' if paired else '') + \
            (', or puts any challenging question to the player character' if value.get('challenge') else '')
    if kind == 'toll_raised':
        toll = (source.get('tolls') or {}).get(value) or {}
        return (f'names the amount ({toll.get("amount")} {toll.get("unit", "")}) together with a toll word '
                '(toll, passage, fee, a head, the price, protection, to pass, way through)')
    return 'meets it'


def check_raised(due, source, state, spoken):
    """HARD: an overdue primary hook is raised this turn by its NPC, in character."""
    story = compile_story(source).get((state or {}).get('area')) or {}
    by_id = {hook['id']: hook for hook in story.get('hooks') or ()}
    for item in due or ():
        hook = by_id.get(item['id'])
        if hook and not holds(hook['delivered_when'], source, state, spoken):
            raise InvalidChange(
                f'Story hook overdue: the {item["by"]} raises it this turn, in character, as their own '
                f'move (not the Narrator): {item["text"]} It counts when their line '
                f'{_needs(hook["delivered_when"], source)}.')


def beat_event(source, state, spoken, turn_id):
    """The per-turn record for an area with a story block: one more beat, and the hooks
    delivered by now (latched). None when the area has no story block."""
    area = (state or {}).get('area')
    story = compile_story(source).get(area)
    if not story or _fighting(state):
        return None  # a fight's rounds are not story beats
    mem = story_state(state, area)
    delivered = [hook['id'] for hook in story.get('hooks') or ()
                 if hook['id'] in mem['delivered'] or holds(hook['delivered_when'], source, state, spoken)]
    return {'type': 'story_beat', 'area': area, 'delivered': delivered,
            'evidence': f'Story beat in {area} with turn {turn_id}; delivered: '
                        f'{", ".join(delivered) or "none"}.'}


def heard_here(source, state):
    """{actor id: sound} for the live actors heard from this approach area (its tease's
    ``heard``). They can be voiced from here: a challenge through the door."""
    from .kit_rooms import stage
    if stage(source, state) != 'approach':
        return {}
    tease = ((source.get('areas') or {}).get((state or {}).get('area')) or {}).get('tease') or {}
    live = (state or {}).get('actors') or {}
    return {item['actor']: item['sound'] for item in tease.get('heard') or ()
            if (live.get(item.get('actor')) or {}).get('status') not in (None, *GONE)}


def heard_events(source, state, spoken, turn_id):
    """Hooks delivered this turn by someone in another area of the room: a challenge called
    through the door to a PC still on the threshold (watchroom playtest: the warden's challenge
    at the door was not counted, and the hook was flagged overdue inside). No beat is added
    to that area; only its delivered hooks are latched."""
    events, here = [], (state or {}).get('area')
    lines = _spoken_by(spoken, source)
    for area, story in compile_story(source).items():
        if area == here:
            continue
        mem = story_state(state, area)
        found = [hook['id'] for hook in story.get('hooks') or ()
                 if hook['id'] not in mem['delivered'] and hook.get('by') in lines and
                 holds(hook['delivered_when'], source, state, spoken)]
        if found:
            events.append({'type': 'story_beat', 'area': area, 'delivered': found, 'beat': False,
                           'evidence': f'Heard from {area} on turn {turn_id}; delivered: {", ".join(found)}.'})
    return events


def apply_event(state, source, event):
    area = event.get('area')
    story = compile_story(source).get(area)
    require(story is not None, 'story_beat needs a story block for its area')
    hooks = {hook['id'] for hook in story.get('hooks') or ()}
    delivered = event.get('delivered')
    require(isinstance(delivered, list) and set(delivered) <= hooks, 'story_beat delivered names hook ids')
    mem = story_state(state, area)
    mem = state.setdefault('story', {})[area] = {**mem, 'scene': scene_key(state)}
    require(event.get('beat', True) in (True, False), 'story_beat beat is true or false')
    if event.get('beat', True):
        mem['beats'] += 1
    mem['delivered'] = sorted(set(mem['delivered']) | set(delivered))


def threshold_events(source, state, turn_id):
    """Thresholds whose trigger holds after this turn and that have not crossed yet in this
    scene: a threshold_crossed event each, plus the attitude_shift its shift names."""
    from . import kit_attitude
    area = (state or {}).get('area')
    story = compile_story(source).get(area)
    if not story:
        return []
    crossed = story_state(state, area).get('crossed', [])
    events = []
    for index, item in enumerate(story.get('thresholds') or ()):
        if index in crossed or not item.get('trigger') or not holds(item['trigger'], source, state):
            continue
        events.append({'type': 'threshold_crossed', 'area': area, 'index': index,
                       'evidence': f'Threshold {index} in {area} crossed with turn {turn_id}: {item["when"]}'})
        shift = item.get('shift')
        if shift:
            present = kit_attitude._present(state)
            by = shift.get('to') or shift.get('by')
            changed = kit_attitude.shift_event(source, state, {a: by for a in shift['actors'] if a in present},
                                               f'threshold: {item["when"]}', events[-1]['evidence'])
            if changed:
                events.append(changed)
    return events


def apply_threshold(state, source, event):
    area = event.get('area')
    story = compile_story(source).get(area)
    require(story is not None and type(event.get('index')) is int and
            0 <= event['index'] < len(story.get('thresholds') or ()) and
            (story['thresholds'][event['index']] or {}).get('trigger'),
            'threshold_crossed names a threshold with a trigger in its area')
    mem = story_state(state, area)
    mem = state.setdefault('story', {})[area] = {**mem, 'scene': scene_key(state)}
    mem['crossed'] = sorted(set(mem.get('crossed', [])) | {event['index']})
