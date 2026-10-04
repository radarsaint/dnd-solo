"""#99 review (Nagatha, 2026-10-04): manifest freshness by nonce, not by line completion.

Every manifest layer and every room diff carries a short random nonce. Kit echoes the nonces of
the copies she holds in the private ``manifest`` block of her output (``manifest.check``), never
in spoken. A wrong or missing nonce re-sends only that layer. A host whose room copy went stale
(it never applied a diff) is caught on the next turn; a chat restored from an uploaded save is
checked on its first turn; spoken that carries a hash, a nonce or the check is refused.
Synthetic non-6c rooms (a grain mill and a ferry house built on the watchroom shape); no model."""
import copy
import json
import shutil
import sys
import unittest
from pathlib import Path

from runtime import kit_manifest
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_manifests import WAITS, Host, Layers
from test_kit_room_review import ROOT, WATCH
from test_kit_watchroom_stalls import landing

ROOMS = {
    'mill': dict(id='synthetic-grain-mill', room='Millhouse', npc='miller', name='Floury miller',
                 secret='The miller hides a stolen signet in the grain.'),
    'ferry': dict(id='synthetic-ferry-house', room='Ferry house', npc='ferryman', name='Old ferryman',
                  secret='The ferryman drowned the last toll collector.'),
}


def synthetic(key):
    spec = ROOMS[key]
    room = json.loads((ROOT / WATCH).read_text())
    room['id'] = spec['id']
    room['areas']['watchroom'].update(name=spec['room'], called='the ' + spec['room'].lower())
    warden = room['actors'].pop('warden')
    warden.update(name=spec['name'], secrets=[spec['secret']], knowledge=[spec['secret']])
    room['actors'][spec['npc']] = warden
    for hook in room['story']['watchroom']['hooks']:
        hook['by'] = spec['npc']
        hook['roots'] = [spec['npc']]
        hook['delivered_when']['said']['by'] = [spec['npc']]
    room['areas']['landing']['tease']['heard'][0]['actor'] = spec['npc']
    return room


class NonceHost(Host):
    """The honest host of test_kit_manifests, plus the nonces of the copies it holds."""

    def __init__(self):
        super().__init__()
        self.nonces = {'session': None, 'room': None}
        self.frozen = set()   # layers this host stops updating (a stale copy)

    def read(self, packet):
        for layer in ('session', 'room'):
            item = packet.get(f'{layer}_manifest') or {}
            if layer in self.frozen and self.bodies[layer] is not None:
                continue
            if 'body' in item or 'diff' in item:
                self.nonces[layer] = item.get('nonce')
        live = {k: v for k, v in packet.items() if not (k.endswith('_manifest') and k[:-9] in self.frozen
                                                          and self.bodies[k[:-9]] is not None)}
        super().read(live)

    def forget(self, layer=None):
        for name in ([layer] if layer else ['session', 'room']):
            self.bodies[name] = None
            self.nonces[name] = None

    def echo(self, packet):
        echo = {'session': packet['session_manifest']['hash'], 'room': packet['room_manifest']['hash']}
        if packet.get('manifest_check'):
            echo['check'] = {layer: self.nonces[layer] or '' for layer in packet['manifest_check']['lines']}
        return echo


class Fresh(Layers):
    room_key = 'mill'

    def setUp(self):
        super().setUp()
        self.runtime = self.start(str(self.write(synthetic(self.room_key))))
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10),
                                    manifests=True)
        self.host = NonceHost()

    def turn(self, turn):
        packet, output = self.wait(turn)
        self.host.read(packet)
        output['manifest'] = self.host.echo(packet)
        return packet, output

    def opened(self):
        packet, output = self.open_room(echo=False)
        self.host.read(packet)
        output['manifest'] = self.host.echo(packet)
        self.bridge.complete('open', output)
        return packet


class EveryLayerCarriesANonce(Fresh):
    def test_bodies_and_diffs_carry_a_nonce_and_cached_layers_do_not(self):
        opened = self.opened()
        for layer in ('session', 'room'):
            self.assertRegex(opened[f'{layer}_manifest']['nonce'], r'^\d[0-9a-f]{6}$')
        self.assertNotEqual(opened['session_manifest']['nonce'], opened['room_manifest']['nonce'])
        packet, output = self.turn('w1')
        self.assertEqual(packet['session_manifest'], {'hash': opened['session_manifest']['hash'], 'cached': True})
        self.assertNotIn(opened['session_manifest']['nonce'], json.dumps(packet))
        self.bridge.complete('w1', output)
        self.go_in()
        moved, output = self.turn('in1')
        self.assertIn('diff', moved['room_manifest'])
        self.assertRegex(moved['room_manifest']['nonce'], r'^\d[0-9a-f]{6}$')
        self.assertNotEqual(moved['room_manifest']['nonce'], opened['room_manifest']['nonce'])
        self.bridge.complete('in1', output)

    def test_every_layered_packet_asks_for_the_nonces(self):
        self.opened()
        for n in range(5):
            packet, output = self.turn(f'w{n}')
            self.assertEqual(set(packet['manifest_check']['lines']), {'session', 'room'})
            self.bridge.complete(f'w{n}', output)


