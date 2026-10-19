"""Resume from the player's save (campaign-record design P3). Standard library only.

The save is the ZIP (or folder) that `save` writes. kit.sqlite never travels, so:

- a kit.sqlite here that matches campaign.location continues mid-room (the existing resume);
- otherwise the save's current room mounts fresh at its start, with campaign.json applied:
  the rooms left, people met, facts learned and loot carried (campaign_log), and the
  player's sheet as written. Mid-room hidden state is not rebuilt (design Q1: yes);
- only the journal survived: rebuild from its kit-state block;
- neither: Kit asks the player once and they confirm (stage needs_rebuild).

find_saves() is what the greeting lists. Nothing here reads a room's hidden content into
the result; the room file is found by id and mounted the normal way.
"""

import json
import zipfile
from pathlib import Path, PurePosixPath

from . import kit_rooms, kit_save
from .state_context import PROJECT_ROOT, InvalidChange

UPLOAD_DIRS = ('/mnt/data', '/mnt/user-data/uploads', '/mnt/user-data')  # ChatGPT, Claude
MEMBER_MAX_BYTES = 2_000_000
SEARCH_DEPTH_GLOBS = ('*.json', '*/*.json', '*/*/*.json')


class ResumeError(InvalidChange):
    pass


def _safe_member(name):
    path = PurePosixPath(name)
    return bool(path.parts) and not name.startswith('/') and '\\' not in name \
        and ':' not in path.parts[0] and '..' not in path.parts


def load_save(path):
    """{name: text} of a save ZIP or folder (only the player files)."""
    path = Path(path)
    files = {}
    if path.is_dir():
        for item in [path / 'campaign.json', path / 'journal.md',
                     *sorted(path.glob('characters/*/sheet.json')), *sorted(path.glob('characters/*/journal.md'))]:
            if item.is_file():
                files[item.relative_to(path).as_posix()] = item.read_text(encoding='utf-8')
        return files
    if not path.is_file():
        raise ResumeError(f'No save at {path}. Pass the save ZIP the player uploaded, or its folder.')
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if not _safe_member(info.filename):
                    raise ResumeError(f'{path} has an unsafe file name ({info.filename!r}); not reading it.')
                name = info.filename
                if name.count('/') == 1 and not name.startswith('characters/'):
                    name = name.split('/', 1)[1]  # a ZIP of the folder itself: <campaign>/campaign.json
                if not (name in ('campaign.json', 'journal.md') or
                        (name.startswith('characters/') and name.endswith(('/sheet.json', '/journal.md')))):
                    continue
                if info.file_size > MEMBER_MAX_BYTES:
                    raise ResumeError(f'{info.filename} in {path} is too large for a save file.')
                files[name] = archive.read(info).decode('utf-8')
    except zipfile.BadZipFile as exc:
        raise ResumeError(f'{path} is not a ZIP file.') from exc
    return files


def _journal(files):
    for name in ['journal.md'] + sorted(n for n in files if n.endswith('/journal.md')):
        if name in files:
            return name, files[name]
    return None, None


def read_campaign(files):
    """(campaign, rebuilt_from_journal) or (None, False) when neither campaign.json nor kit-state survives."""
    if 'campaign.json' in files:
        try:
            campaign = json.loads(files['campaign.json'])
            if isinstance(campaign, dict) and (campaign.get('location') or {}).get('room_id'):
                return campaign, False
        except ValueError:
            pass
    state = kit_save.kit_state(_journal(files)[1])
    if state and (state.get('location') or {}).get('room_id'):
        return {'schema': kit_save.CAMPAIGN_SCHEMA, 'journal_mode': state.get('journal_mode') or 'campaign',
                'pcs': state.get('pcs') or ['pc'], 'location': state['location'],
                'source_hashes': state.get('source_hashes') or {},
                'export': {'revision': state.get('revision'), 'player': state.get('player'),
                           'campaign': state.get('campaign')},
                'rooms': [], 'npcs_met': [], 'learned': [], 'loot': [], 'sessions': [], 'edits': []}, True
    return None, False


