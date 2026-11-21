"""v0.15.0: the SRD 5.1 monster list ships as data (runtime/data/srd_5_1_monsters.json), built by
tools/build_srd_monsters.py from 5e-bits/5e-database (MIT). Synthetic converter fixtures only."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

from runtime import kit_moves, kit_rooms, srd_creatures

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('build_srd_monsters', ROOT / 'tools' / 'build_srd_monsters.py')
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def monster(**over):
    """A made-up creature in the 5e-database shape."""
    base = {'name': 'Test Lurker', 'armor_class': [{'type': 'natural', 'value': 14}], 'hit_points': 19,
            'strength': 16, 'dexterity': 12, 'constitution': 14, 'intelligence': 6, 'wisdom': 13, 'charisma': 7,
            'proficiencies': [{'value': 5, 'proficiency': {'index': 'skill-stealth'}},
                              {'value': 4, 'proficiency': {'index': 'saving-throw-con'}}],
            'actions': [{'name': 'Bite', 'attack_bonus': 5,
                         'damage': [{'damage_type': {'index': 'piercing'}, 'damage_dice': '2d6+3'}]},
                        {'name': 'Claw', 'attack_bonus': 5,
                         'damage': [{'damage_type': {'index': 'slashing'}, 'damage_dice': '1d4+3'}]}]}
    base.update(over)
    return base


class ConverterTest(unittest.TestCase):
    def test_numbers_come_from_the_dice_and_scores(self):
        line = build.convert(monster())
        self.assertEqual((line['ac'], line['hp'], line['initiative'], line['grapple']), (14, 19, 1, 3))
        self.assertEqual(line['stealth'], 5)
        self.assertEqual(line['saves']['con'], 4)
        self.assertEqual(line['saves']['dex'], 1)
        self.assertEqual(line['attacks'], [{'name': 'bite', 'verb': 'bites', 'to_hit': 5, 'damage': 10,
                                            'type': 'piercing'}])

    def test_a_multiattack_of_two_is_two_swings(self):
        actions = [{'name': 'Multiattack', 'desc': 'The lurker makes two attacks.'}] + monster()['actions']
        self.assertEqual(len(build.convert(monster(actions=actions))['attacks']), 2)

    def test_a_versatile_choice_takes_the_first_option(self):
        act = {'name': 'Longblade', 'attack_bonus': 3, 'damage': [{'choose': 1, 'from': {'options': [
            {'damage_type': {'index': 'slashing'}, 'damage_dice': '1d8+1'},
            {'damage_type': {'index': 'slashing'}, 'damage_dice': '1d10+1'}]}}]}
        line = build.convert(monster(actions=[act]))
        self.assertEqual((line['attacks'][0]['damage'], line['attacks'][0]['verb']), (5, 'cuts'))

    def test_a_creature_with_no_attack_is_left_out(self):
        self.assertIsNone(build.convert(monster(actions=[{'name': 'Shriek', 'desc': 'It shrieks.'}])))


class ShippedTableTest(unittest.TestCase):
    def test_the_full_list_ships_and_hand_lines_still_win(self):
        self.assertGreaterEqual(len(srd_creatures.SRD), 300)
        self.assertEqual(srd_creatures.CREATURES['ghoul'], srd_creatures.HAND['ghoul'])
        for name in srd_creatures.HAND:
            self.assertIn(name, srd_creatures.SRD, name)

    def test_every_shipped_line_is_one_the_engine_can_run(self):
        for name, line in srd_creatures.CREATURES.items():
            block = srd_creatures.stat_block({'srd': name})
            self.assertTrue(type(block['ac']) is int and type(block['hp']) is int and block['hp'] > 0, name)
            self.assertTrue(block['attacks'], name)
            for attack in block['attacks']:
                self.assertTrue({'name', 'verb', 'to_hit', 'damage', 'type'} <= set(attack), name)
                self.assertGreater(attack['damage'], 0, name)

    def test_creatures_missing_before_now_resolve_by_name(self):
        for name in ('Wolf', 'Bugbear', 'Zombie', 'Hobgoblin', 'Orc'):
            block = srd_creatures.stat_block({'srd': name})
            self.assertIsNotNone(block, name)
        self.assertIsNone(srd_creatures.stat_block({'srd': 'Made-up Horror'}))

    def test_npc_templates_resolve_but_are_not_looked_for_in_book_text(self):
        for name in ('druid', 'noble', 'spy'):
            self.assertIsNotNone(srd_creatures.stat_block({'srd': name}), name)
            self.assertNotIn(name, srd_creatures.DETECT, name)
        for name in ('wolf', 'hobgoblin', 'goblin', 'guard', 'bandit'):
            self.assertIn(name, srd_creatures.DETECT, name)

    def test_a_bare_role_word_in_a_synthetic_note_is_not_cast(self):
        from runtime import kit_adventure
        note = 'The reeve is an old friend of a druid named Test Elder. Two wolves lurk past the fence.'
        names = {c['name'] for c in kit_adventure._creatures(note, 0, {})}
        self.assertIn('wolf', names)
        self.assertNotIn('druid', names)
        self.assertEqual(kit_adventure._present('Two wolves lurk past the fence.', 'wolf')[0], 2)
        self.assertEqual(kit_adventure._present('Three harpies circle.', 'harpy')[0], 3)

    def test_resolving_returns_a_copy(self):
        block = srd_creatures.stat_block({'srd': 'wolf'})
        block['hp'] = 1
        self.assertNotEqual(srd_creatures.stat_block({'srd': 'wolf'})['hp'], 1)

    def test_a_listed_stealth_is_known_for_a_newly_shipped_creature(self):
        self.assertEqual(kit_moves.known_stealth({'srd': 'wolf'}), srd_creatures.SRD['wolf']['stealth'])

    def test_no_description_text_ships(self):
        raw = (ROOT / 'runtime' / 'data' / 'srd_5_1_monsters.json').read_text(encoding='utf-8')
        self.assertNotIn('"desc"', raw)
        self.assertNotIn('Melee Weapon Attack', raw)


class RoomCheckTest(unittest.TestCase):
    def test_a_room_citing_a_newly_shipped_creature_passes_the_fight_check(self):
        room = {'actors': {'wolf_1': {'name': 'Wolf 1', 'stat_block': {'srd': 'Wolf'}}}}
        problems = []
        try:
            kit_rooms.check_room(copy.deepcopy(room))
        except Exception as exc:  # other room fields are out of scope; only the stat line matters here
            problems = [str(exc)]
        self.assertFalse(any('no usable stat_block' in p for p in problems), problems)


if __name__ == '__main__':
    unittest.main()
