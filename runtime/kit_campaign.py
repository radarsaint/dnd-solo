"""What Kit is available for, before any room is mounted.

`start` with no room used to mount Area 6c. It must not. It also must not treat
"I want to play" as a request for Dungeon of the Mad Mage. That adventure starts
only when the player asks for it. Talk, debrief, and working on a scene or a
character do not go through a room at all.
"""
import hashlib
import json
import re
import shlex
import sqlite3
from pathlib import Path

from . import _lazy, kit_rooms, pc_sheet
kit_chargen = _lazy.module('.kit_chargen', __package__)
from .state_context import PROJECT_ROOT

# Outside rooms/ on purpose: a regression fixture, not a campaign start.
REGRESSION_ROOM = 'tests/fixtures/level_01_area_06c.json'
EXAMPLE_SHEET = 'tests/fixtures/characters/example_pc.json'
MAD_MAGE_KEYS = ('dotmm', 'mad mage', 'mad-mage', 'dungeon of the mad mage')
GREETING = "Pull up a chair. Are we rolling dice tonight, or building something?"
PLAY_NEEDS_LINES = {
    ('a module', 'your character'): "Then hand me two things: the adventure, and whoever's walking into it.",
    ('a module',): "Good. Now, what am I running? Hand me the module.",
    ('your character',): "And who's walking in? Give me your sheet. I read those closely.",
}
TABLE_LINE = "Just you tonight, or a full table taking turns?"
SOLO_LINE = "Just us, then. Settle in."
SHARED_LINE = "A full table. Tell me who's talking and I'll get to everyone."
BUILD_LINE = ("Building, then. Encounters, NPCs, rulings, what that loot's worth: that's my wheelhouse. "
              "Character options past the core rules, hand me the text and I'll check it.")
TABLE_MODES = ('solo', 'shared')
INTENTS = ('play', 'build')
SHARED_NOTE = ('Shared table is recorded, but turn-taking is basic for now: the host prefixes each '
               'line with the speaker\'s name and Kit answers in the order lines arrive. '
               'No initiative-style turn order outside combat yet.')
MAD_MAGE_LINE = (
    "Dungeon of the Mad Mage isn't a playable room in this build. It should open at the "
    "Yawning Portal, then the first room under the well. I won't put you in a test room instead.")
NOT_A_CAMPAIGN_LINE = (
    "That isn't a campaign room. It's a test file, and I won't start the adventure there.")


def campaign_entry(db, sheet_path=None, rooms_dir=None, campaign=None, intent=None, table=None,
                   saves_db=None):
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
    if campaign is None and intent == 'build':
        return _build(sheet_path)
    if campaign is None and intent == 'play':
        return _play(db, sheet_path, executable, blocked, table, modules=rooms_dir)
    if campaign is None:
        from . import kit_resume  # local: kit_resume imports this module's callers
        return _greeting(sheet_path, executable, blocked, kit_resume.find_saves(saves_db or db))
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
        if path.name.casefold() == 'manifest.json':
            continue  # a pack's manifest describes the pack; it is not a room
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


NEW_CAMPAIGN_ASK = [
    {'key': 'journal_mode', 'question': 'One journal for the whole campaign, or one per character?',
     'options': ['campaign', 'character'],
     'then': 'Pass save --journal-mode <choice> on the first save. It sticks.'},
    {'key': 'master_sheet', 'question': "What's your master sheet?",
     'options': ['D&D Beyond', 'Avrae GSheet', 'paper', 'JSON'],
     'then': 'Pass import-sheet --master-sheet "<their answer>" when the sheet comes in.'},
    {'key': 'sheet_upload', 'question': 'Upload a PDF or JSON of it (or use the example).',
     'options': ['pdf', 'json', 'example'],
     'then': 'A PDF: import-sheet --pdf <file>. A JSON: start --sheet <file>. The example only if they ask for it.'},
]


def saves_line(saves):
    if not saves:
        return ''
    if len(saves) == 1:
        s = saves[0]
        return f" I see a saved game: {s['pc']}, last at {s.get('area') or s['room_id']}. Say if you want to pick it up."
    return f" I see {len(saves)} saved games. Say which one you want to pick up, or start something new."


