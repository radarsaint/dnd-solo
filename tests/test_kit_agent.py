import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.kit_agent import (KitAgent, OpenAIResponsesModel, PendingRuling,
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
            'move': 'kit_comment_then_npc',
            'public_brief': ('Reveal the doppelganger.' if self.leaky_brief else
                             'Kit briefly enjoys the social gamble; the dealer offers a bargain and leaves the choice open.'),
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
        self.assertNotIn('dm_only', self.model.performances[0])
        self.assertNotIn('doppelganger', json.dumps(self.model.performances[0]).lower())
        self.assertNotIn('uktarl', json.dumps(self.model.performances[0]).lower())
        self.assertEqual(self.model.performances[0]['selected_move']['focus_actor'], 'Dealer')
        self.assertIn('Kit:', result['spoken'])
        self.assertIn('Dealer:', result['spoken'])
        self.assertEqual(self.runtime.load()[1]['kit']['episodes'][0]['turn_id'], 'first')
        self.assertEqual(self.runtime.recent_kit_turns()[0]['trace']['memory_refs'], [])
        self.runtime.close()
        self.runtime = Runtime(self.path)
        self.agent.runtime = self.runtime
        self.assertEqual(self.runtime.recent_kit_turns()[0]['spoken'], result['spoken'])
        self.agent.turn('What if I offered you a deal?', 'second')
        self.assertEqual(self.model.plans[-1]['kit_state']['episodes'][0]['turn_id'], 'first')
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


if __name__ == '__main__':
    unittest.main()
