"""Source inventory repairs use native state, not edited live room files."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import kit_adventure, kit_combat, kit_situation
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import Runtime, InvalidChange
from test_kit_later_situation import LaterSituation, SOURCE, CONDITION

CAPTIVE = 'Mara is unconscious and bound beside the wolf Ash in this chamber.'
STATS = 'Ash uses wolf statistics but has 18 hit points.'


class Inventory(LaterSituation):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.db=Path(folder.name)/'kit.sqlite'
        kit_adventure.import_adventure(self.db,text=SOURCE.replace(CONDITION,CONDITION+'\n'+CAPTIVE+'\n'+STATS))
        index,_=kit_adventure._load(self.db)
        self.key=next(k for k,l in index['locations'].items() if 'Upper Watch' in l['name'])
        self.room=kit_adventure.compile_location(self.db,self.key,neighbours=False)['room']
        room=json.loads(Path(self.room).read_text(encoding='utf-8'))
        room['actors']={k:v for k,v in room['actors'].items() if 'goblin' in v['name'].lower()}
        for trigger in room.get('triggers',[]):
            trigger['actors']=[k for k in trigger['actors'] if k in room['actors']]
        room['triggers']=[t for t in room.get('triggers',[]) if t['actors']]
        Path(self.room).write_text(json.dumps(room),encoding='utf-8')
        self.before=Path(self.room).read_bytes()
        self.packet=start_session(str(self.db),'tests/fixtures/characters/nik.json',room=self.room,world_response=True)
        self.runtime=Runtime(self.db);self.addCleanup(self.runtime.close)
        self.bridge=KitChatBridge(self.runtime,RoomAdjudicator(),world_response=True)

    def inventory(self):
        reading=self.reading();req=self.packet['input']
        reading['additions']={}
        for key,name,kind in [('mara','Mara','person'),('ash','Ash','creature')]:
            reading['additions'][key]={'name':name,'kind':kind,'presence':'present','goal':'','basis':'unknown',
                'evidence':[self.quote(req,CAPTIVE)],'visibility':'visible',
                'visibility_evidence':[self.quote(req,CAPTIVE)]}
        reading['additions']['ash']['statistics']={'srd':'wolf','hp':18,'evidence':[self.quote(req,STATS)]}
        reading['additions']['mara']['status']='unconscious'
        return reading

    def test_restored_people_and_authored_stats_reach_native_state_and_restart(self):
        output=self.output(self.inventory())
        result=self.bridge.complete(self.packet['turn_id'],output)
        source=self.runtime.source();state=self.runtime.load()[1]
        self.assertEqual(set(source['actors']),set(state['actors']))
        self.assertIn('mara',state['actors'])
        self.assertEqual(state['actors']['mara']['status'],'unconscious')
        self.assertNotIn('mara',kit_combat.config(source)['actors'])
        self.assertEqual(kit_combat.config(source)['actors']['ash']['hp'],18)
        self.assertEqual(state['actors']['ash']['statistics_provenance']['srd'],'wolf')
        self.assertEqual(Path(self.room).read_bytes(),self.before)
        self.runtime.close();self.runtime=Runtime(self.db);self.addCleanup(self.runtime.close)
        self.bridge=KitChatBridge(self.runtime,world_response=True)
        self.assertEqual(kit_combat.config(self.runtime.source())['actors']['ash']['hp'],18)
        self.assertEqual(self.bridge.complete(self.packet['turn_id'],output)['revision'],result['revision'])

    def test_actual_turn_context_and_native_fight_use_the_restored_inventory(self):
        reading=self.inventory()
        self.bridge.complete(self.packet['turn_id'],self.output(reading))
        packet=self.bridge.prepare(None,opening=True,one_pass=True,turn_id='entry-context')
        private=packet['input']['private']
        self.assertEqual(private['source_situation']['reading']['additions'],reading['additions'])
        self.bridge.abandon('entry-context')
        rev,state=self.runtime.load()
        fight=kit_combat.Fight(self.runtime.source(),state,rev,'I hold my ground.',check=None,roll=lambda:1)
        fight.ensure_fight('inventory-regression');fight.set_order(25)
        self.assertEqual(fight.fight['hp']['ash'],18)
        self.assertNotIn('mara',fight.fight['hp'])
        self.runtime.commit('native-fight',rev,fight.events())
        self.runtime.close();self.runtime=Runtime(self.db);self.addCleanup(self.runtime.close)
        self.assertEqual(self.runtime.load()[1]['combat']['hp']['ash'],18)

    def test_bad_inventory_or_stat_evidence_cannot_commit(self):
        for fault in ['id','name','offset','remote','hp','boolean','base','collision','alias','status']:
            reading=self.inventory();mara=reading['additions']['mara'];ash=reading['additions']['ash']
            if fault=='id':reading['additions']['Bad ID']=reading['additions'].pop('mara')
            if fault=='name':mara['name']='Invented Person'
            if fault=='offset':mara['evidence'][0]['offset']+=1
            if fault=='remote':mara['evidence'][0]['unit']='reference_missing'
            if fault=='hp':ash['statistics']['hp']=180
            if fault=='boolean':ash['statistics']['hp']=True
            if fault=='base':ash['statistics']['srd']='dragon'
            if fault=='collision':reading['additions'][next(iter(reading['actors']))]=reading['additions'].pop('mara')
            if fault=='alias':ash.update(source_name='Invented Name',identity_evidence=[self.quote(self.packet['input'],STATS)])
            if fault=='status':mara['status']='dead'
            before=copy.deepcopy(self.runtime.load())
            with self.subTest(fault=fault),self.assertRaises(InvalidChange):
                self.bridge.complete(self.packet['turn_id'],self.output(reading))
            self.assertEqual(self.runtime.load(),before)

    def test_interpretation_after_a_played_turn_cannot_reset_outcomes(self):
        rev,_=self.runtime.load()
        self.runtime.commit('played',rev,[{'type':'beat','tags':['wait'],'evidence':'Time passes.'}])
        before=copy.deepcopy(self.runtime.load())
        with self.assertRaises(InvalidChange):
            self.runtime._commit('late-reading',before[0],[{'type':'source_situation',
                'reading':self.inventory(),'action':'','entry':True}])
        self.assertEqual(self.runtime.load(),before)

    def test_source_named_alias_preserves_identity_and_statistics(self):
        reading=self.inventory();ash=reading['additions'].pop('ash')
        ash.update(name='wolf',source_name='Ash',identity_evidence=[self.quote(self.packet['input'],STATS)])
        reading['additions']['wolf_identity']=ash
        self.bridge.complete(self.packet['turn_id'],self.output(reading))
        source=self.runtime.source()
        self.assertEqual(source['actors']['wolf_identity']['name'],'Ash')
        self.assertEqual(kit_combat.config(source)['actors']['wolf_identity']['hp'],18)

    def test_pinned_compiler_limits_reach_the_private_turn_packet(self):
        original=kit_adventure.draft_room
        def flagged(*args,**kwargs):
            room,prov=original(*args,**kwargs)
            prov['flags'].append('Synthetic creature: not run by the engine: legendary action')
            return room,prov
        with patch.object(kit_adventure,'draft_room',side_effect=flagged):
            self.bridge.abandon(self.packet['turn_id'])
            self.packet=self.bridge.prepare(None,opening=True,one_pass=True,turn_id='new-source')
            self.bridge.complete(self.packet['turn_id'],self.output(self.inventory()))
            packet=self.bridge.prepare(None,opening=True,one_pass=True,turn_id='context')
        self.assertIn('Synthetic creature: not run by the engine: legendary action',
                      packet['input']['private']['source_situation']['compiler_limits'])


if __name__=='__main__':unittest.main()
