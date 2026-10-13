"""Kit-declared combat acts (#122): the scenarios the word-matching clause splitter was tested on
(test_kit_review101c flag-on classes, test_kit_grapple5e) retargeted as declared-entry
validation. Kit's entries are hand-written as she would emit them; the engine validates each,
commits the legal ones and voices why the rest did not happen. Plus the wiring: the prepare
offer and the decision schema, the way #97's handles are. Rooms: kiln, rope bridge, shrine
(never 6c). Every die is pinned; the engine never rolls for the PC; the actor wins ties."""
import copy
import itertools
import unittest

from runtime import kit_acts, kit_combat_acts
from runtime.kit_agent import API_PLAN_SCHEMA, ONE_PASS_SCHEMA, KitChatBridge
from runtime.state_context import InvalidChange
from test_kit_agent import RecordingModel
from test_kit_review101c import (Arena, KILN_OPEN, clause_log, rogue, warlock, without_shield, wizard)

BRIDGE_OPEN = 'Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.'  # a miss; he hits for 13


def A(kind, order, **kw):
    return {'kind': kind, 'order': order, **kw}


def ud_bridge(test, sheet=None, die=10):
    arena = Arena(test, 'rope_bridge', sheet=sheet or rogue(), roll=lambda: die)
    arena.act(BRIDGE_OPEN)
    return arena


def kiln(test, sheet, die=10):
    arena = Arena(test, 'kiln', sheet=sheet, roll=lambda: die)
    arena.act(KILN_OPEN)
    return arena


def shrine(test, sheet, die):
    arena = Arena(test, 'shrine', sheet=sheet, roll=lambda: die)
    arena.act('Initiative 25. I stab the adept with my dagger, 3 to hit, 3 piercing.')
    return arena


def absorber():
    sheet = without_shield(wizard(hp=60))
    sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
    return sheet


UD = A('reaction', 1, reaction='uncanny_dodge', says='I Uncanny Dodge that hit')
STAB = A('attack', 2, target='ogre', weapon='rapier', roll='18 to hit, 7 piercing', says='stab the bridge ogre')


class LateReactionWithTheAct(unittest.TestCase):
    """Was LateReactionKeepsTheAct (flag-on): the reaction and the act both resolve, either order."""

    def check(self, entries):
        arena = ud_bridge(self)
        result = arena.act('(declared)', combat_acts=entries)
        self.assertIn('Uncanny Dodge: you take half', result.public_event)
        self.assertIn('hits the bridge ogre', result.public_event)
        self.assertEqual(arena.fight['hp']['ogre'], 59 - 7)
        return result

    def test_dodge_then_attack(self):
        self.check([UD, STAB])

    def test_attack_then_dodge(self):
        self.check([{**STAB, 'order': 1}, {**UD, 'order': 2}])

    def test_the_late_dodge_says_the_new_damage(self):
        result = ud_bridge(self).act('I Uncanny Dodge that greatclub hit.', combat_acts=[{**UD, 'order': 1}])
        self.assertIn('Uncanny Dodge: you take half, 6 instead of 13.', result.public_event)

    def test_absorb_elements_then_fire_bolt_carries_both_and_uses_avraes_level(self):
        arena = kiln(self, absorber())
        result = arena.act('Absorb Elements at 2nd, then Fire Bolt the slinger.', combat_acts=[
            A('reaction', 1, reaction='absorb_elements', roll='!cast absorb elements -l 2'),
            A('spell', 2, target='archer', spell='fire bolt', roll='19 to hit, 8 fire')])
        self.assertIn('Absorb Elements: resistance to the fire', result.public_event)
        self.assertIn('Your Fire Bolt hits', result.public_event)
        slots = arena.state['pc_resources']['slots']
        self.assertEqual((slots['1']['used'], slots['2']['used']), (0, 1))
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'resolved'])


