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
from runtime import kit_reactions
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, WindowAnswer
from runtime.state_context import InvalidChange, Runtime

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
        self._test = test

    def act(self, action, **choice):
        """``choice``: Kit's structured read of the reply to an open window (react=..., cast_in_avrae=...,
        flourish=...), as her window_answer decision carries it. The engine never reads the words."""
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(action, revision, state, choice=choice or None)
        self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    def held(self, action, **choice):
        revision, state = self.runtime.load()
        with self._test.assertRaises(PendingRuling) as caught:
            self.adjudicator.resolve(action, revision, state, choice=choice or None)
        return caught.exception

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


def shield_only(sheet=NIK):
    """Nik without Chronal Shift, so the windows offer Shield alone."""
    sheet = copy.deepcopy(sheet)
    sheet['features'] = [f for f in sheet['features'] if not f.startswith('Chronal Shift')]
    return sheet


SHIELD = {'react': 'shield', 'cast_in_avrae': True}
CAST = 'Nik casts Shield! (Avrae: !cast shield)'
DECLINE = {'react': 'decline'}


class ReactionWindow(unittest.TestCase):
    def test_shield_is_offered_before_the_first_incoming_hit(self):
        camp = Camp(self)
        result = camp.act(OPEN)
        self.assertEqual(result.kind, 'combat_interstitial')
        self.assertTrue(result.public_event.endswith("The bandit captain's scimitar comes at you: that is a 15, a hit."),
                        result.public_event)
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['kind'], waiting['awaits'], waiting['options']),
                         ('reaction_window', 'player_answer', ['shield', 'chronal_shift']))
        self.assertTrue(waiting['deferred_action_id'])
        self.assertEqual(camp.fight['pc_damage'], 0, 'stopped before damage')
        self.assertEqual(camp.state['actors']['cutthroat_a']['status'], 'dead', 'the PC\'s blow stands')

    def test_shield_cast_in_avrae_turns_the_hits_and_the_slot_is_session_state(self):
        camp = Camp(self)
        camp.act(OPEN)
        result = camp.act(CAST, **SHIELD)
        self.assertEqual(result.kind, 'combat_round')
        fight = camp.fight
        self.assertEqual(fight['pc_damage'], 0)
        self.assertFalse(fight.get('pc_down'))
        self.assertEqual(camp.state['pc_resources']['slots']['1'], {'max': 4, 'used': 1})
        self.assertNotIn('slots_spent', fight)
        self.assertIsNone(fight.get('awaiting'))
        self.assertIn('Your turn.', result.public_event)
        self.assertFalse(fight.get('shield_up'), 'Shield ends at the start of your next turn')
        self.assertFalse(fight.get('reaction_used'), 'your reaction comes back on your turn')

    def test_the_engine_never_reads_the_reply_for_intent(self):
        # Nagatha's probe: the word lists flipped 'No way, I cast Shield!', 'Nah, Shield' and "Don't let it
        # hit me - Shield!" into declines and 'Absolutely not' into a cast. Kit reads the reply now.
        self.assertFalse(hasattr(kit_combat, 'answer_choice'))
        for reply in ('No way, I cast Shield!', 'Nah, Shield', "Don't let it hit me - Shield!", 'Absolutely not'):
            with self.subTest(reply=reply):
                camp = Camp(self)
                camp.act(OPEN)
                revision, state = camp.runtime.load()
                with self.assertRaises(WindowAnswer):
                    camp.adjudicator.resolve(reply, revision, state)
        camp = Camp(self)
        camp.act(OPEN)
        camp.act('No way, I cast Shield! ' + CAST, **SHIELD)
        self.assertEqual(camp.state['pc_resources']['slots']['1']['used'], 1)
        camp = Camp(self)
        camp.act(OPEN)
        camp.act('Absolutely not', **DECLINE)
        self.assertEqual(camp.state['pc_resources']['slots']['1']['used'], 0)

    def test_a_spell_reaction_is_cast_in_avrae_first(self):
        camp = Camp(self)
        camp.act(OPEN)
        held = camp.held('Shield!', react='shield', cast_in_avrae=False)
        self.assertEqual((held.code, held.ask), ('needs_cast', '!cast shield'))
        self.assertEqual(camp.state['pc_resources']['slots']['1']['used'], 0, 'no silent slot spend')

    def test_kit_unclear_or_an_option_not_offered_commits_nothing(self):
        camp = Camp(self)
        camp.act(OPEN)
        self.assertEqual(camp.held('I look at the fire.', react='unclear').code, 'unclear')
        self.assertEqual(camp.held('Absorb Elements!', react='absorb_elements', cast_in_avrae=True).code,
                         'not_offered')

    def test_declining_is_not_re_offered_that_round_unless_the_stakes_rise(self):
        camp = Camp(self, sheet=shield_only())
        camp.act(OPEN)
        camp.act('No, let it hit.', **DECLINE)
        # The captain's other blows and the fire-side cutthroat's mace land without a second offer.
        self.assertIsNone(camp.fight.get('awaiting'))
        self.assertEqual(camp.fight['pc_damage'], 28)
        self.assertEqual(camp.fight['declined']['families'], {'hit': 'normal'})

    def test_a_declined_window_comes_back_when_the_hit_would_drop_him(self):
        sheet = shield_only()
        sheet['hp'] = 20
        camp = Camp(self, sheet=sheet)
        camp.act(OPEN)
        camp.act('No.', **DECLINE)  # 6 from the first scimitar
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['trigger'], waiting['stakes']), ('hit', 'drop'))
        self.assertEqual(waiting['options'], ['shield'])

    def test_no_window_for_a_miss(self):
        camp = Camp(self, roll=lambda: 2)
        result = camp.act(OPEN)
        self.assertEqual(result.kind, 'combat_round')
        self.assertIsNone(camp.fight.get('awaiting'))

    def test_no_window_when_the_sheet_has_no_reaction(self):
        sheet = without_shield(shield_only())
        camp = Camp(self, sheet=sheet)
        result = camp.act(OPEN)
        self.assertEqual(result.kind, 'combat_round')
        self.assertEqual(camp.fight['pc_damage'], 28)

    def test_no_window_with_no_slot_left(self):
        sheet = shield_only()
        sheet['slots'] = {'1': 0, '2': 0, '3': 0}
        camp = Camp(self, sheet=sheet)
        self.assertEqual(camp.act(OPEN).kind, 'combat_round')

    def test_no_second_window_once_the_reaction_is_spent(self):
        # The captain's first blow totals 15 (window); his second rolls 15 + 5 = 20, which beats
        # AC 19 even under Shield, and no window is offered: the reaction is spent.
        camp = Camp(self, roll=rolls(10, 15))
        camp.act(OPEN)
        result = camp.act(CAST, **SHIELD)
        self.assertEqual(result.kind, 'combat_round')
        self.assertEqual(camp.fight['pc_damage'], 6)

    def test_shield_is_never_offered_on_a_natural_20(self):
        camp = Camp(self, roll=lambda: 20)
        camp.act(OPEN)
        self.assertEqual(camp.fight['awaiting']['options'], ['chronal_shift'])

    def test_chronal_shift_forces_a_reroll_and_counts_its_uses(self):
        camp = Camp(self, roll=rolls(10, 2))  # the scimitar's 10 (15, a hit); the reroll 2 (7, a miss)
        camp.act(OPEN)
        result = camp.act('Chronal Shift: reroll that.', react='chronal_shift')
        self.assertEqual(camp.state['pc_resources']['uses']['chronal_shift'], {'max': 2, 'used': 1, 'recharge': 'long'})
        self.assertIn('The scimitar is rerolled: 7, a miss.', result.public_event)
        self.assertEqual(camp.fight['pc_damage'], 6 + 5 + 11, 'the rerolled blow misses; the rest land')

    def test_odd_sheet_formats_do_not_crash(self):
        # Nagatha's probes: spells as a list, slots as {max, used}, no slots at all.
        listed = shield_only()
        listed['spells'] = [{'name': 'Shield', 'level': 1}, 'Magic Missile']
        camp = Camp(self, sheet=listed)
        self.assertEqual(camp.act(OPEN).kind, 'combat_interstitial')
        self.assertEqual(camp.fight['awaiting']['options'], ['shield'])
        used_up = shield_only()
        used_up['slots'] = {'1': {'max': 4, 'used': 4}}
        self.assertEqual(Camp(self, sheet=used_up).act(OPEN).kind, 'combat_round', 'no slot left: no Shield')
        bare = shield_only()
        bare.pop('slots')
        self.assertEqual(Camp(self, sheet=bare).act(OPEN).kind, 'combat_round')

    def test_slots_carry_across_fights_and_own_turn_casts_count(self):
        sheet = shield_only()
        sheet['slots'] = {'1': 1, '3': 1}
        camp = Camp(self, sheet=sheet)
        camp.act(OPEN)
        camp.act(CAST, **SHIELD)
        self.assertEqual(camp.state['pc_resources']['slots']['1'], {'max': 1, 'used': 1})
        camp.act('I cast Fireball at the bandit captain and the cutthroat, 28 fire damage.')
        self.assertEqual(camp.state['pc_resources']['slots']['3'], {'max': 1, 'used': 1}, 'own-turn slot counted')


