"""#101 re-review at 9200c42 (Nagatha, Oct 4): the P2s still open after the P1 work, on her
from-scratch Kiln, Shrine and Rope Bridge rooms (tests/fixtures/rooms). Never 6c; dice pinned."""
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import kit_due  # noqa: E402
from runtime import kit_combat, kit_reactions
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
ROOMS = ROOT / 'tests' / 'fixtures' / 'rooms'
NIK = json.loads((ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json').read_text())


def clause_parser(cls):
    """The word-matching clause splitter and confidence gate are off by default since the
    2026-10-13 architecture decision (Kit-declared acts replace them). These classes pin the
    flagged-off code's behaviour while it remains: run with CLAUSE_PARSER on."""
    return mock.patch.object(kit_combat, 'CLAUSE_PARSER', True)(cls)


def wizard(**extra):
    """Shield and slots, no Chronal Shift: windows offer Shield alone."""
    sheet = copy.deepcopy(NIK)
    sheet['features'] = [f for f in sheet['features'] if not f.startswith('Chronal Shift')]
    sheet.update(extra)
    return sheet


class Arena:
    def __init__(self, test, room, sheet=None, roll=lambda: 2):
        temp = tempfile.TemporaryDirectory()
        test.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        test.addCleanup(self.runtime.close)
        source = json.loads((ROOMS / f'{room}.json').read_text())
        with mock.patch('runtime.state_context.secrets.token_hex', return_value='7' * 32):
            self.runtime.initialize(source, source['starting_area'])
        self.sheet = copy.deepcopy(sheet or wizard())
        self.runtime.set_player_sheet(copy.deepcopy(self.sheet))
        self.adjudicator = RoomAdjudicator(roll=roll, source=self.runtime.source())
        self.test = test

    def act(self, action, **choice):
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(action, revision, state, choice=choice or None)
        self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    def held(self, action, **choice):
        revision, state = self.runtime.load()
        with self.test.assertRaises(PendingRuling) as caught:
            self.adjudicator.resolve(action, revision, state, choice=choice or None)
        return caught.exception

    @property
    def state(self):
        return self.runtime.load()[1]

    @property
    def fight(self):
        return self.state['combat']

    def slot1(self):
        return self.state['pc_resources']['slots']['1']['used']


KILN_OPEN = 'Initiative 25. I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.'  # a miss


class OwnTurnShield(unittest.TestCase):
    """A4/A5: Shield cast on his own turn is a cast, not 'outside combat' and not a weapon."""

    def kiln(self):
        arena = Arena(self, 'kiln')  # every foe rolls 2: all miss, no window
        arena.act(KILN_OPEN)
        self.assertIsNone(arena.fight.get('awaiting'))
        return arena

    def test_avrae_cast_shield_on_his_turn_counts_the_slot_and_does_nothing(self):
        # Shield is a reaction to a hit: with no hit it has no effect, but Avrae spent the slot.
        arena = self.kiln()
        result = arena.act('Nik casts Shield! (Avrae: !cast shield)')
        self.assertEqual(arena.slot1(), 1, 'the session matches Avrae')
        self.assertFalse(arena.fight.get('shield_up'))
        self.assertIn('does nothing', result.public_event)
        self.assertNotIn('outside combat', result.public_event)

    def test_a_late_shield_is_not_read_as_a_weapon_and_undoes_nothing(self):
        arena = Arena(self, 'kiln', roll=lambda: 10)  # the imp's spit is a 15: a hit, Shield offered
        arena.act(KILN_OPEN)
        self.assertEqual(arena.fight['awaiting']['options'], ['shield'])
        arena.act('No, let it hit.', react='decline')
        damage = arena.fight['pc_damage']
        self.assertGreater(damage, 0)
        result = arena.act('Wait, I cast Shield on that spit. !cast shield')
        self.assertNotIn('Roll the attack for your shield', result.public_event)
        self.assertIn('already landed', result.public_event)
        self.assertEqual(arena.fight['pc_damage'], damage, 'a Shield after the hit undoes nothing')


class UnclearCap(unittest.TestCase):
    """A7: Kit asks about a window she cannot read at most twice; the third unclear (or still
    uncast) answer is taken as a no and the round runs on."""

    def opened(self):
        arena = Arena(self, 'kiln', roll=lambda: 10)  # the imp's spit is a 15: Shield is offered
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        bridge.prepare(KILN_OPEN, 'v', one_pass=True)
        bridge.complete('v', {'decision': {'window': 'voiced'}, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': 'Your dagger skids off the slinger.'},
            {'speaker': 'Kit', 'text': 'The imp spits fire at you. Shield?'}]}})
        return arena, bridge

    def answer(self, bridge, turn, decision):
        bridge.prepare('Hmm, maybe?', turn, one_pass=True)
        return bridge.complete(turn, {'decision': {'react': decision}, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'Shield, or let it land?'}]}})

    def test_the_third_unclear_answer_is_taken_as_a_no(self):
        arena, bridge = self.opened()
        for turn in ('a1', 'a2'):
            self.assertTrue(self.answer(bridge, turn, {'choice': 'unclear'})['asked'])
        packet = self.answer(bridge, 'a3', {'choice': 'unclear'})
        self.assertEqual(packet['stage'], 'one_pass')
        self.assertTrue(packet['window_answered']['taken_as_no'])
        self.assertIn('taken as a no', arena.runtime.pending_kit_turn('a3')['body']['public_event'])

    def test_a_shield_never_cast_in_avrae_is_asked_twice_then_taken_as_a_no(self):
        arena, bridge = self.opened()
        for turn in ('b1', 'b2'):
            self.assertTrue(self.answer(bridge, turn, {'choice': 'shield', 'cast_in_avrae': False})['asked'])
        packet = self.answer(bridge, 'b3', {'choice': 'shield', 'cast_in_avrae': False})
        self.assertEqual(packet['stage'], 'one_pass')
        self.assertEqual(arena.slot1(), 0)


@clause_parser
class CombatMovement(unittest.TestCase):
    """D5/d1c: moving away ends engagement; a PC who left gets no opportunity-attack window."""

    def bridge(self):
        arena = Arena(self, 'rope_bridge', sheet=wizard(hp=200), roll=lambda: 2)
        arena.act('Initiative 25. I stab the bridge ogre with my dagger, 5 to hit, 3 piercing.')  # a miss
        self.assertIn('ogre', arena.fight['engaged'])
        return arena

    def test_stepping_back_provokes_and_breaks_contact(self):
        arena = self.bridge()
        result = arena.act('I step back 30 feet along the bridge, away from the ogre.')
        self.assertTrue(result.public_event.startswith('The bridge ogre swings as you go and misses. '
                                                      'You fall back out of reach.'), result.public_event)
        # The ogre closes again on its turn and swings: contact is new, not left over.
        self.assertIn('The bridge ogre attacks and misses.', result.public_event)

    def test_disengage_provokes_nothing(self):
        arena = self.bridge()
        result = arena.act('I disengage and back off from the ogre.')
        self.assertNotIn('as you go', result.public_event)
        self.assertIn('You fall back out of reach.', result.public_event)


class SlotsAcrossSheets(unittest.TestCase):
    """D7: re-sending the sheet does not refill spent slots; a rest does, through the CLI too."""

    def spent(self):
        arena = Arena(self, 'kiln')
        arena.act(KILN_OPEN)
        arena.act('Nik casts Shield! (Avrae: !cast shield)')
        self.assertEqual(arena.slot1(), 1)
        return arena

    def test_the_same_sheet_again_keeps_the_spent_slot(self):
        arena = self.spent()
        arena.runtime.set_player_sheet(copy.deepcopy(arena.sheet))
        self.assertEqual(arena.slot1(), 1)

    def test_an_edited_sheet_keeps_what_was_spent(self):
        arena = self.spent()
        arena.runtime.set_player_sheet(dict(copy.deepcopy(arena.sheet), hp=40))
        self.assertEqual(arena.slot1(), 1)

    def test_a_long_rest_on_the_cli_refills_it(self):
        arena = self.spent()
        arena.runtime.close()
        out = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'rest', '--kind', 'long',
                              '--db', str(arena.path)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        arena.runtime = Runtime(arena.path)
        self.addCleanup(arena.runtime.close)
        self.assertEqual(arena.slot1(), 0)


class SlotLevels(unittest.TestCase):
    def test_an_upcast_to_a_level_the_sheet_lacks_is_an_error_not_level_1(self):
        arena = Arena(self, 'kiln', roll=lambda: 10)
        arena.act(KILN_OPEN)
        ruling = arena.held('Nik casts Shield at 9th level!', react='shield', cast_in_avrae=True, slot_level=9)
        self.assertEqual(ruling.code, 'no_slot')
        self.assertEqual(arena.slot1(), 0)


