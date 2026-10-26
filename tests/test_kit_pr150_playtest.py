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
            with self.subTest(line):
                result = self.resolve(self.runtime, line)  # a bid for a check, never refused (#150 retest)
                self.assertEqual(result.kind, 'check_request')
                self.assertIn('search', result.events[0]['tags'])

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



class RetestBoilerplate(unittest.TestCase):
    """#150 retest 3: the degraded-mode and abandon advice is stripped before a reason is cut."""

    def test_degraded_advice_is_not_a_reason(self):
        reason = ('Kit named the DC aloud. No turn was committed. ' + kit_agent.DEGRADED_INSTRUCTION)
        self.assertEqual(kit_manifest.strip_boilerplate(reason), 'Kit named the DC aloud.')
        cut = reason[:400]  # an older record cut mid-advice
        self.assertEqual(kit_manifest.strip_boilerplate(cut), 'Kit named the DC aloud.')
        self.assertEqual(kit_manifest.strip_boilerplate('Too long. ' + kit_agent.ABANDON_INSTRUCTION), 'Too long.')

    def test_the_notice_shows_only_the_reasons(self):
        notice = kit_manifest.rejection_notice(streak(
            'A. ' + kit_agent.DEGRADED_INSTRUCTION, 'B. No turn was committed. ' + kit_agent.DEGRADED_INSTRUCTION), 'h')
        self.assertEqual(notice['reasons'], ['A.', 'B.'])

    def test_a_stored_attempt_reason_is_stripped_then_cut(self):
        reason = 'x' * 10 + '. ' + kit_agent.DEGRADED_INSTRUCTION
        self.assertNotIn('Degraded', kit_manifest.strip_boilerplate(reason)[:400])


class RegularCastingIsNotARitual(Stalls):
    """#150 retest 2."""

    def test_negated_or_regular_casting(self):
        for line in ('I cast Detect Magic, regular casting, no ritual.', 'I cast detect magic, not as a ritual.',
                     'I cast Detect Magic normally, without the ritual.', 'I cast detect magic using a slot.'):
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertNotIn('ritual', result.events[0]['tags'])
                self.assertNotIn('advance_time', [e['type'] for e in result.events])

    def test_a_ritual_is_still_a_ritual(self):
        for line in ('I cast Detect Magic as a ritual.', 'Ritual casting: detect magic.'):
            with self.subTest(line):
                self.assertIn('ritual', self.resolve(self.runtime, line).events[0]['tags'])


class DetectMagicObjects(Stalls):
    """#150 retest 5: auras counted by object and placed; placement in Kit's private packet."""

    def magical(self, **objects):
        source = copy.deepcopy(self.runtime.source())
        fact = source['facts']['door_ajar']
        fact['magic'] = 'illusion'
        if objects:
            fact['magic_objects'] = objects
        return source

    def test_objects_are_counted_and_placed(self):
        source = self.magical(count=8, what='mirrors', where='in the wall niches')
        revision, state = self.runtime.load()
        result = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=source).resolve(
            'I cast detect magic.', revision, state)
        self.assertIn('8 magical auras', result.public_event)
        self.assertIn('8 mirrors in the wall niches', result.public_event)
        self.assertNotIn(source['facts']['door_ajar']['text'], result.public_event)

    def test_kit_gets_the_aura_locations_privately(self):
        self.runtime.db.execute('UPDATE source SET body=? WHERE id=1', (kit_agent.encode(
            self.magical(count=3, what='lamps', where='along the east wall')),))
        self.runtime.db.commit()
        packet = self.bridge.prepare('I cast detect magic.', 'dm', one_pass=True)
        auras = packet['input']['private']['detect_magic']['auras']
        self.assertEqual(auras, [{'fact': 'door_ajar', 'school': 'illusion', 'count': 3, 'what': 'lamps',
                                  'where': 'along the east wall'}])
        self.assertNotIn('detect_magic', packet['input']['public'])

    def test_without_objects_one_aura_per_fact(self):
        source = self.magical()
        self.assertEqual(kit_agent.detect_magic_auras(source, 'landing')[0]['count'], 1)


class InputWhileATurnWaits(Stalls):
    """#150 retest 4: a refused input while a prepared turn waits does not stale that turn."""

    def test_the_waiting_turn_stays_current(self):
        self.go_in()
        self.bridge.prepare('I look around the room.', 'wait', one_pass=True)
        revision, _ = self.runtime.load()
        with self.assertRaises(PendingRuling) as caught:
            self.bridge.prepare('I smash the chest.', 'smash', one_pass=True)
        self.assertIn('once the turn in progress is committed', str(caught.exception))
        self.assertEqual(self.runtime.load()[0], revision)  # no bump: 'wait' still current
        self.assertEqual(self.runtime.db.execute('SELECT COUNT(*) FROM queued_attempts').fetchone()[0], 1)

    def test_the_queue_flushes_once_nothing_waits(self):
        self.go_in()
        self.bridge.prepare('I look around the room.', 'wait', one_pass=True)
        with self.assertRaises(PendingRuling):
            self.bridge.prepare('I smash the chest.', 'smash', one_pass=True)
        self.runtime.db.execute('DELETE FROM kit_pending')
        self.runtime.db.commit()
        revision, _ = self.runtime.load()
        self.assertEqual(self.runtime.flush_queued_attempts(), revision + 1)
        state = self.runtime.load()[1]
        self.assertEqual(state['refused_attempts'][-1]['action'], 'I smash the chest.')
        self.assertIsNone(self.runtime.flush_queued_attempts())

    def test_with_nothing_waiting_an_attempt_commits_at_once(self):
        self.go_in()
        self.runtime.db.execute('DELETE FROM kit_pending')
        self.runtime.db.commit()
        revision, _ = self.runtime.load()
        self.assertEqual(self.runtime.record_refused_attempt('I smash the chest.', 'r'), revision + 1)


if __name__ == '__main__':
    unittest.main()
