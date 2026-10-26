"""Latency priority 4 (docs/latency/experiment-protocol.md): per-turn telemetry, the compact
opening packet, and a stable packet prefix.

Corpus: tests/fixtures/adventures/lantern_ferry.txt (ORIGINAL synthetic adventure) and the
06c regression room fixture. No published text."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_compact, kit_manifest, kit_telemetry  # noqa: E402
from runtime.kit_agent import (KitChatBridge, RoomAdjudicator, fetch_part, personality_core_text,  # noqa: E402
                               start_session)
from runtime.state_context import Runtime  # noqa: E402

CORPUS = ROOT / 'tests/fixtures/adventures/lantern_ferry.txt'
ROOM_06C = ROOT / 'tests/fixtures/level_01_area_06c.json'
NIK = ROOT / 'tests/fixtures/characters/nik.json'
ADDED = {'schema', 'schema_notation', 'retrieval', 'packet_mode'}


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


class Base(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = self.folder / 'kit.sqlite'

    def lantern(self, location='1'):
        kit_adventure.import_adventure(self.db, text=CORPUS.read_text(encoding='utf-8'))
        kit_adventure.compile_location(self.db, location, neighbours=False)
        return kit_adventure.room_file(self.db, location)

    def opening(self, room):
        full = start_session(self.db, NIK, room=room)['prepared']
        return full, kit_compact.compact(full, self.db)


class CompactFidelity(Base):
    """The compact packet carries every fact the active scene needs, byte for byte."""

    def check(self, full, compact_packet, room_path):
        compact, moved = compact_packet
        self.assertEqual(compact['packet_mode'], 'compact')
        # Lossless contract: the schema shorthand expands back to the full schema.
        self.assertEqual(kit_manifest.expand_schema(compact['schema']), full['schema'])
        for key in ('instructions', 'performance_limits', 'host_retry', 'first_try', 'turn_id', 'stage'):
            self.assertEqual(compact[key], full[key], key)
        cp, fp = compact['input']['private'], full['input']['private']
        for key in ('reveal', 'story_brief', 'kit_state', 'dialogue_history', 'table_read',
                    'accepted_public_event', 'player_action', 'discernment_candidates'):
            self.assertEqual(cp.get(key), fp.get(key), key)
        cdm, fdm = cp['dm_context'], fp['dm_context']
        for key in ('scene', 'player_perceivable', 'constraints', 'recent_rhythm', 'source_ref', 'source_id'):
            self.assertEqual(cdm.get(key), fdm.get(key), key)
        self.assertEqual(cdm['dm_only'].get('room_rules'), fdm['dm_only'].get('room_rules'))
        self.assertEqual(cdm['dm_only'].get('geometry'), fdm['dm_only'].get('geometry'))
        # Every string of the active area that the full packet sends, the compact one sends too.
        area = fdm['scene']['current_area']
        source = json.loads(Path(room_path).read_text(encoding='utf-8'))
        here = [source['areas'][area]] + [
            entry for group in ('facts', 'actors') for entry in (source.get(group) or {}).values()
            if isinstance(entry, dict) and entry.get('area') in (None, area)]
        sent_full, sent_compact = set(strings(full)), json.dumps(compact, ensure_ascii=False)
        for text in strings(here):
            if text in sent_full:
                self.assertIn(json.dumps(text, ensure_ascii=False)[1:-1], sent_compact, text)
        # Hidden-state guards: held facts stay held, withheld text stays out, in both.
        self.assertEqual(cp['reveal'].get('hold'), fp['reveal'].get('hold'))
        # Retrieval: what moved comes back on demand, exactly.
        self.assertEqual(moved.get('personality_core'), fp['personality_core'])
        self.assertNotIn('personality_core', cp)
        self.assertIn('persona', compact['retrieval'])
        self.assertLess(len(json.dumps(compact)), len(json.dumps(full)))

    def test_lantern_opening(self):
        room = self.lantern('1')
        full, compact = self.opening(room)
        self.check(full, compact, room)
        texts = json.dumps(compact[0], ensure_ascii=False)
        for fact in ('Oswin Tarr, a nervous ferryman, waits under the eaves.',
                     'He will not cross tonight unless paid three silver.',
                     'The bell rope is frayed; a DC 12 Strength (Athletics) check pulls it loose.'):
            self.assertIn(fact, texts)

    def test_lantern_hidden_creature_room(self):
        room = self.lantern('3')
        full, compact = self.opening(room)
        self.check(full, compact, room)
        self.assertEqual(json.dumps(compact[0]['input']['public']).count('wight'),
                         json.dumps(full['input']['public']).count('wight'))

    def test_06c_regression_room(self):
        full, compact = self.opening(str(ROOM_06C))
        self.check(full, compact, ROOM_06C)
        # Leak guards ride in the public side and private brief unchanged.
        self.assertEqual(compact[0]['input']['public'].get('speakers'), full['input']['public'].get('speakers'))

    def test_far_area_facts_move_behind_fetch_and_come_back(self):
        packet = {'instructions': 'i', 'schema': {'type': 'string'}, 'turn_id': 't', 'input': {
            'private': {'personality_core': 'core', 'dm_context': {
                'scene': {'current_area': 'a'}, 'missing_production_layers': ['x'],
                'dm_only': {'unrevealed_facts': {'f1': {'area': 'a', 'text': 'here'},
                                                 'f2': {'area': 'b', 'text': 'far'},
                                                 'f3': {'text': 'room-wide'}},
                            'actors': {'n1': {'area': 'b'}, 'n2': {'area': 'a'}}}}},
            'public': {}}}
        compact, moved = kit_compact.compact(packet, 'db')
        dm_only = compact['input']['private']['dm_context']['dm_only']
        self.assertEqual(set(dm_only['unrevealed_facts']), {'f1', 'f3'})
        self.assertEqual(set(dm_only['actors']), {'n2'})
        self.assertEqual(set(moved['dm_only.unrevealed_facts']), {'f2'})
        self.assertEqual(moved['missing_production_layers'], ['x'])
        self.assertIn('fetch --db db --part area', compact['retrieval']['other_area'])

    def test_fetch_returns_what_compact_left_out(self):
        room = self.lantern('1')
        start_session(self.db, NIK, room=room)
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        self.assertEqual(fetch_part(runtime, 'persona')['personality_core'], personality_core_text())
        self.assertIn('properties', fetch_part(runtime, 'schema')['schema'])
        self.assertTrue(fetch_part(runtime, 'production_layers')['missing_production_layers'])
        self.assertEqual(fetch_part(runtime, 'area', 'to_2')['area'], 'to_2')

    def test_full_stays_the_default(self):
        room = self.lantern('1')
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        self.assertFalse(KitChatBridge(runtime, RoomAdjudicator()).compact)
        full = start_session(self.db, NIK, room=room, runtime=runtime)['prepared']
        self.assertNotIn('packet_mode', full)
        self.assertIn('personality_core', full['input']['private'])


class StablePrefix(Base):
    """No timestamps or per-turn ids at the start of a packet: the contract leads."""

    def test_one_pass_packet_starts_with_the_contract(self):
        full, (compact, _) = self.opening(self.lantern('1'))
        for packet in (full, compact):
            head = list(packet)[:4]
            self.assertEqual(head[:2], ['performance_variant', 'instructions'], head)
            self.assertNotIn('turn_id', head)
            self.assertNotIn('first_try', head)

    def test_prefix_is_identical_across_two_sessions(self):
        first = self.opening(self.lantern('1'))[0]
        self.db = self.folder / 'two.sqlite'
        second = self.opening(self.lantern('1'))[0]
        stable = lambda p: json.dumps({k: p[k] for k in list(p)[:5]}, ensure_ascii=False)  # noqa: E731
        self.assertEqual(stable(first), stable(second))

    def test_start_result_leads_with_the_packet(self):
        result = start_session(self.db, NIK, room=self.lantern('1'))
        self.assertEqual(list(result)[0], 'prepared')


class Telemetry(Base):
    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, '-W', 'ignore', '-m', 'runtime.kit_agent', *args], cwd=ROOT,
                              capture_output=True, text=True, env={**os.environ, **(env or {})})

    def rows(self):
        path = kit_telemetry.log_path(self.db)
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def test_start_and_prepare_write_records_and_nulls_are_never_guessed(self):
        room = self.lantern('1')
        out = self.run_cli('start', '--compact', '--db', str(self.db), '--room', str(room), '--sheet', str(NIK),
                           '--host', 'chatgpt')
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = [r for r in self.rows() if r['command'] == 'start']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        data = out.stdout.rstrip('\n').encode('utf-8') + b'\n'
        self.assertEqual(row['packet_bytes'], len(data))
        self.assertEqual(row['packet_sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(row['turn_id'], json.loads(out.stdout)['prepared']['turn_id'])
        self.assertEqual(row['host'], 'chatgpt')
        self.assertEqual(row['packet_mode'], 'compact')
        self.assertEqual(row['tool_calls'], 1)
        self.assertGreater(row['engine_ms'], 0)
        self.assertGreater(row['serialization_ms'], 0)
        for key in kit_telemetry.UNKNOWN:
            self.assertIsNone(row[key], key)
        # A second call on the same turn counts as the turn's second tool call.
        turn = row['turn_id']
        self.run_cli('stamp', '--db', str(self.db), '--turn-id', turn, '--stamp', 'received_at=1700000000')
        self.assertEqual([r['tool_calls'] for r in self.rows() if r['turn_id'] == turn], [1, 2])

    def test_play_output_is_unchanged_by_telemetry(self):
        room = self.lantern('1')
        on = self.run_cli('status', '--db', str(self.db))
        off = self.run_cli('status', '--db', str(self.db), env={'KIT_TELEMETRY': '0'})
        self.assertEqual(on.stdout, off.stdout)
        self.assertEqual(on.stderr, off.stderr)
        self.assertTrue(room.is_file())

    def test_off_switch_and_unwritable_path(self):
        self.assertIsNone(kit_telemetry.record(self.folder / 'missing' / 'k.sqlite', 'prepare', 1, 0, '{}'))
        os.environ['KIT_TELEMETRY'] = '0'
        try:
            self.assertIsNone(kit_telemetry.record(self.db, 'prepare', 1, 0, '{}'))
        finally:
            del os.environ['KIT_TELEMETRY']

    def test_report_medians_and_p95(self):
        for ms in range(1, 21):
            kit_telemetry.record(self.db, 'prepare', ms * 1_000_000, 0, '{"turn_id":"t%d"}' % ms)
        kit_telemetry.note(self.db, condition='D', first_visible_ms=4000, complete_ms=9000)
        kit_telemetry.note(self.db, condition='D', first_visible_ms=6000)
        rep = kit_telemetry.report(self.db)
        self.assertEqual(rep['by_command']['prepare']['engine_ms'], {'n': 20, 'median': 10.5, 'p95': 19.0})
        self.assertEqual(rep['manual_by_condition']['D']['first_visible_ms']['median'], 5000)
        self.assertEqual(rep['manual_by_condition']['D']['complete_ms']['n'], 1)
        text = self.run_cli('telemetry', 'report', '--db', str(self.db)).stdout
        self.assertIn('median / p95', text)
        self.assertIn('prepare: engine_ms 10.5 / 19', text)

    def test_log_is_git_ignored(self):
        self.assertIn('*.telemetry.jsonl', (ROOT / '.gitignore').read_text())


if __name__ == '__main__':
    unittest.main()
