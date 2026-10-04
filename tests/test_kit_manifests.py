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


WAITS = [WAITING] + [{'segments': [{'speaker': 'Narrator', 'text': a}, {'speaker': 'Narrator', 'text': b}]} for a, b in (
    ('A moth finds the lamplight leaking from the gap and batters itself against the iron, ticking softly, '
     'until it gives up and drifts away down into the stairwell. '
     'The draft that carries it smells of wet rock and tallow.',
     'Inside, a stool scrapes once on flagstones. The humming pauses for a long breath, a cough follows, and '
     'then the tune returns, a little slower than before, as if its owner has settled in for a long night of it. Lamplight wavers on the landing stones and steadies.'),
    ('Wind leans on some unseen shutter far above and makes it groan. Dust sifts from the ceiling joists and '
     'settles on your sleeve like fine flour. '
     'A rat noses along the far wall, sees you, and thinks better of it.',
     'The man behind the iron door mutters a word you cannot catch, laughs at himself under his breath, and '
     'goes back to the four notes. A spoon rattles in a cup. Whatever he is drinking, he drinks it slowly, '
     'and the landing stays empty. Below, the stair keeps its dark.'),
    ('Your own breathing sounds loud in the hush. The stone under your boots is worn smooth in a shallow dip '
     'where countless guards have stood exactly where you stand now. '
     'The iron door is cold enough to feel from a hand away.',
     'From the room comes the creak of leather and the soft knock of a spear butt set down against wood. The '
     'hum breaks off, starts over from the first note, and steadies. Nothing else stirs on the stair, above or '
     'below, for a good while. The light in the gap does not move.'),
    ('Somewhere deep below a heavy door booms shut, and the sound rolls up the stairwell and dies against the '
     'iron. The lamp beyond the gap flickers, then holds. '
     'A thin line of smoke curls out over the threshold and fades.',
     'Paper rustles inside, a page turned and smoothed flat with a palm. The singer loses the tune, finds it, '
     'loses it again, and gives up with a grunt. Silence settles, close and warm, broken only by the tick of '
     'cooling metal somewhere near the hinges. No one comes.'))]


def nbytes(value):
    return len(json.dumps(value, ensure_ascii=False).encode('utf-8'))


class Layers(Stalls):
    def setUp(self):
        super().setUp()
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10),
                                    manifests=True)

    def echo(self, packet):
        """The hashes, plus the nonces of the copies this host holds (#99 review: every layer and
        room diff carries one; Kit echoes them in manifest.check)."""
        held = self.__dict__.setdefault('held_nonces', {})
        for layer in ('session', 'room'):
            item = packet.get(f'{layer}_manifest') or {}
            if item.get('nonce'):
                held[layer] = item['nonce']
        echo = {'session': packet['session_manifest']['hash'], 'room': packet['room_manifest']['hash']}
        if packet.get('manifest_check'):
            echo['check'] = {layer: held.get(layer) or '' for layer in packet['manifest_check']['lines']}
        return echo

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
        self.waited = getattr(self, 'waited', -1) + 1
        speech = WAITS[self.waited % len(WAITS)]
        return packet, {'decision': plan, 'performance': speech, 'manifest': self.echo(packet)}


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
        self.assertEqual({k: v for k, v in full['session_manifest'].items() if k != 'nonce'},
                         {k: v for k, v in packet['session_manifest'].items() if k != 'nonce'})
        self.assertNotEqual(full['session_manifest']['nonce'], packet['session_manifest']['nonce'])
        self.assertEqual(full['room_manifest']['hash'], later['room_manifest']['hash'])
        self.assertEqual(kit_manifest.digest(full['room_manifest']['body']), full['room_manifest']['hash'])
        self.echo(full)                      # the host keeps the copies (and their nonces)
        output['manifest'] = self.echo(later)
        self.assertTrue(self.bridge.complete('w1', output)['spoken'])


WORD = __import__('re').compile(r"[a-z0-9']+")


def words(text):
    return WORD.findall(str(text).casefold())


class Host:
    """A scripted host with an honest memory: it keeps every body it is sent, applies room
    diffs to the copy it holds, and echoes the nonce of each copy it holds (or cannot)."""

    def __init__(self):
        self.bodies = {'session': None, 'room': None}
        self.nonces = {'session': None, 'room': None}

    def read(self, packet):
        for layer in ('session', 'room'):
            item = packet.get(f'{layer}_manifest') or {}
            if item.get('nonce') and ('body' in item or 'diff' in item):
                self.nonces[layer] = item['nonce']
            if 'body' in item:
                self.bodies[layer] = item['body']
            elif 'diff' in item:
                assert self.bodies[layer] is not None and kit_manifest.digest(self.bodies[layer]) == item['base']
                self.bodies[layer] = kit_manifest.apply_diff(self.bodies[layer], item['diff'])
                assert kit_manifest.digest(self.bodies[layer]) == item['hash'], 'diff did not land on the new hash'

    def forget(self):
        self.bodies = {'session': None, 'room': None}
        self.nonces = {'session': None, 'room': None}

    def echo(self, packet):
        echo = {'session': packet['session_manifest']['hash'], 'room': packet['room_manifest']['hash']}
        check = packet.get('manifest_check')
        if check:
            echo['check'] = {layer: self.nonces[layer] or '' for layer in check['lines']}
        return echo