class AbsorbElements(unittest.TestCase):
    def camp(self):
        sheet = without_shield(shield_only())
        sheet['spells']['1'].append('Absorb Elements')
        source = json.loads(CAMP.read_text())
        source['combat']['actors']['harl']['attacks'][0].update(name='flame blade', type='fire')
        path = Path(tempfile.mkdtemp()) / 'camp.json'
        path.write_text(json.dumps(source))
        with mock.patch(f'{__name__}.CAMP', path):
            return Camp(self, sheet=sheet)

    def test_resistance_to_the_trigger_and_extra_damage_on_the_next_melee_hit(self):
        camp = self.camp()
        camp.act(OPEN)
        self.assertEqual(camp.fight['awaiting']['options'], ['absorb_elements'])
        camp.act('Nik casts Absorb Elements!', react='absorb_elements', cast_in_avrae=True)
        fight = camp.fight
        self.assertEqual(fight['pc_damage'], 3 + 6 + 5 + 11, 'the fire hit is halved (resistance), the rest land')
        self.assertTrue(fight['absorb_bonus']['armed'])
        result = camp.act('I stab the bandit captain with my dagger, 18 to hit, 6 piercing.')
        self.assertIn('Absorb Elements adds 1d6 fire', result.public_event)
        self.assertNotIn('absorb_bonus', camp.fight)
        self.assertEqual(camp.fight['pending']['needs'], 'damage')

    def test_only_elemental_hits_open_it(self):
        sheet = without_shield(shield_only())
        sheet['spells']['1'].append('Absorb Elements')
        camp = Camp(self, sheet=sheet)
        self.assertEqual(camp.act(OPEN).kind, 'combat_round')