def _greeting(sheet_path, executable, blocked, saves=()):
    saves = list(saves)
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
        'choices': list(INTENTS),
        'executable_starts': executable,
        'do_not_start': blocked,
        'mad_mage': _mad_mage_facts(),
        'saves': saves,
        'new_campaign': {'ask': NEW_CAMPAIGN_ASK,
                         'note': 'Ask these, in order, when the player starts a new campaign.'},
        'table_line': GREETING + saves_line(saves),
        'next_step': (
            'Say table_line in your own voice if they have not already said what they want: play or build. '
            'Play: run start --intent play [--sheet <file>]. Build: run start --intent build. '
            'Do not mention Dungeon of the Mad Mage unless they did. '
            'Do not pass --room. Do not pass --regression. Do not open do_not_start. '
            'If they want to play and have not named a game, ask which one. '
            'If they asked for Mad Mage, run start --campaign dotmm and say that table_line. '
            'Talk, debrief, and design do not use the bridge.'
            + (' To pick up a listed save: start --save <its path> (add --room <file> if its room '
               'is not attached). Never ask for kit.sqlite.' if saves else '')),
    }


def _sheet_real(sheet_path):
    return bool(sheet_path) and Path(sheet_path).is_file()


def _asked_key(name, unsourced):
    return json.dumps([str(name).casefold(), sorted(str(u['proficiency']).casefold() for u in unsourced)])


def _question_id(key):
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]


def _ensure_question_tables(con):
    con.execute('CREATE TABLE IF NOT EXISTS kit_asked (key TEXT PRIMARY KEY, kind TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS kit_pending_question (id TEXT PRIMARY KEY, key TEXT NOT NULL, '
                'kind TEXT NOT NULL, table_line TEXT NOT NULL, shown INTEGER NOT NULL DEFAULT 0, '
                'carried_turn TEXT)')


def _read(db, sql, args=()):
    path = Path(db) if db else None
    if path is None or not path.is_file():
        return None
    con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        return con.execute(sql, args).fetchone()
    except sqlite3.Error:
        return None
    finally:
        con.close()


def proficiency_question_asked(db, name, unsourced):
    """True when this exact unsourced-proficiency question was delivered to the player in this save."""
    return _read(db, 'SELECT 1 FROM kit_asked WHERE key = ?', (_asked_key(name, unsourced),)) is not None


def record_proficiency_question(db, name, unsourced, table_line=''):
    """Persist the unsourced-proficiency question as PENDING (generated, not yet known delivered).

    Delivery design (host-agnostic; docs in docs/architecture/LOBBY_QUESTIONS.md): a question is
    marked asked only on a positive delivery signal, never when it is generated:
      1. the host confirms with `start --question-delivered <id>` after showing table_line, or
      2. a play turn whose packet carried it as lobby_question commits (`complete` succeeds;
         the committed `spoken` is what the player sees).
    Until then every lobby call raises it again and every play prepare carries it, so a dropped
    reply is asked again. Returns the question id."""
    key = _asked_key(name, unsourced)
    qid = _question_id(key)
    con = sqlite3.connect(str(db))
    try:
        _ensure_question_tables(con)
        # A changed sheet replaces the older pending question of the same kind.
        con.execute('DELETE FROM kit_pending_question WHERE kind = ? AND id != ?', ('proficiency_source', qid))
        con.execute('INSERT INTO kit_pending_question (id, key, kind, table_line, shown) VALUES (?, ?, ?, ?, 1) '
                    'ON CONFLICT(id) DO UPDATE SET shown = shown + 1, table_line = excluded.table_line',
                    (qid, key, 'proficiency_source', table_line or ''))
        con.commit()
    finally:
        con.close()
    return qid


def pending_question(db):
    """The oldest lobby question still awaiting confirmed delivery: {'id', 'table_line', 'shown'} or None."""
    row = _read(db, 'SELECT id, table_line, shown, carried_turn FROM kit_pending_question ORDER BY rowid LIMIT 1')
    return None if row is None else {'id': row[0], 'table_line': row[1], 'shown': row[2], 'carried_turn': row[3]}


def carry_question(db, turn_id):
    """Note that a play turn's packet carries the pending question; its commit confirms delivery."""
    pending = pending_question(db)
    if not pending:
        return None
    con = sqlite3.connect(str(db))
    try:
        con.execute('UPDATE kit_pending_question SET carried_turn = ? WHERE id = ?', (turn_id, pending['id']))
        con.commit()
    finally:
        con.close()
    return pending


# Words that name a kind of proficiency, not the item itself; they never identify the question.
_GENERIC_TERMS = frozenset('supplies supply tools tool kit kits set sets proficiency proficiencies instrument '
                           'instruments the a an of and with'.split())
_ASK_SIGNAL = re.compile(r"\?|\b(?:where|how|why|pitch|tell me|story)\b", re.I)


def _stem(word):
    word = re.sub(r"(?:'s|’s|'|’)$", '', word.casefold())
    return word[:max(5, len(word) - 3)] if len(word) > 5 else word


