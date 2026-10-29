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
        self.assertIn('missing: player_mood, tone', message)  # #129 wording
        self.assertIn('not allowed: bogus', message)


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
        source['facts']['door_ajar']['visible'] = True  # the ajar door is in plain sight
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

    def cast(self, source):
        revision, state = self.runtime.load()
        return RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=source).resolve(
            'I cast detect magic.', revision, state).public_event

    def test_visible_objects_get_a_count_and_a_vague_area(self):
        source = self.magical(count=8, what='mirrors', where='in the wall niches, third from the left',
                              visible=True, area='the wall niches')
        public = self.cast(source)
        self.assertIn('8 magical auras', public)
        self.assertIn('from the wall niches', public)
        self.assertNotIn('third from the left', public)
        self.assertNotIn('mirrors', public)
        self.assertNotIn(source['facts']['door_ajar']['text'], public)

    def test_a_hidden_object_is_never_named_or_located(self):
        # #150 retest 2 leak: 'a plain copper ring buried in the bone pile' reached the public line.
        source = self.magical(count=1, what='a plain copper ring', where='buried in the bone pile in the south alcove')
        public = self.cast(source)
        for word in ('ring', 'buried', 'bone', 'alcove', 'illusion', '1 '):
            self.assertNotIn(word, public)
        self.assertIn('cannot pin it to a place', public)

    def test_unmarked_objects_count_as_hidden(self):
        source = self.magical(count=2, what='the rusty manacles', where="on the east alcove's back wall")
        public = self.cast(source)
        self.assertNotIn('manacles', public)
        self.assertNotIn('2 the', public)
        self.assertNotIn('east', public)

    def test_mixed_visible_and_hidden(self):
        source = self.magical(count=2, what='manacles', where='on the wall', visible=True, area='the east alcove')
        source['facts']['door_ajar2'] = {'area': 'landing', 'visible': False, 'text': 'A ring in the bones.',
                                         'magic': 'abjuration',
                                         'magic_objects': {'count': 1, 'what': 'a ring', 'where': 'in the bones'}}
        public = self.cast(source)
        self.assertIn('2 magical auras within 30 feet (illusion), from the east alcove.', public)
        self.assertIn('as well', public)
        self.assertNotIn('abjuration', public)
        self.assertNotIn('ring', public)

    def test_kit_gets_the_aura_locations_privately(self):
        self.runtime.db.execute('UPDATE source SET body=? WHERE id=1', (kit_agent.encode(
            self.magical(count=3, what='lamps', where='along the east wall')),))
        self.runtime.db.commit()
        packet = self.bridge.prepare('I cast detect magic.', 'dm', one_pass=True)
        auras = packet['input']['private']['detect_magic']['auras']
        self.assertEqual(auras, [{'fact': 'door_ajar', 'school': 'illusion', 'count': 3, 'what': 'lamps',
                                  'where': 'along the east wall', 'hidden': True}])
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
            self.bridge.prepare('I steal everything in the room.', 'smash', one_pass=True)
        self.assertIn('once the turn in progress is committed', str(caught.exception))
        self.assertEqual(self.runtime.load()[0], revision)  # no bump: 'wait' still current
        self.assertEqual(self.runtime.db.execute('SELECT COUNT(*) FROM queued_attempts').fetchone()[0], 1)

    def test_the_queue_flushes_once_nothing_waits(self):
        self.go_in()
        self.bridge.prepare('I look around the room.', 'wait', one_pass=True)
        with self.assertRaises(PendingRuling):
            self.bridge.prepare('I steal everything in the room.', 'smash', one_pass=True)
        self.runtime.db.execute('DELETE FROM kit_pending')
        self.runtime.db.commit()
        revision, _ = self.runtime.load()
        self.assertEqual(self.runtime.flush_queued_attempts(), revision + 1)
        state = self.runtime.load()[1]
        self.assertEqual(state['refused_attempts'][-1]['action'], 'I steal everything in the room.')
        self.assertIsNone(self.runtime.flush_queued_attempts())

    def test_with_nothing_waiting_an_attempt_commits_at_once(self):
        self.go_in()
        self.runtime.db.execute('DELETE FROM kit_pending')
        self.runtime.db.commit()
        revision, _ = self.runtime.load()
        self.assertEqual(self.runtime.record_refused_attempt('I smash the chest.', 'r'), revision + 1)


