"""A verified source contract cannot retain an unaccounted-for combat actor.

Regression for the compiler producing a statted NPC from adjacent source text
when the host's validated opening names no such creature.
"""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_skim


def _room(path):
    room = {
        'id': 'source-test', 'starting_area': 'here',
        'areas': {'here': {'name': 'the trail'}}, 'facts': {}, 'exits': {},
        'actors': {
            'sentry': {'name': 'Sentry', 'location': 'here', 'status': 'hidden',
                       'visible': False, 'stat_block': {'srd': 'goblin'}},
            'guide': {'name': 'Guide', 'location': 'here', 'status': 'alive',
                      'visible': True, 'role': 'speaker'},
        },
        'triggers': [{'id': 'arrival', 'actors': ['sentry'],
                      'on': {'enter': 'here'}, 'starts_combat': True}],
    }
    path.write_text(json.dumps(room))


def _beat(people):
    return {'source_verified': True, 'place_noun': 'trail', 'people': people,
            'notice': {'holds': False}, 'source_contract': {'pressures': []},
            'discoveries': []}


class VerifiedOpeningActors(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'room.json'
        _room(self.path)

    def test_no_attested_actors_removes_statted_guesses_and_triggers(self):
        kit_skim._stamp_beat(self.path, _beat([]))
        room = json.loads(self.path.read_text())
        self.assertEqual(room['actors'], {})
        self.assertEqual(room['triggers'], [])
        self.assertEqual(room['_opening_people'], [])
        self.assertTrue(room['_opening_verified'])

    def test_only_named_actor_remains_even_if_another_has_stats(self):
        kit_skim._stamp_beat(self.path, _beat([{
            'id': 'guide', 'name': 'Guide', 'hidden': False,
            'kind': 'speaker', 'goal': 'The guide wants to talk.',
        }]))
        room = json.loads(self.path.read_text())
        self.assertEqual(list(room['actors']), ['guide'])
        self.assertEqual(room['triggers'], [])
        self.assertEqual(room['_opening_people'], ['guide'])


if __name__ == '__main__':
    unittest.main()