def question_terms(key):
    """Per unsourced item, the stems that must all appear for a reply to name it:
    'Shield' -> ['shie'... ], "Calligrapher's Supplies" -> ['calligrap']."""
    try:
        _, profs = json.loads(key)
    except (TypeError, ValueError):
        return []
    items = []
    for prof in profs:
        words = [w for w in re.findall(r"[a-z’']+", str(prof).casefold()) if w.strip("'’") not in _GENERIC_TERMS]
        stems = [_stem(w) for w in words if len(w.strip("'’")) > 1]
        if stems:
            items.append(stems)
    return items


def question_asked_in(key, spoken):
    """Host-agnostic check that a reply actually asks the lobby question: every unsourced item is
    named (each of its key stems at a word start, so 'calligraphy' names calligrapher's supplies)
    and the reply asks something (a question mark or an ask word). Wording is Kit's own."""
    text = (spoken or '').casefold()
    items = question_terms(key)
    if not items or not _ASK_SIGNAL.search(text):
        return False
    return all(all(re.search(r'\b' + re.escape(stem), text) for stem in stems) for stems in items)


def carried_question(db, turn_id):
    """The pending question a given play turn carries ({'id','key','table_line'}) or None."""
    if not turn_id:
        return None
    row = _read(db, 'SELECT id, key, table_line FROM kit_pending_question WHERE carried_turn = ?', (turn_id,))
    return None if row is None else {'id': row[0], 'key': row[1], 'table_line': row[2]}


def question_word_allowance(db, turn_id, spoken):
    """Extra words a turn may spend asking its carried lobby question (exempt from the length caps):
    the table line's length, but only when the reply really asks it."""
    carried = carried_question(db, turn_id)
    if not carried or not question_asked_in(carried['key'], spoken):
        return 0
    return len(re.findall(r"[A-Za-z0-9’']+", carried['table_line'] or '')) or 0


def confirm_question_delivered(db, question_id=None, turn_id=None, spoken=None):
    """Mark a pending question asked. By id: the host confirmed it showed table_line. By turn: the
    committed turn that carried it, and only when its spoken reply actually asks it
    (question_asked_in); otherwise it stays pending and rides the next turn. True if one moved."""
    if _read(db, "SELECT name FROM sqlite_master WHERE name = 'kit_pending_question'") is None:
        return False
    con = sqlite3.connect(str(db))
    try:
        if question_id is not None:
            row = con.execute('SELECT id, key, kind FROM kit_pending_question WHERE id = ?', (question_id,)).fetchone()
        else:
            row = con.execute('SELECT id, key, kind FROM kit_pending_question WHERE carried_turn = ?',
                              (turn_id,)).fetchone()
            if row is not None and not question_asked_in(row[1], spoken):
                return False
        if row is None:
            return False
        con.execute('INSERT OR IGNORE INTO kit_asked (key, kind) VALUES (?, ?)', (row[1], row[2]))
        con.execute('DELETE FROM kit_pending_question WHERE id = ?', (row[0],))
        con.commit()
        return True
    finally:
        con.close()


def lobby_sheet(sheet_path, db=None):
    """Load and check the player's sheet in the lobby: real name and proficiency sources.

    With a save (db), the unsourced-proficiency question is kept pending and raised on every
    lobby call until delivery is confirmed (see record_proficiency_question); after that,
    table_line is dropped and already_asked is set."""
    try:
        sheet = json.loads(Path(sheet_path).read_text(encoding='utf-8'))
        pc_sheet.check_sheet(sheet)
    except Exception as exc:  # noqa: BLE001 - a bad sheet is reported, never crashes the lobby
        return {'sheet_loaded': False, 'sheet_problems': [str(exc)]}
    check = kit_chargen.proficiency_sources(sheet)
    name = kit_chargen.character_name(sheet)
    if check.get('unsourced') and db:
        if proficiency_question_asked(db, name, check['unsourced']):
            check.pop('table_line', None)
            check['already_asked'] = True
            check['next_step'] = ('Already asked once in this save. Do not ask again; play it by the rules as '
                                  'written until the player settles it.')
        else:
            qid = record_proficiency_question(db, name, check['unsourced'], check.get('table_line', ''))
            check['already_asked'] = False
            check['question_id'] = qid
            check['delivery'] = (f'Say table_line, then run start --db <db> --question-delivered {qid}. '
                                 'Until it is confirmed (or a play turn carrying it commits) it is raised again.')
    return {'sheet_loaded': True, 'character_loaded': True,
            'character': {'name': name, 'sheet_title': sheet.get('name'),
                          'ancestry': sheet.get('ancestry'), 'class': sheet.get('class'),
                          'level': sheet.get('level')},
            'proficiency_check': check}