class Amortized(Layers):
    """PR-T: a body is sent when its hash changes, a room change is a diff, and a cache miss
    (a wrong or missing echo, a failed check, a rehydrate request) is the only full re-send."""

    def setUp(self):
        super().setUp()
        self.host = Host()

    def play_open(self):
        packet, output = self.open_room(echo=False)
        self.host.read(packet)
        output['manifest'] = self.host.echo(packet)
        self.bridge.complete('open', output)
        return packet

    def play_wait(self, turn):
        packet, output = self.wait(turn)
        self.host.read(packet)
        output['manifest'] = self.host.echo(packet)
        return packet, output

    def test_the_session_body_is_sent_once_in_twenty_turns(self):
        self.play_open()
        sizes = []
        for n in range(20):
            packet, output = self.play_wait(f'w{n}')
            self.assertNotIn('body', packet['session_manifest'], f'turn w{n} re-sent the session body')
            self.assertNotIn('body', packet['room_manifest'], f'turn w{n} re-sent an unchanged room body')
            sizes.append(nbytes(packet))
            self.bridge.complete(f'w{n}', output)
        self.assertLess(max(sizes), 30_000)

    def test_a_room_change_is_sent_as_a_diff_the_host_can_apply(self):
        opened = self.play_open()
        self.go_in()
        packet, output = self.play_wait('in1')
        room = packet['room_manifest']
        self.assertNotIn('body', room)
        self.assertEqual(room['base'], opened['room_manifest']['hash'])
        self.assertNotEqual(room['hash'], room['base'])
        self.assertLess(nbytes(room['diff']), nbytes(self.host.bodies['room']))
        self.assertEqual(kit_manifest.digest(self.host.bodies['room']), room['hash'])
        self.assertTrue(packet['session_manifest'].get('cached'))
        self.bridge.complete('in1', output)
        again, _ = self.play_wait('in2')
        self.assertEqual(again['room_manifest'], {'hash': room['hash'], 'cached': True})

    def test_diff_round_trips(self):
        old = {'a': 1, 'b': {'c': [1, 2], 'd': 'x'}, 'e': 'gone'}
        new = {'a': 1, 'b': {'c': [1, 2, 3], 'f': None}, 'g': {'h': 'new'}}
        diff = kit_manifest.diff(old, new)
        self.assertEqual(kit_manifest.apply_diff(old, diff), new)
        self.assertEqual(old['e'], 'gone')  # the base is not changed in place
        self.assertEqual(kit_manifest.diff(new, new), [])

    def test_a_wrong_echo_is_a_cache_miss_and_the_next_turn_carries_both_bodies(self):
        self.play_open()
        packet, output = self.play_wait('w1')
        output['manifest'] = {'session': 'stale', 'room': packet['room_manifest']['hash']}
        with self.assertRaisesRegex(InvalidChange, 'rehydrate'):
            self.bridge.complete('w1', output)
        self.bridge.abandon('w1')
        again, _ = self.play_wait('w2')
        self.assertIn('body', again['session_manifest'])
        self.assertIn('body', again['room_manifest'])

    def test_after_a_rehydrate_the_next_turn_is_cached_again(self):
        self.play_open()
        packet, output = self.play_wait('w1')
        output['manifest'] = {'session': packet['session_manifest']['hash']}
        with self.assertRaisesRegex(InvalidChange, 'rehydrate'):
            self.bridge.complete('w1', output)
        full = self.bridge.rehydrate('w1')
        self.host.read(full)
        output['manifest'] = self.host.echo(packet)
        self.bridge.complete('w1', output)
        again, _ = self.play_wait('w2')
        self.assertTrue(again['session_manifest'].get('cached'))
        self.assertTrue(again['room_manifest'].get('cached'))

    def test_the_delta_never_carries_a_held_nonce(self):
        opened = self.play_open()
        for n in range(3):
            packet, output = self.play_wait(f'w{n}')
            self.assertIn('manifest_check', packet)
            text = json.dumps(packet)
            for layer in ('session', 'room'):
                self.assertNotIn(opened[f'{layer}_manifest']['nonce'], text)
            self.bridge.complete(f'w{n}', output)

    def test_a_host_that_lost_its_copy_is_caught_on_the_next_turn_and_rehydrated(self):
        self.play_open()
        packet, output = self.play_wait('w0')
        self.bridge.complete('w0', output)
        self.host.forget()        # the chat trimmed the old turns: the bodies are gone
        packet, output = self.play_wait('w1')
        with self.assertRaisesRegex(InvalidChange, 'rehydrate'):
            self.bridge.complete('w1', output)
        self.host.read(self.bridge.rehydrate('w1'))
        output['manifest'] = self.host.echo(packet)
        self.assertTrue(self.bridge.complete('w1', output)['spoken'])

    def test_a_rejection_does_not_resend_a_layer(self):
        self.play_open()
        packet, out = self.play_wait('w1')
        flat = dict(out, performance={'segments': [{'speaker': 'Narrator', 'text': 'Dark.'}] +
                                      [{'speaker': 'Kit', 'text': 'Ooh.'}] * 3})   # quiet Kit speaks
        for _ in range(2):
            with self.assertRaises(InvalidChange):
                self.bridge.complete('w1', flat)
        self.bridge.abandon('w1')
        again, _ = self.play_wait('w2')
        self.assertNotIn('body', again['session_manifest'])
        self.assertIn('manifest_check', again)


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
