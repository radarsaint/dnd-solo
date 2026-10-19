"""Brendon's rulings (2026-10-19), on synthetic rooms (tests/fixtures/rooms) with every die pinned:

(1) Slot ask: a plain leveled cast with no slot left at the spell's level ASKS ("cast it at 2nd
    level?"), states the rule, and spends nothing until the player answers. Yes spends that slot
    and resolves; no spends nothing. No higher slot free: it fizzles, as before. ``-l N`` wins.
(2) Equipment audit: at session start and after rests the engine checks the sheet against the
    gear in use (armor/shield proficiency, attunement). Each mismatch is a pending clarification
    Kit raises once, in voice; the answer is game state. While non-proficient armor or a shield
    is in use the engine enforces the SRD: disadvantage on Strength/Dexterity checks, saves and
    attacks, and no spellcasting. A shield swap costs the action, every time. An item's own
    initiative advantage applies only while it is in use, and cancels against disadvantage.

General, never a special case: every fixture sheet in tests/fixtures/characters is checked, and
the slot ask runs on a wizard, a cleric and a sorcerer."""
import copy
import itertools
import json
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_acts, kit_combat, kit_gear, kit_rolls
from runtime.kit_agent import (KitChatBridge, PendingRuling, RoomAdjudicator, WindowAnswer, check_window_answer,
                               check_window_voice, prepare_turn, window_view)
from runtime.state_context import InvalidChange
from test_kit_gear_answers import answered
from test_kit_review101c import Arena

ROOT = Path(__file__).resolve().parents[1]
SHEETS = ROOT / 'tests' / 'fixtures' / 'characters'


def sheet(name, **extra):
    out = json.loads((SHEETS / f'{name}.json').read_text())
    out.update(extra)
    return out


def stowed(arena, item):
    """The player puts the item away, in play (the act path): the audit's question is settled."""
    arena.act('I take off my chain shirt.' if item == 'chain_shirt' else 'I put my shield away.')
    assert kit_gear.gear(arena.state)['in_use'][item] is False, item
    return arena


def held(test, arena, item):
    """He tells Kit the item is in use (her question, his answer, through the bridge): the
    rules as written apply from then on (Brendon: ask first)."""
    return answered(test, arena, item, 'held')


def spend(arena, *levels):
    """Every slot at these levels used (test setup)."""
    revision, state = arena.runtime.load()
    resources = copy.deepcopy(state['pc_resources'])
    for level in levels:
        resources['slots'][str(level)]['used'] = resources['slots'][str(level)]['max']
    arena.runtime.commit(f'spent-{levels}', revision, [{'type': 'pc_resources', 'resources': resources,
                                                       'evidence': 'slots spent (test setup)'}])


def used(arena):
    return {level: slot['used'] for level, slot in arena.state['pc_resources']['slots'].items()}


def wizard():
    """Nik's sheet as it is, with the Sentinel Shield stowed (the audit answered): he may cast."""
    return sheet('nik', hp=60)


MM = 'Initiative 25. I cast Magic Missile at the ember imp (!cast magic missile) 3d4 (3, 2, 4) + 3 = 12 force'