class WindowVoiceContext(unittest.TestCase):
    """window_voice carries Kit's personality core and the scene she is narrating in."""

    def test_the_window_packet_has_core_and_scene(self):
        arena = Arena(self, 'kiln', roll=lambda: 10)
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        packet = bridge.prepare(KILN_OPEN, 'w1', one_pass=True)
        self.assertEqual(packet['stage'], 'window_voice')
        given = packet['input']
        self.assertTrue(given.get('personality_core'))
        self.assertIn('kiln', json.dumps(given.get('scene') or {}).casefold())
        self.assertLess(len(json.dumps(packet)), 6000)


class ReactionsReadySplit(unittest.TestCase):
    def test_the_window_turn_and_the_next_turn_share_the_session_manifest(self):
        arena = Arena(self, 'kiln', roll=lambda: 10)
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        from runtime import kit_manifest
        one = bridge.prepare('I look at the kiln.', 'a', one_pass=True)
        before = kit_manifest.digest(kit_manifest.split(one)[0])
        bridge.abandon('a')
        revision, state = arena.runtime.load()
        spent, _ = kit_reactions.spend(state['pc_resources'], 'shield')
        arena.runtime.commit('spend', revision, [{'type': 'pc_resources', 'resources': spent, 'evidence': 'test'}])
        two = bridge.prepare('I look at the shelves.', 'b', one_pass=True)
        self.assertEqual(before, kit_manifest.digest(kit_manifest.split(two)[0]))
        self.assertIn('L1 3/4', two['input']['private']['reactions_ready'])
        self.assertNotIn('3/4', two['input']['private']['available_reactions'])


class DirectedReveal(unittest.TestCase):
    """h_reveal: Kit cannot certify her own 'directed' entry. The held facts she calls relevant
    must be ones the player's own words point at."""

    def setUp(self):
        from runtime import kit_reveal, kit_rooms
        self.reveal_mod = kit_reveal
        self.src = kit_rooms.check_room(json.loads((ROOMS / 'kiln.json').read_text()))
        self.view = kit_reveal.view(self.src, {'area': 'kiln', 'room': {}, 'visited': []}, 'opening')
        self.assertIn('shelves', self.view['hold_ids'])
        self.segments = [{'speaker': 'Narrator', 'text': self.src['facts']['kiln']['text'] + ' ' +
                          self.src['facts']['shelves']['text']}]
        self.plan = {'reveal_entry': {'mode': 'directed', 'relevant': ['shelves']}}

    def test_a_directed_entry_the_player_never_directed_is_rejected(self):
        from runtime.state_context import InvalidChange
        with self.assertRaisesRegex(InvalidChange, 'did not point'):
            self.reveal_mod.check_spoken(self.view, self.segments, self.src, self.plan, action='I walk in.')

    def test_the_players_own_words_make_it_directed(self):
        self.reveal_mod.check_spoken(self.view, self.segments, self.src, self.plan,
                                     action='I walk in and go straight to the shelves.')


@clause_parser
class NeverDropAnAct(unittest.TestCase):
    """#101 review P1-3, the cases left at c8bf217: D1, D5 and d1c from Nagatha's probes."""

    def camp(self):
        from test_kit_combat_checkpoints import Camp, KILL_CAPTAIN, shield_only
        camp = Camp(self, sheet=shield_only())
        camp.act(KILL_CAPTAIN)
        self.assertEqual(camp.fight['awaiting']['kind'], 'flourish_window')
        return camp

    def test_d1_an_act_with_the_flourish_is_held_for_his_turn_and_kit_says_so(self):
        camp = self.camp()
        stab = 'I stab the wagon-side cutthroat with my dagger, 18 to hit, 20 piercing.'
        result = camp.act(stab, flourish='new_action')
        self.assertIn('already acted this turn', result.public_event)
        self.assertIn('stab the wagon-side cutthroat', camp.fight.get('declared_next') or '')

    def stay_and_fight(self):
        """The road camp with cutthroats who hold their ground when the captain falls."""
        from test_kit_combat_checkpoints import CAMP, Camp, shield_only
        source = json.loads(CAMP.read_text())
        for key in ('cutthroat_a', 'cutthroat_b'):
            source['combat']['actors'][key].pop('retreat')
        path = Path(tempfile.mkdtemp()) / 'camp.json'
        path.write_text(json.dumps(source))
        with mock.patch('test_kit_combat_checkpoints.CAMP', path):
            camp = Camp(self, sheet=wizard(hp=200), roll=lambda: 2)  # every foe misses
        camp.act('Initiative 25. I stab the bandit captain with my dagger, 18 to hit, 30 piercing.')
        self.assertEqual(camp.fight['awaiting']['kind'], 'flourish_window')
        return camp

    def test_d1_the_held_act_runs_when_his_turn_comes(self):
        camp = self.stay_and_fight()
        result = camp.act('I stab the fire-side cutthroat with my dagger, 18 to hit, 20 piercing.', flourish='new_action')
        self.assertIn('already acted this turn', result.public_event)
        self.assertIn('Your dagger hits the fire-side cutthroat', result.public_event,
                      'the round runs to his turn and the held stab lands there')
        self.assertLess(result.public_event.index('already acted'), result.public_event.index('Your dagger hits'))
        self.assertEqual(camp.state['actors']['cutthroat_b']['status'], 'dead')
        self.assertFalse(camp.fight.get('declared_next'))

    def test_d1_a_held_act_the_fight_outlasts_is_said_not_dropped(self):
        camp = self.camp()  # the cutthroats flee when the captain falls: the fight ends first
        result = camp.act('I stab the fire-side cutthroat with my dagger, 18 to hit, 20 piercing.', flourish='new_action')
        while (camp.fight.get('awaiting') or {}).get('kind') == 'reaction_window':
            result = camp.act('No.', react='decline')
        self.assertEqual(camp.fight['status'], 'over')
        self.assertFalse(camp.fight.get('declared_next'))
        self.assertIn('held act', result.public_event)

    def test_d1c_a_foe_he_has_run_from_gets_no_opportunity_window(self):
        camp = self.camp()
        camp.act("I grab the captain's purse and run for the road.", flourish='new_action')
        self.assertNotEqual((camp.fight.get('awaiting') or {}).get('trigger'), 'leaves_reach')

    def test_d5_step_back_and_fire_bolt_runs_the_move_then_the_attack(self):
        arena = Arena(self, 'rope_bridge', sheet=wizard(hp=200), roll=lambda: 2)
        arena.act('Initiative 25. I stab the bridge ogre with my dagger, 5 to hit, 3 piercing.')  # a miss
        result = arena.act('I back away 30 feet and cast Fire Bolt at the bridge ogre, 25 to hit, 9 fire.')
        text = result.public_event
        self.assertIn('swings as you go', text)
        self.assertIn('Your Fire Bolt hits', text)
        self.assertLess(text.index('swings as you go'), text.index('Your Fire Bolt hits'))
        # Hurt, the ogre flees; he is out of its reach, so no opportunity attack is offered.
        self.assertNotEqual((arena.fight.get('awaiting') or {}).get('trigger'), 'leaves_reach')


class HeldLayerWithheld(unittest.TestCase):
    """h_reveal: a paraphrase of the held layer slips past any word check, so on the entry turn Kit
    is never shown a held fact's text unless the player's own words point at it. What she was not
    shown she cannot paraphrase."""

    def entry(self, action):
        arena = Arena(self, 'kiln')
        source = json.loads((ROOMS / 'kiln.json').read_text())
        bridge = KitChatBridge(arena.runtime, arena.adjudicator)
        packet = bridge.prepare(action, 'e', one_pass=True, opening=action is None)
        return source, json.dumps(packet, ensure_ascii=False)

    def test_no_held_text_reaches_kit_on_the_entry(self):
        source, sent = self.entry(None)
        for key in ('shelves', 'soot'):
            self.assertNotIn(source['facts'][key]['text'], sent)
            self.assertNotIn(' '.join(source['facts'][key]['text'].split()[:4]), sent, 'not even its gist')
        self.assertIn(source['facts']['kiln']['text'], sent, 'the obvious layer is there')
        self.assertIn('shelves', sent, 'the held fact is named by id, so Kit knows something is held')

    def test_a_held_fact_the_player_points_at_is_given(self):
        from runtime import kit_reveal, kit_rooms
        src = kit_rooms.check_room(json.loads((ROOMS / 'kiln.json').read_text()))
        reveal = kit_reveal.view(src, {'area': 'kiln', 'room': {}, 'visited': []}, 'exit',
                                 action='I walk in and go straight to the shelves.')
        self.assertEqual(list(reveal['pointed']), ['shelves'])
        self.assertEqual(reveal['hold'], ['soot'])


