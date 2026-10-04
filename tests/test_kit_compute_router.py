"""PR4 (plan update #3): a deterministic compute router. The engine decides routine, normal
or consequential from action_kind, a pending ruling, an important NPC, the active brief and
state change. Same model and same contract on every tier; routine turns ask for less.
Watchroom fixture; no model."""
import unittest

from runtime import kit_router
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from runtime.state_context import InvalidChange
from test_kit_manifests import WAITING
from test_kit_watchroom_stalls import Stalls

WAIT = 'I wait on the landing and listen to the humming.'


class RouteIsPure(unittest.TestCase):
    def test_the_tiers(self):
        quiet = [{'type': 'beat'}]
        cases = [
            (('opening', [], {}), 'consequential'),
            (('exit', [{'type': 'move'}], {}), 'consequential'),
            (('social', quiet, {}, ['Watch warden'], ['Watch warden']), 'consequential'),
            (('social', quiet, {}, ['Card player'], ['Watch warden']), 'normal'),
            (('threshold_look', quiet, {}), 'routine'),
            (('check_request', quiet, {}), 'routine'),
            (('threshold_look', quiet, {}, [], [], [{'id': 'h'}]), 'consequential'),
            (('called_check', [{'type': 'pending_check', 'check': None}], {}), 'routine'),
            (('called_check', [{'type': 'pending_check', 'check': None}, {'type': 'claim_learned'}], {}), 'consequential'),
        ]
        for args, tier in cases:
            with self.subTest(args):
                self.assertEqual(kit_router.route(*args)['tier'], tier)
                self.assertEqual(kit_router.route(*args), kit_router.route(*args))   # deterministic

    def test_a_held_description_is_consequential(self):
        self.assertEqual(kit_router.route('called_check', [], {}, held=True)['tier'], 'consequential')


class RouterOnTheBridge(Stalls):
    def setUp(self):
        super().setUp()
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10),
                                    manifests=True)

    def routine_plan(self, packet):
        plan = self.plan_for(packet)
        for key in ('appraisal', 'memory_refs', 'tone', 'player_note', 'player_mood', 'turn_mode',
                    'observed_event', 'detail'):
            plan.pop(key, None)
        for key in ('story_anchor', 'story_basis', 'actor_ref', 'actor_basis'):
            plan['improv_read'].pop(key)
        plan['public_brief'].update(reply_to='I wait on the landing', scope='feature')
        return plan

    def echo(self, packet):
        return {'session': packet['session_manifest']['hash'], 'room': packet['room_manifest']['hash']}

    def test_an_empty_landing_wait_is_routine_and_asks_for_less(self):
        packet = self.bridge.prepare(WAIT, 'w', one_pass=True)
        compute = packet['input']['private']['compute']
        self.assertEqual(compute['tier'], 'routine')
        self.assertTrue(any(line.startswith('Routine turn') for line in packet['first_try']))
        plan = self.routine_plan(packet)
        self.bridge.complete('w', {'decision': plan, 'performance': WAITING, 'manifest': self.echo(packet)})
        trace = self.runtime.committed_kit_turn('w')['trace']
        self.assertEqual(trace['appraisal']['label'], 'none')
        self.assertEqual(trace['improv_read']['kit_choice'], plan['improv_read']['kit_choice'])  # Kit's own

    def test_a_turn_with_the_warden_is_consequential_and_asks_for_everything(self):
        self.go_in()
        packet = self.bridge.prepare('"Evening. Quiet night?"', 's', one_pass=True)
        self.assertEqual(self.runtime.pending_kit_turn('s')['body']['compute']['tier'], 'consequential')
        self.assertNotIn('compute', packet['input']['private'])   # the full contract, nothing added
        plan = self.routine_plan(packet)
        with self.assertRaisesRegex(InvalidChange, 'Incomplete'):
            self.bridge.complete('s', {'decision': plan, 'performance': WAITING, 'manifest': self.echo(packet)})

    def test_someone_heard_through_the_door_makes_it_count(self):
        """Watchroom T5: on the landing, speaking to the warden inside is not routine."""
        self.bridge.prepare('Nik says through the gap: "Evening. I am not here for trouble."', 't5', one_pass=True)
        self.assertEqual(self.runtime.pending_kit_turn('t5')['body']['compute']['tier'], 'consequential')

    def test_every_tier_gets_the_same_contract(self):
        routine = self.bridge.prepare(WAIT, 'w', one_pass=True)
        self.bridge.abandon('w')
        self.go_in()
        heavy = self.bridge.prepare('"Evening. Quiet night?"', 's', one_pass=True)
        self.assertEqual(routine['session_manifest']['hash'], heavy['session_manifest']['hash'])
        self.assertNotIn('model', routine['input']['private'])


class PendingRulingTier(unittest.TestCase):
    """Nagatha's #96 review: the docstring and QUIET_EVENT_TYPES now say the same thing."""

    def test_a_pending_check_alone_is_routine(self):
        from runtime import kit_router
        events = [{'type': 'pending_check', 'check': None}, {'type': 'beat', 'tags': ['check']}]
        self.assertEqual(kit_router.route('called_check', events, {})['tier'], 'routine')

    def test_a_held_description_makes_it_consequential(self):
        from runtime import kit_router
        events = [{'type': 'pending_check', 'check': None}]
        self.assertEqual(kit_router.route('called_check', events, {}, held=True)['tier'], 'consequential')


if __name__ == '__main__':
    unittest.main()
