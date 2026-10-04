"""Room loader: mount any room file in the repo's room format, chain rooms in one session.

docs/architecture/ROOM_LOADER.md is the design. The short version:

* ``load_room(path)`` reads a room file and checks, up front, only what the first framing
  needs (stage 1/2: areas, exits, facts, actors, the starting area) plus a structural
  check of every later-stage block, without building any of it. A room that cannot mount
  raises ``RoomMountError``: ``problems`` names what is missing for the host, and
  ``TABLE_LINE`` is the plain, brief line Kit says at the table instead of improvising.
* An area may carry ``room_link`` ({room: <path>, area: <area in that room>}). Arriving in
  it mounts that room (``Runtime.mount_room``): the room left is archived with how it
  resolved (left or bypassed), the PC carries over (HP, gold, what they took), and nothing
  room-scoped crosses. Coming back restores the archived room.
* ``stage(source, state)`` says where play is in a room: approach, first_look, explore, or
  resolution. Stages are read from state, not a rail: a PC may start in, barge into, or
  bypass any of them.

Mechanic blocks are optional and turn on only from what the file declares (procedures,
tolls, combat, claims, story, attitudes, agenda, texture_palette). No model calls.
"""
import copy
import json
import re
import warnings
from pathlib import Path

from .state_context import PLAYER_NOTE_LIMIT, InvalidChange

ROOT = Path(__file__).resolve().parents[1]

# What Kit says at the table when a room cannot mount. Plain and brief: no improvised
# room, no engineering talk. (GPT owns Kit's voice; this is the floor, not a style.)
TABLE_LINE = "I can't run that room yet; it isn't set up for play. We can stop here or go another way."

REQUIRED = ('id', 'starting_area', 'areas', 'exits', 'facts', 'actors')
# Every block a room file may declare. Anything else is an unsupported feature: the loader
# refuses it rather than mounting a room whose data nothing reads.
KNOWN_BLOCKS = set(REQUIRED) | {
    'resources', 'fixture_only', 'stub', 'source_ref', 'map_ref', 'test_precondition', 'level_context',
    'campaign_context', 'public_performance', 'numeric_facts', 'leak_phrases', 'leak_keywords', 'claims',
    'room_rules', 'procedures', 'tolls', 'attitudes', 'story', 'texture_palette', 'combat', 'agenda',
    'triggers', 'traps', 'source_claims', 'authoring'}
# The JSON type of each block (anything not listed is an object). A wrong type is refused at
# mount, before any engine reads it.
BLOCK_TYPES = {'id': str, 'starting_area': str, 'source_ref': str, 'map_ref': str, 'test_precondition': str,
               'fixture_only': bool, 'stub': bool, 'room_rules': list, 'triggers': list, 'traps': list,
               'source_claims': list}
CARD_GAMES = ('twenty_one', 'three_dragon_ante')
CARRIED_LIMIT = 24  # things taken out of rooms, kept as text; the oldest go first
STAGES = ('approach', 'first_look', 'explore', 'resolution')

# State that belongs to the character and the session; everything else belongs to the room
# and is archived when the PC leaves it (state_context.Runtime.mount_room).
SESSION_KEYS = ('schema_version', 'kit', 'player_character', 'player_sheet', 'pc_state', 'roll_seed',
                'elapsed_seconds', 'rooms', 'carried', 'scene_id', 'scenes_closed', 'memory_trimmed')


class RoomMountError(InvalidChange):
    """A room that cannot mount. str() is the host's error; table_line is Kit's."""

    def __init__(self, room, problems):
        self.room, self.problems, self.table_line = str(room), list(problems), TABLE_LINE
        super().__init__(f"Room {self.room} can't be mounted: " + '; '.join(self.problems))

    def host_view(self):
        return {'stage': 'rejected', 'error': 'room_unmountable', 'room': self.room,
                'problems': self.problems, 'table_line': self.table_line, 'committed': False}


def room_path(ref):
    path = Path(ref)
    return path if path.is_absolute() else ROOT / path