if __name__ == '__main__':
    unittest.main()


EXAMPLE = json.loads((ROOT / 'tests' / 'fixtures' / 'characters' / 'example_pc.json').read_text())


def rogue(**extra):
    """Wren at level 5: Uncanny Dodge, no spells."""
    sheet = copy.deepcopy(EXAMPLE)
    sheet.update(level=5, hp=60, ac=15)
    sheet['features'] = sheet['features'] + ['Uncanny Dodge']
    sheet.update(extra)
    return sheet


def warlock(**extra):
    """A tiefling warlock: Hellish Rebuke, two pact slots, no Shield."""
    sheet = copy.deepcopy(EXAMPLE)
    sheet.update({'name': 'Sorrel', 'class': 'Warlock', 'level': 3, 'hp': 40, 'ac': 13, 'spell_save_dc': 13,
                  'features': ['Pact of the Blade'], 'spells': {'cantrips': ['Eldritch Blast'],
                                                                 '1': ['Hellish Rebuke', 'Hex']},
                  'slots': {'1': 2}})
    sheet.update(extra)
    return sheet


class PlayerMayDeclare(unittest.TestCase):
    """Nagatha #101 P2 (player agency): the 'worth it' threshold decides only whether Kit prompts.
    A reaction the hit makes legal is the player's to take when he says so, prompted or not."""

    def test_an_eligible_reaction_not_prompted_in_an_open_window_is_accepted(self):
        sheet = wizard(hp=60)
        sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
        arena = Arena(self, 'kiln', sheet=sheet, roll=lambda: 10)  # 15s: every attack hits
        arena.act(KILN_OPEN)
        waiting = arena.fight['awaiting']
        self.assertEqual(waiting['options'], ['shield'], 'the 7-point fire spit is not worth prompting Absorb at 60 hp')
        result = arena.act('Nik casts Absorb Elements! (Avrae: !cast absorb elements)',
                           react='absorb_elements', cast_in_avrae=True)
        self.assertIn('Absorb Elements: resistance to the fire', result.public_event)
        self.assertEqual(arena.fight['pc_damage'], 3 + 4, 'the fire spit halved, the sling lands')
        self.assertEqual(arena.slot1(), 1)

    def test_uncanny_dodge_declared_after_an_unprompted_hit_halves_it(self):
        arena = Arena(self, 'rope_bridge', sheet=rogue(), roll=lambda: 10)  # 16 hits AC 15
        arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')  # a miss
        self.assertIsNone(arena.fight.get('awaiting'), '13 of 60 hp: no prompt')
        self.assertEqual(arena.fight['pc_damage'], 13)
        result = arena.act('I Uncanny Dodge that greatclub hit.')
        self.assertIn('Uncanny Dodge: you take half, 6 instead of 13.', result.public_event)
        self.assertEqual(arena.fight['pc_damage'], 6)
        again = arena.act('Uncanny Dodge again!')
        self.assertEqual(arena.fight['pc_damage'], 6, 'one reaction for that round')
        self.assertIn('nothing to answer', again.public_event)

    def test_hellish_rebuke_declared_after_unprompted_damage_answers_the_named_attacker(self):
        arena = Arena(self, 'kiln', sheet=warlock(), roll=lambda: 10)  # imp 15, sling 15: both hit AC 13
        arena.act('Initiative 25. I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')
        self.assertIsNone(arena.fight.get('awaiting'), '7 and 4 of 40 hp: no prompt')
        held = arena.act('Hellish Rebuke on the ember imp!')
        self.assertIn('!cast hellish rebuke', held.public_event, 'a spell is cast in Avrae first')
        self.assertEqual(arena.slot1(), 0)
        result = arena.act('Hellish Rebuke on the ember imp! (Avrae: !cast hellish rebuke) 2d10 = 12 fire')
        self.assertIn('Hellish Rebuke: 12 fire damage to the ember imp.', result.public_event)
        self.assertEqual(arena.slot1(), 1)

    def test_a_reaction_the_hit_does_not_allow_is_still_refused(self):
        sheet = wizard(hp=200)
        sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
        arena = Arena(self, 'rope_bridge', sheet=without_shield(sheet), roll=lambda: 10)
        arena.act('Initiative 25. I stab the bridge ogre with my dagger, 5 to hit, 3 piercing.')
        result = arena.act('Nik casts Absorb Elements! (Avrae: !cast absorb elements)')
        self.assertIn('Absorb Elements has nothing to answer right now', result.public_event)
        self.assertEqual(arena.fight['pc_damage'], 13, 'a greatclub is not elemental damage')
        self.assertEqual(arena.slot1(), 1, 'the slot Avrae spent is counted, as with Shield')

    def test_the_claim_lapses_once_he_takes_his_turn(self):
        arena = Arena(self, 'rope_bridge', sheet=rogue(), roll=lambda: 10)
        arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
        arena.act('I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
        # Round 1's blow lapsed when he acted; only round 2's is his to answer.
        self.assertEqual(len(arena.fight['unprompted']), 1)
        arena.act('I Uncanny Dodge that greatclub hit.')
        self.assertEqual(arena.fight['pc_damage'], 13 + 6)


def without_shield(sheet):
    sheet = copy.deepcopy(sheet)
    sheet['spells'] = {level: [s for s in names if s != 'Shield'] for level, names in sheet['spells'].items()}
    return sheet


class LateRerollIsSaid(unittest.TestCase):
    def test_a_reroll_declared_after_the_hit_landed_changes_nothing_and_spends_nothing(self):
        sheet = rogue(spells={'1': ['Silvery Barbs']}, slots={'1': 2})
        arena = Arena(self, 'rope_bridge', sheet=sheet, roll=lambda: 10)
        arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
        result = arena.act('Silvery Barbs on the ogre! (Avrae: !cast silvery barbs)')
        self.assertIn('Silvery Barbs cannot change it now', result.public_event)
        self.assertEqual((arena.fight['pc_damage'], arena.slot1()), (13, 0))


@clause_parser
class LateReactionKeepsTheAct(unittest.TestCase):
    """Nagatha at 70c1612 (P1): a late reaction in the same message as his act resolves, then the
    rest of the message is his act; neither order drops the attack."""

    def bridge(self):
        arena = Arena(self, 'rope_bridge', sheet=rogue(), roll=lambda: 10)
        arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
        self.assertEqual(arena.fight['pc_damage'], 13)
        return arena

    def check(self, arena, text):
        result = arena.act(text)
        self.assertIn('Uncanny Dodge: you take half', result.public_event)
        self.assertIn('hits the bridge ogre', result.public_event)
        self.assertEqual(arena.fight['hp']['ogre'], 59 - 7)
        return result

    def test_dodge_then_attack(self):
        self.check(self.bridge(), 'I Uncanny Dodge that hit, then stab the bridge ogre with my rapier, '
                                  '18 to hit, 7 piercing.')

    def test_attack_then_dodge(self):
        self.check(self.bridge(), 'I stab the bridge ogre with my rapier, 18 to hit, 7 piercing, and Uncanny '
                                  'Dodge that greatclub hit.')

    def test_the_late_dodge_says_the_new_damage(self):
        result = self.bridge().act('I Uncanny Dodge that greatclub hit.')
        self.assertIn('Uncanny Dodge: you take half, 6 instead of 13.', result.public_event)

    def test_a_late_spell_uses_the_slot_avrae_cast_and_the_fire_bolt_still_flies(self):
        sheet = without_shield(wizard(hp=60))
        sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
        arena = Arena(self, 'kiln', sheet=sheet, roll=lambda: 10)
        arena.act(KILN_OPEN)
        self.assertIsNone(arena.fight.get('awaiting'))
        result = arena.act('I cast Absorb Elements at 2nd level (Avrae: !cast absorb elements -l 2), then Fire Bolt '
                           'the kobold slinger, 19 to hit, 8 fire.')
        self.assertIn('Absorb Elements: resistance to the fire', result.public_event)
        self.assertIn('Your Fire Bolt hits', result.public_event)
        slots = arena.state['pc_resources']['slots']
        self.assertEqual((slots['1']['used'], slots['2']['used']), (0, 1))


class SealedSubject(unittest.TestCase):
    """Nagatha at 70c1612 (P2): 'its lid' and 'the sarcophagus's lid' are the feature's part, and
    wear is description only when what wore is not the feature or its part."""
    CRYPT = {'names': ['coffin', 'handle', 'lid', 'sarcophagus', 'tomb'], 'parts': ['lid', 'handle'],
             'interior': [], 'contents': []}
    CHEST = {'names': ['chest', 'strongbox', 'lid', 'hasp'], 'parts': ['lid', 'hasp'], 'interior': [],
             'contents': []}

    def verdict(self, terms, text):
        from runtime.kit_agent import InvalidChange, check_sealed
        try:
            check_sealed(text, {'f': terms})
            return 'ok'
        except InvalidChange:
            return 'refused'

    def test_the_part_itself_coming_off_is_refused(self):
        for terms, text in [(self.CRYPT, 'Its lid is knocked off.'), (self.CRYPT, "The sarcophagus's lid is pried off."),
                            (self.CRYPT, "The sarcophagus's lid is broken off."), (self.CHEST, "The chest's hasp is pried off."),
                            (self.CRYPT, 'The lid is stripped off.'), (self.CRYPT, 'The lid has rotted away.'),
                            (self.CRYPT, 'The lid is peeled back.'), (self.CHEST, 'Its lid has been worn away.'),
                            (self.CRYPT, "The lid's handle is pried off and the lid follows.")]:
            self.assertEqual(self.verdict(terms, text), 'refused', text)

    def test_wear_on_something_else_is_description(self):
        for terms, text in [(self.CRYPT, "The knight's nose is broken off."),
                            (self.CRYPT, "The lid's carvings have crumbled away at the foot."),
                            (self.CRYPT, 'The stone handles have rusted away to stubs.'),
                            (self.CHEST, "The chest's paint has flaked off in strips."),
                            (self.CHEST, 'Its corners are chipped off and smoothed by hands.')]:
            self.assertEqual(self.verdict(terms, text), 'ok', text)


def clause_log(result):
    """The engine's per-clause record (in the turn's evidence): [(index, total, outcome)]."""
    import re as _re
    text = next((e.get('evidence', '') for e in result.events if 'clause 1/' in e.get('evidence', '')), '')
    return [(int(a), int(b), c) for a, b, c in _re.findall(r'clause (\d+)/(\d+): (resolved|refused)', text)]


def ud_bridge(test, sheet=None):
    arena = Arena(test, 'rope_bridge', sheet=sheet or rogue(), roll=lambda: 10)
    arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
    return arena


@clause_parser
class EveryClauseResolves(unittest.TestCase):
    """Nagatha FAILED f3e880e: fresh multi-clause messages. The message is split into all its
    clauses; reactions resolve, every other clause goes in order to the act and move parser, and
    no clause is silently dropped: each one resolves or gets a 'didn't happen because' line."""

    def test_stab_dodge_and_back_off(self):
        arena = ud_bridge(self)
        result = arena.act('I stab the bridge ogre with my rapier, 18 to hit, 7 piercing, Uncanny Dodge that '
                           'greatclub hit, and back off 10 feet.')
        self.assertEqual(arena.fight['hp']['ogre'], 52, 'the stab lands')
        self.assertIn('Uncanny Dodge: you take half', result.public_event)
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved'] * 3)

    def test_dodge_twice_then_stab(self):
        arena = ud_bridge(self)
        result = arena.act('I Uncanny Dodge that hit and Uncanny Dodge it again, then stab the bridge ogre with my '
                           'rapier, 18 to hit, 7 piercing.')
        self.assertEqual(arena.fight['hp']['ogre'], 52)
        self.assertIn("Uncanny Dodge again didn't happen because you have already used your reaction",
                      result.public_event)
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'refused', 'resolved'])

    def test_warlock_dodge_rebuke_stab(self):
        sheet = warlock(hp=60)
        arena = Arena(self, 'kiln', sheet=sheet, roll=lambda: 10)
        arena.act(KILN_OPEN)
        result = arena.act('I Uncanny Dodge that hit and Hellish Rebuke the ember imp (Avrae: !cast hellish rebuke) '
                           '2d10 = 12 fire, then stab the kobold slinger with my rapier, 18 to hit, 4 piercing.')
        text = result.public_event
        self.assertIn("Uncanny Dodge didn't happen because it is not on your sheet", text)
        self.assertIn('Hellish Rebuke: 12 fire damage to the ember imp.', text)
        self.assertEqual(arena.fight['hp']['archer'], 3)
        self.assertEqual(arena.slot1(), 1)

    def test_dodge_step_back_then_stab_keeps_the_move(self):
        arena = ud_bridge(self)
        result = arena.act('I Uncanny Dodge that hit, step back 5 feet, then stab the bridge ogre with my rapier, '
                           '18 to hit, 7 piercing.')
        text = result.public_event
        self.assertIn('lashes out as you go', text)
        # Since 92b86a6's review: 5 feet back is out of the ogre's reach, so the stab is refused, said.
        self.assertLess(text.index('lashes out as you go'), text.index("didn't happen because the bridge ogre is out"))

    def test_a_repeat_spell_reaction_charges_only_what_avrae_cast(self):
        sheet = without_shield(wizard(hp=60))
        sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
        arena = Arena(self, 'kiln', sheet=sheet, roll=lambda: 10)
        arena.act(KILN_OPEN)
        arena.act('Absorb Elements! (Avrae: !cast absorb elements -l 3)')
        slots = lambda: {k: v['used'] for k, v in arena.state['pc_resources']['slots'].items()}
        self.assertEqual(slots(), {'1': 0, '2': 0, '3': 1})
        arena.act('Absorb Elements again!')  # no Avrae cast: nothing charged
        self.assertEqual(slots(), {'1': 0, '2': 0, '3': 1})
        arena.act('Absorb Elements! (Avrae: !cast absorb elements -l 2)')  # Avrae cast it: counted at -l 2
        self.assertEqual(slots(), {'1': 0, '2': 1, '3': 1})


