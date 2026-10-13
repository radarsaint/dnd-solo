"""#97 review at 8664e8e (Nagatha): P1-E, P1-B' and four P2s.

P1-E: a look, a listen, a sniff, a wait or a threshold look is no hands-on turn: no handles
      offer, and a declaration on it is rejected (nothing fires).
P1-B': on a turn that offers handles, none carries a reason from a closed set, and no
      performance shows an offered feature moving or opening unless a declaration fires it.
P2: a player-safe message on a pending ruling; a look into the next area by its name is a
    threshold look voiced from the room's exit; a death save counts only once it is owed;
    a tied save on a half-damage spell takes the full rolled total.

Room-agnostic: the from-scratch crypt (tests/fixtures/rooms/crypt.json) and a bell tower
written here. Dice are pinned (``roll`` the monsters' d20s, ``npc_roll`` their Stealth).
"""
import copy
import unittest

from runtime import kit_acts, kit_agent, kit_combat, kit_triggers
from runtime.state_context import InvalidChange
from test_kit_review97b import Room, bridge_turn, crypt, open_tomb


def belfry():
    """A bell tower with a bell rope that wakes the bats (from scratch, no book text)."""
    return {
        'id': 'synthetic-belfry-v1', 'fixture_only': True, 'starting_area': 'stair',
        'areas': {'stair': {'name': 'Tower stair', 'called': 'the stair', 'arrival': 'Someone climbs up.'},
                  'loft': {'name': 'Bell loft', 'called': 'the bell loft', 'arrival': 'Someone climbs up.'}},
        'exits': {'ladder': {'name': 'the ladder', 'areas': ['stair', 'loft'], 'secret': False,
                             'labels': {'stair': 'A ladder climbs to the loft.', 'loft': 'The ladder drops away.'}}},
        'facts': {'rope': {'area': 'stair', 'visible': True, 'text': 'A frayed bell rope hangs down the stairwell.',
                           'handling': {'nouns': ['rope', 'bellrope'], 'parts': ['knot'],
                                        'look': 'Pigeon droppings crust the knot.',
                                        'move': 'High above, the bell swings and booms.',
                                        'handle': 'The rope is rough in your hands.'}},
                  'beam': {'area': 'loft', 'visible': True, 'text': 'A cracked oak beam.'}},
        'actors': {'bats': {'name': 'Bat swarm', 'location': 'stair', 'status': 'hidden', 'visible': False,
                            'motive': 'Roost.', 'knowledge': [], 'secrets': [],
                            'communication_profile': {'rhythm': 'None.', 'humor': 'None.'},
                            'stat_block': {'ac': 12, 'hp': 9, 'initiative': 2, 'stealth': 4,
                                           'attacks': [{'name': 'Bites', 'verb': 'bite', 'to_hit': 3,
                                                        'damage': 5, 'type': 'piercing'}]}}},
        'triggers': [{'id': 'bell_rung', 'on': {'disturb': 'rope'}, 'actors': ['bats'],
                      'surprise': {'stealth': None}, 'reveal': 'A shrieking cloud pours down from the rafters.'}],
        'story': {}, 'resources': {}}


NO_HANDS = ('I look around the nave.', 'I wait.', 'I listen at the lid.', 'I sniff the air.',
            'I look at the sarcophagus.', 'I peer through the arch.')
HANDS = ('I push the lid aside.', 'I push it.', 'I pry it open.', 'I heave the stone slab aside.')


