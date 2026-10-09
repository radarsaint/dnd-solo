"""#97 re-review (Nagatha, at c78ebfc) and Brendon's save-tie ruling.

A) a handles offer on any physical turn near a known watched feature: pronouns and other
   words are Kit's to resolve, the regex only hints;
B) an offered act must be answered, and no performance shows a still-hidden creature;
C) an unfound feature is not offered, not shown, cannot fire until found;
D) a downed or incapacitated PC: death saves, healing, Kit's call on the foes, conditions
   with SRD durations and repeat saves, the engine never rolling for him;
saves: the attacker meets or beats, so a save that ties the DC fails (both ways);
P2: best-match feature routing, handling mid-fight costs an action or the free interaction.

Room-agnostic: a crypt written from scratch (tests/fixtures/rooms/crypt.json, SRD Ghoul,
Skeleton and Commoner), the carcass room, and three sheets (Nik, Wren, Ilsevel). Every die
is pinned: ``roll`` is the monsters' d20s (attacks, their saves), ``npc_roll`` their Stealth.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_acts, kit_combat, kit_rolls, kit_rooms, kit_triggers
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import RecordingModel

ROOT = Path(__file__).resolve().parents[1]
CRYPT = ROOT / 'tests/fixtures/rooms/crypt.json'
CARCASS = ROOT / 'tests/fixtures/rooms/carcass.json'
SHEETS = {'nik': ROOT / 'tests/fixtures/characters/nik.json',
          'wren': ROOT / 'tests/fixtures/characters/example_pc.json',
          'ilsevel': ROOT / 'tests/fixtures/pc_sheets/ilsevel.json'}


def crypt(**changes):
    source = json.loads(CRYPT.read_text())
    for key, fact in changes.get('facts', {}).items():
        source['facts'][key].update(fact)
    return source


class Room:
    def __init__(self, test, source=None, start=None, sheet='nik', roll=lambda: 10, npc_roll=lambda: 1, hp=None):
        source = source or crypt()
        self._temp = tempfile.TemporaryDirectory()
        test.addCleanup(self._temp.cleanup)
        self.test = test
        self.runtime = Runtime(Path(self._temp.name) / 'kit.sqlite')
        test.addCleanup(self.runtime.close)
        try:
            mounted = kit_rooms.check_room(source)
        except InvalidChange as exc:
            test.fail(f'the room does not mount: {exc}')
        with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{7:032x}'):
            self.runtime.initialize(mounted, start or source['starting_area'])
        pc = json.loads(SHEETS[sheet].read_text())
        if hp is not None:
            pc['hp'] = hp
        self.runtime.set_player_sheet(pc)
        self.adjudicator = RoomAdjudicator(roll=roll, npc_roll=npc_roll, source=self.runtime.source())

    @property
    def state(self):
        return self.runtime.load()[1]

    def resolve(self, action):
        revision, state = self.runtime.load()
        return self.adjudicator.resolve(action, revision, state)

    def act(self, action, handles=None, downed=None):
        """One player line; ``handles``/``downed``: Kit's declared acts, resolved as at commit."""
        revision, state = self.runtime.load()
        try:
            result = self.adjudicator.resolve(action, revision, state)
        except PendingRuling as exc:
            self.test.fail(f'{action!r} was refused: {exc}')
        events = list(result.events)
        plan = {**({'handles': handles} if handles else {}), **({'downed': {'act': downed}} if downed else {})}
        if plan:
            if downed and not (result.offers or {}).get('downed'):
                self.test.fail(f'no downed call offered after {action!r}: {result.public_event}')
            acts = kit_acts.check(plan, {'acts': result.offers or {}})
            after = self.runtime.preview_state(revision, events)
            if hasattr(self.adjudicator, 'declared_acts'):
                declared = self.adjudicator.declared_acts(acts, action, revision, after)
            elif downed:
                self.test.fail('the engine has no way to take Kit\'s call on the downed PC\'s foes')
            else:  # before the act family resolved more than handles
                declared = self.adjudicator.declared_handling(acts['handles'], action, revision, after)
            events += list(declared.events)
            result = declared.__class__(declared.kind, f'{result.public_event} {declared.public_event}'.strip(),
                                        events, declared.handoff, result.offers)
        self.runtime.commit(f't{revision}', revision, events)
        return result

    def wound(self, left):
        """The PC with ``left`` hit points in the running fight (a test shortcut)."""
        revision, state = self.runtime.load()
        fight = copy.deepcopy(state['combat'])
        fight['pc_damage'] = int(state['player_sheet']['hp']) - left
        self.runtime.commit(f'w{revision}', revision, [{'type': 'combat_state', 'state': fight, 'evidence': 'test'}])

    @property
    def fight(self):
        return self.state.get('combat') or {}


