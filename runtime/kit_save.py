"""Player-safe save: `kit_agent save` (campaign-record design P1 + P2).

kit.sqlite is runtime-only. It holds the whole room file (hidden facts, DCs, claims,
secret actors and exits, book text) and Kit's private decisions, so it never leaves
the runtime. What the player downloads is a ZIP of:

  campaign.json                 kit_campaign_v1, player-safe
  journal.md                    rendered from campaign.json (or characters/<pc>/journal.md
                                in per-character mode); ends in a kit-state block
  characters/<pc>/sheet.json    the player's character_sheet_v1
  characters/<pc>/sheet.md      a render of that sheet

Everything exported is built from a whitelist: the public player view, what the player
learned, the player's own sheet and words, ids, counts and hashes. Nothing is copied out
of the room file wholesale or out of Kit's trace.

P2: the public record of a room is folded into state['campaign_log'] at room exit
(kit_rooms.mounted_state; the room file is replaced once the next room mounts) and again on
every save. Kit's recap is hers: <=120 words, checked like public text. Hand edits are taken
as written and noted, never arbitrated (docs/architecture/PLAYER_SAVE.md). Standard library only.
"""

import hashlib
import json
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

CAMPAIGN_SCHEMA = 'kit_campaign_v1'
EXPORT_PHASE = 'p5'
ZIP_STAMP = (2026, 1, 1, 0, 0, 0)  # fixed member times
JOURNAL_MODES = ('campaign', 'character')
RECAP_MAX_WORDS = 120
CHOICES_MAX = 20
DC_TEXT = re.compile(r'(?i)\bDC\s*\d+')


class SaveError(Exception):
    pass


def slug(text, default):
    out = re.sub(r'[^a-z0-9]+', '-', str(text or '').lower()).strip('-')
    return out or default


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _default_campaign(room_id):
    return 'dotmm' if str(room_id).lower().startswith('dotmm') else 'solo'


# --- the public record of one room -------------------------------------------------------

def room_record(source, state, status):
    """What the player saw of a room: area names visited, people seen, facts learned,
    what they took. Only the public half: invisible actors, unrevealed facts and secret
    exits never enter it."""
    from .kit_rooms import known_fact_ids, _room_totals
    areas = source.get('areas') or {}
    visited = [a for a in state.get('visited') or () if a in areas]
    facts = source.get('facts') or {}
    learned = [facts[k]['text'] for k in sorted(known_fact_ids(source, state)) if k in facts]
    met = [{'name': a['name'], 'status': a['status']}
           for a in (state.get('actors') or {}).values()
           if a.get('visible') and a.get('location') in visited]
    took = _room_totals(state)[1]
    exits = source.get('exits') or {}
    carry = {  # P4: ids of what the player already knows, so a room left can be found as left
        'visited': visited,
        'known_facts': [k for k in state.get('known_facts') or () if k in facts],
        'known_exits': [k for k in state.get('known_exits') or () if k in exits],
        'actors': {k: a['status'] for k, a in (state.get('actors') or {}).items()
                   if a.get('visible') and a.get('location') in visited},
        'resources': {k: v for k, v in (state.get('resources') or {}).items() if type(v) is int},
    }
    return {'room_id': source.get('id'), 'status': status,
            'areas': [areas[a]['name'] for a in visited],
            'npcs_met': met, 'learned': learned, 'took': list(took), 'carry': carry}


ACTOR_STATUSES = ('alive', 'unconscious', 'dead', 'fled')


