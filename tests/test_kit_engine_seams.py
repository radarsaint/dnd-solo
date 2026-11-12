"""Characterization of the host seams an engineering split may move but not rewrite.

These lock the bridge entry points and the pure helpers the CLI owns. They do not
lock packet contents the session-manifest work is changing, and they do not lock
roll parsing or message classification.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_appraise
from runtime.state_context import PROJECT_ROOT, InvalidChange

ROOT = PROJECT_ROOT
ROOM = 'tests/fixtures/rooms/watchroom.json'
SHEET = 'tests/fixtures/characters/example_pc.json'


def _run(*args):
    return subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *args],
                          cwd=ROOT, capture_output=True, text=True, check=False)


class PublicSeamTests(unittest.TestCase):
    def test_host_entry_names_stay_on_kit_agent(self):
        for name in ('main', 'start_session', 'persona_text', 'KitChatBridge', 'RoomAdjudicator',
                     'PendingRuling', 'prepare_turn', 'check_speech', 'check_plan'):
            self.assertTrue(callable(getattr(kit_agent, name)), name)
        for name in ('_cli_stamps', '_carry_lobby_question', '_lobby_question_delivery'):
            self.assertTrue(callable(getattr(kit_agent, name)), name)

    def test_help_names_the_host_commands(self):
        proc = _run('--help')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for command in ('start', 'prepare', 'complete', 'finish', 'persona', 'rehydrate'):
            self.assertIn(command, proc.stdout)

    def test_stamp_helper_accepts_epoch_seconds_and_names_a_bad_one(self):
        self.assertEqual(kit_agent._cli_stamps(['received_at=10', 'shown_at=10.5']),
                         {'received_at': 10.0, 'shown_at': 10.5})
        with self.assertRaises(InvalidChange) as raised:
            kit_agent._cli_stamps(['shown_at=noon'])
        self.assertIn('--stamp', str(raised.exception))
        self.assertIn('shown_at=noon', str(raised.exception))

    def test_lobby_delivery_leaves_a_packet_alone_when_nothing_is_pending(self):
        args = type('A', (), {'command': 'prepare', 'table_talk': False, 'db': '/no/such/kit.sqlite',
                              'turn_id': 't'})()
        result = {'turn_id': 't', 'stage': 'one_pass'}
        kit_agent._lobby_question_delivery(args, result)
        self.assertEqual(result, {'turn_id': 't', 'stage': 'one_pass'})

    def test_persona_text_is_the_bridge_core_plus_the_authority_note(self):
        text = kit_agent.persona_text()
        self.assertTrue(text.endswith(kit_agent.PERSONA_AUTHORITY_NOTE + '\n') or
                        text.rstrip('\n').endswith(kit_agent.PERSONA_AUTHORITY_NOTE))
        self.assertIn('Authority:', text)


class HostCommandTests(unittest.TestCase):
    def test_start_room_then_prepare_keeps_the_cli_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'kit.sqlite')
            started = _run('start', '--db', db, '--room', ROOM, '--sheet', SHEET, '--regression')
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assertEqual(started.stderr, '')
            payload = json.loads(started.stdout)
            self.assertEqual(payload['stage'], 'started')
            self.assertEqual(payload['room_id'], 'synthetic-watchroom-v1')
            self.assertEqual(payload['character']['name'], 'Wren')
            self.assertEqual(payload['prepared']['stage'], 'one_pass')
            self.assertTrue(payload['prepared']['turn_id'])
            action = Path(temp) / 'action.txt'
            action.write_text('I look at the iron door.', encoding='utf-8')
            prepared = _run('prepare', '--one-pass', '--db', db, '--action-file', str(action))
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            turn = json.loads(prepared.stdout)
            self.assertEqual(turn['stage'], 'one_pass')
            self.assertTrue(turn['turn_id'])
            self.assertNotIn('committed', turn)

    def test_appraise_price_fields_for_a_known_srd_item(self):
        result = kit_appraise.price('potion of healing')
        self.assertEqual(result['item'], 'Potion of Healing')
        self.assertEqual(result['final_price'], 70)
        self.assertEqual(result['list_price'], 70)
        self.assertEqual(result['mode'], 'buy')
        self.assertEqual(result['unit'], 'gp')
        self.assertIsNone(result['quantity'])
        self.assertTrue(result['basis'])
        self.assertEqual(kit_appraise.name_variants('potion of healing'),
                         ['potions of healing', 'potion of healing', 'healing potions', 'healing potion'])


if __name__ == '__main__':
    unittest.main()