def open_tomb(room):
    return room.act('I push the lid aside.', {'target': 'lid', 'act': 'push'})


def bridge_turn(room, action, handles=None, text='Cold stone, dust, and silence.', turn_id='t1', omit=False):
    bridge = KitChatBridge(room.runtime, room.adjudicator)
    packet = bridge.prepare(action, turn_id, one_pass=True)
    plan = RecordingModel().plan(packet['input']['private'])
    plan['improv_read'].update(actor_ref='none', actor_basis='none')
    plan.update(move='world_description', focus_actor='none')
    for key in ('objective', 'visible_cue', 'player_opening'):
        plan['public_brief'].pop(key, None)
    plan['public_brief']['scope'] = 'call'
    if handles is not None:
        plan['handles'] = handles
    elif not omit:
        plan['handles'] = {'target': 'none', 'act': 'none'}
    try:
        return packet, bridge.complete(turn_id, {'decision': plan, 'performance': {
            'segments': [{'speaker': 'Narrator', 'text': text}]}})
    except InvalidChange:
        bridge.abandon(turn_id)
        raise


class AnyPhysicalTurnOffersTests(unittest.TestCase):
    """A: the noun regex no longer gates whether a disturbance is possible."""

    def test_pronouns_and_other_words_reach_kit_with_the_offer(self):
        for line in ('I push it open.', 'I open it up.', 'I heave the stone slab aside.', 'I tip the stone box over.',
                     'I lean my weight on it.'):
            with self.subTest(line=line):
                room = Room(self)
                room.act('I look at the sarcophagus.')
                result = room.resolve(line)
                self.assertIn('sarcophagus', ((result.offers or {}).get('handles') or {}).get('targets', {}),
                              f'{line!r}: {result}')
                self.assertNotIn('trigger_fired', [e['type'] for e in result.events])

    def test_kit_resolving_the_pronoun_fires_the_tomb(self):
        room = Room(self)
        room.act('I look at the sarcophagus.')
        result = room.act('I push it open.', {'target': 'sarcophagus', 'act': 'push'})
        self.assertEqual(room.state['triggers_fired'], ['tomb_opened'])
        self.assertIn('Roll initiative.', result.public_event)

    def test_speech_questions_and_table_talk_carry_no_offer(self):
        for line in ('"Is anyone in there?"', 'What is carved on the sarcophagus?', 'OOC: how do death saves work?'):
            with self.subTest(line=line):
                try:
                    result = Room(self).resolve(line)
                except PendingRuling:
                    continue
                self.assertFalse((result.offers or {}).get('handles'), line)

    def test_a_look_is_offered_but_nothing_fires_and_no_hint_says_handle(self):
        room = Room(self)
        result = room.act('I look at the sarcophagus.')
        self.assertIn('handles', result.offers or {})
        self.assertNotIn('hint', result.offers['handles'])
        self.assertFalse(room.state.get('triggers_fired'))

    def test_examining_is_not_a_hands_on_hint(self):
        """Strong P2: examine, inspect and check are looking, not handling."""
        for line in ('I examine the sarcophagus.', 'I inspect the lid.', 'I check the coffin for traps.'):
            with self.subTest(line=line):
                result = Room(self).resolve(line)
                self.assertNotIn('hint', ((result.offers or {}).get('handles') or {}), line)
        self.assertIn('Looking, examining', kit_acts.HANDLES_RULE)