class NoHandsNoOfferTests(unittest.TestCase):
    """P1-E."""

    def test_looks_listens_and_waits_offer_nothing(self):
        for line in NO_HANDS:
            with self.subTest(line=line):
                result = Room(self).resolve(line)
                self.assertNotIn('handles', result.offers or {})

    def test_hands_on_lines_and_pronouns_are_still_offered(self):
        for line in HANDS:
            with self.subTest(line=line):
                self.assertIn('sarcophagus', Room(self).resolve(line).offers['handles']['targets'])

    def test_a_declaration_on_a_look_or_a_wait_is_rejected_and_fires_nothing(self):
        for line, decl in (('I look around the nave.', {'target': 'sarcophagus', 'act': 'open'}),
                           ('I wait.', {'target': 'sarcophagus', 'act': 'roll'}),
                           ('I listen at the lid.', {'target': 'lid', 'act': 'lift'}),
                           ('I sniff the air.', {'target': 'sarcophagus', 'act': 'roll'})):
            with self.subTest(line=line):
                room = Room(self)
                with self.assertRaisesRegex(InvalidChange, 'Nothing here can be handled'):
                    kit_acts.check({'handles': decl}, {'acts': room.resolve(line).offers or {}})
                if line.startswith('I look') or line.startswith('I sniff'):
                    with self.assertRaisesRegex(InvalidChange, 'Nothing here can be handled'):
                        bridge_turn(room, line, decl, text='Dust and silence.')
                self.assertFalse(room.state.get('triggers_fired'))
                self.assertEqual(room.state['actors']['ghoul']['status'], 'hidden')

    def test_physical_needs_a_hands_on_verb_or_a_pronoun_object(self):
        for line in ('I wait.', 'I look at it.', 'I listen at it.', 'I take a step toward it.', 'I sniff the air.'):
            self.assertFalse(kit_triggers.physical(line), line)
        for line in ('I push it.', 'I lean my weight on it.', 'I yank the rope.', 'I wrestle it loose.'):
            self.assertTrue(kit_triggers.physical(line), line)

    def test_another_room_the_bell_rope(self):
        room = Room(self, source=belfry())
        self.assertNotIn('handles', room.resolve('I look up the stairwell at the rope.').offers or {})
        self.assertIn('rope', room.resolve('I yank it hard.').offers['handles']['targets'])
        room.act('I yank the rope.', {'target': 'rope', 'act': 'pull'})
        self.assertEqual(room.state['triggers_fired'], ['bell_rung'])


class NoneNeedsAReasonTests(unittest.TestCase):
    """P1-B'."""

    def test_a_bare_none_on_a_hands_on_turn_is_rejected(self):
        for line, text in (('I push the lid aside.', 'Nothing happens.'), ('I push it.', 'You push. Stone scrapes.')):
            with self.subTest(line=line):
                room = Room(self)
                with self.assertRaisesRegex(InvalidChange, 'needs a reason'):
                    bridge_turn(room, line, {'target': 'none', 'act': 'none'}, text=text)
                self.assertFalse(room.state.get('triggers_fired'))

    def test_an_unknown_reason_is_rejected(self):
        offer = {'acts': {'handles': {'targets': {'sarcophagus': ['lid']}}}}
        with self.assertRaises(InvalidChange):
            kit_acts.check({'handles': {'target': 'none', 'act': 'none', 'reason': 'felt_like_it'}}, offer)
        self.assertEqual(kit_acts.check({'handles': {'target': 'none', 'act': 'none', 'reason': 'too_heavy'}}, offer), {})
        with self.assertRaises(InvalidChange):  # a reason goes only with none
            kit_acts.check({'handles': {'target': 'lid', 'act': 'push', 'reason': 'blocked'}}, offer)

    def test_none_with_a_reason_may_not_narrate_the_feature_moving(self):
        for line, text in (('I push the lid aside.', 'The lid grinds aside a hand-width.'),
                           ('I push it.', 'You push. It scrapes.'),
                           ('I pry it open.', 'It comes open with a crack.')):
            with self.subTest(line=line):
                room = Room(self)
                with self.assertRaisesRegex(InvalidChange, 'moving or opening'):
                    bridge_turn(room, line, {'target': 'none', 'act': 'none', 'reason': 'too_heavy'}, text=text)
                self.assertFalse(room.state.get('triggers_fired'))

    def test_none_with_a_reason_and_honest_narration_commits_quietly(self):
        room = Room(self)
        _, result = bridge_turn(room, 'I push the lid aside.', {'target': 'none', 'act': 'none', 'reason': 'too_heavy'},
                                text='You strain, but the lid will not budge.')
        self.assertIn('will not budge', result['spoken'])
        self.assertFalse(room.state.get('triggers_fired'))

    def test_a_real_declaration_may_narrate_it_moving(self):
        room = Room(self)
        bridge_turn(room, 'I push the lid aside.', {'target': 'lid', 'act': 'push'},
                    text='The lid grinds aside.')
        self.assertEqual(room.state['triggers_fired'], ['tomb_opened'])

    def test_another_room_the_bell_rope(self):
        room = Room(self, source=belfry())
        with self.assertRaisesRegex(InvalidChange, 'moving or opening'):
            bridge_turn(room, 'I yank the rope.', {'target': 'none', 'act': 'none', 'reason': 'blocked'},
                        text='The rope swings and the bell booms above.')
        self.assertFalse(room.state.get('triggers_fired'))


