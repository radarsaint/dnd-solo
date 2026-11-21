"""v0.11.0 turn spine: moves, open asks, the skill picker, passives first, the speaking contract.

Modelled on a live run's turns 4-7 (an Investigation call for scanning the brush, a passive
ignored, a roll plus a question answered only with "You go ahead.", a stray question).
Original synthetic source only. No published adventure text.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from runtime import kit_adventure, kit_moves, kit_perform, kit_skills, kit_skim
from runtime.kit_agent import (SIMPLE_ACT_LINE, KitChatBridge, RoomAdjudicator, check_not_only_roll,
                               check_no_internal_labels, start_session, turn_spine)
from runtime.state_context import InvalidChange, Runtime

from test_kit_scene_contract_gpt import ENCOUNTER, FICTION, LOW_SHEET, SCENE, SHEET

CONDITION = 'If the bandits go unnoticed, they spring from their hiding place and attack.'
SCAN = 'I stay back, scanning the brush for movement.'


class Scene(unittest.TestCase):
    """A synthetic road with two hidden bandits (SRD stat blocks, Stealth +1)."""

    def _start(self, sheet):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'kit.sqlite'
        scene = copy.deepcopy(SCENE)
        scene['pressures'][0].update(quote=CONDITION, status='conditional', activation='failed_notice')
        kit_adventure.ingest_adventure(db, text='1. The Road\n> ' + FICTION + '\n' + ENCOUNTER + '\n' +
                                       CONDITION + '\n2. The Tower\n> A bell rings at a distant tower.\n')
        response = kit_skim.accept(db, {'burst': FICTION, 'source_quote': FICTION, 'page_start': 1,
                                        'page_end': 1, 'alt_starts': [], 'design_start_name': 'The Road',
                                        'scene': scene})
        self.assertEqual(response.get('stage'), 'skim_accepted', response)
        start_session(str(db), str(sheet))
        self.runtime = Runtime(str(db))
        self.addCleanup(self.runtime.close)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10))
        self.bridge.prepare('Yes.')

    def say(self, line):
        result = self.bridge.prepare(line, one_pass=True)
        spoken = result.get('spoken') or ''
        public = ((result.get('input') or {}).get('private') or {}).get('accepted_public_event') or ''
        return result, spoken + ' ' + public

    def pending(self):
        return self.runtime.load()[1].get('pending_check')

    def call_old(self, skill):
        """The live bug's state: an Investigation roll already called for scanning the brush."""
        revision, _ = self.runtime.load()
        self.runtime.commit('old-call', revision, [{'type': 'pending_check', 'check': {
            'skill': skill, 'ability': 'wis' if skill == 'perception' else 'int', 'target': 'none', 'called_turn': 'revision 2',
            'action': SCAN}, 'evidence': 'An older call, before the skill picker.'}])


class ScanningCallsPerception(Scene):
    """Live turn 4: scanning the brush for movement was called as Investigation."""

    def test_scanning_lines_pick_perception(self):
        for line in (SCAN, 'I stop fifty feet short and watch the thickets for anyone hiding.', 'I keep watch on the treeline.',
                     'I look around for anything moving in the thickets.', 'I listen for footsteps.'):
            self.assertEqual(kit_skills.skill_for_intent(line), 'perception', line)
            self.assertEqual(kit_moves.pick_skill(line, 'look')[0], 'perception', line)

    def test_searching_an_object_stays_investigation(self):
        for line in ('I search the desk drawers for a false bottom.', 'I examine the lock for scratches.'):
            self.assertNotEqual(kit_moves.pick_skill(line, 'look')[0], 'perception', line)

    def test_the_opening_call_for_scanning_is_perception(self):
        self._start(LOW_SHEET)
        result, text = self.say(SCAN)
        self.assertEqual(result['stage'], 'called_roll', result)
        self.assertIn('Roll Perception', text)
        self.assertNotIn('Investigation', text)
        self.assertEqual(self.pending()['skill'], 'perception')


class PassiveFirst(Scene):
    """Live turn 4: Nik's passive Perception was never used."""

    def test_a_passive_that_meets_their_stealth_spots_them_with_no_roll(self):
        self._start(SHEET)  # passive 14 at ease; SRD bandits are Stealth +1 (11)
        result, text = self.say(SCAN)
        self.assertNotEqual(result['stage'], 'called_roll', text)
        self.assertIn('You spot', text)
        self.assertIsNone(self.pending())
        self.assertFalse(self.runtime.load()[1].get('combat'))

    def test_a_low_roll_never_notices_less_than_the_passive(self):
        self._start(SHEET)
        self.call_old('perception')
        result, text = self.say('3')
        self.assertIn('You spot', text)
        self.assertNotIn('initiative', text.casefold())

    def test_passive_and_floor_need_a_known_stealth(self):
        self.assertEqual(kit_moves.known_stealth({'stealth': 6}), 6)
        self.assertEqual(kit_moves.known_stealth({'skills': {'stealth': 4}}), 4)
        self.assertIsNone(kit_moves.known_stealth({}))
        self.assertEqual(kit_moves.notice_total(3, 14), 14)
        self.assertEqual(kit_moves.notice_total(18, 14), 18)


