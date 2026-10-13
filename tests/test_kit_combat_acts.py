"""Kit-declared combat acts (Brendon's decision, 2026-10-13): Kit's structured list, one entry
per clause; the engine validates each against the rules and the fight, commits the legal ones
and voices why the rest did not happen. Kit is a model, so these tests hand-write her entries
for messages from Nagatha's acceptance sets (/tmp/rvdf, /tmp/rv5d, /tmp/rv92). Dice pinned."""
import copy
import unittest

from runtime import kit_combat_acts
from runtime.state_context import InvalidChange
from test_kit_review101c import (Arena, KILN_OPEN, clause_log, rogue, ruling_of, warlock, without_shield,
                                 wizard)


def A(kind, order, **kw):
    return {'kind': kind, 'order': order, **kw}


def bridge(test, sheet=None):
    arena = Arena(test, 'rope_bridge', sheet=sheet or rogue(), roll=lambda: 10)
    arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')  # a miss; he hits for 13
    return arena


def kiln(test, sheet):
    arena = Arena(test, 'kiln', sheet=sheet, roll=lambda: 10)
    arena.act(KILN_OPEN)
    return arena


STAB = A('attack', 1, target='ogre', weapon='rapier', roll='16 to hit, 5 piercing', says='I stab the ogre')


class DeclaredAttacks(unittest.TestCase):
    def test_a_declared_attack_resolves_from_its_entry_not_the_words(self):
        arena = bridge(self)
        arena.act('Rapier at the big lump, the usual.', combat_acts=[STAB])
        self.assertEqual(arena.fight['hp']['ogre'], 54)

    def test_a_missing_roll_is_an_avrae_ask_and_nothing_commits(self):
        arena = bridge(self)
        before = copy.deepcopy(arena.fight)
        exc = arena.held('I stab the ogre.', combat_acts=[A('attack', 1, target='ogre', weapon='rapier')])
        self.assertIn('Avrae', str(exc))
        self.assertEqual(arena.fight, before)

    def test_a_weapon_not_on_the_sheet_is_refused_and_said(self):
        arena = bridge(self)
        result = arena.act('I swing my greataxe.', combat_acts=[A('attack', 1, target='ogre', weapon='greataxe',
                                                                  roll='16 to hit, 9 slashing', says='I swing my greataxe')])
        self.assertIn("didn't happen because there is no greataxe on your sheet", result.public_event)
        self.assertEqual(arena.fight['hp']['ogre'], 59)

    def test_a_second_action_attack_is_refused_with_its_reason(self):
        arena = bridge(self)
        result = arena.act('I stab twice.', combat_acts=[STAB, {**STAB, 'order': 2, 'says': 'and again'}])
        self.assertEqual(arena.fight['hp']['ogre'], 54)
        self.assertIn('"Again" didn\'t happen because you have already used your action this turn',
                      result.public_event)

    def test_moving_away_then_a_melee_blow_is_out_of_reach_but_a_thrown_dagger_flies(self):
        arena = bridge(self)
        result = arena.act('I back off and stab.', combat_acts=[A('move', 1, way='away', distance_ft=10),
                                                                {**STAB, 'order': 2}])
        self.assertIn('out of your reach now', result.public_event)
        self.assertEqual(arena.fight['hp']['ogre'], 59)
        arena = bridge(self, rogue(gear=['rapier', 'dagger (thrown)', 'shortbow']))
        arena.act('I step back and throw a dagger.', combat_acts=[
            A('move', 1, way='away', distance_ft=5),
            A('attack', 2, target='ogre', weapon='dagger', thrown=True, roll='15 to hit, 4 piercing')])
        self.assertEqual(arena.fight['hp']['ogre'], 55)

    def test_every_entry_gets_a_clause_record(self):
        arena = bridge(self)
        result = arena.act('Uncanny Dodge, then stab, then shove him.', combat_acts=[
            A('reaction', 1, reaction='uncanny_dodge'), {**STAB, 'order': 2},
            A('shove', 3, target='ogre', says='shove him off the bridge')])
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'resolved', 'refused'])
        self.assertEqual(arena.fight['pc_damage'], 6)
        self.assertEqual(arena.fight['hp']['ogre'], 54)
        self.assertIn('"Shove him off the bridge" didn\'t happen because', result.public_event)