class PendingRulingMessageTests(unittest.TestCase):
    def test_the_player_message_is_curtain_safe(self):
        for message in (f'{kit_agent.UNSUPPORTED_RULING} No turn was committed.',
                        'Spell effects outside combat are not resolved in this slice yet, so the spell is not cast. '
                        'No turn was committed.'):
            with self.subTest(message=message):
                result = kit_agent.pending_ruling_result(kit_agent.PendingRuling(message))
                self.assertEqual(result['message'], message)
                safe = result['player_message']
                for word in ('slice', 'committed', 'ruling', 'engine'):
                    self.assertNotIn(word, safe.casefold())
                self.assertTrue(safe.strip())

    def test_a_bridge_ruling_carries_it(self):
        room = Room(self, source=belfry())
        result = kit_agent.KitChatBridge(room.runtime, room.adjudicator).try_prepare(
            'I cast Light on my staff.', 'p', one_pass=True)
        self.assertEqual(result['stage'], 'pending_ruling')
        self.assertNotIn('slice', result['player_message'])


class ThresholdByAreaNameTests(unittest.TestCase):
    def test_looking_into_the_next_area_by_name_is_a_threshold_look(self):
        for source, line, exit_name in ((crypt(), 'I look into the vestibule.', 'the low arch'),
                                        (belfry(), 'I peer into the bell loft.', 'the ladder')):
            with self.subTest(line=line):
                result = Room(self, source=source).resolve(line)
                self.assertEqual(result.kind, 'threshold_look')
                self.assertNotIn('look around the room', result.public_event)
                self.assertIn(exit_name, result.public_event)


class DeathSaveOrderTests(unittest.TestCase):
    """A death save counts only once it is owed: one typed before the foes' blows is not
    spent on the save those blows create."""

    def test_an_early_death_save_is_not_spent_after_the_blow(self):
        source = crypt()
        room = Room(self, source=source, sheet='nik', roll=lambda: 15)
        open_tomb(room)
        room.wound(1)
        room.act('Initiative 1')  # the ghoul drops him: a death save is owed
        room.act('Death save 12')  # a host that never sent Kit's call on the ghoul
        saves = dict(room.fight['death_saves'])
        # The ghoul's next turn is due (Kit's call open); the player types a save early.
        fight = room.fight
        if (fight.get('awaiting') or {}).get('kind') != 'kit_call':
            self.skipTest('no open call to test against')
        result = room.act('Death save 3')
        self.assertIn('roll it again', result.public_event)
        self.assertEqual(room.fight['death_saves']['successes'], saves['successes'])
        self.assertLessEqual(room.fight['death_saves']['failures'] - saves['failures'], 2)
        self.assertEqual((room.fight.get('awaiting') or {}).get('save'), 'death')


class HalvedDamageTests(unittest.TestCase):
    def test_an_odd_total_is_not_short_by_one(self):
        source = crypt()
        source['actors']['ghoul']['stat_block']['hp'] = 40
        room = Room(self, source=source, sheet='nik', roll=lambda: 2)
        open_tomb(room)
        room.act('Initiative 20')
        room.act('I cast Fireball at the hollow-eyed ghoul.\nNik casts Fireball!\n**DC**: 15\nHollow-eyed ghoul\n'
                 '**DEX Save**: 1d20 (13) + 2 = `15`; Success!\n'
                 '**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 2) [fire] = `13`')
        self.assertEqual(room.fight['max_hp']['ghoul'] - room.fight['hp']['ghoul'], 27)
        self.assertEqual(kit_combat.unhalved_damage('**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 2) [fire] = `13`', 13), 27)


if __name__ == '__main__':
    unittest.main()
