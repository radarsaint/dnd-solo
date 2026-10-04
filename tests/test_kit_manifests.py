"""PR2 (plan update #3): one-pass packets in three layers, SessionManifest, RoomManifest and
TurnDelta, stable first and content-hashed. Kit echoes the hashes or rehydrates. Nothing is
trimmed: the layers join back to the full packet. Watchroom fixture; no model."""
import json
import unittest

from runtime import kit_manifest
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from runtime.state_context import InvalidChange
from test_kit_watchroom_stalls import Stalls, landing


WAITING = {'segments': [
    {'speaker': 'Narrator', 'text': 'The humming keeps its four notes and its slow pace, and once it falters as if '
                                    'the singer has lost his place, then picks the tune up again without hurry.'},
    {'speaker': 'Narrator', 'text': 'Cold air breathes up the stairwell from below, carrying wet stone and old smoke, '
                                    'and somewhere far down a drip keeps its own patient time against the dark. Nobody comes up, and nobody calls out, and the light under the iron door holds steady and warm while the long minutes slowly pass.'}]}


def nbytes(value):
    return len(json.dumps(value, ensure_ascii=False).encode('utf-8'))


class Layers(Stalls):
    def setUp(self):
        super().setUp()
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10),
                                    manifests=True)

    def echo(self, packet):
        return {'session': packet['session_manifest']['hash'], 'room': packet['room_manifest']['hash']}

    def open_room(self, echo=True):
        packet = self.bridge.prepare(opening=True, one_pass=True, turn_id='open')
        plan = self.plan_for(packet)
        plan['public_brief'].update(scope='feature')
        output = {'decision': plan, 'performance': landing()}
        if echo:
            output['manifest'] = self.echo(packet)
        return packet, output

    def wait(self, turn):
        packet = self.bridge.prepare('I wait on the landing and listen to the humming.', turn, one_pass=True)
        plan = self.plan_for(packet)
        plan['public_brief'].update(reply_to='I wait on the landing', scope='feature')
        return packet, {'decision': plan, 'performance': WAITING, 'manifest': self.echo(packet)}


class StableFirst(Layers):
    def test_the_first_packet_carries_both_bodies_first(self):
        packet, _ = self.open_room()
        self.assertEqual(list(packet)[:3], ['session_manifest', 'room_manifest', 'manifest_rule'])
        for layer in ('session_manifest', 'room_manifest'):
            self.assertEqual(packet[layer]['hash'], kit_manifest.digest(packet[layer]['body']))
        self.assertIn('personality_core', packet['session_manifest']['body'])   # the core, untrimmed
        self.assertIn('dm_only', packet['room_manifest']['body'])               # dm_only, untrimmed
        self.assertNotIn('instructions', packet)
        self.assertNotIn('personality_core', packet['input']['private'])

    def test_the_layers_join_back_to_the_full_packet(self):
        full = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10)).prepare(
            opening=True, one_pass=True, turn_id='full')
        session, room, delta = kit_manifest.split(full)
        self.assertEqual(kit_manifest.join(session, room, delta), full)
        layered, hashes, _ = kit_manifest.layered(full)
        self.assertEqual(kit_manifest.join(layered['session_manifest']['body'], layered['room_manifest']['body'],
                                           layered), full)

    def test_later_turns_send_hashes_only(self):
        packet, output = self.open_room()
        self.bridge.complete('open', output)
        later, _ = self.wait('w1')
        self.assertEqual(later['session_manifest'], {'hash': packet['session_manifest']['hash'], 'cached': True})
        self.assertTrue(later['room_manifest'].get('cached') or 'body' in later['room_manifest'])
        self.assertLess(nbytes(later), 30_000)
        private = later['input']['private']
        for key in ('player_action', 'accepted_public_event', 'story_brief', 'kit_state', 'dialogue_history'):
            self.assertIn(key, private)                       # the turn delta keeps the turn
        self.assertIn('player_perceivable', private['dm_context'])

    def test_the_default_bridge_sends_the_full_packet(self):
        packet = KitChatBridge(self.runtime).prepare(opening=True, one_pass=True, turn_id='plain')
        self.assertIn('instructions', packet)
        self.assertNotIn('session_manifest', packet)