@clause_parser
class ClauseFuzz(unittest.TestCase):
    """Fresh clause combinations across sheets and rooms: the invariant holds for every one."""

    def setups(self):
        ae = without_shield(wizard(hp=60))
        ae['spells']['1'] = ae['spells']['1'] + ['Absorb Elements']
        rw = warlock(hp=60)
        rw['features'] = rw['features'] + ['Uncanny Dodge']
        return [
            ('rope_bridge', rogue(), 'Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.',
             ['I Uncanny Dodge that hit', 'Uncanny Dodge it again', 'step back 5 feet', 'back off 10 feet',
              'stab the bridge ogre with my rapier, 18 to hit, 7 piercing', 'I grab the bridge ogre',
              'Hellish Rebuke the ogre']),
            ('kiln', rw, KILN_OPEN,
             ['Uncanny Dodge that fire spit', 'Hellish Rebuke the ember imp (Avrae: !cast hellish rebuke) 2d10 = 12 fire',
              'stab the kobold slinger with my rapier, 18 to hit, 4 piercing', 'step back 5 feet',
              'Absorb Elements (Avrae: !cast absorb elements)']),
            ('kiln', ae, KILN_OPEN,
             ['I cast Absorb Elements (Avrae: !cast absorb elements -l 2)', 'Fire Bolt the kobold slinger, 19 to hit, 8 fire',
              'back off 10 feet', 'stab the ember imp with my dagger, 18 to hit, 4 piercing', 'Uncanny Dodge that hit']),
        ]

    def test_no_clause_is_silently_dropped(self):
        import itertools
        joins = [', ', ', then ', ' and ', '. ', '; ']
        checked = 0
        for room, sheet, opener, pool in self.setups():
            for n in (2, 3):
                for combo in itertools.permutations(pool, n):
                    if checked > 400:
                        break
                    join = joins[checked % len(joins)]
                    text = join.join(combo) + '.'
                    arena = Arena(self, room, sheet=sheet, roll=lambda: 10)
                    arena.act(opener)
                    try:
                        result = arena.act(text)
                    except PendingRuling as caught:
                        self.assertIn('No turn was committed', str(caught), text)
                        checked += 1
                        continue
                    log = clause_log(result)
                    self.assertEqual(len(log), n, f'{text!r}: {log}')
                    if any(c[2] == 'refused' for c in log):
                        self.assertIn("didn't happen because", result.public_event, text)
                    checked += 1
        self.assertGreater(checked, 100)


class SealedRemoval(unittest.TestCase):
    CRYPT = SealedSubject.CRYPT

    def test_worn_to_nothing_is_removal(self):
        for text in ['The lid has rusted away to nothing.', 'The lid has worn away to dust.',
                     'Its lid has crumbled away to ash.']:
            self.assertEqual(SealedSubject.verdict(self, self.CRYPT, text), 'refused', text)
        for text in ['The handles have rusted away to stubs.',
                     'The carvings on the lid have worn away to faint lines.', 'The lid is worn away to faint lines.']:
            self.assertEqual(SealedSubject.verdict(self, self.CRYPT, text), 'ok', text)


