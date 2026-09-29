import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import kit_agent
from runtime.kit_agent import (EXCHANGE_MIN_ACTOR_WORDS, KitAgent, KitChatBridge,
                               OpenAIResponsesModel, PendingRuling, Room6CAdjudicator, room_intent)
from runtime.state_context import InvalidChange, Runtime, StaleTurn


FIXTURE = Path(__file__).parent / 'fixtures/level_01_area_06c.json'

KIT_CHOICE = 'Kit favors the roleplay opening and lets the dealer try a bargain.'
KIT_FOCUS = 'Spotlight the dealer sizing up the visitor’s nerve rather than the passage price.'

# A performed exchange that clears the flat-reply floor. Its length is not a
# quality claim; it only gives the format tests a turn the guard accepts.
EXCHANGE_SPEECH = {'segments': [
    {'speaker': 'Kit', 'text': 'That is a choice.'},
    {'speaker': 'Narrator', 'text': 'The dealer lets a card hang between two fingers while the others go still.'},
    {'speaker': 'Dealer', 'text': ('Sit, then, and let us see what kind of guest you are. Ten gold buys '
                                   'safe passage, but a player who sits at this table usually wants more '
                                   'than a door. So tell me plainly, friend: what would you wager tonight?')},
]}
QUIET_EXCHANGE_SPEECH = {'segments': EXCHANGE_SPEECH['segments'][1:]}

# The saved Nik reply from tests/playtests/2026-09-26-area-06c-nik.md, verbatim.
NIK_GREETING = "Hi, I'm Nik. I wasn't expecting to find people gambling. Whats going on here?"
NIK_REPLY = {'segments': [
    {'speaker': 'Narrator', 'text': 'The dealer keeps a hand on the deck and gives you his attention.'},
    {'speaker': 'Dealer', 'text': ('“Gambling? Cards, Nik. Passage is ten gold a head. If you came for '
                                   'something besides a game or a way through, I’m listening.”')},
]}


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
                'kit_choice': KIT_CHOICE,
            },
            'move': 'kit_comment_then_npc',
            'public_brief': {
                'objective': 'Invite the visitor to commit to the game or a passage bargain.',
                'tactic': ('Reveal the doppelganger.' if self.leaky_brief else
                           'The dealer treats the question as an opening bid.'),
                'visible_cue': 'The dealer suspends a card over the table.',
                'player_opening': 'The visitor may ask about the terms, play, or leave.',
                'reply_to': ('none' if payload['action_kind'] == 'opening'
                             else payload['player_action']),
                'scope': 'feature' if payload['action_kind'] == 'opening' else 'exchange',
                'kit_focus': KIT_FOCUS,
                'callback': 'none',
            },
            'focus_actor': 'uktarl',
            'table_presence': 'brief', 'tone': 'wry',
            'player_note': {'note': 'none', 'evidence_turns': [], 'replaces': 'none'},
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
        return json.loads(json.dumps(EXCHANGE_SPEECH))


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
        # reply_to quotes the player, who named Harria; Kit's own direction must not.
        direction = {**performance['input']['selected_move'],
                     'brief': {k: v for k, v in performance['input']['selected_move']['brief'].items()
                               if k != 'reply_to'}}
        self.assertNotIn('Harria', json.dumps(direction))
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

    def test_kit_expression_trial_changes_only_staged_instructions(self):
        bridge = KitChatBridge(self.runtime, self.agent.adjudicator)
        current_prepared = bridge.prepare('Hi. What is going on here?', 'identity-current')
        trial_prepared = bridge.prepare('Hi. What is going on here?', 'identity-trial')
        self.assertEqual(current_prepared['input'], trial_prepared['input'])
        plan = self.model.plan(current_prepared['input'])
        current = bridge.decide('identity-current', plan)
        trial = bridge.decide('identity-trial', plan, 'kit_expression_v1')
        self.assertEqual(current['input'], trial['input'])
        self.assertEqual(current['schema'], trial['schema'])
        self.assertNotEqual(current['instructions'], trial['instructions'])
        self.assertEqual(trial['performance_variant'], 'kit_expression_v1')
        self.assertNotIn('dm_only', json.dumps(trial['input']))
        self.assertEqual(self.runtime.load()[0], 0)
        with self.assertRaisesRegex(InvalidChange, 'Unknown performance variant'):
            bridge.decide('identity-trial', plan, 'invented')

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
                        'reply_to': 'none', 'scope': 'feature',
                        'kit_focus': 'Let the interrupted game, not the room inventory, greet the newcomer.',
                        'callback': 'none',
                    })
        speech = {'segments': [
            {'speaker': 'Narrator', 'text': ('A card pauses between the dealer’s fingers mid-deal. Four pale '
                                             'players sit among scattered coins and a silver ring, and one of '
                                             'them slowly turns to look at the doorway. North of the table, a '
                                             'carved mountain crowded with tiny dwarves hangs above a recessed '
                                             'stone tub.')},
            {'speaker': 'Dealer', 'text': ('Well now. A visitor, and on such a slow night. Come in, come in; '
                                           'the table is far friendlier than the corridor. Care to make an offer, '
                                           'or shall I name one?')}]}
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