def read_room(ref):
    path = room_path(ref)
    if not path.is_file():
        raise RoomMountError(ref, [f'no room file at {path}'])
    try:
        source = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RoomMountError(ref, [f'not valid JSON ({exc})']) from None
    if not isinstance(source, dict):
        raise RoomMountError(ref, ['the file is not a JSON object'])
    return source


def first_framing_problems(source):
    """What stage 1 and 2 need, checked up front: the areas, exits, facts, and actors the
    PC can meet on arrival, and a starting area. Names every problem, not just the first."""
    problems = [f'missing {key}' for key in REQUIRED if key not in source]
    if problems:
        return problems
    problems = block_type_problems(source)
    if problems:
        return problems
    areas = source['areas']
    if not areas:
        return ['areas must name at least one area']
    problems = [f'area {key} must be an object' for key, area in areas.items() if not isinstance(area, dict)]
    if problems:
        return problems
    problems = area_field_problems(areas)
    if problems:
        return problems
    if source['starting_area'] not in areas:
        problems.append(f"starting_area {source['starting_area']!r} is not one of the areas")
    for key, edge in source['exits'].items():
        ends = edge.get('areas') if isinstance(edge, dict) else None
        if not (isinstance(ends, list) and len(ends) == 2 and len(set(ends)) == 2 and all(a in areas for a in ends)):
            problems.append(f'exit {key} must join two of the areas')
        elif not isinstance(edge.get('secret'), bool):
            problems.append(f'exit {key} needs secret true or false')
        elif not all(isinstance((edge.get('labels') or {}).get(a), str) for a in ends):
            problems.append(f'exit {key} needs a label as seen from each of its two areas')
    for key, fact in source['facts'].items():
        if key.startswith('_'):
            continue
        if not (isinstance(fact, dict) and fact.get('area') in areas and isinstance(fact.get('text'), str)
                and isinstance(fact.get('visible'), bool)):
            problems.append(f'fact {key} needs an area, text, and visible')
            continue
        handling = fact.get('handling')
        if handling is not None and not (isinstance(handling, dict) and handling.get('nouns') and
                                         (handling.get('holds') is None or handling['holds'] in source['facts'])):
            problems.append(f'fact {key} handling needs nouns, and holds must name a fact')
        elif handling is not None and handling.get('parts') is not None and not (
                isinstance(handling['parts'], list) and
                all(isinstance(part, str) and part.strip() for part in handling['parts'])):
            problems.append(f'fact {key} handling parts must be a list of words (the claw of a carcass)')
    for key, actor in source['actors'].items():
        if not (isinstance(actor, dict) and actor.get('location') in areas and actor.get('status')):
            problems.append(f'actor {key} needs a location among the areas and a status')
    for key, area in areas.items():
        link = area.get('room_link')
        if link is not None and not (isinstance(link, dict) and (
                isinstance(link.get('room'), str) and isinstance(link.get('area'), str) or
                # Authored on demand from the book (runtime/kit_author.py): {author: {level, area}}.
                'room' not in link and isinstance(link.get('author'), dict) and
                isinstance(link['author'].get('area'), str) and link['author'].get('level') is not None and
                isinstance(link.get('area', ''), str))):
            problems.append(f'area {key} room_link needs room and area (or author: {{level, area}})')
    from .kit_reveal import check_layer
    return problems + secrecy_problems(source) + tease_problems(source) + fighter_problems(source) + \
        alarm_problems(source) + check_layer(source)


class RoomWarning(UserWarning):
    """A room that mounts but will make Kit invent something the file should say."""


ALARM_WORDS = re.compile(r"\b(bells?|horns?|gongs?|alarms?|whistles?|klaxons?|signal fires?|"
                         r"(?:shouts?|calls?|cr(?:y|ies)) for help|raises? the alarm)\b", re.I)


