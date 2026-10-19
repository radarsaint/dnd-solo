"""The engine-line policy after Nagatha's e3fc5a7 playtest (5 of 17 turns became engine text over
small style misses; the opening came out as 'The newcomer arrives: Dark hallway.'; a table-talk
turn echoed the question and never answered it).

- A narration that fails only on style (floors, sentence length, shape, fidelity: anything not a
  secret or the player's agency) keeps ONE retry; the engine line commits on the second failure.
- A secrecy failure (hidden information leaked) or an agency failure (acting for the player)
  commits the engine line at once.
- Every validator is classified (kit_agent.VALIDATOR_KINDS); the PR body lists them.
- The room opening and table talk get a real fallback, built from public state only.

Synthetic roadcamp room (tests/fixtures/rooms), a variant with no arrival line and a hidden fact,
hidden exit and hidden actor; the 06c fixture BridgeCase for the existing NIK_REPLY style miss.
NPC d20s pinned."""
import copy
import inspect
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_agent
from runtime.kit_agent import KitAgent, KitChatBridge, PerformanceRejected, RoomAdjudicator
from runtime.state_context import Runtime
from test_kit_agent import MIRROR, RecordingModel
from test_kit_combat_checkpoints import CAMP, NIK, without_shield
from test_kit_hardening import NIK_GREETING, NIK_REPLY, BridgeCase
from test_kit_open_ask import HIT

BROKEN = {'segments': [{'speaker': 'Nobody', 'text': 'Words.'}]}  # a shape miss: style
LEAKY = {'segments': [{'speaker': 'Narrator', 'text': 'The doppelganger smiles.'},
                      {'speaker': 'Dealer', 'text': 'Sit.'}]}  # names a private fact: secrecy
PUSHY = {'segments': [{'speaker': 'Narrator', 'text': 'You decide to sit down at the table.'},
                      {'speaker': 'Dealer', 'text': 'Sit.'}]}  # decides for the player: agency


class ValidatorKinds(unittest.TestCase):
    def test_every_validator_is_classified(self):
        called = set()
        for fn in (kit_agent.check_speech, kit_agent.checked_record):
            for module, name in re.findall(r'\b(?:(kit_\w+)\.)?(check_\w+)', inspect.getsource(fn)):
                called.add((module, name))
        called -= {('', 'check_variant'), ('', 'check_speech'), ('', 'check_secrecy_and_agency_first')}
        kinds = kit_agent.VALIDATOR_KINDS
        missing = sorted(f'{module}.{name}' for module, name in called
                         if f'{module}.{name}' not in kinds and name not in kinds)
        self.assertEqual(missing, [], 'every validator a narration faces has a kind')
        self.assertLessEqual(set(kit_agent.VALIDATOR_KINDS.values()), {'style', 'secrecy', 'agency'})

    def test_the_secrecy_and_agency_validators(self):
        kinds = kit_agent.VALIDATOR_KINDS
        for name in ('check_public_content', 'check_paraphrased_leaks', 'check_public_numbers',
                     'check_hidden_actors', 'check_sealed'):
            self.assertEqual(kinds[name], 'secrecy', name)
        for name in ('check_player_agency', 'check_player_identity'):
            self.assertEqual(kinds[name], 'agency', name)
        for name in ('check_scope', 'check_padding', 'check_voice_style', 'check_voice_presence'):
            self.assertEqual(kinds[name], 'style', name)


class StyleKeepsOneRetry(BridgeCase):
    def test_a_style_miss_is_retried_once_then_the_engine_line_commits(self):
        self.staged(NIK_GREETING, 'style', reply_to='Whats going on here?')
        with self.assertRaises(PerformanceRejected) as caught:
            self.bridge.finish('style', NIK_REPLY)
        message = str(caught.exception)
        self.assertIn('Exchange scope', message)
        self.assertIsNone(self.runtime.latest_kit_turn_id(), 'nothing committed: one retry')
        self.assertTrue(caught.exception.guidance['engine_line_next'])
        note = message.index(kit_agent.ENGINE_LINE_NOTE)
        self.assertRegex(message[:note], r'[.!?] $', 'a full stop before the note')
        result = self.bridge.finish('style', NIK_REPLY)
        self.assertTrue(result['engine_line'])
        self.assertIn('Exchange scope', result['last_rejection'])
        self.assertEqual(result['rejected_attempts'], 2)

    def test_secrecy_commits_the_engine_line_at_once(self):
        self.staged('I take a seat.', 'secret')
        result = self.bridge.finish('secret', LEAKY)
        self.assertTrue(result['engine_line'])
        self.assertEqual(result['rejected_attempts'], 1)
        self.assertIn('private fact', result['last_rejection'])
        self.assertNotIn('doppelganger', result['spoken'].casefold())

    def test_agency_commits_the_engine_line_at_once(self):
        self.staged('I take a seat.', 'pushy')
        result = self.bridge.finish('pushy', PUSHY)
        self.assertTrue(result['engine_line'])
        self.assertIn('Player agency', result['last_rejection'])

    def test_a_style_miss_then_a_secrecy_failure_commits(self):
        self.staged(NIK_GREETING, 'mixed', reply_to='Whats going on here?')
        with self.assertRaises(PerformanceRejected):
            self.bridge.finish('mixed', NIK_REPLY)
        self.assertTrue(self.bridge.finish('mixed', LEAKY)['engine_line'])

    def test_the_api_turn_retries_a_style_miss(self):
        class Broken(RecordingModel):
            def plan(inner, payload):
                return {**super().plan(payload), 'move': 'npc_reply', 'table_presence': 'quiet'}

            def perform(inner, payload, performance_variant='current'):
                return BROKEN

        result = KitAgent(self.runtime, Broken(), self.adjudicator).turn('I take a seat.', 'api-style')
        self.assertEqual(result['timing']['model_calls'], 1 + 2, 'one plan, a narration and its one retry')
        self.assertTrue(result['timing']['engine_line'])