class SlotAsk(unittest.TestCase):
    """(1) No slot at the spell's level, a higher one free: Kit asks; nothing is spent until the answer."""

    def casters(self):
        # (sheet, item to stow first or None, the cast)
        return (('nik', 'sentinel_shield', MM),
                ('mirel_sorcerer', 'chain_shirt', MM),
                ('ilsa_cleric', None, 'Initiative 25. I cast Guiding Bolt at the ember imp (!cast guiding bolt)'))

    def arena(self, name, item):
        arena = Arena(self, 'kiln', sheet=sheet(name, hp=60), roll=lambda: 2)  # every foe misses
        if item:
            stowed(arena, item)
        spend(arena, 1)
        return arena

    def test_a_plain_cast_with_no_slot_at_its_level_asks_and_spends_nothing(self):
        for name, item, cast in self.casters():
            with self.subTest(sheet=name):
                arena = self.arena(name, item)
                before = used(arena)
                result = arena.act(cast)
                waiting = arena.fight['awaiting']
                self.assertEqual(waiting['kind'], 'slot_ask')
                self.assertEqual(waiting['level'], 2, 'the next free slot')
                self.assertIn('2nd level', result.public_event)
                self.assertIn('higher-level slot', result.public_event, 'the rule is stated')
                self.assertTrue(result.public_event.rstrip().endswith('?'), result.public_event)
                self.assertEqual(used(arena), before, 'nothing spent until he answers')
                self.assertEqual(arena.fight['hp']['imp'], arena.fight['max_hp']['imp'])
                self.assertNotIn('fizzles', result.public_event)

    def test_yes_spends_the_offered_slot_once_and_resolves(self):
        arena = self.arena('nik', 'sentinel_shield')
        arena.act(MM)
        result = arena.act('Yes, second level.', upcast='yes')
        self.assertIsNone(arena.fight.get('awaiting'))
        self.assertIn('Magic Missile', result.public_event)
        # The 1st-level roll in the first message is not the 2nd-level spell (Nagatha, 59ce12a):
        # he rolls it at 2nd level, and that roll lands.
        self.assertEqual(arena.fight['hp']['imp'], 18)
        self.assertIn('!cast magic missile -l 2', result.public_event)
        arena.act('Magic Missile: 4d4 (3, 2, 4, 1) + 4 = 14 force')
        self.assertEqual(used(arena), {'1': 4, '2': 1, '3': 0})
        self.assertEqual(arena.fight['hp']['imp'], 18 - 14)

    def test_yes_with_a_named_higher_slot_spends_that_one(self):
        arena = self.arena('mirel_sorcerer', 'chain_shirt')
        arena.act(MM)
        arena.act('Use a third-level slot.', upcast='yes', slot_level=3)
        self.assertEqual(used(arena), {'1': 4, '2': 0, '3': 1})

    def test_no_spends_nothing_and_his_turn_is_still_his(self):
        for answer in ('no', 'cancel'):
            with self.subTest(answer=answer):
                arena = self.arena('nik', 'sentinel_shield')
                arena.act(MM)
                result = arena.act('No, never mind.', upcast='no')
                self.assertIsNone(arena.fight.get('awaiting'))
                self.assertEqual(used(arena), {'1': 4, '2': 0, '3': 0})
                self.assertEqual(arena.fight['hp']['imp'], arena.fight['max_hp']['imp'])
                self.assertIn('Nothing is cast', result.public_event)
                fight = kit_combat.Fight(arena.runtime.source(), arena.state, 0, '', None)
                self.assertTrue(fight.pc_turn_now(), 'the action is not spent')

    def test_an_attack_spell_asks_before_the_attack_roll_and_keeps_the_level(self):
        arena = self.arena('ilsa_cleric', None)
        arena.act('Initiative 25. I cast Guiding Bolt at the ember imp (!cast guiding bolt)')
        arena.act('Yes.', upcast='yes')
        self.assertEqual(used(arena)['2'], 0, 'nothing spent before the roll')
        self.assertEqual(arena.fight['pending'].get('slot_level'), 2)
        arena.act('Guiding Bolt: To Hit: 1d20 (15) + 6 = 21\nDamage: 5d6 (3, 3, 3, 3, 2) = 14 radiant')
        self.assertEqual(used(arena), {'1': 4, '2': 1, '3': 0})
        self.assertEqual(arena.fight['hp']['imp'], 18 - 14)

    def test_without_kits_read_the_engine_does_not_guess(self):
        arena = self.arena('nik', 'sentinel_shield')
        arena.act(MM)
        revision, state = arena.runtime.load()
        with self.assertRaises(WindowAnswer):
            arena.adjudicator.resolve('Sure', revision, state)

    def test_an_explicit_level_wins_and_is_never_asked(self):
        arena = self.arena('nik', 'sentinel_shield')
        result = arena.act(MM.replace('(!cast magic missile)', '(!cast magic missile -l 3)'))
        self.assertIsNone((arena.fight or {}).get('awaiting'))
        self.assertEqual(used(arena), {'1': 4, '2': 0, '3': 1})
        self.assertNotIn('?', result.public_event.split('Magic Missile')[0])

    def test_a_free_slot_at_its_own_level_is_spent_without_asking(self):
        arena = Arena(self, 'kiln', sheet=sheet('ilsa_cleric', hp=60), roll=lambda: 2)
        arena.act('Initiative 25. I cast Guiding Bolt at the ember imp (!cast guiding bolt). '
                  'To Hit: 1d20 (15) + 6 = 21\nDamage: 4d6 (3, 3, 3, 3) = 12 radiant')
        self.assertIsNone(arena.fight.get('awaiting'))
        self.assertEqual(used(arena), {'1': 1, '2': 0, '3': 0})

    def test_no_higher_slot_free_still_fizzles(self):
        arena = self.arena('nik', 'sentinel_shield')
        spend(arena, 2, 3)
        result = arena.act(MM)
        self.assertIn('fizzles', result.public_event)
        self.assertIsNone(arena.fight.get('awaiting'))