class DeclaredOtherActs(unittest.TestCase):
    def test_an_object_act_is_refused_and_the_attack_still_lands(self):
        sheet = without_shield(wizard(hp=60))
        arena = kiln(self, sheet)
        result = arena.act('I push the kiln door shut, then stab the slinger.', combat_acts=[
            A('object', 1, says='push the kiln door shut'),
            A('attack', 2, target='archer', weapon='dagger', roll='16 to hit, 3 piercing')])
        self.assertIn('"Push the kiln door shut" didn\'t happen because', result.public_event)
        self.assertEqual(arena.fight['hp']['archer'], 4)

    def test_a_grapple_is_contested_and_asks_for_athletics_when_unrolled(self):
        arena = bridge(self)
        exc = arena.held('I grab him.', combat_acts=[A('grapple', 1, target='ogre')])
        self.assertIn('Athletics', str(exc))
        arena.act('I grab him, Athletics 16.', combat_acts=[A('grapple', 1, target='ogre', roll='Athletics 16')])
        self.assertEqual(arena.state['scene']['grappled'], 'ogre')

    def test_dodge_takes_the_action(self):
        arena = bridge(self)
        result = arena.act('I dodge, then stab.', combat_acts=[A('dodge', 1), {**STAB, 'order': 2}])
        self.assertIn('Dodge action', result.public_event)
        self.assertIn('already used your action', result.public_event)
        self.assertEqual(arena.fight['hp']['ogre'], 59)

    def test_hide_needs_its_stealth_roll(self):
        arena = bridge(self)
        exc = arena.held('I hide.', combat_acts=[A('hide', 1)])
        self.assertIn('Stealth', str(exc))

    def test_an_off_hand_attack_is_the_bonus_action_after_a_light_weapon(self):
        sheet = warlock(hp=60, gear=['dagger', 'dagger'])
        arena = kiln(self, sheet)
        arena.act('Dagger, then the off-hand dagger.', combat_acts=[
            A('attack', 1, target='imp', weapon='dagger', roll='16 to hit, 3 piercing'),
            A('bonus_attack', 2, target='imp', weapon='dagger', roll='16 to hit, 2 piercing')])
        self.assertEqual(arena.fight['hp']['imp'], 13)
        arena = kiln(self, sheet)
        result = arena.act('Off-hand dagger only.', combat_acts=[
            A('bonus_attack', 1, target='imp', weapon='dagger', roll='16 to hit, 2 piercing', says='off-hand dagger')])
        self.assertIn("didn't happen because an off-hand attack follows", result.public_event)

    def test_a_declared_spell_and_a_late_hellish_rebuke(self):
        sheet = without_shield(wizard(hp=60))
        arena = kiln(self, sheet)
        arena.act('Fire Bolt the imp.', combat_acts=[A('spell', 1, target='imp', spell='fire bolt',
                                                        roll='17 to hit, 7 fire')])
        self.assertEqual(arena.fight['hp']['imp'], 11)
        arena = kiln(self, warlock(hp=60))
        arena.act('Hellish Rebuke the imp.', combat_acts=[A('reaction', 1, target='imp', reaction='hellish_rebuke',
                                                             roll='!cast hellish rebuke -t imp -l 1\nHellish Rebuke: 10 fire')])
        self.assertEqual(arena.fight['hp']['imp'], 8)
        self.assertEqual(arena.slot1(), 1)


class DeclaredSchema(unittest.TestCase):
    def offer(self):
        return {'targets': ['ogre'], 'weapons': ['rapier'], 'spells': [], 'reactions': ['uncanny_dodge']}

    def test_unknown_ids_and_kinds_are_fixable_rejections(self):
        for bad in ([A('attack', 1, target='dragon')], [A('fly', 1)], [STAB, {**STAB}], [], 'stab'):
            with self.subTest(bad=bad), self.assertRaises(InvalidChange):
                kit_combat_acts.check(bad, self.offer())

    def test_no_fight_no_combat_acts(self):
        with self.assertRaises(InvalidChange):
            kit_combat_acts.check([STAB], None)

    def test_entries_come_back_in_order(self):
        out = kit_combat_acts.check([{**STAB, 'order': 2}, A('move', 1, way='away')], self.offer())
        self.assertEqual([e['kind'] for e in out], ['move', 'attack'])


if __name__ == '__main__':
    unittest.main()