class EveryEntryResolves(unittest.TestCase):
    """Was EveryClauseResolves / Review92 / Review5d (flag-on): no entry is silently dropped."""

    def test_stab_dodge_and_back_off(self):
        arena = ud_bridge(self)
        result = arena.act('(declared)', combat_acts=[{**STAB, 'order': 1}, {**UD, 'order': 2},
                                                      A('move', 3, way='away', distance_ft=10, says='back off 10 feet')])
        self.assertEqual(arena.fight['hp']['ogre'], 52)
        self.assertIn('Uncanny Dodge: you take half', result.public_event)
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved'] * 3)

    def test_dodge_twice_then_stab(self):
        arena = ud_bridge(self)
        result = arena.act('(declared)', combat_acts=[
            UD, A('reaction', 2, reaction='uncanny_dodge', says='Uncanny Dodge it again'), {**STAB, 'order': 3}])
        self.assertEqual(arena.fight['hp']['ogre'], 52)
        self.assertIn('"Uncanny Dodge it again" didn\'t happen because you have already used your reaction',
                      result.public_event)
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'refused', 'resolved'])

    def test_warlock_dodge_rebuke_stab(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger', 'rapier']))
        result = arena.act('(declared)', combat_acts=[
            A('reaction', 1, reaction='uncanny_dodge', says='Uncanny Dodge that hit'),
            A('reaction', 2, target='imp', reaction='hellish_rebuke',
              roll='(Avrae: !cast hellish rebuke) 2d10 = 12 fire'),
            A('attack', 3, target='archer', weapon='dagger', roll='18 to hit, 4 piercing')])
        text = result.public_event
        self.assertIn('"Uncanny Dodge that hit" didn\'t happen because it is not on your sheet', text)
        self.assertIn('Hellish Rebuke: 12 fire damage to the ember imp.', text)
        self.assertEqual(arena.fight['hp']['archer'], 3)
        self.assertEqual(arena.slot1(), 1)

    def test_a_melee_stab_after_stepping_back_is_out_of_reach_and_said_after_the_move(self):
        arena = ud_bridge(self)
        result = arena.act('(declared)', combat_acts=[
            UD, A('move', 2, way='away', distance_ft=5), {**STAB, 'order': 3}])
        self.assertEqual(arena.fight['hp']['ogre'], 59)
        self.assertIn("didn't happen because the bridge ogre is out of your reach now", result.public_event)
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'resolved', 'refused'])

    def test_a_ranged_bolt_after_backing_off_still_flies_and_closing_in_restores_reach(self):
        arena = kiln(self, without_shield(wizard(hp=60)))
        arena.act('(declared)', combat_acts=[A('move', 1, way='away', distance_ft=10),
                                             A('spell', 2, target='archer', spell='fire bolt', roll='19 to hit, 6 fire')])
        self.assertEqual(arena.fight['hp']['archer'], 1)
        arena = ud_bridge(self)
        arena.act('(declared)', combat_acts=[A('move', 1, target='ogre', way='toward'), STAB])
        self.assertEqual(arena.fight['hp']['ogre'], 52)

    def test_a_thrown_dagger_after_backing_off_flies(self):
        arena = ud_bridge(self, rogue(gear=['rapier', 'dagger (thrown)', 'shortbow']))
        arena.act('(declared)', combat_acts=[A('move', 1, way='away', distance_ft=5),
                                             A('attack', 2, target='ogre', weapon='dagger', thrown=True,
                                               roll='15 to hit, 4 piercing')])
        self.assertEqual(arena.fight['hp']['ogre'], 55)

    def test_kit_says_whether_a_dagger_is_thrown_and_a_stab_stays_melee(self):
        # SRD: a dagger has the thrown property whether or not the sheet spells it out.
        arena = kiln(self, warlock(hp=60, gear=['dagger', 'rapier']))
        arena.act('(declared)', combat_acts=[A('move', 1, way='away', distance_ft=10),
                                             A('attack', 2, target='imp', weapon='dagger', thrown=True,
                                               roll='15 to hit, 3 piercing')])
        self.assertEqual(arena.fight['hp']['imp'], 15)
        arena = ud_bridge(self, rogue(gear=['rapier', 'dagger (thrown)', 'shortbow']))
        result = arena.act('(declared)', combat_acts=[A('move', 1, way='away', distance_ft=5),
                                                      A('attack', 2, target='ogre', weapon='dagger',
                                                        roll='15 to hit, 4 piercing', says='stab him with my dagger')])
        self.assertIn('out of your reach now', result.public_event)
        self.assertEqual(arena.fight['hp']['ogre'], 59)

    def test_a_rapier_declared_thrown_is_refused(self):
        arena = ud_bridge(self)
        result = arena.act('(declared)', combat_acts=[{**STAB, 'order': 1, 'thrown': True, 'says': 'I throw my rapier'}])
        self.assertIn('"I throw my rapier" didn\'t happen because a rapier is not a thrown weapon', result.public_event)

    def test_refusals_name_things_as_said_not_by_id(self):
        arena = ud_bridge(self)
        result = arena.act('(declared)', combat_acts=[A('reaction', 1, reaction='uncanny_dodge'),
                                                      A('reaction', 2, reaction='uncanny_dodge')])
        self.assertNotIn('uncanny_dodge', result.public_event)
        self.assertIn('The Uncanny Dodge didn\'t happen because', result.public_event)

    def test_the_target_is_the_one_kit_names_not_a_guess(self):
        arena = kiln(self, without_shield(wizard(hp=60)))
        arena.act('I step up to the imp and stab it.', combat_acts=[
            A('move', 1, target='imp', way='toward'),
            A('attack', 2, target='imp', weapon='dagger', roll='15 to hit, 3 piercing')])
        self.assertEqual(arena.fight['hp']['imp'], 15)
        self.assertEqual(arena.fight['hp']['archer'], 7)

    def test_a_pasted_rebuke_uses_its_target_and_damage(self):
        arena = kiln(self, warlock(hp=60, gear=['dagger', 'rapier']))
        arena.act('(declared)', combat_acts=[
            A('attack', 1, target='archer', weapon='dagger', roll='18 to hit, 3 piercing'),
            A('reaction', 2, target='imp', reaction='hellish_rebuke',
              roll='!cast hellish rebuke -t imp -l 1\nHellish Rebuke: 12 fire'),
            A('move', 3, way='away', distance_ft=10, says='then I back away 10 feet')])
        self.assertEqual(arena.fight['hp']['imp'], 6)
        self.assertEqual(arena.fight['hp']['archer'], 4)

    def test_a_late_absorb_cast_after_his_act_fizzles_and_counts(self):
        arena = kiln(self, absorber())
        result = arena.act('(declared)', combat_acts=[
            A('spell', 1, target='imp', spell='fire bolt', roll='17 to hit, 7 fire'),
            A('reaction', 2, reaction='absorb_elements', roll='(Avrae: !cast absorb elements -l 1)')])
        self.assertIn('fizzles', result.public_event)
        self.assertNotIn('resistance to the fire', result.public_event)
        self.assertEqual(arena.slot1(), 1)

    def test_a_reaction_not_on_the_sheet_is_refused_not_a_bash(self):
        arena = ud_bridge(self)
        result = arena.act('I Shield myself and stab.', combat_acts=[
            A('reaction', 1, reaction='shield', says='I Shield myself'), STAB])
        self.assertNotIn('Your shield hits', result.public_event)
        self.assertIn('"I Shield myself" didn\'t happen because it is not on your sheet', result.public_event)
        self.assertEqual(arena.fight['hp']['ogre'], 52)

    def test_object_and_environment_deeds_are_rulings_with_a_record_and_nothing_commits(self):
        for says in ('push the kiln door shut', 'push the shelf over onto the slinger', 'cut the bellows strap'):
            arena = kiln(self, warlock(hp=60, gear=['dagger', 'rapier']))
            before = copy.deepcopy(arena.fight)
            exc = arena.held('(declared)', combat_acts=[
                A('object', 1, says=says),
                A('attack', 2, target='archer', weapon='dagger', roll='16 to hit, 3 piercing')])
            self.assertIn(f'"{says}" needs the DM\'s call', str(exc))
            self.assertEqual([c['outcome'] for c in exc.clauses], ['ruling', 'waits'])
            self.assertEqual(arena.fight, before)

    def test_an_off_hand_stab_is_his_bonus_action(self):
        arena = kiln(self, without_shield(wizard(hp=60)))
        arena.act('(declared)', combat_acts=[
            A('attack', 1, target='archer', weapon='dagger', roll='18 to hit, 3 piercing'),
            A('bonus_attack', 2, target='imp', weapon='dagger', roll='15 to hit, 2 piercing')])
        self.assertEqual((arena.fight['hp']['archer'], arena.fight['hp']['imp']), (4, 16))

    def test_a_single_entry_gets_a_clause_record(self):
        result = ud_bridge(self).act('I stab.', combat_acts=[{**STAB, 'order': 1}])
        self.assertEqual(clause_log(result), [(1, 1, 'resolved')])