@clause_parser
class Review92(unittest.TestCase):
    """Nagatha FAILED 92b86a6: reach after moving, filler, Avrae pastes, grapple wording (P1s), and
    the cheap P2s. Rooms: rope bridge (rogue), kiln (warlock, Absorb wizard)."""

    def kiln(self, sheet):
        arena = Arena(self, 'kiln', sheet=sheet, roll=lambda: 10)
        arena.act(KILN_OPEN)
        return arena

    # P1-1: reach follows the clauses in order
    def test_a_melee_stab_after_backing_off_is_refused_with_a_reason(self):
        arena = ud_bridge(self)
        result = arena.act('I Uncanny Dodge that greatclub hit; I step back 5 feet; I stab the bridge ogre with my '
                           'rapier, 18 to hit, 7 piercing.')
        self.assertEqual(arena.fight['hp']['ogre'], 59)
        self.assertIn("didn't happen because the bridge ogre is out of your reach now", result.public_event)
        self.assertEqual([c[2] for c in clause_log(result)], ['resolved', 'resolved', 'refused'])

    def test_a_ranged_bolt_after_backing_off_still_flies(self):
        sheet = without_shield(wizard(hp=60))
        arena = self.kiln(sheet)
        arena.act('I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')  # in reach now
        result = arena.act('I back away 10 feet, then Fire Bolt the kobold slinger, 19 to hit, 8 fire.')
        self.assertIn('Your Fire Bolt hits', result.public_event)

    def test_closing_back_in_puts_him_in_reach(self):
        arena = ud_bridge(self)
        result = arena.act('I step back 5 feet, then I close in on the bridge ogre and stab it with my rapier, '
                           '18 to hit, 7 piercing.')
        self.assertEqual(arena.fight['hp']['ogre'], 52, result.public_event)

    # P1-2: filler is flavor
    def test_waiting_and_breathing_are_not_his_action(self):
        for text in ['I wait, and then I stab the bridge ogre with my rapier, 18 to hit, 7 piercing.',
                     'I pause, breathe, steady myself, then stab the bridge ogre with my rapier, 18 to hit, 7 piercing.']:
            arena = ud_bridge(self)
            result = arena.act(text)
            self.assertEqual(arena.fight['hp']['ogre'], 52, text)
            self.assertNotIn("didn't happen", result.public_event, text)

    # P1-3: pastes
    def test_lines_after_a_paste_are_new_clauses(self):
        arena = ud_bridge(self)
        result = arena.act('I stab the bridge ogre with my rapier.\n**Rapier**: 1d20+7 = 18 to hit; 7 piercing\n'
                           'then I back off 10 feet.')
        self.assertEqual(arena.fight['hp']['ogre'], 52)
        self.assertIn('You fall back out of reach.', result.public_event)
        self.assertEqual(len(clause_log(result)), 2)

    def test_a_pasted_rebuke_uses_its_target_and_damage(self):
        arena = self.kiln(warlock(hp=60))
        result = arena.act('I stab the kobold slinger with my dagger, 18 to hit, 3 piercing.\n'
                           '!cast hellish rebuke -t imp -l 1\nHellish Rebuke: 12 fire\nthen I back away 10 feet.')
        self.assertIn('Hellish Rebuke: 12 fire damage to the ember imp.', result.public_event)
        self.assertEqual(arena.fight['hp']['archer'], 4, 'the stab lands')
        self.assertEqual(arena.fight['hp']['imp'], 6)
        self.assertEqual(arena.slot1(), 1)
        self.assertEqual(len(clause_log(result)), 3)

    def test_a_leading_attacks_with_block_is_the_attack(self):
        arena = ud_bridge(self)
        result = arena.act('Nik attacks with a Rapier!\nTo Hit: 1d20 (11) + 7 = 18\nDamage: 7 piercing\n'
                           'and I Uncanny Dodge that hit.')
        self.assertEqual(arena.fight['hp']['ogre'], 52)
        self.assertIn('Uncanny Dodge: you take half', result.public_event)

    # P1-4: grapple wording
    def test_gripping_a_rope_and_glaring_is_no_grapple(self):
        arena = ud_bridge(self)
        result = arena.act('I grip the rope, heart pounding, and glare at the ogre.')
        self.assertNotIn('grip', result.public_event.replace('I grip', ''))
        self.assertNotIn('twists out of your', result.public_event)

    def test_grabbing_the_ogre_is_a_grapple(self):
        arena = ud_bridge(self)
        result = arena.act('I grab the bridge ogre by the arm, Athletics 9.')  # contested since rv5e
        self.assertIn('grip', result.public_event)

    # P2s
    def test_repeated_refusals_are_said_once(self):
        arena = self.kiln(warlock(hp=60))
        result = arena.act('I Hellish Rebuke the imp, Hellish Rebuke the slinger, then stab the slinger with my '
                           'dagger, 18 to hit, 3 piercing.')
        self.assertEqual(result.public_event.count("Hellish Rebuke didn't happen because"), 1)

    def test_two_moves_end_the_turn_like_one(self):
        arena = ud_bridge(self)
        result = arena.act('I back off 10 feet, then I back off another 10 feet.')
        self.assertTrue(result.public_event.rstrip().endswith('Your turn.'))
        self.assertEqual(arena.fight['round'], 3, 'the foes took their turn')

    def test_a_cast_reaction_that_does_nothing_counts_its_slot_and_fizzles(self):
        sheet = without_shield(wizard(hp=60))
        sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
        arena = self.kiln(sheet)
        arena.act('Absorb Elements! (Avrae: !cast absorb elements -l 1)')
        result = arena.act('Absorb Elements! (Avrae: !cast absorb elements -l 2)')
        self.assertNotIn('!g ss', result.public_event, 'no undo cue: the engine matches Avrae')
        self.assertIn('fizzles', result.public_event)
        self.assertEqual(arena.state['pc_resources']['slots']['2']['used'], 1)

    def test_a_second_reaction_already_cast_in_avrae_fizzles_and_counts(self):
        arena = self.kiln(warlock(hp=60))
        result = arena.act('Hellish Rebuke the ember imp (Avrae: !cast hellish rebuke) 2d10 = 12 fire, then Hellish '
                           'Rebuke the slinger (Avrae: !cast hellish rebuke) 2d10 = 9 fire.')
        self.assertIn('Hellish Rebuke: 12 fire damage to the ember imp.', result.public_event)
        self.assertIn('fizzles', result.public_event)
        self.assertEqual(arena.slot1(), 2, 'both casts Avrae made are counted')
        self.assertEqual(arena.fight['hp']['archer'], 7, 'the second does nothing')

    def test_an_off_sheet_reaction_cast_in_avrae_fizzles_and_counts(self):
        arena = self.kiln(without_shield(wizard(hp=60)))  # no Absorb Elements on this sheet
        result = arena.act('Absorb Elements (Avrae: !cast absorb elements -l 1), then Fire Bolt the kobold slinger, '
                           '19 to hit, 8 fire.')
        self.assertIn("Absorb Elements didn't happen because it is not on your sheet", result.public_event)
        self.assertIn('fizzles', result.public_event)
        self.assertEqual(arena.slot1(), 1)

    def test_an_illegal_reaction_not_yet_cast_is_refused_before_the_cast(self):
        arena = self.kiln(warlock(hp=60))
        result = arena.act('Hellish Rebuke the ember imp (Avrae: !cast hellish rebuke) 2d10 = 12 fire, then Hellish '
                           'Rebuke the slinger.')
        self.assertNotIn('cast in Avrae first', result.public_event, 'never ask for a cast that cannot happen')
        self.assertIn('you have already used your reaction', result.public_event)
        self.assertEqual(arena.slot1(), 1)

    def test_absorb_elements_after_his_own_act_lapses(self):
        sheet = without_shield(wizard(hp=60))
        sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
        arena = self.kiln(sheet)
        result = arena.act('Fire Bolt the slinger, 19 to hit, 8 fire, then Absorb Elements (Avrae: !cast absorb '
                           'elements -l 1).')
        self.assertIn("Absorb Elements didn't happen because", result.public_event)
        self.assertNotIn('resistance to the fire', result.public_event)

    def test_stab_and_stab_uses_his_weapon(self):
        arena = ud_bridge(self)
        try:
            result = arena.act('I Uncanny Dodge that hit, and I stab, and I stab, and I back off.')
            text = result.public_event
        except PendingRuling as caught:
            text = str(caught)
        self.assertNotIn('unarmed', text)

    def test_shield_myself_without_shield_is_refused_not_a_bash(self):
        arena = ud_bridge(self)
        result = arena.act('I Shield myself and stab the bridge ogre with my rapier, 18 to hit, 7 piercing.')
        self.assertNotIn('Your shield hits', result.public_event)
        self.assertIn("Shield didn't happen because it is not on your sheet", result.public_event)
        self.assertEqual(arena.fight['hp']['ogre'], 52)

    def test_an_unresolvable_clause_is_said_in_kits_voice(self):
        from runtime import kit_combat
        self.assertNotIn('the engine', kit_combat.UNRESOLVED)


