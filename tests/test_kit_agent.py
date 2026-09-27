import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.kit_agent import (KitAgent, KitChatBridge, OpenAIResponsesModel, PendingRuling,
                               Room6CAdjudicator, room_intent)
from runtime.state_context import InvalidChange, Runtime, StaleTurn


FIXTURE = Path(__file__).parent / 'fixtures/level_01_area_06c.json'


class RecordingModel:
    def __init__(self, leak=False, on_perform=None, leaky_brief=False):
        self.plans = []
        self.performances = []
        self.leak = leak
        self.leaky_brief = leaky_brief
        self.on_perform = on_perform

    def plan(self, payload):
        self.plans.append(payload)
        episodes = payload['kit_state']['episodes']
        return {
            'observed_event': payload['accepted_public_event'],
            'goal': 'roleplay',
            'appraisal': {'label': 'interest', 'intensity': 1,
                          'cause': f"The player chose: {payload['player_action']}",
                          'goal_effect': 'advances', 'target': 'player'},
            'memory_refs': [episodes[-1]['turn_id']] if episodes else [],
            'improv_read': {
                'player_bid': f"The player declared: {payload['player_action']}",
                'story_anchor': 'scene', 'story_basis': 'scene_state',
                'actor_ref': 'uktarl', 'actor_basis': 'immediate_goal',
                'connection': 'The visitor approaches the table while the dealer wants control of the encounter.',
                'kit_choice': 'Kit favors the roleplay opening and lets the dealer try a bargain.',
            },
            'move': 'kit_comment_then_npc',
            'public_brief': {
                'objective': 'Invite the visitor to commit to the game or a passage bargain.',
                'tactic': ('Reveal the doppelganger.' if self.leaky_brief else
                           'The dealer treats the question as an opening bid.'),
                'visible_cue': 'The dealer suspends a card over the table.',
                'player_opening': 'The visitor may ask about the terms, play, or leave.',
            },
            'focus_actor': 'uktarl',
            'table_presence': 'brief', 'tone': 'wry',
        }

    def perform(self, payload):
        self.performances.append(payload.copy())
        if self.on_perform:
            callback, self.on_perform = self.on_perform, None
            callback()
        if self.leak:
            return {'segments': [
                {'speaker': 'Kit', 'text': 'That is a choice.'},
                {'speaker': 'Dealer', 'text': 'Ten gold for safe passage.'},
                {'speaker': 'Narrator', 'text': 'The doppelganger smiles.'},
            ]}
        return {'segments': [
            {'speaker': 'Kit', 'text': 'That is a choice.'},
            {'speaker': 'Dealer', 'text': 'Sit, then. Ten gold buys safe passage. What would you wager?'},
        ]}


class KitAgentTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.model = RecordingModel()
        self.agent = KitAgent(self.runtime, self.model, Room6CAdjudicator(
            perception=0, insight=0, roll=lambda: 20))

    def test_personality_probe_actions_route_to_bounded_room_operations(self):
        probes = {
            'I pull up a chair and ask what the stakes are.': 'social',
            "I call out the dealer's marked cards.": 'social',
            'I study those tiny figures in the carving while they argue.': 'inspect_fresco',
            'I could help you get rid of Harria. What is that worth?': 'social',
            'I tip the stone tub over and use it as cover.': 'tip_tub',
            'I attack Uktarl in the middle of the game.': 'combat',
        }
        for action, kind in probes.items():
            with self.subTest(action=action):
                self.assertEqual(room_intent(action), kind)

    def test_decision_precedes_performance_and_persists_with_world(self):
        result = self.agent.turn('I pull up a chair and ask about the stakes.', 'first')
        self.assertEqual(result['revision'], 1)
        self.assertEqual(len(self.model.plans), 1)
        self.assertEqual(len(self.model.performances), 1)
        self.assertIn('marked_deck', self.model.plans[0]['dm_context']['dm_only']['unrevealed_facts'])
        self.assertEqual(set(self.model.plans[0]['discernment_candidates']['story_bases']),
                         {'level', 'none', 'scene'})
        self.assertNotIn('dm_only', self.model.performances[0])
        self.assertNotIn('doppelganger', json.dumps(self.model.performances[0]).lower())
        self.assertNotIn('uktarl', json.dumps(self.model.performances[0]).lower())
        self.assertNotIn('improv_read', self.model.performances[0])
        self.assertEqual(self.model.performances[0]['selected_move']['focus_actor'], 'Dealer')
        self.assertEqual(self.model.performances[0]['selected_move']['brief']['tactic'],
                         'The dealer treats the question as an opening bid.')
        self.assertIn('drawl', self.model.performances[0]['performance_reference']['actor_cards']['Dealer']['vocal_signature'])
        self.assertIn('Kit:', result['spoken'])
        self.assertIn('Dealer:', result['spoken'])
        self.assertEqual(self.runtime.load()[1]['kit']['episodes'][0]['turn_id'], 'first')
        self.assertEqual(self.runtime.recent_kit_turns()[0]['trace']['memory_refs'], [])
        self.assertEqual(self.runtime.recent_kit_turns()[0]['trace']['improv_read']['actor_ref'], 'uktarl')
        self.runtime.close()
        self.runtime = Runtime(self.path)
        self.agent.runtime = self.runtime
        self.assertEqual(self.runtime.recent_kit_turns()[0]['spoken'], result['spoken'])
        self.agent.turn('What if I offered you a deal?', 'second')
        self.assertEqual(self.model.plans[-1]['kit_state']['episodes'][0]['turn_id'], 'first')
        self.assertEqual(self.model.plans[-1]['dialogue_history'][0]['spoken'], result['spoken'])
        self.assertEqual(self.runtime.recent_kit_turns()[-1]['trace']['memory_refs'], ['first'])

    def test_known_check_reveals_only_what_was_found(self):
        result = self.agent.turn('I study the tiny dwarven figures in the carving.', 'fresco')
        self.assertIn('stone key', result['spoken'])
        public = json.dumps(self.runtime.player_view()).lower()
        self.assertIn('stone key', public)
        self.assertNotIn('area 14b', public)
        self.assertEqual(self.runtime.load()[0], 1)

    def test_private_fact_in_performance_rolls_back_kit_and_world(self):
        self.model.leak = True
        before = self.runtime.load()
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            self.agent.turn('I accuse that player of being a doppelganger.', 'leaky')
        self.assertEqual(self.runtime.load(), before)
        self.assertEqual(len(self.model.performances), 2)
        self.assertEqual(self.runtime.recent_kit_turns(), [])
        self.assertEqual(self.runtime.db.execute('SELECT count(*) FROM ledger').fetchone()[0], 0)

    def test_private_fact_in_plan_brief_never_reaches_performer(self):
        model = RecordingModel(leaky_brief=True)
        agent = KitAgent(self.runtime, model, self.agent.adjudicator)
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            agent.turn('I take a seat.', 'bad-brief')
        self.assertEqual(model.performances, [])
        self.assertEqual(self.runtime.load()[0], 0)

    def test_private_discernment_selects_live_level_pressure_and_stays_private(self):
        bridge = KitChatBridge(self.runtime, self.agent.adjudicator)
        prepared = bridge.prepare('I could help you get rid of Harria. What is that worth?', 'faction')
        plan = self.model.plan(prepared['input'])
        plan['improv_read'].update(
            story_anchor='level', story_basis='pressure_here', actor_basis='motive',
            connection='The offer touches the live leadership rivalry, which Uktarl wants to exploit.',
            kit_choice='Kit wants consequential roleplay, so she gives the offer room while Uktarl tests it.')
        for bad_read, reason in [
            ({'story_anchor': 'campaign'}, 'not active'),
            ({'story_basis': 'invented_plot'}, 'not established'),
            ({'actor_ref': 'harria'}, 'not available'),
            ({'actor_ref': 'bandit_a'}, 'disagrees with selected actor'),
        ]:
            bad = {**plan, 'improv_read': {**plan['improv_read'], **bad_read}}
            with self.subTest(bad_read=bad_read), self.assertRaisesRegex(InvalidChange, reason):
                bridge.decide('faction', bad)
        self.assertIsNone(self.runtime.pending_kit_turn('faction')['plan'])
        performance = bridge.decide('faction', plan)
        self.assertNotIn('improv_read', performance['input'])
        self.assertNotIn('Harria', json.dumps(performance['input']['selected_move']))
        bridge.finish('faction', self.model.perform(performance['input']))
        self.assertEqual(self.runtime.recent_kit_turns()[0]['trace']['improv_read']['story_anchor'], 'level')

    def test_unsupported_actions_and_missing_modifier_do_not_consume_turn(self):
        for action in ('I attack Uktarl.', 'I pocket the silver ring.', 'I inspect the deck.'):
            with self.assertRaises(PendingRuling):
                self.agent.turn(action)
        agent = KitAgent(self.runtime, self.model, Room6CAdjudicator())
        with self.assertRaisesRegex(PendingRuling, 'Perception modifier'):
            agent.turn('I inspect the fresco.')
        self.assertEqual(self.runtime.load()[0], 0)
        self.assertEqual(self.model.plans, [])

    def test_failed_check_does_not_reveal_or_fabricate_discovery(self):
        agent = KitAgent(self.runtime, self.model, Room6CAdjudicator(
            perception=0, insight=0, roll=lambda: 1))
        result = agent.turn('I inspect the fresco.', 'failed-check')
        self.assertIn('1 vs DC 13', result['spoken'])
        self.assertNotIn('stone key', json.dumps(self.runtime.player_view()))
        self.assertEqual(self.runtime.recent_kit_turns()[0]['public_event'],
                         'Your careful look reveals nothing further. (1 vs DC 13)')

    def test_model_failure_does_not_reroll_same_uncommitted_check(self):
        bad = KitAgent(self.runtime, RecordingModel(leak=True),
                       Room6CAdjudicator(perception=0))
        with self.assertRaises(InvalidChange):
            bad.turn('I inspect the fresco.', 'failed-render')
        first_result = bad.model.plans[0]['accepted_public_event']
        good = KitAgent(self.runtime, RecordingModel(), Room6CAdjudicator(perception=0))
        accepted = good.turn('I inspect the fresco.', 'accepted-render')
        self.assertEqual(accepted['public_event'], first_result)

    def test_memory_can_be_hidden_for_ablation_without_erasing_it(self):
        self.agent.turn('I take a seat.', 'first')
        self.agent.turn('What are the stakes?', 'ablated', use_memory=False)
        self.assertEqual(self.model.plans[-1]['kit_state']['episodes'], [])
        self.assertEqual(self.runtime.load()[1]['kit']['episodes'][0]['turn_id'], 'first')

    def test_concurrent_world_commit_rejects_stale_personality_turn(self):
        self.model.on_perform = lambda: self.runtime.commit('interleaving', 0, [
            {'type': 'beat', 'tags': ['test'], 'evidence': 'Another adjudicator committed.'}])
        with self.assertRaises(StaleTurn):
            self.agent.turn('I sit down.', 'stale')
        self.assertEqual(self.runtime.load()[0], 1)
        self.assertEqual(self.runtime.recent_kit_turns(), [])

    def test_same_kit_commit_is_idempotent_and_cannot_be_rewritten(self):
        result = self.agent.turn('I take a seat.', 'fixed-id')
        record = self.runtime.recent_kit_turns()[0]
        event = {'type': 'beat', 'tags': ['social'],
                 'evidence': 'Player declared: I take a seat.. Resolution: You address the figures at the card table.'}
        self.assertEqual(self.runtime.commit_kit_turn('fixed-id', 0, [event], record), result['revision'])
        with self.assertRaises(InvalidChange):
            self.runtime.commit_kit_turn('fixed-id', 0, [event], {**record, 'spoken': 'changed'})
        self.assertEqual(len(self.runtime.load()[1]['kit']['episodes']), 1)

    def test_responses_adapter_uses_structured_calls_without_storage(self):
        model = OpenAIResponsesModel('test-model', api_key='test-key')
        response = {'status': 'completed', 'output': [
            {'content': [{'type': 'output_text', 'text': json.dumps({'segments': []})}]}]}
        captured = []

        def open_fake(request, timeout):
            captured.append(json.loads(request.data))
            return io.BytesIO(json.dumps(response).encode())

        with patch('runtime.kit_agent.urllib.request.urlopen', side_effect=open_fake):
            self.assertEqual(model.perform({'player_action': 'Hello'}), {'segments': []})
        self.assertFalse(captured[0]['store'])
        self.assertEqual(captured[0]['text']['format']['type'], 'json_schema')
        self.assertTrue(captured[0]['text']['format']['strict'])

    def test_chat_bridge_runs_without_api_key_and_resumes_between_stages(self):
        bridge = KitChatBridge(self.runtime, self.agent.adjudicator)
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            prepared = bridge.prepare('I pull up a chair and ask the stakes.', 'chat-turn')
            self.assertEqual(prepared['stage'], 'private_decision')
            self.assertIn('marked_deck', prepared['input']['dm_context']['dm_only']['unrevealed_facts'])
            self.assertEqual(self.runtime.load()[0], 0)
            self.runtime.close()
            self.runtime = Runtime(self.path)
            bridge.runtime = self.runtime

            plan = self.model.plan(prepared['input'])
            performance = bridge.decide('chat-turn', plan)
            self.assertEqual(performance['stage'], 'public_performance')
            self.assertNotIn('dm_only', performance['input'])
            self.assertNotIn('doppelganger', json.dumps(performance['input']).lower())
            self.assertEqual(self.runtime.load()[0], 0)
            self.runtime.close()
            self.runtime = Runtime(self.path)
            bridge.runtime = self.runtime

            result = bridge.finish('chat-turn', self.model.perform(performance['input']))
        self.assertEqual(result['revision'], 1)
        self.assertIn('Kit:', result['spoken'])
        self.assertEqual(self.runtime.recent_kit_turns()[0]['trace'], plan)
        self.assertEqual(self.runtime.load()[1]['kit']['episodes'][0]['turn_id'], 'chat-turn')
        with self.assertRaisesRegex(InvalidChange, 'No pending'):
            self.runtime.pending_kit_turn('chat-turn')

    def test_chat_bridge_rejects_leaks_and_locks_decision_before_performance(self):
        bridge = KitChatBridge(self.runtime, self.agent.adjudicator)
        prepared = bridge.prepare('I sit down.', 'guarded')
        plan = self.model.plan(prepared['input'])
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            bridge.decide('guarded', {**plan, 'public_brief': {
                **plan['public_brief'], 'tactic': 'Reveal the doppelganger.'}})
        self.assertIsNone(self.runtime.pending_kit_turn('guarded')['plan'])
        with self.assertRaisesRegex(InvalidChange, 'before performance'):
            bridge.finish('guarded', self.model.perform({}))
        performance = bridge.decide('guarded', plan)
        with self.assertRaisesRegex(InvalidChange, 'already fixed'):
            bridge.decide('guarded', {**plan, 'tone': 'warm'})
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            bridge.finish('guarded', RecordingModel(leak=True).perform(performance['input']))
        self.assertEqual(self.runtime.load()[0], 0)
        self.assertEqual(self.runtime.recent_kit_turns(), [])
        self.assertEqual(bridge.finish('guarded', self.model.perform(performance['input']))['revision'], 1)

    def test_chat_bridge_stale_turn_cannot_commit_after_other_world_change(self):
        bridge = KitChatBridge(self.runtime, self.agent.adjudicator)
        prepared = bridge.prepare('I sit down.', 'stale-chat')
        plan = self.model.plan(prepared['input'])
        performance = bridge.decide('stale-chat', plan)
        self.runtime.commit('interleaving', 0, [
            {'type': 'beat', 'tags': ['test'], 'evidence': 'Another adjudicator committed.'}])
        with self.assertRaises(StaleTurn):
            bridge.finish('stale-chat', self.model.perform(performance['input']))
        self.assertEqual(self.runtime.load()[0], 1)
        self.assertEqual(self.runtime.recent_kit_turns(), [])

    def test_stale_chat_decision_is_rejected_before_performance(self):
        bridge = KitChatBridge(self.runtime, self.agent.adjudicator)
        staged = bridge.prepare('What is this game?', 'old-stage')
        fast = bridge.prepare('I take a seat.', 'old-fast', one_pass=True)
        self.runtime.commit('interleaving', 0, [
            {'type': 'beat', 'tags': ['test'], 'evidence': 'The scene changed.'}])
        with self.assertRaises(StaleTurn):
            bridge.decide('old-stage', self.model.plan(staged['input']))
        with self.assertRaises(StaleTurn):
            bridge.complete('old-fast', {'decision': self.model.plan(fast['input']['private']),
                                         'performance': self.model.perform({})})
        self.assertEqual(self.runtime.recent_kit_turns(), [])

    def test_one_pass_chat_turn_commits_decision_and_speech_without_api_key(self):
        bridge = KitChatBridge(self.runtime, self.agent.adjudicator)
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            prepared = bridge.prepare('What are the stakes?', 'quick', one_pass=True)
            self.assertEqual(prepared['stage'], 'one_pass')
            self.assertNotIn('dm_only', prepared['input']['public'])
            self.assertIn('dm_only', prepared['input']['private']['dm_context'])
            plan = self.model.plan(prepared['input']['private'])
            with self.assertRaisesRegex(InvalidChange, 'Use complete'):
                bridge.decide('quick', plan)
            speech = self.model.perform({})
            result = bridge.complete('quick', {'decision': plan, 'performance': speech})
        self.assertEqual(result['revision'], 1)
        self.assertEqual(self.runtime.recent_kit_turns()[0]['trace'], plan)
        with self.assertRaisesRegex(InvalidChange, 'No pending'):
            self.runtime.pending_kit_turn('quick')

    def test_one_pass_rejection_keeps_world_uncommitted_and_decision_fixed(self):
        bridge = KitChatBridge(self.runtime, self.agent.adjudicator)
        prepared = bridge.prepare('I take a seat.', 'quick-guarded', one_pass=True)
        plan = self.model.plan(prepared['input']['private'])
        bad = RecordingModel(leak=True).perform({})
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            bridge.complete('quick-guarded', {'decision': plan, 'performance': bad})
        self.assertEqual(self.runtime.load()[0], 0)
        self.assertEqual(self.runtime.pending_kit_turn('quick-guarded')['plan'], plan)
        with self.assertRaisesRegex(InvalidChange, 'already fixed'):
            bridge.complete('quick-guarded', {'decision': {**plan, 'tone': 'warm'},
                                              'performance': self.model.perform({})})
        self.assertEqual(bridge.complete('quick-guarded', {
            'decision': plan, 'performance': self.model.perform({})})['revision'], 1)

    def test_opening_is_a_saved_scene_turn_with_an_actor_card(self):
        bridge = KitChatBridge(self.runtime)
        prepared = bridge.prepare(opening=True, one_pass=True, turn_id='entry')
        self.assertEqual(prepared['input']['private']['action_kind'], 'opening')
        public = prepared['input']['public']
        self.assertIn('entry_frame', public['performance_reference'])
        self.assertIn('vocal_signature', public['performance_reference']['actor_cards']['Dealer'])
        self.assertNotIn('doppelganger', json.dumps(public).lower())
        self.assertNotIn('marked deck', json.dumps(public).lower())
        plan = self.model.plan(prepared['input']['private'])
        plan.update(move='world_description', table_presence='quiet',
                    public_brief={
                        'objective': 'Frame the interruption of the card game.',
                        'tactic': 'Let the dealer weigh the visitor as a potential customer.',
                        'visible_cue': 'The dealer suspends a card above the table.',
                        'player_opening': 'The newcomer can speak, observe, or leave.',
                    })
        speech = {'segments': [
            {'speaker': 'Narrator', 'text': 'A card pauses between the dealer’s fingers. Four pale players sit among coins; north of them, a mountain carving hangs above a recessed stone tub.'},
            {'speaker': 'Dealer', 'text': 'A visitor. Care to make an offer?'}]}
        result = bridge.complete('entry', {'decision': plan, 'performance': speech})
        self.assertEqual(result['revision'], 1)
        self.assertEqual(self.runtime.recent_kit_turns()[0]['player_input'], '[scene entry]')
        self.assertEqual(self.runtime.load()[1]['rhythm'][0]['tags'], ['scene_entry'])
        self.assertNotIn('A newcomer has reached', result['spoken'])
        with self.assertRaisesRegex(InvalidChange, 'only before the first turn'):
            bridge.prepare(opening=True)
        bridge.prepare('Hello. What is this game?', turn_id='reply')
        self.assertEqual(self.runtime.load()[0], 1)

    def test_opening_requires_visible_scene_and_rejects_private_reveal(self):
        bridge = KitChatBridge(self.runtime)
        prepared = bridge.prepare(opening=True, turn_id='bad-entry')
        plan = self.model.plan(prepared['input'])
        plan.update(move='world_description', table_presence='quiet')
        payload = bridge.decide('bad-entry', plan)
        self.assertEqual(payload['input']['action_kind'], 'opening')
        with self.assertRaisesRegex(InvalidChange, 'world description'):
            bridge.finish('bad-entry', {'segments': [
                {'speaker': 'Dealer', 'text': 'Sit and play.'}]})
        with self.assertRaisesRegex(InvalidChange, 'narration and the dealer'):
            bridge.finish('bad-entry', {'segments': [
                {'speaker': 'Narrator', 'text': 'The game stops at the threshold.'}]})
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            bridge.finish('bad-entry', {'segments': [
                {'speaker': 'Narrator', 'text': 'The doppelganger watches from the card table.'},
                {'speaker': 'Dealer', 'text': 'Make an offer.'}]})
        self.assertEqual(self.runtime.load()[0], 0)


if __name__ == '__main__':
    unittest.main()
