"""Opening-turn friction on non-Grok hosts (a fresh host's opening was rejected six times on
format alone). Watchroom fixture only, never 6c. Dice pinned; no model.

1. Each format rejection names the field to fill, its shape, and an example.
2. A failed attempt no longer locks the decision: a corrected decision on the same turn faces
   every check again and can commit. Abandoning the opening tells the host to prepare the
   opening again, not a player action, so the room never has to restart.
3. On room entry, an NPC only heard through the door (not in direct contact) need not speak.
   One in the room with the PC still must. Secrecy and agency checks are untouched.
4. A resend of the decision already fixed for the turn, with only a new performance, commits
   (rooms-pack build: it was refused as "already fixed" and only abandon recovered). A key the
   engine fills when left out counts as the same whether the resend leaves it out, sends the
   filled value, or sends its empty value. A resend that changes the decision is handled as before.
"""
import copy

from runtime import kit_agent
from runtime.state_context import InvalidChange
from test_kit_watchroom_stalls import NARRATION, Stalls, landing
from test_kit_room_review import WATCH


class OpeningFriction(Stalls):
    def opening(self):
        packet = self.bridge.prepare(opening=True, one_pass=True)
        return packet['turn_id'], self.plan_for(packet)

    def reject(self, turn, plan, speech=None):
        with self.assertRaises(InvalidChange) as caught:
            self.bridge.complete(turn, {'decision': plan, 'performance': speech or landing()})
        return str(caught.exception)


class RejectionsSayWhatToFill(OpeningFriction):
    def test_missing_brief_fields_are_named_with_shape_and_example(self):
        turn, plan = self.opening()
        for key in ('mirror', 'npc_notice'):
            del plan['public_brief'][key]
        message = self.reject(turn, plan)
        self.assertIn('Invalid public performance brief', message)
        self.assertIn('missing: mirror, npc_notice', message)
        for key in kit_agent.BRIEF_FIELDS:
            self.assertIn(key, message)
        self.assertIn('"none"', message)
        self.assertIn('Example:', message)

    def test_an_empty_or_unknown_brief_field_is_named(self):
        turn, plan = self.opening()
        plan['public_brief']['callback'] = ''
        plan['public_brief']['mood'] = 'tense'
        message = self.reject(turn, plan)
        self.assertIn('empty: callback', message)
        self.assertIn('not allowed: mood', message)

    def test_generic_kit_focus_gets_an_example(self):
        turn, plan = self.opening()
        plan['public_brief']['kit_focus'] = 'Make the scene feel tense and interesting.'
        message = self.reject(turn, plan)
        self.assertIn('kit_focus is too generic', message)
        self.assertIn('Example:', message)

    def test_player_note_shape_says_none_with_an_example(self):
        turn, plan = self.opening()
        plan['player_note'] = {'note': 'none'}
        message = self.reject(turn, plan)
        self.assertIn('player_note', message)
        self.assertIn('{"note": "none", "evidence_turns": [], "replaces": "none"}', message)

    def test_an_empty_note_with_evidence_says_how_to_fix_it(self):
        turn, plan = self.opening()
        plan['player_note'] = {'note': 'none', 'evidence_turns': ['this_turn'], 'replaces': 'none'}
        message = self.reject(turn, plan)
        self.assertIn('{"note": "none", "evidence_turns": [], "replaces": "none"}', message)