class SlotAskWindow(unittest.TestCase):
    """The slot ask is an engine window: Kit voices it (naming the level, ending on the question)
    and reads the reply as the ``upcast`` act field."""

    def window(self):
        return {'kind': 'slot_ask', 'awaits': 'player_answer', 'spell': 'magic missile', 'spell_level': 1,
                'level': 2, 'free': [2, 3], 'deferred_action_id': 'x'}

    def test_the_view_names_the_spell_the_level_and_the_rule(self):
        view = window_view({}, {'player_sheet': sheet('nik')}, self.window())
        self.assertEqual((view['spell'], view['level'], view['free']), ('Magic Missile', 2, [2, 3]))
        self.assertIn('higher-level slot', view['rule'])

    def test_kit_must_name_the_level_and_ask(self):
        view = window_view({}, {'player_sheet': sheet('nik')}, self.window())
        narrate = {'speaker': 'Narrator', 'text': 'The imp hisses as the last of your first-circle power gutters out.'}
        with self.assertRaisesRegex(InvalidChange, '2nd level'):
            check_window_voice(view, [narrate, {'speaker': 'Kit', 'text': 'Your slots are empty. Still cast it?'}])
        check_window_voice(view, [narrate, {'speaker': 'Kit', 'text': 'No first-level slot left; a higher slot works. '
                                                                      'Cast it at 2nd level?'}])

    def test_the_answer_is_yes_no_or_unclear_at_a_free_level(self):
        view = window_view({}, {'player_sheet': sheet('nik')}, self.window())
        self.assertEqual(check_window_answer(view, {'upcast': {'choice': 'yes'}}, []), {'upcast': 'yes'})
        self.assertEqual(check_window_answer(view, {'upcast': {'choice': 'yes', 'slot_level': 3}}, []),
                         {'upcast': 'yes', 'slot_level': 3})
        self.assertEqual(check_window_answer(view, {'upcast': {'choice': 'no'}}, []), {'upcast': 'no'})
        with self.assertRaisesRegex(InvalidChange, 'slot_level'):
            check_window_answer(view, {'upcast': {'choice': 'yes', 'slot_level': 1}}, [])
        with self.assertRaisesRegex(InvalidChange, 'ask'):
            check_window_answer(view, {'upcast': {'choice': 'unclear'}}, [])

    def test_through_the_bridge(self):
        arena = Arena(self, 'kiln', sheet=sheet('nik', hp=60), roll=lambda: 2)
        stowed(arena, 'sentinel_shield')
        spend(arena, 1)
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        packet = bridge.prepare(MM, 'w1', one_pass=True)
        self.assertEqual(packet['stage'], 'window_voice')
        self.assertEqual(packet['input']['window']['kind'], 'slot_ask')
        bridge.complete('w1', {'decision': {'window': 'voiced'}, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': 'You reach for the familiar first-circle weave and find it spent.'},
            {'speaker': 'Kit', 'text': 'A higher slot works for it. Cast it at 2nd level?'}]}})
        packet = bridge.prepare('Do it.', 'w2', one_pass=True)
        self.assertEqual(packet['stage'], 'window_answer')
        packet = bridge.complete('w2', {'decision': {'upcast': {'choice': 'yes'}}, 'performance': {'segments': []}})
        self.assertEqual(packet['window_answered'], {'upcast': 'yes'})


