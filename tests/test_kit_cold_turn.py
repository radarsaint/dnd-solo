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

    def test_a_flat_feature_and_a_one_segment_near_miss_still_fail(self):
        flat = FEATURE_MIN_WORDS - 6  # outside the margin
        with self.assertRaisesRegex(InvalidChange, 'Feature scope was flat'):
            check_scope(_feature(flat), _feature_plan())
        one = [{'speaker': 'Narrator', 'text': _words(FEATURE_MIN_WORDS - 3)}]
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
        self.assertLess(size, OPENING_PACKET_BEFORE - 4000, size)
        self.assertLess(size, 54000, size)
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