def alarm_problems(source):
    """A fact's ``alarm`` says who answers it: ``responders`` (each ``who``, ``count``, and a
    ``stat_block`` the engine can use) and ``arrives_in_rounds`` (watchroom playtest: Kit had
    to invent the bell's responders)."""
    from . import srd_creatures
    problems = []
    for key, fact in (source.get('facts') or {}).items():
        alarm = fact.get('alarm') if isinstance(fact, dict) else None
        if alarm is None:
            continue
        responders = alarm.get('responders') if isinstance(alarm, dict) else None
        if not (isinstance(responders, list) and responders and all(
                isinstance(r, dict) and isinstance(r.get('who'), str) and r['who'].strip() and
                type(r.get('count')) is int and r['count'] >= 1 and srd_creatures.stat_block(r.get('stat_block'))
                for r in responders) and type(alarm.get('arrives_in_rounds')) is int and alarm['arrives_in_rounds'] >= 0):
            problems.append(f'fact {key} alarm needs responders (each who, count 1+, stat_block inline or '
                            '{"srd": ...}) and arrives_in_rounds (0+)')
    return problems


def alarm_warnings(source):
    """Facts that read as an alarm (a bell, a horn, a shout for help) with no responders."""
    return [f'fact {key} looks like an alarm ({ALARM_WORDS.search(json.dumps(fact)).group(0)}) but lists no '
            'responders: add "alarm": {"responders": [{"who", "count", "stat_block"}], "arrives_in_rounds"} '
            'or Kit will have to invent who answers it'
            for key, fact in (source.get('facts') or {}).items()
            if isinstance(fact, dict) and 'alarm' not in fact and ALARM_WORDS.search(json.dumps(fact))]


def fighters(source):
    """Actors who can fight: armed (``armed`` true), guarding an exit (``guards``), starting
    hostile, or carrying combat stats already."""
    start = ((source.get('attitudes') or {}).get('start') or {}) if isinstance(source.get('attitudes'), dict) else {}
    combat = ((source.get('combat') or {}).get('actors') or {}) if isinstance(source.get('combat'), dict) else {}
    return [key for key, actor in (source.get('actors') or {}).items() if isinstance(actor, dict) and (
        actor.get('armed') is True or actor.get('guards') or start.get(key) == 'hostile' or
        actor.get('stat_block') is not None or key in combat)]


def fighter_problems(source):
    """Every actor who can fight has a stat block the combat engine can use: inline
    (ac, hp, attacks) or an SRD reference ({"srd": "Guard"}, runtime/srd_creatures.py), or an
    entry in the room's combat block (watchroom playtest: the warden's fight ran off-engine)."""
    from . import srd_creatures
    combat = ((source.get('combat') or {}).get('actors') or {}) if isinstance(source.get('combat'), dict) else {}
    problems = []
    for key in fighters(source):
        actor = source['actors'][key]
        if key in combat and actor.get('stat_block') is None:
            continue
        if srd_creatures.stat_block(actor.get('stat_block')) is None:
            problems.append(f'actor {key} can fight but has no usable stat_block: give one inline '
                            f'(ac, hp, attacks) or cite an SRD creature, e.g. {{"srd": "Guard"}} '
                            f'(known: {", ".join(sorted(srd_creatures.CREATURES))})')
        guards = actor.get('guards')
        if guards is not None and not (isinstance(guards, list) and all(g in (source.get('exits') or {}) for g in guards)):
            problems.append(f'actor {key} guards must list exit ids')
    return problems


AREA_STRINGS = ('called', 'arrival')  # optional; `name` is required
AREA_BOOLS = ('outside', 'beyond', 'no_refreshment')


def area_field_problems(areas):
    """Each area's own fields have their JSON types: `name` a non-empty string (Nagatha,
    705df01: a numeric name loaded), `called` and `arrival` strings, flags booleans."""
    problems = []
    for key, area in areas.items():
        if not (isinstance(area.get('name'), str) and area['name'].strip()):
            problems.append(f'area {key} name must be a non-empty string')
        problems += [f'area {key} {field} must be a string' for field in AREA_STRINGS
                     if field in area and not isinstance(area[field], str)]
        problems += [f'area {key} {field} must be true or false' for field in AREA_BOOLS
                     if field in area and not isinstance(area[field], bool)]
    return problems


def block_type_problems(source):
    problems = []
    for key, value in source.items():
        if key.startswith('_') or key not in KNOWN_BLOCKS:
            continue  # unsupported blocks are named by unsupported()
        kind = BLOCK_TYPES.get(key, dict)
        if key in ('id', 'starting_area'):
            if not (isinstance(value, str) and value.strip()):
                problems.append(f'{key} must be a non-empty string')
        elif not isinstance(value, kind) or (kind is bool) != isinstance(value, bool):
            problems.append(f'{key} must be {_KIND_NAMES[kind]}')
    return problems