def check_carry(carry):
    """A room's carry record: ids and statuses only."""
    from .state_context import require
    if carry is None:
        return
    ids = lambda v: isinstance(v, list) and len(v) <= 200 and all(isinstance(i, str) and len(i) <= 120 for i in v)
    require(isinstance(carry, dict) and set(carry) <= {'visited', 'known_facts', 'known_exits', 'actors', 'resources'},
            'carry is {visited, known_facts, known_exits, actors, resources}')
    for key in ('visited', 'known_facts', 'known_exits'):
        require(key not in carry or ids(carry[key]), f'carry.{key} lists ids')
    require(isinstance(carry.get('actors', {}), dict) and all(
        isinstance(k, str) and v in ACTOR_STATUSES for k, v in carry.get('actors', {}).items()),
        'carry.actors maps actor id to alive, unconscious, dead or fled')
    require(isinstance(carry.get('resources', {}), dict) and all(
        isinstance(k, str) and type(v) is int and v >= 0 for k, v in carry.get('resources', {}).items()),
        'carry.resources maps a resource to a count')


def carry_for(state, room_id):
    for record in (state.get('campaign_log') or {}).get('rooms') or ():
        if record.get('room_id') == room_id:
            return record.get('carry')
    return None


def apply_carry(new, source, carry):
    """A room mounted fresh that the player left before: what they knew and did stays.
    Only ids the room file still has; secrets the player never learned stay as written."""
    if not carry:
        return
    areas, facts, exits = source.get('areas') or {}, source.get('facts') or {}, source.get('exits') or {}
    for key, pool in (('visited', areas), ('known_facts', facts), ('known_exits', exits)):
        for item in carry.get(key) or ():
            if item in pool and item not in new[key]:
                new[key].append(item)
    for key, status in (carry.get('actors') or {}).items():
        if key in new['actors'] and status in ACTOR_STATUSES:
            new['actors'][key]['status'] = status
    for key, value in (carry.get('resources') or {}).items():
        if key in new['resources'] and type(value) is int:
            new['resources'][key] = value


def pc_state(state):
    """What the PC carries besides the sheet: spent slots and uses, and conditions."""
    from . import kit_reactions
    res = kit_reactions.current(state) if state.get('player_sheet') else {}
    return {'slots': {k: v.get('used', 0) for k, v in (res.get('slots') or {}).items()},
            'uses': {k: v.get('used', 0) for k, v in (res.get('uses') or {}).items()},
            'conditions': list(state.get('pc_conditions') or ())}


def fold_room_exit(old_source, state, new_state):
    """Called as the PC leaves a room for another: keep that room's public record."""
    from .kit_rooms import resolution
    log = dict(state.get('campaign_log') or {})
    record = room_record(old_source, state, resolution(old_source, state))
    log['rooms'] = [r for r in log.get('rooms') or () if r['room_id'] != record['room_id']] + [record]
    new_state['campaign_log'] = log


# --- collecting the campaign -------------------------------------------------------------

def _open(db):
    path = Path(db)
    if not path.is_file():
        raise SaveError(f'No game to save at {db}. Run start first; save writes the player files '
                        'for the game in that kit.sqlite.')
    from .state_context import Runtime
    runtime = Runtime(str(path))
    if runtime.db.execute('SELECT 1 FROM source').fetchone() is None:
        runtime.close()
        raise SaveError(f'{db} has no room mounted yet. Run start first.')
    return runtime


def _choices(runtime):
    rows = runtime.db.execute('''SELECT kit_turns.turn_id, kit_turns.body FROM kit_turns
        JOIN turns ON turns.id = kit_turns.turn_id ORDER BY turns.revision''').fetchall()
    out = []
    for turn_id, body in rows:
        record = json.loads(body)
        said = (record.get('player_input') or '').strip()
        if said and not record.get('table_talk') and record.get('turn_role') != 'interstitial':
            out.append({'said': said[:300], 'turn_id': turn_id})
    return out[-CHOICES_MAX:]