@clause_parser
class ClauseFuzzWide(unittest.TestCase):
    """Widened: pastes, filler, reach after moving, grip and glare wording, across sheets and rooms."""

    def test_every_clause_is_recorded_and_refusals_are_voiced(self):
        import itertools
        rb = ['I Uncanny Dodge that hit', 'step back 5 feet', 'stab the bridge ogre with my rapier, 18 to hit, 7 piercing',
              'I wait', 'I breathe', 'I grip the rope', 'I glare at the ogre', 'I close in on the bridge ogre',
              'I stab the bridge ogre with my rapier.\n**Rapier**: 1d20+7 = 18 to hit; 7 piercing\n']
        wl = ['Hellish Rebuke the ember imp (Avrae: !cast hellish rebuke) 2d10 = 12 fire',
              '!cast hellish rebuke -t imp -l 1\nHellish Rebuke: 12 fire\n',
              'stab the kobold slinger with my dagger, 18 to hit, 3 piercing', 'I pause', 'back away 10 feet',
              'I steady myself']
        joins = [', ', ', then ', ' and ', '. ', '; ', '\n']
        setups = [('rope_bridge', rogue(), 'Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.', rb),
                  ('kiln', warlock(hp=60), KILN_OPEN, wl)]
        checked = 0
        for room, sheet, opener, pool in setups:
            for combo in itertools.permutations(pool, 3):
                join = joins[checked % len(joins)]
                text = join.join(c.strip('\n') if not c.endswith('\n') else c for c in combo).replace('\n' + join, '\n')
                arena = Arena(self, room, sheet=sheet, roll=lambda: 10)
                arena.act(opener)
                try:
                    result = arena.act(text)
                except PendingRuling as caught:
                    self.assertIn('No turn was committed', str(caught), text)
                    checked += 1
                    continue
                log = clause_log(result)
                if log:
                    self.assertEqual(sorted({c[1] for c in log}), [len(log)], text)
                    if any(c[2] == 'refused' for c in log):
                        self.assertIn("didn't happen because", result.public_event, text)
                self.assertNotIn('twists out of your grip', result.public_event, text)
                checked += 1
        self.assertGreater(checked, 300)


def ruling_of(test, arena, text):
    """The pending ruling a message becomes (nothing committed), with its clause record."""
    revision, state = arena.runtime.load()
    with test.assertRaises(PendingRuling) as caught:
        arena.adjudicator.resolve(text, revision, state)
    from runtime.kit_agent import pending_ruling_result
    return caught.exception, pending_ruling_result(caught.exception)


@clause_parser
class Review5d(unittest.TestCase):
    """Nagatha FAILED 5dd307f. The engine commits only a clause it reads with high confidence (a
    known combat verb, a resolved target, a legal action); any other deed is a pending ruling for
    Kit's call, recorded as 'ruling'. Nothing in that message commits until it is ruled on."""

    def kiln(self, sheet):
        arena = Arena(self, 'kiln', sheet=sheet, roll=lambda: 10)
        arena.act(KILN_OPEN)
        return arena

    def test_a_thrown_dagger_after_backing_off_flies(self):
        arena = ud_bridge(self, rogue(gear=['rapier', 'dagger', 'shortbow']))
        result = arena.act('I step back 5 feet, then throw a dagger at the bridge ogre, 15 to hit, 4 piercing.')
        self.assertEqual(arena.fight['hp']['ogre'], 55, result.public_event)

    def test_pushing_a_shelf_onto_a_foe_and_yanking_a_sling_are_rulings(self):
        sheet = without_shield(wizard(hp=60))
        for text in ['I push the shelf over onto the slinger.', "I grip the slinger's sling and yank it away.",
                     'I shove the ember imp into the kiln.']:
            arena = self.kiln(sheet)
            before = copy.deepcopy(arena.fight)
            exc, shown = ruling_of(self, arena, text)
            self.assertEqual(arena.fight, before, text)
            self.assertNotIn('twists out of your', shown['player_message'], text)
            self.assertIn('ruling', [c['outcome'] for c in shown['clauses']], text)

    def test_it_binds_to_the_creature_just_named(self):
        sheet = without_shield(wizard(hp=60))
        arena = self.kiln(sheet)
        arena.act('I step up to the imp and stab it with my dagger, 15 to hit, 3 piercing.')
        self.assertEqual(arena.fight['hp']['imp'], 15)
        self.assertEqual(arena.fight['hp']['archer'], 7)

    def test_a_late_absorb_cast_after_he_acted_fizzles_and_counts(self):
        sheet = without_shield(wizard(hp=60))
        sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
        arena = self.kiln(sheet)
        result = arena.act('Fire Bolt the imp, 17 to hit, 7 fire, and Absorb Elements (Avrae: !cast absorb elements -l 1).')
        self.assertIn('fizzles', result.public_event)
        self.assertEqual(arena.slot1(), 1)

    def test_a_door_clause_is_a_ruling_with_a_record(self):
        arena = self.kiln(warlock(hp=60))
        exc, shown = ruling_of(self, arena, 'I push the kiln door shut, then stab the kobold slinger with my dagger, '
                                            '16 to hit, 3 piercing.')
        self.assertEqual([c['outcome'] for c in shown['clauses']], ['ruling', 'waits'])
        self.assertIn('push the kiln door shut', shown['player_message'])
        self.assertNotRegex(shown['player_message'], r'engine|slice|committed')
        self.assertEqual(arena.fight['hp']['archer'], 7)

    def test_cutting_the_rope_is_a_ruling(self):
        arena = ud_bridge(self)
        exc, shown = ruling_of(self, arena, 'I cut the bridge rope behind the ogre.')
        self.assertEqual([c['outcome'] for c in shown['clauses']], ['ruling'])

    def test_an_off_hand_stab_is_his_bonus_action(self):
        sheet = without_shield(wizard(hp=60))
        arena = self.kiln(sheet)
        result = arena.act('I stab the kobold slinger with my dagger, 18 to hit, 3 piercing, and with my off-hand '
                           'dagger I stab the ember imp, 15 to hit, 2 piercing.')
        self.assertEqual((arena.fight['hp']['archer'], arena.fight['hp']['imp']), (4, 16), result.public_event)

    def test_a_single_act_gets_a_clause_record(self):
        arena = ud_bridge(self)
        result = arena.act('I stab the bridge ogre with my rapier, 16 to hit, 5 piercing.')
        self.assertEqual(clause_log(result), [(1, 1, 'resolved')])


@clause_parser
class HighConfidenceFuzz(unittest.TestCase):
    """Property: a clause outside the high-confidence set (object and environment deeds, shoves,
    yanks, cuts at things) is never committed as an engine act."""

    def test_no_low_confidence_clause_is_ever_committed(self):
        import itertools
        deeds = ['I push the shelf over onto the slinger', 'I yank the sling away', 'I shove the ember imp into the kiln',
                 'I push the kiln door shut', 'I kick the bellows at the imp', 'I cut the bellows strap',
                 'I take the poker from the rack', 'I shove the kobold slinger']
        acts = ['stab the kobold slinger with my dagger, 18 to hit, 3 piercing', 'I step back 5 feet',
                'Fire Bolt the imp, 17 to hit, 7 fire', 'I grin', 'I wait']
        checked = 0
        sheet = without_shield(wizard(hp=60))
        for deed, act, order in itertools.product(deeds, acts, (0, 1)):
            text = (f'{deed}, then {act}.' if order else f'{act}, then {deed}.')
            arena = self.kiln_arena(sheet)
            before = (copy.deepcopy(arena.fight), copy.deepcopy(arena.state['pc_resources']))
            exc, shown = ruling_of(self, arena, text)
            self.assertEqual((arena.fight, arena.state['pc_resources']), before, text)
            self.assertIn('ruling', [c['outcome'] for c in shown['clauses']], text)
            checked += 1
        self.assertGreaterEqual(checked, 80)

    def kiln_arena(self, sheet):
        arena = Arena(self, 'kiln', sheet=sheet, roll=lambda: 10)
        arena.act(KILN_OPEN)
        return arena


