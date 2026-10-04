"""Room traps (runtime/kit_traps.py) run on-engine: a step trap springs to a roll_call for the
player's save and lands the source's damage; a trap spotted by passive Perception is
stepped around and can be jammed; a reset-on-its-own trap on a lid fires each time it is
opened; tools need a stated roll. Synthetic rooms; every die pinned or stated."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_handoff, kit_rooms, kit_traps
from runtime.kit_agent import INTERSTITIAL_KIND, PendingRuling, RoomAdjudicator
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
NIK = ROOT / 'tests/fixtures/characters/nik.json'   # passive Perception 14


def trap_room(detect_dc=None, chest_reset='auto'):
    plate = {'id': 'scree_slide', 'on': {'step': 'ledge'}, 'feature': 'loose_scree',
             'effect': {'save': 'dex', 'dc': 12, 'damage': [{'dice': '3d6', 'type': 'bludgeoning'}],
                        'half_on_success': True},
             'disarm': [{'method': 'jam', 'with': 'a pitoned rope'}], 'reset': 'once',
             'reveal': 'The scree under your boots lets go.', 'spotted': 'The scree ahead sits wrong; you stop short.'}
    if detect_dc is not None:
        plate['detect'] = {'skill': 'perception', 'dc': detect_dc}
    return {
        'id': 'trap-test-quarry', 'source_ref': 'synthetic quarry', 'starting_area': 'cut',
        'areas': {'cut': {'name': 'Quarry cut', 'called': 'the cut'},
                  'ledge': {'name': 'Scree ledge', 'called': 'the ledge'}},
        'exits': {'up': {'name': 'the scree path', 'areas': ['cut', 'ledge'], 'secret': False,
                         'labels': {'cut': 'A scree path climbs to a ledge.', 'ledge': 'The path back down.'}}},
        'facts': {
            'loose_scree': {'area': 'ledge', 'visible': False, 'text': 'The scree on the ledge is ready to slide.',
                            'handling': {'nouns': ['scree']}},
            'chest': {'area': 'cut', 'visible': True, 'text': 'A tin chest sits on a block of stone.',
                      'handling': {'nouns': ['chest', 'lid'], 'move': 'The lid comes up.', 'look': 'Tin, dented, latched.'}},
            'needle': {'area': 'cut', 'visible': False, 'text': 'A spring needle in the lock.'}},
        'actors': {}, 'resources': {},
        'traps': [plate, {'id': 'chest_needle', 'on': {'open': 'chest'}, 'feature': 'needle',
                          'effect': {'damage': [{'dice': '1d4', 'type': 'piercing'}]},
                          'disarm': [{'method': 'thieves_tools', 'dc': 15}], 'reset': chest_reset,
                          'reveal': 'A needle snaps out of the lock.'}],
    }


class Quarry:
    def __init__(self, test, room):
        temp = tempfile.TemporaryDirectory()
        test.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        test.addCleanup(self.runtime.close)
        with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{7:032x}'):
            self.runtime.initialize(room, room['starting_area'])
        self.runtime.set_player_sheet(json.loads(NIK.read_text()))
        self.adjudicator = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=self.runtime.source())

    def act(self, action):
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(action, revision, state)
        self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    @property
    def state(self):
        return self.runtime.load()[1]


class TrapSchema(unittest.TestCase):
    def test_a_sound_room_has_no_trap_problems_and_each_break_is_named(self):
        self.assertEqual(kit_traps.trap_problems(trap_room(13)), [])
        bad = trap_room()
        bad['traps'][0]['effect']['dc'] = None                 # a save with no DC and no needs_dc flag
        bad['traps'][1]['on'] = {'stare': 'chest'}             # no such kind
        bad['traps'][1]['disarm'] = [{'method': 'prayer'}]     # no such method
        problems = ' | '.join(kit_traps.trap_problems(bad))
        for named in ('trap scree_slide: a save or check needs', 'trap chest_needle: on is one of',
                      'trap chest_needle: disarm method'):
            self.assertIn(named, problems)

    def test_a_trap_that_breaks_the_schema_stops_the_mount(self):
        bad = trap_room()
        bad['traps'][0]['effect']['damage'] = [{'dice': 'lots', 'type': 'bludgeoning'}]
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            kit_rooms.check_room(bad, 'quarry')
        self.assertIn('trap scree_slide: damage is a list', str(caught.exception))

    def test_object_stats_follow_the_srd_table(self):
        self.assertEqual(kit_traps.object_stats({'material': 'wood', 'size': 'small', 'resilient': True}), (15, 10))
        self.assertEqual(kit_traps.object_stats({'material': 'iron', 'size': 'medium'}), (19, 4))
        self.assertEqual(kit_traps.average('3d6'), 10)
        self.assertEqual(kit_traps.average('2d10+2'), 13)


class TrapsInPlay(unittest.TestCase):
    def test_a_step_trap_springs_to_a_roll_call_and_lands_the_source_damage(self):
        quarry = Quarry(self, trap_room(detect_dc=17))         # passive 14 misses it
        result = quarry.act('I climb the scree path to the ledge.')
        self.assertEqual(result.kind, INTERSTITIAL_KIND)
        self.assertIn('Dexterity', result.public_event)
        self.assertNotIn('12', result.public_event)            # the DC stays behind the screen
        self.assertEqual(quarry.state['trap_save']['trap'], 'scree_slide')
        handoff = kit_handoff.classify(result.kind, {}, {}, {}, quarry.state)
        self.assertEqual(handoff['type'], 'roll_call')
        with self.assertRaises(PendingRuling):                  # no roll in the input: nothing commits
            quarry.adjudicator.resolve('I brace myself.', *quarry.runtime.load())
        landed = quarry.act('Dexterity save: 1d20 (4) + 2 = 6')
        self.assertIn('10 damage', landed.public_event)
        self.assertEqual(quarry.state['hazard_damage'], 10)
        self.assertEqual(quarry.state['traps']['scree_slide']['status'], 'spent')
        self.assertIn('loose_scree', quarry.state['known_facts'])
        self.assertNotIn('trap_save', quarry.state)

    def test_a_good_save_halves_it(self):
        quarry = Quarry(self, trap_room(detect_dc=17))
        quarry.act('I climb the scree path to the ledge.')
        landed = quarry.act('Dexterity save: 1d20 (15) + 2 = 17')
        self.assertIn('5 damage', landed.public_event)

    def test_a_spotted_trap_is_stepped_around_and_can_be_jammed(self):
        quarry = Quarry(self, trap_room(detect_dc=13))         # passive 14 sees it
        result = quarry.act('I climb the scree path to the ledge.')
        self.assertNotEqual(result.kind, INTERSTITIAL_KIND)
        self.assertIn('stop short', result.public_event)
        self.assertEqual(quarry.state['traps']['scree_slide']['status'], 'found')
        jammed = quarry.act('I jam the scree in place with a pitoned rope.')
        self.assertIn('will not go off', jammed.public_event)
        self.assertEqual(quarry.state['traps']['scree_slide']['status'], 'disarmed')

    def test_a_lid_trap_that_resets_fires_each_time_and_tools_need_a_roll(self):
        quarry = Quarry(self, trap_room())
        first = quarry.act('I open the chest.')
        self.assertIn('needle', first.public_event.lower())
        dealt = quarry.state['hazard_damage']
        self.assertEqual(dealt, 2)
        self.assertEqual(quarry.state['traps']['chest_needle']['status'], 'armed')   # reset: auto
        with self.assertRaises(PendingRuling) as caught:
            quarry.adjudicator.resolve("I disarm the chest's needle with thieves' tools.", *quarry.runtime.load())
        self.assertIn('Roll', str(caught.exception))
        done = quarry.act("I disarm the chest's needle with thieves' tools. 1d20 (12) + 7 = 19")
        self.assertIn('disarmed', done.public_event)
        quarry.act('I open the chest.')
        self.assertEqual(quarry.state['hazard_damage'], dealt)   # disarmed: nothing more

    def test_a_trap_set_once_stays_spent(self):
        quarry = Quarry(self, trap_room(chest_reset='once'))
        quarry.act('I open the chest.')
        quarry.act('I open the chest.')
        self.assertEqual(quarry.state['hazard_damage'], 2)
        self.assertEqual(quarry.state['traps']['chest_needle']['status'], 'spent')


if __name__ == '__main__':
    unittest.main()
