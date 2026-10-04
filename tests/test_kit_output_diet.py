"""PR3 (plan update #3): the output diet. Kit writes one line per real choice; the engine fills
what it already knows; speech has ceilings that never cut the actor's move, a due hook, the
chosen detail, or Kit's single reaction. Watchroom fixture (detail checks on a synthetic deal);
no model."""
import copy
import json
import unittest

from runtime import kit_agent, kit_detail, kit_voice
from runtime.kit_agent import check_scope, ceiling_note, actor_speakers
from runtime.state_context import InvalidChange
from test_kit_watchroom_stalls import Stalls, landing

WORD = 'stone '


def words(n, word='stone'):
    return ' '.join([word] * n) + '.'


class LeanDecision(Stalls):
    def lean(self, packet):
        plan = self.plan_for(packet)
        plan.pop('observed_event', None)
        plan.pop('detail', None)
        for key in ('player_bid', 'connection'):
            plan['improv_read'].pop(key, None)
        for key in ('objective', 'visible_cue', 'player_opening'):
            plan['public_brief'].pop(key, None)
        plan['public_brief'].update(scope='feature')
        plan['improv_read']['kit_choice'] = 'Nik arrives quiet at a lit door; Kit lets the hum carry the threat.'
        return plan

    def test_a_lean_decision_commits_and_the_engine_fills_the_rest(self):
        packet = self.bridge.prepare(opening=True, one_pass=True, turn_id='o')
        plan = self.lean(packet)
        self.bridge.complete('o', {'decision': plan, 'performance': landing()})
        trace = self.runtime.committed_kit_turn('o')['trace']
        self.assertEqual(trace['observed_event'], packet['input']['private']['accepted_public_event'])
        self.assertEqual(trace.get('detail', kit_detail.NO_DETAIL), kit_detail.NO_DETAIL)

    def test_the_schema_no_longer_asks_for_the_dropped_fields(self):
        schema = kit_agent.PLAN_SCHEMA
        self.assertNotIn('observed_event', schema['required'])
        self.assertNotIn('detail', schema['required'])
        brief = schema['properties']['public_brief']['required']
        for key in ('objective', 'visible_cue', 'player_opening'):
            self.assertNotIn(key, brief)
        read = schema['properties']['improv_read']['required']
        self.assertEqual(sorted(read), ['actor_basis', 'actor_ref', 'kit_choice', 'story_anchor', 'story_basis'])
        for key in ('reply_to', 'scope', 'tactic', 'kit_focus', 'mirror', 'callback', 'npc_notice'):
            self.assertIn(key, brief)                    # the enums and the real choices stay

    def test_an_older_host_s_full_decision_still_commits(self):
        packet = self.bridge.prepare(opening=True, one_pass=True, turn_id='o')
        plan = self.plan_for(packet)
        plan['public_brief'].update(scope='feature', objective='Frame the door.', visible_cue='The lit gap.',
                                    player_opening='Knock, listen, or go down.')
        plan['improv_read'].update(player_bid='Nik arrives.', connection='The post is awake.')
        self.assertTrue(self.bridge.complete('o', {'decision': plan, 'performance': landing()})['spoken'])

    def test_the_lean_decision_is_smaller(self):
        packet = self.bridge.prepare(opening=True, one_pass=True, turn_id='o')
        full = self.plan_for(packet)
        self.assertLess(len(json.dumps(self.lean(packet))), len(json.dumps(full)) * 0.85)


class DealtDetailIsDrawIdPlusOneFact(unittest.TestCase):
    ORACLE = {'slot': 'landing/smell', 'status': 'open',
              'deal': [{'draw_id': 'd0.oil', 'card': 'oil', 'entry': 'lamp oil gone a little rancid',
                        'basis': 'the hooded lamp burns cheap oil', 'roots': ['lamp'], 'handle': 'douse the lamp'}]}

    def detail(self, **extra):
        fact = {'slot': 'landing/smell', 'kind': 'appearance', 'fact': 'Lamp oil from Waterdeep gone a little rancid.',
                'basis': 'the hooded lamp burns cheap oil', 'public': True, 'scope': 'scene',
                'procedure': 'none', 'change_reason': 'none'}
        return {'request': 'what does it smell like', 'slot': 'landing/smell', 'choice': 'd0.oil',
                'inventions': [fact], **extra}

    def check(self, detail):
        kit_detail.check_detail(detail, 'What does it smell like?', 'social', {}, {}, oracle=self.ORACLE)

    def test_a_dealt_card_needs_only_its_draw_id(self):
        detail = self.detail()
        self.check(detail)
        self.assertEqual(detail['owner'], 'none')            # filled, not asked for

    def test_an_override_still_writes_its_candidates_and_owner(self):
        with self.assertRaises(InvalidChange):
            self.check(self.detail(choice='override: the oil is wrong for this post tonight'))


