"""Priority 4, latency instrumentation (docs/latency/experiment-protocol.md): per-turn telemetry
JSONL, the opt-in compact packet and its fidelity to the active scene, and a stable packet
prefix. Corpus: tests/fixtures/adventures/lantern_ferry.txt (original synthetic adventure) and
the watchroom fixture room. No model; no published text."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_manifest, kit_telemetry  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, personality_core_text  # noqa: E402
from test_kit_manifests import Layers  # noqa: E402

CORPUS = ROOT / 'tests/fixtures/adventures/lantern_ferry.txt'
NIK = ROOT / 'tests/fixtures/characters/nik.json'
TIMESTAMP = re.compile(r'\b20\d\d-\d\d-\d\d[T ]\d\d:\d\d|\b1[6-9]\d{8}(?:\.\d+)?\b')


def run(*args, env=None):
    return subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *args], cwd=ROOT, capture_output=True,
                          text=True, env={**os.environ, **(env or {})})


def adventure_db(folder, name):
    db = Path(folder) / f'{name}.sqlite'
    kit_adventure.import_adventure(db, text=CORPUS.read_text(encoding='utf-8'))
    kit_adventure.compile_location(db, '1')
    return db


class AdventureOpening(unittest.TestCase):
    """The fixture adventure's opening, full and compact, through the real CLI."""

    @classmethod
    def setUpClass(cls):
        warnings.simplefilter('ignore')
        cls.temp = tempfile.TemporaryDirectory()
        cls.out, cls.dbs = {}, {}
        for name, extra in (('full', []), ('compact', ['--compact']), ('again', [])):
            db = adventure_db(cls.temp.name, name)
            done = run('start', '--db', str(db), '--room', str(kit_adventure.room_file(db, '1')),
                       '--sheet', str(NIK), '--host', 'unittest', *extra)
            assert done.returncode == 0, done.stderr
            cls.dbs[name], cls.out[name] = db, done.stdout

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def packet(self, name):
        return json.loads(self.out[name])['prepared']

    # -- telemetry --

    def test_one_record_per_call_with_null_host_fields(self):
        rows = kit_telemetry.read(self.dbs['compact'])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(tuple(row), kit_telemetry.FIELDS)
        self.assertEqual((row['command'], row['host'], row['packet_mode'], row['exit_code'], row['tool_calls']),
                         ('start', 'unittest', 'compact', 0, 1))
        self.assertEqual(row['turn_id'], self.packet('compact')['turn_id'])
        data = self.out['compact'].encode('utf-8')
        self.assertEqual(row['packet_bytes'], len(data))
        import hashlib
        self.assertEqual(row['packet_sha256'], hashlib.sha256(data).hexdigest())
        self.assertGreater(row['engine_ms'], 0)
        self.assertGreater(row['serialization_ms'], 0)
        for name in kit_telemetry.HOST_ONLY:
            self.assertIsNone(row[name], name)   # never guessed

    def test_telemetry_flags_never_reach_the_packet(self):
        self.assertNotIn('unittest', self.out['full'])

    def test_tool_calls_count_per_turn_and_the_report(self):
        db = self.dbs['again']
        turn = self.packet('again')['turn_id']
        self.assertEqual(run('rehydrate', '--db', str(db), '--turn-id', turn).returncode, 0)
        rows = kit_telemetry.read(db)
        self.assertEqual([r['tool_calls'] for r in rows if r['turn_id'] == turn], [1, 2])
        self.assertEqual(len({r['session_id'] for r in rows}), 1)
        shown = run('telemetry', 'report', '--db', str(db))
        self.assertEqual(shown.returncode, 0)
        report = json.loads(shown.stdout)
        self.assertEqual(report['records'], 2)
        self.assertEqual(report['tool_calls_per_turn']['median'], 2)
        self.assertIn('p95', report['by_command']['start|full']['engine_ms'])
        self.assertEqual(set(report['host_only_fields'].values()), {0})

    # -- compact vs full --

    def test_full_stays_the_default(self):
        self.assertIn('personality_core', self.packet('full')['session_manifest']['body'])
        self.assertNotIn('retrieval', self.packet('full'))

    def test_compact_is_smaller(self):
        self.assertLess(len(self.out['compact']), len(self.out['full']) * 0.75)

    def test_compact_keeps_the_whole_active_scene(self):
        full, compact = self.packet('full'), self.packet('compact')
        for key in full:
            if key not in ('session_manifest', 'room_manifest', 'turn_id'):
                self.assertEqual(compact[key], full[key], key)   # turn delta, first_try, input: identical
        fs, cs = full['session_manifest']['body'], compact['session_manifest']['body']
        for key in fs:
            if key != 'personality_core':
                self.assertEqual(cs[key], fs[key], key)          # the operating contract, whole
        fr, cr = full['room_manifest']['body'], compact['room_manifest']['body']
        self.assertEqual(cr, fr)   # one location: every hidden fact is in or next to the scene
        self.assertIn('rehydrate', compact['retrieval']['full_manifests'])
        self.assertIn('persona', cs['personality_ref']['command'])

    def test_compact_reveal_ids_all_resolve(self):
        private = self.packet('compact')['input']['private']
        self.assertEqual(private['reveal'], self.packet('full')['input']['private']['reveal'])
        self.assertEqual(private['story_brief'], self.packet('full')['input']['private']['story_brief'])

    # -- stable prefix --

    def test_session_manifest_is_byte_stable_across_sessions(self):
        prefix = lambda text: text[:text.index('"room_manifest"')]  # noqa: E731
        a, b = (self.out[n][self.out[n].index('"prepared"'):] for n in ('full', 'again'))
        self.assertEqual(prefix(a), prefix(b))

    def test_no_volatile_state_before_the_packet(self):
        for name in ('full', 'compact'):
            text = self.out[name]
            head = text[:text.index('"room_manifest"')]
            self.assertNotIn(self.packet(name)['turn_id'], head)
            self.assertIsNone(TIMESTAMP.search(head), name)
            keys = list(json.loads(text))
            self.assertLess(keys.index('prepared'), keys.index('next_step'))
            self.assertEqual(list(self.packet(name))[:3], ['session_manifest', 'room_manifest', 'manifest_rule'])