class RollPlusQuestion(Scene):
    """Live turn 5: "Perception? I rolled a 15." got only "You go ahead." and moved the PC."""

    def test_roll_wrapped_in_a_question_resolves_the_stored_act(self):
        self._start(LOW_SHEET)
        self.say(SCAN)
        result, text = self.say('Perception? I rolled a 15.')
        self.assertIn('You spot', text)
        self.assertNotIn('go ahead', text.casefold())
        self.assertFalse(text.strip().startswith(SIMPLE_ACT_LINE))
        self.assertIsNone(self.pending())

    def test_pushback_on_an_investigation_call_is_accepted(self):
        self._start(LOW_SHEET)
        self.call_old('investigation')
        result, text = self.say("Shouldn't scanning the brush be Perception?")
        self.assertIn('Perception', text)
        self.assertNotIn('go ahead', text.casefold())
        self.assertEqual(self.pending()['skill'], 'perception')
        self.assertEqual(self.pending()['open_ask']['skill'], 'perception')
        result, text = self.say('15')
        self.assertIn('You spot', text)
        self.assertIsNone(self.pending())

    def test_pushback_and_roll_in_one_line_resolve_in_one_exchange(self):
        self._start(LOW_SHEET)
        self.call_old('investigation')
        result, text = self.say('Is that not Perception? I got a 15.')
        self.assertIn('You spot', text)
        self.assertNotIn('go ahead', text.casefold())
        self.assertIsNone(self.pending())

    def test_a_pushback_that_does_not_fit_is_declined_and_the_ask_stays_open(self):
        self._start(LOW_SHEET)
        self.say(SCAN)
        result, text = self.say('Can I roll Persuasion instead?')
        self.assertIn('Perception', text)
        self.assertEqual(self.pending()['skill'], 'perception')

    def test_the_neutral_act_line_never_reads_as_movement(self):
        self.assertNotIn('go ahead', SIMPLE_ACT_LINE.casefold())
        self.assertEqual(kit_moves.stance_problems('Narrator: ' + SIMPLE_ACT_LINE, SCAN), [])


class RulesQuestions(Scene):
    """A rules question to Kit is table talk (ask_dm), never a call across the road."""

    def test_rules_questions_are_not_speech_to_the_scene(self):
        self._start(LOW_SHEET)
        for line in ('Can I use my bonus action to hide behind the cart?',
                     'Do I need to roll to stay hidden, or is my Stealth enough?'):
            result, text = self.say(line)
            self.assertNotIn('call out', text.casefold(), line)
            self.assertNotEqual(result.get('stage'), 'clarify', text)
            self.assertEqual(result.get('player_move', '').split()[0], 'ask_dm', result.get('player_move'))
            if result.get('turn_id'):
                self.runtime.discard_pending_kit_turn(result['turn_id'])


class OpenAsk(Scene):
    def test_a_called_roll_stores_its_open_ask(self):
        self._start(LOW_SHEET)
        self.say(SCAN)
        ask = self.pending()['open_ask']
        self.assertEqual((ask['kind'], ask['skill'], ask['waits']), ('roll', 'perception', 'player'))
        self.assertEqual(kit_moves.open_ask_from_state(self.runtime.load()[1])['skill'], 'perception')

    def test_an_answer_is_read_against_the_ask(self):
        ask = kit_moves.open_ask('roll', SCAN, SCAN, skill='investigation')
        got = kit_moves.answer_of('Perception? I rolled a 15.', ask)
        self.assertEqual(got['total'], 15)
        self.assertEqual(got['pushback'], 'perception')

    def test_the_turn_spine_carries_the_move_and_stance(self):
        spine = turn_spine(SCAN, {})
        self.assertEqual(spine['player_move'], {'kind': 'look', 'stance': 'hold'})


