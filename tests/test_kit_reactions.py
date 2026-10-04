"""The PC's reaction inventory (PR-H; Brendon's requirement): built from any sheet, engine state
like HP (slots and uses session-long, the reaction back each turn), a compact cached line for
Kit, and windows only when an event matches an available reaction. Roadcamp and carcass
fixtures; every die pinned."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_manifest, kit_reactions
from runtime.kit_agent import KitChatBridge
from test_kit_combat_checkpoints import CAMP, CAST, Camp, NIK, OPEN, SHIELD, rolls, shield_only
from test_kit_monster_initiative import ROLL, Room

ROOT = Path(__file__).resolve().parents[1]
BASE = {k: v for k, v in json.loads((ROOT / 'tests/fixtures/characters/example_pc.json').read_text()).items()
        if k not in ('spells', 'slots', 'features', 'feats', 'magic_items', 'items', 'equipment')}
SYNTHETIC = {
    **BASE, 'name': 'Vess', 'class': 'Rogue (Thief) / Bard', 'level': 7, 'ac': 15, 'hp': 44,
    'spells': [{'name': 'Silvery Barbs', 'level': 1, 'casting_time': '1 reaction'},
               {'name': 'Healing Word', 'level': 1, 'casting_time': '1 bonus action'},
               {'name': 'Vicious Mockery', 'level': 0}],
    'slots': {'1': {'max': 3, 'used': 1}, '2': {'max': 1, 'used': 0}},
    'features': [{'name': 'Uncanny Dodge', 'text': 'When an attacker you can see hits you, you can use your '
                                                   'reaction to halve the damage.'},
                 {'name': 'Cutting Words (4/short rest)', 'activation': 'reaction',
                  'text': 'Subtract a Bardic Inspiration die from a creature\'s roll.'}],
    'feats': ['Sentinel'],
    'magic_items': [{'name': 'Cloak of Displacement', 'text': 'Attackers have disadvantage.'}],
}


def ids(resources):
    return [r['id'] for r in resources['reactions']]


class Inventory(unittest.TestCase):
    def test_niks_sheet(self):
        resources = kit_reactions.build(NIK)
        self.assertEqual(ids(resources), ['shield', 'chronal_shift', 'lucky_footwork', 'opportunity_attack'])
        by_id = {r['id']: r for r in resources['reactions']}
        self.assertEqual((by_id['shield']['source'], by_id['shield']['cost']), ('spell (level 1)', {'slot': 1}))
        self.assertEqual(resources['uses'], {'chronal_shift': {'max': 2, 'used': 0, 'recharge': 'long'}})
        self.assertIn('War Caster', by_id['opportunity_attack']['note'], 'War Caster changes the OA, not its own')
        self.assertEqual(resources['slots'], {'1': {'max': 4, 'used': 0}, '2': {'max': 3, 'used': 0},
                                              '3': {'max': 2, 'used': 0}})
        gaps = kit_reactions.gaps(NIK)
        self.assertTrue(any('Clue, Arcane Aegis' in g for g in gaps), gaps)
        self.assertTrue(any('no weapons or attacks' in g for g in gaps), gaps)

    def test_a_synthetic_sheet_in_other_formats(self):
        resources = kit_reactions.build(SYNTHETIC)
        self.assertEqual(ids(resources), ['silvery_barbs', 'uncanny_dodge', 'cutting_words', 'sentinel',
                                          'opportunity_attack'])
        by_id = {r['id']: r for r in resources['reactions']}
        self.assertEqual(by_id['silvery_barbs']['trigger'], ['creature_succeeds'])
        self.assertEqual(by_id['sentinel']['source'], 'feat (feats)')
        self.assertEqual((by_id['cutting_words']['trigger'], by_id['cutting_words']['effect']),
                         (['custom'], 'kit_adjudicates'))
        self.assertEqual(resources['uses']['cutting_words'], {'max': 4, 'used': 0, 'recharge': 'short'})
        self.assertEqual(resources['slots']['1'], {'max': 3, 'used': 1}, 'a {max, used} slot is read as written')
        self.assertNotIn('cloak_of_displacement', ids(resources), 'nothing says it uses a reaction')

    def test_nothing_is_invented(self):
        self.assertEqual(ids(kit_reactions.build(BASE)), ['opportunity_attack'])
        self.assertEqual(kit_reactions.build({'spells': ['Shield']})['reactions'][0]['cost'], {'slot': 1})

    def test_the_inventory_is_built_when_the_sheet_loads(self):
        camp = Camp(self)
        self.assertEqual(camp.state['pc_resources'], kit_reactions.build(NIK))


class Rests(unittest.TestCase):
    def test_a_short_rest_restores_short_rest_features_only(self):
        sheet = copy.deepcopy(SYNTHETIC)
        camp = Camp(self, sheet=sheet)
        revision, state = camp.runtime.load()
        spent, _ = kit_reactions.spend(state['pc_resources'], 'cutting_words')
        spent, _ = kit_reactions.spend(spent, 'silvery_barbs')
        camp.runtime.commit('spend', revision, [{'type': 'pc_resources', 'resources': spent, 'evidence': 'test'}])
        camp.runtime.rest('short')
        resources = camp.state['pc_resources']
        self.assertEqual(resources['uses']['cutting_words']['used'], 0)
        self.assertEqual(resources['slots']['1']['used'], 2, 'slots wait for a long rest')

    def test_a_long_rest_restores_slots_and_long_rest_uses(self):
        camp = Camp(self)
        camp.act(OPEN)
        camp.act(CAST, **SHIELD)
        self.assertEqual(camp.state['pc_resources']['slots']['1']['used'], 1)
        camp.runtime.rest('long')
        self.assertEqual(camp.state['pc_resources'], kit_reactions.build(NIK))


class Windows(unittest.TestCase):
    def test_silvery_barbs_on_an_npc_succeeding_on_a_save(self):
        sheet = copy.deepcopy(SYNTHETIC)
        sheet['spell_save_dc'] = 15
        # The cutthroats fail (3), the captain saves (18 >= 15); Silvery Barbs rerolls (3), the lower stands.
        camp = Camp(self, sheet=sheet, roll=rolls(3, 3, 18, 3, then=2))
        result = camp.act('Initiative 25. I cast Fireball at the bandit captain, 20 fire damage.')
        waiting = camp.fight['awaiting']
        self.assertEqual((result.kind, waiting['trigger'], waiting['target'], waiting['options']),
                         ('combat_interstitial', 'npc_save', 'harl', ['silvery_barbs']))
        self.assertEqual(camp.fight['hp']['harl'], 30, 'the damage waits on the answer')
        camp.act('Nik casts Silvery Barbs!', react='silvery_barbs', cast_in_avrae=True)
        self.assertEqual(camp.fight['hp']['harl'], 10, 'the reroll failed: full damage')
        self.assertEqual(camp.fight['hp']['cutthroat_b'], 0, 'the cutthroats failed: full damage')
        self.assertEqual(camp.state['pc_resources']['slots']['1']['used'], 2)

    def test_no_window_when_the_reaction_is_spent_or_no_slot_is_left(self):
        sheet = copy.deepcopy(SYNTHETIC)
        sheet['spell_save_dc'] = 15
        sheet['slots'] = {'1': {'max': 1, 'used': 1}}
        sheet['features'] = []
        sheet['feats'] = []
        camp = Camp(self, sheet=sheet, roll=rolls(18, then=2))
        camp.act('Initiative 25. I cast Fireball at the bandit captain, 20 fire damage.')
        self.assertNotEqual((camp.fight.get('awaiting') or {}).get('trigger'), 'npc_save', 'no slot: no Silvery Barbs')
        # Spent: the captain's second blow (15 + 5 = 20) gets no window once Shield used the reaction.
        camp = Camp(self, sheet=shield_only(), roll=rolls(10, 15))
        camp.act(OPEN)
        camp.act(CAST, **SHIELD)
        self.assertIsNone(camp.fight.get('awaiting'))
        self.assertEqual(camp.fight['pc_damage'], 6)

    def test_uncanny_dodge_halves_the_hit(self):
        sheet = copy.deepcopy(SYNTHETIC)
        sheet['ac'] = 14
        sheet['feats'] = []
        sheet['spells'] = []
        sheet['features'] = sheet['features'][:1]
        camp = Camp(self, sheet=sheet)
        camp.act(OPEN)
        self.assertEqual(camp.fight['awaiting']['options'], ['uncanny_dodge'])
        camp.act('Dodge it.', react='uncanny_dodge')
        self.assertEqual(camp.fight['pc_damage'], 3 + 6 + 5 + 11)

    def test_shield_blocks_magic_missile(self):
        source = json.loads(CAMP.read_text())
        source['combat']['actors']['harl']['attacks'] = [
            {'name': 'magic missile', 'verb': 'blasts', 'to_hit': 0, 'damage': 10, 'type': 'force', 'auto_hit': True}]
        path = Path(tempfile.mkdtemp()) / 'camp.json'
        path.write_text(json.dumps(source))
        with mock.patch('test_kit_combat_checkpoints.CAMP', path):
            camp = Camp(self, sheet=shield_only())
        camp.act(OPEN)
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['options'], waiting['magic_missile']), (['shield'], True))
        camp.act(CAST, **SHIELD)
        self.assertEqual(camp.fight['pc_damage'], 0, 'the missiles are blocked; the mace misses AC 19')

    def test_counterspell_answers_a_spell_cast(self):
        source = json.loads(CAMP.read_text())
        source['combat']['actors']['harl']['attacks'] = [
            {'name': 'fire bolt', 'verb': 'burns', 'to_hit': 5, 'damage': 9, 'type': 'fire', 'spell': True,
             'level': 0, 'ranged': True}]
        path = Path(tempfile.mkdtemp()) / 'camp.json'
        path.write_text(json.dumps(source))
        sheet = shield_only()
        sheet['spells']['3'].append('Counterspell')
        with mock.patch('test_kit_combat_checkpoints.CAMP', path):
            camp = Camp(self, sheet=sheet)
        camp.act(OPEN)
        waiting = camp.fight['awaiting']
        self.assertEqual((waiting['trigger'], waiting['options']), ('npc_spell', ['counterspell']))
        camp.act('Nik casts Counterspell!', react='counterspell', cast_in_avrae=True, slot_level=3)
        self.assertEqual(camp.state['pc_resources']['slots']['3']['used'], 1)
        self.assertEqual(camp.fight['pc_damage'], 11, 'the fire bolt fails; the mace lands')

    def test_a_97_era_save_prompt_resumes(self):
        # Nagatha's probe: a paused #97 roll call says "from", not "attacker", and has no attack_index.
        room = Room(self, npc_roll=lambda: 1, roll=lambda: 12, sheet=shield_only())
        room.act('I roll the carcass over.', ROLL)
        room.act('Initiative 1')
        room.act('No.', react='decline')
        revision, state = room.runtime.load()
        waiting = state['combat']['awaiting']
        state['combat']['awaiting'] = {'kind': 'roll_call', 'awaits': 'player_roll', 'save': waiting['save'],
                                       'dc': waiting['dc'], 'damage': waiting['damage'], 'type': waiting['type'],
                                       'half': waiting['half'], 'at_zero': waiting['at_zero'],
                                       'from': waiting['attacker']}
        result = room.adjudicator.resolve('Con save 5', revision, state)
        self.assertIn('10 poison', result.public_event)


class ManifestLine(unittest.TestCase):
    def session_hash(self, bridge, turn, action):
        packet = bridge.prepare(action, turn, one_pass=True)
        if packet['stage'] != 'one_pass':
            return packet, None
        session, _, _ = kit_manifest.split(packet)
        bridge.abandon(turn)
        return packet, kit_manifest.digest(session)

    def test_the_line_is_in_the_session_manifest_and_changes_only_on_spend(self):
        camp = Camp(self, sheet=shield_only(), roll=lambda: 2)
        bridge = KitChatBridge(camp.runtime, camp.adjudicator)
        packet, first = self.session_hash(bridge, 'a', 'I look around the camp.')
        line = packet['input']['private']['available_reactions']
        self.assertIn('Shield (spell, L1+ slot, cast in Avrae: !cast shield)', line)
        self.assertLess(len(line), 300)
        _, again = self.session_hash(bridge, 'b', 'I look at the wagon.')
        self.assertEqual(first, again, 'nothing spent: the cached session manifest is unchanged')
        revision, state = camp.runtime.load()
        spent, _ = kit_reactions.spend(state['pc_resources'], 'shield')
        camp.runtime.commit('spend', revision, [{'type': 'pc_resources', 'resources': spent, 'evidence': 'test'}])
        packet, after = self.session_hash(bridge, 'c', 'I look at the fire.')
        self.assertNotEqual(first, after)
        self.assertIn('L1 3/4', packet['input']['private']['available_reactions'])


if __name__ == '__main__':
    unittest.main()
