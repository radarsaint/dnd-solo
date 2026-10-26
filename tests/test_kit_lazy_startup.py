"""Startup cost (latbench REPORT.md): combat, chargen, toll and twenty-one load on first use,
module phrase patterns compile on first use, and the manifest split copies only what it pops."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from runtime import _lazy, kit_manifest

ROOT = Path(__file__).resolve().parents[1]


class LazyStartup(unittest.TestCase):
    def test_importing_the_agent_leaves_the_heavy_modules_unloaded(self):
        code = ('import sys, runtime.kit_agent; print([m for m in ("runtime.kit_combat", "runtime.kit_chargen", '
                '"runtime.kit_toll", "runtime.kit_twenty_one") if m in sys.modules])')
        out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), '[]')

    def test_a_lazy_module_loads_on_first_use_and_sees_patches(self):
        from unittest import mock
        from runtime import kit_agent, kit_combat
        with mock.patch.object(kit_combat, 'aimed_attack', return_value=True):
            self.assertIs(kit_agent.kit_combat.aimed_attack('x', None, ()), True)

    def test_a_lazy_pattern_behaves_like_the_compiled_one(self):
        lazy = _lazy.regex(r'\bshield\s+(up)\b', 2)
        self.assertEqual(lazy.search('Shield UP!').group(1), 'UP')
        self.assertEqual(lazy.pattern, r'\bshield\s+(up)\b')
        self.assertEqual(lazy.sub('-', 'shield up'), '-')


class SplitCopiesOnlyWhatItPops(unittest.TestCase):
    def test_split_leaves_the_packet_and_joins_back(self):
        packet = {'instructions': ['x'], 'schema': {'a': 1}, 'input': {'private': {
            'personality_core': {'p': 1}, 'dm_context': {'dm_only': {'f': [1]}, 'scene': {'s': 1}}}, 'public': {}}}
        before = json.dumps(packet, sort_keys=True)
        session, room, delta = kit_manifest.split(packet)
        self.assertEqual(json.dumps(packet, sort_keys=True), before)
        self.assertNotIn('dm_only', delta['input']['private']['dm_context'])
        self.assertEqual(json.dumps(kit_manifest.join(session, room, delta), sort_keys=True), before)


if __name__ == '__main__':
    unittest.main()
