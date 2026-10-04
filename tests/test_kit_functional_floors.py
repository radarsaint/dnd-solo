"""PR-F, after Nagatha's #102 review: one structural handoff rule, no word floors.

A feature or exchange ends by handing the floor back to the player. Kit declares how in her
decision (hands_off: question | check_call | npc_challenge | combat_prompt | none with a reason)
and the engine checks the declaration against the structure of the speech (runtime/kit_floor.py).
Omitted, the engine accepts what it can see. No minimum word count and no mood word lists: a
lone "What do you do?" or "Stay down." is a whole turn; padded mood that hands nothing over is
not. The same rule serves PR-H's progressive reveal (required=True: none is not enough).
Synthetic non-6c rooms (grain mill, ferry house), the watchroom and the 17a stub; no model."""
import unittest
from pathlib import Path

from runtime import kit_agent, kit_floor
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, check_scope, guard_context
from runtime.state_context import InvalidChange
from test_kit_manifest_nonces import synthetic
from test_kit_room_review import ROOT, STUB, WATCH
from test_kit_watchroom_stalls import Stalls, landing

# 44 words: a pithy human-DM room opening (Brendon's harness case, rebuilt on the watchroom).
PITHY_OPENING = {'segments': [
    {'speaker': 'Narrator', 'text': 'An iron door stands ajar, lamplight leaking through the gap. Behind it someone '
                                    'hums the same four notes, over and over.'},
    {'speaker': 'Narrator', 'text': 'The stair keeps winding down past the door into the dark. Up here, only the '
                                    'humming and the light. What do you do?'}]}
TERSE_CHALLENGE = {'segments': [
    {'speaker': 'Narrator', 'text': 'His hand settles beside the bell cord.'},
    {'speaker': 'Watch warden', 'text': 'Who sent you?'}]}


def N(text):
    return {'speaker': 'Narrator', 'text': text}


def plan(scope, focus=None, **extra):
    return {'public_brief': {'scope': scope, **extra.pop('brief', {})}, 'focus_actor': focus or 'none',
            'move': 'npc_move' if focus else 'world_description', **extra}


class Areas(Stalls):
    """Guards for a look in each area: the synthetic mill and ferry house (inside, the keeper
    present), the watchroom landing and the 17a doorway (nobody to speak)."""

    def area(self, room, enter):
        runtime = self.start(str(self.write(synthetic(room))) if room in ('mill', 'ferry') else room)
        if enter:
            revision, _ = runtime.load()
            runtime.commit('in', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'In.'}])
        bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10))
        packet = bridge.prepare('I look around.', 'look', one_pass=True)
        body = runtime.pending_kit_turn(packet['turn_id'])['body']
        guards = guard_context(runtime.source(), body)
        npc = next(((key, label) for key, label in guards['speakers'].items()
                    if (runtime.load()[1]['actors'].get(key) or {}).get('location') == runtime.load()[1]['area']),
                   (None, None))
        return guards, npc

    def each(self):
        for room, enter in (('mill', True), ('ferry', True), (WATCH, False), (STUB, False)):
            with self.subTest(room=str(room)):
                yield self.area(room, enter)


class TerseValidTurnsPass(Areas):
    def test_terse_lines_pass_in_every_area(self):
        for guards, (key, npc) in self.each():
            cases = [(plan('feature'), [N('What do you do?')]),
                     (plan('feature'), [N('Iron door. A stair down. Roll Perception.')]),
                     (plan('call'), [N('Roll Perception.')])]
            if npc:
                say = lambda text: {'speaker': npc, 'text': text}
                cases += [(plan('exchange', key), [say('Who sent you?')]),
                          (plan('exchange', key), [say('Stay down.')]),
                          (plan('exchange', key), [N('His hand settles beside the bell cord.'), say('Who sent you?')]),
                          (plan('exchange', key), [N('Roll initiative.')]),
                          (plan('exchange', key), [N('He swings. Miss. Steel sparks.'), N('Your move.')]),
                          (plan('exchange', key), [N('He reaches for the bell.'), N('Roll Dexterity.')])]
            for p, segments in cases:
                check_scope(segments, p, guards)


