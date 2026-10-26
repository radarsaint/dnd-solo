"""Kit II's #150 playtest (/workspace/kit2/pr150-log.md): the rejection notice keeps every
reason and reads as guidance for the next decision; a missing decision field is named; a
search with a walk in it is not a simple act; Detect Magic senses the room's magic or says
there is none. Watchroom fixture, dice pinned, no model."""
import copy
import json
import unittest

from runtime import kit_agent, kit_manifest
from runtime.kit_agent import PendingRuling, RoomAdjudicator
from runtime.state_context import InvalidChange
from test_kit_watchroom_stalls import Stalls


def streak(*reasons):
    return [{'attempts': [{'outcome': 'rejected', 'reason': r} for r in reasons]}]


class RejectionNotice(unittest.TestCase):
    def test_keeps_every_reason_without_repeats(self):
        notice = kit_manifest.rejection_notice(streak(
            'Bad tone. No turn was committed.', 'Missing goal. No turn was committed.',
            'Bad tone. No turn was committed.', 'Too long.'), 'h')
        self.assertEqual(notice['rejections'], 4)
        self.assertEqual(notice['reasons'], ['Bad tone.', 'Missing goal.', 'Too long.'])

    def test_reads_as_guidance_for_the_next_decision(self):
        note = kit_manifest.rejection_notice(streak('a', 'b'), 'h')['note']
        self.assertNotIn('Fix exactly', note)
        self.assertIn('Before you write this decision', note)

    def test_no_streak_no_notice(self):
        self.assertIsNone(kit_manifest.rejection_notice(streak('a'), 'h'))


class MissingFieldsNamed(unittest.TestCase):
    def test_incomplete_decision_names_the_missing_fields(self):
        plan = {k: None for k in kit_agent.PLAN_SCHEMA['required'] if k not in ('tone', 'player_mood')}
        plan['bogus'] = 1
        with self.assertRaises(InvalidChange) as caught:
            kit_agent.check_plan(plan, [], 'x')
        message = str(caught.exception)
        self.assertIn('missing player_mood, tone', message)
        self.assertIn('unexpected bogus', message)


class SearchBeatsSimpleAct(Stalls):
    def test_a_walk_with_a_search_is_not_a_simple_act(self):
        for line in ('I walk the wall and search it for seams.', 'I step over and check the chest for traps.',
                     'I kneel and examine the floor.'):
            with self.subTest(line), self.assertRaises(PendingRuling):
                self.resolve(self.runtime, line)

    def test_a_plain_walk_is_still_a_simple_act(self):
        result = self.resolve(self.runtime, 'I walk over to the table.')
        self.assertIn('simple_act', result.events[0]['tags'])


class DetectMagic(Stalls):
    def test_no_magic_here_is_said_plainly(self):
        result = self.resolve(self.runtime, 'I cast Detect Magic as a ritual.')
        self.assertIn('no', result.public_event.split('ten minutes.')[1].casefold())
        self.assertIn('detect_magic', result.events[0]['tags'])

    def test_the_rooms_magic_is_sensed_without_reading_out_the_fact(self):
        source = copy.deepcopy(self.runtime.source())
        source['facts']['door_ajar']['magic'] = 'abjuration'
        revision, state = self.runtime.load()
        result = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=source).resolve(
            'I cast detect magic.', revision, state)
        self.assertIn('a magical aura', result.public_event)
        self.assertIn('abjuration', result.public_event)
        self.assertNotIn(source['facts']['door_ajar']['text'], result.public_event)
        self.assertIn('door_ajar', result.events[0]['evidence'])


if __name__ == '__main__':
    unittest.main()