def collect(runtime):
    """(campaign, sheet or None, public view for guards) for the game in this runtime."""
    from .kit_rooms import fold_pc
    revision, state = runtime.load()
    source = runtime.source()
    view = runtime.player_view()
    raw = runtime.db.execute('SELECT body FROM source').fetchone()[0]
    turns = runtime.db.execute('SELECT COUNT(*) FROM kit_turns').fetchone()[0]
    last = runtime.db.execute('SELECT id FROM turns ORDER BY revision DESC LIMIT 1').fetchone()
    sheet, carried, _ = fold_pc(source, state)  # as if the room were left now
    pc = state.get('player_character') or {}
    pc_id = slug((sheet or {}).get('name') or pc.get('name'), 'pc')
    room_id = source['id']
    provenance = {'room_id': room_id, 'turn_id': last[0] if last else None}
    current = room_record(source, state, 'current')
    log = [r for r in (state.get('campaign_log') or {}).get('rooms') or () if r['room_id'] != room_id]
    rooms = log + [current]
    campaign = {
        'schema': CAMPAIGN_SCHEMA,
        'export': {'phase': EXPORT_PHASE, 'revision': revision,
                   'saved_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                   'runtime_only': ['kit.sqlite', 'dm-notes.json']},
        'journal_mode': 'campaign',
        'pcs': [pc_id],
        'pc': {'id': pc_id, **{k: pc[k] for k in ('name', 'ancestry', 'class', 'level') if k in pc}},
        'sheet_source': {**{'kind': 'json' if sheet else 'other', 'named_by_player': None,
                            'imported_at': None, 'at': None},
                         **{k: v for k, v in (state.get('sheet_import') or {}).items()
                            if k in ('kind', 'named_by_player', 'imported_at', 'at')}},
        'location': {'room_id': room_id, 'area': view['area'], **provenance},
        'rooms': [{'room_id': r['room_id'], 'status': r['status'], 'areas': r['areas'],
                   **({'carry': r['carry']} if r['status'] != 'current' and r.get('carry') else {})} for r in rooms],
        'pc_state': pc_state(state),
        'npcs_met': [{**n, 'room_id': r['room_id']} for r in rooms for n in r['npcs_met']],
        'learned': [{'text': t, 'room_id': r['room_id']} for r in rooms for t in r['learned']],
        'loot': [{'item': c['item'], 'room_id': c.get('from')} for c in carried],
        'gold_gp': (sheet or {}).get('gold_gp'),
        'debts': [], 'threads': [], 'choices': _choices(runtime),
        'sessions': [{'revision': revision, 'turns': turns, **provenance}],
        'edits': [],
        'source_hashes': {room_id: sha(raw)},
    }
    guard = {'view': view, 'source': source, 'state': state,
             'said': ' '.join(c['said'] for c in campaign['choices'])}
    return campaign, sheet, guard


# --- Kit's recap -------------------------------------------------------------------------

def _hidden_literals(source, state):
    """Literal hidden strings of the current room: unrevealed facts, unseen actors, secret exits."""
    from .kit_rooms import known_fact_ids
    known = known_fact_ids(source, state)
    out = [f['text'] for k, f in (source.get('facts') or {}).items() if k not in known]
    out += [a['name'] for a in (state.get('actors') or {}).values() if not a.get('visible')]
    for key, edge in (source.get('exits') or {}).items():
        if edge.get('secret') and key not in (state.get('known_exits') or ()):
            out += [edge.get('name') or ''] + list((edge.get('labels') or {}).values())
    return [s for s in out if s and len(s) >= 6]


def check_recap(recap, campaign, guard):
    """Kit's recap: her voice, short, and only public text (the same leak guards as play)."""
    from . import kit_guards
    from .kit_agent import check_public_content
    from .state_context import InvalidChange
    if not isinstance(recap, str) or not recap.strip():
        raise SaveError('The recap is empty. Write one to three sentences in Kit\'s voice, or leave it out.')
    words = len(recap.split())
    if words > RECAP_MAX_WORDS:
        raise SaveError(f'The recap has {words} words; keep it to {RECAP_MAX_WORDS} or fewer.')
    if DC_TEXT.search(recap):
        raise SaveError('The recap names a DC. Keep numbers the player never saw out of it.')
    lower = recap.lower()
    for item in _hidden_literals(guard['source'], guard['state']):
        if item.lower() in lower:
            raise SaveError('The recap mentions something the player has not learned. '
                            'Recap only what happened in front of them.')
    public = {'view': guard['view'], 'learned': campaign['learned'], 'met': campaign['npcs_met']}
    source = guard['source']
    try:
        check_public_content(recap, public, guard['said'], kit_guards.leak_sets(source),
                             kit_guards.leak_phrases(source))
    except InvalidChange as exc:
        raise SaveError(f'The recap failed the public-text check ({exc}). '
                        'Recap only what happened in front of the player.') from exc
    return recap.strip()


# --- rendering ---------------------------------------------------------------------------

def journal_name(campaign):
    if campaign.get('journal_mode') == 'character':
        return f'characters/{campaign["pcs"][0]}/journal.md'
    return 'journal.md'


def journal_md(campaign, written=None):
    pc, loc = campaign['pc'], campaign['location']
    who = pc.get('name') or pc['id']
    about = ', '.join(str(pc[k]) for k in ('ancestry', 'class') if pc.get(k))
    if pc.get('level'):
        about += f', level {pc["level"]}'
    people = [f'- {n["name"]} ({n["status"]}), {n["room_id"]}' for n in campaign.get('npcs_met') or ()]
    loot = [f'- {item["item"]} (from {item["room_id"]})' for item in campaign.get('loot') or ()]
    gold = campaign.get('gold_gp')
    debts = [f'- {_flat(d)}' for d in campaign.get('debts') or ()]
    threads = [f'- {_flat(t)}' for t in campaign.get('threads') or ()]
    learned = [f'- {f["text"]}' for f in campaign.get('learned') or ()]
    log = []
    entries = sorted(campaign.get('sessions') or (), key=lambda s: s.get('revision') or 0, reverse=True)
    edits = sorted(campaign.get('edits') or (), key=lambda e: e.get('revision') or 0, reverse=True)
    for entry in entries:
        line = f'- Revision {entry.get("revision")}: {entry.get("turns", 0)} turns'
        if entry.get('saved_at'):
            line += f', saved {entry["saved_at"]}'
        log.append(line + '.')
        if entry.get('recap'):
            log.append(f'  {entry["recap"]}')
        for edit in edits:
            if edit.get('revision') == entry.get('revision'):
                log.append(f'  {edit["file"]} edited by player{": " + edit["note"] if edit.get("note") else ""}.')
    state = {k: campaign.get(k) for k in ('schema', 'journal_mode', 'pcs', 'location', 'source_hashes')}
    state['revision'] = campaign['export']['revision']
    state['player'] = campaign['export'].get('player')
    state['campaign'] = campaign['export'].get('campaign')
    state['written'] = written or {}
    lines = [
        f'# Journal: {who}', '',
        f'- Character: {who}' + (f' ({about})' if about else ''),
        f'- Where: {loc["area"]} ({loc["room_id"]})',
        f'- Saved: {campaign["export"]["saved_at"]} (revision {campaign["export"]["revision"]})',
        '- Rendered from campaign.json. Edit campaign.json or your sheet; prose here is not read back.',
        '', '## Threads', '', *(threads or ['- None recorded yet.']),
        '', '## People met', '', *(people or ['- No one yet.']),
        '', '## What you learned', '', *(learned or ['- Nothing yet.']),
        '', '## Loot and coin', '',
        f'- Gold: {gold} gp (from your sheet)' if gold is not None else '- Gold: not on the sheet.',
        *loot,
        '', '## Debts', '', *(debts or ['- None recorded yet.']),
        '', '## Session log', '', *(log or ['- No sessions yet.']),
        '', '```kit-state', json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), '```', '']
    return '\n'.join(lines)


