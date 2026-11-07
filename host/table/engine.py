"""Drive the public kit_agent CLI. The runtime stays the authority.

This module does not import the rules engine. It runs
``python3 -m runtime.kit_agent`` the same way a chat host is required to,
and it never invokes the paid ``play`` command.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


class EngineError(Exception):
    def __init__(self, code, payload, raw, stdout_payload=None):
        self.code = code
        self.payload = payload if isinstance(payload, dict) else None
        self.raw = raw or ''
        self.stdout_payload = stdout_payload
        message = ''
        if self.payload:
            message = str(self.payload.get('message') or self.payload.get('stage') or '')
        super().__init__(message or f'kit_agent exited {code}')


def _parse_json(text):
    text = (text or '').strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def tighten(path):
    """Best-effort private mode. A platform that ignores chmod still works."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


class Engine:
    def __init__(self, root, timeout=180):
        self.root = Path(root).resolve()
        self.timeout = timeout

    def run(self, args, timeout=None):
        env = os.environ.copy()
        env['PYTHONPATH'] = str(self.root)
        env['PYTHONIOENCODING'] = 'utf-8'
        # The legacy play command is the paid API. This host never calls it,
        # and it does not inherit a key that would make an accidental call work.
        env.pop('OPENAI_API_KEY', None)
        proc = subprocess.run(
            [sys.executable, '-m', 'runtime.kit_agent', *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout or self.timeout,
            env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def json_call(self, args, timeout=None):
        code, out, err = self.run(args, timeout=timeout)
        try:
            parsed = _parse_json(out)
        except json.JSONDecodeError as exc:
            raise EngineError(code, None, f'engine stdout was not JSON: {exc}', None) from exc
        try:
            error = _parse_json(err)
        except json.JSONDecodeError:
            error = None
        if code != 0:
            raise EngineError(code, error, err, parsed)
        if not isinstance(parsed, dict):
            raise EngineError(code, None, err or 'engine returned no JSON object', parsed)
        return parsed

    def status(self, db):
        return self.json_call(['status', '--db', str(db)])

    def view(self, db):
        return self.json_call(['view', '--db', str(db)])

    def greeting(self, db):
        return self.json_call(['start', '--db', str(db)])

    def lobby(self, db):
        return self.json_call(['start', '--db', str(db), '--intent', 'play'])

    def begin(self, db, room, sheet, table='solo'):
        return self.json_call([
            'start', '--db', str(db), '--room', str(room), '--sheet', str(sheet),
            '--intent', 'play', '--table', table,
        ])

    def begin_regression(self, db, room, sheet):
        """Engineering probe only. Player-facing begin() never passes --regression."""
        return self.json_call([
            'start', '--db', str(db), '--room', str(room), '--sheet', str(sheet),
            '--regression', '--intent', 'play', '--table', 'solo',
        ])

    def prepare(self, db, action=None, opening=False, table_talk=False, turn_id=None):
        args = ['prepare', '--one-pass', '--db', str(db)]
        if opening:
            args.append('--opening')
        else:
            if action is None:
                raise EngineError(2, {'message': 'prepare needs the player\'s words'}, '', None)
            path = Path(db).resolve().parent / 'action.txt'
            path.write_text(action, encoding='utf-8')
            tighten(path)
            args += ['--action-file', str(path)]
        if table_talk:
            args.append('--table-talk')
        if turn_id:
            args += ['--turn-id', turn_id]
        return self.json_call(args)

    def complete(self, db, turn_id, payload):
        path = Path(db).resolve().parent / 'o.json'
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        tighten(path)
        return self.json_call([
            'complete', '--db', str(db), '--turn-id', str(turn_id), '--input-file', str(path),
        ])

    def rehydrate(self, db, turn_id):
        return self.json_call(['rehydrate', '--db', str(db), '--turn-id', str(turn_id)])

    def abandon(self, db, turn_id):
        return self.json_call(['abandon', '--db', str(db), '--turn-id', str(turn_id)])

    def ingest_text(self, db, text, title=None):
        path = Path(db).resolve().parent / 'adventure.txt'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        tighten(path)
        args = ['ingest', '--db', str(db), '--text-file', str(path)]
        if title:
            args += ['--title', title]
        return self.json_call(args, timeout=180)

    def ingest_pdf(self, db, pdf_path):
        return self.json_call(['ingest', '--db', str(db), str(pdf_path)], timeout=180)

    def save(self, db, player='player'):
        return self.json_call(['save', '--db', str(db), '--player', player])

    def persona(self):
        code, out, err = self.run(['persona'], timeout=60)
        if code != 0:
            raise EngineError(code, None, err, None)
        return out
