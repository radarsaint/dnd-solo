"""Nagatha FAILED #122 at 9e33c4b: when Kit declares no combat acts (null or []), the turn must be
main's, entirely: the same pending ruling, the same refused attempt recorded, nothing else
committed; no synthesized turn. Her playtest snapshots (tests/fixtures/declared/snaps, from
/tmp/rvw/snaps): a20, a21, a26, a30. Main's outcome is taken on a copy of the same snapshot
with the combat_acts offer switched off, and compared byte-for-byte."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, pending_ruling_result
from runtime.state_context import HostSequenceError, Runtime
from test_kit_combat_acts_slice2 import plan_for

SNAPS = Path(__file__).resolve().parent / 'fixtures' / 'declared' / 'snaps'
CASES = {'a20': '3d8 (5, 8, 7) = 20 psychic', 'a21': 'Nik backs off 30 feet down the hall.',
         'a26': 'No reaction.', 'a30': 'No reaction.'}


class NoDeclarationIsMains(unittest.TestCase):
    def copy(self, snap):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'kit.sqlite'
        shutil.copy(SNAPS / f'{snap}.sqlite', path)
        runtime = Runtime(path)
        self.addCleanup(runtime.close)
        return runtime, KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))

    @staticmethod
    def snapshot(runtime):
        revision, state = runtime.load()
        return revision, json.dumps(state, sort_keys=True), json.dumps(runtime.recent_kit_turns(limit=5), sort_keys=True)

    def mains(self, snap, text):
        runtime, bridge = self.copy(snap)
        with mock.patch.object(RoomAdjudicator, '_declare_instead', return_value=None), \
                self.assertRaises(PendingRuling) as caught:
            bridge.prepare(text, 't', one_pass=True)
        return pending_ruling_result(caught.exception), self.snapshot(runtime)

    def test_null_or_empty_is_mains_pending_ruling_byte_for_byte(self):
        for snap, text in CASES.items():
            expected, after = self.mains(snap, text)
            for declared in (None, []):
                with self.subTest(snap=snap, declared=declared):
                    runtime, bridge = self.copy(snap)
                    packet = bridge.prepare(text, 't', one_pass=True)
                    self.assertIn('combat_acts', packet['input']['private']['acts'])
                    plan = plan_for(packet)
                    plan['combat_acts'] = declared
                    with self.assertRaises(PendingRuling) as caught:
                        bridge.complete('t', {'decision': plan, 'performance': {'segments': [
                            {'speaker': 'Narrator', 'text': 'You hold.'}]}})
                    self.assertEqual(pending_ruling_result(caught.exception), expected)
                    self.assertEqual(self.snapshot(runtime), after)
                    with self.assertRaises(HostSequenceError):  # the staged turn is gone
                        runtime.pending_kit_turn('t')


if __name__ == '__main__':
    unittest.main()
