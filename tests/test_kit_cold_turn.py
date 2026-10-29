"""Cold-mount turn latency: near-miss word floors, roll_call form, a smaller opening
packet, custom-folder module discovery, tease.heard, the entry engine line, and a
host wall-clock log.

Corpus: the synthetic watchroom, carcass, and bunkroom fixtures, plus a room built in
the test. No published adventure text. Dice are pinned. No model.
"""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agenda, kit_campaign, kit_rooms
from runtime.kit_agent import (FEATURE_MIN_WORDS, FEATURE_MIN_SEGMENTS, KitChatBridge,
                               PRIVATE_INSTRUCTIONS, PerformanceRejected, check_scope, private_parts,
                               start_session)
from runtime.state_context import InvalidChange

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / 'tests/fixtures/rooms/watchroom.json'
BUNK = ROOT / 'tests/fixtures/rooms/bunkroom.json'
NIK = ROOT / 'tests/fixtures/characters/nik.json'
# Layered watchroom opening on main b136732 (after #199), before this change.
OPENING_PACKET_BEFORE = 58752


def _words(n):
    return ' '.join(['stone'] * n)


def _feature(n):
    return [{'speaker': 'Narrator', 'text': _words(n // 2)},
            {'speaker': 'Narrator', 'text': _words(n - n // 2)}]


def _feature_plan():
    return {'public_brief': {'scope': 'feature'}, 'table_presence': 'brief', 'focus_actor': 'none'}


def _playable_room():
    room = json.loads(WATCH.read_text(encoding='utf-8'))
    room.pop('fixture_only', None)
    room['id'] = 'synthetic-cold-folder-v1'
    return room


class WordFloorMargin(unittest.TestCase):
    def test_a_near_miss_under_the_feature_floor_is_not_rejected(self):
        # 77 words against the 80-word floor: a retry, not a flat reply.
        near = FEATURE_MIN_WORDS - 3
        self.assertGreaterEqual(near, FEATURE_MIN_WORDS - 5)
        note = check_scope(_feature(near), _feature_plan())
        self.assertTrue(note)
        self.assertIn(str(near), note)
        self.assertIn(str(FEATURE_MIN_WORDS), note)
        self.assertIsNone(check_scope(_feature(FEATURE_MIN_WORDS), _feature_plan()))

    def test_a_66_word_feature_passes_and_a_flat_one_still_fails(self):
        # Measured room entry: 66 words against the 80-word feature floor.
        self.assertTrue(check_scope(_feature(66), _feature_plan()))
        with self.assertRaisesRegex(InvalidChange, 'Feature scope was flat'):
            check_scope(_feature(65), _feature_plan())
        one = [{'speaker': 'Narrator', 'text': _words(66)}]
        with self.assertRaisesRegex(InvalidChange, str(FEATURE_MIN_SEGMENTS)):
            check_scope(one, _feature_plan())


class RollCallForm(unittest.TestCase):
    def test_a_normal_call_missing_cause_and_target_is_repaired(self):
        source = json.loads(WATCH.read_text(encoding='utf-8'))
        call = {'skill': 'Perception', 'mode': 'Normal'}
        kit_agenda.check_roll_call(call, source, {'area': 'landing', 'actors': {}})
        self.assertEqual(call['mode'], 'normal')
        self.assertEqual(call['target'], 'none')
        self.assertEqual(set(call['cause']), {'kind', 'ref', 'roots'})
        self.assertNotIn('dc', call)

    def test_an_unrepairable_call_names_the_copyable_form(self):
        with self.assertRaises(InvalidChange) as caught:
            kit_agenda.check_roll_call({'mode': 'advantage'}, {}, {'area': 'landing'})
        message = str(caught.exception)
        self.assertIn('{"skill": "perception", "mode": "normal"', message)
        self.assertIn('"mode": "advantage"', message)
        self.assertNotIn('"dc"', message)


class OpeningPacket(unittest.TestCase):
    def _packet(self, room):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        started = start_session(Path(folder.name) / 'kit.sqlite', str(NIK), room=room, manifests=True)
        packet = started['prepared']
        raw = json.dumps(packet, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return packet, len(raw), raw.decode('utf-8')

    def test_the_watchroom_opening_drops_procedures_it_does_not_use(self):
        packet, size, text = self._packet(WATCH)
        # docs/PLAY_CARD.md is embedded verbatim for the host. It is read once; it is not engine state.
        card_bytes = len(json.dumps(packet['play_card'], ensure_ascii=False).encode())
        engine = size - card_bytes
        self.assertLess(engine, OPENING_PACKET_BEFORE - 4000, size)
        self.assertLess(engine, 54000, size)
        for absent in ('DETAIL:', 'CLAIMS.', 'AGENDA.'):
            self.assertNotIn(absent, text, absent)
        self.assertIn('PC STATE:', text)
        self.assertIn('PLAN:', text)
        self.assertIn('personality_core', packet['session_manifest']['body'])
        self.assertIn('story_brief', json.dumps(packet['input']))
        # The first turn still has the obvious scene, not a trimmed room.
        self.assertIn('dm_only', packet['room_manifest']['body'])
        order = ('core', 'detail', 'claims', 'agenda', 'plan', 'attitudes', 'story', 'pc_state')
        self.assertEqual(''.join(private_parts()[name] for name in order), PRIVATE_INSTRUCTIONS)

    def test_a_claims_room_still_receives_the_claims_procedure(self):
        packet, _, text = self._packet(BUNK)
        self.assertIn('CLAIMS.', text)
        loaded = packet.get('loaded') or {}
        self.assertIn('CLAIMS.', loaded.get('instructions', ''))
        self.assertNotIn('CLAIMS.', packet['session_manifest']['body']['instructions'])


class ModuleDiscovery(unittest.TestCase):
    def test_json_suffix_case_a_room_file_and_a_manifest_entry_are_found(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        room = _playable_room()
        (root / 'Room.JSON').write_text(json.dumps(room), encoding='utf-8')
        found, blocked = kit_campaign.inspect_rooms(root)
        self.assertEqual(len(found), 1, blocked)
        self.assertEqual(found[0]['room_id'], room['id'])
        alone, _ = kit_campaign.inspect_rooms(root / 'Room.JSON')
        self.assertEqual(len(alone), 1)
        pack = root / 'pack'
        pack.mkdir()
        (pack / 'scene').mkdir()
        (pack / 'scene' / 'landing.room').write_text(json.dumps(room), encoding='utf-8')
        (pack / 'manifest.json').write_text(json.dumps({'rooms': ['scene/landing.room']}), encoding='utf-8')
        listed, blocked = kit_campaign.inspect_rooms(pack)
        self.assertEqual([item['room_id'] for item in listed], [room['id']], blocked)

    def test_a_sound_without_an_actor_mounts_and_a_broken_entry_names_the_form(self):
        room = _playable_room()
        room['areas']['landing']['tease']['heard'] = 'water dripping somewhere past the door'
        source = kit_rooms.check_room(room)
        heard = source['areas']['landing']['tease']['heard']
        self.assertEqual(heard, [{'actor': 'none', 'sound': 'water dripping somewhere past the door'}])
        room = _playable_room()
        room['areas']['landing']['tease']['heard'] = [{'sound': 'a chair creaking'}]
        source = kit_rooms.check_room(room)
        self.assertEqual(source['areas']['landing']['tease']['heard'][0]['actor'], 'none')
        room = _playable_room()
        room['areas']['landing']['tease']['heard'] = [{'actor': 'warden'}]
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            kit_rooms.check_room(room)
        message = ' '.join(caught.exception.problems)
        self.assertIn('{"actor": "warden", "sound":', message)
        self.assertIn('"actor": "none"', message)


class EntryEngineLine(unittest.TestCase):
    def test_the_engine_line_does_not_speak_the_held_layer(self):
        from test_kit_handoffs import plan_for
        from test_kit_monster_initiative import Room
        room = Room(self)
        bridge = KitChatBridge(room.runtime, room.adjudicator)
        packet = bridge.prepare(opening=True, one_pass=True, turn_id='open')
        plan = plan_for(packet)
        flat = {'segments': [{'speaker': 'Narrator', 'text': 'The hall is dark and still.'}]}
        with self.assertRaises(PerformanceRejected):
            bridge.complete('open', {'decision': plan, 'performance': flat})
        result = bridge.complete('open', {'decision': plan, 'performance': flat})
        self.assertTrue(result['engine_line'])
        spoken = result['spoken'].casefold()
        self.assertIn('basilisk', spoken)
        self.assertNotIn('coiling serpents', spoken)
        self.assertNotIn('pillars carved', spoken)


class AreaChangePacket(unittest.TestCase):
    def test_a_new_area_adds_only_that_area_and_stays_under_6kb(self):
        import sys
        sys.path.insert(0, str(ROOT / 'tests'))
        from test_kit_agent import RecordingModel
        from test_kit_room_review import Base, WATCH
        from test_kit_watchroom_stalls import landing
        from runtime.kit_agent import RoomAdjudicator
        case = Base()
        case.setUp()
        runtime = case.start(WATCH)
        bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10), manifests=True)
        opening = bridge.prepare(opening=True, one_pass=True, turn_id='open')
        plan = RecordingModel().plan(opening['input']['private'])
        plan.update(move='world_description', table_presence='quiet', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(scope='feature', reply_to='none')
        bridge.complete('open', {'decision': plan, 'performance': landing(), 'manifest': {
            'session': opening['session_manifest']['hash'], 'room': opening['room_manifest']['hash']}})
        revision, _ = runtime.load()
        runtime.commit('in', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'In.'}])
        packet = bridge.prepare('I look around the room.', 'inside', one_pass=True)
        raw = json.dumps(packet, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.assertLess(len(raw), 6000, len(raw))
        self.assertNotIn('body', packet['session_manifest'])
        self.assertNotIn('body', packet['room_manifest'])
        self.assertTrue(packet['session_manifest'].get('cached'))
        self.assertTrue(packet['room_manifest'].get('cached'))
        self.assertEqual(packet['room_manifest']['hash'], opening['room_manifest']['hash'])
        area = packet['area']
        self.assertEqual(area['id'], 'watchroom')
        hidden = area['dm_only']['unrevealed_facts']
        self.assertIn('chest_contents', hidden)
        self.assertIn('sealed letter', hidden['chest_contents']['text'])
        text = json.dumps(packet['session_manifest'])
        self.assertNotIn('personality_core', text)


# Watchroom replay, manifests on, json.dumps(ensure_ascii=False), main b5ddad74.
# T0 is the opening. T1-T8 are the per-turn packets that climbed on main.
MAIN_B5_TURN_BYTES = {
    'T1': 8504, 'T2': 9773, 'T3': 11928, 'T4': 10715,
    'T5': 14512, 'T6': 19828, 'T7': 16389, 'T8': 12624,
}


class EightTurnPackets(unittest.TestCase):
    def test_per_turn_packets_stay_at_or_under_main_and_do_not_climb(self):
        import sys
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / 'scripts'))
        import scripts.watchroom_replay as replay
        from runtime.kit_agent import RoomAdjudicator
        from runtime.kit_manifest import expand_session
        from runtime.state_context import Runtime
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'replay.sqlite'
        started = start_session(db, replay.NIK, room=replay.ROOM, manifests=True)
        runtime = Runtime(db)
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10), manifests=True)

        def nbytes(value):
            return len(json.dumps(value, ensure_ascii=False).encode('utf-8'))

        def expanded(packet):
            body = (packet.get('session_manifest') or {}).get('body')
            if not body or 'properties' in body.get('schema', {}):
                return packet
            packet = dict(packet)
            packet['session_manifest'] = dict(packet['session_manifest'], body=dict(body))
            packet['session_manifest']['body']['schema'] = expand_session(dict(body))['schema']
            return packet

        sizes = {}
        for turn in replay.TURNS:
            if turn['id'] not in set(MAIN_B5_TURN_BYTES) | {'T0'}:
                continue
            packet = started['prepared'] if turn.get('opening') else bridge.prepare(turn['line'], one_pass=True)
            if turn['id'] != 'T0':
                self.assertNotIn('loaded', packet, turn['id'])
                self.assertNotIn('body', packet['session_manifest'], turn['id'])
                sizes[turn['id']] = nbytes(packet)
            speech = {'segments': [
                {'speaker': speaker, 'text': text,
                 **({'reacts_to': (turn.get('line') or 'the landing')[:40]} if speaker == 'Kit' else {})}
                for speaker, text in turn['speech']]}
            decision = replay.kit_decision(expanded(packet), turn)
            output = {'decision': decision, 'performance': speech}
            if 'session_manifest' in packet:
                output['manifest'] = {'session': packet['session_manifest']['hash'],
                                      'room': packet['room_manifest']['hash']}
            bridge.complete(packet['turn_id'], output)
        self.assertEqual(set(sizes), set(MAIN_B5_TURN_BYTES))
        for turn_id, limit in MAIN_B5_TURN_BYTES.items():
            self.assertLessEqual(sizes[turn_id], limit, turn_id)
        # No climb: the eighth turn is not larger than the first, and the spread stays
        # inside one speech's worth of variation rather than the old multi-kilobyte trend.
        ordered = [sizes[turn_id] for turn_id in sorted(sizes, key=lambda name: int(name[1:]))]
        self.assertLessEqual(ordered[-1], ordered[0])
        self.assertLess(max(ordered) - min(ordered), 2500, ordered)


class HostLatencyLog(unittest.TestCase):
    def test_a_host_line_records_wall_clock_and_rejections(self):
        from runtime import kit_latency_log
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'kit.sqlite'
        row = kit_latency_log.record(db, turn_id='t1', message_at=1000.0, reply_at=1017.5, rejections=2,
                                     packet_bytes=50000)
        self.assertEqual(row['wall_s'], 17.5)
        self.assertEqual(row['rejections'], 2)
        hand = kit_latency_log.path_for(db)
        hand.write_text(hand.read_text(encoding='utf-8') +
                        '{"v":1,"turn_id":"t2","message_at":2000,"reply_at":2004,"rejections":0}\n',
                        encoding='utf-8')
        report = kit_latency_log.report(db)
        self.assertEqual(report['n'], 2)
        self.assertEqual(report['rejections'], 2)
        self.assertEqual(report['turns'][1]['wall_s'], 4.0)
        with self.assertRaises(ValueError):
            kit_latency_log.record(db, turn_id='t3', message_at=5, reply_at=4, rejections=0)
        with self.assertRaises(ValueError):
            kit_latency_log.record(db, turn_id='t3', message_at=1, reply_at=2, rejections=-1)


if __name__ == '__main__':
    unittest.main()
