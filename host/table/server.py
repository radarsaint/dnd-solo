"""Loopback HTTP table. Bound to 127.0.0.1 unless a preview explicitly widens it."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from host.table.session import Table

STATIC = Path(__file__).resolve().parent / 'static'
FILES = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/index.html': ('index.html', 'text/html; charset=utf-8'),
    '/app.css': ('app.css', 'text/css; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/manifest.webmanifest': ('manifest.webmanifest', 'application/manifest+json'),
    '/sw.js': ('sw.js', 'text/javascript; charset=utf-8'),
    '/icon.svg': ('icon.svg', 'image/svg+xml'),
    '/icon-192.png': ('icon-192.png', 'image/png'),
    '/icon-512.png': ('icon-512.png', 'image/png'),
}
MAX_BODY = 1_500_000


class TableServer(ThreadingHTTPServer):
    def __init__(self, address, table):
        self.table = table
        self.lock = threading.Lock()
        super().__init__(address, Handler)
        self.daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        # Path only. Query strings can carry a save token.
        path = urlparse(self.path).path
        self.server.table._log(f'{self.command} {path}')

    def _allowed_host(self):
        if os.environ.get('KIT_TABLE_PREVIEW') == '1':
            return True
        host = (self.headers.get('Host') or '').split(':')[0].strip('[]')
        return host in ('127.0.0.1', 'localhost', '::1')

    def _read_json(self):
        length = int(self.headers.get('Content-Length') or '0')
        if length < 0 or length > MAX_BODY:
            raise ValueError('request is too large')
        raw = self.rfile.read(length) if length else b''
        if not raw:
            return {}
        value = json.loads(raw.decode('utf-8'))
        if not isinstance(value, dict):
            raise ValueError('JSON object required')
        return value

    def _send(self, code, body, content_type, extra=None):
        data = body if isinstance(body, bytes) else body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _json(self, code, payload):
        self._send(code, json.dumps(payload, ensure_ascii=False), 'application/json; charset=utf-8')

    def do_GET(self):
        if not self._allowed_host():
            self._json(403, {'ok': False, 'note': 'this table only answers on localhost'})
            return
        path = urlparse(self.path).path
        if path == '/api/health':
            self._json(200, {'ok': True, 'service': 'kit-table'})
            return
        if path == '/api/state':
            with self.server.lock:
                self._json(200, self.server.table.snapshot())
            return
        if path == '/api/settings':
            self._json(200, self.server.table.model_status())
            return
        if path == '/api/save/download':
            token = (parse_qs(urlparse(self.path).query).get('token') or [''])[0]
            with self.server.lock:
                archive = self.server.table.save_file(token)
            if archive is None:
                self._json(404, {'ok': False, 'note': 'that save link is not valid'})
                return
            data = archive.read_bytes()
            self._send(200, data, 'application/zip', {
                'Content-Disposition': 'attachment; filename="kit-save.zip"',
            })
            return
        spec = FILES.get(path)
        if spec is None:
            self._json(404, {'ok': False, 'note': 'not found'})
            return
        file_path = STATIC / spec[0]
        if not file_path.is_file():
            self._json(404, {'ok': False, 'note': 'not found'})
            return
        self._send(200, file_path.read_bytes(), spec[1])

    def do_POST(self):
        if not self._allowed_host():
            self._json(403, {'ok': False, 'note': 'this table only answers on localhost'})
            return
        path = urlparse(self.path).path
        try:
            if self.headers.get('Content-Type', '').startswith('application/pdf'):
                length = int(self.headers.get('Content-Length') or '0')
                if length <= 0 or length > MAX_BODY:
                    raise ValueError('PDF is empty or too large')
                folder = self.server.table.campaign_dir()
                target = folder / 'inbox.pdf'
                target.write_bytes(self.rfile.read(length))
                with self.server.lock:
                    result = self.server.table.import_pdf(target)
                self._json(200 if result.get('ok') else 422, result)
                return
            body = self._read_json()
        except (ValueError, json.JSONDecodeError):
            self._json(400, {'ok': False, 'note': 'that request was not readable'})
            return
        try:
            with self.server.lock:
                result = self._post(path, body)
        except ValueError as exc:
            self._json(422, {'ok': False, 'note': str(exc)})
            return
        if result is None:
            self._json(404, {'ok': False, 'note': 'not found'})
            return
        code = 200 if result.get('ok', True) else 422
        self._json(code, result)

    def _post(self, path, body):
        table = self.server.table
        if path == '/api/message':
            return table.say(body.get('text') or '', table_talk=bool(body.get('table_talk')))
        if path == '/api/begin':
            return table.begin(table=body.get('table') or 'solo', module_id=body.get('module_id'))
        if path == '/api/import':
            return table.import_text(body.get('text') or '', title=body.get('title'))
        if path == '/api/sheet':
            sheet = body.get('sheet') if isinstance(body.get('sheet'), dict) else body
            stored = table.store_sheet(sheet)
            return {'ok': True, **stored, 'state': table.snapshot()}
        if path == '/api/settings':
            status = table.configure_model(body.get('base_url') or '', body.get('name') or '', body.get('api_key'))
            return {'ok': True, 'model': status}
        if path == '/api/save':
            return table.save()
        if path == '/api/abandon':
            return table.abandon()
        if path == '/api/campaign/new':
            archived = table.archive()
            return {'ok': True, **archived, 'state': table.snapshot()}
        return None


def serve(root, home, host, port):
    table = Table(root, home)
    server = TableServer((host, port), table)
    print(f'Kit table on http://{host}:{port}/', flush=True)
    server.serve_forever()
