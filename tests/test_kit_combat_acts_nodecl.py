"""Nagatha FAILED #122 at 9e33c4b: when Kit declares no combat acts (null or []), the turn must be
main's, entirely: the same pending ruling, the same refused attempt recorded, nothing else
committed; no synthesized turn. Her four playtest cases (a no-reaction line, a bare Avrae damage
line, a 'backs off 30 feet' line, a second no-reaction line) rebuilt on the synthetic fixture rooms,
state built at runtime. Main's outcome is taken on a twin fight with the combat_acts offer switched
off, and compared byte-for-byte."""
import json
import unittest
from unittest import mock

from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, pending_ruling_result
from runtime.state_context import HostSequenceError
from test_kit_combat_acts_retarget import kiln, shrine
from test_kit_combat_acts_slice2 import plan_for
from test_kit_review101c import rogue, warlock, without_shield, wizard

CASES = {
    'no reaction (warlock, kiln)': (lambda t: kiln(t, warlock(hp=60, gear=['dagger'])), 'No reaction.'),
    'avrae damage (wizard, shrine)': (lambda t: shrine(t, without_shield(wizard(hp=60)), 10), '3d8 (5, 8, 7) = 20 psychic'),
    'backs off (rogue, kiln)': (lambda t: kiln(t, rogue(speed='30 ft.')), 'Sorrel backs off 30 feet down the hall.'),
    'no reaction again (rogue, shrine)': (lambda t: shrine(t, rogue(), 10), 'No reaction.'),
}


class NoDeclarationIsMains(unittest.TestCase):
    @staticmethod
    def snapshot(runtime):
        revision, state = runtime.load()
        return revision, json.dumps(state, sort_keys=True), json.dumps(runtime.recent_kit_turns(limit=5), sort_keys=True)

    def mains(self, build, text):
        arena = build(self)
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        with mock.patch.object(RoomAdjudicator, '_declare_instead', return_value=None), \
                self.assertRaises(PendingRuling) as caught:
            bridge.prepare(text, 't', one_pass=True)
        return pending_ruling_result(caught.exception), self.snapshot(arena.runtime)

    def test_null_or_empty_is_mains_pending_ruling_byte_for_byte(self):
        for name, (build, text) in CASES.items():
            expected, after = self.mains(build, text)
            for declared in (None, []):
                with self.subTest(case=name, declared=declared):
                    arena = build(self)
                    runtime, bridge = arena.runtime, KitChatBridge(arena.runtime, arena.adjudicator)
                    packet = bridge.prepare(text, 't', one_pass=True)
                    self.assertIn('combat_acts', packet['input']['private']['acts'])
                    plan = plan_for(packet)
                    plan['combat_acts'] = declared
                    with self.assertRaises(PendingRuling) as caught:
                        bridge.complete('t', {'decision': plan, 'performance': {'segments': [
                            {'speaker': 'Narrator', 'text': 'You hold.'}]}})
                    self.assertEqual(pending_ruling_result(caught.exception), expected)
                    self.assertNotIn('You declare', str(caught.exception))
                    self.assertEqual(self.snapshot(runtime), after)
                    with self.assertRaises(HostSequenceError):  # the staged turn is gone
                        runtime.pending_kit_turn('t')


if __name__ == '__main__':
    unittest.main()
