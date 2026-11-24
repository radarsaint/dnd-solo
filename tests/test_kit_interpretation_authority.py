"""Authentic quotations do not confer player-discovery or placement authority."""
import copy
import json
import unittest
import contextlib
import io
from unittest.mock import patch
import test_kit_later_situation as helpers
from runtime import kit_scene_contract, kit_combat, kit_agent
from runtime.state_context import InvalidChange


class Authority(unittest.TestCase):
    setUp=helpers.LaterSituation.setUp
    quote=helpers.LaterSituation.quote
    reading=helpers.LaterSituation.reading
    output=helpers.LaterSituation.output

    def test_normal_cli_start_and_bridge_enable_source_reading_without_a_flag(self):
        db=self.db.parent/'normal.sqlite'
        helpers.kit_adventure.import_adventure(db,text=helpers.SOURCE)
        room=helpers.kit_adventure.compile_location(db,self.key,neighbours=False)['room']
        out=io.StringIO()
        with patch('sys.argv',['kit_agent','start','--db',str(db),'--room',room,
                    '--sheet','tests/fixtures/characters/nik.json']),contextlib.redirect_stdout(out):
            self.assertEqual(kit_agent.main(),0)
        packet=json.loads(out.getvalue())
        self.assertEqual(packet['stage'],'situation_required',packet)
        with contextlib.closing(helpers.Runtime(db)) as runtime:
            bridge=kit_agent.KitChatBridge(runtime)
            self.assertTrue(bridge.world_response)

    def test_discovery_remains_an_adjudicated_event(self):
        reading=self.reading();self.bridge.complete(self.packet['turn_id'],self.output(reading))
        source=self.runtime.source()
        key=next(k for k,f in source['facts'].items() if not f.get('visible'))
        before=set(self.runtime.load()[1]['known_facts'])
        self.assertNotIn(key,before)
        rev,_=self.runtime.load()
        self.runtime.commit('discovered',rev,[{'type':'reveal_fact','fact':key,'evidence':'Resolved observation.'}])
        self.assertIn(key,self.runtime.load()[1]['known_facts'])

    def test_all_visible_interpretation_is_rejected_without_committing_discovery(self):
        reading=self.reading();before=copy.deepcopy(self.runtime.load())
        reading['facts']={key:'visible' for key in reading['facts']}
        self.assertTrue(any(not fact.get('visible') for fact in self.packet['input']['facts'].values()))
        with self.assertRaisesRegex(InvalidChange,'Preparation cannot disclose'):
            self.bridge.complete(self.packet['turn_id'],self.output(reading))
        self.assertEqual(self.runtime.load(),before)
        self.assertNotIn(helpers.CONDITION,json.dumps(self.runtime.player_view()))

    def test_remote_quotation_can_only_create_a_private_proposal(self):
        reading=self.reading();q=self.quote(self.packet['input'],helpers.REMOTE)
        reading['additions']={'venn':{'name':'Commander Venn','kind':'person','presence':'present',
            'goal':'','basis':'unknown','evidence':[q],'visibility':'visible','visibility_evidence':[q]}}
        self.bridge.complete(self.packet['turn_id'],self.output(reading))
        source=self.runtime.source();state=self.runtime.load()[1]
        self.assertNotIn('venn',source['actors']);self.assertNotIn('venn',state['actors'])
        self.assertNotIn('venn',kit_combat.config(source).get('actors',{}))
        self.assertEqual(source['_proposed_actors']['venn']['authority'],'PROPOSED')
        self.assertNotIn('Commander Venn',json.dumps(self.runtime.player_view()))
        words=kit_agent.hidden_actor_words(source,state)
        with self.assertRaises(InvalidChange):
            kit_agent.check_hidden_actors('Narrator: Commander Venn stands in the room.',words)

    def test_preparation_does_not_retract_preexisting_player_knowledge(self):
        before=set(self.runtime.load()[1]['known_facts'])
        reading=self.reading();reading['facts']={key:'private' for key in reading['facts']}
        self.bridge.complete(self.packet['turn_id'],self.output(reading))
        self.assertTrue(before<=set(self.runtime.load()[1]['known_facts']))

    def test_hidden_actor_cannot_be_revealed_by_interpretation(self):
        reading=self.reading();key=next(k for k,a in self.packet['input']['actors'].items() if a['status']=='hidden')
        reading['actors'][key].update(visibility='visible',visibility_evidence=[self.quote(self.packet['input'],helpers.LOCAL)])
        with self.assertRaisesRegex(InvalidChange,'Preparation cannot reveal'):
            self.bridge.complete(self.packet['turn_id'],self.output(reading))


