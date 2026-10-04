"""PR-H: interruptible combat checkpoints (Brendon's 691e834 harness findings, rebuilt on the
roadcamp fixture, never 6c). Every die is pinned: NPC d20s come from the adjudicator's roll
override; the player's numbers are stated the way Avrae reports them.

1. Reaction window: Nik (AC 14, Shield, slots) took 38 damage and dropped without being
   offered Shield, though every hit (15-16) would have missed AC 19.
2. Flourish: "describe your kill" through ask_player left the bandit alive.
3. One gulp: the kill, the enemy attacks and the flight all resolved in one turn."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_combat
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
CAMP = ROOT / 'tests' / 'fixtures' / 'rooms' / 'roadcamp.json'
NIK = json.loads((ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json').read_text())
OPEN = 'Initiative 25. I stab the wagon-side cutthroat with my dagger, 18 to hit, 20 piercing.'
KILL_CAPTAIN = 'Initiative 25. I stab the bandit captain with my dagger, 18 to hit, 30 piercing.'


def rolls(*values, then=10):
    seq = list(values)
    return lambda: seq.pop(0) if seq else then


class Camp:
    def __init__(self, test, roll=lambda: 10, sheet=NIK):
        temp = tempfile.TemporaryDirectory()
        test.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        test.addCleanup(self.runtime.close)
        with mock.patch('runtime.state_context.secrets.token_hex', return_value='7' * 32):
            self.runtime.initialize(json.loads(CAMP.read_text()), 'camp')
        self.runtime.set_player_sheet(copy.deepcopy(sheet))
        self.adjudicator = RoomAdjudicator(roll=roll, source=self.runtime.source())

    def act(self, action):
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(action, revision, state)
        self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    @property
    def state(self):
        return self.runtime.load()[1]

    @property
    def fight(self):
        return self.state['combat']


def without_shield(sheet):
    sheet = copy.deepcopy(sheet)
    sheet['spells'] = {level: [s for s in names if s != 'Shield'] for level, names in sheet['spells'].items()}
    return sheet


class ReactionWindow(unittest.TestCase):
    def test_shield_is_offered_before_the_first_incoming_hit(self):
        camp = Camp(self)
        result = camp.act(OPEN)
        self.assertEqual(result.kind, 'combat_interstitial')
        self.assertTrue(result.public_event.endswith('That hits 15. Shield?'), result.public_event)
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['kind'], waiting['awaits'], waiting['options']),
                         ('reaction_window', 'player_answer', ['shield']))
        self.assertTrue(waiting['deferred_action_id'])
        self.assertEqual(camp.fight['pc_damage'], 0, 'stopped before damage')
        self.assertEqual(camp.state['actors']['cutthroat_a']['status'], 'dead', 'the PC\'s blow stands')

    def test_shield_turns_the_hits_that_would_land_into_misses_and_nik_stands(self):
        camp = Camp(self)
        camp.act(OPEN)
        result = camp.act('Yes, Shield.')
        self.assertEqual(result.kind, 'combat_round')
        fight = camp.fight
        self.assertEqual(fight['pc_damage'], 0)
        self.assertFalse(fight.get('pc_down'))
        self.assertEqual(fight['slots_spent'], {'1': 1})
        self.assertIsNone(fight.get('awaiting'))
        self.assertIn('Your turn.', result.public_event)
        self.assertFalse(fight.get('shield_up'), 'Shield ends at the start of your next turn')
        self.assertFalse(fight.get('reaction_used'), 'your reaction comes back on your turn')

    def test_declining_takes_the_hits(self):
        camp = Camp(self)
        camp.act(OPEN)
        offers = 1
        while camp.fight.get('awaiting'):  # each hit Shield could turn is offered; declining spends nothing
            camp.act('No, let it hit.')
            offers += 1
        self.assertEqual(offers, 5)  # the captain's three blows and the fire-side cutthroat's mace
        self.assertEqual(camp.fight['pc_damage'], 28)  # 6 + 6 + 5 from the captain, 11 from the fire-side cutthroat
        self.assertNotIn('slots_spent', camp.fight)

    def test_an_unclear_answer_asks_and_commits_nothing(self):
        camp = Camp(self)
        camp.act(OPEN)
        revision, state = camp.runtime.load()
        with self.assertRaisesRegex(PendingRuling, 'Shield'):
            camp.adjudicator.resolve('I look at the fire.', revision, state)

    def test_no_window_for_a_miss(self):
        camp = Camp(self, roll=lambda: 2)
        result = camp.act(OPEN)
        self.assertEqual(result.kind, 'combat_round')
        self.assertIsNone(camp.fight.get('awaiting'))

    def test_no_window_when_the_sheet_has_no_reaction(self):
        camp = Camp(self, sheet=without_shield(NIK))
        result = camp.act(OPEN)
        self.assertEqual(result.kind, 'combat_round')
        self.assertEqual(camp.fight['pc_damage'], 28)

    def test_no_window_with_no_slot_left(self):
        sheet = copy.deepcopy(NIK)
        sheet['slots'] = {'1': 0, '2': 0, '3': 0}
        camp = Camp(self, sheet=sheet)
        self.assertEqual(camp.act(OPEN).kind, 'combat_round')

    def test_no_second_window_once_the_reaction_is_spent(self):
        # The captain's first blow totals 15 (window); his second rolls 15 + 5 = 20, which beats
        # AC 19 even under Shield, and no window is offered: the reaction is spent.
        camp = Camp(self, roll=rolls(10, 15))
        camp.act(OPEN)
        result = camp.act('Shield!')
        self.assertEqual(result.kind, 'combat_round')
        self.assertEqual(camp.fight['pc_damage'], 6)

    def test_absorb_elements_answers_elemental_damage_only(self):
        sheet = {'spells': {'1': ['Absorb Elements']}, 'slots': {'1': 2}}
        fight = {'slots_spent': {}, 'reaction_used': False}
        self.assertEqual(kit_combat.reaction_options(sheet, fight, die=12, total=17, ac=14, dtype='fire'),
                         ['absorb elements'])
        self.assertEqual(kit_combat.reaction_options(sheet, fight, die=12, total=17, ac=14, dtype='slashing'), [])

    def test_shield_is_not_offered_against_a_hit_it_cannot_turn(self):
        fight = {'slots_spent': {}, 'reaction_used': False}
        self.assertEqual(kit_combat.reaction_options(NIK, fight, die=20, total=25, ac=14, dtype='slashing'), [])
        self.assertEqual(kit_combat.reaction_options(NIK, fight, die=18, total=23, ac=14, dtype='slashing'), [])
        self.assertEqual(kit_combat.reaction_options(NIK, fight, die=10, total=15, ac=14, dtype='slashing'), ['shield'])


class FlourishWindow(unittest.TestCase):
    def test_a_kill_of_the_leader_commits_before_the_handoff(self):
        camp = Camp(self)
        result = camp.act(KILL_CAPTAIN)
        self.assertEqual(result.kind, 'combat_interstitial')
        self.assertEqual(camp.state['actors']['harl']['status'], 'dead')
        self.assertTrue(result.public_event.endswith("He's yours. Describe it."), result.public_event)
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['kind'], waiting['awaits']), ('flourish_window', 'player_description'))
        # Stopped there: no enemy turn ran, nobody fled yet.
        self.assertEqual(camp.fight['pc_damage'], 0)
        self.assertEqual(camp.state['actors']['cutthroat_b']['status'], 'alive')

    def test_the_description_cannot_revive_the_target(self):
        camp = Camp(self)
        camp.act(KILL_CAPTAIN)
        result = camp.act('I pull the dagger free. He gasps, alive after all, and staggers back to his feet.')
        self.assertEqual(camp.state['actors']['harl']['status'], 'dead')
        self.assertEqual(camp.fight['hp']['harl'], 0)
        self.assertEqual(result.kind, 'combat_flourish')  # Kit's turn: she yes-ands the description
        self.assertIn('changes no outcome', json.dumps(result.events))

    def test_a_mook_that_is_not_the_last_gets_no_flourish(self):
        camp = Camp(self, roll=lambda: 2)
        camp.act(OPEN)
        self.assertIsNone(camp.fight.get('awaiting'))

    def test_the_last_foe_gets_one(self):
        camp = Camp(self, roll=lambda: 2)
        camp.act(OPEN)  # the wagon-side cutthroat dies; the others miss
        camp.act('I stab the fire-side cutthroat with my dagger, 18 to hit, 20 piercing.')
        self.assertIsNone(camp.fight.get('awaiting'), 'the captain still stands: no flourish for a mook')
        result = camp.act('I stab the bandit captain with my dagger, 18 to hit, 30 piercing.')
        self.assertEqual(result.kind, 'combat_interstitial')
        fight = camp.fight
        self.assertEqual(fight['status'], 'over')
        self.assertEqual(fight['awaiting']['kind'], 'flourish_window')


class OpportunityAttack(unittest.TestCase):
    def leader_down(self, camp):
        camp.act(KILL_CAPTAIN)
        return camp.act('I wipe the blade on his coat and look at the other two.')

    def test_a_foe_leaving_your_reach_offers_your_reaction(self):
        camp = Camp(self)
        result = self.leader_down(camp)
        # The description turn is Kit's (she yes-ands it); the round it releases stops at the window,
        # whose question follows her narration (the accepted event comes after the performance).
        self.assertEqual(result.kind, 'combat_flourish')
        self.assertTrue(result.public_event.endswith('Opportunity attack?'), result.public_event)
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['kind'], waiting['trigger'], waiting['awaits']),
                         ('reaction_window', 'leaves_reach', 'player_answer'))
        self.assertEqual(camp.state['actors']['cutthroat_a']['status'], 'alive', 'not gone yet')

    def test_yes_without_a_roll_asks_for_it(self):
        camp = Camp(self)
        self.leader_down(camp)
        revision, state = camp.runtime.load()
        with self.assertRaisesRegex(PendingRuling, 'Roll the opportunity attack'):
            camp.adjudicator.resolve('Yes!', revision, state)

    def test_the_attack_lands_before_they_leave(self):
        camp = Camp(self)
        self.leader_down(camp)
        camp.act('Yes. Dagger, 17 to hit, 12 piercing.')
        self.assertEqual(camp.state['actors']['cutthroat_a']['status'], 'dead')
        self.assertTrue(camp.fight['reaction_used'])

    def test_declining_lets_them_go(self):
        camp = Camp(self)
        self.leader_down(camp)
        camp.act('No, let him run.')
        self.assertEqual(camp.state['actors']['cutthroat_a']['status'], 'fled')

    def test_no_window_out_of_reach_or_once_spent(self):
        camp = Camp(self)
        self.leader_down(camp)
        camp.act('Yes. Dagger, 17 to hit, 12 piercing.')
        # The fire-side cutthroat was never in reach, and the reaction is spent anyway.
        self.assertEqual(camp.state['actors']['cutthroat_b']['status'], 'fled')
        self.assertIsNone(camp.fight.get('awaiting'))


class EngineInterstitials(unittest.TestCase):
    def bridge(self):
        camp = Camp(self)
        return camp, KitChatBridge(camp.runtime, camp.adjudicator)

    def test_a_reaction_window_is_emitted_without_a_model_packet(self):
        camp, bridge = self.bridge()
        before = copy.deepcopy(camp.state['kit'])
        packet = bridge.prepare(OPEN, 'h1', one_pass=True)
        self.assertEqual(packet['stage'], 'interstitial')
        self.assertTrue(packet['committed'])
        self.assertEqual(packet['turn_role'], 'interstitial')
        self.assertEqual(packet['interstitial']['kind'], 'reaction_window')
        self.assertEqual(packet['interstitial']['awaits'], 'player_answer')
        self.assertTrue(packet['interstitial']['deferred_action_id'])
        self.assertTrue(packet['spoken'].endswith('That hits 15. Shield?'))
        for key in ('instructions', 'schema', 'input'):
            self.assertNotIn(key, packet)
        self.assertLess(len(json.dumps(packet)), 3000)
        # Public history has it; Kit's own appraisal and memory are untouched.
        self.assertEqual(camp.runtime.recent_kit_turns(limit=1)[-1]['spoken'], packet['spoken'])
        after = camp.state['kit']
        self.assertEqual(after['current_appraisal'], before['current_appraisal'])
        self.assertEqual(after['episodes'], before['episodes'])

    def test_the_answer_is_a_full_turn_for_kit(self):
        camp, bridge = self.bridge()
        bridge.prepare(OPEN, 'h1', one_pass=True)
        packet = bridge.prepare('Yes, Shield.', 'h2', one_pass=True)
        self.assertEqual(packet['stage'], 'one_pass')
        self.assertEqual(camp.runtime.pending_kit_turn('h2')['body']['kind'], 'combat_round')

    def test_the_flourish_answer_carries_the_rule_to_kit(self):
        camp, bridge = self.bridge()
        handoff = bridge.prepare(KILL_CAPTAIN, 'f1', one_pass=True)
        self.assertEqual(handoff['interstitial']['kind'], 'flourish_window')
        packet = bridge.prepare('I drive the blade home and he sags against the wagon wheel.', 'f2', one_pass=True)
        self.assertEqual(packet['stage'], 'one_pass')
        flourish = packet['input']['private']['flourish']
        self.assertIn('never for outcomes', flourish['rule'])
        self.assertIn('Bandit captain', flourish['rule'])

    def test_speculative_branches_stay_in_telemetry(self):
        camp, bridge = self.bridge()
        bridge.prepare(OPEN, 'h1', one_pass=True)
        branches = camp.runtime.kit_timing('h1')['speculative']
        self.assertEqual(set(branches), {'shield', 'decline'})
        self.assertLessEqual(branches['shield']['pc_damage'], branches['decline']['pc_damage'])
        self.assertNotIn('speculative', json.dumps(camp.state))
        ledger = [row[0] for row in camp.runtime.db.execute('SELECT body FROM ledger')]
        self.assertFalse(any('speculative' in body for body in ledger))


if __name__ == '__main__':
    unittest.main()


from test_kit_short_beats import PERCEPTION, ShortBeat, kit  # noqa: E402
from runtime import kit_interstitial  # noqa: E402
from runtime.state_context import InvalidChange  # noqa: E402

RISK = {'fact': 'Someone inside is humming; a kicked door will be heard.', 'action': 'kick the iron door open'}
WARNING = 'Whoever is humming in there will hear that door hit the wall. Are you sure?'


class KitRaisedInterstitials(ShortBeat):
    """roll_call, clarify and risk_confirm are typed; structural checks only (watchroom)."""

    def warn(self, turn, segments, risk=RISK):
        packet = self.bridge.prepare('I kick the iron door open.', turn, one_pass=True)
        plan = self.plan_for(packet, move='ask_clarification', table_presence='brief', risk_confirm=dict(risk))
        plan['public_brief'].update(reply_to='kick the iron door', scope='call')
        return self.bridge.complete(turn, {'decision': plan, 'performance': {'segments': segments}})

    def test_a_stall_check_is_a_roll_call_interstitial(self):
        _, result = self.stall(roll_call=PERCEPTION)
        self.assertEqual(result['turn_role'], 'interstitial')
        self.assertEqual((result['interstitial']['kind'], result['interstitial']['awaits']),
                         ('roll_call', 'player_roll'))
        self.assertTrue(result['interstitial']['deferred_action_id'])

    def test_risk_confirm_states_the_fact_and_records_it(self):
        result = self.warn('w1', [kit(WARNING, 'kick the iron door')])
        self.assertEqual((result['interstitial']['kind'], result['interstitial']['awaits']),
                         ('risk_confirm', 'confirmation'))
        self.assertEqual(self.runtime.load()[1]['risks_warned'][0]['fact'], RISK['fact'])

    def test_the_same_warning_is_never_repeated(self):
        self.warn('w1', [kit(WARNING, 'kick the iron door')])
        with self.assertRaisesRegex(InvalidChange, 'already stated'):
            self.warn('w2', [kit('That door will ring like a bell when it hits the wall. Still want to?',
                                 'kick the iron door')])

    def test_a_risk_confirm_must_ask(self):
        with self.assertRaisesRegex(InvalidChange, 'question'):
            self.warn('w3', [kit('Whoever is humming in there will hear that door hit the wall.', 'kick the iron door')])

    def test_a_substantive_turn_says_so(self):
        self.assertEqual(kit_interstitial.describe({'public_brief': {'scope': 'feature'}}, 't'),
                         {'turn_role': 'substantive'})
        self.assertEqual(kit_interstitial.describe({'ask_player': {'question': 'Which door?'},
                                                    'public_brief': {'scope': 'call'}}, 't')['interstitial']['kind'],
                         'clarify')
