"""PR0: time from the player's message to Kit's first playable line, split into host,
runtime, model, validation and retry, from stamps the host records and the bridge's own
clocks (docs/architecture/HOST_TIMING.md). Watchroom, dice pinned, no model."""
import json
import subprocess
import sys
import unittest

from runtime import kit_agent
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, turn_latency
from runtime.state_context import InvalidChange
from test_kit_room_review import ROOT, WATCH, Base

LANDING = {'segments': [
    {'speaker': 'Narrator', 'text': 'Lamplight leaks through the gap in the iron door and lays a thin bright stripe '
                                    'across the landing stones. Behind the door someone hums the same four notes '
                                    'over and over, and a chair creaks when he shifts.'},
    {'speaker': 'Narrator', 'text': 'A stair winds on down past the door into the dark. The post is awake, and the '
                                    'door stands ajar the width of a hand, the light inside steady and close, and nothing at all climbs the stair from below tonight, not yet anyway.'}]}


class HostStampedTiming(Base):
    def setUp(self):
        super().setUp()
        self.runtime = self.start(WATCH)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10))

    def plan(self, packet, **brief):
        from test_kit_agent import RecordingModel
        plan = RecordingModel().plan(packet['input']['private'])
        plan.update(move='world_description', table_presence='quiet', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none', story_basis='scene_state')
        plan['public_brief'].update({'reply_to': 'none', 'scope': 'feature', **brief})
        return plan

    def test_every_segment_of_the_turn_is_recorded(self):
        packet = self.bridge.prepare(opening=True, one_pass=True, host_stamps={'received_at': 1000.0})
        turn = packet['turn_id']
        flat = {'segments': [{'speaker': 'Narrator', 'text': 'A door, a light, a stair.'}]}  # under the floor: one retry
        try:
            self.bridge.complete(turn, {'decision': self.plan(packet), 'performance': flat},
                                 host_stamps={'model_sent_at': 1000.5, 'model_done_at': 1010.0})
        except InvalidChange:
            pass
        self.bridge.complete(turn, {'decision': self.plan(packet), 'performance': LANDING},
                             host_stamps={'model_sent_at': 1010.2, 'model_done_at': 1018.0})
        shown = self.runtime.kit_timing(turn)['committed_at'] + 0.4
        self.bridge.stamp(turn, shown_at=shown, received_at=shown - 18.4)
        latency = turn_latency(self.runtime.kit_timing(turn))
        self.assertAlmostEqual(latency['end_to_end_s'], 18.4, places=2)
        self.assertEqual(latency['model_s'], 17.3)            # both model trips: 9.5 + 7.8
        self.assertEqual(latency['retry_s'], 8.0)             # from the first reject's model_done to the last
        self.assertEqual(latency['rejects'], 1)
        self.assertGreater(latency['runtime_prepare_ms'], 0)
        self.assertGreater(latency['validation_ms'], 0)
        self.assertAlmostEqual(latency['shown_after_commit_s'], 0.4, places=2)
        self.assertGreater(latency['packet_bytes'], 10000)
        self.assertEqual(len(latency['output_bytes']), 2)    # one per attempt
        self.assertIn('host_s', latency)
        self.assertEqual(latency['missing'], [])

    def test_missing_host_stamps_are_named_not_guessed(self):
        packet = self.bridge.prepare(opening=True, one_pass=True)
        self.bridge.complete(packet['turn_id'], {'decision': self.plan(packet), 'performance': LANDING})
        latency = turn_latency(self.runtime.kit_timing(packet['turn_id']))
        self.assertIsNone(latency['end_to_end_s'])
        self.assertEqual(sorted(latency['missing']), ['model_done_at', 'model_sent_at', 'received_at', 'shown_at'])
        self.assertGreater(latency['runtime_prepare_ms'], 0)

    def test_a_stamp_must_be_a_time(self):
        packet = self.bridge.prepare(opening=True, one_pass=True)
        with self.assertRaises(InvalidChange):
            self.bridge.stamp(packet['turn_id'], shown_at='soon')
        with self.assertRaises(InvalidChange):
            self.bridge.stamp(packet['turn_id'], arrived='1.0')

    def test_the_cli_takes_the_stamps(self):
        db = self.folder / 'cli.sqlite'
        run = lambda *args: subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *args, '--db', str(db)],
                                           cwd=ROOT, capture_output=True, text=True)
        started = json.loads(run('start', '--example-pc', '--room', WATCH).stdout)
        turn = started['prepared']['turn_id']
        out = run('stamp', '--turn-id', turn, '--stamp', 'shown_at=1234.5')
        self.assertEqual(out.returncode, 0, out.stderr)
        timing = json.loads(run('timing').stdout)
        self.assertEqual(timing[-1]['host_stamps']['shown_at'], 1234.5)
        self.assertIn('latency', timing[-1])


if __name__ == '__main__':
    unittest.main()