class AuditAcrossSheets(unittest.TestCase):
    """(2) The audit reads any sheet: class training, multiclassing, feats, explicit lists, attunement."""

    EXPECTED = {'nik': ['shield_proficiency'], 'brannoc_fighter': [], 'ilsa_cleric': [],
                'mirel_sorcerer': ['armor_proficiency'], 'tamsin_bard': ['attunement_limit'], 'example_pc': [],
                'pell_wizard': ['unverified_proficiency']}

    def test_every_fixture_sheet(self):
        for path in sorted(SHEETS.glob('*.json')):
            with self.subTest(sheet=path.stem):
                self.assertIn(path.stem, self.EXPECTED, 'a new fixture sheet needs its expected audit here')
                found = [issue['issue'] for issue in kit_gear.audit(json.loads(path.read_text()))]
                self.assertEqual(found, self.EXPECTED[path.stem])

    def test_training_comes_from_the_build_not_the_name(self):
        nik = sheet('nik')
        self.assertEqual(kit_gear.audit(dict(nik, **{'class': 'Wizard 4 / Fighter 1'})), [], 'multiclass fighter: shields')
        self.assertEqual(kit_gear.audit(dict(nik, features=nik['features'] + ['Moderately Armored'])), [])
        self.assertEqual([i['issue'] for i in kit_gear.audit(dict(nik, armor_proficiencies=['shields']))],
                         ['unverified_proficiency'], 'a listed training with no source is asked about, not trusted')
        wren = sheet('example_pc')
        self.assertEqual([i['issue'] for i in kit_gear.audit(dict(wren, gear=wren['gear'] + ['shield']))],
                         ['shield_proficiency'], 'a rogue has no shield training')
        self.assertEqual([i['issue'] for i in kit_gear.audit(dict(wren, gear=wren['gear'] + ['plate armor']))],
                         ['armor_proficiency'])
        self.assertEqual(kit_gear.audit(dict(wren, **{'class': 'Mystery Class'}, gear=['shield'])), [],
                         'an unknown build is never guessed at')

    def test_an_item_can_describe_itself(self):
        brannoc = sheet('brannoc_fighter')
        staff = {'name': 'Rod of the Old Moon', 'requires_attunement': True, 'attunement_by': 'wizard'}
        self.assertEqual([i['issue'] for i in kit_gear.audit(dict(brannoc, magic_items=[staff]))], ['attunement_class'])
        self.assertEqual(kit_gear.audit(dict(brannoc, magic_items=[dict(staff, attuned=False)])), [])


