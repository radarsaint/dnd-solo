"""Synthetic published-style procedure; native events and persisted SQLite state."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from runtime import kit_adventure,kit_combat,kit_situation,kit_timed_procedures,kit_rooms
from runtime.kit_agent import KitChatBridge,start_session
from runtime.state_context import Runtime,InvalidChange

PRESENCE='Two goblins stand guard in this room.'
PROCEDURE='At the start of combat, one goblin runs to warn the commander in area 3, then returns 2 rounds later.'
TEXT=('1. Landing\n> A stair leads upward.\nA passage leads to area 2.\n'
      '2. Watch\n> A brazier glows in the watch room.\n'+PRESENCE+'\n'+PROCEDURE+'\n'
      '3. Command Room\n> A writing desk stands here.\n')

class TimedProcedures(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/'kit.sqlite'
        kit_adventure.import_adventure(self.db,text=TEXT)
        index,_=kit_adventure._load(self.db)
        key=next(k for k,v in index['locations'].items() if v['name']=='Watch')
        room=kit_adventure.compile_location(self.db,key,neighbours=False)['room']
        self.packet=start_session(str(self.db),'tests/fixtures/characters/nik.json',room=room,world_response=True)
        self.r=Runtime(self.db);self.addCleanup(self.r.close)
        req=self.packet['input'];local=req['units']['local']
        def quote(text):return {'unit':'local','quote':text,'offset':local['span'][0]+local['text'].index(text)}
        self.guards=[k for k,v in req['actors'].items() if 'goblin' in v['name'].lower()]
        self.away=self.guards[0];self.stays=self.guards[1]
        unit=next(k for k,v in req['units'].items() if k!='local' and v.get('room_id'))
        self.destination=req['units'][unit]['room_id']
        self.reading={'request_hash':req['request_hash'],
          'actors':{k:{'presence':'present' if k in self.guards else 'mentioned',
            'goal':'Guard the watch room.' if k in self.guards else '',
            'basis':'inferred' if k in self.guards else 'unknown',
            'evidence':[quote(PRESENCE if k in self.guards else PROCEDURE)]} for k in req['actors']},
          'facts':{k:'private' for k in req['facts']},'conditions':[quote(PROCEDURE)],'unresolved':[],
          'timed_procedures':[{'id':'warn-return','kind':'warn_and_return','actor':self.away,
            'destination_unit':unit,'destination_room':self.destination,'after_rounds':2,'evidence':quote(PROCEDURE)}]}
        KitChatBridge(self.r,world_response=True).complete(self.packet['turn_id'],
            {'decision':{'situation':self.reading},'performance':{'segments':[]}})
        self.r.commit('reveal',self.r.load()[0],[{'type':'actor_status','actor':key,
            'status':'alive','reveal':True,'evidence':'Native reveal before the test encounter starts.'}
            for key in self.guards])

    def fight(self):
        rev,state=self.r.load()
        return kit_combat.Fight(self.r.source(),state,rev,'I hold my ground.',check=None,roll=lambda:1)

    def save(self,fight,key):
        events=fight.events();self.r.commit(key,self.r.load()[0],events);return events

    def start(self):
        f=self.fight();f.ensure_fight('test');self.save(f,'start');return f

    def round(self,f):
        before=f.fight['round']
        while f.fight['round']==before:f.step()

    def test_departure_and_warning_commit_once_and_restart(self):
        f=self.start();state=self.r.load()[1]
        self.assertEqual(state['actors'][self.away]['location'],'away:'+self.destination)
        self.assertEqual(len(state['source_warnings']),1)
        self.assertNotIn(self.away,f.hostiles())
        self.assertNotIn(self.away,kit_combat.present(self.r.source(),state))
        self.r.close();self.r=Runtime(self.db);self.addCleanup(self.r.close)
        f=self.fight();self.assertFalse(f.ensure_fight('again'))
        self.save(f,'after-restart');self.assertEqual(len(self.r.load()[1]['source_warnings']),1)

    def test_return_at_round_three_and_retained_initiative_slot(self):
        self.start();f=self.fight();f.set_order(25)
        self.assertIn(self.away,f.fight['order'])
        self.round(f);self.assertEqual(f.fight['round'],2);self.assertNotIn(self.away,f.hostiles())
        self.save(f,'round-two');self.r.close();self.r=Runtime(self.db);self.addCleanup(self.r.close)
        f=self.fight();self.round(f)
        self.assertEqual(f.fight['round'],3);self.assertIn(self.away,f.hostiles())
        self.assertNotEqual(f.label(self.away),'unseen opponent')
        self.save(f,'round-three');self.assertEqual(self.r.load()[1]['actors'][self.away]['location'],'here')

    def test_checkpoint_does_not_advance_deadline(self):
        self.start();f=self.fight();f.set_order(25)
        f.fight['awaiting']={'kind':'reaction_window','trigger':'hit','options':[]}
        self.save(f,'checkpoint');f=self.fight()
        self.assertEqual(f.fight['round'],1)
        self.assertEqual(f.fight['source_procedures'][0]['due_round'],3)
        f.fight['awaiting']=None;self.save(f,'answer-only')
        self.assertEqual(self.r.load()[1]['combat']['round'],1)

    def test_absent_foe_keeps_encounter_open(self):
        self.start();f=self.fight();f.statuses[self.stays]='dead'
        f.check_over();self.assertNotEqual(f.fight['status'],'over')

    def test_dead_or_relocated_actor_is_not_restored(self):
        self.start()
        for changed in ('dead','relocated'):
            f=self.fight();f.set_order(25)
            if changed=='dead':f.state['actors'][self.away]['status']='dead'
            else:f.state['actors'][self.away]['location']='elsewhere'
            self.round(f);self.assertEqual(f.fight['source_procedures'][0]['status'],'cancelled')
            self.assertNotIn(self.away,f.hostiles())

    def test_atomic_failure_and_exact_replay(self):
        f=self.fight();f.ensure_fight('test');events=f.events();before=copy.deepcopy(self.r.load())
        original=self.r._apply
        def interrupted(state,source,event,*args,**kw):
            result=original(state,source,event,*args,**kw)
            if event['type']=='combat_state':raise RuntimeError('interrupted after warning')
            return result
        with patch.object(self.r,'_apply',side_effect=interrupted):
            with self.assertRaises(RuntimeError):self.r.commit('start',before[0],events)
        self.assertEqual(self.r.load(),before)
        rev=self.r.commit('start',before[0],events)
        self.assertEqual(self.r.commit('start',before[0],events),rev)
        self.assertEqual(len(self.r.load()[1]['source_warnings']),1)

    def test_warning_survives_destination_mount_and_revisit(self):
        self.start();source=self.r.source();state=self.r.load()[1]
        # Mount state transformer, not a claim that the PC can leave an active fight.
        other=copy.deepcopy(source);other['id']=self.destination
        mounted=kit_rooms.mounted_state(source,state,other,'here','destination.json')
        self.assertEqual(len(kit_timed_procedures.warnings_here(mounted,self.destination)),1)
        back=kit_rooms.mounted_state(other,mounted,source,'here','origin.json')
        again=kit_rooms.mounted_state(source,back,other,'here','destination.json')
        self.assertEqual(len(kit_timed_procedures.warnings_here(again,self.destination)),1)

    def test_false_dependency_or_changed_evidence_refused(self):
        req=self.packet['input']
        for field,value in [('destination_room','invented'),('after_rounds',True),('actor','invented')]:
            reading=copy.deepcopy(self.reading);reading['timed_procedures'][0][field]=value
            with self.subTest(field=field),self.assertRaises(InvalidChange):kit_situation.validate(reading,req)

    def test_early_return_event_is_refused(self):
        f=self.start();f=self.fight();f.fight['source_procedures'][0]['status']='returned'
        with self.assertRaises(InvalidChange):self.save(f,'early-return')
