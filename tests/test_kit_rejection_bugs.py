"""Rejection-causing bugs from the PR 145 playtests (/workspace/kit2 logs), fixed in the latency
PR: a refused attempt no longer clears Kit's called check; an Avrae roll (with its header line or
with words in front) answers that check; simple moves are not "the DM's call"; mixed messages and
questions keep their action; out-of-combat spells and rituals resolve; resubmitting the identical
decision after a performance rejection is not "already fixed". Watchroom fixture, dice pinned."""
import unittest

from runtime import kit_agent
from runtime.kit_agent import PendingRuling
from test_kit_watchroom_stalls import Stalls


class CalledCheck(Stalls):
    def call(self, skill='investigation', target='none', turn='call'):
        packet = self.bridge.prepare('Can I make a check?', turn, one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief',
                             roll_call={'skill': skill, 'mode': 'normal', 'target': target,
                                        'cause': {'kind': 'position', 'ref': 'none', 'roots': []}})
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        self.bridge.complete(turn, {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'Give me an Investigation check.', 'reacts_to': 'Can I make a check'}]}})
        self.assertEqual(self.runtime.load()[1]['pending_check']['skill'], skill)

    def test_avrae_header_answers_the_called_check(self):
        self.call()
        result = self.resolve(self.runtime, 'Nik makes an Investigation check! 1d20 (1) + 7 = 8')
        self.assertEqual(result.kind, 'called_check')
        self.assertIn('8', result.public_event)

    def test_a_roll_with_words_in_front_answers_the_called_check(self):
        self.call()
        for line in ('Deal, 2d20kh1 (4, 5) + 4 = 9',
                     'I search the throne for seams. Investigation 1d20 (1) + 7 = 8'):
            with self.subTest(line):
                self.assertEqual(self.resolve(self.runtime, line).kind, 'called_check')

    def test_an_unlabelled_roll_inside_a_long_message_is_not_taken_as_the_answer(self):
        self.call()
        line = 'I would rather talk to the warden first and see what he wants, 1d20 (4) + 4 = 8?'
        self.assertNotEqual(self.resolve(self.runtime, line).kind, 'called_check')

    def test_a_refused_attempt_keeps_the_called_check(self):
        self.call()
        with self.assertRaises(PendingRuling):
            self.bridge.prepare('I steal everything in the room.', 'smash', one_pass=True)
        self.assertEqual(self.runtime.load()[1]['pending_check']['skill'], 'investigation')
        self.assertEqual(self.resolve(self.runtime, '1d20 (1) + 7 = 8').kind, 'called_check')


class SimpleActs(Stalls):
    def test_simple_moves_are_not_the_dms_call(self):
        for line in ('I hold up a light at the doorway.', 'I sweep the cobwebs off the table with my staff.',
                     'I crouch by the table.', 'I tap the chest with my staff.'):
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertEqual(result.kind, 'observe')
                self.assertIn('simple_act', result.events[0]['tags'])

    def test_hop_on_in_goes_in(self):
        self.assertEqual(self.resolve(self.runtime, 'Hop on in.').kind, 'exit')

    def test_a_risky_act_is_kits_ruling_not_a_refusal(self):
        # #150 retest 2b: an attempt on a thing in the room is an ordinary turn Kit rules.
        self.assertEqual(self.resolve(self.runtime, 'I smash the chest.').kind, 'kit_ruling')
        with self.assertRaises(PendingRuling):
            self.resolve(self.runtime, 'I steal everything in the room.')


