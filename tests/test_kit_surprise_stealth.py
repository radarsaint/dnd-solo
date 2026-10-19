"""Nagatha's clean-host review: surprise ignored the ambusher's Stealth. A room trigger with a flat
``surprise: {"dc": 15}`` surprised Nik although the ambusher's stat block gives Stealth -4 (its best
roll, 20 - 4 = 16, is below Nik's passive Perception 19 with his shield in hand).

The rule (Brendon): each ambusher's Stealth check against the PC's passive Perception; the actor
wins ties, so a Stealth total >= the passive goes unnoticed, and the PC is surprised only if he
notices none of them. A known Stealth (the trigger's own bonus, else the stat block's) is rolled;
a flat dc stands in only for an ambusher whose Stealth is unknown.

Synthetic: the carcass fixture, centipedes given Stealth -4. Dice pinned."""
import unittest

from runtime import kit_triggers
from test_kit_monster_initiative import ROLL, Room, carcass


def clumsy(dc=15, stealth=-4):
    source = carcass()
    source['triggers'][0]['surprise'] = {'dc': dc}
    for key in ('centipede_a', 'centipede_b'):
        source['actors'][key]['stat_block']['stealth'] = stealth
    return source


class StealthAgainstPassivePerception(unittest.TestCase):
    def fire(self, source, npc_roll, held=None):
        room = Room(self, source=source, npc_roll=lambda: npc_roll)
        if held is not None:
            room.runtime.set_pc_state(held=held)
        room.act('I roll the carcass over.', ROLL)
        return room

    def test_a_known_stealth_is_rolled_not_the_flat_dc(self):
        room = self.fire(clumsy(), npc_roll=10)  # 10 - 4 = 6 against passive 14
        self.assertNotIn('pc', room.state['combat']['surprised'])

    def test_nagathas_case_pp_19_against_stealth_minus_4_is_never_surprised(self):
        room = self.fire(clumsy(), npc_roll=20, held=['Sentinel Shield'])  # 20 - 4 = 16 < 19
        self.assertNotIn('pc', room.state['combat']['surprised'])

    def test_the_actor_wins_ties(self):
        room = self.fire(clumsy(stealth=-6), npc_roll=20)  # 20 - 6 = 14 = passive 14: unnoticed
        self.assertIn('pc', room.state['combat']['surprised'])

    def test_one_noticed_ambusher_means_no_surprise(self):
        source = clumsy()
        source['actors']['centipede_a']['stat_block']['stealth'] = 10  # 20 + 10 beats 14
        room = self.fire(source, npc_roll=20)  # centipede_b: 20 - 4 = 16 also beats 14
        self.assertIn('pc', room.state['combat']['surprised'])
        source['actors']['centipede_b']['stat_block']['stealth'] = -10  # 20 - 10 = 10 < 14
        room = self.fire(source, npc_roll=20)
        self.assertNotIn('pc', room.state['combat']['surprised'])

    def test_the_flat_dc_stands_in_only_for_an_unknown_stealth(self):
        source = carcass()
        source['triggers'][0]['surprise'] = {'dc': 15}
        room = self.fire(source, npc_roll=1)  # no stealth on the stat block: DC 15 >= 14
        self.assertIn('pc', room.state['combat']['surprised'])

    def test_the_trace_names_each_stealth_and_the_passive(self):
        source = clumsy()
        state = {'roll_seed': 's', 'actors': {}}
        surprised, trace = kit_triggers.pc_surprised(source, state, 1, source['triggers'][0], 19,
                                                     npc_roll=lambda: 20)
        self.assertFalse(surprised)
        self.assertIn('centipede_a stealth d20 20 + -4 = 16', trace)
        self.assertIn('passive Perception 19', trace)


if __name__ == '__main__':
    unittest.main()
