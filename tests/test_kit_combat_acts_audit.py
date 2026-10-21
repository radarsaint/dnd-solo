"""The #122 audit (Brendon, 2026-10-18), three holes, synthetic fixture rooms, dice pinned (all 10s):
(a) a declared combat act that hits a pending ruling (an Avrae ask, an object act's ruling) must
commit nothing: no beat, the staged turn dropped, main's pending ruling raised;
(b) a required combat_acts offer that Kit's decision omits falls back to main's routing, as null
and [] do (held to real main's recorded outcome in test_kit_combat_acts_fallback);
(c) a late reaction answers the event it names, never a guessed first event."""
import json
import unittest

from runtime import kit_combat_acts
from runtime.kit_agent import KitAgent, KitChatBridge, PendingRuling, pending_ruling_result
from runtime.state_context import HostSequenceError
from test_kit_combat_acts_retarget import kiln
from test_kit_combat_acts_slice2 import plan_for
from test_kit_review101c import Arena, rogue, warlock

SPOKEN = {'performance': {'segments': [{'speaker': 'Narrator', 'text': 'You hold.'}]}}
NO_ROLL = [{'kind': 'attack', 'order': 1, 'target': 'imp', 'weapon': 'dagger', 'says': 'Dagger at the imp'}]
OBJECT = [{'kind': 'object', 'order': 1, 'says': 'I kick the brazier over'}]


def snapshot(runtime):
    revision, state = runtime.load()
    return revision, json.dumps(state, sort_keys=True), json.dumps(runtime.recent_kit_turns(limit=5), sort_keys=True)


def offered(test):
    arena = kiln(test, warlock(hp=60, gear=['dagger']))
    bridge = KitChatBridge(arena.runtime, arena.adjudicator)
    packet = bridge.prepare('Dagger at the imp.', 't', one_pass=True)
    test.assertIn('combat_acts', packet['input']['private']['acts'])
    return arena, bridge, packet