_KIND_NAMES = {str: 'a string', bool: 'true or false', list: 'a list', dict: 'an object'}


def _strings(value, minimum=1):
    return isinstance(value, list) and len(value) >= minimum and all(isinstance(v, str) and v.strip() for v in value)


def secrecy_problems(source):
    """The leak guards' blocks (kit_guards.leak_sets / leak_phrases), by shape and reference:
    a malformed guard would otherwise mount and then fail mid-play, in the guard itself."""
    problems = []
    for key, entry in (source.get('leak_keywords') or {}).items():
        if key.startswith('_'):
            continue
        if not isinstance(entry, dict):
            problems.append(f'leak_keywords {key} must be an object')
            continue
        groups = entry.get('groups')
        if not (isinstance(groups, list) and groups and all(_strings(group) for group in groups)):
            problems.append(f'leak_keywords {key} needs groups: one or more lists of non-empty words')
        revealed = entry.get('revealed_by')
        if revealed is not None:
            facts = [revealed] if isinstance(revealed, str) else revealed
            if not _strings(facts, minimum=0):
                problems.append(f'leak_keywords {key} revealed_by must name a fact or a list of facts')
            else:
                problems += [f'leak_keywords {key} revealed_by names no fact: {fact!r}'
                             for fact in facts if fact not in source['facts']]
    phrases = source.get('leak_phrases')
    if phrases is not None:
        listed = phrases.get('phrases', [])
        if not _strings(listed, minimum=0):
            problems.append('leak_phrases phrases must be a list of non-empty strings')
            listed = []
        named = phrases.get('player_may_name', [])
        if not _strings(named, minimum=0):
            problems.append('leak_phrases player_may_name must be a list of non-empty strings')
        else:
            lowered = {p.casefold() for p in listed}
            problems += [f'leak_phrases player_may_name {name!r} is not one of the phrases'
                         for name in named if name.casefold() not in lowered]
    return problems


def approaches(source):
    """Outside areas the PC can stand in before going in: outside, not marked ``beyond``
    (past the room), and joined by an exit to an inside area."""
    areas = source.get('areas') or {}
    inside = set(room_areas(source))
    found = []
    for key, area in areas.items():
        if not (isinstance(area, dict) and area.get('outside')) or area.get('beyond'):
            continue
        if any(isinstance(edge, dict) and key in (edge.get('areas') or ()) and inside & set(edge.get('areas') or ())
               for edge in (source.get('exits') or {}).values()):
            found.append(key)
    return found


def tease_problems(source):
    """Brendon's ruling: the doorway carries the room's tease (what can be seen or heard from
    outside that points toward the hook, and who is audibly there). An approach without one
    does not mount."""
    problems = []
    hooks = {hook.get('id') for story in (source.get('story') or {}).values() if isinstance(story, dict)
             for hook in story.get('hooks') or () if isinstance(hook, dict)}
    for key in approaches(source):
        tease = source['areas'][key].get('tease')
        if not (isinstance(tease, dict) and isinstance(tease.get('text'), str) and tease['text'].strip()):
            problems.append(f'area {key} is an approach and needs a tease: text (what is seen or heard from '
                            'outside that points toward the hook), points_to (the hook), heard (who is audible)')
            continue
        if hooks and tease.get('points_to') not in hooks:
            problems.append(f"area {key} tease points_to {tease.get('points_to')!r} is not a story hook")
        heard = tease.get('heard', [])
        if not isinstance(heard, list):
            problems.append(f'area {key} tease heard must be a list')
            continue
        for item in heard:
            if not (isinstance(item, dict) and isinstance(item.get('sound'), str) and item['sound'].strip()):
                problems.append(f'area {key} tease heard entries need an actor and a sound')
            elif item.get('actor') not in source['actors']:
                problems.append(f"area {key} tease heard {item.get('actor')!r} is not an actor")
    return problems