class FlourishOffByDefault(unittest.TestCase):
    """Nagatha at d0e533e: the flourish window ran by default and stalled play. It is behind the
    off-by-default flag; a kill now plays on exactly as on main (rv92 #35, /tmp/rvt x.txt)."""

    def kiln(self):
        arena = Arena(self, 'kiln', sheet=warlock(hp=60), roll=lambda: 10)
        arena.act(KILN_OPEN)
        return arena

    def test_killing_the_imp_runs_the_round_and_the_slinger_flees(self):
        arena = self.kiln()
        result = arena.act('I stab the imp with my dagger, 18 to hit, 20 piercing.')
        self.assertIn('The ember imp goes down and does not get up.', result.public_event)
        # The round ran on: the slinger's turn came and it runs (main: it flees; #101 keeps the
        # opportunity attack its leaving reach offers, a reaction window, voiced).
        self.assertIn('The kobold slinger breaks away, leaving your reach.', result.public_event)
        self.assertNotEqual((arena.fight.get('awaiting') or {}).get('kind'), 'flourish_window')

    def test_the_next_message_is_a_normal_act_not_a_flourish_answer(self):
        arena = Arena(self, 'rope_bridge', sheet=rogue(), roll=lambda: 10)
        arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
        arena.act('I stab the bridge ogre with my rapier, 25 to hit, 50 piercing.')
        self.assertNotEqual(((arena.fight or {}).get('awaiting') or {}).get('kind'), 'flourish_window')

    def test_rv92_35_rebuke_then_stab(self):
        arena = self.kiln()
        result = arena.act('I cast Hellish Rebuke on the imp at 2nd level, 15 fire, then stab the slinger with my '
                           'dagger, 18 to hit, 3 piercing.')
        self.assertNotEqual((arena.fight.get('awaiting') or {}).get('kind'), 'flourish_window', result.public_event)
        self.assertIn('breaks away', result.public_event)


class VoicedNothingHappens(unittest.TestCase):
    """Nagatha at 35fac3b, before the playtest: an act that changes nothing is said, never echoed
    as table talk or dropped in silence."""

    def test_an_attack_once_the_fight_is_over_is_voiced(self):
        arena = Arena(self, 'rope_bridge', sheet=rogue(), roll=lambda: 10)
        arena.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
        arena.act('I stab the bridge ogre with my rapier, 25 to hit, 80 piercing.')
        self.assertEqual(arena.fight['status'], 'over')
        before = arena.state
        result = arena.act('I stab the bridge ogre with my rapier, 17 to hit, 6 piercing.')
        self.assertIn("There's nobody left to hit.", result.public_event)
        self.assertNotIn('You declare', result.public_event)
        self.assertEqual(arena.fight, before['combat'])

    def test_a_decline_with_an_act_after_the_fight_ends_voids_it_out_loud(self):
        arena = Arena(self, 'kiln', sheet=warlock(hp=60), roll=lambda: 10)
        arena.act(KILN_OPEN)
        arena.act('I stab the imp with my dagger, 18 to hit, 20 piercing.')
        self.assertEqual(arena.fight['awaiting']['trigger'], 'leaves_reach')
        result = arena.act('I let it go and cast Hex on the slinger', react='decline')
        self.assertEqual(arena.fight['status'], 'over')
        self.assertIn('The fight is over before your held act comes up, so it does not happen.', result.public_event)


class AbsorbUpcast(unittest.TestCase):
    """Nagatha's playtest at 02e1c4f: an upcast Absorb Elements always said 1d6. SRD: 1d6 per
    slot level (-l 2 is 2d6)."""

    def sheet(self, **extra):
        sheet = without_shield(wizard(**extra))
        sheet['spells']['1'] = sheet['spells']['1'] + ['Absorb Elements']
        return sheet

    def test_declared_after_the_hit_scales_with_the_slot(self):
        for level in (1, 2, 3):
            with self.subTest(level=level):
                arena = Arena(self, 'kiln', sheet=self.sheet(hp=60), roll=lambda: 10)
                arena.act(KILN_OPEN)
                result = arena.act(f'Absorb Elements (Avrae: !cast absorb elements -l {level})')
                self.assertIn(f'your next melee hit adds {level}d6 fire', result.public_event)
                self.assertEqual(arena.fight['absorb_bonus']['dice'], f'{level}d6')
                self.assertEqual(arena.state['pc_resources']['slots'][str(level)]['used'], 1)

    def test_taken_in_the_window_scales_with_the_slot(self):
        for level in (1, 2, 3):
            with self.subTest(level=level):
                arena = Arena(self, 'kiln', sheet=self.sheet(hp=12), roll=lambda: 10)
                arena.act(KILN_OPEN)
                self.assertIn('absorb_elements', (arena.fight.get('awaiting') or {}).get('options', ()))
                result = arena.act(f'Absorb Elements (Avrae: !cast absorb elements -l {level})',
                                   react='absorb_elements', cast_in_avrae=True, slot_level=level)
                self.assertIn(f'your next melee hit adds {level}d6 fire', result.public_event)
                self.assertEqual(arena.fight['absorb_bonus']['dice'], f'{level}d6')


class KitTwoPlaytest(unittest.TestCase):
    """Nagatha's Kit II playtest at e5e11bf: the merge blockers, each pinned before its fix."""

    def test_two_mentions_of_one_door_are_one_entry(self):
        # Snapshot b8 ('shoves the door open ... steps through the door'): on main he ends in the
        # hall; the second mention walked him back out. Only a different exit is a second move.
        arena = Arena(self, 'watchroom', sheet=wizard(), roll=lambda: 10)
        result = arena.act('I shove the iron door open with my staff and step through the iron door into the room, '
                           'light held high.')
        self.assertEqual(arena.state['area'], 'watchroom')
        self.assertEqual(result.public_event.count('You go through'), 1, result.public_event)

    def test_a_question_after_the_kill_is_not_a_voided_act(self):
        arena = Arena(self, 'kiln', sheet=warlock(hp=60), roll=lambda: 10)
        arena.act(KILN_OPEN)
        arena.act('I stab the imp with my dagger, 18 to hit, 20 piercing.')
        result = arena.act("No, let it go. What's left standing, and did the slinger get away?", react='decline')
        self.assertNotIn('held act', result.public_event)
        self.assertNotIn('does not happen', result.public_event)

    def test_no_reroll_window_when_half_damage_already_kills(self):
        from test_kit_reactions import SYNTHETIC
        from test_kit_combat_checkpoints import Camp, rolls
        sheet = copy.deepcopy(SYNTHETIC)
        sheet['spell_save_dc'] = 15
        # The captain saves (18), but half of 70 is 35 against his 30: failing changes nothing.
        camp = Camp(self, sheet=sheet, roll=rolls(3, 3, 18, 3, then=2))
        camp.act('Initiative 25. I cast Fireball at the bandit captain, 70 fire damage.')
        self.assertNotEqual((camp.fight.get('awaiting') or {}).get('trigger'), 'npc_save')
        self.assertEqual(camp.fight['hp']['harl'], 0)

    def chronurgist(self, hp):
        sheet = without_shield(copy.deepcopy(NIK))
        sheet['hp'] = hp
        return sheet

    def test_chronal_shift_is_offered_by_the_hit_points_he_has_left(self):
        # 60 hp, 33 already taken: the imp's 7 is over a quarter of the 27 left. Legal and worth it,
        # so it is prompted, not skipped in silence (the sheet maximum alone said it was small).
        arena = Arena(self, 'kiln', sheet=self.chronurgist(60), roll=lambda: 10)
        arena.act(KILN_OPEN)
        for _ in range(2):
            arena.act('I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')
        self.assertEqual(arena.fight['pc_damage'], 33)
        arena.act('I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')
        self.assertEqual((arena.fight.get('awaiting') or {}).get('options'), ['chronal_shift'])

    def test_the_player_hears_his_reaction_is_spent(self):
        from test_kit_combat_checkpoints import Camp, OPEN, rolls
        camp = Camp(self, roll=rolls(10, 2), sheet=dict(copy.deepcopy(NIK), hp=24))
        camp.act(OPEN)
        result = camp.act('Chronal Shift: reroll that.', react='chronal_shift')
        self.assertIn('Your reaction is already spent this round', result.public_event)

    def test_the_rewind_is_told_before_the_blows_that_follow(self):
        from runtime.kit_agent import KitChatBridge
        from test_kit_combat_checkpoints import Camp, OPEN, rolls
        from test_kit_handoffs import answer, plan_for, voice
        camp = Camp(self, roll=rolls(10, 2), sheet=dict(copy.deepcopy(NIK), hp=24))
        bridge = KitChatBridge(camp.runtime, camp.adjudicator)
        bridge.prepare(OPEN, 'h1', one_pass=True)
        voice(bridge, 'h1')
        packet = answer(bridge, 'h2', 'Chronal Shift: reroll that.', {'react': 'chronal_shift'})
        plan = plan_for(packet, turn_mode='combat')
        plan['public_brief'].update(reply_to='reroll that', scope='call')
        rewind = 'Time hiccups. The scimitar swing never happens, and the steel goes wide past your ear.'
        out = bridge.complete('h2', {'decision': plan, 'performance': {'segments': kit_due.asked(packet, [
            {'speaker': 'Narrator', 'text': rewind}])}})
        lines = out['spoken'].split('\n')
        self.assertEqual(lines[0], f'Narrator: {rewind}')
        self.assertIn('hits you', lines[1])