class MixedMessages(Stalls):
    def test_talk_act_and_question_keep_the_act(self):
        for line in ('Matching set, never good. I back up to the door and look over the chest. Does it look trapped?',
                     'I look over the chest and the ledger. Do either look valuable?'):
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertEqual(result.kind, 'observe')
                self.assertNotIn('You declare', result.public_event)

    def test_a_simple_act_with_a_question(self):
        result = self.resolve(self.runtime, 'I tap the chest. Is it hollow?')
        self.assertIn('simple_act', result.events[0]['tags'])

    def test_a_check_question_with_an_act_is_still_a_check_request(self):
        self.assertEqual(self.resolve(self.runtime, 'Hmm. I crouch by the table. Could I roll Perception?').kind,
                         'check_request')

    def test_a_bare_question_and_speech_stay_speech(self):
        for line in ("What's on the table?", 'I ask the warden what he is guarding. "Long night?"'):
            with self.subTest(line):
                self.assertEqual(self.resolve(self.runtime, line).kind, 'social')


class Spells(Stalls):
    def test_detect_magic_as_a_ritual_is_cast_and_takes_ten_minutes(self):
        result = self.resolve(self.runtime, 'I sit by the door and cast Detect Magic as a ritual.')
        self.assertEqual(result.kind, 'spell_cast')
        self.assertIn('ritual', result.events[0]['tags'])
        time = [e for e in result.events if e['type'] == 'advance_time']
        self.assertEqual(time[0]['seconds'], 600)
        before = self.runtime.load()[1]['elapsed_seconds']
        revision, _ = self.runtime.load()
        self.runtime.commit('ritual', revision, list(result.events))
        self.assertEqual(self.runtime.load()[1]['elapsed_seconds'], before + 600)

    def test_a_plain_spell_out_of_combat_takes_no_extra_time(self):
        result = self.resolve(self.runtime, 'I cast light on my staff.')
        self.assertEqual(result.kind, 'spell_cast')
        self.assertFalse([e for e in result.events if e['type'] == 'advance_time'])


class ResubmitSameDecision(Stalls):
    def test_the_identical_decision_resubmitted_after_a_performance_rejection_commits(self):
        import copy
        from runtime.state_context import InvalidChange, encode
        packet = self.bridge.prepare('Can I make a check?', 'r', one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief')
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        plan.pop('observed_event', None)
        plan.pop('detail', None)  # what a host leaves out; the engine fills both in
        sent = copy.deepcopy(plan)
        long = ' '.join(['No roll needed: you hear him humming plainly from right here.'] * 8)
        with self.assertRaises(InvalidChange):
            self.bridge.complete('r', {'decision': plan, 'performance': {'segments': [
                {'speaker': 'Kit', 'text': long, 'reacts_to': 'Can I make a check'}]}})
        stored = self.runtime.pending_kit_turn('r')['plan']
        self.assertNotEqual(encode(stored), encode(sent))  # the engine filled things in
        result = self.bridge.complete('r', {'decision': copy.deepcopy(sent), 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'No roll needed: you hear him humming plainly from here.',
             'reacts_to': 'Can I make a check'}]}})
        self.assertTrue(result['spoken'])

    def test_a_changed_decision_is_still_refused(self):
        from runtime.state_context import InvalidChange
        packet = self.bridge.prepare('Can I make a check?', 'c', one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief')
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        long = ' '.join(['No roll needed: you hear him humming plainly from right here.'] * 8)
        with self.assertRaises(InvalidChange):
            self.bridge.complete('c', {'decision': dict(plan), 'performance': {'segments': [
                {'speaker': 'Kit', 'text': long, 'reacts_to': 'Can I make a check'}]}})
        # Presentation keys may be corrected after a rejection (#129, REPLACEABLE_PLAN_KEYS); what
        # the engine acts on may not.
        other = next(mode for mode in kit_agent.kit_voice.TURN_MODES if mode != plan['turn_mode'])
        with self.assertRaisesRegex(InvalidChange, 'already fixed'):
            self.bridge.complete('c', {'decision': {**plan, 'turn_mode': other}, 'performance': {
                'segments': [{'speaker': 'Kit', 'text': 'No roll needed.', 'reacts_to': 'Can I make a check'}]}})


if __name__ == '__main__':
    unittest.main()