class Ceilings(Stalls):
    def guards(self, **extra):
        return {'speakers': actor_speakers(self.runtime.source()), 'brief_speakers': ('Watch warden',), **extra}

    def plan(self, scope, focus='none', **update):
        return {'public_brief': {'scope': scope}, 'focus_actor': focus, 'table_presence': 'brief',
                'improv_read': {'actor_ref': focus}, **update}

    def seg(self, speaker, n, word='stone'):
        return {'speaker': speaker, 'text': words(n, word)}

    def test_an_exchange_s_narration_has_a_ceiling(self):
        segments = [self.seg('Narrator', 95), self.seg('Watch warden', 5)]
        check_scope(segments, self.plan('exchange', 'warden'), self.guards())  # advisory: never a reject
        self.assertIn('ceiling', ceiling_note(segments, self.plan('exchange', 'warden'), self.guards()))

    def test_kit_s_remarks_after_the_first_count_outside_showtime(self):
        segments = [self.seg('Narrator', 50), self.seg('Watch warden', 10), self.seg('Kit', 10), self.seg('Kit', 45)]
        self.assertIn('ceiling', ceiling_note(segments, self.plan('exchange', 'warden'), self.guards()))
        self.assertIsNone(ceiling_note(segments[:3], self.plan('exchange', 'warden'), self.guards()))

    def test_the_focus_actor_s_move_is_never_counted(self):
        check_scope([self.seg('Narrator', 40), self.seg('Watch warden', 120)], self.plan('exchange', 'warden'),
                    self.guards())

    def test_a_due_hook_s_raiser_is_never_counted(self):
        check_scope([self.seg('Narrator', 140), self.seg('Watch warden', 60)], self.plan('feature'),
                    self.guards(raisers=('Watch warden',)))

    def test_kit_s_single_reaction_is_never_counted(self):
        check_scope([self.seg('Narrator', 85), self.seg('Watch warden', 10), self.seg('Kit', 40)],
                    self.plan('exchange', 'warden'), self.guards())

    def test_the_chosen_detail_is_never_counted(self):
        fact = 'the lamp oil smells a little rancid and sweet like old fat on a cold pan'
        detail = {'inventions': [{'fact': fact, 'public': True}]}
        segments = [{'speaker': 'Narrator', 'text': words(140) + ' ' + fact[0].upper() + fact[1:] + '.'},
                    self.seg('Narrator', 5)]
        check_scope(segments, self.plan('feature', detail=detail), self.guards())

    def test_a_feature_s_narration_has_a_ceiling(self):
        segments = [self.seg('Narrator', 100), self.seg('Narrator', 60)]
        check_scope(segments, self.plan('feature'), self.guards())
        self.assertIn('ceiling', ceiling_note(segments, self.plan('feature'), self.guards()))

    def test_the_floors_stay(self):
        with self.assertRaisesRegex(InvalidChange, 'flat'):
            check_scope([self.seg('Narrator', 30), self.seg('Narrator', 30)], self.plan('feature'), self.guards())

    def test_the_ceilings_are_in_the_packet(self):
        self.assertIn('ceiling', kit_agent.performance_limits())


class CeilingsAreAdvisory(Stalls):
    """Nagatha's #95 review: the ceilings said soft but rejected outside degraded mode."""

    EXTRA = ('Far below, a cart rattles over cobbles and fades, and somewhere a dog answers it twice before '
             'the night swallows both. Cold air climbs the stair behind you and tugs at your sleeve, smelling '
             'of river mud, wet rope and smoke from a chimney you cannot see, while a moth knocks softly '
             'against the warm glass of a lantern hung somewhere above the turn of the stair.')

    def test_an_over_ceiling_turn_commits_with_a_note(self):
        packet = self.bridge.prepare(opening=True, one_pass=True)
        plan = self.plan_for(packet)
        plan['public_brief'].update(reply_to='none', scope='feature')
        speech = landing()
        speech['segments'].append({'speaker': 'Narrator', 'text': self.EXTRA})
        result = self.bridge.complete(packet['turn_id'], {'decision': plan, 'performance': speech})
        self.assertTrue(result['spoken'])
        record = self.runtime.committed_kit_turn(packet['turn_id'])
        self.assertIn('ceiling', record['over_ceiling'])


class OneKitRemarkUnlessPlayful(unittest.TestCase):
    def plan(self, mood):
        return {'table_presence': 'showtime', 'public_brief': {'npc_notice': 'none'},
                'player_mood': {'read': mood}}

    def segs(self, n):
        return [{'speaker': 'Kit', 'text': 'Look at the lamp.'}] * n + [{'speaker': 'Narrator', 'text': 'A card turns.'}]

    def test_showtime_is_one_remark_by_default(self):
        kit_voice.check_voice_presence(self.segs(1), self.plan('neutral'))
        with self.assertRaisesRegex(InvalidChange, 'Showtime'):
            kit_voice.check_voice_presence(self.segs(2), self.plan('neutral'))

    def test_a_playful_player_gets_up_to_three(self):
        kit_voice.check_voice_presence(self.segs(3), self.plan('playful'))
        with self.assertRaisesRegex(InvalidChange, 'Showtime'):
            kit_voice.check_voice_presence(self.segs(4), self.plan('playful'))


if __name__ == '__main__':
    unittest.main()
