"""PR1 (plan update #3): a short beat is a complete, call-sized turn with no floor padding.

(i) A real reaction plus a narrowing question, or an "are you sure?" before a risky act.
(ii) The stall check: on a heavy turn (room entry, a first look, a way through), Kit's first
commit may be just a fitting check call. The engine holds the description for the roll and
the next turn delivers it, scaled to the result. Kit still calls the check; it is never
used while one is pending or when a due hook must land; and the reaction is Kit's own
judgment, never canned filler or a line she already used. Watchroom fixture; no model."""
import unittest

from runtime.state_context import InvalidChange
from test_kit_watchroom_stalls import Stalls, landing

PERCEPTION = {'skill': 'perception', 'mode': 'normal', 'target': 'none',
              'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}
KICK = 'I kick the iron door open.'


def kit(text, quote):
    return {'speaker': 'Kit', 'text': text, 'reacts_to': quote}


class ShortBeat(Stalls):
    def narrow(self, turn, segments, line=KICK, quote='kick the iron door'):
        packet = self.bridge.prepare(line, turn, one_pass=True)
        plan = self.plan_for(packet, move='ask_clarification', table_presence='brief')
        plan['public_brief'].update(reply_to=quote, scope='call')
        return self.bridge.complete(turn, {'decision': plan, 'performance': {'segments': segments}})

    def stall(self, turn='open', say='Roll Perception.', **update):
        packet = self.bridge.prepare(opening=True, one_pass=True, turn_id=turn)
        plan = self.plan_for(packet, move='ruling', table_presence='brief', **update)
        plan['public_brief'].update(scope='call')
        result = self.bridge.complete(turn, {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': say}]}})
        return packet, result


class ReactionAndNarrowingQuestion(ShortBeat):
    def test_a_reaction_and_a_narrowing_question_is_a_whole_turn(self):
        result = self.narrow('n', [kit('An iron door with a guard post behind it, and your boot is the plan. How do you want to do that?',
                                       'kick the iron door')])
        self.assertTrue(result['spoken'])

    def test_an_are_you_sure_before_a_risky_act_is_a_whole_turn(self):
        result = self.narrow('w', [kit('Whoever is humming in there will hear that door hit the wall. Are you sure?', 'kick the iron door')])
        self.assertTrue(result['spoken'])

    def test_a_short_beat_still_asks(self):
        with self.assertRaises(InvalidChange):
            self.narrow('q', [kit('Whoever is humming in there will hear that door hit the wall.', 'kick the iron door')])


class CannedFillerIsNotAReaction(ShortBeat):
    def test_a_canned_reaction_is_refused(self):
        for filler in ('Ooh, bold!', 'Oh ho, interesting.', 'Love it. Classic.', 'Well, well, well.'):
            with self.subTest(filler), self.assertRaisesRegex(InvalidChange, 'canned'):
                self.narrow('c', [kit(filler + ' How do you want to do that?', 'kick the iron door')])
            self.bridge.abandon('c')

    def test_a_laugh_or_a_gasp_before_a_real_question_passes(self):
        for line in ('Ha! Are you sure?', 'Wow. How do you want to do that?'):
            with self.subTest(line):
                self.assertTrue(self.narrow('l' + line[:2], [kit(line, 'kick the iron door')])['spoken'])

    def test_a_laugh_with_no_question_is_still_canned(self):
        with self.assertRaisesRegex(InvalidChange, 'canned|ask'):
            self.narrow('h', [kit('Ha!', 'kick the iron door')])

    def test_a_reaction_kit_already_used_is_refused(self):
        line = 'Whoever is humming in there will hear that door hit the wall.'
        self.narrow('a', [kit(line + ' Are you sure?', 'kick the iron door')])
        with self.assertRaisesRegex(InvalidChange, 'recycles'):
            self.narrow('b', [kit(line + ' Is that the plan?', 'kick the iron door')])


class StallCheckOnAHeavyTurn(ShortBeat):
    def test_room_entry_may_open_on_a_fitting_check_call(self):
        _, result = self.stall(roll_call=PERCEPTION)
        self.assertTrue(result['spoken'])
        pending = self.runtime.load()[1]['pending_check']
        self.assertEqual(pending['skill'], 'perception')
        self.assertEqual(pending['held']['kind'], 'opening')

    def test_the_roll_delivers_the_held_description_scaled_to_the_result(self):
        self.stall(roll_call=PERCEPTION)
        rolled = self.bridge.prepare('Perception check: 1d20 (13) + 2 = 15', 'r', one_pass=True)
        held = rolled['input']['private']['held_description']
        self.assertEqual(held['kind'], 'opening')
        self.assertEqual(held['roll'], 15)
        self.assertTrue(held['rule'])
        self.assertTrue(any('held' in line for line in rolled['first_try']))
        self.assertTrue(rolled['input']['private']['story_brief'])  # the description's material is there
        plan = self.plan_for(rolled)
        plan['public_brief'].update(reply_to='Perception check', scope='call')
        with self.assertRaisesRegex(InvalidChange, 'held'):  # the description is due now, in full
            self.bridge.complete('r', {'decision': plan, 'performance': {'segments': [
                {'speaker': 'Narrator', 'text': 'You see the door.'}]}})
        plan['public_brief'].update(scope='feature')
        self.assertTrue(self.bridge.complete('r', {'decision': plan, 'performance': landing()})['spoken'])
        self.assertNotIn('pending_check', self.runtime.load()[1])

    def test_a_stall_must_call_the_check(self):
        with self.assertRaises(InvalidChange):
            self.stall()

    def test_no_stall_on_an_ordinary_turn_s_floor(self):
        """An ordinary social bid keeps its exchange; only heavy turns may open on a check."""
        self.go_in()
        packet = self.bridge.prepare('"Evening. Quiet night?"', 's', one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief', roll_call=PERCEPTION)
        plan['public_brief'].update(reply_to='Quiet night', scope='call')
        with self.assertRaises(InvalidChange):
            self.bridge.complete('s', {'decision': plan, 'performance': {'segments': [
                {'speaker': 'Narrator', 'text': 'Roll Perception.'}]}})

    def test_no_second_stall_while_one_is_held(self):
        self.stall(roll_call=PERCEPTION)
        packet = self.bridge.prepare('I peek through the gap in the door.', 'p2', one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief', roll_call=PERCEPTION)
        plan['public_brief'].update(reply_to='peek through the gap', scope='call')
        with self.assertRaisesRegex(InvalidChange, 'held'):
            self.bridge.complete('p2', {'decision': plan, 'performance': {'segments': [
                kit('Roll Perception.', 'peek through the gap')]}})


class HeldDescriptionIsAnObligation(ShortBeat):
    """Nagatha's #91 review: the held description could be forgotten (no roll, a new check, a
    move) and its delivery was barely checked."""

    def beat(self, name):
        revision, _ = self.runtime.load()
        self.runtime.commit(name, revision, [{'type': 'beat', 'tags': ['observe'], 'evidence': 'A look.'}])

    def test_the_held_record_names_its_room(self):
        self.stall(roll_call=PERCEPTION)
        self.assertEqual(self.runtime.load()[1]['pending_check']['held'], {'kind': 'opening', 'area': 'landing'})

    def test_no_roll_keeps_the_obligation_and_the_next_turn_delivers_the_plain_view(self):
        self.stall(roll_call=PERCEPTION)
        self.beat('b')  # a turn passes with no roll: the obligation stays
        self.assertTrue(self.runtime.load()[1]['pending_check']['held'])
        packet = self.bridge.prepare('I wait on the landing and listen.', 'n', one_pass=True)
        held = packet['input']['private']['held_description']
        self.assertIsNone(held['roll'])
        self.assertIn('did not roll', held['rule'])
        plan = self.plan_for(packet)
        plan['public_brief'].update(reply_to='wait on the landing', scope='feature')
        self.bridge.complete('n', {'decision': plan, 'performance': landing()})
        self.assertNotIn('pending_check', self.runtime.load()[1])  # delivered, so discharged

    def test_a_new_check_cannot_replace_the_held_one(self):
        self.stall(roll_call=PERCEPTION)
        packet = self.bridge.prepare('I wait on the landing and listen.', 'c2', one_pass=True)
        plan = self.plan_for(packet, roll_call={**PERCEPTION, 'skill': 'investigation'})
        plan['public_brief'].update(reply_to='wait on the landing', scope='feature')
        with self.assertRaisesRegex(InvalidChange, 'held'):
            self.bridge.complete('c2', {'decision': plan, 'performance': landing()})
        self.assertEqual(self.runtime.load()[1]['pending_check']['skill'], 'perception')

    def test_moving_rooms_lapses_it_and_it_never_lands_in_the_wrong_room(self):
        self.stall(roll_call=PERCEPTION)
        self.go_in()
        self.assertNotIn('pending_check', self.runtime.load()[1])
        packet = self.bridge.prepare('I look around.', 'w', one_pass=True)
        self.assertNotIn('held_description', packet['input']['private'])

    def test_the_resolution_turn_must_describe_the_held_place(self):
        self.stall(roll_call=PERCEPTION)
        rolled = self.bridge.prepare('Perception check: 1d20 (13) + 2 = 15', 'd', one_pass=True)
        self.assertIn('door', rolled['input']['private']['held_description']['cues'])
        plan = self.plan_for(rolled)
        plan['public_brief'].update(reply_to='Perception check', scope='feature')
        elsewhere = ('You take a slow breath and weigh what you know so far, turning the question of the night '
                     'over in your mind while your pulse settles and your thoughts run on ahead of you, patient '
                     'and careful and wholly your own, until you are ready to decide what comes next.')
        with self.assertRaisesRegex(InvalidChange, 'held'):
            self.bridge.complete('d', {'decision': plan, 'performance': {'segments': [
                {'speaker': 'Narrator', 'text': elsewhere}, {'speaker': 'Narrator', 'text': (
                    'Whatever you choose, it will be yours to choose, and the choosing will not wait '
                    'forever, so you gather yourself and get ready, slowly and deliberately, to decide at last.')}]}})
        self.assertTrue(self.bridge.complete('d', {'decision': plan, 'performance': landing()})['spoken'])


class CheckRequestIsThePlayerAsking(unittest.TestCase):
    def test_not_check_requests(self):
        from runtime.kit_agent import CHECK_REQUEST
        for line in ('Can I save him?', 'Dealer, can you check my hand?'):
            with self.subTest(line):
                self.assertIsNone(CHECK_REQUEST.search(line))

    def test_still_check_requests(self):
        from runtime.kit_agent import CHECK_REQUEST
        for line in ('Can I roll Perception on the door?', 'Do I need to make a check?',
                     'Can I make a saving throw?', 'Should we check for traps?'):
            with self.subTest(line):
                self.assertIsNotNone(CHECK_REQUEST.search(line))


if __name__ == '__main__':
    unittest.main()