class AnswerAndHiddenActorTests(unittest.TestCase):
    """B: an offered act is answered, and no performance shows a creature still hidden."""

    def test_leaving_handles_out_when_offered_is_rejected(self):
        room = Room(self)
        with self.assertRaisesRegex(InvalidChange, 'acts.handles is offered'):
            bridge_turn(room, 'I push the lid aside.', omit=True, text='You push the heavy lid aside; dust, nothing more.')
        self.assertFalse(room.state.get('triggers_fired'))

    def test_saying_none_commits_quietly(self):
        room = Room(self)
        bridge_turn(room, 'I take a step toward the sarcophagus.', {'target': 'none', 'act': 'none'})
        self.assertFalse(room.state.get('triggers_fired'))

    def test_half_none_is_rejected(self):
        offer = {'handles': {'targets': {'sarcophagus': ['lid']}}}
        for value in ({'target': 'none', 'act': 'push'}, {'target': 'lid', 'act': 'none'}):
            with self.subTest(value=value):
                with self.assertRaises(InvalidChange):
                    kit_acts.check({'handles': value}, {'acts': offer})

    def test_a_performance_naming_or_describing_the_hidden_ghoul_is_rejected(self):
        for text in ('You push the lid and a grey ghoul lunges out at you.',
                     'You push the lid; something hisses and grey fingers curl over the rim.'):
            with self.subTest(text=text):
                room = Room(self)
                with self.assertRaisesRegex(InvalidChange, 'still hidden'):
                    bridge_turn(room, 'I push the lid aside.', {'target': 'none', 'act': 'none'}, text=text)
                self.assertFalse(room.state.get('triggers_fired'))

    def test_the_declaration_that_wakes_it_lets_kit_show_it(self):
        room = Room(self)
        _, result = bridge_turn(room, 'I push the lid aside.', {'target': 'lid', 'act': 'push'},
                                text='You push the lid and a grey ghoul lunges out at you.')
        self.assertEqual(room.state['triggers_fired'], ['tomb_opened'])
        self.assertIn('ghoul', result['spoken'])

    def test_a_downed_call_must_be_answered(self):
        with self.assertRaisesRegex(InvalidChange, 'acts.downed is offered'):
            kit_acts.check({}, {'acts': {'downed': {'foes': ['ghoul']}}})
        with self.assertRaises(InvalidChange):
            kit_acts.check({'downed': {'act': 'devour'}}, {'acts': {'downed': {'foes': ['ghoul']}}})


class HiddenFeatureTests(unittest.TestCase):
    """C: the unfound trapdoor."""

    def test_an_unfound_trapdoor_is_not_offered_routed_or_fired(self):
        room = Room(self)
        for line in ('I lift the hatch.', 'I pull the trapdoor open.', 'I shove the chest.'):
            with self.subTest(line=line):
                try:
                    result = room.resolve(line)
                except PendingRuling:
                    continue
                self.assertNotIn('trapdoor', json.dumps(result.offers or {}))
                self.assertNotIn('groans up', result.public_event)
        with self.assertRaises(InvalidChange):
            kit_acts.check({'handles': {'target': 'trapdoor', 'act': 'lift'}},
                           {'acts': {'handles': {'targets': {'sarcophagus': ['lid', 'seal']}}}})
        self.assertNotIn('trapdoor', kit_triggers.disturb_targets(room.runtime.source(), room.state))

    def test_the_trapdoor_is_not_in_the_kit_visible_packet(self):
        room = Room(self)
        packet = KitChatBridge(room.runtime, room.adjudicator).prepare('I shove the chest.', 'k', one_pass=True)
        private = copy.deepcopy(packet['input']['private'])
        (private.get('dm_context') or {}).pop('dm_only', None)
        self.assertNotIn('trapdoor', json.dumps(private.get('acts') or {}).casefold())
        self.assertNotIn('hatch', json.dumps(private.get('acts') or {}).casefold())

    def test_found_by_a_search_it_is_offered_and_fires(self):
        room = Room(self)
        room.act('I search the flagstones by the wall. Investigation 15')
        self.assertIn('trapdoor', room.state['known_facts'])
        result = room.resolve('I haul the hatch up.')
        self.assertIn('trapdoor', result.offers['handles']['targets'])
        room.act('I haul the hatch up.', {'target': 'trapdoor', 'act': 'lift'})
        self.assertIn('shaft_opened', room.state['triggers_fired'])
        self.assertEqual(room.state['actors']['skeleton']['status'], 'alive')