class DeclaredGrapple(unittest.TestCase):
    """Was test_kit_grapple5e (flag-on): an SRD contested grapple. The PC's Athletics comes from
    Avrae (asked for when missing); the creature rolls its better of Athletics and Acrobatics in
    the engine; the actor wins ties."""

    def test_no_roll_asks_for_athletics_and_holds_nobody(self):
        for arena, target in ((kiln(self, without_shield(wizard(hp=60))), 'archer'), (ud_bridge(self), 'ogre')):
            before = copy.deepcopy(arena.fight)
            exc = arena.held('I grab him.', combat_acts=[A('grapple', 1, target=target)])
            self.assertIn('Athletics', str(exc))
            self.assertEqual(arena.fight, before)
            self.assertFalse((arena.state.get('scene') or {}).get('grappled'))

    def test_the_actor_wins_ties(self):
        arena = kiln(self, without_shield(wizard(hp=60)))  # slinger: 10 + Dex 2 = 12
        arena.act('I grab the slinger.', combat_acts=[A('grapple', 1, target='archer', roll='Athletics 12')])
        self.assertEqual(arena.state['scene']['grappled'], 'archer')
        arena = ud_bridge(self)  # ogre: 10 + 6 = 16
        arena.act('I grab the ogre.', combat_acts=[A('grapple', 1, target='ogre', roll='Athletics 16')])
        self.assertEqual(arena.state['scene']['grappled'], 'ogre')

    def test_one_short_and_he_twists_free(self):
        arena = ud_bridge(self)
        result = arena.act('I grab the ogre.', combat_acts=[A('grapple', 1, target='ogre', roll='Athletics 15')])
        self.assertFalse(arena.state['scene'].get('grappled'))
        self.assertIn('twists out of your grip', result.public_event)
        arena = shrine(self, without_shield(wizard(hp=60)), 4)  # adept: 4 + Dex 5 = 9
        arena.act('I grab the adept.', combat_acts=[A('grapple', 1, target='adept', roll='Athletics 9')])
        self.assertEqual(arena.state['scene']['grappled'], 'adept')

    def test_an_avrae_check_paste_is_the_roll(self):
        arena = ud_bridge(self, die=3)  # ogre 3 + 6 = 9
        arena.act('I grab the ogre.', combat_acts=[A('grapple', 1, target='ogre', roll=(
            '!check athletics\nWren makes an Athletics check!\n1d20 (7) + 3 = `10`'))])
        self.assertEqual(arena.state['scene']['grappled'], 'ogre')


