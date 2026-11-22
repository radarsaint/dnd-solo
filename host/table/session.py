"""One campaign on disk, and the play loop the chat host is required to run.

State lives in kit.sqlite. This process may die; the next one reads status
and continues. The browser receives spoken text, the player view, and the
transcript. It does not receive packets.
"""
import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

from runtime import kit_lifecycle

from host.table.engine import Engine, EngineError, tighten
from host.table.model import ModelClient, ModelError
from host.table.public import adventure_public, modules_public, project

SAFE_NOTE = "That didn't commit. The game was not changed."
NO_VOICE = (
    "Kit's voice model is not connected. Nothing was invented, and this line "
    "was not recorded as play."
)
OPENING_ENGINE = (
    "That opening is the book's own read-aloud, committed by the rules engine. "
    "It is not a model performance. Later turns still need a voice model."
)


def _now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _read_json(path, default):
    path = Path(path)
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tighten(path)


class Table:
    def __init__(self, root, home):
        self.root = Path(root).resolve()
        self.home = Path(home).resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.engine = Engine(self.root)
        self._config = _read_json(self.home / 'host.json', {'active': 'default'})
        if not self._config.get('active'):
            self._config['active'] = 'default'

    # ---------------------------------------------------------------- files

    def campaign_dir(self):
        path = self.home / 'campaigns' / self._config['active']
        path.mkdir(parents=True, exist_ok=True)
        return path

    def db_path(self):
        return self.campaign_dir() / 'kit.sqlite'

    def _sheet_path(self):
        return self.campaign_dir() / 'sheet.json'

    def _transcript_path(self):
        return self.campaign_dir() / 'transcript.jsonl'

    def _cache_path(self):
        return self.campaign_dir() / 'manifest-cache.json'

    def _pending_path(self):
        return self.campaign_dir() / 'pending-packet.json'

    def _key_path(self):
        return self.home / 'model.key'

    def model(self):
        model = (self._config.get('model') or {})
        key = ''
        if self._key_path().is_file():
            key = self._key_path().read_text(encoding='utf-8').strip()
        return ModelClient(model.get('base_url') or '', model.get('name') or '', key)

    def configure_model(self, base_url, name, api_key=None):
        self._config['model'] = {
            'base_url': (base_url or '').strip(),
            'name': (name or '').strip(),
        }
        _write_json(self.home / 'host.json', self._config)
        if api_key is not None:
            text = api_key.strip()
            if text:
                self._key_path().write_text(text + '\n', encoding='utf-8')
                tighten(self._key_path())
            elif self._key_path().is_file():
                self._key_path().unlink()
        return self.model_status()

    def model_status(self):
        client = self.model()
        return {
            'configured': client.configured,
            'base_url': client.base_url,
            'name': client.model,
            'key': 'set' if client.api_key else 'absent',
            'warning': client.warn(),
            'satisfactory_local': False,
        }

    def _log(self, line):
        path = self.home / 'host.log'
        with path.open('a', encoding='utf-8') as handle:
            handle.write(_now() + ' ' + line + '\n')
        tighten(path)

    def _remember(self, role, text):
        if not text:
            return
        path = self._transcript_path()
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'at': _now(), 'role': role, 'text': text}, ensure_ascii=False) + '\n')
        tighten(path)

    def transcript(self):
        path = self._transcript_path()
        if not path.is_file():
            return []
        rows = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get('role') in ('player', 'kit', 'note') and row.get('text'):
                rows.append({'role': row['role'], 'text': row['text'], 'at': row.get('at')})
        return rows[-200:]

    # ---------------------------------------------------------------- engine reads

    def _status(self):
        # status is read-only and does not create kit.sqlite. An imported adventure
        # lives beside the save before any room is mounted, so a missing file is
        # not the same as "no adventure".
        return self.engine.status(self.db_path())

    def _view(self):
        db = self.db_path()
        if not db.is_file() or db.stat().st_size == 0:
            return None
        try:
            return self.engine.view(db)
        except EngineError:
            return None

    def _store_packet(self, packet):
        if isinstance(packet, dict) and packet.get('turn_id'):
            _write_json(self._pending_path(), packet)
            self._hydrate(packet)

    def _cached_packet(self, turn_id):
        packet = _read_json(self._pending_path(), None)
        if isinstance(packet, dict) and packet.get('turn_id') == turn_id:
            return self._hydrate(packet)
        db = self.db_path()
        recovered = self.engine.rehydrate(db, turn_id)
        packet = recovered.get('packet') if isinstance(recovered, dict) else None
        if not isinstance(packet, dict):
            packet = recovered
        self._store_packet(packet)
        return packet

    def _hydrate(self, packet):
        """A later turn sends manifest hashes only. A stateless model needs the bodies."""
        cache = _read_json(self._cache_path(), {})
        if not isinstance(cache, dict):
            cache = {}
        changed = False
        for key in ('session_manifest', 'room_manifest'):
            block = packet.get(key)
            if not isinstance(block, dict) or not block.get('hash'):
                continue
            if isinstance(block.get('body'), dict):
                cache[key] = {'hash': block['hash'], 'body': block['body']}
                changed = True
            elif block.get('cached') and cache.get(key, {}).get('hash') == block['hash']:
                packet = dict(packet)
                packet[key] = {'hash': block['hash'], 'body': cache[key]['body']}
        if changed:
            _write_json(self._cache_path(), cache)
        return packet

    def snapshot(self):
        status = self._status()
        lobby = None
        if status.get('state') == 'unmounted':
            try:
                lobby = self.engine.lobby(self.db_path())
            except EngineError as exc:
                self._log('lobby failed: ' + str(exc)[:200])
        view = self._view()
        adventure = adventure_public(status.get('adventure'))
        sheet = _read_json(self._sheet_path(), None)
        character = None
        if isinstance(sheet, dict) and sheet.get('name'):
            character = {
                'name': sheet.get('name'),
                'ancestry': sheet.get('ancestry'),
                'class': sheet.get('class'),
                'level': sheet.get('level'),
            }
        return {
            'state': status.get('state') or 'unmounted',
            'pending': status.get('pending_kind'),
            'committed_turns': status.get('committed_turns') or 0,
            'adventure': adventure,
            'modules': modules_public(lobby),
            'character': character,
            'view': project(view) if isinstance(view, dict) else None,
            'model': self.model_status(),
            'transcript': self.transcript(),
            'has_sheet': self._sheet_path().is_file(),
            'can_begin': bool(self._sheet_path().is_file() and (
                (adventure and adventure.get('readiness') not in (None, 'none')) or modules_public(lobby)
            )),
        }

    # ---------------------------------------------------------------- mutations

    def store_sheet(self, sheet):
        if not isinstance(sheet, dict):
            raise ValueError('a character sheet is a JSON object')
        if sheet.get('schema') not in (None, 'character_sheet_v1'):
            raise ValueError('the sheet schema must be character_sheet_v1')
        if not str(sheet.get('name') or '').strip():
            raise ValueError('the sheet needs a name')
        body = dict(sheet)
        body['schema'] = 'character_sheet_v1'
        _write_json(self._sheet_path(), body)
        return {'stored': True, 'name': body['name']}

    def import_text(self, text, title=None):
        text = (text or '').strip()
        if len(text) < 20:
            raise ValueError('paste the adventure text, or choose a text file')
        db = self.db_path()
        db.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = self.engine.ingest_text(db, text, title=title)
        except EngineError as exc:
            self._log('ingest rejected')
            problems = (exc.payload or {}).get('problems')
            note = problems[0] if isinstance(problems, list) and problems else SAFE_NOTE
            return {'ok': False, 'note': str(note)}
        tighten(db)
        public = adventure_public(result) or {}
        self._remember('note', 'Adventure imported: ' + str(public.get('title') or 'untitled'))
        return {'ok': True, 'adventure': public, 'state': self.snapshot()}

    def import_pdf(self, path):
        db = self.db_path()
        db.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = self.engine.ingest_pdf(db, path)
        except EngineError:
            self._log('pdf ingest rejected')
            return {'ok': False, 'note': 'That PDF could not be read. Paste the text instead.'}
        tighten(db)
        return {'ok': True, 'adventure': adventure_public(result), 'state': self.snapshot()}

    def archive(self):
        current = self.campaign_dir()
        if not any(current.iterdir()):
            return {'ok': True, 'archived': False}
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        dest = self.home / 'archives' / (self._config['active'] + '-' + stamp)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(dest))
        return {'ok': True, 'archived': True}

    def begin(self, table='solo', module_id=None):
        if table not in ('solo', 'shared'):
            return {'ok': False, 'note': 'The table is solo or shared.'}
        sheet = self._sheet_path()
        if not sheet.is_file():
            return {'ok': False, 'note': "Give me a character sheet first. I won't invent one."}
        room = self._room_to_open(module_id)
        if room is None:
            return {'ok': False, 'note': 'Hand me the adventure. Nothing here is a module I can run.'}
        db = self.db_path()
        try:
            started = self.engine.begin(db, room, sheet, table=table)
        except EngineError as exc:
            self._log('begin rejected: ' + str(exc)[:180])
            return {'ok': False, 'note': (exc.payload or {}).get('table_line') or SAFE_NOTE}
        tighten(db)
        packet = started.get('prepared') if isinstance(started, dict) else None
        if isinstance(packet, dict):
            self._store_packet(packet)
        if started.get('stage') != 'started':
            line = started.get('table_line') or 'The game did not open.'
            return {'ok': False, 'note': line, 'state': self.snapshot()}
        client = self.model()
        if client.configured and isinstance(packet, dict):
            spoken = self._perform(packet)
            if spoken:
                self._remember('kit', spoken)
                return {'ok': True, 'spoken': spoken, 'note': None, 'state': self.snapshot()}
            return {
                'ok': False,
                'spoken': None,
                'note': SAFE_NOTE + ' The opening is still waiting. You can retry, or say "begin" to commit the book\'s own read-aloud.',
                'state': self.snapshot(),
            }
        # No voice model: commit the engine's own opening read-aloud so the
        # book is actually open, and say plainly that this is not Kit's performance.
        try:
            opened = self.engine.prepare(db, action='Begin')
        except EngineError:
            self._log('engine opening did not commit')
            return {'ok': False, 'note': NO_VOICE, 'state': self.snapshot()}
        spoken = opened.get('spoken') if isinstance(opened, dict) else None
        if spoken:
            self._remember('kit', spoken)
            self._remember('note', OPENING_ENGINE)
        return {'ok': bool(spoken), 'spoken': spoken, 'note': OPENING_ENGINE, 'state': self.snapshot()}

    def _room_to_open(self, module_id):
        status = self._status()
        adventure = status.get('adventure') if isinstance(status, dict) else None
        if isinstance(adventure, dict) and adventure.get('start_room'):
            return adventure['start_room']
        try:
            lobby = self.engine.lobby(self.db_path())
        except EngineError:
            return None
        rows = [row for row in (lobby.get('modules_available') or []) if isinstance(row, dict)]
        if module_id:
            for row in rows:
                if row.get('room_id') == module_id and row.get('path'):
                    return row['path']
            return None
        if len(rows) == 1 and rows[0].get('path'):
            return rows[0]['path']
        return None

    def say(self, text, table_talk=False):
        text = (text or '').strip()
        if not text:
            return {'ok': False, 'note': 'Say something first.'}
        if len(text) > 8000:
            return {'ok': False, 'note': 'That line is too long to take as one action.'}
        status = self._status()
        state = status.get('state')
        if state == 'unmounted':
            return {'ok': False, 'note': 'No game is open. Import an adventure, give me a sheet, then begin.'}
        if state == 'mounted':
            return {'ok': False, 'note': 'The room is mounted, but the opening has not been played. Begin first.'}
        db = self.db_path()

        # A go-ahead while the opening waits, and no voice model: the engine
        # commits the book's own read-aloud. It does not invent a performance.
        if state == 'ready' and kit_lifecycle.is_confirmation(text) and not self.model().configured:
            return self._engine_opening(db, text)

        pending_spoken = None
        if state in ('ready', 'awaiting_completion'):
            finished = self._finish_pending(status)
            if not finished.get('ok'):
                return {**finished, 'state': self.snapshot()}
            pending_spoken = finished.get('spoken')
            if kit_lifecycle.is_confirmation(text):
                return {'ok': True, 'spoken': pending_spoken, 'state': self.snapshot()}

        self._remember('player', text)
        try:
            packet = self.engine.prepare(db, action=text, table_talk=table_talk)
        except EngineError:
            self._log('prepare rejected')
            return {'ok': False, 'note': SAFE_NOTE, 'state': self.snapshot()}
        if not isinstance(packet, dict):
            return {'ok': False, 'note': SAFE_NOTE, 'state': self.snapshot()}
        if packet.get('spoken') and packet.get('committed'):
            self._remember('kit', packet['spoken'])
            return {'ok': True, 'spoken': packet['spoken'], 'state': self.snapshot()}
        if packet.get('stage') == 'pending_ruling':
            note = packet.get('player_message') or 'That needs a clearer action. Nothing was committed.'
            self._remember('kit', note)
            return {'ok': True, 'spoken': note, 'state': self.snapshot()}
        if packet.get('stage') == 'turn_pending':
            return {'ok': False, 'note': 'A turn is still waiting. Nothing new was recorded.', 'state': self.snapshot()}
        if packet.get('turn_id') and 'input' in packet:
            spoken = self._perform(packet)
            if not spoken:
                return {'ok': False, 'note': SAFE_NOTE, 'state': self.snapshot()}
            self._remember('kit', spoken)
            return {'ok': True, 'spoken': spoken, 'also': pending_spoken, 'state': self.snapshot()}
        return {'ok': False, 'note': SAFE_NOTE, 'state': self.snapshot()}

    def _engine_opening(self, db, text):
        try:
            opened = self.engine.prepare(db, action=text)
        except EngineError:
            self._log('opening confirmation rejected')
            return {'ok': False, 'note': SAFE_NOTE, 'state': self.snapshot()}
        spoken = opened.get('spoken') if isinstance(opened, dict) else None
        if not spoken:
            return {'ok': False, 'note': SAFE_NOTE, 'state': self.snapshot()}
        self._remember('player', text)
        self._remember('kit', spoken)
        note = None if self.model().configured else OPENING_ENGINE
        if note:
            self._remember('note', note)
        return {'ok': True, 'spoken': spoken, 'note': note, 'state': self.snapshot()}

    def _finish_pending(self, status):
        turn_id = status.get('pending_turn_id')
        if not turn_id:
            return {'ok': True}
        if status.get('state') == 'ready' and not self.model().configured:
            return {'ok': False, 'note': NO_VOICE}
        if not self.model().configured:
            return {'ok': False, 'note': NO_VOICE}
        try:
            packet = self._cached_packet(turn_id)
        except EngineError:
            self._log('rehydrate failed')
            return {'ok': False, 'note': SAFE_NOTE}
        spoken = self._perform(packet)
        if not spoken:
            return {'ok': False, 'note': SAFE_NOTE}
        self._remember('kit', spoken)
        return {'ok': True, 'spoken': spoken}

    def _perform(self, packet):
        packet = self._hydrate(packet)
        self._store_packet(packet)
        client = self.model()
        if not client.configured:
            return None
        correction = None
        last_error = None
        for _attempt in range(3):
            try:
                obj = client.complete(packet, correction=correction)
            except ModelError as exc:
                self._log('model error: ' + str(exc)[:160])
                return None
            self._stamp_manifest(packet, obj)
            try:
                done = self.engine.complete(self.db_path(), packet['turn_id'], obj)
            except EngineError as exc:
                last_error = exc
                correction = (exc.payload or {}).get('retry_instruction') or str(exc)[:500]
                self._log('complete rejected, retrying')
                continue
            spoken = done.get('spoken') if isinstance(done, dict) else None
            if spoken:
                pending = self._pending_path()
                if pending.is_file():
                    pending.unlink()
                return spoken
            return None
        if last_error is not None:
            self._log('complete failed after retries')
        return None

    @staticmethod
    def _stamp_manifest(packet, obj):
        session = (packet.get('session_manifest') or {}).get('hash')
        room = (packet.get('room_manifest') or {}).get('hash')
        if session and room and isinstance(obj, dict):
            obj['manifest'] = {'session': session, 'room': room}

    def abandon(self):
        status = self._status()
        turn_id = status.get('pending_turn_id')
        if not turn_id:
            return {'ok': True, 'note': 'Nothing is waiting.', 'state': self.snapshot()}
        try:
            self.engine.abandon(self.db_path(), turn_id)
        except EngineError:
            self._log('abandon failed')
            return {'ok': False, 'note': SAFE_NOTE, 'state': self.snapshot()}
        pending = self._pending_path()
        if pending.is_file():
            pending.unlink()
        self._remember('note', 'The unfinished turn was dropped. The last committed moment still stands.')
        return {'ok': True, 'state': self.snapshot()}

    def save(self):
        db = self.db_path()
        if not db.is_file():
            return {'ok': False, 'note': 'There is no game to save.'}
        try:
            result = self.engine.save(db)
        except EngineError:
            self._log('save rejected')
            return {'ok': False, 'note': 'The save did not write. The game itself was not changed.'}
        archive = Path(result.get('zip') or '')
        if not archive.is_file() or archive.suffix != '.zip' or archive.stat().st_size == 0:
            return {'ok': False, 'note': 'The save did not write.'}
        # The zip must sit under this campaign. Refuse anything else.
        try:
            archive.resolve().relative_to(self.campaign_dir().resolve())
        except ValueError:
            return {'ok': False, 'note': 'The save landed outside the campaign folder and was not offered.'}
        token = secrets.token_urlsafe(24)
        _write_json(self.home / 'last-save.json', {'token': token, 'zip': str(archive.resolve())})
        ask = result.get('ask_player')
        return {
            'ok': True,
            'download': token,
            'location': result.get('location'),
            'ask_player': ask,
            'note': 'This ZIP is your save: the campaign, the journal, and the sheet. The hidden game file stays on the tablet.',
        }

    def save_file(self, token):
        record = _read_json(self.home / 'last-save.json', {})
        if not token or token != record.get('token'):
            return None
        path = Path(record.get('zip') or '')
        try:
            path.resolve().relative_to(self.home.resolve())
        except ValueError:
            return None
        if path.is_file() and path.suffix == '.zip':
            return path
        return None