class Clarification(unittest.TestCase):
    """Each mismatch is a pending clarification at session start and after a rest; Kit raises it
    once, in voice; the player's answer is recorded as game state."""

    def test_session_start_queues_one_per_mismatch(self):
        for name, issues in AuditAcrossSheets.EXPECTED.items():
            with self.subTest(sheet=name):
                arena = Arena(self, 'kiln', sheet=sheet(name))
                queued = [(c['issue'], c['status']) for c in kit_gear.gear(arena.state)['clarify']]
                self.assertEqual(queued, [(issue, 'pending') for issue in issues])

    def test_a_rest_audits_again_but_never_raises_one_twice(self):
        arena = Arena(self, 'kiln', sheet=sheet('tamsin_bard'))
        revision, state = arena.runtime.load()
        entry = kit_gear.pending(state)
        arena.runtime.commit('raise', revision, [kit_gear.raised_event(entry['id'], 't1')])
        arena.runtime.rest('long')
        clarify = kit_gear.gear(arena.state)['clarify']
        self.assertEqual([(c['issue'], c['status']) for c in clarify], [('attunement_limit', 'raised')])
        self.assertEqual(kit_gear.gear(arena.state)['audits'], 2, 'the rest ran the audit')

    def test_a_rest_finds_what_the_sheet_load_did_not(self):
        arena = Arena(self, 'kiln', sheet=sheet('brannoc_fighter'))
        revision, state = arena.runtime.load()
        state_gear = kit_gear.gear(state)
        self.assertEqual(state_gear['clarify'], [])
        arena.runtime.set_player_sheet(sheet('brannoc_fighter', magic_items=[
            {'name': 'Rod of the Old Moon', 'requires_attunement': True, 'attunement_by': 'wizard'}]))
        self.assertEqual([c['issue'] for c in kit_gear.gear(arena.state)['clarify']], ['attunement_class'])

    def test_kit_gets_it_once_on_a_natural_turn_and_the_answer_is_game_state(self):
        arena = Arena(self, 'kiln', sheet=sheet('nik'))
        _, body, planning = prepare_turn(arena.runtime, arena.adjudicator, 'I look around the kiln room.')
        ask = planning['gear_clarify']
        self.assertEqual(ask['item'], 'Sentinel Shield')
        self.assertIn('cannot cast spells', ask['rule'])
        self.assertIn('disadvantage', ask['rule'])
        self.assertEqual(body['gear_clarify'], ask['id'])
        _, body, planning = prepare_turn(arena.runtime, arena.adjudicator, 'Hey Kit, how long is a short rest?',
                                         table_talk=True)
        self.assertNotIn('gear_clarify', planning, 'never in table talk')
        # Kit raised it (the commit of that turn records it); it is not raised again.
        revision, state = arena.runtime.load()
        arena.runtime.commit('raised', revision, [kit_gear.raised_event(ask['id'], 't1')])
        _, body, planning = prepare_turn(arena.runtime, arena.adjudicator, 'I look at the kiln door.')
        self.assertNotIn('gear_clarify', planning)
        self.assertEqual(body['acts']['gear']['items'], ['sentinel_shield'], 'the answer is Kit\'s to read')
        # The answer: he stows it. Recorded, and the clarification is closed.
        revision, state = arena.runtime.load()
        decl = kit_acts.check({'gear': {'item': 'sentinel_shield', 'state': 'stowed'}}, body)['gear']
        result = arena.adjudicator.declared_acts({'gear': decl}, 'I sling it on my back.', revision, state)
        arena.runtime.commit('answer', revision, list(result.events))
        body_now = kit_gear.gear(arena.state)
        self.assertFalse(body_now['in_use']['sentinel_shield'])
        self.assertEqual(body_now['clarify'][0]['status'], 'answered')

    def test_the_raise_check_names_the_item_and_asks(self):
        entry = kit_gear.audit(sheet('mirel_sorcerer'))[0]
        with self.assertRaisesRegex(InvalidChange, 'chain shirt'):
            kit_gear.check_spoken_clarify(entry, [{'speaker': 'Kit', 'text': 'The dust settles. What now?'}])
        kit_gear.check_spoken_clarify(entry, [{'speaker': 'Kit', 'text': 'That chain shirt: you never trained in '
                                                                         'armor, so no spells while it is on. Keep it?'}])