def room(test, arrival=False):
    """The roadcamp room; without its arrival line, with a hidden fact, a secret exit and a hidden actor."""
    source = json.loads(CAMP.read_text())
    if not arrival:
        source['areas']['camp'].pop('arrival', None)
    source['facts']['cache'] = {'area': 'camp', 'visible': False,
                                'text': 'A strongbox of stolen silver is buried under the wagon.'}
    source['exits']['gully'] = {'name': 'the gully', 'areas': ['camp', 'road'], 'secret': True,
                                'labels': {'camp': 'A hidden gully path behind the rocks.', 'road': 'A gully.'}}
    source['actors']['lookout'] = {**copy.deepcopy(source['actors']['cutthroat_b']), 'name': 'Hidden lookout',
                                   'visible': False}
    temp = tempfile.TemporaryDirectory()
    test.addCleanup(temp.cleanup)
    runtime = Runtime(Path(temp.name) / 'kit.sqlite')
    test.addCleanup(runtime.close)
    with mock.patch('runtime.state_context.secrets.token_hex', return_value='7' * 32):
        runtime.initialize(source, 'camp')
    runtime.set_player_sheet(without_shield(NIK))
    return runtime, RoomAdjudicator(roll=lambda: 2, source=runtime.source())


CAMP_FLAT = {'segments': [{'speaker': 'Narrator', 'text': 'A strongbox of stolen silver lies under the wagon.'}]}


def twice(test, bridge, turn_id, plan):
    """A style miss gets its one retry; the second miss commits the engine line."""
    with test.assertRaises(PerformanceRejected) as caught:
        bridge.complete(turn_id, {'decision': plan, 'performance': CAMP_FLAT})
    test.assertEqual(caught.exception.guidance['rejected_attempts'], 1)
    return bridge.complete(turn_id, {'decision': plan, 'performance': CAMP_FLAT})
HIDDEN = ('strongbox', 'silver', 'gully', 'lookout')


class OpeningFallback(unittest.TestCase):
    def opened(self, arrival=False):
        runtime, adjudicator = room(self, arrival)
        bridge = KitChatBridge(runtime, adjudicator)
        prepared = bridge.prepare(opening=True, one_pass=True, turn_id='open')
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='world_description', table_presence='quiet', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(scope='feature', reply_to='none', mirror=MIRROR)
        result = twice(self, bridge, 'open', plan)
        self.assertTrue(result['engine_line'])
        return result

    def test_the_opening_fallback_frames_the_room_from_public_state(self):
        spoken = self.opened()['spoken']
        self.assertNotIn('The newcomer arrives', spoken)
        for seen in ('Roadside camp', 'cookfire', 'canvas is slashed', 'Bandit captain', 'road runs on'):
            self.assertIn(seen.casefold(), spoken.casefold(), seen)
        for hidden in HIDDEN:
            self.assertNotIn(hidden, spoken.casefold(), hidden)

    def test_the_rooms_own_arrival_line_leads(self):
        spoken = self.opened(arrival=True)['spoken']
        self.assertTrue(spoken.startswith('Narrator: A stranger walks into the firelight.'), spoken)
        self.assertIn('cookfire', spoken)


