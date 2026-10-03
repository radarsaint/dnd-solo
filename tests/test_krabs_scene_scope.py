"""KRABS §8 minimal fixture (docs/architecture/KRABS.md, "Fact Scope Across Scenes").

A globally scoped consequence made during a scene survives the scene's close and a fresh
projection (a new Runtime on the same database); a fact scoped only to scene A does not
reach a later scene B in the same room. §14 (source retrieval) stays parked: nothing here
retrieves source text."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime.state_context import FIRST_SCENE, InvalidChange, Runtime, canon_in_scope, current_scene
from test_kit_agent import FIXTURE

SOURCE = json.loads(FIXTURE.read_text())
FEASIBILITY = json.loads((Path(__file__).parent / 'fixtures/feasibility_room.json').read_text())


def canon(slot, fact, scope, public=True):
    return {'type': 'canon_entry', 'slot': slot, 'kind': 'appearance', 'fact': fact, 'basis': 'Kit, this scene.',
            'public': public, 'scope': scope, 'procedure': None, 'roots': [], 'choice': None, 'price': None,
            'evidence': 'Test: Kit establishes a detail.'}


class Scenes(unittest.TestCase):
    source, area, actor, room = SOURCE, 'area_06c', 'uktarl', 'area_06c'

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        self.runtime.initialize(copy.deepcopy(self.source), self.area)
        self.turn = 0

    def tearDown(self):
        self.runtime.close()

    def commit(self, *events):
        revision, _ = self.runtime.load()
        self.turn += 1
        return self.runtime.commit(f't{self.turn}', revision, list(events))

    def fresh(self):
        """A fresh projection: a new Runtime on the same database."""
        self.runtime.close()
        self.runtime = Runtime(self.path)
        return self.runtime.load()[1]

    def test_a_death_in_scene_a_stays_true_in_scene_b(self):
        self.assertEqual(current_scene(self.runtime.load()[1]), FIRST_SCENE)
        self.commit({'type': 'actor_status', 'actor': self.actor, 'status': 'dead',
                     'evidence': 'Test: the actor dies in scene A.'})
        closed = self.runtime.close_scene('The player leaves; scene A is over.')
        self.assertEqual(closed['scene'], 'scene-2')
        state = self.fresh()
        self.assertEqual(current_scene(state), 'scene-2')
        self.assertEqual(state['actors'][self.actor]['status'], 'dead')
        self.assertEqual(state['scenes_closed'], [{'scene': FIRST_SCENE, 'area': self.area}])
        with self.assertRaises(InvalidChange):  # dead stays dead
            self.commit({'type': 'actor_status', 'actor': self.actor, 'status': 'alive', 'evidence': 'Test.'})
        context = self.runtime.context()['dm_context']
        self.assertEqual(context['scene']['scene_id'], 'scene-2')
        self.assertEqual(context['dm_only']['actors'][self.actor]['status'], 'dead')

    def test_a_scene_a_only_fact_does_not_reach_scene_b_in_the_same_room(self):
        self.commit(canon(f'{self.room}/mood/this_scene', 'A cold draft gutters the candles tonight.', 'scene'),
                    canon(f'{self.room}/wall/crack', 'A long crack runs up the east wall.', 'location'))
        state = self.runtime.load()[1]
        self.assertIn(f'{self.room}/mood/this_scene', canon_in_scope(state))
        self.runtime.close_scene('Scene A ends.')
        state = self.fresh()
        self.assertEqual(state['area'], self.area)  # the same room
        here = canon_in_scope(state)
        self.assertNotIn(f'{self.room}/mood/this_scene', here)
        self.assertNotIn(f'{self.room}/mood/this_scene', state.get('canon') or {})
        self.assertIn(f'{self.room}/wall/crack', here)  # the location's own fact stays
        view = json.dumps(self.runtime.context(), ensure_ascii=False)
        self.assertNotIn('cold draft', view)
        self.assertIn('long crack', view)
        # Scene B may establish its own scene detail under the same slot; it is scene B's.
        self.commit(canon(f'{self.room}/mood/this_scene', 'The air is still and warm.', 'scene'))
        self.assertEqual(canon_in_scope(self.runtime.load()[1])[f'{self.room}/mood/this_scene']['scene'], 'scene-2')

    def test_closing_needs_the_open_scene_and_a_reason(self):
        revision, _ = self.runtime.load()
        with self.assertRaises(InvalidChange):
            self.runtime.commit('bad', revision, [{'type': 'scene_close', 'scene': 'scene-9', 'evidence': 'x'}])
        with self.assertRaises(InvalidChange):
            self.runtime.close_scene('  ')

    def test_a_state_from_before_scene_ids_is_in_its_first_scene(self):
        state = copy.deepcopy(self.runtime.load()[1])
        state.pop('scene_id')
        state['canon'] = {f'{self.room}/old/detail': {'scope': 'scene', 'area': self.area, 'fact': 'old',
                                                       'public': True, 'kind': 'detail'}}
        self.assertEqual(current_scene(state), FIRST_SCENE)
        self.assertIn(f'{self.room}/old/detail', canon_in_scope(state))


class ScenesInAnyRoom(Scenes):
    """Non-6c: the same contract in the feasibility room."""
    source, area, actor, room = FEASIBILITY, 'entry', 'sentry', 'entry'


if __name__ == '__main__':
    unittest.main()