def unsupported(source):
    problems = [f'unsupported block {key!r}' for key in source if not key.startswith('_') and key not in KNOWN_BLOCKS]
    for key, config in (source.get('procedures') or {}).items():
        if key.startswith('_'):
            continue
        if not isinstance(config, dict) or config.get('kind') != 'card_game':
            problems.append(f'procedure {key}: unsupported kind {(config or {}).get("kind")!r}')
        elif config.get('game', 'three_dragon_ante') not in CARD_GAMES:
            problems.append(f'procedure {key}: unsupported card game {config.get("game")!r}')
    return problems


def later_stage_problems(source):
    """Every later-stage block, validated without being built: no card engine, no brief, no
    fight is created here. The texture palette is not checked here at all: it is checked per
    area the first time play draws on it (kit_texture.area_palette)."""
    from . import kit_agenda, kit_attitude, kit_brief, kit_cards, kit_claims, kit_toll, kit_triggers
    problems = []
    checks = [('claims', kit_claims.compile_claims), ('attitudes', kit_attitude.compile_attitudes),
              ('agenda', kit_agenda.compile_agenda), ('tolls', kit_toll.compile_tolls),
              ('story', kit_brief.compile_story), ('triggers', kit_triggers.compile_triggers)]
    for block, check in checks:
        if source.get(block):
            problems += [f'{block}: {p}' for p in every_problem(source, block, check)]
    from . import kit_traps
    problems += [f'traps: {p}' for p in kit_traps.trap_problems(source)]
    for key, config in (source.get('procedures') or {}).items():
        if not key.startswith('_') and isinstance(config, dict) and config.get('kind') == 'card_game':
            try:
                kit_cards.check_config(config)
            except (InvalidChange, KeyError, TypeError) as exc:
                problems.append(f'procedure {key}: {exc}')
    return problems


COMPILE_ERRORS = (InvalidChange, KeyError, TypeError, AttributeError, ValueError, IndexError)
MAX_PROBLEMS_PER_BLOCK = 12


def _first(source, check):
    try:
        check(source)
    except COMPILE_ERRORS as exc:
        return str(exc) or type(exc).__name__
    return None


def _items(value, path=()):
    """Removable pieces of a block, deepest first: (path, ...) into dicts and lists."""
    out = []
    if isinstance(value, dict):
        for key, item in value.items():
            out += _items(item, path + (key,)) + [path + (key,)]
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out += _items(item, path + (index,)) + [path + (index,)]
    return out


def _without(block, path):
    import copy as _copy
    block = _copy.deepcopy(block)
    parent = block
    for step in path[:-1]:
        parent = parent[step]
    del parent[path[-1]]
    return block


def every_problem(source, block, check):
    """Every problem a block's compiler finds, not just its first: the compilers stop at the
    first error, so the piece that raised it is set aside and the compiler runs again (up to
    MAX_PROBLEMS_PER_BLOCK). A repair gets one try, so it sees them all."""
    import copy as _copy
    import sys as _sys
    found = []
    # A soft pass first: the compiler's own require() records instead of raising, so one
    # entry with two problems (a hook missing its text and its condition) names both.
    module = _sys.modules.get(getattr(check, '__module__', ''))
    original = getattr(module, 'require', None)
    if original is not None:
        def record(condition, message):
            if not condition and message not in found:
                found.append(message)
        module.require = record
        try:
            check(_copy.deepcopy(source))
        except Exception:  # noqa: BLE001 - soft pass: bad data may fail anywhere after a recorded miss
            pass
        finally:
            module.require = original
        found = found[:MAX_PROBLEMS_PER_BLOCK]
    trial = _copy.deepcopy(source)
    while len(found) < MAX_PROBLEMS_PER_BLOCK:
        error = _first(trial, check)
        if error is None:
            break
        if error not in found:
            found.append(error)
        culprit = None
        # Whole entries only (a list element, or a block's top-level entry), never one field of
        # an entry: setting aside a field would only raise a new, made-up problem.
        for path in [p for p in _items(trial[block]) if isinstance(p[-1], int) or len(p) == 1]:
            candidate = {**trial, block: _without(trial[block], path)}
            if _first(candidate, check) != error:
                culprit = candidate
                break
        if culprit is None:
            break
        trial = culprit
    return found


