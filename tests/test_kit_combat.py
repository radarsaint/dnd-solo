"""Physical acts and the minimal 6c fight (scorecard item 1, 6c baseline 2026-10-03).

Every die here is pinned: Kit's own d20s come from the adjudicator's ``roll`` override or
a pinned roll seed, and the player's numbers are stated the way Avrae reports them."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_combat, kit_voice
from runtime.kit_agent import PendingRuling, RoomAdjudicator
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'level_01_area_06c.json'
NIK = ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json'
NUMBERS_KIT_KEEPS = ('AC', 'DC', 'hit points', ' hp', 'd20')


class Room:
    def __init__(self, test, roll=lambda: 10, seed=7):
        temp = tempfile.TemporaryDirectory()
        test.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        test.addCleanup(self.runtime.close)
        with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{seed:032x}'):
            self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.runtime.set_player_sheet(json.loads(NIK.read_text()))
        self.adjudicator = RoomAdjudicator(roll=roll, source=self.runtime.source())

    def act(self, action, **choice):
        """``choice``: Kit's structured read of a reply to an open reaction window (react=...)."""
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(action, revision, state, choice=choice or None)
        self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    @property
    def state(self):
        return self.runtime.load()[1]


class PhysicalActTests(unittest.TestCase):
    def assertNoHiddenNumbers(self, text):
        for word in NUMBERS_KIT_KEEPS:
            self.assertNotIn(word, text)

    def test_flipping_the_table_changes_the_room_and_cracks_the_act(self):
        room = Room(self)
        result = room.act('I grab the edge of the card table and heave it over, coins and all.')
        self.assertEqual(result.kind, 'physical_act')
        scene = room.state['scene']
        self.assertEqual(scene['table'], 'overturned')
        self.assertEqual(scene['ring'], 'uktarl', 'the dealer grabs the ring')
        self.assertEqual(scene['grovelling'], 'bandit_a')
        self.assertEqual(scene['act'], 'cracked')
        self.assertIn('vampire_tells', room.state['known_facts'])
        view = room.runtime.player_view()
        self.assertEqual(view['room_now']['table'], 'overturned')
        self.assertNotIn('uktarl', json.dumps(view['room_now']))
        self.assertNoHiddenNumbers(result.public_event)

    def test_wiping_paint_off_a_face_is_physical_not_a_look(self):
        room = Room(self)
        result = room.act("I lick my thumb and wipe a streak of paint off the dealer's cheek.")
        self.assertEqual(result.kind, 'physical_act')
        self.assertNotIn('take a look', result.public_event)
        self.assertIn('vampire_tells', room.state['known_facts'])
        self.assertEqual(room.state['scene']['cracked_by'], 'face')

    def test_taking_the_pot_in_plain_sight_starts_a_fight_they_start(self):
        room = Room(self)
        result = room.act('I scoop a handful of coins from the pot and pocket them. [Sleight of Hand: 18]')
        self.assertEqual(result.kind, 'combat_round')
        self.assertEqual(room.state['combat']['started_by'], 'npcs')
        self.assertEqual(room.state['combat']['status'], 'awaiting_initiative')
        self.assertIn('Roll initiative.', result.public_event)
        self.assertIn('table coins', room.state['scene']['pc_took'][0])

    def test_the_players_own_things_and_glances_are_not_physical_acts(self):
        room = Room(self)
        source, state = room.runtime.source(), room.state
        for action in ('I take 10 gold out of my purse and pay.', 'I touch my face.', 'I catch his eye.',
                       'I take the empty chair.', 'Hit.', 'I cut the deck.', 'I put down ten gold.',
                       "I say 'I'll cut you if you cheat.'"):
            with self.subTest(action=action):
                self.assertIsNone(kit_combat.parse(action, source, state))


