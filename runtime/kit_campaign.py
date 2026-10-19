"""What Kit is available for, before any room is mounted.

`start` with no room used to mount Area 6c. It must not. It also must not treat
"I want to play" as a request for Dungeon of the Mad Mage. That adventure starts
only when the player asks for it. Talk, debrief, and working on a scene or a
character do not go through a room at all.
"""
import json
import sqlite3
from pathlib import Path

from . import kit_rooms
from .state_context import PROJECT_ROOT

# Outside rooms/ on purpose: a regression fixture, not a campaign start.
REGRESSION_ROOM = 'tests/fixtures/level_01_area_06c.json'
EXAMPLE_SHEET = 'tests/fixtures/characters/example_pc.json'
MAD_MAGE_KEYS = ('dotmm', 'mad mage', 'mad-mage', 'dungeon of the mad mage')
GREETING = (
    "I'm Kit. I can talk with you, go over a game, work on a character or a scene, "
    "or run a session once you tell me which one. I won't pick the adventure for you.")
MAD_MAGE_LINE = (
    "Dungeon of the Mad Mage isn't a playable room in this build. It should open at the "
    "Yawning Portal, then the first room under the well. I won't put you in a test room instead.")
NOT_A_CAMPAIGN_LINE = (
    "That isn't a campaign room. It's a test file, and I won't start the adventure there.")


def campaign_entry(db, sheet_path=None, rooms_dir=None, campaign=None):
    """No room was named.

    No campaign: a greeting. She does not open a game.
    A named campaign: only that campaign, and only to say whether it can be played.
    A save that already holds a game is a resume, not a new start.
    """
    saved = saved_game(db)
    if saved is not None:
        return _resume(saved, campaign)
    executable, blocked = inspect_rooms(rooms_dir or (PROJECT_ROOT / 'rooms'))
    blocked = _with_regression(blocked)
    if campaign is None:
        return _greeting(sheet_path, executable, blocked)
    if _is_mad_mage(campaign):
        return _mad_mage(sheet_path, executable, blocked)
    return {
        'stage': 'unknown_game',
        'committed': False,
        'opened_room': None,
        'character_loaded': False,
        'sheet_noted': str(sheet_path) if sheet_path else None,
        'sheet_loaded': False,
        'asked': campaign,
        'table_line': "I don't have that as a game I can run. We can talk about it, or you can name something else.",
        'next_step': (
            'Say table_line. Do not invent a dungeon or a character. Do not pass --room. '
            'Do not substitute Dungeon of the Mad Mage.'),
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
            'Do not mount this file. If the player did not name a game, say the greeting from start '
            'with no --room and no --campaign. Pass --regression with --room only when an engineering '
            'fixture was asked for by name.'),
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


def _resume(saved, campaign):
    pending = saved.get('pending_turn')
    if pending:
        nxt = (f'A turn is already waiting ({pending}). Continue only if the player wants this game. '
               'Complete that turn if you still have the decision. Do not open a different room. '
               'Show the player only "spoken".')
    else:
        nxt = ('A save is present. Continue it only if the player wants this game. '
               'On the next in-fiction line, prepare --one-pass and then complete. '
               'Show the player only "spoken". Do not start Dungeon of the Mad Mage over it.')
    nxt += (' kit.sqlite is runtime-only: never offer it to the player. To give them a save, run '
            'save --db <this db> and offer the ZIP it names.')
    line = "There's already a game in this save. We can pick it up if that's what you want. I won't start a second one over it."
    if campaign and not _is_mad_mage(campaign):
        line = "This save already has a game. I won't start another over it. Say if you want to continue this one."
    elif _is_mad_mage(campaign):
        line = "This save already has a game. I won't start Mad Mage over it. Say if you want to continue this one."
    return {
        'stage': 'resume',
        'committed': False,
        'opened_room': None,
        **saved,
        'table_line': line,
        'next_step': nxt,
    }