class ACorrectedDecisionCanCommit(OpeningFriction):
    def test_a_corrected_decision_commits_after_a_rejected_performance(self):
        turn, plan = self.opening()
        loud = {'segments': [{'speaker': 'Kit', 'text': 'Well then.'}]}
        self.reject(turn, plan, loud)  # the decision passed; the performance failed
        fixed = copy.deepcopy(plan)
        fixed['public_brief']['kit_focus'] = 'Let the humming behind the iron door carry the beat; hold back the stair.'
        result = self.bridge.complete(turn, {'decision': fixed, 'performance': landing()})
        self.assertIn('spoken', result)
        trace = self.runtime.committed_kit_turn(turn)['trace']
        self.assertEqual(trace['public_brief']['kit_focus'], fixed['public_brief']['kit_focus'])

    def test_a_corrected_decision_faces_every_check_again(self):
        turn, plan = self.opening()
        self.reject(turn, plan, {'segments': [{'speaker': 'Kit', 'text': 'Well then.'}]})
        bad = copy.deepcopy(plan)
        bad['public_brief']['kit_focus'] = 'Make the scene feel tense and interesting.'
        self.assertIn('kit_focus is too generic', self.reject(turn, bad))
        self.assertEqual(self.bridge.guidance(turn)['rejected_attempts'], 2)
        # The first decision still works.
        self.assertIn('spoken', self.bridge.complete(turn, {'decision': plan, 'performance': landing()}))

    def test_what_the_engine_acts_on_stays_fixed(self):
        turn, plan = self.opening()
        self.reject(turn, plan, {'segments': [{'speaker': 'Kit', 'text': 'Well then.'}]})
        other = next(mode for mode in kit_agent.kit_voice.TURN_MODES if mode != plan['turn_mode'])
        message = self.reject(turn, {**plan, 'turn_mode': other})
        self.assertIn('already fixed', message)
        self.assertIn('turn_mode', message)
        self.assertIn('public_brief', message)  # names what may be corrected

    def test_abandoning_the_opening_says_to_prepare_the_opening_again(self):
        turn, plan = self.opening()
        plan['public_brief']['kit_focus'] = 'Make the scene feel tense and interesting.'
        for _ in range(kit_agent.ABANDON_SUGGEST_AFTER):
            message = self.reject(turn, plan)
        self.assertIn('--opening', message)
        abandoned = self.bridge.abandon(turn)
        self.assertIn('prepare --opening --one-pass', abandoned['next_step'])
        turn2, plan2 = self.opening()
        self.assertIn('spoken', self.bridge.complete(turn2, {'decision': plan2, 'performance': landing()}))


QUIET_KIT = {'segments': [{'speaker': 'Kit', 'text': 'Well then.'}]}  # style miss: one retry


