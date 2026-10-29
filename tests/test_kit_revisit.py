"""Revisits keep what changed. Reverse exits are explicit. Ids do not flip.

Go forward, kill, loot, open a door, go back two rooms, return. The change log
is what comes back, not the read-aloud, and a reload in the middle keeps it.
Synthetic text only.
"""
import json
import tempfile
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from runtime import kit_adventure, kit_save  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import Runtime  # noqa: E402

ROAD = ROOT / 'tests/fixtures/adventures/revisit_road.txt'
NIK = ROOT / 'tests/fixtures/characters/nik.json'


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


class Revisit(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'
        report = kit_adventure.ingest_adventure(self.db, text=ROAD.read_text(encoding='utf-8'))
        self.index = json.loads((kit_adventure.folder_for(self.db) / 'index.json').read_text(encoding='utf-8'))
        self.assertTrue(str(report['start_location']).startswith('scene:'), report['start_location'])
        self.started = start_session(self.db, NIK, room=report['start_room'], manifests=True)
        self.runtime = Runtime(self.db)
        self.addCleanup(self.runtime.close)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10),
                                    manifests=True)
        self.bridge.prepare('Yes.', one_pass=True)

    def _commit(self, line):
        packet = self.bridge.prepare(line, one_pass=True)
        body = self.runtime.pending_kit_turn(packet['turn_id'])['body']
        revision = self.runtime.load()[0]
        self.bridge.abandon(packet['turn_id'])
        self.runtime.commit(packet['turn_id'], revision, body['events'])
        return packet

    def _here(self):
        return self.runtime.source()['id']

    def test_forward_change_back_two_and_return(self):
        self._commit('I go to room 1.')
        self._commit('I go inside.')
        cave = self._here()
        self.assertIn('1', cave)
        self._commit('I go to room 2.')
        self._commit('I go inside.')
        niche = self._here()
        self._commit('I go to room 3.')
        self._commit('I go inside.')
        cell = self._here()
        self.assertNotEqual(cell, niche)
        state = self.runtime.load()[1]
        bandit = next(key for key, actor in state['actors'].items() if actor.get('name') == 'Bandit')
        revision = self.runtime.load()[0]
        self.runtime.commit('kill', revision, [{
            'type': 'actor_status', 'actor': bandit, 'status': 'dead',
            'evidence': 'The bandit falls and stays down.'}])
        revision = self.runtime.load()[0]
        self.runtime.commit('loot', revision, [{
            'type': 'place_change', 'change': 'loot', 'what': 'tin box',
            'evidence': 'The tin box is taken.'}])
        revision = self.runtime.load()[0]
        self.runtime.commit('door', revision, [{
            'type': 'place_change', 'change': 'door', 'what': 'shut door', 'detail': 'open',
            'evidence': 'The shut door is opened.'}])
        place = self.runtime.load()[1]['places'][cell]
        self.assertEqual(place['actors']['Bandit'], 'dead')
        self.assertEqual(place['status'], 'changed')
        self.assertTrue(place['trigger_spent'])
        # A mention of area 1 in the cell is not a way back.
        cell_loc = next(loc for loc in self.index['locations'].values() if loc.get('number') == '3')
        self.assertNotIn('open_road-1', [c['to'] for c in cell_loc['connections']])

        path = self.runtime.path
        self.runtime.close()
        fresh = Runtime(path)
        self.addCleanup(fresh.close)
        self.runtime = fresh
        self.bridge = KitChatBridge(fresh, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10),
                                    manifests=True)
        self.assertEqual(fresh.load()[1]['places'][cell]['actors']['Bandit'], 'dead')
        self.assertEqual(fresh.source()['id'], cell)
        self.assertEqual(fresh.load()[1]['actors'][bandit]['status'], 'dead')

        saved = kit_save.save(str(path), journal_mode='campaign')
        campaign = json.loads((Path(saved['folder']) / 'campaign.json').read_text(encoding='utf-8'))
        self.assertEqual(campaign['places'][cell]['actors']['Bandit'], 'dead')

        self._commit('I go back to room 2.')
        self._commit('I go inside.')
        self.assertEqual(self._here(), niche)
        self._commit('I go back to room 1.')
        self._commit('I go inside.')
        self.assertEqual(self._here(), cave)
        self._commit('I go back to the road opening.')
        road = self._here()
        self.assertNotEqual(road, cave)
        back = self._commit('I look around.')
        self.assertTrue(back['room_manifest'].get('cached'), back['room_manifest'])
        self.assertLess(_bytes(back), 12000)
        now = back.get('place_now') or {}
        self.assertTrue(now.get('narration', '').startswith("You're back"))
        self.assertFalse(now.get('trigger_fires'))
        self.assertNotIn('broken wheel', now.get('narration', '').lower())

        self._commit('I go inside.')
        self._commit('I go to room 1.')
        self._commit('I go inside.')
        self.assertEqual(self._here(), cave)
        self._commit('I go to room 2.')
        self._commit('I go inside.')
        self.assertEqual(self._here(), niche)
        self._commit('I go to room 3.')
        self.assertEqual(self._here(), cell)
        self.assertEqual(self.runtime.load()[1]['actors'][bandit]['status'], 'dead')
        again = self._commit('I look around the cell.')
        self.assertTrue(again['room_manifest'].get('cached'))
        self.assertLess(_bytes(again), 12000)
        place_now = again['place_now']
        self.assertTrue(place_now['narration'].startswith("You're back"))
        self.assertIn('Bandit is dead', place_now['narration'])
        self.assertIn('tin box', place_now['narration'])
        self.assertIn('open', place_now['narration'])
        self.assertNotIn('stands by a shut door', place_now['narration'])
        self.assertFalse(place_now['read_aloud'])
        self.assertFalse(place_now['trigger_fires'])
        self.assertNotIn('body', again['room_manifest'])


class Rules(unittest.TestCase):
    def test_a_mention_is_not_an_exit_and_a_repeat_is_only_when_the_book_says(self):
        text = (
            'PART 1: THE YARD\n\n'
            '1. Gate\n'
            '> You stand at a gate.\n'
            'The scouts in area 2 keep watch.\n'
            'Whenever the characters return, the bell rings again.\n'
            'A path leads to area 2.\n\n'
            '2. Yard\n'
            '> The yard is empty.\n'
            'The path leads back to area 1.\n'
        )
        index = kit_adventure.build_index(text)
        gate = index['locations']['yard-1']
        self.assertEqual([c['to'] for c in gate['connections']], ['yard-2'])
        self.assertNotIn('scouts in area 2', ' '.join(c['quote'] for c in gate['connections']).lower())
        room, _side = kit_adventure.draft_room(':memory:', 'yard-1', index, text)
        self.assertTrue(room.get('_repeatable'))

    def test_a_fled_creature_stays_fled_and_is_logged(self):
        from runtime import kit_scenes
        state = {'places': {}, 'actors': {'bandit': {'name': 'Bandit', 'status': 'alive', 'visible': True}}}
        kit_scenes.log_change(state, 'room-3', 'fled', 'Bandit', 'toward the road')
        self.assertEqual(state['places']['room-3']['actors']['Bandit'], 'fled')
        kit_scenes.leave_place(state, 'room-3')
        kit_scenes.enter_place(state, 'room-3')
        kit_scenes.apply_actors(state, {'id': 'room-3'})
        self.assertEqual(state['actors']['bandit']['status'], 'fled')
        view = kit_scenes.revisit_view(state, 'room-3')
        self.assertIn('fled', view['narration'])
        self.assertFalse(view['trigger_fires'])


if __name__ == '__main__':
    unittest.main()