def find_room(room_id, search):
    for folder in search:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for pattern in SEARCH_DEPTH_GLOBS:
            for path in sorted(folder.glob(pattern)):
                try:
                    body = json.loads(path.read_text(encoding='utf-8'))
                except (OSError, ValueError, UnicodeDecodeError):
                    continue
                if isinstance(body, dict) and body.get('id') == room_id and 'areas' in body:
                    return path
    return None


def default_search(db):
    return [Path(db).resolve().parent, Path.cwd(), PROJECT_ROOT / 'rooms', *map(Path, UPLOAD_DIRS)]


def _restore(campaign, current_id):
    """campaign_log and carried for the runtime, from campaign.json (public data only)."""
    rooms = []
    for room in campaign.get('rooms') or ():
        rid = room.get('room_id')
        if not isinstance(rid, str) or rid == current_id or room.get('status') == 'current':
            continue
        rooms.append({'room_id': rid, 'status': room.get('status') if room.get('status') in ('left', 'bypassed') else 'left',
                      'areas': [a for a in room.get('areas') or () if isinstance(a, str)],
                      'npcs_met': [{'name': n['name'], 'status': n.get('status', 'alive')}
                                   for n in campaign.get('npcs_met') or ()
                                   if isinstance(n, dict) and n.get('room_id') == rid and isinstance(n.get('name'), str)],
                      'learned': [f['text'] for f in campaign.get('learned') or ()
                                  if isinstance(f, dict) and f.get('room_id') == rid and isinstance(f.get('text'), str)],
                      'took': [i['item'] for i in campaign.get('loot') or ()
                               if isinstance(i, dict) and i.get('room_id') == rid and isinstance(i.get('item'), str)],
                      **({'carry': room['carry']} if isinstance(room.get('carry'), dict) else {})})
    carried = [{'item': i['item'], 'from': i['room_id']} for i in campaign.get('loot') or ()
               if isinstance(i, dict) and isinstance(i.get('item'), str) and i.get('room_id') != current_id]
    pc = campaign.get('pc_state') if isinstance(campaign.get('pc_state'), dict) else None
    return {'log': {'rooms': rooms}, 'carried': carried, **({'pc_state': pc} if pc else {})}