class TheSameDecisionWithANewPerformanceCommits(OpeningFriction):
    """Through complete (one-pass) and decide/finish (staged), synthetic watchroom only."""

    def resend(self, turn, decision):
        result = self.bridge.complete(turn, {'decision': decision, 'performance': landing()})
        self.assertIn('spoken', result)
        self.assertFalse(result.get('engine_line'))  # the new narration, not the fallback
        self.assertIn('stripe across the landing', result['spoken'])
        return self.runtime.committed_kit_turn(turn)['trace']

    def test_the_identical_resend_commits_the_new_performance(self):
        turn, plan = self.opening()
        sent = copy.deepcopy(plan)
        self.reject(turn, plan, QUIET_KIT)
        fixed = self.runtime.pending_kit_turn(turn)['plan']
        self.assertEqual(self.resend(turn, sent), fixed)

    def test_resending_what_the_engine_filled_in_commits(self):
        turn, plan = self.opening()
        self.reject(turn, plan, QUIET_KIT)
        fixed = self.runtime.pending_kit_turn(turn)['plan']
        self.assertIn('detail', fixed)  # filled by the engine: the host left it out
        self.assertEqual(self.resend(turn, copy.deepcopy(fixed)), fixed)

    def test_an_empty_value_for_a_key_left_out_is_the_same_decision(self):
        for key, empty in (('claims', []), ('salience', []), ('agenda', None), ('ask_player', False),
                           ('ask_player', None), ('roll_call', None), ('pc_state', None)):
            with self.subTest(key=key, empty=empty):
                self.setUp()
                turn, plan = self.opening()
                plan.pop(key, None)
                self.reject(turn, copy.deepcopy(plan), QUIET_KIT)
                fixed = self.runtime.pending_kit_turn(turn)['plan']
                self.assertNotIn(key, fixed)
                self.assertEqual(self.resend(turn, {**plan, key: empty}), fixed)

    def test_a_lost_response_resent_as_first_sent_returns_the_committed_turn(self):
        turn, plan = self.opening()
        sent = copy.deepcopy(plan)
        self.reject(turn, plan, QUIET_KIT)
        committed = self.resend(turn, copy.deepcopy(sent))
        again = self.bridge.complete(turn, {'decision': copy.deepcopy(sent), 'performance': landing()})
        self.assertTrue(again.get('already_committed'))
        self.assertEqual(self.runtime.committed_kit_turn(turn)['trace'], committed)

    def test_the_staged_path_takes_the_same_decision_again(self):
        packet = self.bridge.prepare(opening=True)
        turn, plan = packet['turn_id'], self.plan_for({'input': {'private': packet['input']}})
        plan.pop('claims', None)
        self.bridge.decide(turn, copy.deepcopy(plan))
        with self.assertRaises(InvalidChange):
            self.bridge.finish(turn, QUIET_KIT)
        fixed = self.runtime.pending_kit_turn(turn)['plan']
        for again in (copy.deepcopy(plan), copy.deepcopy(fixed), {**plan, 'claims': []}):
            self.assertEqual(self.bridge.decide(turn, again)['stage'], 'public_performance')
        self.assertEqual(self.runtime.pending_kit_turn(turn)['plan'], fixed)
        self.assertIn('stripe across the landing', self.bridge.finish(turn, landing())['spoken'])
        self.assertEqual(self.runtime.committed_kit_turn(turn)['trace'], fixed)

    def test_a_resend_that_changes_the_decision_is_handled_as_before(self):
        turn, plan = self.opening()
        self.reject(turn, plan, QUIET_KIT)
        other = next(mode for mode in kit_agent.kit_voice.TURN_MODES if mode != plan['turn_mode'])
        self.assertIn('already fixed', self.reject(turn, {**plan, 'turn_mode': other}))
        self.assertIn('already fixed', self.reject(turn, {**plan, 'claims': [{'about': 'x'}]}))
        packet = self.bridge.prepare(opening=True)
        staged = self.plan_for({'input': {'private': packet['input']}})
        self.bridge.decide(packet['turn_id'], staged)
        with self.assertRaisesRegex(InvalidChange, 'already fixed'):
            self.bridge.decide(packet['turn_id'], {**staged, 'tone': 'warm'})

    def test_the_rejection_and_the_host_note_say_a_matching_resend_commits(self):
        turn, plan = self.opening()
        self.reject(turn, plan, QUIET_KIT)
        other = next(mode for mode in kit_agent.kit_voice.TURN_MODES if mode != plan['turn_mode'])
        message = self.reject(turn, {**plan, 'turn_mode': other})
        for text in (message, kit_agent.HOST_RETRY_NOTE):
            with self.subTest(text=text[:40]):
                self.assertIn('same decision with only a new performance', text)
                self.assertIn('is accepted', text)


class HeardOnlyNeedsNoFirstLine(OpeningFriction):
    def test_an_npc_heard_through_the_door_need_not_speak_on_entry(self):
        turn, plan = self.opening()
        plan['focus_actor'] = 'warden'
        result = self.bridge.complete(turn, {'decision': plan, 'performance': landing()})
        self.assertIn('spoken', result)

    def test_an_npc_in_the_room_still_gives_the_first_line(self):
        runtime = self.start(WATCH, area='watchroom')
        bridge = kit_agent.KitChatBridge(runtime, kit_agent.RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))
        packet = bridge.prepare(opening=True, one_pass=True)
        plan = self.plan_for(packet, focus_actor='warden')
        speech = {'segments': [{'speaker': 'Narrator', 'text': NARRATION}]}
        with self.assertRaisesRegex(InvalidChange, "focus actor's first line"):
            bridge.complete(packet['turn_id'], {'decision': plan, 'performance': speech})


if __name__ == '__main__':
    import unittest
    unittest.main()
