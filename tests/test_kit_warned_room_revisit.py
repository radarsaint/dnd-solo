"""Engine-level transition integration; public host performance is tested in private trace."""
import unittest
from unittest.mock import patch
from runtime.kit_agent import KitChatBridge
from runtime import kit_timed_procedures
import test_kit_timed_procedures as helpers

class WarnedRevisit(unittest.TestCase):
    fight=helpers.TimedProcedures.fight
    save=helpers.TimedProcedures.save
    start=helpers.TimedProcedures.start
    round=helpers.TimedProcedures.round

    def setUp(self):
        text=helpers.TEXT+'A door leads back to area 2.\n'
        with patch.object(helpers,'TEXT',text):helpers.TimedProcedures.setUp(self)

    def step(self,action):
        bridge=KitChatBridge(self.r,world_response=True)
        packet=bridge.prepare(action,one_pass=True)
        if packet['stage']=='situation_required':
            req=packet['input'];self.assertFalse(req['actors'])
            self.assertEqual(len(req['established_warnings']),1)
            reading={'request_hash':req['request_hash'],'actors':{},
                'facts':{k:'visible' if f.get('visible') else 'private' for k,f in req['facts'].items()},
                'conditions':[],'unresolved':[]}
            bridge.complete(packet['turn_id'],{'decision':{'situation':reading},'performance':{'segments':[]}})
            packet=bridge.prepare(action,one_pass=True)
        self.assertEqual(packet['stage'],'one_pass')
        body=self.r.pending_kit_turn(packet['turn_id'])['body'];revision=self.r.load()[0]
        bridge.abandon(packet['turn_id'])
        self.r.commit(packet['turn_id'],revision,body['events'])

    def test_warning_and_previous_room_state_survive_playable_round_trip(self):
        self.start();f=self.fight();f.set_order(25);self.round(f);self.round(f)
        # Native event fixture closes the encounter before transition assertions.
        for key in self.guards:f.statuses[key]='dead';f.fight['hp'][key]=0
        f.check_over();self.save(f,'finished-fixture-combat')
        self.step('I go to the Command Room.')
        self.step('I go into the Command Room.')
        self.assertEqual(self.r.source()['id'],self.destination)
        self.r.commit('inspect-desk',self.r.load()[0],[{'type':'beat','tags':['inspected_desk'],
            'evidence':'Player examines the visible writing desk.'}])
        original=self.r.load()[1];known=list(original['known_facts'])
        self.step('I go to the Watch.')
        self.step('I go into the Watch.')
        self.step('I go to the Command Room.')
        self.step('I go into the Command Room.')
        state=self.r.load()[1]
        self.assertEqual(self.r.source()['id'],self.destination)
        self.assertEqual(len(kit_timed_procedures.warnings_here(state,self.destination)),1)
        self.assertTrue(set(known)<=set(state['known_facts']))
        self.assertGreaterEqual(state['room']['turns_in']['here'],original['room']['turns_in']['here'])
        self.assertEqual(state['source_situation'],original['source_situation'])
