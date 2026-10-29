"""Host lifecycle (postmortem: opening pending, player said "Yes.", nothing committed).

While a turn waits, prepare stages nothing and records nothing; it answers turn_pending with
the exact complete command. The state lives in the save, so it survives a Python reset.
Watchroom fixture; no model."""
import json
import subprocess
import sys
import unittest

from runtime import kit_lifecycle
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from runtime.state_context import PROJECT_ROOT
from runtime.state_context import Runtime
from test_kit_manifests import Layers


def queued(runtime):
    return runtime.db.execute('SELECT COUNT(*) FROM queued_attempts').fetchone()[0]


class PendingOpening(Layers):
    def test_yes_on_a_pending_opening_then_complete_commits_it(self):
        packet, output = self.open_room()
        self.assertEqual(kit_lifecycle.status(self.runtime.path)['state'], 'ready')
        held = self.bridge.try_prepare('Yes.', one_pass=True)
        self.assertNotEqual(held['stage'], 'turn_pending')
        self.assertEqual(held['turn_id'], 'open')
        self.assertEqual(held['pending_kind'], 'opening')
        self.assertTrue(held['confirmation'])
        self.assertTrue(held['committed'])
        self.assertTrue(held['spoken'])
        self.assertEqual(queued(self.runtime), 0)          # "Yes." was not held as an attempt
        self.assertEqual(self.runtime.db.execute('SELECT COUNT(*) FROM kit_pending').fetchone()[0], 0)
        self.assertLess(len(json.dumps(held)), 4000)
        status = kit_lifecycle.status(self.runtime.path)
        self.assertEqual((status['state'], status['committed_turns']), ('playing', 1))
        self.assertIn('prepare --one-pass', status['next_command'])
        self.assertEqual(queued(self.runtime), 0)

    def test_the_pending_opening_survives_a_python_reset(self):
        packet, output = self.open_room()
        path = self.runtime.path
        self.runtime.close()                               # the host's Python went away
        fresh = Runtime(path)
        self.addCleanup(fresh.close)
        status = kit_lifecycle.status(path)
        self.assertEqual((status['state'], status['pending_turn_id']), ('ready', 'open'))
        bridge = KitChatBridge(fresh, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10), manifests=True)
        again = bridge.prepare(opening=True, one_pass=True, turn_id='open')   # packet_command: same turn
        self.assertEqual(again['turn_id'], 'open')
        gone = bridge.try_prepare("Let's go!", one_pass=True)
        self.assertTrue(gone['committed'])
        self.assertNotEqual(gone['stage'], 'turn_pending')
        self.assertTrue(gone['spoken'])
        self.assertEqual(kit_lifecycle.status(path)['state'], 'playing')

    def test_non_confirmations_stay_safe(self):
        self.open_room()
        for line in ('Yes, I kick the door down.', 'I draw my sword.', 'yes but what is the room like?',
                     'Begin by searching the bodies', 'no', 'Not yet.'):
            held = self.bridge.try_prepare(line, one_pass=True)
            self.assertEqual(held['stage'], 'turn_pending', line)
            self.assertFalse(held['confirmation'], line)
            self.assertIn('not recorded', held['instruction'])
        self.assertEqual(queued(self.runtime), 0)
        self.assertEqual(self.runtime.db.execute('SELECT COUNT(*) FROM kit_pending').fetchone()[0], 1)
        self.assertEqual(self.runtime.db.execute('SELECT COUNT(*) FROM kit_turns').fetchone()[0], 0)


class Confirmations(unittest.TestCase):
    def test_bare_go_aheads_match(self):
        for line in ('Yes.', 'yes', 'Yeah!', "Let's go", 'Let\u2019s begin.', 'Ok, begin', 'Start', 'ready',
                     "I'm ready!", 'Yes, let\'s do it.', 'Sure, go ahead', 'Dewit'):
            self.assertTrue(kit_lifecycle.is_confirmation(line), line)

    def test_deeds_and_questions_do_not(self):
        for line in ('', 'Yes, I open the door.', 'I go north', 'Go left', 'Start a fire', 'Yes?',
                     'What do I see?', 'no', 'wait', '"Yes," I tell the guard.', 'begin casting shield'):
            self.assertFalse(kit_lifecycle.is_confirmation(line), line)


class WaitingPlayerTurn(Layers):
    def test_a_confirmation_on_a_waiting_turn_points_at_complete(self):
        packet, output = self.open_room()
        self.bridge.complete('open', output)
        self.wait('w1')
        self.assertEqual(kit_lifecycle.status(self.runtime.path)['state'], 'awaiting_completion')
        held = self.bridge.try_prepare('Yes.', one_pass=True)
        self.assertEqual((held['stage'], held['pending_kind'], held['pending_turn_id']),
                         ('turn_pending', 'turn', 'w1'))
        self.assertIn('rehydrate', held['packet_command'])


class StatusCommand(Layers):
    def test_cli_status_reads_the_save(self):
        self.open_room()
        out = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'status', '--db', str(self.runtime.path)],
                             cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout
        status = json.loads(out)
        self.assertEqual((status['stage'], status['state']), ('status', 'ready'))
        self.assertIn('--turn-id open --input-file', status['next_command'])

    def test_unmounted(self):
        status = kit_lifecycle.status(self.folder / 'nothing.sqlite')
        self.assertEqual(status['state'], 'unmounted')
        self.assertFalse((self.folder / 'nothing.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