def resume(db, save_path, room=None, sheet=None, search=None, manifests=False):
    """Resume a game from the player's save. See the module docstring."""
    from .kit_agent import start_session
    from .kit_campaign import _resume, need_character, saved_game
    files = load_save(save_path)
    campaign, rebuilt = read_campaign(files)
    if campaign is None:
        return {
            'stage': 'needs_rebuild', 'committed': False, 'opened_room': None, 'save': str(save_path),
            'table_line': ("I can read your journal, but not where we stopped. Tell me the room and give me "
                           "your sheet, and I'll pick it up from the start of that room."),
            'next_step': ('The save has no campaign.json and no kit-state block. Ask the player once which room '
                          'they were in and for their sheet, read it back to them and have them confirm, then '
                          'run start --room <file> --sheet <file>. Do not guess a room.'),
        }
    room_id = campaign['location']['room_id']
    saved = saved_game(db)
    if saved is not None:
        if saved.get('room_id') == room_id:
            return {**_resume(saved, None), 'from_save': str(save_path)}
        raise ResumeError(f'{db} already holds a game in {saved.get("room_id")}, not {room_id}. '
                          'Pass a new --db to resume this save.')
    if room:
        source = kit_rooms.load_room(room)
        if source.get('id') != room_id:
            raise ResumeError(f'{room} is room {source.get("id")!r}; the save stopped in {room_id!r}.')
        room_path = Path(room)
    else:
        room_path = find_room(room_id, search if search is not None else default_search(db))
        if room_path is None:
            raise ResumeError(f'The save stopped in room {room_id!r}, and no room file with that id is here. '
                              'Attach the rooms pack or pass --room <file>.')
    export = campaign.get('export') or {}
    player_id = kit_save.slug(export.get('player'), 'player')
    campaign_id = kit_save.slug(export.get('campaign'), kit_save._default_campaign(room_id))
    pc_id = (campaign.get('pcs') or ['pc'])[0]
    sheet_name = f'characters/{pc_id}/sheet.json'
    if sheet is None and sheet_name not in files:
        return {**need_character(room_path, kit_rooms.load_room(room_path)), 'from_save': str(save_path)}
    written = (kit_save.kit_state(_journal(files)[1]) or {}).get('written') or {}
    noticed = [n for n in ('campaign.json', sheet_name)
               if n in files and written.get(n) and kit_save.sha(files[n]) != written[n]]

    folder = Path(db).resolve().parent / 'saves' / player_id / campaign_id
    for name, text in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    if noticed:  # reported now; the next save should not report the same edit again
        jname, jtext = _journal(files)
        state = kit_save.kit_state(jtext)
        state['written'] = {**written, **{n: kit_save.sha(files[n]) for n in noticed}}
        start, end = jtext.index('```kit-state\n'), jtext.rindex('```')
        new = jtext[:start] + '```kit-state\n' + json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + '\n' + jtext[end:]
        (folder / jname).write_text(new, encoding='utf-8')
    sheet_path = Path(sheet) if sheet else folder / sheet_name
    restore = _restore(campaign, room_id)
    result = start_session(str(db), str(sheet_path), room=str(room_path), manifests=manifests, restore=restore)
    from .state_context import Runtime
    runtime = Runtime(str(db))
    try:
        raw = runtime.db.execute('SELECT body FROM source').fetchone()[0]
        area = runtime.player_view()['area']
    finally:
        runtime.close()
    expected = (campaign.get('source_hashes') or {}).get(room_id)
    changed = bool(expected) and kit_save.sha(raw) != expected
    line = f"We pick this up at the start of {area}. What came before is as your journal has it."
    if changed:
        line += " This room's file changed since your save, so it may not match what you remember."
    step = result['next_step']
    if noticed:
        step += (' The player edited ' + ', '.join(noticed) + ' since the save; it was taken as written. '
                 'You may mention it once, lightly. Do not ask them to confirm it.')
    return {**result, 'stage': 'resumed_from_save', 'from_save': str(save_path), 'save_folder': str(folder),
            'rebuilt_from_journal': rebuilt, 'noticed': noticed, 'room_changed': changed,
            'room_status': [{'room_id': r['room_id'], 'status': r['status']} for r in restore['log']['rooms']],
            'table_line': line, 'next_step': step}


def _entry(path, kind, files):
    campaign, _ = read_campaign(files)
    if campaign is None:
        return None
    export = campaign.get('export') or {}
    sessions = sorted(campaign.get('sessions') or (), key=lambda s: s.get('revision') or 0)
    last = sessions[-1] if sessions else {}
    return {'path': str(path), 'kind': kind,
            'player': kit_save.slug(export.get('player'), 'player'),
            'campaign': kit_save.slug(export.get('campaign'), kit_save._default_campaign(campaign['location']['room_id'])),
            'pc': (campaign.get('pc') or {}).get('name') or (campaign.get('pcs') or ['pc'])[0],
            'room_id': campaign['location']['room_id'], 'area': campaign['location'].get('area'),
            'last_session': {k: last.get(k) for k in ('revision', 'saved_at', 'recap')},
            'open_threads': len(campaign.get('threads') or ())}


def find_saves(db, dirs=None):
    """Saves the greeting can list: folders under saves/ next to db, and save ZIPs nearby or uploaded."""
    found, seen = [], set()
    root = Path(db).resolve().parent
    for campaign in sorted((root / 'saves').glob('*/*/campaign.json')):
        entry = _entry(campaign.parent, 'folder', load_save(campaign.parent))
        if entry:
            found.append(entry)
            seen.add(campaign.parent.resolve())
    for folder in dirs if dirs is not None else [root, Path.cwd(), *map(Path, UPLOAD_DIRS)]:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob('*.zip')):
            if path.resolve() in seen:
                continue
            seen.add(path.resolve())
            try:
                with zipfile.ZipFile(path) as archive:
                    names = archive.namelist()
                if not any(n == 'campaign.json' or n.endswith('/campaign.json') and n.count('/') == 1
                           or n.endswith('journal.md') for n in names):
                    continue
                entry = _entry(path, 'zip', load_save(path))
            except (ResumeError, zipfile.BadZipFile, OSError, UnicodeDecodeError):
                continue
            if entry:
                found.append(entry)
    return found