class DownedPCTests(unittest.TestCase):
    """D: death saves the player rolls in Avrae, Kit's call on the foes, healing, the
    engine never rolling for him. Nik (32 hp), Wren (21), Ilsevel (44)."""

    def dropped(self, sheet='nik', roll=lambda: 15):
        room = Room(self, sheet=sheet, roll=roll)
        open_tomb(room)
        room.wound(1)
        return room, room.act('Initiative 1')  # the ghoul goes first; its claws drop him

    def test_a_drop_asks_for_a_death_save_not_a_freeze(self):
        for sheet in ('nik', 'wren', 'ilsevel'):
            with self.subTest(sheet=sheet):
                room, result = self.dropped(sheet)
                self.assertTrue(room.fight.get('pc_down'))
                self.assertIn('Roll a death saving throw.', result.public_event)
                self.assertIn('unconscious', room.state.get('pc_conditions') or [])
                with self.assertRaisesRegex(PendingRuling, 'death saving throw'):
                    room.resolve('I crawl to the arch.')

    def test_three_successes_stabilize_and_turned_away_foes_end_the_fight(self):
        room, _ = self.dropped('wren')
        room.act('Death save 12', downed='turn_away')
        room.act('death saving throw: 15', downed='turn_away')
        result = room.act('I roll a death save, 10')
        self.assertIn('You are stable.', result.public_event)
        self.assertTrue(room.fight.get('pc_stable'))
        room2 = room
        last = room2.resolve('Death save 12') if room2.fight.get('awaiting', {}).get('kind') == 'roll_call' else None
        self.assertIsNone(last, 'a stable PC rolls no more death saves')
        offers = room.fight.get('awaiting') or {}
        self.assertEqual(offers.get('kind'), 'kit_call')

    def test_three_failures_kill_and_a_natural_1_counts_twice(self):
        room, _ = self.dropped('ilsevel')
        result = room.act('Death save: nat 1', downed='turn_away')
        self.assertEqual(room.fight['death_saves']['failures'], 2)
        result = room.act('Death save 9')
        self.assertIn('You die.', result.public_event)
        self.assertTrue(room.fight.get('pc_dead'))
        with self.assertRaisesRegex(PendingRuling, 'dead'):
            room.resolve('I get up.')

    def test_a_natural_20_brings_him_back_with_1_hp_and_it_is_his_turn(self):
        room, _ = self.dropped('nik')
        result = room.act('Death save 20')
        self.assertFalse(room.fight.get('pc_down'))
        self.assertEqual(int(room.state['player_sheet']['hp']) - room.fight['pc_damage'], 1)
        self.assertIn('Your turn.', result.public_event)
        self.assertNotIn('unconscious', room.state.get('pc_conditions') or [])

    def test_monsters_keep_acting_and_attacking_him_is_kits_call(self):
        room, _ = self.dropped('nik')
        # Kit: the ghoul attacks. Advantage, and a hit within 5 feet is a critical hit: two failures.
        result = room.act('Death save 12', downed='attack')
        self.assertEqual(result.offers['downed']['foes'], ['ghoul'])
        self.assertEqual(room.fight['death_saves'], {'successes': 1, 'failures': 2})
        evidence = ' '.join(e.get('evidence', '') for e in result.events)
        self.assertIn('(advantage)', evidence)
        self.assertIn('crit 14', evidence)
        self.assertIn('Roll a death saving throw.', result.public_event)

    def test_turning_away_leaves_him_be(self):
        room, _ = self.dropped('nik')
        room.act('Death save 12', downed='turn_away')
        self.assertEqual(room.fight['death_saves'], {'successes': 1, 'failures': 0})
        self.assertIn('death', (room.fight.get('awaiting') or {}).get('save', ''))

    def test_massive_damage_kills_outright(self):
        source = crypt()
        source['actors']['ghoul']['stat_block'] = {'ac': 12, 'hp': 22, 'initiative': 2,
                                                   'attacks': [{'name': 'claws', 'to_hit': 4, 'damage': 40,
                                                                'type': 'slashing'}]}
        room = Room(self, source=source, sheet='wren', roll=lambda: 15)  # Wren: 21 hp
        open_tomb(room)
        room.wound(1)
        result = room.act('Initiative 1')
        self.assertIn('You die.', result.public_event)
        self.assertTrue(room.fight.get('pc_dead'))

    def test_healing_from_someone_else_revives_him(self):
        room, _ = self.dropped('wren')
        with self.assertRaisesRegex(PendingRuling, 'cannot do that yourself'):
            room.resolve('I drink my potion of healing: 7')
        with self.assertRaisesRegex(PendingRuling, 'Roll the healing'):
            room.resolve('The sexton pours a potion of healing down my throat.')
        result = room.act('The sexton pours a potion of healing down my throat: 7')
        self.assertFalse(room.fight.get('pc_down'))
        self.assertEqual(int(room.state['player_sheet']['hp']) - room.fight['pc_damage'], 7)
        self.assertIn('You come to with 7 hit points.', result.public_event)
        self.assertNotIn('unconscious', room.state.get('pc_conditions') or [])

    def test_the_engine_never_rolls_his_death_save(self):
        room, _ = self.dropped('nik')
        for line in ('I hope I live.', 'Initiative 3'):
            with self.subTest(line=line):
                with self.assertRaisesRegex(PendingRuling, 'death saving throw in Avrae first'):
                    room.resolve(line)
        self.assertEqual(kit_combat.save_total('Death Save: 1d20 (13) = `13`', 'death'), 13)