def check_room(source, ref='room'):
    problems = first_framing_problems(source)
    if not problems:
        problems = unsupported(source) or later_stage_problems(source)
    if problems:
        raise RoomMountError(ref, problems)
    for line in alarm_warnings(source):
        warnings.warn(f'ROOM WARNING {ref}: {line}', RoomWarning, stacklevel=3)
    source.setdefault('resources', {})
    return source


def load_room(ref):
    source = read_room(ref)
    try:
        return check_room(source, ref)
    except RoomMountError:
        raise
    except (AttributeError, TypeError, KeyError, ValueError, IndexError) as exc:
        # A shape no check above names yet: still Kit's plain line, never a traceback.
        raise RoomMountError(ref, [f'malformed room data ({type(exc).__name__}: {exc})']) from None


def resolved_link(link, authored=None):
    """A ``room_link`` as {room, area}. An ``author`` link names a keyed area whose room Kit
    writes from the book (runtime/kit_author.py); it resolves to that session's accepted room,
    or raises kit_author.RoomNotAuthored (a RoomMountError) naming the request command."""
    if 'author' not in link or 'room' in link:
        return link
    from . import kit_author
    if authored is None:
        raise kit_author.RoomNotAuthored(f"area {link['author'].get('area')}", [
            'this room is authored from the book and the session has no authored-room cache'], {})
    return kit_author.Session(authored).resolve_link(link)


def load_link(link, authored=None):
    """The room an area's ``room_link`` leads to, checked down to its arrival area."""
    link = resolved_link(link, authored)
    source = load_room(link['room'])
    if link['area'] not in source['areas']:
        raise RoomMountError(link['room'], [f"room_link area {link['area']!r} is not one of its areas"])
    return source


def _same_file(a, b):
    return room_path(a).resolve() == room_path(b).resolve()


def arrive(old_source, state, link, authored=None):
    """(the linked room, the state on arrival in it): the room loaded and checked, the room
    left archived, the arrival area observed, and the new room's context within its caps.
    ``authored``: the session's authored-room directory, for ``author`` links."""
    from .state_context import Runtime
    link = resolved_link(link, authored)
    source = load_link(link)
    seen = ((state.get('rooms') or {}).get(source.get('id')) or {}).get('state', {}).get('room', {}).get('path')
    if source.get('id') == old_source.get('id') or seen and _same_file(seen, link['room']) is False:
        # Room ids key the archive: a second file with the same id would overwrite a room left.
        raise RoomMountError(link['room'], [f"room id {source.get('id')!r} is already used by another room file"])
    new = mounted_state(old_source, state, source, link['area'], link['room'])
    Runtime._observe(new, source)
    check_context(source, new, ref=link['room'])
    return source, new


# Room context caps (Claude's review of #87): the room file's own share of Kit's private input,
# dm_only without play-grown canon and procedure state, and claims_here. 6c, the richest room,
# peaks at 9,554 B and 3,057 B in the suite; the caps sit just above, so 6c plays and a room
# materially richer than 6c is refused, naming the block, instead of the budget quietly trimming
# Kit's memory to make room. They bound the room's share; they cannot buy headroom the budget
# does not have (ROOM_LOADER.md, "Context headroom").
DM_ONLY_ROOM_MAX_BYTES = 9700
CLAIMS_HERE_MAX_BYTES = 3150
PLAY_GROWN_DM_ONLY = ('canon_here', 'procedures_private')  # bounded by their own limits


def check_context(source, state, dm_only=None, claims=None, ref=None):
    from . import kit_claims
    from .state_context import Runtime, encode
    if dm_only is None:
        dm_only = Runtime.dm_only(source, state)
    if claims is None and source.get('claims'):
        claims = kit_claims.claims_here(source, state, state.get('player_sheet'))
    room_part = {k: v for k, v in dm_only.items() if k not in PLAY_GROWN_DM_ONLY}
    problems = []
    for name, value, cap in (('dm_only', room_part, DM_ONLY_ROOM_MAX_BYTES),
                             ('claims_here', claims or {}, CLAIMS_HERE_MAX_BYTES)):
        size = len(encode(value).encode())
        if size > cap:
            problems.append(f"room context over its cap: {name} is {size} bytes in area {state['area']} "
                            f'(cap {cap}). Trim or split the room file; Kit\'s memory is not trimmed to make '
                            'room for it (docs/architecture/ROOM_LOADER.md, "Context headroom")')
    if problems:
        raise RoomMountError(ref or source.get('id'), problems)