class TableTalkFallback(unittest.TestCase):
    def talk(self, question, mid_ask=False):
        runtime, adjudicator = room(self)
        if mid_ask:
            revision, state = runtime.load()
            result = adjudicator.resolve(HIT, revision, state)
            runtime.commit(f't{revision}', revision, list(result.events))
        bridge = KitChatBridge(runtime, adjudicator)
        prepared = bridge.prepare(question, 'talk', one_pass=True, table_talk=not mid_ask)
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='world_description', table_presence='brief', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        result = twice(self, bridge, 'talk', plan)
        self.assertTrue(result['engine_line'])
        return result['spoken']

    def assertAnswers(self, spoken, *wanted):
        self.assertTrue(spoken.startswith('Kit: '), spoken)
        for word in wanted:
            self.assertIn(word.casefold(), spoken.casefold(), word)
        for hidden in HIDDEN:
            self.assertNotIn(hidden, spoken.casefold(), hidden)
        self.assertNotIn('Table talk to Kit', spoken, 'an answer, not an echo')

    def test_how_many_exits_is_answered_from_the_known_exits(self):
        self.assertAnswers(self.talk('How many exits does this place have?'), 'one way out', 'road runs on')

    def test_who_is_here_is_answered_from_the_visible_actors(self):
        self.assertAnswers(self.talk("Who's here with me?"), 'bandit captain', 'wagon-side cutthroat')

    def test_mid_ask_a_question_is_answered_and_the_ask_is_restated(self):
        spoken = self.talk('Wait, before I roll: how many are still standing?', mid_ask=True)
        self.assertAnswers(spoken, 'three', 'still waits for its damage roll')


if __name__ == '__main__':
    unittest.main()


class ReviewAt79196b5(unittest.TestCase):
    """Nagatha's #127 review at 79196b5: (1) table talk that is no question gets the engine's own
    line, and an answer keeps to the topic asked; (2) only performance rejections count toward the
    style retry; (3) secrecy and agency run before style, so a mixed failure commits at once; the
    'of: An' capitalisation."""

    def test_a_correction_gets_the_engines_own_line_not_the_board(self):
        for words in ('No wait, that 5 was for the captain', '5, and I yell at the captain'):
            with self.subTest(words=words):
                spoken = TableTalkFallback.talk(self, words, mid_ask=True)
                self.assertTrue(spoken.startswith('Narrator: '), spoken)
                self.assertNotIn('unhurt', spoken)
                self.assertNotIn('way out', spoken)
                self.assertIn('Table talk to Kit', spoken, 'the engine line')
                self.assertIn('still waits for its damage roll', spoken)

    def test_a_question_on_no_known_topic_gets_the_engines_own_line(self):
        spoken = TableTalkFallback.talk(self, "What's your favourite colour?")
        self.assertTrue(spoken.startswith('Narrator: '), spoken)
        self.assertNotIn('way out', spoken)

    def test_a_big_pack_is_grouped_by_its_wound_state(self):
        wounds = {f'Giant rat {n}': 'unhurt' for n in range(1, 11)}
        wounds['Giant rat 4'] = 'hurt'
        view = {'fight': {'status': 'running', 'wounds': wounds}}
        answer = kit_agent.table_talk_answer(view, 'How many are still standing?')
        self.assertEqual(answer.count('unhurt'), 1, answer)
        self.assertIn('Ten still standing', answer)
        self.assertIn('hurt: Giant rat 4', answer)

    def test_an_exit_line_after_a_colon_is_not_capitalised(self):
        view = {'exits': [{'description': 'An iron door stands shut.'}, {'description': 'The road runs on.'}]}
        answer = kit_agent.table_talk_answer(view, 'How many exits are there?')
        self.assertIn('Two ways out that you know of: an iron door stands shut; the road runs on.', answer)

    def test_a_decision_rejection_does_not_spend_the_style_retry(self):
        runtime, adjudicator = room(self)
        bridge = KitChatBridge(runtime, adjudicator)
        prepared = bridge.prepare(opening=True, one_pass=True, turn_id='open')
        plan = RecordingModel().plan(prepared['input']['private'])
        with self.assertRaises(PerformanceRejected) as caught:  # 'uktarl' is not in this room
            bridge.complete('open', {'decision': plan, 'performance': CAMP_FLAT})
        self.assertFalse(caught.exception.guidance['engine_line_next'])
        plan.update(move='world_description', table_presence='quiet', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(scope='feature', reply_to='none', mirror=MIRROR)
        with self.assertRaises(PerformanceRejected) as caught:
            bridge.complete('open', {'decision': plan, 'performance': CAMP_FLAT})
        self.assertTrue(caught.exception.guidance['engine_line_next'])
        result = bridge.complete('open', {'decision': plan, 'performance': CAMP_FLAT})
        self.assertTrue(result['engine_line'])
        self.assertEqual(result['rejected_attempts'], 3, 'all rejections are still counted')


class SecrecyBeforeStyle(BridgeCase):
    def test_a_leak_in_a_malformed_narration_commits_at_once(self):
        self.staged('I take a seat.', 'mixed')
        result = self.bridge.finish('mixed', {'segments': [{'speaker': 'Nobody', 'text': 'The doppelganger smiles.'}]})
        self.assertTrue(result['engine_line'])
        self.assertIn('secrecy', result['rejection_kinds'])

    def test_acting_for_the_player_in_a_narration_missing_its_move_commits_at_once(self):
        self.staged('I take a seat.', 'pushy')
        result = self.bridge.finish('pushy', {'segments': [{'speaker': 'Narrator',
                                                            'text': 'You decide to sit down at the table.'}]})
        self.assertTrue(result['engine_line'])
        self.assertIn('agency', result['rejection_kinds'])