class SpeakingContract(unittest.TestCase):
    """Live turns 5-7: a bare result, an internal label, a stray question, the PC moved."""

    def test_bare_results_are_rejected(self):
        for text in ('Kit: You roll History: 12.', 'Kit: 15.', 'Kit: Initiative: 14.', 'Perception 15'):
            self.assertTrue(kit_moves.bare_result(text), text)
            with self.assertRaises(InvalidChange):
                check_not_only_roll(text)
        self.assertFalse(kit_moves.bare_result('Kit: 15. You spot two shapes low in the ditch.'))

    def test_internal_labels_are_rejected(self):
        for text in ('Kit: open_ask: roll perception.', 'Kit: player_move look. You see the pine.'):
            with self.assertRaises(InvalidChange):
                check_no_internal_labels(text)

    def test_a_stray_question_the_reply_answers_is_rejected(self):
        segments = [{'speaker': 'Kit', 'text': 'Which thicket do you mean? You spot two figures in the left one.'}]
        with self.assertRaises(InvalidChange) as caught:
            kit_moves.check_turn_shape(segments, 'I scan the left thicket.')
        self.assertIn('ask or resolve', str(caught.exception))

    def test_a_choice_the_player_already_made_is_rejected(self):
        segments = [{'speaker': 'Kit', 'text': 'Left or right?'}]
        with self.assertRaises(InvalidChange):
            kit_moves.check_turn_shape(segments, 'I throw a stone into the left thicket.')

    def test_asking_for_a_roll_already_given_is_rejected(self):
        ask = kit_moves.open_ask('roll', SCAN, SCAN, skill='perception')
        with self.assertRaises(InvalidChange):
            kit_moves.check_turn_shape([{'speaker': 'Kit', 'text': 'Roll Perception.'}],
                                       'Perception? I rolled a 15.', ask)

    def test_moving_the_pc_against_his_stated_hold_is_rejected(self):
        with self.assertRaises(InvalidChange):
            kit_moves.check_stance([{'speaker': 'Narrator', 'text': 'You go ahead.'}], SCAN)
        with self.assertRaises(InvalidChange):
            kit_moves.check_stance([{'speaker': 'Narrator', 'text': 'You step closer to the thickets.'}], SCAN)
        kit_moves.check_stance([{'speaker': 'Narrator', 'text': 'You go ahead.'}], 'I walk up the road.')

    def test_a_clean_reply_passes(self):
        segments = [{'speaker': 'Narrator', 'text': 'Wind combs the brush. Two shapes lie flat in the ditch.'},
                    {'speaker': 'Kit', 'text': 'What do you do?'}]
        kit_moves.check_turn_shape(segments, SCAN)
        kit_moves.check_stance(segments, SCAN)


class NameCheckNit(unittest.TestCase):
    """Live turn 6: "Roll History." was flagged as an unattested name."""

    def test_mechanic_runs_are_not_names(self):
        for name in ('Roll History', 'Roll Perception', 'a Dexterity Saving Throw', 'Roll Initiative'):
            self.assertTrue(kit_moves.is_mechanic_run(name), name)
        self.assertFalse(kit_moves.is_mechanic_run('Captain Mira'))

    def test_roll_history_passes_the_performance_check(self):
        facts = {'kind': 'lookup', 'visible': ['A bell rings at a distant tower.'], 'section': [],
                 'people': [], 'link_notes': [], 'spoiler_fence': [],
                 'knowledge': {'mode': 'baseline', 'skill': None, 'result_tier': None}}
        performance = {'segments': [{'speaker': 'Kit', 'text': 'That bell rings a memory. Roll History.',
                                     'reacts_to': 'what do I know'}]}
        problems = kit_perform.performance_problems(performance, facts, beat={'source_verified': True,
                                                    'people': []}, action='What do I know about the bell?')
        self.assertFalse([p for p in problems if 'name' in p], problems)


class ReadyLine(unittest.TestCase):
    def test_the_ready_line_reads_cleanly(self):
        self.assertEqual(kit_skim.READY_LINE, "We're set. Say Yes and we start at the beginning of the book.")


class Moves(unittest.TestCase):
    TABLE = (
        ('I look around the clearing.', 'look'),
        ('I scan the thickets for movement.', 'look'),
        ('"Good evening," I say to the innkeeper.', 'talk'),
        ('I ask the guard about the road north.', 'talk'),
        ('What do I know about the old tower?', 'recall'),
        ('I walk up the road toward the tower.', 'move'),
        ('I sneak along the ditch.', 'move'),
        ('I drink my healing potion.', 'use'),
        ('I attack the bandit with my staff.', 'fight'),
        ('I take a short rest.', 'rest'),
        ('Can I use my bonus action to hide?', 'ask_dm'),
    )

    def test_every_move_is_declared(self):
        self.assertEqual(set(kit_moves.MOVES),
                         {'look', 'talk', 'recall', 'move', 'use', 'fight', 'rest', 'ask_dm'})

    def test_classify_table(self):
        for line, kind in self.TABLE:
            self.assertEqual(kit_moves.classify(line), kind, line)

    def test_stances(self):
        self.assertEqual(kit_moves.stance_of(SCAN), 'hold')
        self.assertEqual(kit_moves.stance_of('I walk up to the cart.'), 'advance')
        self.assertEqual(kit_moves.stance_of('I back away from the ditch.'), 'withdraw')

    def test_a_declared_move_that_contradicts_the_player_is_rejected(self):
        self.assertTrue(kit_moves.check_declared({'kind': 'look', 'stance': 'advance'}, SCAN))
        self.assertTrue(kit_moves.check_declared({'kind': 'fight'}, 'I look around the clearing.'))
        self.assertFalse(kit_moves.check_declared({'kind': 'look', 'stance': 'hold'}, SCAN))


if __name__ == '__main__':
    unittest.main()
