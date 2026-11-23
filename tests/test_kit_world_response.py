"""Synthetic encounter, full public bridge; no model API or manual record rescue."""
import copy
import unittest
from unittest.mock import patch
from runtime import kit_world_response
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime
import test_kit_source_ambush_gpt as ambush
from test_kit_agent import RecordingModel

class WorldResponse(unittest.TestCase):
    setUp = ambush.SourceAuthoredAmbush.setUp
    _scene = ambush.SourceAuthoredAmbush._scene
    _room = ambush.SourceAuthoredAmbush._room
    def setup_scene(self, enabled=True):
        self._room(False)  # No source-prescribed failed-notice attack.
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(), world_response=enabled)

    def output(self, packet, act='start_combat', actors=None):
        plan = RecordingModel().plan(packet['input']['private'])
        plan.update(move='world_description', focus_actor='none', turn_mode='description')
        plan['improv_read'].update(actor_ref='none', actor_basis='none',
            kit_choice='The opposition responds to the disturbance while pursuing its supplies.',
            connection='The disturbance makes waiting less useful for the existing opposition.')
        brief=plan['public_brief']
        brief.update(objective='Show the disturbance and let the opposition respond.',
            tactic='Keep the response grounded in the scene.', visible_cue='The stone strikes the ditch.',
            player_opening='The player can respond to what happens next.', scope='call',
            kit_focus='The stone hitting the ditch.', mirror='steady energy, standard, dry humor: meet the even pace and let the answer land.')
        plan['world_response']={'act':act, 'actors': actors if actors is not None else ['bandit_1','bandit_2'],
            'why':'The disturbance exposes their position while they still want the supplies.'}
        return {'decision':plan,'performance':{'segments':[{'speaker':'Narrator',
            'text':'The stone lands in the ditch with a dry clatter. Branches shiver where it strikes the bank.'}]}}

    def prepare(self):
        return self.bridge.prepare('I toss a stone into the ditch beside the pine.',one_pass=True)

    def test_response_starts_real_combat_and_replays_once(self):
        self.setup_scene()
        packet=self.prepare()
        self.assertIn('world_response',packet['input']['private'])
        output=self.output(packet)
        before=self.runtime.load()[0]
        result=self.bridge.complete(packet['turn_id'],output)
        state=self.runtime.load()[1]
        self.assertEqual(state['combat']['status'],'awaiting_initiative')
        self.assertEqual(set(state['combat']['participants']),{'bandit_1','bandit_2'})
        self.assertEqual(state['combat']['surprised'],[])
        self.assertTrue(all(state['actors'][k]['status']=='alive' for k in state['combat']['participants']))
        self.assertIn('Roll initiative.',result['spoken'])
        self.assertIn('Bandit',result['spoken'])
        again=self.bridge.complete(packet['turn_id'],output)
        self.assertTrue(again['already_committed'])
        self.assertEqual(self.runtime.load()[0],before+1)
        self.assertEqual(again['spoken'],result['spoken'])

    def test_initiative_continues_native_fight_after_restart(self):
        self.setup_scene()
        packet=self.prepare()
        self.bridge.complete(packet['turn_id'],self.output(packet))
        path=self.runtime.path
        self.runtime.close()
        self.runtime=Runtime(path)
        self.addCleanup(self.runtime.close)
        self.bridge=KitChatBridge(self.runtime, RoomAdjudicator(), world_response=True)
        result=self.bridge.prepare('Initiative 15.',one_pass=True)
        self.assertNotEqual(result.get('stage'),'roll_clarify',result)
        # prepare may stage a normal model turn; its proposed events must advance native combat.
        if result.get('turn_id') and not result.get('committed'):
            pending=self.runtime.pending_kit_turn(result['turn_id'])
            states=[e['state'] for e in pending['body']['events'] if e['type']=='combat_state']
            self.assertTrue(states,result)
            self.assertEqual(states[-1]['status'],'running')
            self.assertEqual(states[-1]['pc_initiative'],15)
            output=self.output(result)
            output['decision'].pop('world_response')
            output['decision']['turn_mode']='combat'
            output['performance']['segments'][0]['text']='The confrontation is out in the open now. The figures beside the ditch are ready to fight.'
            self.bridge.complete(result['turn_id'],output)
            self.assertEqual(self.runtime.load()[1]['combat']['pc_initiative'],15)
        else:
            self.assertEqual(self.runtime.load()[1]['combat']['pc_initiative'],15)

    def test_baseline_commits_stone_without_world_response(self):
        self.setup_scene(False)
        packet=self.prepare(); output=self.output(packet)
        output['decision'].pop('world_response')
        self.bridge.complete(packet['turn_id'],output)
        self.assertFalse(self.runtime.load()[1].get('combat'))
        self.assertEqual(self.runtime.load()[1]['actors']['bandit_1']['status'],'hidden')

    def test_visible_opponents_do_not_reappear_when_starting_combat(self):
        self.setup_scene()
        packet=self.prepare()
        self.bridge.complete(packet['turn_id'],self.output(packet,'reveal'))
        packet=self.prepare()
        output=self.output(packet)
        output['performance']['segments'][0]['text']='The confrontation is out in the open now. The figures beside the ditch are ready to fight.'
        result=self.bridge.complete(packet['turn_id'],output)
        self.assertNotIn('step into view',result['spoken'])
        self.assertIn('Roll initiative.',result['spoken'])

    def test_wait_does_not_force_an_attack(self):
        self.setup_scene()
        packet=self.prepare()
        self.bridge.complete(packet['turn_id'],self.output(packet,'wait',[]))
        self.assertFalse(self.runtime.load()[1].get('combat'))
        self.assertEqual(self.runtime.load()[1]['actors']['bandit_1']['status'],'hidden')

    def test_reveal_allows_negotiation_without_combat(self):
        self.setup_scene()
        packet=self.prepare()
        result=self.bridge.complete(packet['turn_id'],self.output(packet,'reveal'))
        self.assertFalse(self.runtime.load()[1].get('combat'))
        self.assertEqual(self.runtime.load()[1]['actors']['bandit_1']['status'],'alive')
        self.assertNotIn('initiative',result['spoken'].lower())
        from runtime import kit_opening
        beat=kit_opening._load(self.runtime)[1]
        self.assertTrue(beat['people'][0]['revealed'])

    def test_invalid_actor_changes_nothing(self):
        self.setup_scene()
        packet=self.prepare(); before=copy.deepcopy(self.runtime.load())
        with self.assertRaises(InvalidChange):
            self.bridge.complete(packet['turn_id'],self.output(packet,actors=['invented_dragon']))
        self.assertEqual(self.runtime.load(),before)

    def test_disabled_path_does_not_offer_world_response(self):
        self.setup_scene(False)
        packet=self.prepare()
        self.assertNotIn('world_response',packet['input']['private'])
        with self.assertRaises(InvalidChange):
            self.bridge.complete(packet['turn_id'],self.output(packet))

    def test_missing_stats_cannot_start_a_fight(self):
        self.setup_scene()
        packet=self.prepare()
        offered=copy.deepcopy(packet['input']['private']['world_response'])
        offered['actors']['bandit_1']['can_fight']=False
        output=self.output(packet)
        with self.assertRaises(InvalidChange):
            kit_world_response.check(output['decision']['world_response'],offered,output['decision'])

    def test_projection_io_failure_does_not_undo_committed_turn(self):
        self.setup_scene()
        packet=self.prepare(); output=self.output(packet)
        with patch('runtime.kit_agent._remember_npc_replies',side_effect=OSError('projection unavailable')):
            result=self.bridge.complete(packet['turn_id'],output)
        self.assertIn('Roll initiative.',result['spoken'])
        self.assertTrue(self.runtime.kit_timing(packet['turn_id'])['memory_projection_pending'])
        self.assertEqual(self.runtime.load()[1]['combat']['status'],'awaiting_initiative')

    def test_commit_failure_does_not_reveal_or_start_combat(self):
        self.setup_scene()
        packet=self.prepare(); output=self.output(packet); before=copy.deepcopy(self.runtime.load())
        with patch('runtime.kit_agent._remember_npc_replies') as remember:
            with patch.object(self.runtime,'commit_kit_turn',side_effect=RuntimeError('injected interruption')):
                with self.assertRaises(RuntimeError): self.bridge.complete(packet['turn_id'],output)
            remember.assert_not_called()
        self.assertEqual(self.runtime.load(),before)
        self.bridge.complete(packet['turn_id'],output)
        self.assertEqual(self.runtime.load()[1]['combat']['status'],'awaiting_initiative')

if __name__=='__main__': unittest.main()