class EchoOrRehydrate(Layers):
    def test_the_output_must_echo_the_hashes(self):
        packet, output = self.open_room(echo=False)
        with self.assertRaisesRegex(InvalidChange, 'rehydrate'):
            self.bridge.complete('open', output)
        output['manifest'] = self.echo(packet)
        self.assertTrue(self.bridge.complete('open', output)['spoken'])

    def test_a_wrong_hash_is_refused_and_rehydrate_gives_both_bodies(self):
        packet, output = self.open_room()
        self.bridge.complete('open', output)
        later, output = self.wait('w1')
        output['manifest'] = {'session': 'stale', 'room': later['room_manifest']['hash']}
        with self.assertRaisesRegex(InvalidChange, 'rehydrate'):
            self.bridge.complete('w1', output)
        full = self.bridge.rehydrate('w1')
        self.assertEqual(full['session_manifest'], packet['session_manifest'])
        self.assertEqual(full['room_manifest']['hash'], later['room_manifest']['hash'])
        self.assertEqual(kit_manifest.digest(full['room_manifest']['body']), full['room_manifest']['hash'])
        output['manifest'] = self.echo(full)
        self.assertTrue(self.bridge.complete('w1', output)['spoken'])


class Resend(Layers):
    def test_bodies_come_back_every_few_turns(self):
        packet, output = self.open_room()
        self.bridge.complete('open', output)
        sent = []
        for n in range(kit_manifest.FULL_EVERY + 1):
            later, out = self.wait(f'w{n}')
            sent.append('body' in later['session_manifest'])
            self.bridge.abandon(f'w{n}')
        self.assertFalse(any(sent[:kit_manifest.FULL_EVERY - 1]))
        self.assertTrue(any(sent))

    def test_a_rejection_streak_resends_the_bodies(self):
        packet, output = self.open_room()
        self.bridge.complete('open', output)
        later, out = self.wait('w1')
        flat = dict(out, performance={'segments': [{'speaker': 'Narrator', 'text': 'Dark.'}]})
        for _ in range(kit_manifest.REJECT_STREAK):
            with self.assertRaises(InvalidChange):
                self.bridge.complete('w1', flat)
        self.bridge.abandon('w1')
        again, _ = self.wait('w2')
        self.assertIn('body', again['session_manifest'])


class LiveCli(unittest.TestCase):
    """The live host's CLI sends layers by default and rehydrates on request."""

    def test_start_and_prepare_send_layers_and_rehydrate_restores_them(self):
        import contextlib, io, tempfile
        from pathlib import Path
        from unittest.mock import patch
        from runtime import kit_agent
        from test_kit_room_review import WATCH
        db = str(Path(tempfile.mkdtemp()) / 'kit.sqlite')

        def cli(*args):
            out = io.StringIO()
            with patch('sys.argv', ['kit_agent', *args, '--db', db]), contextlib.redirect_stdout(out):
                self.assertEqual(kit_agent.main(), 0)
            return json.loads(out.getvalue())
        opening = cli('start', '--room', str(WATCH))['prepared']
        self.assertIn('body', opening['session_manifest'])
        cli('abandon', '--turn-id', opening['turn_id'])
        later = cli('prepare', '--one-pass', '--action', 'I wait on the landing.', '--turn-id', 'w')
        self.assertTrue(later['session_manifest'].get('cached'))
        full = cli('rehydrate', '--turn-id', 'w')
        self.assertEqual(full['session_manifest']['hash'], later['session_manifest']['hash'])
        self.assertEqual(kit_manifest.digest(full['session_manifest']['body']), full['session_manifest']['hash'])


if __name__ == '__main__':
    unittest.main()