class DeclaredFuzz(unittest.TestCase):
    """Property: every declared entry, in every order, gets a clause record; every refusal is said."""

    POOLS = [
        ('bridge', rogue, [A('reaction', 0, reaction='uncanny_dodge'), A('move', 0, way='away', distance_ft=5),
                           A('attack', 0, target='ogre', weapon='rapier', roll='18 to hit, 7 piercing'),
                           A('move', 0, target='ogre', way='toward'), A('grapple', 0, target='ogre', roll='Athletics 20'),
                           A('object', 0, says='grip the rope'), A('dodge', 0), A('shove', 0, target='ogre')]),
        ('kiln', lambda: warlock(hp=60, gear=['dagger', 'rapier']), [
            A('reaction', 0, target='imp', reaction='hellish_rebuke', roll='!cast hellish rebuke -t imp -l 1\nHellish Rebuke: 12 fire'),
            A('attack', 0, target='archer', weapon='dagger', roll='18 to hit, 3 piercing'),
            A('move', 0, way='away', distance_ft=10), A('spell', 0, target='imp', spell='eldritch blast', roll='17 to hit, 6 force'),
            A('object', 0, says='push the kiln door shut'), A('help', 0)]),
    ]

    def test_every_entry_is_recorded_and_refusals_are_voiced(self):
        checked = 0
        for room, sheet, pool in self.POOLS:
            for combo in itertools.permutations(pool, 3):
                entries = [{**e, 'order': i} for i, e in enumerate(combo, 1)]
                arena = ud_bridge(self, sheet()) if room == 'bridge' else kiln(self, sheet())
                try:
                    result = arena.act('(declared)', combat_acts=entries)
                except Exception as caught:  # an Avrae ask or a ruling commits nothing and says so
                    if getattr(caught, 'clauses', None):
                        self.assertEqual(len(caught.clauses), 3, entries)
                    else:
                        self.assertIn('No turn was committed', str(caught), entries)
                    checked += 1
                    continue
                log = clause_log(result)
                self.assertEqual(len(log), 3, (entries, result.public_event))
                if any(c[2] == 'refused' for c in log):
                    self.assertIn("didn't happen because", result.public_event, entries)
                checked += 1
        self.assertGreater(checked, 400)


