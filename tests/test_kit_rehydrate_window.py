"""Nagatha's clean-host review: rehydrate could not recover the one-pass packet a window answer
returns. Answering a combat window (complete with the reaction) resolves it and returns the full
turn's packet under the same turn_id; a host that lost that response had no way to get it back:
rehydrate gave only the two manifest bodies (or refused, without layers), and resubmitting the
window answer was refused because the turn is now a one-pass turn.

Now rehydrate returns the turn's whole packet while it is pending, in full (both manifests
joined in), as well as both manifest bodies. Synthetic camp room; dice pinned."""
import unittest

from runtime import kit_manifest
from runtime.kit_agent import KitChatBridge
from runtime.state_context import InvalidChange
from test_kit_combat_checkpoints import CAST, NIK, OPEN, Camp

VOICED = [{'speaker': 'Narrator', 'text': 'Your dagger finds the cutthroat and he drops by the wagon.'},
          {'speaker': 'Kit', 'text': 'The scimitar flashes in at your ribs and catches you. Shield?'}]
ANSWER = {'decision': {'react': {'choice': 'shield', 'cast_in_avrae': True}}, 'performance': {'segments': []}}


class RehydrateAfterAWindowAnswer(unittest.TestCase):
    def answered(self, manifests):
        camp = Camp(self, sheet=NIK)
        bridge = KitChatBridge(camp.runtime, camp.adjudicator, manifests=manifests)
        bridge.prepare(OPEN, 'h1', one_pass=True)
        bridge.complete('h1', {'decision': {'window': 'voiced'}, 'performance': {'segments': VOICED}})
        asked = bridge.prepare(CAST, 'h3', one_pass=True)
        self.assertEqual(asked['stage'], 'window_answer')
        packet = bridge.complete('h3', dict(ANSWER))
        self.assertEqual(packet['stage'], 'one_pass')
        return camp, bridge, packet

    def test_the_lost_full_turn_packet_comes_back_in_layers_mode(self):
        camp, bridge, packet = self.answered(manifests=True)
        full = bridge.rehydrate('h3')
        self.assertIn('packet', full)
        expected = kit_manifest.join(full['session_manifest']['body'], full['room_manifest']['body'], packet)
        self.assertEqual(full['packet'], expected)
        self.assertEqual(full['packet']['stage'], 'one_pass')
        self.assertEqual(full['packet']['window_answered']['react'], 'shield')
        self.assertEqual(full['packet']['input'], expected['input'])

    def test_the_lost_packet_comes_back_without_layers(self):
        camp, bridge, packet = self.answered(manifests=False)
        full = bridge.rehydrate('h3')
        self.assertEqual(full['packet'], packet)

    def test_a_plain_one_pass_turn_rehydrates_its_packet_too(self):
        camp = Camp(self, sheet=NIK)
        bridge = KitChatBridge(camp.runtime, camp.adjudicator, manifests=True)
        bridge.prepare('I look around the camp.', 'p1', one_pass=True)
        full = bridge.rehydrate('p1')
        self.assertEqual(full['packet']['turn_id'], 'p1')
        self.assertIn('private', full['packet']['input'])

    def test_an_abandoned_turn_has_no_packet_to_rehydrate(self):
        camp, bridge, packet = self.answered(manifests=True)
        bridge.abandon('h3')
        self.assertNotIn('packet', bridge.rehydrate('h3'))  # its manifests still come back

    def test_an_unlayered_turn_without_a_packet_is_refused(self):
        camp, bridge, packet = self.answered(manifests=False)
        bridge.abandon('h3')
        with self.assertRaisesRegex(InvalidChange, 'nothing to rehydrate'):
            bridge.rehydrate('h3')

if __name__ == '__main__':
    unittest.main()