class JunkFails(Areas):
    def test_padded_mood_that_hands_nothing_over_fails_in_every_area(self):
        for guards, (key, npc) in self.each():
            junk = [(plan('feature'), [N('Shadows gather on the iron door like old regret, and the stair breathes '
                                         'cold air that tastes of rain and endings.'), N('Nothing moves, save the hush.')]),
                    (plan('feature'), [N('The door and the stair sit under a heavy hush; somewhere far off thunder '
                                         'seems to roll and roll.')]),
                    (plan('feature'), [N('Door, stair, dust. Who could say how long the silence has lasted here, or '
                                         'why it feels like grief?')])]
            if npc:
                junk += [(plan('exchange', key), [N('The air is heavy and still and quiet tonight.'),
                                                  {'speaker': npc, 'text': 'Hm.'}]),
                         (plan('exchange', key), [N('He stares at nothing; the lamp is low, like a check left unpaid.')])]
            for p, segments in junk:
                with self.assertRaisesRegex(InvalidChange, 'handing the floor back'):
                    check_scope(segments, p, guards)


class Declared(unittest.TestCase):
    def test_a_declared_kind_must_be_in_the_speech(self):
        with self.assertRaisesRegex(InvalidChange, 'hands_off says check_call'):
            check_scope([N('What do you do?')], plan('feature', hands_off={'kind': 'check_call', 'reason': 'x'}))
        check_scope([N('Roll Perception.')], plan('feature', hands_off={'kind': 'check_call', 'reason': 'a look'}))

    def test_none_needs_a_reason_and_is_refused_where_a_handoff_is_required(self):
        quiet = [N('The lamp burns low and even on its hook, and the room is still.')]
        check_scope(quiet, plan('feature', hands_off={'kind': 'none', 'reason': 'he is still deciding'}))
        with self.assertRaisesRegex(InvalidChange, 'reason'):
            check_scope(quiet, plan('feature', hands_off={'kind': 'none', 'reason': ' '}))
        with self.assertRaisesRegex(InvalidChange, 'handing the floor back'):
            check_scope(quiet, plan('feature', hands_off={'kind': 'none', 'reason': 'x'}), required=True)

    def test_the_shape_is_checked_with_the_plan(self):
        with self.assertRaisesRegex(InvalidChange, 'hands_off is'):
            kit_floor.declared({'hands_off': {'kind': 'monologue', 'reason': 'x'}})
        self.assertIn('hands_off', kit_agent.PLAN_SCHEMA['properties'])
        self.assertIn('hands_off', kit_agent.OPTIONAL_PLAN_KEYS)

    def test_npc_challenge_means_the_focus_actor(self):
        guards = {'speakers': {'miller': 'Floury miller', 'boy': 'Mill boy'}, 'brief_speakers': ('Floury miller', 'Mill boy')}
        declared = plan('exchange', 'miller', hands_off={'kind': 'npc_challenge', 'reason': 'he demands'})
        check_scope([{'speaker': 'Floury miller', 'text': 'Out of my mill.'}], declared, guards)
        with self.assertRaisesRegex(InvalidChange, 'npc_challenge'):
            check_scope([{'speaker': 'Mill boy', 'text': 'He wants you out.'}], declared, guards)


