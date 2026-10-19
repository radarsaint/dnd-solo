"""A pending ruling never crashes a turn (Nagatha's #97 re-review, p2b.py: 'I peer down the
stair into the hall.' fell through every route to the physical-ruling refusal and raised out of
the bridge). Two halves: a look or listen with no physical verb is never a physical ruling, in
any room; and the bridge has one host-safe entry, try_prepare, that turns any pending ruling
into a structured result (the CLI uses it). Rooms: the from-scratch crypt fixture and the
carcass room. No model; dice pinned."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_rooms
from runtime.kit_agent import UNSUPPORTED_RULING, KitChatBridge, PendingRuling, RoomAdjudicator
from runtime.state_context import Runtime
from test_kit_monster_initiative import Room
import fixture_sheets

ROOT = Path(__file__).resolve().parents[1]
CRYPT = ROOT / 'tests' / 'fixtures' / 'rooms' / 'crypt.json'
NIK = fixture_sheets.path(ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json')


def crypt_bridge(test, start='vestibule'):
    temp = tempfile.TemporaryDirectory()
    test.addCleanup(temp.cleanup)
    runtime = Runtime(Path(temp.name) / 'kit.sqlite')
    test.addCleanup(runtime.close)
    with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{7:032x}'):
        runtime.initialize(kit_rooms.check_room(json.loads(CRYPT.read_text())), start)
    runtime.set_player_sheet(json.loads(NIK.read_text()))
    return runtime, KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 1,
                                                           source=runtime.source()))


LOOKS = ('I peer down the arch into the nave.', 'I peer through the low arch.',
         'I listen at the arch.', 'I peer into the dark.', 'I listen.', 'I peer ahead.',
         'I listen down the passage for voices.')


class LooksAreNotPhysicalRulings(unittest.TestCase):
    def test_p2b_stair_peer_in_the_carcass_room(self):
        room = Room(self, start='stair')
        packet = KitChatBridge(room.runtime, room.adjudicator).prepare(
            'I peer down the stair into the hall.', 'a', one_pass=True)
        self.assertEqual(room.runtime.load()[1]['area'], 'stair')  # a look, not a move
        self.assertNotIn(UNSUPPORTED_RULING, json.dumps(packet))

    def test_looks_and_listens_in_a_from_scratch_crypt(self):
        for start in ('vestibule', 'nave'):
            for i, line in enumerate(LOOKS):
                with self.subTest(start=start, line=line):
                    runtime, bridge = crypt_bridge(self, start)
                    try:
                        bridge.prepare(line, f't{i}', one_pass=True)
                    except PendingRuling as exc:
                        self.fail(f'{line!r} from {start} raised a pending ruling: {exc}')
                    self.assertEqual(runtime.load()[1]['area'], start)


class TryPrepareNeverRaises(unittest.TestCase):
    def test_a_real_pending_ruling_becomes_a_result(self):
        runtime, bridge = crypt_bridge(self)
        out = bridge.try_prepare('I juggle three of the loose bricks.', 'j', one_pass=True)
        self.assertEqual(out['stage'], 'pending_ruling')
        self.assertFalse(out['committed'])
        self.assertTrue(out['message'])
        self.assertTrue(out.get('attempt_recorded'))

    def test_a_clarifying_ruling_becomes_a_result(self):
        runtime, bridge = crypt_bridge(self)
        out = bridge.try_prepare('I roll initiative: 14.', 'i', one_pass=True)
        self.assertEqual(out['stage'], 'pending_ruling')
        self.assertNotIn('attempt_recorded', out)

    def test_an_ordinary_turn_passes_through(self):
        runtime, bridge = crypt_bridge(self)
        out = bridge.try_prepare('I look around the room.', 'o', one_pass=True)
        self.assertNotEqual(out.get('stage'), 'pending_ruling')
        self.assertEqual(out['turn_id'], 'o')


if __name__ == '__main__':
    unittest.main()