class OfferAndSchema(unittest.TestCase):
    """Wired like #97's handles: the prepare offer, the packet view and rule line, the schema."""

    def test_the_decision_schemas_carry_combat_acts(self):
        decision = ONE_PASS_SCHEMA['properties']['decision']['properties']
        self.assertIs(decision['combat_acts'], kit_acts.SCHEMAS['combat_acts'])
        self.assertIn('combat_acts', kit_acts.FIELDS)
        strict = API_PLAN_SCHEMA['properties']['combat_acts']
        self.assertIn('null', strict['type'])
        self.assertEqual(sorted(strict['items']['required']), sorted(strict['items']['properties']))

    def turn(self, arena, action, combat_acts=None, turn_id='c1'):
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        packet = bridge.prepare(action, turn_id, one_pass=True)
        plan = RecordingModel().plan(packet['input']['private'])
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan.update(move='world_description', focus_actor='none')
        for key in ('objective', 'visible_cue', 'player_opening'):
            plan['public_brief'].pop(key, None)
        plan['public_brief']['scope'] = 'call'
        if combat_acts is not None:
            plan['combat_acts'] = combat_acts
        speech = {'segments': [{'speaker': 'Narrator', 'text': 'You move.'}]}
        return packet, bridge.complete(turn_id, {'decision': plan, 'performance': speech})

    def test_a_running_fight_offers_combat_acts_at_prepare(self):
        arena = kiln(self, absorber())
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        packet = bridge.prepare('I Fire Bolt the slinger, 19 to hit, 8 fire.', 'c0', one_pass=True)
        view = packet['input']['private']['acts']['combat_acts']
        self.assertEqual(view['targets'], ['archer', 'imp'])
        self.assertIn('fire bolt', view['spells'])
        self.assertIn('absorb_elements', view['reactions'])
        self.assertTrue(any(line.startswith('acts.combat_acts:') for line in packet['first_try']))

    def test_absorb_elements_then_fire_bolt_through_prepare_and_complete(self):
        arena = kiln(self, absorber())
        before = arena.fight['hp']['archer']
        _, result = self.turn(arena, 'Absorb Elements (!cast absorb elements -l 2), then Fire Bolt the slinger, '
                                     '19 to hit, 8 fire.', [
            A('reaction', 1, reaction='absorb_elements', roll='!cast absorb elements -l 2', says='Absorb Elements'),
            A('spell', 2, target='archer', spell='fire bolt', roll='19 to hit, 8 fire', says='Fire Bolt the slinger')])
        self.assertIn('Absorb Elements: resistance to the fire', result['spoken'])
        self.assertIn('Your Fire Bolt hits', result['spoken'])
        self.assertLess(arena.fight['hp']['archer'], before)
        self.assertEqual(arena.state['pc_resources']['slots']['2']['used'], 1)

    def test_kits_entries_replace_the_word_read_not_add_to_it(self):
        arena = kiln(self, without_shield(wizard(hp=60)))
        # The words say the slinger; Kit declares the imp. Only her entry commits, once.
        _, result = self.turn(arena, 'I stab the slinger, 16 to hit, 3 piercing.', [
            A('attack', 1, target='imp', weapon='dagger', roll='16 to hit, 3 piercing')])
        self.assertEqual(arena.fight['hp']['archer'], 7)
        self.assertEqual(arena.fight['hp']['imp'], 15)

    def test_left_out_the_engines_own_read_stands(self):
        arena = kiln(self, without_shield(wizard(hp=60)))
        self.turn(arena, 'I stab the kobold slinger with my dagger, 16 to hit, 3 piercing.')
        self.assertEqual(arena.fight['hp']['archer'], 4)

    def test_no_fight_no_offer_and_a_declaration_is_rejected(self):
        arena = Arena(self, 'kiln', sheet=without_shield(wizard(hp=60)))
        with self.assertRaises(InvalidChange):
            self.turn(arena, 'I look around the kiln.', [A('dodge', 1)])

    def test_an_empty_list_is_none(self):
        self.assertIsNone(kit_acts.declared({'combat_acts': []}, 'combat_acts'))


if __name__ == '__main__':
    unittest.main()