class TelemetrySwitches(unittest.TestCase):
    def test_off_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            db = adventure_db(folder, 'off')
            self.assertEqual(run('start', '--db', str(db), '--room', str(kit_adventure.room_file(db, '1')),
                                 '--sheet', str(NIK), env={'KIT_TELEMETRY': '0'}).returncode, 0)
            self.assertFalse(kit_telemetry.path_for(db).exists())
            self.assertEqual(run('status', '--db', str(db)).returncode, 0)
            self.assertEqual(kit_telemetry.read(db)[0]['command'], 'status')

    def test_a_missing_save_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'none.sqlite'
            run('status', '--db', str(db))
            self.assertFalse(kit_telemetry.path_for(db).exists())

    def test_p95_is_nearest_rank(self):
        self.assertEqual(kit_telemetry.summarize(range(1, 21)), {'n': 20, 'median': 10.5, 'p95': 19})
        self.assertIsNone(kit_telemetry.summarize([None, None]))


class FarFacts(unittest.TestCase):
    def test_far_hidden_facts_are_withheld_and_named(self):
        room = {'constraints': ['x'], 'dm_only': {
            'geometry': {'d1': {'areas': ['a', 'b']}, 'd2': {'areas': ['b', 'c']}},
            'actors': {'guard': {'area': 'c'}},
            'unrevealed_facts': {'here': {'area': 'a', 'text': 'A'}, 'next': {'area': 'b', 'text': 'B'},
                                 'far': {'area': 'c', 'text': 'C'}}}}
        session, out = kit_telemetry.compact_parts({'personality_core': 'P', 'instructions': 'I'}, room, 'a')
        self.assertEqual(sorted(out['dm_only']['unrevealed_facts']), ['here', 'next'])
        self.assertEqual(out['far_facts_withheld']['ids'], ['far'])
        self.assertEqual(out['dm_only']['actors'], room['dm_only']['actors'])   # actors and ways stay
        self.assertEqual(out['dm_only']['geometry'], room['dm_only']['geometry'])
        self.assertNotIn('personality_core', session)
        self.assertEqual(session['instructions'], 'I')
        self.assertIn('c', room['dm_only']['unrevealed_facts']['far']['area'])   # input untouched


class WatchroomCompact(Layers):
    """Compact on the watchroom fixture: the opening completes, and rehydrate gives the full bodies."""

    def setUp(self):
        super().setUp()
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10),
                                    manifests=True, compact=True)

    def test_compact_opening_commits_and_rehydrates_full(self):
        packet, output = self.open_room()
        self.assertNotIn('personality_core', packet['session_manifest']['body'])
        self.assertTrue(self.bridge.complete('open', output)['spoken'])
        back = self.bridge.rehydrate('open')
        self.assertEqual(back['session_manifest']['body']['personality_core'], personality_core_text())
        fr, cr = back['room_manifest']['body'], packet['room_manifest']['body']
        area = packet['input']['private']['dm_context']['scene']['current_area']
        near = kit_telemetry.near_areas(fr['dm_only'], area)
        for fact_id, fact in fr['dm_only']['unrevealed_facts'].items():
            if fact.get('area') in near:
                self.assertEqual(cr['dm_only']['unrevealed_facts'][fact_id], fact)
            else:
                self.assertIn(fact_id, cr['far_facts_withheld']['ids'])
        self.assertEqual(back['session_manifest']['hash'],
                         kit_manifest.digest(back['session_manifest']['body']))


if __name__ == '__main__':
    unittest.main()
