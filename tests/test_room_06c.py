import json
import tempfile
import unittest
from pathlib import Path

from runtime.state_context import Runtime


FIXTURE = Path(__file__).parent / 'fixtures/level_01_area_06c.json'


class UktarlRoomTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db_path = Path(temp.name) / 'session.sqlite'
        self.runtime = Runtime(self.db_path)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')

    def test_the_player_sees_the_scene_but_not_its_secrets(self):
        view = self.runtime.player_view()
        visible = json.dumps(view).lower()
        self.assertEqual(len(view['actors']), 4)
        self.assertIn('mountain', visible)
        self.assertIn('stone tub', visible)
        for secret in ('doppelganger', 'marked', 'stone key', 'uktarl', 'harria',
                       'thieves', 'disguise', 'not a vampire'):
            self.assertNotIn(secret, visible)

        context = self.runtime.context()['dm_context']
        self.assertIn('fresco_key', context['dm_only']['unrevealed_facts'])
        self.assertIn('marked_deck', context['dm_only']['unrevealed_facts'])
        self.assertIn('key_function', context['dm_only']['unrevealed_facts'])
        self.assertTrue(any('DC 14' in rule for rule in context['dm_only']['room_rules']))
        self.assertIn('extort newcomers', context['level_context']['pressure_here'])
        self.assertIn('No Halaster contact', context['campaign_context']['relevance_here'])
        self.assertTrue(context['map_ref'].endswith('map-01.01-dungeon-level-dm.png'))
        self.assertEqual(context['dm_only']['actors']['uktarl']['dm_identity'], 'Uktarl Krannoc')
        self.assertTrue(any('conditional test snapshot' in c for c in context['constraints']))

    def test_discovery_needs_an_adjudicated_event_and_survives_restart(self):
        self.assertNotIn('stone key', json.dumps(self.runtime.player_view()))
        self.runtime.commit('inspect-fresco', 0, [{
            'type': 'reveal_fact', 'fact': 'fresco_key',
            'evidence': 'The character inspected the fresco and passed its DC 13 Perception check.'
        }])
        self.assertIn('stone key', json.dumps(self.runtime.player_view()))
        self.assertNotIn('area 14b', json.dumps(self.runtime.player_view()))
        self.runtime.close()
        self.runtime = Runtime(self.db_path)
        self.assertIn('stone key', json.dumps(self.runtime.player_view()))
        self.assertNotIn('area 14b', json.dumps(self.runtime.player_view()))


if __name__ == '__main__':
    unittest.main()