class Enforcement(unittest.TestCase):
    """While non-proficient armor or a shield is in use: no spellcasting, and disadvantage on
    Strength and Dexterity attacks, saves and checks. Dice pinned."""

    def test_no_spellcasting_in_non_proficient_gear(self):
        for name, cast in (('nik', MM), ('mirel_sorcerer', MM),
                           ('mirel_sorcerer', 'Initiative 25. I cast Fire Bolt at the ember imp. '
                                              'To Hit: 1d20 (15) + 7 = 22\nDamage: 2d10 (5, 5) = 10 fire')):
            with self.subTest(sheet=name, cast=cast[:40]):
                arena = Arena(self, 'kiln', sheet=sheet(name, hp=60), roll=lambda: 2)
                held(self, arena, {'nik': 'sentinel_shield'}.get(name, 'chain_shirt'))
                before = used(arena)
                result = arena.act(cast)
                self.assertIn('cannot cast', result.public_event)
                self.assertIn('not proficient', result.public_event)
                self.assertEqual(used(arena), before)
                self.assertEqual(arena.fight['hp']['imp'], arena.fight['max_hp']['imp'])

    def test_proficient_gear_casts_freely(self):
        arena = Arena(self, 'kiln', sheet=sheet('ilsa_cleric', hp=60), roll=lambda: 2)
        arena.act('Initiative 25. I cast Guiding Bolt at the ember imp (!cast guiding bolt). '
                  'To Hit: 1d20 (15) + 6 = 21\nDamage: 4d6 (3, 3, 3, 3) = 12 radiant')
        self.assertEqual(arena.fight['hp']['imp'], 6)

    def test_no_shield_spell_window_while_casting_is_barred(self):
        arena = held(self, Arena(self, 'kiln', sheet=sheet('nik', hp=60), roll=lambda: 10), 'sentinel_shield')  # the imp hits
        arena.act('Initiative 25. I stab the kobold slinger with my dagger. To Hit: 2d20kl1 (3, 12) + 5 = 8. 3 piercing')
        self.assertIsNone((arena.fight.get('awaiting') or {}).get('options'), 'Shield is a spell: not offered')
        stowed_arena = Arena(self, 'kiln', sheet=sheet('nik', hp=60), roll=lambda: 10)
        stowed(stowed_arena, 'sentinel_shield')
        stowed_arena.act('Initiative 25. I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')
        self.assertEqual(stowed_arena.fight['awaiting']['options'], ['shield'])

    def test_a_weapon_attack_is_rolled_with_disadvantage(self):
        arena = held(self, Arena(self, 'kiln', sheet=sheet('nik', hp=60), roll=lambda: 2), 'sentinel_shield')
        result = arena.act('Initiative 25. I stab the kobold slinger with my dagger, 15 to hit, 3 piercing.')
        self.assertIn('with disadvantage', result.public_event)
        self.assertIn('Sentinel Shield', result.public_event)
        self.assertEqual(arena.fight['hp']['archer'], 7, 'a straight roll is not taken')
        arena.act('Initiative 25. I stab the kobold slinger with my dagger. To Hit: 2d20kl1 (3, 12) + 5 = 8. 3 piercing')
        self.assertEqual(arena.fight['hp']['archer'], 7, 'the disadvantage roll stands: a miss')

    def test_the_same_attack_for_a_trained_build_needs_nothing(self):
        arena = Arena(self, 'kiln', sheet=sheet('brannoc_fighter', hp=60), roll=lambda: 2)
        arena.act('Initiative 25. I hit the kobold slinger with my longsword, 15 to hit, 5 slashing.')
        self.assertEqual(arena.fight['hp']['archer'], 2)

    def test_str_and_dex_checks_take_the_lower_die_and_lose_five_passive(self):
        for name, penalised in (('nik', True), ('mirel_sorcerer', True), ('ilsa_cleric', False),
                                ('brannoc_fighter', False)):
            with self.subTest(sheet=name):
                arena = Arena(self, 'kiln', sheet=sheet(name))
                if penalised:
                    held(self, arena, {'nik': 'sentinel_shield'}.get(name, 'chain_shirt'))
                dice = itertools.cycle([15, 4])
                adjudicator = RoomAdjudicator(roll=lambda: next(dice), source=arena.runtime.source())
                state = arena.state
                result = adjudicator._check('athletics', 30, state, 1, 'physical:test', 'I heave at it.')
                bonus = sheet(name)['skills']['athletics']
                self.assertEqual(result['die'], 4 if penalised else 15)
                self.assertEqual(result['total'], (4 if penalised else 15) + bonus)
                wis = adjudicator._check('insight', 30, arena.state, 1, 'physical:wis', 'I read him.')
                self.assertNotEqual(wis.get('die'), None)

    def test_a_dex_save_is_called_with_disadvantage(self):
        arena = Arena(self, 'kiln', sheet=sheet('nik'))
        self.assertNotIn('disadvantage', kit_combat.save_prompt({'save': 'dex'}, arena.state), 'not before he answers')
        state = dict(held(self, arena, 'sentinel_shield').state, combat={'status': 'running'})
        self.assertIn('with disadvantage', kit_combat.save_prompt({'save': 'dex'}, state))
        self.assertNotIn('disadvantage', kit_combat.save_prompt({'save': 'wis'}, state))
        self.assertNotIn('disadvantage', kit_combat.save_prompt({'save': 'dex'}, {'player_sheet': sheet('ilsa_cleric')}))

    def test_roll_modes_are_read_from_avrae_and_words(self):
        self.assertEqual(kit_rolls.roll_mode('To Hit: 2d20kl1 (3, 12) + 5 = 8'), 'disadvantage')
        self.assertEqual(kit_rolls.roll_mode('!a dagger dis'), 'disadvantage')
        self.assertEqual(kit_rolls.roll_mode('8 to hit, with disadvantage'), 'disadvantage')
        self.assertEqual(kit_rolls.roll_mode('To Hit: 2d20kh1 (3, 12) + 5 = 17'), 'advantage')
        self.assertEqual(kit_rolls.roll_mode('To Hit: 1d20 (12) + 5 = 17'), 'normal')
        self.assertEqual(kit_rolls.roll_mode('15 to hit'), 'normal')