class ConditionTests(unittest.TestCase):
    """D: conditions carry their SRD duration and repeat saves, and expire."""

    def clawed(self, sheet='wren', save='Con save 3', hp=None):
        room = Room(self, sheet=sheet, roll=lambda: 15, hp=hp)  # the claws hit
        open_tomb(room)
        room.act('Initiative 1')
        return room, room.act(save)

    def test_the_ghouls_claws_paralyze_with_a_repeat_save_at_the_end_of_his_turn(self):
        room, result = self.clawed()
        self.assertIn('paralyzed', room.state['pc_conditions'])
        terms = room.state['pc_condition_terms']['paralyzed']
        self.assertEqual((terms['rounds'], terms['save']['ability'], terms['save']['dc']), (10, 'con', 10))
        self.assertIn('pc_conditions', [e['type'] for e in result.events])
        self.assertIn('end of your turn', result.public_event)
        result = room.act('Con save 14')
        self.assertNotIn('paralyzed', room.state['pc_conditions'])
        self.assertIn('You shake off the paralysis.', result.public_event)

    def test_attacks_on_a_paralyzed_pc_have_advantage_and_crit(self):
        room, _ = self.clawed(hp=400)
        result = room.act('Con save 2')  # still paralyzed; the ghoul's turn comes round
        evidence = ' '.join(e.get('evidence', '') for e in result.events)
        self.assertIn('(advantage)', evidence)
        self.assertIn('crit 14', evidence)

    def test_a_duration_in_rounds_ticks_at_the_end_of_his_turn(self):
        room = Room(self, sheet='wren', roll=lambda: 2)
        open_tomb(room)
        room.act('Initiative 20')
        revision, _ = room.runtime.load()
        room.runtime.commit('p', revision, [{'type': 'pc_conditions', 'conditions': ['poisoned'],
                                             'terms': {'poisoned': {'rounds': 1}}, 'evidence': 'test'}])
        result = room.act('I hold my ground and wait.')
        self.assertEqual(room.state['pc_conditions'], [])
        self.assertIn('You are no longer poisoned.', result.public_event)

    def test_an_elf_shrugs_off_the_ghouls_paralysis(self):
        room, result = self.clawed('ilsevel')
        self.assertNotIn('paralyzed', room.state.get('pc_conditions') or [])

    def test_the_paralysis_wears_off_after_a_minute(self):
        room, _ = self.clawed()
        revision, _ = room.runtime.load()
        room.runtime.commit('gone', revision, [{'type': 'actor_status', 'actor': 'ghoul', 'status': 'fled',
                                                'evidence': 'test: the ghoul is gone'}])
        with self.assertRaises(PendingRuling):
            room.resolve('I walk to the arch.')
        result = room.act('I wait a minute.')
        self.assertNotIn('paralyzed', room.state.get('pc_conditions') or [])
        self.assertEqual(room.state['elapsed_seconds'], 60)
        self.assertIn('no longer paralyzed', result.public_event)

    def test_the_centipede_poison_ends_after_an_hour_and_he_comes_to(self):
        carcass = json.loads(CARCASS.read_text())
        room = Room(self, source=carcass, start='hall', sheet='nik', npc_roll=lambda: 1, roll=lambda: 15, hp=12)
        room.act('I roll the carcass over.', {'target': 'carcass', 'act': 'roll'})
        room.act('Initiative 1')
        room.act('Con save 3', downed='turn_away')
        self.assertEqual(room.fight['status'], 'over')
        self.assertEqual(room.state['pc_conditions'], ['unconscious', 'poisoned', 'paralyzed'])
        with self.assertRaisesRegex(PendingRuling, '1d4'):
            room.resolve('I wait.')
        result = room.act('I wait for the poison to wear off. 1d4: 2')
        self.assertEqual(room.state['pc_conditions'], [])
        self.assertFalse(room.fight.get('pc_down'))
        self.assertIn('You come to with 1 hit point.', result.public_event)
        self.assertEqual(room.state['elapsed_seconds'], 7200)