def _greeting(sheet_path, executable, blocked):
    return {
        'stage': 'greeting',
        'committed': False,
        'opened_room': None,
        'character_loaded': False,
        'sheet_noted': str(sheet_path) if sheet_path else None,
        'sheet_loaded': False,
        'for': [
            'Talk, as herself. No room, no character sheet, no adventure assumed.',
            'Go over a game, a ruling, or a scene that already happened.',
            'Work on a character or a scene. That is talk and prep, not a running session.',
            'Run a session only after the player names the game.',
        ],
        'executable_starts': executable,
        'do_not_start': blocked,
        'mad_mage': _mad_mage_facts(),
        'table_line': GREETING,
        'next_step': (
            'Say table_line in your own voice if they have not already said what they want. '
            'Do not mention Dungeon of the Mad Mage unless they did. '
            'Do not pass --room. Do not pass --regression. Do not open do_not_start. '
            'If they want to play and have not named a game, ask which one. '
            'If they asked for Mad Mage, run start --campaign dotmm and say that table_line. '
            'Talk, debrief, and design do not use the bridge.'),
    }


def _mad_mage(sheet_path, executable, blocked):
    ready = [item for item in executable if _room_is_mad_mage(item)]
    facts = _mad_mage_facts()
    if ready:
        return {
            'stage': 'need_character' if not sheet_path else 'campaign_ready',
            'committed': False,
            'opened_room': None,
            'character_loaded': False,
            'sheet_noted': str(sheet_path) if sheet_path else None,
            'sheet_loaded': False,
            'asked': 'dotmm',
            'executable_starts': ready,
            'do_not_start': blocked,
            'table_line': (
                "Mad Mage can open, but I need your character first. I won't invent who you are."),
            'next_step': (
                'They asked for this campaign. Ask for a sheet if sheet_noted is null. '
                'Then run start --room <one path from executable_starts> --sheet <file>. '
                'Never pass a path in do_not_start.'),
        }
    return {
        'stage': 'campaign_unavailable',
        'committed': False,
        'opened_room': None,
        'character_loaded': False,
        'sheet_noted': str(sheet_path) if sheet_path else None,
        'sheet_loaded': False,
        'asked': 'dotmm',
        'campaign': facts,
        'do_not_start': blocked,
        'blocker': {
            'code': 'mad_mage_not_executable',
            'missing': facts['missing'],
        },
        'table_line': MAD_MAGE_LINE,
        'next_step': (
            'They asked for Dungeon of the Mad Mage. Say table_line. Do not invent the Yawning Portal '
            'or a dungeon room. Do not pass --room. Do not pass --regression. Do not open do_not_start.'),
    }


def _mad_mage_facts():
    return {
        'id': 'dotmm',
        'title': 'Dungeon of the Mad Mage',
        'only_if_asked': True,
        'status': 'not_executable',
        'intended_start': (
            'The Yawning Portal in Waterdeep, then the winch descent to Level 1, Area 1. '
            'docs/campaign/levels/LEVEL_00_GAME_SETUP.md describes that opening. It is not a room file.'),
        'source_to_room': 'not_built',
        'missing': [
            'The Yawning Portal is a campaign-layer document, not a room file.',
            'Level 1 Area 1, the first dungeon room after the descent, has no room file.',
            'Source-to-room authoring is not built. Keyed adventure text is not turned into a playable room (PROJECT_CONTROL.md).',
            'rooms/level_01_area_17a.json is a stub with placeholder facts. It is not a campaign start.',
            f'{REGRESSION_ROOM} is a historical regression fixture. It is not a fallback.',
        ],
    }


def _is_mad_mage(campaign):
    return str(campaign).strip().casefold() in MAD_MAGE_KEYS


def _room_is_mad_mage(item):
    room_id = str(item.get('room_id') or '').casefold()
    return room_id.startswith('dotmm-') and 'stub' not in room_id and 'testbed' not in room_id


def _with_regression(blocked):
    if any(item.get('path') == REGRESSION_ROOM for item in blocked):
        return blocked
    return blocked + [{
        'path': REGRESSION_ROOM,
        'kind': 'regression_fixture',
        'reason': 'Historical test room. Not the campaign, not the default, and not a fallback.',
    }]