def kit_state(journal_text):
    """The kit-state block of a journal, or None."""
    match = re.search(r'```kit-state\n(.*?)\n```', journal_text or '', re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def _flat(value):
    if isinstance(value, dict):
        return ', '.join(f'{k} {_flat(v)}' for k, v in value.items())
    if isinstance(value, list):
        return ', '.join(_flat(v) for v in value)
    return str(value)


def sheet_md(sheet):
    top = ('name', 'ancestry', 'class', 'level', 'background', 'alignment', 'size', 'schema', '_note')
    lines = [f'# {sheet.get("name", "Character")}', '']
    about = ', '.join(str(sheet[k]) for k in ('ancestry', 'class') if sheet.get(k))
    if sheet.get('level'):
        about += f', level {sheet["level"]}'
    if about:
        lines += [about, '']
    for key in ('background', 'alignment', 'size'):
        if sheet.get(key):
            lines.append(f'- {key.title()}: {sheet[key]}')
    labels = {'ac': 'AC', 'hp': 'HP', 'speed_ft': 'Speed (ft)', 'spell_save_dc': 'Spell save DC',
              'spell_attack': 'Spell attack', 'gold_gp': 'Gold (gp)', 'proficiency_bonus': 'Proficiency bonus'}
    for key, label in labels.items():
        if key in sheet:
            lines.append(f'- {label}: {_flat(sheet[key])}')
    lines.append('')
    for key, value in sheet.items():
        if key in top or key in labels:
            continue
        lines += [f'## {key.replace("_", " ").title()}', '']
        if isinstance(value, dict):
            lines += [f'- {k}: {_flat(v)}' for k, v in value.items()]
        elif isinstance(value, list):
            lines += [f'- {_flat(v)}' for v in value]
        else:
            lines.append(f'- {value}')
        lines.append('')
    lines.append('Rendered from sheet.json. Your sheet is yours: edit sheet.json, not this file.')
    return '\n'.join(lines) + '\n'


# --- what is already in the save folder --------------------------------------------------

def _read(path):
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None


def prior(folder):
    """What the last save left in this folder: {campaign, campaign_text, journal, sheet_texts}."""
    out = {'campaign': None, 'campaign_text': _read(folder / 'campaign.json'), 'written': {}}
    if out['campaign_text']:
        try:
            out['campaign'] = json.loads(out['campaign_text'])
        except ValueError:
            out['campaign'] = None
    journals = [folder / 'journal.md'] + sorted((folder / 'characters').glob('*/journal.md'))
    for path in journals:
        state = kit_state(_read(path))
        if state:
            out['written'] = state.get('written') or {}
            break
    return out


def merge(fresh, old, edited_campaign, mode):
    """The campaign to write: fresh from the runtime unless the player's edit stands."""
    if old and edited_campaign and (old.get('export') or {}).get('revision') == fresh['export']['revision']:
        base = old  # equal revision, different hash: the player's edit, taken as written
    else:
        base = fresh
        if old:
            for key in ('debts', 'threads'):
                base[key] = old.get(key) or base[key]  # player-kept lists the engine does not write yet
            sessions = [s for s in old.get('sessions') or () if s.get('revision') != fresh['export']['revision']]
            base['sessions'] = sessions + fresh['sessions']
            base['edits'] = list(old.get('edits') or ())
            base['journal_mode'] = old.get('journal_mode') or 'campaign'
    if mode:
        base['journal_mode'] = mode
    base.setdefault('sessions', [])
    base.setdefault('edits', [])
    return base


def save(db, out=None, player=None, campaign=None, journal_mode=None, recap=None):
    """Fold the ledger and write saves/<player>/<campaign>/ next to db, plus a ZIP of it.
    Never copies kit.sqlite. Nothing is written if the recap fails its checks."""
    if journal_mode is not None and journal_mode not in JOURNAL_MODES:
        raise SaveError(f'journal mode is one of {", ".join(JOURNAL_MODES)}')
    runtime = _open(db)
    try:
        record, sheet, guard = collect(runtime)
    except sqlite3.Error as exc:
        raise SaveError(f'Could not read {db}: {exc}') from exc
    finally:
        runtime.close()
    if recap is not None:
        recap = check_recap(recap, record, guard)
    player_id = slug(player, 'player')
    campaign_id = slug(campaign, _default_campaign(record['location']['room_id']))
    folder = Path(db).resolve().parent / 'saves' / player_id / campaign_id
    pc_id = record['pcs'][0]
    sheet_name = f'characters/{pc_id}/sheet.json'
    before = prior(folder)
    written = before['written']
    revision = record['export']['revision']
    noticed = []

    # The player owns the sheet: an edited sheet is taken as written.
    sheet_text = _read(folder / sheet_name)
    if sheet_text is not None and written.get(sheet_name) and sha(sheet_text) != written[sheet_name]:
        try:
            sheet = json.loads(sheet_text)
            noticed.append(sheet_name)
        except ValueError:
            noticed.append(sheet_name)  # unreadable edit: noted; the engine copy is written alongside
    edited_campaign = bool(before['campaign_text'] and written.get('campaign.json')
                           and sha(before['campaign_text']) != written['campaign.json'])
    if edited_campaign:
        noticed.append('campaign.json')
    result = merge(record, before['campaign'], edited_campaign, journal_mode)
    result['export'] = {**record['export'], **({'revision': result['export']['revision']}
                                               if result is before['campaign'] else {}),
                        'player': player_id, 'campaign': campaign_id}
    if sheet and sheet.get('gold_gp') is not None:
        result['gold_gp'] = sheet['gold_gp']
    if recap:
        last = next((s for s in reversed(result['sessions']) if s.get('revision') == revision), None)
        if last is None:
            last = dict(record['sessions'][-1])
            result['sessions'].append(last)
        last['recap'] = recap
    for entry in result['sessions']:
        if entry.get('revision') == revision:
            entry['saved_at'] = record['export']['saved_at']
    for name in noticed:
        note = None if result is before['campaign'] or name != 'campaign.json' else \
            f'superseded by revision {revision}'
        result['edits'].append({'file': name, 'revision': revision, **({'note': note} if note else {})})

    files = {'campaign.json': json.dumps(result, indent=2, ensure_ascii=False) + '\n'}
    if sheet:
        files[sheet_name] = (sheet_text if sheet_name in noticed and sheet_text is not None
                             else json.dumps(sheet, indent=2, ensure_ascii=False) + '\n')
        files[f'characters/{pc_id}/sheet.md'] = sheet_md(sheet)
    hashes = {name: sha(text) for name, text in files.items() if name.endswith('.json')}
    files[journal_name(result)] = journal_md(result, hashes)

    for stale in [folder / 'journal.md'] + list((folder / 'characters').glob('*/journal.md')):
        if stale.relative_to(folder).as_posix() not in files and stale.is_file():
            stale.unlink()
    for name, text in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    archive = Path(out).resolve() if out else folder / f'kit-save-{campaign_id}-{pc_id}.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, ZIP_STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    step = ('Offer the player this ZIP as a download, and say in one line that it is their save '
            '(campaign, journal, sheet). Never offer kit.sqlite: it is runtime-only and holds '
            'hidden room state. Save at every room exit, when the player says save, and on stop.')
    if not recap:
        step += (' For the journal, write a recap in your own voice (at most 120 words, only what '
                 'happened in front of the player) to a file and run save again with --recap-file <file>.')
    if noticed:
        step += (' The player edited ' + ', '.join(noticed) + '; it was taken as written. You may mention '
                 'it once, lightly, in your own voice. Do not ask them to confirm it.')
    return {
        'stage': 'saved', 'zip': str(archive), 'folder': str(folder), 'files': sorted(files),
        'revision': revision, 'location': result['location']['area'], 'noticed': noticed,
        'journal_mode': result['journal_mode'], 'next_step': step,
    }