def outside(source, area):
    return bool(((source.get('areas') or {}).get(area) or {}).get('outside'))


def room_areas(source):
    return [key for key, area in (source.get('areas') or {}).items() if not (area or {}).get('outside')]


def resolution(source, state):
    """How the PC left this room: 'left' (they were inside) or 'bypassed' (never went in)."""
    inside = set(room_areas(source))
    return 'left' if inside & set(state.get('visited') or ()) else 'bypassed'


def stage(source, state):
    """Where play stands in this room, read from state (never a rail):
    approach (outside, not yet in), first_look (inside, no turn yet in this area),
    explore (inside, play under way), resolution (outside again, or past it: left or bypassed)."""
    area = state.get('area')
    if outside(source, area) and ((source.get('areas') or {}).get(area) or {}).get('beyond'):
        return 'resolution'  # past the room: going on without going in is a bypass
    if outside(source, area):
        visited_inside = set(room_areas(source)) & set(state.get('visited') or ())
        others = [a for a in state.get('visited') or () if outside(source, a) and a != area]
        if visited_inside or others:
            return 'resolution'
        return 'approach'
    turns_here = (state.get('room') or {}).get('turns_in', {}).get(area, 0)
    return 'first_look' if not turns_here else 'explore'


def _room_totals(state):
    gold = 0
    for body in (state.get('procedures') or {}).values():
        gold += int((((body or {}).get('public') or {}).get('player') or {}).get('net') or 0)
    for body in (state.get('tolls') or {}).values():
        if not body.get('rode_on'):  # a toll lost on a hand is already in that table's net
            gold -= int(body.get('paid') or 0)
    took = list((state.get('scene') or {}).get('pc_took') or ())
    return {'gold': gold, 'damage': int((state.get('combat') or {}).get('pc_damage') or 0), 'took': len(took)}, took


def fold_pc(source, state):
    """What the PC takes out of a room: current HP after any fight, gold won or lost at its
    tables and paid in its tolls, and what they took. Only what changed since the room was
    last left is folded, so leaving a room twice never counts it twice.
    Returns (sheet, carried, totals)."""
    sheet = copy.deepcopy(state.get('player_sheet'))
    carried = list(state.get('carried') or [])
    totals, took = _room_totals(state)
    folded = (state.get('room') or {}).get('folded') or {'gold': 0, 'damage': 0, 'took': 0}
    if sheet:
        damage = totals['damage'] - folded['damage']
        if damage and isinstance(sheet.get('hp'), (int, float)) and not isinstance(sheet.get('hp'), bool):
            sheet['hp'] = max(0, sheet['hp'] - damage)
        gold = totals['gold'] - folded['gold']
        if gold and isinstance(sheet.get('gold_gp'), (int, float)):
            sheet['gold_gp'] = max(0, sheet['gold_gp'] + gold)
    carried += [{'item': item, 'from': source.get('id')} for item in took[folded['took']:]]
    return sheet, carried[-CARRIED_LIMIT:], totals  # oldest first out; ROOM_LOADER.md gap 7


def initial_room(source, ref=None):
    return {'id': source.get('id'), 'path': str(ref) if ref else None, 'turns_in': {}}


def known_fact_ids(source, state):
    """Every fact the player has learned in this room, in any area: revealed facts, and the
    facts of claims learned in play."""
    from . import kit_claims
    learned = set(((state or {}).get('claims') or {}).get('learned') or ())
    claims = kit_claims.compile_claims(source) if learned else {}
    return set((state or {}).get('known_facts') or ()) | {
        claims[key].get('fact') for key in learned if key in claims and claims[key].get('fact')}


