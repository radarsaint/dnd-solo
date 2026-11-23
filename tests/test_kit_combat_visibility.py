"""Private combat participants must not become public identities before observation."""
import copy
import json
import unittest
from runtime import kit_combat,kit_combat_acts
from runtime.state_context import Runtime,reveal_actor
import test_kit_world_response as helpers

class CombatVisibility(unittest.TestCase):
    setUp=helpers.WorldResponse.setUp
    setup_scene=helpers.WorldResponse.setup_scene
    _scene=helpers.WorldResponse._scene
    _room=helpers.WorldResponse._room

    def scene(self,mark='visible'):
        self.setup_scene()
        source=self.runtime.source();state=copy.deepcopy(self.runtime.load()[1])
        for actor in state['actors'].values():
            actor.update(status='alive',visible=True)
        if mark=='visible':state['actors']['bandit_1']['visible']=False
        elif mark=='conditions':state['actors']['bandit_1']['conditions']=['invisible']
        else:source['actors']['bandit_1'][mark]=True
        return source,state

    def fight(self,source,state):
        f=kit_combat.Fight(source,state,0,'I hold my ground.',check=None,roll=lambda:1)
        f.ensure_fight('visibility-regression');f.set_order(25);return f

    def test_private_roster_and_hp_include_active_unseen_opponent(self):
        source,state=self.scene();f=self.fight(source,state)
        self.assertIn('bandit_1',f.fight['order'])
        self.assertIn('bandit_1',f.fight['hp'])
        self.assertIn('bandit_1',f.hostiles())

    def test_initiative_and_public_view_do_not_identify_unseen_opponent(self):
        source,state=self.scene();f=self.fight(source,state);state['combat']=f.fight
        hidden=kit_combat.labels(source)['bandit_1']
        self.assertNotIn(hidden.casefold(),' '.join(f.lines).casefold())
        self.assertNotIn(hidden,json.dumps(kit_combat.public_view(source,state)))
        self.assertNotIn('bandit_1',kit_combat_acts.offer(source,state)['targets'])

    def test_all_existing_visibility_markers_are_respected(self):
        source,state=self.scene()
        for mark in ('visible','invisible','concealed','unseen','conditions'):
            s=copy.deepcopy(source);st=copy.deepcopy(state)
            st['actors']['bandit_1'].update(visible=True,conditions=[])
            if mark=='visible':st['actors']['bandit_1']['visible']=False
            elif mark=='conditions':st['actors']['bandit_1']['conditions']=['invisible']
            else:s['actors']['bandit_1'][mark]=True
            f=self.fight(s,st);st['combat']=f.fight
            hidden=kit_combat.labels(s)['bandit_1']
            with self.subTest(mark=mark):
                self.assertNotIn(hidden,json.dumps(kit_combat.public_view(s,st)))
                self.assertNotIn('bandit_1',kit_combat_acts.offer(s,st)['targets'])

    def test_unseen_opponent_can_act_without_premature_name_disclosure(self):
        source,state=self.scene();f=self.fight(source,state);f.lines=[]
        f.npc_turn('bandit_1')
        self.assertTrue(f.lines)
        hidden=kit_combat.labels(source)['bandit_1']
        self.assertNotIn(hidden.casefold(),' '.join(f.lines).casefold())
        self.assertTrue(any('bandit_1' in line for line in f.trace))

    def test_explicit_reveal_makes_identity_and_targets_available(self):
        source,state=self.scene('invisible');f=self.fight(source,state);state['combat']=f.fight
        reveal_actor(state['actors']['bandit_1'],source['actors']['bandit_1'])
        hidden=kit_combat.labels(source)['bandit_1'];view=kit_combat.public_view(source,state)
        self.assertIn(hidden,view['fight']['order'])
        self.assertIn(hidden,view['fight']['wounds'])
        self.assertIn('bandit_1',kit_combat_acts.offer(source,state)['targets'])

    def test_hidden_status_does_not_activate_without_source_reveal(self):
        source,state=self.scene();state['actors']['bandit_1']['status']='hidden'
        f=self.fight(source,state)
        self.assertNotIn('bandit_1',f.hostiles())
        self.assertNotIn('bandit_1',f.fight['order'])

    def test_party_order_rendering_does_not_restore_hidden_name(self):
        source,state=self.scene();f=self.fight(source,state);state['combat']=f.fight
        state['party']={'ally':{'sheet':{'name':'Ally'},'hp':10,'max_hp':10,'status':'standing'}}
        f.fight['order'].append('ally')
        view=kit_combat.public_view(source,state)
        self.assertIn('Ally',view['fight']['order'])
        self.assertNotIn(kit_combat.labels(source)['bandit_1'],json.dumps(view))

    def test_persisted_private_roster_survives_restart_and_explicit_reveal(self):
        self.setup_scene();rev,_=self.runtime.load()
        self.runtime.commit('visibility-state',rev,[
            {'type':'actor_status','actor':'bandit_1','status':'alive','evidence':'An active opponent remains unseen.'},
            {'type':'actor_status','actor':'bandit_2','status':'alive','reveal':True,'evidence':'The visible guard is observed.'}])
        source=self.runtime.source();rev,state=self.runtime.load();f=self.fight(source,state)
        self.runtime.commit('private-fight',rev,f.events());path=self.runtime.path
        self.runtime.close();self.runtime=Runtime(path);self.addCleanup(self.runtime.close)
        source=self.runtime.source();rev,state=self.runtime.load();hidden=kit_combat.labels(source)['bandit_1']
        self.assertIn('bandit_1',state['combat']['hp'])
        self.assertNotIn(hidden,json.dumps(kit_combat.public_view(source,state)))
        self.runtime.commit('observed',rev,[{'type':'actor_status','actor':'bandit_1','status':'alive',
            'reveal':True,'evidence':'Explicitly observed and revealed during play.'}])
        self.assertIn(hidden,json.dumps(kit_combat.public_view(source,self.runtime.load()[1])))