class FlourishWindow(unittest.TestCase):
    def test_a_kill_of_the_leader_commits_before_the_handoff(self):
        camp = Camp(self)
        result = camp.act(KILL_CAPTAIN)
        self.assertEqual(result.kind, 'combat_interstitial')
        self.assertEqual(camp.state['actors']['harl']['status'], 'dead')
        self.assertNotIn('Describe it', result.public_event, 'no canned line: Kit voices the window')
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['kind'], waiting['awaits'], waiting['outcome']),
                         ('flourish_window', 'player_description', 'dead'))
        # Stopped there: no enemy turn ran, nobody fled yet.
        self.assertEqual(camp.fight['pc_damage'], 0)
        self.assertEqual(camp.state['actors']['cutthroat_b']['status'], 'alive')

    def test_the_description_cannot_revive_the_target_or_add_damage(self):
        camp = Camp(self)
        camp.act(KILL_CAPTAIN)
        result = camp.act('I stab him but he survives and surrenders, and I deal 40 more damage to the cutthroat',
                          flourish='describe')
        self.assertEqual(camp.state['actors']['harl']['status'], 'dead')
        self.assertEqual(camp.fight['hp']['harl'], 0)
        self.assertEqual(camp.fight['hp']['cutthroat_a'], 11)
        self.assertEqual(result.kind, 'combat_flourish')  # Kit's turn: she yes-ands the description
        self.assertIn('changes no outcome', json.dumps(result.events))

    def test_a_new_action_during_the_flourish_is_kits_read_not_swallowed(self):
        camp = Camp(self)
        camp.act(KILL_CAPTAIN)
        revision, state = camp.runtime.load()
        with self.assertRaises(WindowAnswer):
            camp.adjudicator.resolve("I grab the captain's purse and run for the road.", revision, state)
        result = camp.act("I grab the captain's purse and run for the road.", flourish='new_action')
        self.assertNotEqual(result.kind, 'combat_flourish')
        self.assertNotEqual((camp.fight.get('awaiting') or {}).get('kind'), 'flourish_window')

    def test_a_knockout_the_player_chose_is_down_not_dead(self):
        camp = Camp(self)
        camp.act('Initiative 25. I knock the bandit captain out with the pommel of my dagger, 18 to hit, '
                 '30 bludgeoning, nonlethal.')
        self.assertEqual(camp.state['actors']['harl']['status'], 'unconscious')
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['kind'], waiting['outcome']), ('flourish_window', 'unconscious'))
        bridge = KitChatBridge(camp.runtime, camp.adjudicator)
        packet = bridge.prepare('I lower him to the ground.', 'k1', one_pass=True)
        self.assertEqual(packet['stage'], 'window_answer')
        packet = bridge.complete('k1', {'decision': {'flourish': 'describe'}, 'performance': {'segments': []}})
        rule = packet['input']['private']['flourish']['rule']
        self.assertIn('out cold', rule)
        self.assertNotIn('is dead', rule)

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
        return camp.act('I wipe the blade on his coat and look at the other two.', flourish='describe')

    def test_a_foe_leaving_your_reach_offers_your_reaction(self):
        camp = Camp(self)
        result = self.leader_down(camp)
        self.assertEqual(result.kind, 'combat_flourish')
        self.assertTrue(result.public_event.endswith('The wagon-side cutthroat breaks away, leaving your reach.'),
                        result.public_event)
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['kind'], waiting['trigger'], waiting['awaits'], waiting['options']),
                         ('reaction_window', 'leaves_reach', 'player_answer', ['opportunity_attack']))
        self.assertEqual(camp.state['actors']['cutthroat_a']['status'], 'alive', 'not gone yet')

    def test_yes_without_a_roll_asks_for_it(self):
        camp = Camp(self)
        self.leader_down(camp)
        self.assertEqual(camp.held('Yes!', react='opportunity_attack').code, 'needs_roll')

    def test_a_ranged_weapon_cannot_make_one(self):
        camp = Camp(self)
        self.leader_down(camp)
        held = camp.held('Yes, I shoot him with my longbow, 17 to hit, 8 piercing.', react='opportunity_attack')
        self.assertEqual(held.code, 'ranged_weapon')

    def test_the_attack_lands_before_they_leave(self):
        camp = Camp(self)
        self.leader_down(camp)
        camp.act('Yes. Dagger, 17 to hit, 12 piercing.', react='opportunity_attack')
        self.assertEqual(camp.state['actors']['cutthroat_a']['status'], 'dead')
        self.assertTrue(camp.fight['reaction_used'])

    def test_declining_lets_them_go(self):
        camp = Camp(self)
        self.leader_down(camp)
        camp.act('No, let him run.', **DECLINE)
        self.assertEqual(camp.state['actors']['cutthroat_a']['status'], 'fled')

    def test_no_window_out_of_reach_or_once_spent(self):
        camp = Camp(self)
        self.leader_down(camp)
        camp.act('Yes. Dagger, 17 to hit, 12 piercing.', react='opportunity_attack')
        # The fire-side cutthroat was never in reach, and the reaction is spent anyway.
        self.assertEqual(camp.state['actors']['cutthroat_b']['status'], 'fled')
        self.assertIsNone(camp.fight.get('awaiting'))

    def test_engagement_is_tracked_without_room_data(self):
        # Nagatha's probe: only roadcamp set combat.in_reach. Melee blows engage by default.
        source = json.loads(CAMP.read_text())
        source['combat'].pop('in_reach')
        path = Path(tempfile.mkdtemp()) / 'camp.json'
        path.write_text(json.dumps(source))
        sheet = without_shield(shield_only())
        sheet['hp'] = 80
        with mock.patch(f'{__name__}.CAMP', path):
            camp = Camp(self, sheet=sheet)
        camp.act('Initiative 25. I stab the wagon-side cutthroat with my dagger, 8 to hit, 4 piercing.')
        self.assertIn('cutthroat_a', camp.fight['engaged'], 'the PC swung at him in melee')
        self.assertIn('harl', camp.fight['engaged'], 'the captain cut at the PC in melee')
        camp.act(KILL_CAPTAIN.replace('Initiative 25. ', ''))
        camp.act('He crumples.', flourish='describe')
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['trigger'], waiting['actor']), ('leaves_reach', 'cutthroat_a'))