if __name__ == '__main__':
    unittest.main()


class RetestTwoItems(Stalls):
    """#150 retest at 76d223d: structural search, Kit's ruling, 'wait' + act, resend window,
    Detect Magic that is still up."""

    def test_search_anywhere_in_the_sentence_beats_a_move_or_gesture(self):
        self.go_in()
        for line in ('I run my fingers along the mortar lines, hunting for a hidden catch.',
                     'I go over the west wall inch by inch for anything odd.',
                     'I poke around in the cobwebs with my staff.', 'I study the ledger closely.',
                     'I sift through the ashes.', 'I look behind the table.'):
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertEqual(result.kind, 'check_request')
                self.assertIn('search', result.events[0]['tags'])

    def test_an_unknown_act_on_a_thing_is_kits_ruling(self):
        self.go_in()
        result = self.resolve(self.runtime, 'I pour water over the ledger.')
        self.assertEqual(result.kind, 'kit_ruling')
        self.assertEqual(result.public_event, 'You try that.')
        self.assertNotIn(result.public_event, 'You try: "')
        self.assertIn('may call a check', result.events[0]['evidence'])

    def test_exploits_and_people_stay_refused(self):
        self.go_in()
        for line in ('I steal everything in the room.', 'I instantly open every lock.', "I steal the warden's keys."):
            with self.subTest(line), self.assertRaises(PendingRuling):
                self.resolve(self.runtime, line)

    def test_wait_then_an_act_is_an_act(self):
        self.go_in()
        result = self.resolve(self.runtime, 'Wait, before I roll, I yank the manacles off the wall.')
        self.assertEqual(result.kind, 'kit_ruling')

    def test_abandoned_prepares_do_not_use_up_the_resend_window(self):
        rows = [{'turn_id': 't0', 'manifest': {'session': 'S', 'room': 'R', 'sent': ['session', 'room']}}]
        rows += [{'turn_id': f'a{i}', 'manifest': {'session': 'S', 'room': 'R', 'sent': []}} for i in range(12)]
        self.assertEqual(kit_manifest.plan_sends(rows), {'session': set(), 'room': set()})
        self.assertEqual(kit_manifest.plan_sends(rows, committed={'t0'}), {'session': {'S'}, 'room': {'R'}})
        rows += [{'turn_id': f'c{i}', 'manifest': {'session': 'S', 'room': 'R', 'sent': []}} for i in range(8)]
        committed = {'t0'} | {f'c{i}' for i in range(8)}
        self.assertEqual(kit_manifest.plan_sends(rows, committed=committed), {'session': set(), 'room': set()})

    def test_detect_magic_still_up_senses_the_next_area(self):
        source = copy.deepcopy(self.runtime.source())
        inside = source['exits']['iron_door']['areas']
        revision, state = self.runtime.load()
        there = next(a for a in inside if a != state['area'])
        source['facts']['inside_aura'] = {'area': there, 'visible': False, 'text': 'A warded coin under the floor.',
                                         'magic': 'abjuration',
                                         'magic_objects': {'count': 1, 'what': 'a coin', 'where': 'under the floor'}}
        self.runtime.db.execute('UPDATE source SET body=? WHERE id=1', (kit_agent.encode(source),))
        self.runtime.db.commit()
        adjudicator = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=source)
        cast = adjudicator.resolve('I cast detect magic.', revision, state)
        self.assertIn('spell_running', [e['type'] for e in cast.events])
        self.runtime.commit('cast', revision, cast.events)
        revision, state = self.runtime.load()
        entered = adjudicator.resolve('I go through the iron door.', revision, state)
        self.assertIn('still up', entered.public_event)
        self.assertIn('cannot pin it to a place', entered.public_event)
        self.assertNotIn('coin', entered.public_event)
        self.assertIn('inside_aura', ' '.join(e['evidence'] for e in entered.events))

    def test_detect_magic_that_ended_does_not_sense(self):
        revision, state = self.runtime.load()
        cast = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=self.runtime.source()).resolve(
            'I cast detect magic.', revision, state)
        events = cast.events + [{'type': 'advance_time', 'seconds': 601, 'evidence': 'Time passes.'}]
        self.runtime.commit('cast', revision, events)
        revision, state = self.runtime.load()
        entered = self.resolve(self.runtime, 'I go through the iron door.')
        self.assertNotIn('Detect Magic', entered.public_event)