class OneSlotPerCast(unittest.TestCase):
    """Nagatha's playtest at de764f3 (r29): an upcast spell whose damage comes on its own line spent a
    level 1 slot on the cast and another on the damage. One slot, at the cast's level, once. The
    state is built at runtime in the synthetic kiln (no playtest snapshot: those hold book rooms)."""

    CASES = (
        # (the cast, its separate damage line, the slots used after: {level: used})
        ('Initiative 25. I cast Magic Missile at the ember imp at 2nd level (!cast magic missile -l 2).',
         'Magic Missile damage: 4d4 (3, 2, 4, 1) + 4 = 14 force', {'1': 0, '2': 1, '3': 0}),
        ('Initiative 25. I cast Magic Missile at the ember imp (!cast magic missile).',
         'Magic Missile damage: 3d4 (3, 2, 4) + 3 = 12 force', {'1': 1, '2': 0, '3': 0}),
        ('Initiative 25. I cast Witch Bolt at the ember imp at 2nd level (!cast witch bolt -l 2). 15 to hit.',
         'Witch Bolt damage: 2d12 (5, 6) = 11 lightning', {'1': 0, '2': 1, '3': 0}),
        ('Initiative 25. I cast Mind Spike at the ember imp at 3rd level (!cast mind spike -l 3).',
         'Mind Spike damage: 4d8 (1, 2, 3, 4) = 10 psychic', {'1': 0, '2': 0, '3': 1}),
    )

    def used(self, arena):
        return {level: slot['used'] for level, slot in arena.state['pc_resources']['slots'].items()}

    def test_the_cast_level_is_spent_once_across_the_damage_line(self):
        for cast, damage, expected in self.CASES:
            for answer_window in (True, False):
                with self.subTest(cast=cast, answer_window=answer_window):
                    arena = Arena(self, 'kiln', sheet=wizard(hp=60), roll=lambda: 10)
                    arena.act(cast)
                    if answer_window and arena.fight.get('awaiting'):
                        arena.act('No reaction.', react='decline')
                    elif arena.fight.get('awaiting'):
                        arena.act('No.', react='decline')
                    arena.act(damage)
                    self.assertEqual(self.used(arena), expected)
                    self.assertLess(arena.fight['hp']['imp'], arena.fight['max_hp']['imp'], 'the damage landed')


class CastLevelPhrasings(unittest.TestCase):
    """Nagatha at d60fbbf: the cast level in the player's own words, anywhere in the clause; Avrae's
    -l N wins when both appear; unrelated numbers are not a level."""

    def test_the_level_is_read_from_the_players_phrasing(self):
        from runtime.kit_combat import cast_level
        for text, level in (
                ('Nik casts Magic Missile at the flameskull, 2nd level, all four darts at it.', 2),
                ('Magic Missile, level 2', 2),
                ('I upcast to 2nd', 2),
                ('I upcast it to 3rd level', 3),
                ('2nd-level Magic Missile at the imp', 2),
                ('Magic Missile at third level', 3),
                ('!cast magic missile -l 2', 2),
                ('at 2nd level (!cast absorb elements -l 3)', 3),  # Avrae's cast is the truth
                ('Magic Missile at 3rd level, all three darts (!cast magic missile -l 2)', 2),
                ('a level 2 slot', 2)):
            with self.subTest(text=text):
                self.assertEqual(cast_level(text), level)

    def test_unrelated_numbers_are_not_a_level(self):
        from runtime.kit_combat import cast_level
        for text in ('I cast Magic Missile at the imp on level 2 of the tower.',
                     'the 2nd dart goes at the slinger',
                     'I cast Magic Missile at the 2nd imp.',
                     'I climb to the 3rd level of the tower and cast Magic Missile.',
                     'Magic Missile damage: 4d4 (4, 1, 1, 4) + 4 = 14 force',
                     'Initiative 14. I cast Magic Missile at the imp.'):
            with self.subTest(text=text):
                self.assertIsNone(cast_level(text))

    def test_a_worded_upcast_spends_its_level(self):
        arena = Arena(self, 'kiln', sheet=wizard(hp=60), roll=lambda: 10)
        arena.act('Initiative 25. Nik casts Magic Missile at the ember imp, 2nd level, all four darts at it.')
        slots = arena.state['pc_resources']['slots']
        self.assertEqual((slots['1']['used'], slots['2']['used']), (0, 1))

    def test_the_auto_hit_damage_line_still_says_it_hits(self):
        # Main and de764f3 say 'Your Magic Missile hits the X.' on the damage line; d60fbbf dropped it.
        arena = Arena(self, 'kiln', sheet=wizard(hp=60), roll=lambda: 10)
        arena.act('Initiative 25. I cast Magic Missile at the ember imp (!cast magic missile).')
        if arena.fight.get('awaiting'):
            arena.act('No reaction.', react='decline')
        result = arena.act('Magic Missile damage: 3d4 (3, 2, 4) + 3 = 12 force')
        self.assertIn('Your Magic Missile hits the ember imp.', result.public_event)


class LateReactionPopsOnlyItsOwnEvent(unittest.TestCase):
    """Brendon's plan (2026-10-14): a late reaction answers one unprompted event; the others the
    round made legal stay in the queue until he takes his own turn. Dice pinned (all 10s)."""

    def test_rebuking_the_imp_leaves_the_sling_hit_queued(self):
        arena = Arena(self, 'kiln', sheet=warlock(), roll=lambda: 10)  # imp and sling both hit AC 13
        arena.act('Initiative 25. I stab the kobold slinger with my dagger, 5 to hit, 3 piercing.')
        before = arena.fight['unprompted']
        self.assertEqual(len(before), 2, 'the fire spit and the sling stone, neither prompted')
        result = arena.act('Hellish Rebuke on the ember imp! (Avrae: !cast hellish rebuke) 2d10 = 12 fire')
        self.assertIn('Hellish Rebuke: 12 fire damage to the ember imp.', result.public_event)
        left = arena.fight.get('unprompted') or []
        self.assertEqual(len(left), 1, 'only the answered event leaves the queue')
        self.assertNotEqual(left[0].get('attacker'), 'imp')


class NoSlotLeftFizzles(unittest.TestCase):
    """Brendon's plan (2026-10-14): a leveled spell cast with no slot left by the count fizzles: it
    has no effect, the turn is still spent, and it says so. Dice pinned (all 10s)."""

    CASTS = (
        'Initiative 25. I cast Magic Missile at the ember imp (!cast magic missile) 3d4 (3, 2, 4) + 3 = 12 force',
        'Initiative 25. I cast Mind Spike at the ember imp at 2nd level (!cast mind spike -l 2). 3d8 (5, 8, 7) = 20 psychic',
    )

    def test_a_cast_with_every_slot_spent_fizzles_and_counts(self):
        for cast in self.CASTS:
            with self.subTest(cast=cast):
                arena = Arena(self, 'kiln', sheet=wizard(hp=60), roll=lambda: 10)
                revision, state = arena.runtime.load()
                resources = copy.deepcopy(state['pc_resources'])
                for slot in resources['slots'].values():
                    slot['used'] = slot['max']
                arena.runtime.commit('spent', revision, [{'type': 'pc_resources', 'resources': resources, 'evidence': 'every slot spent (test setup)'}])
                full = {k: s['used'] for k, s in arena.state['pc_resources']['slots'].items()}
                result = arena.act(cast)
                self.assertIn('fizzles', result.public_event)
                self.assertEqual(arena.fight['hp']['imp'], arena.fight['max_hp']['imp'], 'no effect')
                self.assertEqual({k: s['used'] for k, s in arena.state['pc_resources']['slots'].items()}, full)
                self.assertFalse((arena.fight.get('pending') or {}).get('needs'), 'no roll asked for')