class SaveTieTests(unittest.TestCase):
    """Brendon (2026-10-04): the attacker must meet or beat the defender, so a save that ties
    the DC fails. A house rule over 5e, both ways. Death saves are not this rule."""

    def test_the_helper(self):
        attacker_wins = getattr(kit_rolls, 'attacker_wins', None)
        self.assertIsNotNone(attacker_wins, 'kit_rolls.attacker_wins')
        self.assertTrue(attacker_wins(10, 10))
        self.assertTrue(attacker_wins(10, 9))
        self.assertFalse(attacker_wins(10, 11))

    def test_the_pcs_save_against_the_ghouls_dc(self):
        for save, paralyzed in (('Con save 10', True), ('Con save 11', False), ('Con save 9', True)):
            with self.subTest(save=save):
                room = Room(self, sheet='wren', roll=lambda: 15)
                open_tomb(room)
                room.act('Initiative 1')
                room.act(save)
                self.assertEqual('paralyzed' in (room.state.get('pc_conditions') or []), paralyzed)

    def test_the_repeat_save_ties_fail_too(self):
        for save, still in (('Con save 10', True), ('Con save 11', False), ('Con save 9', True)):
            with self.subTest(save=save):
                room = Room(self, sheet='wren', roll=lambda: 15)
                open_tomb(room)
                room.act('Initiative 1')
                room.act('Con save 2')
                room.act(save)
                self.assertEqual('paralyzed' in (room.state.get('pc_conditions') or []), still)

    def test_a_monsters_save_against_the_pcs_spell_dc(self):
        # Nik's spell save DC 15; the ghoul's Wisdom save is d20 + 0.
        for die, saved in ((15, False), (16, True), (14, False)):
            with self.subTest(total=die):
                room = Room(self, sheet='nik', roll=lambda die=die: die)
                open_tomb(room)
                room.act('Initiative 20')
                room.act('I cast Toll the Dead at the hollow-eyed ghoul. 8 necrotic damage.')
                hurt = room.fight['hp']['ghoul'] < 22
                self.assertEqual(hurt, not saved)

    def test_avraes_tie_success_is_a_failure_here(self):
        for total, full in ((15, True), (16, False), (14, True)):
            with self.subTest(total=total):
                room = Room(self, sheet='nik', roll=lambda: 2)
                open_tomb(room)
                room.act('Initiative 20')
                verdict = 'Success!' if total >= 15 else 'Failure!'
                damage = 14 if total >= 15 else 28
                room.act('I cast Fireball at the hollow-eyed ghoul.\n'
                         'Nik casts Fireball!\n'
                         '**DC**: 15\n'
                         'Hollow-eyed ghoul\n'
                         f'**DEX Save**: 1d20 ({total - 2}) + 2 = `{total}`; {verdict}\n'
                         f'**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 3) [fire] = `{damage}`')
                taken = room.fight['max_hp']['ghoul'] - room.fight['hp']['ghoul']
                self.assertEqual(taken, 22 if full else 14)  # 28 caps at its 22 hit points

    def test_death_saves_keep_ten_or_more(self):
        room = Room(self, sheet='nik', roll=lambda: 15)
        open_tomb(room)
        room.wound(1)
        room.act('Initiative 1')
        room.act('Death save 10', downed='turn_away')
        self.assertEqual(room.fight['death_saves']['successes'], 1)


