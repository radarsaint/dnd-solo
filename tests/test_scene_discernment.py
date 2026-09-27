import unittest

from runtime.scene_discernment import check_improv_read, discernment_candidates
from runtime.state_context import InvalidChange


class SceneDiscernmentTests(unittest.TestCase):
    def setUp(self):
        # A different story and cast: the same private read must work without
        # a dealer, a card game, or any of area 6c's authored performance data.
        self.context = {
            'scene': {'current_area': 'flooded_archive'},
            'level_context': {'active_here': True,
                              'pressure_here': 'The archive will flood when the bell rings.'},
            'campaign_context': {'active_here': False,
                                 'relevance_here': 'The royal succession has no contact here.'},
            'dm_only': {'actors': {
                'keeper': {'location': 'flooded_archive', 'status': 'alive',
                           'immediate_goal': 'Get the visitor to move the ledgers before the bell.',
                           'motive': 'Keep the records safe.'},
                'departed': {'location': 'upper_hall', 'status': 'alive',
                             'motive': 'Reach the stairs.'},
                'lost': {'location': 'flooded_archive', 'status': 'fled',
                         'motive': 'Escape.'},
            }},
        }
        self.read = {
            'player_bid': 'The player offers to carry the ledgers.',
            'story_anchor': 'level', 'story_basis': 'pressure_here', 'actor_ref': 'keeper',
            'actor_basis': 'immediate_goal',
            'connection': 'That offer advances the keeper’s urgent archive task.',
            'kit_choice': 'Kit values the creative help and lets the keeper react urgently.',
        }

    def test_live_story_and_actor_references_work_in_another_scene(self):
        candidates = discernment_candidates(self.context)
        self.assertEqual(candidates['story_bases'], {
            'none': ['none'], 'scene': ['scene_state'], 'level': ['pressure_here']})
        self.assertEqual(candidates['actor_bases'], {
            'none': ['none'], 'keeper': ['immediate_goal', 'motive']})
        check_improv_read(self.read, candidates)

    def test_inactive_threads_and_absent_actors_cannot_be_selected(self):
        candidates = discernment_candidates(self.context)
        for change, message in [
            ({'story_anchor': 'campaign'}, 'not active'),
            ({'story_basis': 'invented_plot'}, 'not established'),
            ({'actor_ref': 'departed'}, 'not available'),
            ({'actor_ref': 'lost'}, 'not available'),
            ({'actor_basis': 'none'}, 'not established'),
        ]:
            with self.subTest(change=change), self.assertRaisesRegex(InvalidChange, message):
                check_improv_read({**self.read, **change}, candidates)
        self.context['campaign_context']['active_here'] = True
        check_improv_read({**self.read, 'story_anchor': 'campaign',
                           'story_basis': 'relevance_here'},
                          discernment_candidates(self.context))

    def test_no_relevant_actor_or_story_is_a_valid_read(self):
        read = {**self.read, 'story_anchor': 'none', 'story_basis': 'none', 'actor_ref': 'none',
                'actor_basis': 'none',
                'connection': 'The player studies the room without addressing anyone.',
                'kit_choice': 'Kit describes what is visible and gives the player room.'}
        check_improv_read(read, discernment_candidates(self.context))


if __name__ == '__main__':
    unittest.main()
