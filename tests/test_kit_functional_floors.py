"""PR-F: functional floors replace the raw word floors. A feature names the area's visible,
decision-relevant things and hands the floor to the player; an exchange has the focus actor
make a move and gives the player something to answer. A small sanity minimum stays against
empty turns. Watchroom and 17a fixtures (no 6c); dice pinned; no model."""
import unittest

from runtime import kit_agent
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from runtime.state_context import InvalidChange
from test_kit_room_review import STUB
from test_kit_watchroom_stalls import Stalls

# 44 words: a pithy human-DM room opening (Brendon's harness case, rebuilt on the watchroom).
PITHY_OPENING = {'segments': [
    {'speaker': 'Narrator', 'text': 'An iron door stands ajar, lamplight leaking through the gap. Behind it someone '
                                    'hums the same four notes, over and over.'},
    {'speaker': 'Narrator', 'text': 'The stair keeps winding down past the door into the dark. Up here, only the '
                                    'humming and the light. What do you do?'}]}

# 10 words: the terse NPC challenge from the same harness.
TERSE_CHALLENGE = {'segments': [
    {'speaker': 'Narrator', 'text': 'His hand settles beside the bell cord.'},
    {'speaker': 'Watch warden', 'text': 'Who sent you?'}]}

# Padded but empty: plenty of words, none of the room's visible things, no handoff.
PADDED_FEATURE = {'segments': [
    {'speaker': 'Narrator', 'text': 'Time passes slowly in a place like this, and the air feels heavy with old '
                                    'memories, the kind that settle into the bones of travellers who have walked '
                                    'too far from home and wondered, on long nights, whether any of it mattered.'},
    {'speaker': 'Narrator', 'text': 'Shadows gather and thin again as the moments drift by, quiet and patient, and '
                                    'somewhere in the deep the world goes on turning without hurry, indifferent '
                                    'and vast, while your thoughts wander to roads behind you and roads ahead.'}]}

PADDED_EXCHANGE = {'segments': [
    {'speaker': 'Narrator', 'text': 'A long moment stretches out in the stillness, the kind of moment that seems to '
                                    'hold its breath, heavy and slow, while the world outside goes about its own '
                                    'business far away.'},
    {'speaker': 'Narrator', 'text': 'Dust hangs in the air. Somewhere distant, water drips with patient regularity '
                                    'onto old stone.'}]}


class Base(Stalls):
    def opening(self, runtime=None):
        bridge = self.bridge if runtime is None else KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10))
        packet = bridge.prepare(opening=True, one_pass=True, turn_id='open')
        plan = self.plan_for(packet)
        plan['public_brief'].update(scope='feature')
        return bridge, plan

    def challenge(self):
        self.go_in()
        packet = self.bridge.prepare('"Evening. I am not here for trouble."', 'say', one_pass=True)
        plan = self.plan_for(packet, move='npc_reply', focus_actor='warden', table_presence='quiet')
        plan['improv_read'].update(actor_ref='warden', actor_basis='motive')
        plan['public_brief'].update(scope='exchange', reply_to='I am not here for trouble')
        return plan


class TheHarnessCasesCommit(Base):
    def test_a_pithy_44_word_opening_commits(self):
        self.assertEqual(sum(len(s['text'].split()) for s in PITHY_OPENING['segments']), 44)
        bridge, plan = self.opening()
        result = bridge.complete('open', {'decision': plan, 'performance': PITHY_OPENING})
        self.assertTrue(result['spoken'])

    def test_a_pithy_17a_doorway_opening_commits(self):
        runtime = self.start(STUB)
        bridge, plan = self.opening(runtime)
        speech = {'segments': [
            {'speaker': 'Narrator', 'text': 'Double doors stand closed before you, the way into the foyer of this '
                                            'place. Something dead has been lying beyond them a long while; the smell '
                                            'says so.'},
            {'speaker': 'Narrator', 'text': 'Nothing moves on this side. Do you open the doors?'}]}
        self.assertTrue(bridge.complete('open', {'decision': plan, 'performance': speech})['spoken'])

    def test_a_ten_word_npc_challenge_commits(self):
        self.assertEqual(sum(len(s['text'].split()) for s in TERSE_CHALLENGE['segments']), 10)
        plan = self.challenge()
        self.assertTrue(self.bridge.complete('say', {'decision': plan, 'performance': TERSE_CHALLENGE})['spoken'])

    def test_an_npc_command_is_something_to_answer(self):
        plan = self.challenge()
        speech = {'segments': [{'speaker': 'Narrator', 'text': 'The spear point comes up an inch, level and steady.'},
                               {'speaker': 'Watch warden', 'text': 'No. Hands out. Now.'}]}
        self.assertTrue(self.bridge.complete('say', {'decision': plan, 'performance': speech})['spoken'])