class FightTests(unittest.TestCase):
    def test_an_attack_without_its_roll_waits_and_commits_nothing(self):
        room = Room(self)
        with self.assertRaisesRegex(PendingRuling, 'Roll the attack for your dagger in Avrae'):
            room.act('I stab the dealer with my dagger.')
        self.assertIsNone(room.state.get('combat'))
        self.assertEqual(room.runtime.load()[0], 1, 'only the sheet load is committed')

    def test_the_opening_blow_lands_then_initiative_from_avrae_orders_the_round(self):
        room = Room(self, roll=lambda: 2)  # every NPC swing misses
        opener = room.act('I swing my dagger at the door-side player. 15 to hit, 4 piercing damage.')
        self.assertEqual(opener.kind, 'combat_round')
        fight = room.state['combat']
        self.assertEqual((fight['status'], fight['opener_spent']), ('awaiting_initiative', True))
        self.assertEqual(fight['hp']['bandit_a'], fight['max_hp']['bandit_a'] - 4)
        self.assertTrue(opener.public_event.endswith('Roll initiative.'))
        # Avrae's real format: the total counts, never the die alone.
        order = room.act('Initiative: 1d20 (3) + 2 = 5')
        fight = room.state['combat']
        self.assertEqual(fight['status'], 'running')
        self.assertEqual(fight['pc_initiative'], 5)
        self.assertEqual(fight['order'][-1], 'pc', 'NPCs at 10 + Dexterity all beat a 5')
        self.assertIn('Your turn.', order.public_event)
        self.assertEqual(fight['round'], 2, 'the opener was the first round\'s action')
        for word in ('AC', 'DC', 'hit points'):
            self.assertNotIn(word, order.public_event)

    def test_a_hurt_leader_flees_to_area_7_and_the_rest_to_area_8(self):
        room = Room(self, roll=lambda: 2)
        room.act('I attack the dealer with my dagger. 18 to hit, 5 piercing damage.')
        room.act('Initiative 25.')
        # The dagger engaged the dealer, so his break-away opens Nik's opportunity attack; he lets it go.
        self.assertEqual(room.state['combat']['awaiting']['trigger'], 'leaves_reach')
        room.act('Let him go.', react='decline')
        actors = room.state['actors']
        self.assertEqual((actors['uktarl']['status'], actors['uktarl']['fled_toward']), ('fled', 'area_07'))
        # The fourth player (initiative 14) acted before the dealer ran; it goes on its next turn.
        self.assertEqual(actors['doppelganger']['status'], 'alive')
        room.act('I hold my ground.')
        # The fourth player swung at Nik (engaged), so its break-away is another opportunity attack window.
        self.assertEqual(room.state['combat']['awaiting']['actor'], 'doppelganger')
        room.act('Let it go.', react='decline')
        actors = room.state['actors']
        for key in ('bandit_a', 'bandit_b', 'doppelganger'):
            with self.subTest(actor=key):
                self.assertEqual((actors[key]['status'], actors[key]['fled_toward']), ('fled', 'area_08'))
        self.assertEqual(room.state['combat']['status'], 'over')
        self.assertIn('gone with the dealer', room.state['scene']['ring'])

    def test_an_underling_falling_sends_the_leader_running(self):
        room = Room(self, roll=lambda: 2)
        room.act('Initiative 25. I stab the door-side player with my dagger. 18 to hit, 20 piercing damage.')
        actors = room.state['actors']
        self.assertEqual(actors['bandit_a']['status'], 'dead')
        self.assertEqual(actors['uktarl']['status'], 'fled')

    def test_npc_turns_hit_the_pc_and_report_the_damage_to_apply_in_avrae(self):
        room = Room(self, roll=lambda: 15)  # every NPC swing hits AC 14
        room.act('I scoop a handful of coins from the pot. [Sleight of Hand: 18]')
        room.act('Initiative 1. I wait for them to make the first move.')
        # The 21 beats Shield (AC 19), so only Chronal Shift is offered; Nik takes the hit.
        self.assertEqual(room.state['combat']['awaiting']['options'], ['chronal_shift'])
        result = room.act('No, take it.', react='decline')
        self.assertIn('damage', result.public_event)
        self.assertGreater(room.state['combat']['pc_damage'], 0)
        self.assertNotIn('to hit', result.public_event)

    def test_fireball_uses_the_sheet_save_dc_and_kit_rolls_the_saves(self):
        room = Room(self, roll=lambda: 1)  # every save fails
        result = room.act('I cast Fireball at the middle of the card table. 28 fire damage.')
        actors = room.state['actors']
        self.assertEqual((actors['bandit_a']['status'], actors['bandit_b']['status']), ('dead', 'dead'))
        self.assertIn('vampire_tells', room.state['known_facts'])
        self.assertNotIn('15', result.public_event, 'the save DC is never shown')

    def test_a_pc_hidden_from_everyone_surprises_them(self):
        room = Room(self, roll=lambda: 2)
        room.act('I sneak along the wall toward the table. [Stealth: 1d20 (20) + 2 = 22]')
        self.assertTrue(room.state['scene']['pc_hidden'])
        room.act('I stab the dealer with my dagger. 18 to hit, 4 piercing damage.')
        fight = room.state['combat']
        self.assertEqual(set(fight['surprised']), {'uktarl', 'bandit_a', 'bandit_b', 'doppelganger'})
        self.assertFalse(room.state['scene']['pc_hidden'], 'the first blow gives the PC away')

    def test_walking_in_openly_surprises_nobody(self):
        room = Room(self, roll=lambda: 2)
        room.act('I stab the dealer with my dagger. 18 to hit, 4 piercing damage.')
        self.assertEqual(room.state['combat']['surprised'], [])

    # Avrae's real output (6c rerun 2026-10-03, V2 / V9 / V11): to-hit and damage are separate fields.
    def test_an_avrae_weapon_hit_deals_the_damage_field_not_the_to_hit_roll(self):
        room = Room(self, roll=lambda: 2)
        room.act('I rage and swing my greataxe at the dealer.\n'
                 'Brakka attacks with a Greataxe!\n'
                 '**To Hit**: 1d20 (11) + 7 = `18`\n'
                 '**Damage**: 1d12 (5) + 6 [slashing] = `11`')
        fight = room.state['combat']
        self.assertEqual(fight['max_hp']['uktarl'] - fight['hp']['uktarl'], 11)

    def test_an_avrae_crit_deals_the_crit_damage_field(self):
        room = Room(self, roll=lambda: 2)
        room.act('I stab the dealer with my dagger.\n'
                 'Nik attacks with a Dagger!\n'
                 '**To Hit**: 1d20 (20) + 5 = `25`\n'
                 '**Damage (CRIT!)**: 2d4 (3, 4) + 3 [piercing] = `10`')
        fight = room.state['combat']
        self.assertEqual(fight['max_hp']['uktarl'] - fight['hp']['uktarl'], 10)

    def test_an_avrae_fireball_resolves_and_initiative_follows(self):
        room = Room(self, roll=lambda: 1)  # every save Kit rolls fails
        result = room.act('From the doorway, I cast Fireball at the middle of the card table.\n'
                          'Nik casts Fireball!\n'
                          '**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 3) [fire] = `28`')
        self.assertEqual(result.kind, 'combat_round')
        actors = room.state['actors']
        self.assertEqual((actors['bandit_a']['status'], actors['bandit_b']['status']), ('dead', 'dead'))
        fight = room.state['combat']
        self.assertEqual(fight['max_hp']['uktarl'] - fight['hp']['uktarl'], 28)
        order = room.act('Rolling initiative.\n**Initiative**: 1d20 (12) + 2 = `14`')
        self.assertEqual(room.state['combat']['pc_initiative'], 14)
        self.assertEqual(room.state['combat']['status'], 'running', order.public_event)

    def test_avrae_dc_line_and_per_target_saves_are_used(self):
        room = Room(self, roll=lambda: 20)  # Kit's own saves would all succeed
        room.act('I cast Fireball at the card table.\n'
                 'Nik casts Fireball!\n'
                 '**DC**: 25\n'
                 'Dealer\n'
                 '**DEX Save**: 1d20 (3) + 2 = `5`; Failure!\n'
                 '**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 3) [fire] = `28`\n'
                 'Door-side player\n'
                 '**DEX Save**: 1d20 (18) + 1 = `19`; Failure!\n'
                 '**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 3) [fire] = `28`')
        fight = room.state['combat']
        self.assertEqual(fight['max_hp']['uktarl'] - fight['hp']['uktarl'], 28, "Avrae's failed save")
        self.assertEqual(room.state['actors']['bandit_a']['status'], 'dead')
        # Not in Avrae's output: Kit rolls the save (20) against Avrae's DC 25, so it fails.
        self.assertEqual(room.state['actors']['bandit_b']['status'], 'dead')

    def test_avrae_fire_bolt_uses_its_damage_field(self):
        room = Room(self, roll=lambda: 2)
        room.act('I hit the dealer with Fire Bolt.\n'
                 'Nik casts Fire Bolt!\n'
                 '**To Hit**: 1d20 (12) + 7 = `19`\n'
                 '**Damage**: 2d10 (4, 5) [fire] = `9`')
        fight = room.state['combat']
        self.assertEqual(fight['max_hp']['uktarl'] - fight['hp']['uktarl'], 9)

    def test_the_same_seed_gives_the_same_fight(self):
        def run():
            room = Room(self, roll=None, seed=11)
            room.act('I swing my dagger at the dealer. 16 to hit, 4 piercing damage.')
            return room.act('Initiative 9.').public_event, room.state['combat']
        self.assertEqual(run(), run())

    def test_a_fight_round_is_a_combat_turn_for_the_voice(self):
        self.assertEqual(kit_voice.mode_hint('combat_round', False), 'combat')
        kit_voice.check_turn_mode({'turn_mode': 'combat'}, 'combat_round', False)
        with self.assertRaises(Exception):
            kit_voice.check_turn_mode({'turn_mode': 'description'}, 'combat_round', False)


if __name__ == '__main__':
    unittest.main()