class RoutingAndActionCostTests(unittest.TestCase):
    def test_the_feature_named_first_is_the_one_meant(self):
        """P2: not file order."""
        room = Room(self)
        result = room.act('I look inside the chest beside the sarcophagus.')
        self.assertNotEqual(result.kind, 'feature_act', result)
        self.assertIn('Moth-eaten vestments', result.public_event)
        self.assertFalse(room.state.get('triggers_fired'))

    def fighting(self):
        room = Room(self, source=crypt(facts={'trapdoor': {'visible': True}}), roll=lambda: 2)
        room.act('I haul the trapdoor up.', {'target': 'trapdoor', 'act': 'lift'})
        room.act('Initiative 20')
        self.assertEqual(room.fight['status'], 'running')
        return room

    def test_heaving_a_lid_mid_fight_takes_his_action(self):
        room = self.fighting()
        result = room.act('I heave the lid aside.', {'target': 'lid', 'act': 'lift'})
        self.assertIn('That takes your action.', result.public_event)
        self.assertIn('tomb_opened', room.state['triggers_fired'])
        self.assertIn('ghoul', room.fight['order'])

    def test_a_light_touch_is_the_free_object_interaction(self):
        room = self.fighting()
        result = room.act('I tug at the seal.', {'target': 'seal', 'act': 'pull'})
        self.assertNotIn('That takes your action.', result.public_event)
        result = room.act('I tug at the lid.', {'target': 'lid', 'act': 'pull'}) \
            if 'sarcophagus' in kit_triggers.disturb_targets(room.runtime.source(), room.state) else result
        self.assertTrue(room.fight.get('interaction_used') or 'tomb_opened' in room.state.get('triggers_fired', []))


class FromScratchRoomTests(unittest.TestCase):
    def test_the_crypt_carries_real_srd_lines(self):
        from runtime import srd_creatures
        fighters = kit_combat.config(json.loads(CRYPT.read_text()))['actors']
        for key, name in (('ghoul', 'Ghoul'), ('skeleton', 'Skeleton'), ('sexton', 'Commoner')):
            with self.subTest(creature=name):
                cited = srd_creatures.stat_block({'srd': name})
                self.assertIsNotNone(cited, f'srd_creatures lists {name}')
                for field in ('ac', 'hp', 'initiative'):
                    self.assertEqual(fighters[key][field], cited[field])
                self.assertEqual([(a['to_hit'], a['damage']) for a in fighters[key]['attacks']],
                                 [(a['to_hit'], a['damage']) for a in cited['attacks']])
        self.assertEqual(fighters['ghoul']['attacks'][0]['save']['condition']['name'], 'paralyzed')

    def test_the_pcs_stealth_against_the_sextons_passive(self):
        """The PC-Stealth tie off 6c: the sexton's passive Perception is 10."""
        for total, unnoticed in ((10, True), (11, True), (9, False)):
            with self.subTest(total=total):
                room = Room(self, start='vestibule')
                result = room.resolve(f'I sneak toward the arch, Stealth {total}')
                self.assertEqual('unnoticed' in result.public_event, unnoticed, result.public_event)


if __name__ == '__main__':
    unittest.main()
