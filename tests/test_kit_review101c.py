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

from runtime import kit_reactions
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
ROOMS = ROOT / 'tests' / 'fixtures' / 'rooms'
NIK = json.loads((ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json').read_text())


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
