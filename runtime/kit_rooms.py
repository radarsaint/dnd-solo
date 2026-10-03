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
from pathlib import Path

from .state_context import InvalidChange

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
    'room_rules', 'procedures', 'tolls', 'attitudes', 'story', 'texture_palette', 'combat', 'agenda'}
CARD_GAMES = ('twenty_one', 'three_dragon_ante')
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
    areas = source['areas']
    if not isinstance(areas, dict) or not areas:
        return ['areas must name at least one area']
    problems = [f'{key} must be an object' for key in ('exits', 'facts', 'actors')
                if not isinstance(source[key], dict)]
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
    for key, actor in source['actors'].items():
        if not (isinstance(actor, dict) and actor.get('location') in areas and actor.get('status')):
            problems.append(f'actor {key} needs a location among the areas and a status')
    for key, area in areas.items():
        link = (area or {}).get('room_link')
        if link is not None and not (isinstance(link, dict) and isinstance(link.get('room'), str)
                                     and isinstance(link.get('area'), str)):
            problems.append(f'area {key} room_link needs room and area')
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
    from . import kit_agenda, kit_attitude, kit_brief, kit_cards, kit_claims, kit_toll
    problems = []
    checks = [('claims', kit_claims.compile_claims), ('attitudes', kit_attitude.compile_attitudes),
              ('agenda', kit_agenda.compile_agenda), ('tolls', kit_toll.compile_tolls),
              ('story', kit_brief.compile_story)]
    for block, check in checks:
        if source.get(block):
            try:
                check(source)
            except (InvalidChange, KeyError, TypeError, AttributeError) as exc:
                problems.append(f'{block}: {exc}')
    for key, config in (source.get('procedures') or {}).items():
        if not key.startswith('_') and isinstance(config, dict) and config.get('kind') == 'card_game':
            try:
                kit_cards.check_config(config)
            except (InvalidChange, KeyError, TypeError) as exc:
                problems.append(f'procedure {key}: {exc}')
    return problems


def check_room(source, ref='room'):
    problems = first_framing_problems(source)
    if not problems:
        problems = unsupported(source) or later_stage_problems(source)
    if problems:
        raise RoomMountError(ref, problems)
    source.setdefault('resources', {})
    return source


def load_room(ref):
    return check_room(read_room(ref), ref)


def load_link(link):
    """The room an area's ``room_link`` leads to, checked down to its arrival area."""
    source = load_room(link['room'])
    if link['area'] not in source['areas']:
        raise RoomMountError(link['room'], [f"room_link area {link['area']!r} is not one of its areas"])
    return source


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
        if damage and type(sheet.get('hp')) is int:
            sheet['hp'] = max(0, sheet['hp'] - damage)
        gold = totals['gold'] - folded['gold']
        if gold and isinstance(sheet.get('gold_gp'), (int, float)):
            sheet['gold_gp'] = max(0, sheet['gold_gp'] + gold)
    carried += [{'item': item, 'from': source.get('id')} for item in took[folded['took']:]]
    return sheet, carried[-24:], totals


def initial_room(source, ref=None):
    return {'id': source.get('id'), 'path': str(ref) if ref else None, 'turns_in': {}}


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
    if sheet is not None:
        new['player_sheet'] = sheet
    new['carried'] = carried
    archived = rooms.pop(new_source.get('id'), None)
    if archived:
        new.update(copy.deepcopy(archived['state']))
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