class Swaps(unittest.TestCase):
    """Donning or doffing a shield costs the action; every swap costs its own, so the
    drop-cast-ready exploit costs three turns, not one."""

    OPEN = 'Initiative 25. I stab the kobold slinger with my dagger. To Hit: 2d20kl1 (3, 2) + 5 = 7. 3 piercing'

    def opened(self):
        arena = Arena(self, 'kiln', sheet=sheet('nik', hp=60), roll=lambda: 2)
        arena.act(self.OPEN)
        self.assertEqual(arena.fight['round'], 2)
        return arena

    def test_stowing_takes_the_action_then_the_cast_works_then_readying_takes_another(self):
        arena = self.opened()
        result = arena.act('I stow my shield.')
        self.assertIn('takes your action', result.public_event)
        self.assertEqual(arena.fight['round'], 3, 'the swap was his turn: the round ran on')
        self.assertFalse(kit_gear.gear(arena.state)['in_use']['sentinel_shield'])
        arena.act('I cast Magic Missile at the ember imp (!cast magic missile) 3d4 (3, 2, 4) + 3 = 12 force')
        self.assertEqual(arena.fight['hp']['imp'], 6)
        self.assertEqual(arena.fight['round'], 4)
        arena.act('I ready my shield again.')
        self.assertTrue(kit_gear.gear(arena.state)['in_use']['sentinel_shield'])
        self.assertEqual(arena.fight['round'], 5)

    def test_drop_and_cast_in_one_breath_is_the_swap_only(self):
        arena = self.opened()
        result = arena.act('I drop my shield and cast Magic Missile at the ember imp (!cast magic missile) '
                           '3d4 (3, 2, 4) + 3 = 12 force')
        self.assertEqual(arena.fight['hp']['imp'], 18, 'the swap took the action')
        self.assertIn('takes your action', result.public_event)
        self.assertEqual(used(arena)['1'], 0)

    def test_the_spell_shield_is_never_a_swap(self):
        state = {'player_sheet': sheet('nik')}
        for text in ('I cast Shield!', 'I raise a shield of force (!cast shield)', 'Should I stow my shield?'):
            with self.subTest(text=text):
                self.assertIsNone(kit_gear.read_swap(text, state))
        self.assertEqual(kit_gear.read_swap('I sling the Sentinel Shield onto my back.', state)['in_use'], False)
        self.assertEqual(kit_gear.read_swap('I strap on my shield.', state)['in_use'], True)

    def test_stowing_the_shield_gives_up_its_ac(self):
        arena = self.opened()
        fight = kit_combat.Fight(arena.runtime.source(), arena.state, 0, '', None)
        self.assertEqual(fight.pc_ac(), 14, 'held, a shield gives its AC even untrained (SRD)')
        arena.act('I stow my shield.')
        fight = kit_combat.Fight(arena.runtime.source(), arena.state, 0, '', None)
        self.assertEqual(fight.pc_ac(), 12)