class DeclaredPendingRulingCommitsNothing(unittest.TestCase):
    def test_an_avrae_ask_raises_and_commits_no_beat(self):
        arena, bridge, packet = offered(self)
        before = snapshot(arena.runtime)
        with self.assertRaises(PendingRuling) as caught:
            bridge.complete('t', {'decision': plan_for(packet, combat_acts=NO_ROLL), **SPOKEN})
        self.assertIn('Avrae', str(caught.exception))
        self.assertFalse(pending_ruling_result(caught.exception)['committed'])
        self.assertEqual(snapshot(arena.runtime), before, 'an ask records nothing, as main\'s prepare')
        with self.assertRaises(HostSequenceError):  # the staged turn is gone
            arena.runtime.pending_kit_turn('t')

    def test_a_declared_ruling_is_a_refused_attempt_not_a_beat(self):
        arena, bridge, packet = offered(self)
        turns = json.dumps(arena.runtime.recent_kit_turns(limit=5), sort_keys=True)
        with self.assertRaises(PendingRuling) as caught:
            bridge.complete('t', {'decision': plan_for(packet, combat_acts=OBJECT), **SPOKEN})
        self.assertIn('kick the brazier over', str(caught.exception))
        self.assertEqual(json.dumps(arena.runtime.recent_kit_turns(limit=5), sort_keys=True), turns)
        _, state = arena.runtime.load()
        self.assertEqual(len(state['refused_attempts']), 1)
        self.assertNotIn('combat_declare', json.dumps(state))
        with self.assertRaises(HostSequenceError):
            arena.runtime.pending_kit_turn('t')

    def test_the_staged_path_drops_the_turn_too(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger']))
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        packet = bridge.prepare('Dagger at the imp.', 't')
        before = snapshot(arena.runtime)
        bridge.decide('t', plan_for({'input': {'private': packet['input']}}, combat_acts=NO_ROLL))
        with self.assertRaises(PendingRuling):
            bridge.finish('t', SPOKEN['performance'])
        self.assertEqual(snapshot(arena.runtime), before)
        with self.assertRaises(HostSequenceError):
            arena.runtime.pending_kit_turn('t')


class OmittedIsUndeclared(unittest.TestCase):
    def test_an_omitted_required_key_is_mains_pending_ruling(self):
        arena, bridge, packet = offered(self)
        plan = plan_for(packet)
        plan.pop('combat_acts', None)
        with self.assertRaises(PendingRuling) as caught:
            bridge.complete('t', {'decision': plan, **SPOKEN})
        self.assertEqual(pending_ruling_result(caught.exception)['stage'], 'pending_ruling')
        with self.assertRaises(HostSequenceError):
            arena.runtime.pending_kit_turn('t')

    def test_the_api_path_falls_back_on_omitted_null_or_empty(self):
        for declared in ('omitted', None, []):
            with self.subTest(declared=declared):
                arena = kiln(self, warlock(hp=60, gear=['dagger']))
                before = snapshot(arena.runtime)

                class Model:
                    def plan(inner, planning_input):
                        plan = plan_for({'input': {'private': planning_input}})
                        plan.pop('combat_acts', None)
                        if declared != 'omitted':
                            plan['combat_acts'] = declared
                        return plan

                    def perform(inner, payload, performance_variant=None):
                        raise AssertionError('main holds the turn before any performance')

                with self.assertRaises(PendingRuling):
                    KitAgent(arena.runtime, Model(), arena.adjudicator).turn('Dagger at the imp.', 't')
                self.assertEqual(snapshot(arena.runtime), before)


class LateReactionMatchesItsEvent(unittest.TestCase):
    """The kiln round leaves two unprompted hits on the warlock: the imp's fire spit (7) and the
    kobold slinger's stone (4)."""

    @staticmethod
    def rebuke(target=None):
        entry = {'kind': 'reaction', 'order': 1, 'reaction': 'hellish_rebuke', 'says': 'Hellish Rebuke',
                 'roll': '!cast hellish rebuke 2d10 = 12 fire'}
        return [{**entry, 'target': target}] if target else [entry]

    def arena(self):
        arena = Arena(self, 'kiln', sheet=warlock(), roll=lambda: 10)
        arena.act('Initiative 25. I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')
        self.assertEqual([e['attacker'] for e in arena.fight['unprompted']], ['imp', 'archer'])
        return arena

    def test_naming_the_second_attacker_answers_its_hit(self):
        arena = self.arena()
        result = arena.act('Hellish Rebuke on the slinger!', combat_acts=self.rebuke('archer'))
        self.assertIn('Hellish Rebuke: 12 fire damage to the kobold slinger.', result.public_event)
        self.assertEqual(arena.fight['hp']['imp'], 18)
        self.assertEqual([e['attacker'] for e in arena.fight['unprompted']], ['imp'])

    def test_no_target_with_two_attackers_is_refused_not_guessed(self):
        arena = self.arena()
        result = arena.act('Hellish Rebuke!', combat_acts=self.rebuke())
        self.assertIn('say whose hit it answers', result.public_event)
        self.assertEqual(arena.fight['hp'], {'archer': 7, 'imp': 18})
        self.assertEqual(len(arena.fight['unprompted']), 2)
        self.assertEqual(arena.state['pc_resources']['slots']['1']['used'], 0, 'nothing spent')

    def late(self, arena, events, target=None):
        state = arena.state
        state['combat']['unprompted'] = events
        multi = kit_combat_acts.to_act(self.rebuke(target), arena.runtime.source(), state)
        return multi['steps'][0]['act']

    def test_a_named_foe_that_did_not_hit_is_refused(self):
        arena = self.arena()
        imp = arena.fight['unprompted'][0]
        act = self.late(arena, [imp], 'archer')
        self.assertEqual(act['kind'], 'refused')
        self.assertEqual(act['because'], 'there is no hit from the kobold slinger for it to answer')

    def test_one_attacker_twice_answers_the_latest(self):
        arena = self.arena()
        imp = arena.fight['unprompted'][0]
        later = {**imp, 'damage': 3}
        for target in (None, 'imp'):
            with self.subTest(target=target):
                act = self.late(arena, [imp, later], target)
                self.assertEqual((act['kind'], act['event']), ('late_reaction', later))

    def test_one_attacker_alone_needs_no_name(self):
        arena = self.arena()
        imp = arena.fight['unprompted'][0]
        act = self.late(arena, [imp])
        self.assertEqual((act['kind'], act['event'], act['target']), ('late_reaction', imp, 'imp'))

    def test_nothing_to_answer_is_still_the_engines_fizzle(self):
        arena = self.arena()
        act = self.late(arena, [])
        self.assertEqual((act['kind'], act['event']), ('late_reaction', None))


if __name__ == '__main__':
    unittest.main()