def room_private_kit(source, kit, state=None):
    """(what of Kit's memory stays with this room, the player notes that travel on).

    A player note stays with the room only while it names a secret that is still unrevealed.
    What the player has learned follows them (Nagatha, 705df01: "Nik knows the marked deck is
    rigged" was archived after the deck was revealed in public). A hidden fact is revealed
    once it is known; a keyword set once one of its revealing facts is known (the same rule
    the leak guard applies); a leak phrase once a known fact says it or a revealed set covers
    it ("marked deck" under the marked_deck set). A note naming a revealed secret and an
    unrevealed one stays with the room."""
    from . import kit_guards
    facts = source.get('facts') or {}
    known = known_fact_ids(source, state)
    known_text = ' '.join(kit_guards.normalize(str(facts[key].get('text') or '')) for key in known if key in facts)
    sets = kit_guards.leak_sets(source)
    revealed = lambda entry: any(kit_guards.normalize(t) in known_text for t in entry.get('revealed_texts') or ())
    open_sets = [entry for entry in sets if not revealed(entry)]
    phrases = [p for p in kit_guards.leak_phrases(source)['phrases']
               if kit_guards.normalize(p) not in known_text and
               not any(revealed(entry) and kit_guards._sentence_hits(p, entry['groups']) for entry in sets)]
    hidden = [str(fact.get('text') or '').casefold() for key, fact in facts.items()
              if isinstance(fact, dict) and not fact.get('visible') and key not in known]

    def secret(note):
        text = str(note.get('note') or '').casefold()
        return (any(p in text for p in phrases) or any(h and h in text for h in hidden) or
                any(kit_guards._sentence_hits(sentence, entry['groups'])
                    for entry in open_sets for sentence in re.split(r'(?<=[.!?])\s+', text)))
    notes = list(kit.get('player_notes') or [])
    return ({'episodes': list(kit.get('episodes') or []), 'current_appraisal': kit.get('current_appraisal'),
             'player_notes': [n for n in notes if secret(n)]},
            [n for n in notes if not secret(n)])


def mounted_state(old_source, state, new_source, area, ref):
    """The state after the PC arrives in ``area`` of ``new_source``: the room left is
    archived under state['rooms'] with how it resolved; the character and the session
    carry over; a room seen before comes back as it was left."""
    if area not in new_source['areas']:
        raise RoomMountError(ref, [f'room_link area {area!r} is not one of its areas'])
    sheet, carried, totals = fold_pc(old_source, state)
    rooms = copy.deepcopy(state.get('rooms') or {})
    left = {key: copy.deepcopy(value) for key, value in state.items() if key not in SESSION_KEYS}
    left['room'] = dict(left.get('room') or initial_room(old_source), folded=totals)
    rooms[old_source.get('id')] = {'resolution': resolution(old_source, state), 'state': left}
    new = {key: copy.deepcopy(value) for key, value in state.items() if key in SESSION_KEYS}
    # Kit's private memory of a room stays with the room (its secrets are guarded only by its
    # own leak blocks): her episodes, her current appraisal, and any player note that names one
    # of the room's secrets. Player notes that don't travel on; her public lines are public.
    kit = new.get('kit') or {}
    private, notes = room_private_kit(old_source, kit, state)
    left['kit'] = private
    new['kit'] = {**kit, 'episodes': [], 'current_appraisal': None, 'player_notes': notes}
    if sheet is not None:
        new['player_sheet'] = sheet
    new['carried'] = carried
    archived = rooms.pop(new_source.get('id'), None)
    if archived:
        back = copy.deepcopy(archived['state'])
        kept = back.pop('kit', None) or {}
        new.update(back)
        new['kit'] = {**new['kit'], 'episodes': kept.get('episodes') or [],
                      'current_appraisal': kept.get('current_appraisal'),
                      'player_notes': (new['kit'].get('player_notes', []) +
                                       (kept.get('player_notes') or []))[-PLAYER_NOTE_LIMIT:]}
    else:
        new.update(visited=[], known_facts=[], known_exits=[], actors=copy.deepcopy(new_source['actors']),
                   resources=copy.deepcopy(new_source.get('resources') or {}), rhythm=[],
                   room=initial_room(new_source, ref))
    new['area'] = area
    new['room'] = {k: v for k, v in (new.get('room') or {}).items() if k != 'came_by'}  # came from another room
    if area not in new['visited']:
        new['visited'].append(area)
    new['rooms'] = rooms
    return new