class EngineInterstitials(unittest.TestCase):
    """The engine holds the window; Kit voices it (window_voice) and reads the reply (window_answer)."""

    def bridge(self, sheet=NIK):
        camp = Camp(self, sheet=sheet)
        return camp, KitChatBridge(camp.runtime, camp.adjudicator)

    def voice(self, bridge, turn, text='Kit: The scimitar flashes in at your ribs and catches you. Shield?'):
        segments = [{'speaker': 'Narrator', 'text': 'Your dagger finds the cutthroat and he drops by the wagon.'},
                    {'speaker': 'Kit', 'text': text.split(': ', 1)[1]}]
        return bridge.complete(turn, {'decision': {'window': 'voiced'}, 'performance': {'segments': segments}})

    def test_the_window_is_a_tiny_packet_kit_voices(self):
        camp, bridge = self.bridge()
        before = copy.deepcopy(camp.state['kit'])
        packet = bridge.prepare(OPEN, 'h1', one_pass=True)
        self.assertEqual(packet['stage'], 'window_voice')
        window = packet['input']['window']
        self.assertEqual([o['id'] for o in window['options']], ['shield', 'chronal_shift'])
        self.assertEqual(window['options'][0]['avrae'], '!cast shield')
        self.assertIn('scimitar comes at you', packet['input']['narrate_first'])
        self.assertLess(len(json.dumps(packet)), 4000)
        self.assertIsNone(camp.state.get('combat'), 'nothing is committed before Kit voices it')
        result = self.voice(bridge, 'h1')
        self.assertTrue(result['committed'])
        self.assertEqual(result['turn_role'], 'interstitial')
        self.assertEqual(result['interstitial']['kind'], 'reaction_window')
        self.assertTrue(result['interstitial']['deferred_action_id'])
        self.assertEqual(camp.runtime.recent_kit_turns(limit=1)[-1]['spoken'], result['spoken'])
        self.assertNotIn('Kit: Turn order', result['spoken'], 'the engine never speaks as Kit')
        after = camp.state['kit']
        self.assertEqual(after['current_appraisal'], before['current_appraisal'])
        self.assertEqual(after['episodes'], before['episodes'])

    def test_kit_must_name_the_reaction_and_ask(self):
        _, bridge = self.bridge()
        bridge.prepare(OPEN, 'h1', one_pass=True)
        with self.assertRaisesRegex(InvalidChange, 'Name the reaction'):
            self.voice(bridge, 'h1', 'Kit: The scimitar flashes in at your ribs. What now?')
        with self.assertRaisesRegex(InvalidChange, 'question'):
            self.voice(bridge, 'h1', 'Kit: The scimitar flashes in at your ribs. Shield, if you want it.')

    def test_the_answer_is_read_by_kit_then_a_full_turn(self):
        camp, bridge = self.bridge()
        bridge.prepare(OPEN, 'h1', one_pass=True)
        self.voice(bridge, 'h1')
        packet = bridge.prepare('Nah, Shield', 'h2', one_pass=True)
        self.assertEqual(packet['stage'], 'window_answer')
        self.assertEqual(packet['input']['player_reply'], 'Nah, Shield')
        asked = bridge.complete('h2', {'decision': {'react': {'choice': 'shield', 'cast_in_avrae': False}},
                                       'performance': {'segments': [{'speaker': 'Kit',
                                                                     'text': 'Cast it in Avrae: !cast shield?'}]}})
        self.assertTrue(asked['asked'])
        self.assertEqual(camp.fight['awaiting']['kind'], 'reaction_window', 'the window stays open')
        packet = bridge.prepare(CAST, 'h3', one_pass=True)
        packet = bridge.complete('h3', {'decision': {'react': {'choice': 'shield', 'cast_in_avrae': True}}, 'performance': {'segments': []}})
        self.assertEqual(packet['stage'], 'one_pass')
        self.assertEqual(packet['window_answered']['react'], 'shield')
        self.assertEqual(camp.runtime.pending_kit_turn('h3')['body']['kind'], 'combat_round')
        self.assertEqual(camp.runtime.kit_timing('h3')['window_round_trips'], 1, 'one tiny read; the full turn is the normal trip')
        self.assertEqual(camp.runtime.kit_timing('h1')['window_round_trips'], 1)

    def test_an_answer_needing_an_ask_without_one_is_rejected(self):
        _, bridge = self.bridge()
        bridge.prepare(OPEN, 'h1', one_pass=True)
        self.voice(bridge, 'h1')
        bridge.prepare('Shield!', 'h2', one_pass=True)
        with self.assertRaisesRegex(InvalidChange, r'!cast shield'):
            bridge.complete('h2', {'decision': {'react': {'choice': 'shield', 'cast_in_avrae': False}},
                                   'performance': {'segments': []}})
        with self.assertRaisesRegex(InvalidChange, 'react.choice must be one of'):
            bridge.complete('h2', {'decision': {'react': {'choice': 'yes'}}, 'performance': {'segments': []}})

    def test_the_flourish_answer_carries_the_rule_to_kit(self):
        _, bridge = self.bridge()
        handoff = bridge.prepare(KILL_CAPTAIN, 'f1', one_pass=True)
        self.assertEqual(handoff['input']['window']['kind'], 'flourish_window')
        self.voice(bridge, 'f1', 'Kit: The captain folds over your blade. How does it look?')
        bridge.prepare('I drive the blade home and he sags against the wagon wheel.', 'f2', one_pass=True)
        packet = bridge.complete('f2', {'decision': {'flourish': 'describe'}, 'performance': {'segments': []}})
        self.assertEqual(packet['stage'], 'one_pass')
        flourish = packet['input']['private']['flourish']
        self.assertIn('never for outcomes', flourish['rule'])
        self.assertIn('Bandit captain', flourish['rule'])

    def test_speculative_branches_stay_in_telemetry(self):
        camp, bridge = self.bridge()
        bridge.prepare(OPEN, 'h1', one_pass=True)
        branches = camp.runtime.kit_timing('h1')['speculative']
        self.assertEqual(set(branches), {'shield', 'chronal_shift', 'decline'})
        self.assertEqual(set(branches['shield']), {'pc_damage', 'pc_down', 'next_checkpoint'})
        self.voice(bridge, 'h1')
        self.assertNotIn('speculative', json.dumps(camp.state))
        ledger = [row[0] for row in camp.runtime.db.execute('SELECT body FROM ledger')]
        self.assertFalse(any('speculative' in body for body in ledger))


if __name__ == '__main__':
    unittest.main()


from test_kit_short_beats import PERCEPTION, ShortBeat, kit  # noqa: E402
from runtime import kit_interstitial  # noqa: E402

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
