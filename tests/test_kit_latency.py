"""Latency PR: a smaller session manifest, a lazy urllib, and bytecode built at mount."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_manifest

ROOT = Path(__file__).resolve().parents[1]


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


class CompactSchema(unittest.TestCase):
    def test_the_shorthand_expands_to_the_exact_schema(self):
        for schema in (kit_agent.ONE_PASS_SCHEMA, kit_agent.PLAN_SCHEMA, kit_agent.SPEECH_SCHEMA):
            with self.subTest(size=size(schema)):
                self.assertEqual(kit_manifest.expand_schema(kit_manifest.compact_schema(schema)), schema)

    def test_the_shorthand_is_less_than_half_the_size(self):
        compact = kit_manifest.compact_schema(kit_agent.ONE_PASS_SCHEMA)
        self.assertLess(size(compact) + len(kit_manifest.SCHEMA_NOTATION), size(kit_agent.ONE_PASS_SCHEMA) // 2)

    def test_unknown_shapes_pass_through_raw(self):
        odd = {'type': 'object', 'properties': {'x': {'type': ['string', 'null']}}, 'required': ['x'],
               'additionalProperties': False}
        self.assertEqual(kit_manifest.expand_schema(kit_manifest.compact_schema(odd)), odd)

    def test_split_and_join_still_restore_the_full_packet(self):
        packet = {'instructions': 'x', 'schema': kit_agent.ONE_PASS_SCHEMA, 'performance_limits': {},
                  'host_retry': 'r', 'performance_variant': 'v',
                  'input': {'private': {'personality_core': 'core', 'dm_context': {'source_id': 's'}}}}
        session, room, delta = kit_manifest.split(packet)
        self.assertIn('schema_notation', session)
        self.assertIsInstance(session['schema']['decision'], dict)
        self.assertEqual(kit_manifest.join(session, room, delta), packet)


class LazyNetwork(unittest.TestCase):
    def test_kit_agent_does_not_import_urllib_request_http_or_ssl(self):
        code = ('import sys; import runtime.kit_agent; '
                'print(sorted(m for m in ("urllib.request", "http.client", "ssl") if m in sys.modules))')
        out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), '[]')

    def test_urllib_still_resolves_when_used(self):
        self.assertTrue(callable(kit_agent.urllib.request.urlopen))
        self.assertTrue(issubclass(kit_agent.urllib.error.HTTPError, Exception))


class Precompile(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import kit_host
        self.kit_host = kit_host

    def test_mount_builds_the_runtime_bytecode(self):
        root = Path(tempfile.mkdtemp())
        (root / 'runtime').mkdir()
        (root / 'runtime' / 'a.py').write_text('X = 1\n')
        self.assertTrue(self.kit_host.precompile(root))
        self.assertTrue(list((root / 'runtime' / '__pycache__').glob('a.*.pyc')))

    def test_a_read_only_or_missing_folder_never_fails(self):
        self.assertIsInstance(self.kit_host.precompile(Path(tempfile.mkdtemp()) / 'missing'), bool)
        root = Path(tempfile.mkdtemp())
        (root / 'runtime').mkdir()
        (root / 'runtime' / 'a.py').write_text('X = 1\n')
        (root / 'runtime').chmod(0o555)
        try:
            self.assertIsInstance(self.kit_host.precompile(root), bool)
        finally:
            (root / 'runtime').chmod(0o755)


if __name__ == '__main__':
    unittest.main()
