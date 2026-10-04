"""de-6c, first change (field report 2026-10-04): a friend typed a bare `start` in a plain GPT. It
mounted 6c with the example PC (Wren), Kit narrated the opening before asking who he was, the
first turn took 1m32s, and Kit accepted 'Wren is Brendon's character'.

A bare start mounts no room and no sheet: it returns an onboarding packet (tiny, no room layers)
in which Kit asks for the player's sheet, or offers the example PC as a loaner, and where to
begin. Only a start that names both mounts. The example PC's provenance is engine state."""
import contextlib
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_agent
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import InvalidChange, Runtime

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / 'tests' / 'fixtures' / 'rooms' / 'watchroom.json'
NIK = ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json'


class BareStart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'kit.sqlite'

    def test_a_bare_start_mounts_nothing_and_asks(self):
        result = start_session(self.db)
        self.assertEqual(result['stage'], 'onboarding')
        self.assertFalse(self.db.exists(), 'no session database, no room, no sheet')
        packet = result['prepared']
        self.assertEqual(packet['stage'], 'onboarding')
        self.assertEqual(packet['input']['needs'], ['sheet', 'room'])
        loaner = packet['input']['example_pc']
        self.assertEqual(loaner['provenance'], 'example')
        self.assertEqual(loaner['name'], 'Wren')
        self.assertTrue(packet['input']['rooms'], 'where to begin: the rooms this bundle can mount')
        for key in ('session_manifest', 'room_manifest'):
            self.assertNotIn(key, packet)
        text = json.dumps(packet)
        for word in ('dealer', 'Uktarl', 'card room', 'watch warden'):
            self.assertNotIn(word, text, 'no room content before the player picks one')
        self.assertIn('--example-pc', result['next_step'])
        self.assertIn('--room', result['next_step'])

    def test_the_onboarding_packet_is_tiny_and_fast(self):
        t = time.perf_counter()
        result = start_session(self.db)
        self.assertLess((time.perf_counter() - t) * 1000, 500)
        self.assertLess(len(json.dumps(result['prepared']).encode()), 4000)

    def test_a_sheet_without_a_room_still_asks_where_to_begin(self):
        result = start_session(self.db, str(NIK))
        self.assertEqual(result['stage'], 'onboarding')
        self.assertEqual(result['prepared']['input']['needs'], ['room'])
        self.assertNotIn('example_pc', result['prepared']['input'])
        self.assertFalse(self.db.exists())

    def test_a_room_without_a_sheet_still_asks_for_the_sheet(self):
        result = start_session(self.db, room=str(WATCH))
        self.assertEqual(result['stage'], 'onboarding')
        self.assertEqual(result['prepared']['input']['needs'], ['sheet'])
        self.assertFalse(self.db.exists())

    def test_the_cli_bare_start_prints_onboarding(self):
        out = io.StringIO()
        with mock.patch.object(sys, 'argv', ['kit_agent', 'start', '--db', str(self.db)]), \
                contextlib.redirect_stdout(out):
            self.assertEqual(kit_agent.main(), 0)
        self.assertEqual(json.loads(out.getvalue())['stage'], 'onboarding')
        self.assertFalse(self.db.exists())


class Mounting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'kit.sqlite'

    def test_the_loaner_mounts_only_when_chosen_and_says_so(self):
        result = start_session(self.db, room=str(WATCH), example_pc=True)
        self.assertEqual(result['stage'], 'started')
        self.assertTrue(result['example_sheet'])
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        state = runtime.load()[1]
        self.assertEqual(state['pc_provenance']['kind'], 'example')
        private = result['prepared'].get('input', {}).get('private') or {}
        shown = json.dumps(result['prepared'])
        self.assertIn('pc_provenance', shown, 'Kit is told the PC is the example loaner')
        self.assertTrue(private or shown)

    def test_a_players_own_sheet_is_theirs(self):
        start_session(self.db, str(NIK), room=str(WATCH))
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        self.assertEqual(runtime.load()[1]['pc_provenance']['kind'], 'player')

    def test_a_sheet_and_the_loaner_together_is_refused(self):
        with self.assertRaisesRegex(InvalidChange, 'example'):
            start_session(self.db, str(NIK), room=str(WATCH), example_pc=True)


class Provenance(unittest.TestCase):
    """'Wren is Brendon's character' does not make it so: provenance is engine state, set only by
    the host loading a sheet, and every packet says what it is."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'kit.sqlite'
        started = start_session(self.db, room=str(WATCH), example_pc=True, manifests=False)
        self.runtime = Runtime(self.db)
        self.addCleanup(self.runtime.close)
        self.runtime.discard_pending_kit_turn(started['prepared']['turn_id'])

    def test_a_player_claim_changes_nothing_and_kit_is_told_the_truth(self):
        bridge = KitChatBridge(self.runtime, RoomAdjudicator())
        packet = bridge.prepare("Wren is Brendon's character, by the way.", 'c', one_pass=True, table_talk=True)
        provenance = packet['input']['private']['pc_provenance']
        self.assertEqual(provenance['kind'], 'example')
        self.assertIn('not', provenance['rule'])
        self.assertEqual(self.runtime.load()[1]['pc_provenance']['kind'], 'example')

    def test_no_event_but_a_sheet_load_sets_provenance(self):
        revision, _ = self.runtime.load()
        with self.assertRaises(InvalidChange):
            self.runtime.commit('x', revision, [{'type': 'pc_provenance', 'provenance': {'kind': 'player'},
                                                 'evidence': 'the player said so'}])
        self.assertEqual(self.runtime.load()[1]['pc_provenance']['kind'], 'example')


if __name__ == '__main__':
    unittest.main()