class AnsweringALook(unittest.TestCase):
    LOOK = [N('The serpents carved up each pillar are worn smooth where hands have touched them.'),
            N('One serpent near the floor has had its head broken off and carried away.')]

    def test_answering_the_players_own_look_hands_back_by_itself(self):
        check_scope(self.LOOK, plan('feature', brief={'reply_to': 'look at the pillars'}), {'kind': 'observe'})

    def test_but_not_without_a_reply_or_on_a_turn_that_is_not_a_look(self):
        with self.assertRaisesRegex(InvalidChange, 'handing the floor back'):
            check_scope(self.LOOK, plan('feature', brief={'reply_to': 'none'}), {'kind': 'observe'})
        with self.assertRaisesRegex(InvalidChange, 'handing the floor back'):
            check_scope(self.LOOK, plan('feature', brief={'reply_to': 'I wait'}), {'kind': 'social'})
        with self.assertRaisesRegex(InvalidChange, 'handing the floor back'):
            check_scope(self.LOOK, plan('feature', brief={'reply_to': 'look at the pillars'}), {'kind': 'observe'},
                        required=True)


class HarnessCasesOnTheBridge(Stalls):
    def test_a_pithy_44_word_opening_and_a_ten_word_challenge_commit(self):
        self.assertEqual(sum(len(s['text'].split()) for s in PITHY_OPENING['segments']), 44)
        packet = self.bridge.prepare(opening=True, one_pass=True, turn_id='open')
        p = self.plan_for(packet)
        p['public_brief'].update(scope='feature')
        self.assertTrue(self.bridge.complete('open', {'decision': p, 'performance': PITHY_OPENING})['spoken'])
        self.go_in()
        packet = self.bridge.prepare('"Evening. I am not here for trouble."', 'say', one_pass=True)
        p = self.plan_for(packet, move='npc_reply', focus_actor='warden', table_presence='quiet')
        p['improv_read'].update(actor_ref='warden', actor_basis='motive')
        p['public_brief'].update(scope='exchange', reply_to='I am not here for trouble')
        self.assertTrue(self.bridge.complete('say', {'decision': p, 'performance': TERSE_CHALLENGE})['spoken'])


class RestatingTheHandoff(Stalls):
    """The decision is fixed for a turn, but how the turn hands over is Kit's answer to a handoff
    rejection: she may restate hands_off on the resubmit, and nothing else."""

    def test_a_handoff_reject_is_answered_by_declaring_not_by_appending_a_prompt(self):
        packet = self.bridge.prepare(opening=True, one_pass=True, turn_id='open')
        p = self.plan_for(packet, hands_off=None)
        p.pop('hands_off')
        p['public_brief'].update(scope='feature')
        with self.assertRaisesRegex(InvalidChange, 'handing the floor back'):
            self.bridge.complete('open', {'decision': p, 'performance': landing()})
        with self.assertRaisesRegex(InvalidChange, 'already fixed'):
            self.bridge.complete('open', {'decision': {**p, 'table_presence': 'brief'}, 'performance': landing()})
        p['hands_off'] = {'kind': 'none', 'reason': 'the landing is set; the player has not acted yet'}
        spoken = self.bridge.complete('open', {'decision': p, 'performance': landing()})['spoken']
        self.assertNotIn('What do you do', spoken)
        self.assertEqual(self.runtime.committed_kit_turn('open')['trace'].get('hands_off', p['hands_off']),
                         p['hands_off'])


class NoWordFloorsOrLists(unittest.TestCase):
    def test_the_word_floors_and_lists_are_gone(self):
        for name in ('SANITY_MIN_WORDS', 'FEATURE_MIN_THINGS', '_THING_NOISE', '_HANDOFF_PHRASE', '_HANDOFF_CALL',
                     'FEATURE_MIN_WORDS', 'EXCHANGE_MIN_WORDS'):
            self.assertFalse(hasattr(kit_agent, name), name)

    def test_the_replay_adds_no_lines_to_kits_speech(self):
        text = (ROOT / 'scripts/watchroom_replay.py').read_text()
        self.assertNotIn('What do you do?\'', text.split('PITHY = {')[0] + text.split('def pithy_turns')[1])
        self.assertNotIn('def hand_off', text)
        self.assertNotIn('follow_contract', text)

    def test_the_limits_state_function(self):
        limits = kit_agent.performance_limits()
        self.assertIn('hands_off', limits)
        self.assertNotIn('words outside', limits['feature'])


if __name__ == '__main__':
    unittest.main()
