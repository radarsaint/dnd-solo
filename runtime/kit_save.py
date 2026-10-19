"""Player-safe save (P1 of the campaign-record design): `kit_agent save`.

kit.sqlite is runtime-only. It holds the whole room file (hidden facts, DCs, claims,
secret actors and exits, book text) and Kit's private decisions, so it never leaves
the runtime. What the player downloads is a ZIP of:

  campaign.json                 kit_campaign_v1, player-safe
  journal.md                    rendered from campaign.json; ends in a kit-state block
  characters/<pc>/sheet.json    the player's character_sheet_v1, as loaded
  characters/<pc>/sheet.md      a render of that sheet

Everything exported is built from a whitelist: the public player view, the player's own
sheet, ids, counts and hashes. Nothing is copied out of the room file or Kit's trace.
P1 is the leak fix only; the ledger fold, recap and resume are P2/P3
(docs/architecture/PLAYER_SAVE.md). Standard library only.
"""

import hashlib
import json
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

CAMPAIGN_SCHEMA = 'kit_campaign_v1'
EXPORT_PHASE = 'p1'
ZIP_STAMP = (2026, 1, 1, 0, 0, 0)  # fixed member times: same content, same bytes


class SaveError(Exception):
    pass


def slug(text, default):
    out = re.sub(r'[^a-z0-9]+', '-', str(text or '').lower()).strip('-')
    return out or default


def _default_campaign(room_id):
    return 'dotmm' if str(room_id).lower().startswith('dotmm') else 'solo'


def _open(db):
    path = Path(db)
    if not path.is_file():
        raise SaveError(f'No game to save at {db}. Run start first; save writes the player files '
                        'for the game in that kit.sqlite.')
    from .state_context import Runtime  # local: keeps this module cheap to import
    runtime = Runtime(str(path))
    if runtime.db.execute('SELECT 1 FROM source').fetchone() is None:
        runtime.close()
        raise SaveError(f'{db} has no room mounted yet. Run start first.')
    return runtime


def collect(runtime):
    """The player-safe record of the game in this runtime: (campaign, sheet or None)."""
    revision, state = runtime.load()
    source = runtime.source()
    view = runtime.player_view()  # the public view the player is already shown
    raw = runtime.db.execute('SELECT body FROM source').fetchone()[0]
    turns = runtime.db.execute('SELECT COUNT(*) FROM kit_turns').fetchone()[0]
    last = runtime.db.execute('SELECT id FROM turns ORDER BY revision DESC LIMIT 1').fetchone()
    sheet = state.get('player_sheet')
    pc = state.get('player_character') or {}
    pc_id = slug((sheet or {}).get('name') or pc.get('name'), 'pc')
    room_id = source['id']
    provenance = {'room_id': room_id, 'turn_id': last[0] if last else None}
    campaign = {
        'schema': CAMPAIGN_SCHEMA,
        'export': {'phase': EXPORT_PHASE, 'revision': revision,
                   'saved_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                   'runtime_only': ['kit.sqlite', 'dm-notes.json']},
        'journal_mode': 'campaign',
        'pcs': [pc_id],
        'pc': {'id': pc_id, **{k: pc[k] for k in ('name', 'ancestry', 'class', 'level') if k in pc}},
        'sheet_source': {'kind': 'json' if sheet else 'other', 'named_by_player': None,
                         'imported_at': None, 'at': None},
        'location': {'room_id': room_id, 'area': view['area'], **provenance},
        'rooms': [{'room_id': room_id, 'status': 'current', **provenance}],
        'npcs_met': [{'name': a['name'], 'status': a['status'], **provenance} for a in view['actors']],
        'loot': [],
        'gold_gp': (sheet or {}).get('gold_gp'),
        'debts': [], 'threads': [], 'choices': [],
        'sessions': [{'revision': revision, 'turns': turns, **provenance}],
        'source_hashes': {room_id: hashlib.sha256(raw.encode('utf-8')).hexdigest()},
    }
    return campaign, sheet


def journal_md(campaign):
    pc, loc = campaign['pc'], campaign['location']
    who = pc.get('name') or pc['id']
    about = ', '.join(str(pc[k]) for k in ('ancestry', 'class') if pc.get(k))
    if pc.get('level'):
        about += f', level {pc["level"]}'
    people = [f'- {n["name"]} ({n["status"]}), {n["room_id"]}' for n in campaign['npcs_met']]
    session = campaign['sessions'][-1]
    gold = campaign.get('gold_gp')
    state = {k: campaign[k] for k in ('schema', 'journal_mode', 'pcs', 'location', 'source_hashes')}
    state['revision'] = campaign['export']['revision']
    lines = [
        f'# Journal: {who}', '',
        f'- Character: {who}' + (f' ({about})' if about else ''),
        f'- Where: {loc["area"]} ({loc["room_id"]})',
        f'- Saved: {campaign["export"]["saved_at"]} (revision {campaign["export"]["revision"]})',
        '- This journal is rendered from campaign.json. Edit campaign.json or your sheet; prose here is not read back.',
        '', '## Threads', '', '- None recorded yet.',
        '', '## People met', '', *(people or ['- No one yet.']),
        '', '## Loot and coin', '', f'- Gold: {gold} gp (from your sheet)' if gold is not None else '- Gold: not on the sheet.',
        '', '## Debts', '', '- None recorded yet.',
        '', '## Session log', '',
        f'- Revision {session["revision"]}: {session["turns"]} turns played; now in {loc["area"]}.',
        '', '```kit-state', json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), '```', '']
    return '\n'.join(lines)


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


def files_for(campaign, sheet):
    out = {'campaign.json': json.dumps(campaign, indent=2, ensure_ascii=False) + '\n',
           'journal.md': journal_md(campaign)}
    if sheet:
        base = f'characters/{campaign["pcs"][0]}/'
        out[base + 'sheet.json'] = json.dumps(sheet, indent=2, ensure_ascii=False) + '\n'
        out[base + 'sheet.md'] = sheet_md(sheet)
    return out


def save(db, out=None, player=None, campaign=None):
    """Write saves/<player>/<campaign>/ next to db and a ZIP of it. Never copies kit.sqlite."""
    runtime = _open(db)
    try:
        record, sheet = collect(runtime)
    except sqlite3.Error as exc:
        raise SaveError(f'Could not read {db}: {exc}') from exc
    finally:
        runtime.close()
    player_id = slug(player, 'player')
    campaign_id = slug(campaign, _default_campaign(record['location']['room_id']))
    folder = Path(db).resolve().parent / 'saves' / player_id / campaign_id
    files = files_for(record, sheet)
    for name, text in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    archive = Path(out).resolve() if out else folder / f'kit-save-{campaign_id}-{record["pcs"][0]}.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, ZIP_STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    return {
        'stage': 'saved', 'zip': str(archive), 'folder': str(folder), 'files': sorted(files),
        'revision': record['export']['revision'], 'location': record['location']['area'],
        'next_step': ('Offer the player this ZIP as a download, and say in one line that it is their save '
                      '(campaign, journal, sheet). Never offer kit.sqlite: it is runtime-only and holds '
                      'hidden room state. Save at every room exit, when the player says save, and on stop.'),
    }
