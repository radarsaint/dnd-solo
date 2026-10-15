"""Player-facing campaign entry.

`start` with no room used to mount Area 6c and the example character. That room is a
historical regression fixture. The campaign is Dungeon of the Mad Mage, and its start
(the Yawning Portal, then Level 1 Area 1) is not a room file. This module reports that.
It does not mount a room and it does not invent one.
"""
import json
import sqlite3
from pathlib import Path

from . import kit_rooms
from .state_context import PROJECT_ROOT

# Outside rooms/ on purpose: a regression fixture, not a campaign start.
REGRESSION_ROOM = 'tests/fixtures/level_01_area_06c.json'
EXAMPLE_SHEET = 'tests/fixtures/characters/example_pc.json'
CAMPAIGN_ID = 'dotmm'
CAMPAIGN_TITLE = 'Dungeon of the Mad Mage'
INTENDED_START = (
    'The Yawning Portal in Waterdeep, then the winch descent to Level 1, Area 1. '
    'docs/campaign/levels/LEVEL_00_GAME_SETUP.md describes that opening. '
    'It is not a room file.')
TABLE_LINE = (
    "I can't start the campaign from this build. The adventure is Dungeon of the Mad Mage, "
    "and it should open at the Yawning Portal, then the first room under the well. "
    "That start isn't a playable room yet. I won't drop you into a test room instead.")
NOT_A_CAMPAIGN_LINE = (
    "That isn't a campaign room. It's a test file, and I won't start the adventure there.")


def campaign_entry(db, sheet_path=None, rooms_dir=None):
    """What a host gets when the player asks to play and no room was named.

    No database is created. A save that already holds a game is a resume, not a new start.
    """
    saved = saved_game(db)
    if saved is not None:
        return _resume(saved)
    executable, blocked = inspect_rooms(rooms_dir or (PROJECT_ROOT / 'rooms'))
    blocked = _with_regression(blocked)
    noted = str(sheet_path) if sheet_path else None
    if executable:
        stage_line = (
            "There is a real start I can open, but I need your character first. "
            "I won't pick a test room, and I won't invent who you are.")
        nxt = (
            'If more than one path is in executable_starts, ask the player which start they want. '
            'Ask for a character sheet, or write character_sheet_v1 JSON from numbers they actually give you. '
            f'Do not load {EXAMPLE_SHEET} unless they explicitly ask for the example character. '
            'Then run start --db <db> --room <one path from executable_starts> --sheet <file>. '
            'Never pass a path in do_not_start. Never pass --regression.')
    else:
        stage_line = TABLE_LINE
        nxt = (
            'Say table_line to the player in your own voice. Do not invent a tavern, a dungeon room, '
            'or a character. Do not run start --room. Do not pass --regression. '
            'Do not open any path in do_not_start. This build has no playable campaign room.')
    return {
        'stage': 'campaign_entry',
        'committed': False,
        'opened_room': None,
        'character_loaded': False,
        'sheet_noted': noted,
        'sheet_loaded': False,
        'campaign': {
            'id': CAMPAIGN_ID,
            'title': CAMPAIGN_TITLE,
            'intended_start': INTENDED_START,
            'source_to_room': 'not_built',
        },
        'executable_starts': executable,
        'do_not_start': blocked,
        'blocker': None if executable else {
            'code': 'no_executable_campaign_start',
            'missing': [
                'The Yawning Portal is a campaign-layer document, not a room file.',
                'Level 1 Area 1, the first dungeon room after the descent, has no room file.',
                'Source-to-room authoring is not built. Keyed adventure text is not turned into a playable room (PROJECT_CONTROL.md).',
                'rooms/level_01_area_17a.json is a stub with placeholder facts. It is not the campaign.',
                f'{REGRESSION_ROOM} is a historical regression fixture. It is not the campaign and not a fallback.',
            ],
        },
        'table_line': stage_line,
        'next_step': nxt,
    }