class KitFocusAndScopeTests(unittest.TestCase):
    """Regression tests for the kit_focus brief and the flat-reply guard."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.model = RecordingModel()
        self.adjudicator = Room6CAdjudicator(perception=0, insight=0, roll=lambda: 20)
        self.bridge = KitChatBridge(self.runtime, self.adjudicator)

    def _prepared_plan(self, action, turn_id, **brief):
        prepared = self.bridge.prepare(action, turn_id)
        plan = self.model.plan(prepared['input'])
        plan['public_brief'].update(brief)
        return prepared, plan

    def test_exact_nik_reply_is_rejected_as_a_flat_exchange(self):
        prepared, plan = self._prepared_plan(NIK_GREETING, 'nik', reply_to='Whats going on here?')
        plan.update(move='npc_reply', table_presence='quiet')
        self.bridge.decide('nik', plan)
        with self.assertRaisesRegex(InvalidChange, rf'Dealer spoke 23 words \(floor {EXCHANGE_MIN_ACTOR_WORDS}\)'):
            self.bridge.finish('nik', NIK_REPLY)
        self.assertEqual(self.runtime.load()[0], 0)
        self.assertEqual(self.runtime.kit_timing('nik')['rejected_attempts'], 1)
        self.assertIn('Exchange scope', self.runtime.kit_timing('nik')['last_rejection'])
        # The fixed decision still accepts a performance that actually plays the exchange.
        self.assertEqual(self.bridge.finish('nik', QUIET_EXCHANGE_SPEECH)['revision'], 1)

    def test_one_line_roll_prompt_is_accepted_as_a_call(self):
        prepared, plan = self._prepared_plan(
            'Can I tell if they are friendly?', 'roll', reply_to='Can I tell if they are friendly',
            scope='call', kit_focus='Rule plainly and hand the moment back to the player.')
        plan.update(move='ruling', table_presence='brief', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        self.bridge.decide('roll', plan)
        result = self.bridge.finish('roll', {'segments': [
            {'speaker': 'Kit', 'text': 'Give me a Wisdom (Insight) check.'}]})
        self.assertEqual(result['spoken'], 'Kit: Give me a Wisdom (Insight) check.')

    def test_call_scope_cannot_run_long_or_cover_an_npc_reply(self):
        prepared, plan = self._prepared_plan('Can I tell if they are friendly?', 'long-call',
                                             reply_to='friendly', scope='call')
        with self.assertRaisesRegex(InvalidChange, 'Call scope is only for'):
            self.bridge.decide('long-call', plan)  # kit_comment_then_npc with a dealer focus
        plan.update(move='ruling', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        self.bridge.decide('long-call', plan)
        with self.assertRaisesRegex(InvalidChange, 'Call scope ran long'):
            self.bridge.finish('long-call', {'segments': [
                {'speaker': 'Kit', 'text': 'Roll Insight. ' + 'Very long table chatter. ' * 20}]})

    def test_reply_to_must_quote_the_players_own_words(self):
        prepared, plan = self._prepared_plan(NIK_GREETING, 'misquote',
                                             reply_to='What does the passage cost?')
        with self.assertRaisesRegex(InvalidChange, 'reply_to must quote'):
            self.bridge.decide('misquote', plan)
        # Case, whitespace, and curly apostrophes do not matter; the words do.
        plan['public_brief']['reply_to'] = 'I WASN’T expecting  to find people gambling'
        self.bridge.decide('misquote', plan)

    def test_player_quoting_a_secret_word_does_not_fail_the_brief(self):
        prepared, plan = self._prepared_plan('I accuse that player of being a doppelganger.', 'accuse',
                                             reply_to='being a doppelganger')
        self.bridge.decide('accuse', plan)
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            self.bridge.finish('accuse', {'segments': [
                {'speaker': 'Kit', 'text': 'Bold.'},
                {'speaker': 'Narrator', 'text': 'The doppelganger smiles.'},
                {'speaker': 'Dealer', 'text': 'Sit down.'}]})

    def test_kit_focus_reaches_performer_but_private_choice_and_cause_do_not(self):
        agent = KitAgent(self.runtime, self.model, self.adjudicator)
        agent.turn(NIK_GREETING, 'focus')
        plan = self.runtime.recent_kit_turns()[0]['trace']
        performed = json.dumps(self.model.performances[0], ensure_ascii=False)
        self.assertEqual(self.model.performances[0]['selected_move']['brief']['kit_focus'], KIT_FOCUS)
        self.assertEqual(self.model.performances[0]['selected_move']['brief']['reply_to'], NIK_GREETING)
        self.assertNotIn(KIT_CHOICE, performed)
        self.assertNotIn(plan['appraisal']['cause'], performed)
        self.assertNotIn('improv_read', self.model.performances[0])
        self.assertNotIn('appraisal', self.model.performances[0]['selected_move'])
        # Kit's focus is remembered with the episode for her later decisions.
        self.assertEqual(self.runtime.load()[1]['kit']['episodes'][0]['brief']['kit_focus'], KIT_FOCUS)

    def test_kit_focus_must_be_public_short_direction(self):
        prepared, plan = self._prepared_plan(NIK_GREETING, 'bad-focus')
        for focus, reason in [
            (KIT_CHOICE, 'copies private kit_choice'),
            ('Have the dealer say “Ten gold, friend.”', 'not quoted dialogue'),
            ('x' * 201, 'Invalid public performance brief|exceeds 200'),
        ]:
            bad = {**plan, 'public_brief': {**plan['public_brief'], 'kit_focus': focus}}
            with self.subTest(focus=focus[:30]), self.assertRaisesRegex(InvalidChange, reason):
                self.bridge.decide('bad-focus', bad)
        leaky = {**plan, 'public_brief': {**plan['public_brief'],
                                          'kit_focus': 'Hint that the deck is marked.'}}
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            self.bridge.decide('bad-focus', leaky)

    def test_opening_must_be_feature_scope_with_no_reply_to(self):
        prepared = self.bridge.prepare(opening=True, turn_id='entry')
        plan = self.model.plan(prepared['input'])
        plan.update(move='world_description', table_presence='quiet')
        with self.assertRaisesRegex(InvalidChange, 'feature scope'):
            self.bridge.decide('entry', {**plan, 'public_brief': {**plan['public_brief'], 'scope': 'exchange'}})
        with self.assertRaisesRegex(InvalidChange, 'reply_to must be none'):
            self.bridge.decide('entry', {**plan, 'public_brief': {**plan['public_brief'],
                                                                  'reply_to': '[scene entry]'}})
        self.bridge.decide('entry', plan)
        with self.assertRaisesRegex(InvalidChange, 'Feature scope was flat'):
            self.bridge.finish('entry', {'segments': [
                {'speaker': 'Narrator', 'text': 'Four pale figures play cards.'},
                {'speaker': 'Dealer', 'text': 'Ten gold.'}]})

    def test_retry_carries_the_specific_rejection_reason(self):
        flat = iter([NIK_REPLY, QUIET_EXCHANGE_SPEECH])
        seen = []

        class FlatThenFixed(RecordingModel):
            def plan(inner, payload):
                return {**super().plan(payload), 'move': 'npc_reply', 'table_presence': 'quiet'}

            def perform(inner, payload):
                seen.append(payload.get('retry_instruction'))
                return json.loads(json.dumps(next(flat)))

        agent = KitAgent(self.runtime, FlatThenFixed(), self.adjudicator)
        result = agent.turn(NIK_GREETING, 'retry')
        self.assertIsNone(seen[0])
        self.assertIn('Exchange scope: the Dealer spoke 23 words', seen[1])
        self.assertEqual(result['timing']['model_calls'], 3)
        self.assertEqual(len(result['timing']['rejections']), 1)

    def test_latency_is_recorded_outside_the_turn_hash(self):
        agent = KitAgent(self.runtime, self.model, self.adjudicator)
        result = agent.turn('I take a seat.', 'timed')
        timing = self.runtime.kit_timing('timed')
        self.assertEqual(timing['outcome'], 'committed')
        self.assertEqual(timing['model_calls'], 2)
        self.assertGreaterEqual(timing['received_to_done_s'], 0)
        record = self.runtime.recent_kit_turns()[0]
        self.assertNotIn('timing', record)
        self.assertNotIn('timing', record['trace'])
        # Telemetry changes never alter the idempotent commit.
        self.runtime.record_kit_timing('timed', note='later edit')
        event = {'type': 'beat', 'tags': ['social'], 'evidence':
                 'Player declared: I take a seat.. Resolution: You address the figures at the card table.'}
        self.assertEqual(self.runtime.commit_kit_turn('timed', 0, [event], record), result['revision'])

    def test_staged_bridge_records_prepare_to_commit_time(self):
        prepared, plan = self._prepared_plan('I take a seat.', 'staged')
        payload = self.bridge.decide('staged', plan)
        result = self.bridge.finish('staged', self.model.perform(payload['input']))
        self.assertEqual(result['timing']['mode'], 'staged')
        self.assertGreaterEqual(result['timing']['prepare_to_commit_s'], 0)
        self.assertEqual(self.runtime.recent_kit_timings()[-1]['turn_id'], 'staged')



class ChatBridgeCarrierTests(unittest.TestCase):
    """The ChatGPT host path must carry reply_to, scope, and kit_focus end to end."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.model = RecordingModel()
        self.bridge = KitChatBridge(self.runtime, Room6CAdjudicator(perception=0, insight=0))

    def assert_host_is_told_how_to_fill_the_carrier(self, instructions, brief_schema):
        self.assertEqual(set(brief_schema['required']) & {'reply_to', 'scope', 'kit_focus'},
                         {'reply_to', 'scope', 'kit_focus'})
        for phrase in ('reply_to', 'copy verbatim', 'kit_focus', 'derived from your goal and kit_choice',
                       'scope', 'own motives'):
            self.assertIn(phrase, instructions)

    def test_staged_bridge_carries_focus_fields_to_the_performer(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'staged')
        self.assert_host_is_told_how_to_fill_the_carrier(
            prepared['instructions'], prepared['schema']['properties']['public_brief'])
        self.assertIn('exchange', prepared['performance_limits'])
        self.assertIn('same turn_id', prepared['host_retry'])
        plan = self.model.plan(prepared['input'])
        plan.update(move='npc_reply', table_presence='quiet')
        performance = self.bridge.decide('staged', plan)
        brief = performance['input']['selected_move']['brief']
        self.assertEqual((brief['reply_to'], brief['scope'], brief['kit_focus']),
                         (NIK_GREETING, 'exchange', KIT_FOCUS))
        self.assertNotIn(KIT_CHOICE, json.dumps(performance['input'], ensure_ascii=False))
        for phrase in ('reply_to', 'kit_focus', 'grants no authority', 'mouthpieces'):
            self.assertIn(phrase, performance['instructions'])
        self.assertEqual(performance['performance_limits']['selected_scope'], 'exchange')
        self.assertIn(str(EXCHANGE_MIN_ACTOR_WORDS), performance['performance_limits']['rule'])
        trial = self.bridge.prepare(NIK_GREETING, 'staged-trial')
        trial_perf = self.bridge.decide('staged-trial', self.model.plan(trial['input']), 'kit_expression_v1')
        self.assertIn('kit_focus', trial_perf['instructions'])
        with self.assertRaisesRegex(InvalidChange, 'Exchange scope'):
            self.bridge.finish('staged', NIK_REPLY)
        self.assertEqual(self.bridge.finish('staged', QUIET_EXCHANGE_SPEECH)['revision'], 1)

    def test_one_pass_bridge_carries_and_checks_focus_fields(self):
        prepared = self.bridge.prepare(NIK_GREETING, 'fast', one_pass=True)
        self.assert_host_is_told_how_to_fill_the_carrier(
            prepared['instructions'],
            prepared['schema']['properties']['decision']['properties']['public_brief'])
        self.assertIn('Do not copy improv_read', prepared['instructions'])
        self.assertIn('feature', prepared['performance_limits'])
        plan = self.model.plan(prepared['input']['private'])
        plan.update(move='npc_reply', table_presence='quiet')
        misquoted = {**plan, 'public_brief': {**plan['public_brief'], 'reply_to': 'How much to pass?'}}
        with self.assertRaisesRegex(InvalidChange, 'reply_to must quote'):
            self.bridge.complete('fast', {'decision': misquoted, 'performance': QUIET_EXCHANGE_SPEECH})
        with self.assertRaisesRegex(InvalidChange, 'Exchange scope'):
            self.bridge.complete('fast', {'decision': plan, 'performance': NIK_REPLY})
        result = self.bridge.complete('fast', {'decision': plan, 'performance': QUIET_EXCHANGE_SPEECH})
        self.assertEqual(result['revision'], 1)
        self.assertEqual(self.runtime.recent_kit_turns()[0]['trace']['public_brief']['kit_focus'], KIT_FOCUS)

    def _cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['kit_agent', *argv, '--db', str(self.path)]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = kit_agent.main()
        return code, out.getvalue(), err.getvalue()

    def test_cli_rejection_tells_the_host_how_to_retry(self):
        self.runtime.close()
        code, out, _ = self._cli('prepare', '--action', NIK_GREETING, '--turn-id', 'cli')
        self.assertEqual(code, 0)
        prepared = json.loads(out)
        plan = self.model.plan(prepared['input'])
        plan.update(move='npc_reply', table_presence='quiet')
        temp = Path(self.path).parent
        (temp / 'plan.json').write_text(json.dumps(plan))
        (temp / 'flat.json').write_text(json.dumps(NIK_REPLY))
        (temp / 'good.json').write_text(json.dumps(QUIET_EXCHANGE_SPEECH))
        self.assertEqual(self._cli('decide', '--turn-id', 'cli', '--input-file', str(temp / 'plan.json'))[0], 0)
        code, _, err = self._cli('finish', '--turn-id', 'cli', '--input-file', str(temp / 'flat.json'))
        self.assertEqual(code, 2)
        rejected = json.loads(err)
        self.assertTrue(rejected['decision_fixed'])
        self.assertIn('Exchange scope: the Dealer spoke 23 words', rejected['retry_instruction'])
        self.assertIn('same turn_id', rejected['host_retry'])
        code, out, _ = self._cli('finish', '--turn-id', 'cli', '--input-file', str(temp / 'good.json'))
        self.assertEqual((code, json.loads(out)['revision']), (0, 1))
        self.runtime = Runtime(self.path)


if __name__ == '__main__':
    unittest.main()