class StaleRoomIsCaught(Fresh):
    def test_a_host_that_never_applied_the_room_diff_is_caught_and_only_the_room_is_resent(self):
        self.opened()
        self.host.frozen.add('room')        # this host keeps its first room copy forever
        self.go_in()
        packet, output = self.turn('in1')
        self.assertIn('diff', packet['room_manifest'])
        with self.assertRaisesRegex(InvalidChange, r'room'):
            self.bridge.complete('in1', output)
        self.bridge.abandon('in1')
        self.host.frozen.clear()
        again, output = self.turn('in2')
        self.assertIn('body', again['room_manifest'])
        self.assertEqual(again['session_manifest'].get('cached'), True, 'only the stale layer is re-sent')
        self.assertTrue(self.bridge.complete('in2', output)['spoken'])

    def test_a_lost_session_copy_resends_only_the_session(self):
        self.opened()
        packet, output = self.turn('w1')
        self.bridge.complete('w1', output)
        self.host.forget('session')
        packet, output = self.turn('w2')
        with self.assertRaisesRegex(InvalidChange, r'session'):
            self.bridge.complete('w2', output)
        self.bridge.abandon('w2')
        again, output = self.turn('w3')
        self.assertIn('body', again['session_manifest'])
        self.assertEqual(again['room_manifest'].get('cached'), True)
        self.bridge.complete('w3', output)

    def test_rehydrate_returns_the_missed_layer_with_a_fresh_nonce(self):
        self.opened()
        self.host.forget('session')
        packet, output = self.turn('w1')
        with self.assertRaises(InvalidChange):
            self.bridge.complete('w1', output)
        full = self.bridge.rehydrate('w1')
        self.assertIn('session_manifest', full)
        self.assertNotIn('room_manifest', full)
        self.host.read(full)
        output['manifest'] = self.host.echo(packet)
        self.assertTrue(self.bridge.complete('w1', output)['spoken'])
        nxt, _ = self.turn('w2')
        self.assertTrue(nxt['session_manifest'].get('cached'))

    def test_a_correct_resubmit_clears_the_miss(self):
        self.opened()
        packet, output = self.turn('w1')
        good = copy.deepcopy(output['manifest'])
        output['manifest']['check'] = dict(good['check'], room='0000000')
        with self.assertRaises(InvalidChange):
            self.bridge.complete('w1', output)
        output['manifest'] = good          # Kit had the copy after all and resubmits it right
        self.bridge.complete('w1', output)
        nxt, _ = self.turn('w2')
        self.assertTrue(nxt['session_manifest'].get('cached'))
        self.assertTrue(nxt['room_manifest'].get('cached'), 'a successful echo clears the miss')


class FerryHouse(StaleRoomIsCaught):
    room_key = 'ferry'


class LenientEcho(unittest.TestCase):
    def test_formatting_does_not_fail_a_host_that_holds_the_copy(self):
        expected = ['sentences', 'to', 'test', 'tempt', 'threaten', 'or', 'tell', 'a']
        for answer in ('sentences to test, tempt, threaten or tell a', 'sentences to tempt, threaten or tell a',
                       'sentences to test, and tempt, threaten or tell',
                       'A character may take a few sentences to test tempt threaten',
                       'sentences to test/tempt/threaten or tell a'):
            self.assertTrue(kit_manifest._check_passes(answer, expected), answer)
        self.assertTrue(kit_manifest._check_passes(' "3a1b2c4" ', ['3a1b2c4']))
        self.assertTrue(kit_manifest._check_passes('3A1B2C4', ['3a1b2c4']))
        self.assertFalse(kit_manifest._check_passes('3a1b2c5', ['3a1b2c4']))
        self.assertFalse(kit_manifest._check_passes('', ['3a1b2c4']))


class SpokenNeverCarriesManifestInternals(Fresh):
    def leak(self, extra):
        self.opened()
        packet, output = self.turn('w1')
        output['performance'] = copy.deepcopy(output['performance'])
        output['performance']['segments'][-1]['text'] += ' ' + extra(packet, output)
        with self.assertRaisesRegex(InvalidChange, 'manifest'):
            self.bridge.complete('w1', output)

    def test_a_hash_in_spoken_is_refused(self):
        self.leak(lambda packet, _: f'Session {packet["session_manifest"]["hash"]}.')

    def test_a_nonce_in_spoken_is_refused(self):
        self.leak(lambda _, output: f'Check {output["manifest"]["check"]["room"]}.')

    def test_the_check_text_in_spoken_is_refused(self):
        self.leak(lambda packet, _: packet['manifest_check']['lines']['session'] + '.')


class RestoredSave(Fresh):
    def test_a_new_chat_from_an_uploaded_save_is_checked_on_turn_one(self):
        self.opened()
        for n in range(2):
            packet, output = self.turn(f'w{n}')
            self.bridge.complete(f'w{n}', output)
        copied = Path(self.folder) / 'uploaded.sqlite'
        shutil.copy(self.runtime.path, copied)
        runtime = Runtime(copied)
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10), manifests=True)
        first = bridge.prepare('I wait on the landing and listen.', 'r1', one_pass=True)
        self.assertIn('manifest_check', first, 'a cached layer never goes out without a check')
        plan = self.plan_for(first)
        plan['public_brief'].update(reply_to='I wait on the landing', scope='feature')
        fresh = NonceHost()       # the new chat holds nothing
        with self.assertRaisesRegex(InvalidChange, 'rehydrate'):
            bridge.complete('r1', {'decision': plan, 'performance': WAITS[1], 'manifest': fresh.echo(first)})
        fresh.read(bridge.rehydrate('r1'))
        self.assertTrue(bridge.complete('r1', {'decision': plan, 'performance': WAITS[1],
                                               'manifest': fresh.echo(first)})['spoken'])


class ReplayCountsTheEcho(unittest.TestCase):
    def test_the_echo_is_part_of_the_written_output(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import contextlib, io
        import watchroom_replay
        with contextlib.redirect_stdout(io.StringIO()):
            report = watchroom_replay.run(manifests=True)
        rows = [r for r in report['turns'] if 'packet_bytes' in r]
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r['output_bytes'], r['decision_bytes'] + r['speech_bytes'] + r['manifest_out_bytes'])


if __name__ == '__main__':
    unittest.main()