def player_room_refusal(room, source):
    """CLI guard: a named stub or fixture is not a campaign start unless --regression is set."""
    if source.get('stub'):
        kind = 'stub'
    elif source.get('fixture_only'):
        kind = 'regression_fixture'
    else:
        return None
    return {
        'stage': 'rejected',
        'committed': False,
        'error': 'not_a_campaign_room',
        'room': str(room),
        'room_id': source.get('id'),
        'why': kind,
        'table_line': NOT_A_CAMPAIGN_LINE,
        'next_step': (
            'Run start with no --room and follow that campaign_entry. '
            'Pass --regression with --room only when an engineering fixture was asked for by name.'),
    }


def need_character(room, source):
    """A real room was named and no sheet was given. Do not load the example character."""
    return {
        'stage': 'need_character',
        'committed': False,
        'opened_room': None,
        'character_loaded': False,
        'room': str(room),
        'room_id': source.get('id'),
        'example_sheet': EXAMPLE_SHEET,
        'table_line': (
            "This room can open, but I don't have your character. "
            "Tell me who you are playing, or give me a sheet. I won't invent one."),
        'next_step': (
            'Do not start until --sheet is passed. '
            f'Do not offer {EXAMPLE_SHEET} unless the player explicitly asks for the example character. '
            'Then run the same start command with --room and --sheet.'),
    }


def inspect_rooms(rooms_dir):
    """Classify room files. Executable means the loader accepts the file and it is not a stub or fixture."""
    executable, blocked = [], []
    folder = Path(rooms_dir)
    if not folder.is_dir():
        return executable, blocked
    root = PROJECT_ROOT.resolve()
    for path in sorted(folder.rglob('*.json')):
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = str(path)
        try:
            source = kit_rooms.load_room(path)
        except kit_rooms.RoomMountError as exc:
            blocked.append({'path': rel, 'kind': 'unmountable', 'reason': '; '.join(exc.problems)})
            continue
        entry = {'path': rel, 'room_id': source.get('id'), 'starting_area': source.get('starting_area')}
        if source.get('stub'):
            entry['kind'] = 'stub'
            entry['reason'] = 'Stub. Placeholder facts are not the published room. Do not play it.'
            blocked.append(entry)
        elif source.get('fixture_only'):
            entry['kind'] = 'regression_fixture'
            entry['reason'] = 'Marked fixture_only. Not a campaign start.'
            blocked.append(entry)
        else:
            executable.append(entry)
    return executable, blocked


def saved_game(db):
    """The open game in an existing save, or None. Does not create a file."""
    path = Path(db)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    except sqlite3.Error:
        return None
    try:
        if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source'").fetchone() is None:
            return None
        body = con.execute('SELECT body FROM source WHERE id=1').fetchone()
        snap = con.execute('SELECT revision, body FROM snapshots ORDER BY revision DESC LIMIT 1').fetchone()
        if body is None or snap is None:
            return None
        source = json.loads(body[0])
        state = json.loads(snap[1])
        pending = None
        if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kit_pending'").fetchone():
            row = con.execute('SELECT turn_id FROM kit_pending LIMIT 1').fetchone()
            pending = row[0] if row else None
        character = state.get('player_character') or {}
        room = state.get('room') or {}
        return {
            'db': str(path),
            'revision': snap[0],
            'room_id': room.get('id') or source.get('id'),
            'area': state.get('area'),
            'character': character.get('name'),
            'pending_turn': pending,
        }
    except (sqlite3.Error, ValueError, TypeError):
        return None
    finally:
        con.close()


def _resume(saved):
    pending = saved.get('pending_turn')
    if pending:
        nxt = (f'A turn is already waiting ({pending}). Complete that turn if you still have the decision. '
               'Do not run start --room. Do not open a different room. Show the player only "spoken".')
    else:
        nxt = ('This save is the game. Do not run start --room. On the next in-fiction line, '
               'prepare --one-pass and then complete. Show the player only "spoken".')
    return {
        'stage': 'resume',
        'committed': False,
        'opened_room': None,
        **saved,
        'table_line': "We'll pick up the game you already have. I won't start a second one.",
        'next_step': nxt,
    }


def _with_regression(blocked):
    if any(item.get('path') == REGRESSION_ROOM for item in blocked):
        return blocked
    return blocked + [{
        'path': REGRESSION_ROOM,
        'kind': 'regression_fixture',
        'reason': 'Historical test room. Not the campaign, not the default, and not a fallback.',
    }]
