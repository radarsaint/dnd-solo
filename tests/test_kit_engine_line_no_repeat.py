"""Nagatha's clean-host review (Low): the engine's event sentence repeated Kit's narration. Kit
ended on "Roll initiative." and the engine's line after it said "Roll initiative." again.

A sentence of Kit's narration that the engine's line says word for word is said once, where the
engine says it: the engine's line is the authority and stays whole. Paraphrase is left alone.
Synthetic carcass room; dice pinned."""
import unittest

from runtime import kit_agent
from runtime.kit_agent import KitChatBridge
from test_kit_agent import RecordingModel
from test_kit_monster_initiative import Room


class EngineLineSaysItOnce(unittest.TestCase):
    def pry(self, narration):
        room = Room(self)
        bridge = KitChatBridge(room.runtime, room.adjudicator)
        packet = bridge.prepare('I pry the claw open.', 't1', one_pass=True)
        plan = RecordingModel().plan(packet['input']['private'])
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan.update(move='world_description', focus_actor='none', handles={'target': 'claw', 'act': 'pry'})
        for key in ('objective', 'visible_cue', 'player_opening'):
            plan['public_brief'].pop(key, None)
        plan['public_brief']['scope'] = 'call'
        speech = {'segments': [{'speaker': 'Narrator', 'text': narration}]}
        return room, bridge.complete('t1', {'decision': plan, 'performance': speech})

    def test_roll_initiative_is_said_once(self):
        room, result = self.pry('You kneel by the grey claw and work your fingers under the stiff talons. '
                                'Roll initiative.')
        self.assertEqual(result['spoken'].count('Roll initiative'), 1, result['spoken'])
        self.assertTrue(result['spoken'].rstrip().endswith('Roll initiative.'), 'the engine line ends the turn')
        self.assertIn('Narrator: You kneel by the grey claw', result['spoken'])
        self.assertEqual(room.state['combat']['status'], 'awaiting_initiative')

    def test_a_narration_that_was_only_the_repeat_leaves_no_empty_line(self):
        room, result = self.pry('You kneel by the grey claw and work your fingers under the stiff talons.')
        self.assertEqual(result['spoken'].count('Roll initiative'), 1)
        for line in result['spoken'].split('\n'):
            self.assertTrue(line.split(': ', 1)[-1].strip(), result['spoken'])


class Helper(unittest.TestCase):
    def test_only_exact_sentences_of_the_engine_line_drop(self):
        spoken = 'Narrator: The claw gives. Roll initiative!\nKit: Well. Roll initiative.'
        out = kit_agent.without_engine_sentences(spoken, 'Two centipedes boil out. Roll initiative.')
        self.assertEqual(out, 'Narrator: The claw gives.\nKit: Well.')
        self.assertEqual(kit_agent.without_engine_sentences('Narrator: Roll initiative.', 'Roll initiative.'), '')
        self.assertEqual(kit_agent.without_engine_sentences('Narrator: Initiative, now.', 'Roll initiative.'),
                         'Narrator: Initiative, now.')


if __name__ == '__main__':
    unittest.main()