class InitiativeAdvantage(unittest.TestCase):
    """An item's own initiative advantage applies only while it is in use, and cancels against
    the Dexterity disadvantage of untrained gear (SRD: one of each is a straight roll)."""

    def state(self, name, **extra):
        state = {'player_sheet': sheet(name, **extra)}
        kit_gear.run_audit(state, 'test')
        return state

    def test_modes(self):
        sentinel = ['chain mail', {'name': 'Sentinel Shield'}, 'longsword']
        # Before he answers, the sheet alone sets no penalty (Brendon: ask first): the shield's
        # own advantage stands. Once he says it is on his arm, the untrained disadvantage cancels it.
        self.assertEqual(kit_gear.roll_mode(self.state('nik'), 'dex', 'initiative', fight=True)[0], 'advantage')
        nik = held(self, Arena(self, 'kiln', sheet=sheet('nik')), 'sentinel_shield').state
        self.assertEqual(kit_gear.roll_mode(nik, 'dex', 'initiative', fight=True)[0], 'normal')
        self.assertIn('cancel', kit_gear.initiative_prompt(nik))
        self.assertEqual(kit_gear.roll_mode(self.state('brannoc_fighter', gear=sentinel), 'dex', 'initiative',
                                            fight=True)[0], 'advantage')
        self.assertIn('with advantage', kit_gear.initiative_prompt(self.state('brannoc_fighter', gear=sentinel)))
        stowed_state = self.state('brannoc_fighter', gear=sentinel)
        kit_gear.apply_event(stowed_state, kit_gear.change_event(stowed_state, 'sentinel_shield', False, 'stowed'))
        self.assertEqual(kit_gear.initiative_prompt(stowed_state), 'Roll initiative.')
        self.assertEqual(kit_gear.initiative_prompt(self.state('mirel_sorcerer')), 'Roll initiative.')
        mirel = held(self, Arena(self, 'kiln', sheet=sheet('mirel_sorcerer')), 'chain_shirt').state
        self.assertEqual(kit_gear.initiative_prompt(mirel)[:40], 'Roll initiative with disadvantage (the c')
        self.assertEqual(kit_gear.initiative_prompt(self.state('ilsa_cleric')), 'Roll initiative.')

    def test_perception_advantage_from_a_shield_goes_when_it_is_stowed(self):
        from runtime import pc_sheet
        state = self.state('nik')
        state['combat'] = {'status': 'running'}
        self.assertEqual(pc_sheet.advantage_sources(pc_sheet.sheet_now(state, fight=True), 'perception'),
                         ['Sentinel Shield'])
        kit_gear.apply_event(state, kit_gear.change_event(state, 'sentinel_shield', False, 'stowed'))
        self.assertEqual(pc_sheet.advantage_sources(pc_sheet.sheet_now(state, fight=True), 'perception'), [])


if __name__ == '__main__':
    unittest.main()