def _play(db, sheet_path, executable, blocked, table, modules=None):
    """Play: a real module and a real character, then solo or shared table. Lists only what exists."""
    has_sheet = _sheet_real(sheet_path)
    # The player's table choice holds even while a module or sheet is still missing.
    if table in TABLE_MODES:
        record_table_mode(db, table)
    table = table if table in TABLE_MODES else table_mode(db)
    loaded = lobby_sheet(sheet_path, db) if has_sheet else {}
    if loaded and not loaded['sheet_loaded']:
        has_sheet = False
    # An attached module folder must ride along on every retry, or the rerun loses it.
    mods = f' --modules {shlex.quote(str(modules))}' if modules else ''
    base = {
        'committed': False, 'opened_room': None, 'intent': 'play', 'character_loaded': False,
        'sheet_noted': str(sheet_path) if has_sheet else None, 'sheet_loaded': False,
        'modules_available': executable, 'do_not_start': blocked,
        **loaded, **({'table_mode': table} if table in TABLE_MODES else {}),
    }
    if loaded.get('sheet_problems'):
        base['sheet_noted'] = str(sheet_path)
    need = []
    if not executable:
        need.append('a module')
    if not has_sheet:
        need.append('your character')
    if need:
        return {**base, 'stage': 'need_module' if not executable else 'need_character', 'missing': need,
                'table_line': PLAY_NEEDS_LINES[tuple(need)],
                'next_step': (
                    'Say table_line. List only modules_available (it may be empty) and only a sheet the '
                    'player actually gave. Ask them to attach what is missing. Never offer do_not_start, '
                    'the example sheet, or an adventure they did not name.'
                    + (f' Rerun start --intent play --sheet <file>{mods} once they attach it.' if mods else '')),
                **({'modules': str(modules)} if modules else {})}
    if table not in TABLE_MODES:
        return {**base, 'stage': 'ask_table', 'table_modes': list(TABLE_MODES), 'table_line': TABLE_LINE,
                'next_step': ('Ask which module from modules_available if there is more than one, then '
                              f'say table_line. Rerun start --intent play --sheet <file>{mods} --table solo|shared.'),
                **({'modules': str(modules)} if modules else {})}
    return {**base, 'stage': 'ready', 'table_mode': table,
            **({'table_note': SHARED_NOTE} if table == 'shared' else {}),
            'table_line': SOLO_LINE if table == 'solo' else SHARED_LINE,
            **({'modules': str(modules)} if modules else {}),
            'next_step': ('Run start --room <a path from modules_available> --sheet <file> --table '
                          f'{table}. Then prepare --opening. Show the player only "spoken".')}


def _build(sheet_path):
    """Build: DM-assistant mode. No room, no game state."""
    return {
        'stage': 'build', 'intent': 'build', 'committed': False, 'opened_room': None,
        'character_loaded': False, 'sheet_noted': str(sheet_path) if _sheet_real(sheet_path) else None,
        'tools': {
            'design_talk': 'Scenes, NPCs, encounters, rulings, homebrew: talk, no bridge command.',
            'price_item': ('python -m runtime.kit_appraise "<item description>" (Goldscale formula; '
                           'answer its questions with --answer "<reply>"; --formula shows the math).'),
            'character_building': ('python -m runtime.kit_chargen "<request>". Never guess: beyond SRD 5.1, '
                                   'ask for the exact rules text or the finished sheet, then check it.'),
        },
        'table_line': BUILD_LINE,
        'next_step': ('Say table_line in your own voice. Never guess at character generation (runtime/kit_chargen.py). For a price, run the price_item tool and give '
                      'the Final Price with its impact math. Do not open a room.'),
    }


def record_table_mode(db, mode):
    """Persist the table mode (solo or shared) in the save, beside the game."""
    if mode not in TABLE_MODES:
        raise ValueError(f'table mode must be one of {TABLE_MODES}')
    con = sqlite3.connect(str(db))
    try:
        con.execute('CREATE TABLE IF NOT EXISTS kit_table (id INTEGER PRIMARY KEY CHECK (id = 1), mode TEXT NOT NULL)')
        con.execute('INSERT INTO kit_table (id, mode) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET mode=excluded.mode',
                    (mode,))
        con.commit()
    finally:
        con.close()


def table_mode(db):
    """The recorded table mode, or None."""
    path = Path(db)
    if not path.is_file():
        return None
    con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        row = con.execute('SELECT mode FROM kit_table WHERE id = 1').fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


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
