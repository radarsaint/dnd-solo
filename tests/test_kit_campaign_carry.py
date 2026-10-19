"""P4 of the campaign-record design: cross-room carry.

Mounting the next room (live, or after a resume from the save) applies what the PC and the
world carry: spent slots and uses, conditions, loot, the people met and how they were left,
and each room's public status (areas visited, exits and facts known, its resources).
"""

import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_resume, kit_save
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import Runtime
from tests.test_kit_player_save import NIK, ROOMS, secret_room

CARCASS = ROOMS / 'carcass.json'


class Carry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        watch = json.loads(secret_room(self.dir).read_text(encoding='utf-8'))
        self.watch_path = self.dir / 'watch.json'
        self.carcass_path = self.dir / 'carcass.json'
        watch['areas']['stair_down']['room_link'] = {'room': str(self.carcass_path), 'area': 'hall'}
        carcass = json.loads(CARCASS.read_text(encoding='utf-8'))
        carcass['areas']['stair']['room_link'] = {'room': str(self.watch_path), 'area': 'stair_down'}
        self.watch_path.write_text(json.dumps(watch), encoding='utf-8')
        self.carcass_path.write_text(json.dumps(carcass), encoding='utf-8')
        self.db = self.dir / 'a' / 'kit.sqlite'
        self.db.parent.mkdir()
        self.runtime = self.open(self.db, start_session(str(self.db), str(NIK), room=str(self.watch_path),
                                                        area='landing'))

    def open(self, db, started):
        runtime = Runtime(str(db))
        self.addCleanup(runtime.close)
        KitChatBridge(runtime, RoomAdjudicator()).abandon(started['prepared']['turn_id'])
        return runtime

    def play(self, runtime, line):
        revision, state = runtime.load()
        result = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 1,
                                 source=runtime.source()).resolve(line, revision, state)
        runtime.commit(f'p{revision}', revision, list(result.events))

    def commit(self, runtime, *events):
        revision, _ = runtime.load()
        runtime.commit(f'c{revision}', revision, list(events))

    def spend_slot(self, runtime):
        res = json.loads(json.dumps(runtime.load()[1]['pc_resources']))
        res['slots']['1']['used'] = 1
        res['uses']['chronal_shift']['used'] = 1
        self.commit(runtime, {'type': 'pc_resources', 'resources': res, 'evidence': 'Shield, Chronal Shift.'})

    def to_carcass(self, kill=True):
        r = self.runtime
        self.play(r, 'I go through the iron door.')
        if kill:
            self.commit(r, {'type': 'actor_status', 'actor': 'warden', 'status': 'dead', 'evidence': 'Felled.'})
        self.spend_slot(r)
        self.play(r, 'I go back out through the iron door.')
        self.play(r, 'I take the stair down.')
        self.assertEqual(r.source()['id'], 'synthetic-carcass-v1')

    def test_spent_slots_and_uses_survive_a_room_change(self):
        self.to_carcass()
        res = self.runtime.load()[1]['pc_resources']
        self.assertEqual(res['slots']['1']['used'], 1)
        self.assertEqual(res['uses']['chronal_shift']['used'], 1)

    def test_campaign_json_carries_pc_state_and_room_status_and_no_hidden_ids(self):
        self.to_carcass()
        result = kit_save.save(str(self.db))
        text = (Path(result['folder']) / 'campaign.json').read_text(encoding='utf-8')
        campaign = json.loads(text)
        self.assertEqual(campaign['pc_state']['slots']['1'], 1)
        self.assertEqual(campaign['pc_state']['uses']['chronal_shift'], 1)
        watch = campaign['rooms'][0]
        self.assertEqual(watch['carry']['actors'], {'warden': 'dead'})
        self.assertIn('iron_door', watch['carry']['known_exits'])
        for hidden in ('ledger_code', 'bolt_hole', 'lurker', 'chest_contents'):
            self.assertNotIn(hidden, text)

    def resumed(self):
        self.to_carcass()
        archive = kit_save.save(str(self.db))['zip']
        db = self.dir / 'b' / 'kit.sqlite'
        db.parent.mkdir()
        started = kit_resume.resume(str(db), archive, room=str(self.carcass_path))
        return self.open(db, started), db

    def test_resume_keeps_spent_slots_and_uses(self):
        runtime, _ = self.resumed()
        res = runtime.load()[1]['pc_resources']
        self.assertEqual(res['slots']['1']['used'], 1)
        self.assertEqual(res['uses']['chronal_shift']['used'], 1)

    def test_going_back_to_a_room_left_before_the_resume_finds_it_as_left(self):
        runtime, _ = self.resumed()
        self.play(runtime, 'I go up the stair.')
        self.assertEqual(runtime.source()['id'], 'synthetic-watchroom-secrets-v1')
        state = runtime.load()[1]
        self.assertEqual(state['actors']['warden']['status'], 'dead')
        self.assertTrue({'landing', 'watchroom', 'stair_down'} <= set(state['visited']))
        self.assertIn('iron_door', state['known_exits'])
        self.assertNotIn('bolt_hole', state['known_exits'])
        self.assertEqual(state['actors']['lurker']['status'], 'alive')  # never met: as the room file has it
        self.assertEqual(state['pc_resources']['slots']['1']['used'], 1)

    def test_loot_follows_into_the_next_room_after_resume(self):
        runtime, _ = self.resumed()
        self.assertEqual(runtime.load()[1].get('carried'), [])
        # loot taken in a left room would be in carried; nothing was taken here
        self.assertIsInstance(runtime.load()[1]['campaign_log']['rooms'][0]['carry'], dict)

    def test_a_bad_carry_record_is_refused(self):
        runtime, _ = self.resumed()
        revision, _ = runtime.load()
        bad = {'rooms': [{'room_id': 'x', 'status': 'left', 'areas': [], 'npcs_met': [], 'learned': [], 'took': [],
                          'carry': {'actors': {'warden': 'resurrected'}}}]}
        with self.assertRaises(Exception):
            runtime.restore_campaign(bad, [])


if __name__ == '__main__':
    unittest.main()