class EmptyTurnsStillFail(Base):
    def test_a_padded_feature_naming_nothing_fails(self):
        bridge, plan = self.opening()
        with self.assertRaisesRegex(InvalidChange, 'visible things') as caught:
            bridge.complete('open', {'decision': plan, 'performance': PADDED_FEATURE})
        self.assertIn('hand the floor', str(caught.exception))

    def test_a_long_feature_that_never_hands_off_fails(self):
        bridge, plan = self.opening()
        speech = {'segments': [PITHY_OPENING['segments'][0],
                               {'speaker': 'Narrator', 'text': 'The stair keeps winding down past the door into the '
                                                               'dark, and cold air climbs it from far below, smelling '
                                                               'of wet rock and old smoke.'}]}
        with self.assertRaisesRegex(InvalidChange, 'hand the floor'):
            bridge.complete('open', {'decision': plan, 'performance': speech})

    def test_a_padded_exchange_where_the_actor_does_nothing_fails(self):
        plan = dict(self.challenge(), move='world_description')
        with self.assertRaisesRegex(InvalidChange, 'Watch warden') as caught:
            self.bridge.complete('say', {'decision': plan, 'performance': PADDED_EXCHANGE})
        self.assertIn('nothing to answer', str(caught.exception))

    def test_an_exchange_that_moves_but_asks_nothing_fails(self):
        plan = dict(self.challenge(), move='world_description')
        speech = {'segments': [{'speaker': 'Narrator', 'text': 'The warden sets his cup down on the table, slowly, '
                                                               'and studies the stranger in the doorway for a long '
                                                               'moment without a word, the lamp ticking on its hook.'}]}
        with self.assertRaisesRegex(InvalidChange, 'nothing to answer'):
            self.bridge.complete('say', {'decision': plan, 'performance': speech})

    def test_an_empty_turn_fails_the_sanity_minimum(self):
        plan = self.challenge()
        speech = {'segments': [{'speaker': 'Watch warden', 'text': 'Well?'}]}
        with self.assertRaisesRegex(InvalidChange, rf'Exchange scope was flat .*{kit_agent.SANITY_MIN_WORDS}'):
            self.bridge.complete('say', {'decision': plan, 'performance': speech})


class Handoffs(unittest.TestCase):
    """Unit cases for what hands the floor to the player."""

    def handoff(self, *segments, focus=None):
        return kit_agent.hands_off([{'speaker': s, 'text': t} for s, t in segments], focus)

    def test_what_counts(self):
        self.assertTrue(self.handoff(('Narrator', 'The door is open. What do you do?')))
        self.assertTrue(self.handoff(('Kit', 'Give me a Dexterity (Stealth) check.')))
        self.assertTrue(self.handoff(('Narrator', 'He waits.'), ('Watch warden', 'Answer from there.')))
        self.assertTrue(self.handoff(('Watch warden', 'Who sent you?'), ('Kit', 'Oh, he means it.')))
        self.assertTrue(self.handoff(('Narrator', 'The stair is clear. Your move.')))

    def test_what_does_not(self):
        self.assertFalse(self.handoff(('Narrator', 'The lamp burns low. Dust drifts.')))
        self.assertFalse(self.handoff(('Watch warden', 'Who sent you?'), ('Narrator', 'He turns away and sits.')))

    def test_the_limits_state_function_not_word_floors(self):
        limits = kit_agent.performance_limits()
        self.assertNotIn('At least 80 words', limits['feature'])
        self.assertIn('hand', limits['feature'])
        self.assertIn('something to answer', limits['exchange'])


if __name__ == '__main__':
    unittest.main()