class Binding(unittest.TestCase):
    def test_opening_binding_cannot_reveal_an_existing_hidden_actor(self):
        actors=self.actors();actors['goblin_1'].update(status='hidden',visible=False)
        result,_,_=kit_scene_contract.bind_people(actors,[{'id':'goblin_1','name':'Goblin 1',
            'kind':'creature','hidden':False}],'here',True)
        self.assertFalse(result['goblin_1']['visible'])
        self.assertEqual(result['goblin_1']['status'],'hidden')

    def test_committed_opening_keeps_the_second_actor_unchanged(self):
        import tempfile
        from pathlib import Path
        from runtime import kit_skim
        from runtime.state_context import Runtime
        from runtime.kit_agent import KitChatBridge
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
        import kit_fuzz
        burst='Goblin 1 and Goblin 2 stand in the courtyard.'
        line='First Guard is Goblin 1, a goblin with 18 hit points.'
        person=self.correction()
        scene={'place':{'name':'courtyard','quote':burst},'people':[
            {'id':'goblin_1','name':'Goblin 1','quote':burst,'kind':'creature','visibility':'visible',
             'goal':None,'knowledge':[],'source_name':'First Guard',
             'identity_evidence':[{'quote':line,'status':'established'}],
             'statistics':{'srd':'goblin','hp':18,'evidence':[{'quote':line,'status':'established'}]}},
            {'id':'goblin_2','name':'Goblin 2','quote':burst,'kind':'creature','visibility':'visible',
             'goal':None,'knowledge':[]}],'discoveries':[],'pressures':[]}
        self.assertEqual(kit_scene_contract.validate(scene,burst+'\n'+line,burst),[])
        source={'id':'synthetic-group','starting_area':'here','areas':{'here':{'name':'Courtyard'}},
            'actors':self.actors(),'exits':{},'resources':{},
            'facts':{'view':{'area':'here','text':burst,'visible':True}}}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'room.json';path.write_text(json.dumps(source),encoding='utf-8')
            kit_skim._stamp_beat(path,kit_scene_contract.build_beat(scene,burst,'Courtyard'))
            with contextlib.closing(Runtime(Path(folder)/'game.sqlite')) as runtime:
                runtime.initialize(json.loads(path.read_text(encoding='utf-8')),'here')
                runtime.set_player_sheet(json.loads(Path('tests/fixtures/characters/nik.json').read_text()))
                bridge=KitChatBridge(runtime)
                packet=bridge.prepare(opening=True,one_pass=True,turn_id='group-opening')
                result,why=kit_fuzz.complete(bridge,packet)
                self.assertIsNotNone(result,why)
                actors=runtime.source()['actors']
                self.assertEqual(actors['goblin_1']['name'],'First Guard')
                self.assertEqual(kit_combat.config(runtime.source())['actors']['goblin_1']['hp'],18)
                self.assertEqual(actors['goblin_2'],source['actors']['goblin_2'])

    def actors(self):
        return {key:{'name':name,'location':'here','status':'alive','visible':True,
                     'stat_block':{'srd':'goblin'}}
                for key,name in [('goblin_1','Goblin 1'),('goblin_2','Goblin 2')]}

    def correction(self):
        return {'id':'goblin_1','name':'Goblin 1','kind':'creature','hidden':False,
            'source_name':'First Guard','identity_evidence':[],
            'statistics':{'srd':'goblin','hp':18,'evidence':[]}}

    def test_exact_id_does_not_rename_or_restat_the_other_actor(self):
        original=self.actors();person=self.correction()
        actors,ids,bound=kit_scene_contract.bind_people(original,[person],'here',True)
        self.assertEqual(bound,{'goblin_1':['goblin_1']})
        self.assertEqual(ids,['goblin_1'])
        self.assertEqual(actors['goblin_1']['stat_block']['hp'],18)
        self.assertEqual(actors['goblin_2'],original['goblin_2'])
        self.assertEqual(original['goblin_1']['name'],'Goblin 1')

    def test_ambiguous_group_correction_is_refused(self):
        person=self.correction();person.update(id='goblins',name='Goblins')
        with self.assertRaisesRegex(InvalidChange,'unambiguous actor id'):
            kit_scene_contract.bind_people(self.actors(),[person],'here',True)


if __name__=='__main__':unittest.main()
