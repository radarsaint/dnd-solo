"""Loopback table host. Real kit_agent process, no paid API, no model required for the engine path.

The voice, when a test needs one, is a local HTTP stub that fills a decision the
engine already accepts in the watchroom tests. It is not a substitute DM.
"""
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from host.table.cli import probe, smoke  # noqa: E402
from host.table.model import parse_model_json  # noqa: E402
from host.table.server import TableServer  # noqa: E402
from host.table.session import Table  # noqa: E402
from test_kit_agent import RecordingModel  # noqa: E402
from test_kit_manifests import WAITING  # noqa: E402
from test_kit_watchroom_stalls import landing  # noqa: E402

SECRET = 'Keep strangers off the stair.'
HATCH = 'A secret hatch under the stove'
ROOM = ROOT / 'tests' / 'fixtures' / 'rooms' / 'watchroom.json'
SHEET = ROOT / 'tests' / 'fixtures' / 'characters' / 'example_pc.json'
FERRY = ROOT / 'tests' / 'fixtures' / 'adventures' / 'lantern_ferry.txt'


def post_json(url, payload, method='POST'):
    data = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode('utf-8'))


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.status, json.loads(response.read().decode('utf-8'))


def body_of(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode('utf-8')


class StubModel(BaseHTTPRequestHandler):
    """Returns a schema-shaped decision. mode is 'valid' or 'garbage'."""

    mode = 'valid'

    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or '0')
        raw = json.loads(self.rfile.read(length).decode('utf-8'))
        user = raw['messages'][-1]['content']
        if StubModel.mode == 'garbage':
            content = '{"nope": 1}'
        else:
            packet_text = user.split('PACKET\n', 1)[1].split('\n\nThe engine', 1)[0]
            packet = json.loads(packet_text)
            private = packet['input']['private']
            plan = RecordingModel().plan(private)
            plan.update({'move': 'world_description', 'table_presence': 'quiet', 'focus_actor': 'none'})
            plan['improv_read'].update(actor_ref='none', actor_basis='none')
            opening = private.get('action_kind') == 'opening' or private.get('player_action') in (None, '', 'opening')
            if opening:
                plan['public_brief'].update(scope='feature', reply_to='none')
                performance = landing()
            else:
                action = private.get('player_action') or ''
                plan['public_brief'].update(reply_to=action[:40], scope='feature')
                performance = WAITING
            content = json.dumps({'decision': plan, 'performance': performance})
        payload = json.dumps({'choices': [{'message': {'content': content}}]}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve_stub():
    StubModel.mode = 'valid'
    server = ThreadingHTTPServer(('127.0.0.1', 0), StubModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class HostCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.table = Table(ROOT, self.home)
        self.server = TableServer(('127.0.0.1', 0), self.table)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        host, port = self.server.server_address
        self.base = f'http://{host}:{port}'

    def test_health_and_shell_do_not_carry_hidden_facts(self):
        status, health = get_json(self.base + '/api/health')
        self.assertEqual(status, 200)
        self.assertTrue(health['ok'])
        page = body_of(self.base + '/')
        self.assertIn('>Kit<', page)
        self.assertNotIn(SECRET, page)
        self.assertNotIn('dm_only', page)
        css = body_of(self.base + '/app.css')
        self.assertNotIn(SECRET, css)

    def test_missing_save_stays_missing_and_chat_does_not_invent(self):
        status, state = get_json(self.base + '/api/state')
        self.assertEqual(state['state'], 'unmounted')
        self.assertFalse(self.table.db_path().exists())
        code, reply = post_json(self.base + '/api/message', {'text': 'I open the door.'})
        self.assertEqual(code, 422)
        self.assertFalse(reply['ok'])
        self.assertNotIn(SECRET, json.dumps(reply))
        self.assertFalse(self.table.db_path().exists())

    def test_opening_survives_a_new_process_and_hides_the_motive(self):
        self.table.engine.begin_regression(self.table.db_path(), ROOM, SHEET)
        status = self.table.engine.status(self.table.db_path())
        self.assertEqual(status['state'], 'ready')
        # A second host object is a restarted process: same files, new Python.
        restarted = Table(ROOT, self.home)
        self.assertEqual(restarted.snapshot()['state'], 'ready')
        code, reply = post_json(self.base + '/api/message', {'text': "Let's go"})
        self.assertEqual(code, 200, reply)
        self.assertTrue(reply['ok'])
        self.assertTrue(reply.get('spoken'))
        blob = json.dumps(reply)
        self.assertNotIn(SECRET, blob)
        self.assertNotIn('dm_only', blob)
        self.assertNotIn('personality_core', blob)
        self.assertEqual(reply['state']['state'], 'playing')
        again = Table(ROOT, self.home)
        self.assertEqual(again.snapshot()['state'], 'playing')
        self.assertTrue(any(row['role'] == 'kit' for row in again.transcript()))

    def test_voice_stub_commits_a_second_turn_and_a_bad_voice_does_not(self):
        self.table.engine.begin_regression(self.table.db_path(), ROOM, SHEET)
        post_json(self.base + '/api/message', {'text': "Let's go"})
        before = self.table.engine.status(self.table.db_path())['committed_turns']
        stub = serve_stub()
        self.addCleanup(stub.shutdown)
        port = stub.server_address[1]
        post_json(self.base + '/api/settings', {
            'base_url': f'http://127.0.0.1:{port}/v1',
            'name': 'stub',
            'api_key': 'test-key-should-not-echo',
        })
        code, settings = get_json(self.base + '/api/settings')
        self.assertEqual(code, 200)
        self.assertNotIn('test-key-should-not-echo', json.dumps(settings))
        self.assertEqual(settings['key'], 'set')
        code, reply = post_json(self.base + '/api/message', {
            'text': 'I wait on the landing and listen to the humming.',
        })
        self.assertEqual(code, 200, reply)
        self.assertTrue(reply['ok'], reply)
        self.assertNotIn(SECRET, json.dumps(reply))
        self.assertGreater(reply['state']['committed_turns'], before)
        StubModel.mode = 'garbage'
        stalled = self.table.engine.status(self.table.db_path())['committed_turns']
        code, reply = post_json(self.base + '/api/message', {'text': 'I look at the iron door.'})
        self.assertEqual(code, 422)
        self.assertFalse(reply['ok'])
        self.assertNotIn(SECRET, json.dumps(reply))
        self.assertNotIn('retry', json.dumps(reply).lower())
        self.assertEqual(self.table.engine.status(self.table.db_path())['committed_turns'], stalled)

    def test_adventure_import_save_and_abandon_keep_secrets_server_side(self):
        code, imported = post_json(self.base + '/api/import', {'text': FERRY.read_text(encoding='utf-8')})
        self.assertEqual(code, 200, imported)
        blob = json.dumps(imported)
        self.assertNotIn(HATCH, blob)
        self.assertNotIn('DC 12', blob)
        self.assertTrue((self.table.campaign_dir() / 'kit.sqlite.adventure' / 'source.txt').is_file())
        source = (self.table.campaign_dir() / 'kit.sqlite.adventure' / 'source.txt').read_text(encoding='utf-8')
        self.assertIn(HATCH, source)
        code, stored = post_json(self.base + '/api/sheet', {'sheet': json.loads(SHEET.read_text(encoding='utf-8'))})
        self.assertTrue(stored['ok'])
        self.assertTrue(stored['state']['can_begin'])
        code, begun = post_json(self.base + '/api/begin', {'table': 'solo'})
        self.assertEqual(code, 200, begun)
        self.assertTrue(begun.get('spoken'))
        self.assertNotIn(HATCH, json.dumps(begun))
        code, saved = post_json(self.base + '/api/save', {})
        self.assertTrue(saved['ok'], saved)
        archive = self.table.save_file(saved['download'])
        self.assertIsNotNone(archive)
        raw = archive.read_bytes()
        self.assertNotIn(HATCH.encode(), raw)
        self.assertNotIn(b'kit.sqlite', raw)
        # A fresh game with a waiting opening can drop that turn and come back.
        fresh_home = Path(self.tmp.name) / 'other'
        other = Table(ROOT, fresh_home)
        other.engine.begin_regression(other.db_path(), ROOM, SHEET)
        self.assertEqual(other.engine.status(other.db_path())['state'], 'ready')
        other.abandon()
        self.assertNotEqual(other.engine.status(other.db_path())['state'], 'ready')

    def test_probe_and_smoke(self):
        report = probe(ROOT)
        self.assertGreater(report['opening_packet_bytes'], 40000)
        self.assertGreater(report['second_packet_bytes'], 1000)
        self.assertLess(report['second_packet_bytes'], report['opening_packet_bytes'])
        self.assertFalse(report['local_satisfactory'])
        self.assertFalse(report['device_measured'])
        checked = smoke(ROOT)
        self.assertTrue(checked['ok'], checked)
        self.assertFalse(checked['device_installed'])

    def test_model_json_parser_strips_a_fence(self):
        parsed = parse_model_json('```json\n{"decision": {}, "performance": {}}\n```')
        self.assertIn('decision', parsed)

    def test_play_route_is_absent(self):
        request = urllib.request.Request(self.base + '/api/play', data=b'{}', method='POST')
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
