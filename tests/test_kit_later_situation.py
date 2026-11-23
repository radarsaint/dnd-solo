"""Later-source interpretation: no handcrafted room goals and no opening fixture."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import kit_adventure,kit_situation,kit_lifecycle
from runtime.kit_agent import KitChatBridge,RoomAdjudicator,start_session
from runtime.state_context import Runtime,InvalidChange

LOCAL='Two goblins guard these windows.'
REMOTE='Commander Venn posted the sentries, but remains in the distant command room.'
CONDITION='If a visitor gives the agreed password, the sentries let them pass.'
SOURCE=('1. Entry Stair\n> A lantern burns beside the entry stair.\nA passage leads to area 2.\n'
        '2. Upper Watch\n> Narrow windows overlook the outer stair.\n'+LOCAL+'\n'+REMOTE+'\n'+CONDITION+'\n'
        '3. Command Room\n> A writing desk stands beside the far door.\n')

class LaterSituation(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/'kit.sqlite'
        kit_adventure.import_adventure(self.db,text=SOURCE)
        index,_=kit_adventure._load(self.db)
        self.key=next(k for k,l in index['locations'].items() if 'Upper Watch' in l['name'])
        self.room=kit_adventure.compile_location(self.db,self.key,neighbours=False)['room']
        self.before=Path(self.room).read_bytes()
        self.packet=start_session(str(self.db),str(Path('tests/fixtures/characters/nik.json')),room=self.room,world_response=True)
        self.runtime=Runtime(self.db);self.addCleanup(self.runtime.close)
        self.bridge=KitChatBridge(self.runtime,RoomAdjudicator(),world_response=True)

    def quote(self,req,sentence):
        text=req['units']['local']['text']
        return {'unit':'local','quote':sentence,'offset':req['units']['local']['span'][0]+text.index(sentence)}

    def reading(self):
        req=self.packet['input']
        actors={}
        for k,a in req['actors'].items():
            is_guard='goblin' in a['name'].lower()
            actors[k]={'presence':'present' if is_guard else 'mentioned',
                       'goal':'Defend this watch position while respecting the password arrangement.' if is_guard else '',
                       'basis':'inferred' if is_guard else 'unknown',
                       'evidence':[self.quote(req,LOCAL if is_guard else REMOTE)]}
        return {'request_hash':req['request_hash'],'actors':actors,
                'facts':{k:'visible' if 'Narrow windows' in f['text'] else 'private' for k,f in req['facts'].items()},
                'conditions':[self.quote(req,CONDITION)],'unresolved':[]}

    def output(self,reading=None):
        return {'decision':{'situation':reading or self.reading()},'performance':{'segments':[]}}

    def test_normal_later_start_requests_source_interpretation(self):
        self.assertEqual(self.packet['stage'],'situation_required',self.packet)
        self.assertIn(CONDITION,self.packet['input']['units']['local']['text'])
        self.assertNotIn('Commander Venn',json.dumps(self.packet.get('spoken','')))
        self.assertEqual(Path(self.room).read_bytes(),self.before)

    def test_interpretation_supplies_goals_and_excludes_mentioned_authority(self):
        self.bridge.complete(self.packet['turn_id'],self.output())
        source=self.runtime.source();state=self.runtime.load()[1]
        self.assertEqual(len(source['actors']),2)
        self.assertTrue(all(a['goal_authority']=='inferred' for a in source['actors'].values()))
        self.assertEqual(set(source['actors']),set(state['actors']))
        self.assertFalse(state['room']['turns_in'])
        for key,actor in state['actors'].items():
            for field in ('immediate_goal','motive','goal_authority','goal_evidence'):
                self.assertEqual(actor[field],source['actors'][key][field])
        self.assertEqual(state['source_situation']['conditions'],self.reading()['conditions'])
        self.assertEqual(Path(self.room).read_bytes(),self.before)

    def test_restart_and_exact_replay_preserve_interpretation(self):
        output=self.output();accepted=self.bridge.complete(self.packet['turn_id'],output)
        self.runtime.close();self.runtime=Runtime(self.db);self.addCleanup(self.runtime.close)
        self.bridge=KitChatBridge(self.runtime,world_response=True)
        result=self.bridge.complete(self.packet['turn_id'],output)
        self.assertTrue(result['already_committed'])
        self.assertEqual(result['revision'],accepted['revision'])
        for actor in self.runtime.load()[1]['actors'].values():
            self.assertEqual(actor['goal_authority'],'inferred')
            self.assertTrue(actor['goal_evidence'])
        self.assertEqual(kit_lifecycle.status(self.db)['state'],'situation_ready')
        self.assertTrue(kit_lifecycle.status(self.db)['resume_entry'])

    def test_false_quote_or_source_revision_changes_nothing(self):
        for change in ('quote','hash','offset'):
            reading=self.reading();before=copy.deepcopy(self.runtime.load())
            if change=='quote':reading['conditions'][0]['quote']='If someone pays, the guards surrender.'
            if change=='hash':reading['request_hash']='wrong'
            if change=='offset':reading['conditions'][0]['offset']+=1
            with self.subTest(change=change),self.assertRaises(InvalidChange):
                self.bridge.complete(self.packet['turn_id'],self.output(reading))
            self.assertEqual(self.runtime.load(),before)

    def test_clipped_condition_cannot_be_certified(self):
        reading=self.reading();e=reading['conditions'][0]
        clipped='the sentries let them pass.'
        e['offset']+=e['quote'].index(clipped);e['quote']=clipped
        with self.assertRaises(InvalidChange):self.bridge.complete(self.packet['turn_id'],self.output(reading))

    def test_no_unaccounted_or_invented_actor(self):
        for add in (True,False):
            reading=self.reading()
            if add:reading['actors']['invented']=copy.deepcopy(next(iter(reading['actors'].values())))
            else:reading['actors'].pop(next(iter(reading['actors'])))
            with self.assertRaises(InvalidChange):self.bridge.complete(self.packet['turn_id'],self.output(reading))

    def test_acceptance_failure_is_atomic(self):
        before=copy.deepcopy(self.runtime.load())
        with patch.object(self.runtime,'_apply',side_effect=RuntimeError('injected interruption')):
            with self.assertRaises(RuntimeError):self.bridge.complete(self.packet['turn_id'],self.output())
        self.assertEqual(self.runtime.load(),before)
        self.assertTrue(self.runtime.pending_kit_turn(self.packet['turn_id']))
        self.bridge.complete(self.packet['turn_id'],self.output())
        self.assertEqual(len(self.runtime.source()['actors']),2)

    def test_existing_source_files_remain_immutable(self):
        request=kit_situation.request(self.runtime)
        reading=self.reading()
        self.bridge.complete(self.packet['turn_id'],self.output(reading))
        self.assertEqual(request['request_hash'],kit_situation.request(self.runtime)['request_hash'])
        self.assertEqual(Path(self.room).read_bytes(),self.before)

    def test_initial_visibility_corrections_require_evidence_and_persist(self):
        reading=self.reading();guards=[k for k in reading['actors'] if 'goblin' in k]
        for key,visibility in zip(guards,('unperceived','visible')):
            reading['actors'][key].update(visibility=visibility,visibility_evidence=[self.quote(self.packet['input'],LOCAL)])
        self.bridge.complete(self.packet['turn_id'],self.output(reading))
        state=self.runtime.load()[1]
        self.assertFalse(state['actors'][guards[0]]['visible'])
        self.assertTrue(state['actors'][guards[1]]['visible'])
        self.assertEqual(state['actors'][guards[1]]['status'],'alive')
        self.runtime.close();self.runtime=Runtime(self.db);self.addCleanup(self.runtime.close)
        self.assertFalse(self.runtime.source()['actors'][guards[0]]['visible'])
        self.assertTrue(self.runtime.load()[1]['actors'][guards[1]]['visible'])
        self.assertEqual(Path(self.room).read_bytes(),self.before)

    def test_unsupported_or_unattested_visibility_is_rejected(self):
        for visibility,evidence in [('visible',[]),('guessed',[]),('unperceived',[{'unit':'local','quote':'Invented hiding.','offset':0}])]:
            reading=self.reading();key=next(iter(reading['actors']))
            reading['actors'][key].update(visibility=visibility,visibility_evidence=evidence)
            before=copy.deepcopy(self.runtime.load())
            with self.assertRaises(InvalidChange):self.bridge.complete(self.packet['turn_id'],self.output(reading))
            self.assertEqual(self.runtime.load(),before)
