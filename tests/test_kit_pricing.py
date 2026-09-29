"""Prices: Brendon's magic item formula (runtime/pricing.py), the SRD 5.1 tables, and the
precedence that picks between them (runtime/kit_prices.py). Nothing invents a price."""
import json
import unittest
from pathlib import Path

from runtime import kit_prices, pricing
from runtime.state_context import InvalidChange

FIXTURE = Path(__file__).parent / 'fixtures/level_01_area_06c.json'


class FormulaExampleTests(unittest.TestCase):
    """Every example in research/kit-aliveness/05-brendon-price-formula.md."""

    def test_average_rolls(self):
        self.assertEqual(pricing.average_roll('2d4+2'), 7)
        self.assertEqual(pricing.average_roll('8d6'), 28)
        with self.assertRaises(InvalidChange):
            pricing.average_roll('1d4')  # 2.5: the formula needs a whole-number impact

    def test_weapon_bonus_is_24_per_level_times_levels_in_circulation(self):
        value, text = pricing.impact({'impact_kind': 'weapon_bonus', 'bonus': 1, 'levels': 1})
        self.assertEqual(value, 24)
        self.assertIn('+1 x 24 = 24/level', text)
        self.assertEqual(pricing.impact({'impact_kind': 'weapon_bonus', 'bonus': 2, 'levels': 3})[0], 144)
        # The level count is an explicit input; the documented default is one band (4 levels).
        self.assertEqual(pricing.DEFAULT_WEAPON_LEVELS, 4)
        self.assertEqual(pricing.impact({'impact_kind': 'weapon_bonus', 'bonus': 1})[0], 96)

    def test_charged_fireball_wand_is_28_times_7(self):
        value, text = pricing.impact({'impact_kind': 'charged', 'dice': '8d6', 'charges': 7})
        self.assertEqual(value, 196)
        self.assertIn('28 x 7 charges = 196', text)

    def test_area_of_effect_multiplies_impact_by_4_before_gold_per_impact(self):
        value, text = pricing.impact({'impact_kind': 'charged', 'dice': '8d6', 'charges': 7, 'aoe': True})
        self.assertEqual(value, 784)
        self.assertIn('area of effect x4 = 784', text)
        result = pricing.price({'item': 'Wand of Fireballs', 'impact_kind': 'charged', 'dice': '8d6',
                                'charges': 7, 'aoe': True, 'entry_level': 9, 'category': 'Complex Multi-Ability'})
        self.assertEqual(result['final_price'], '784 x 200 = 156800 -> 157000 gp')

    def test_potion_of_healing_is_a_single_use_of_2d4_plus_2(self):
        result = pricing.price({'item': 'Potion of Healing', 'impact_kind': 'consumable', 'dice': '2d4+2',
                                'entry_level': 1, 'category': 'Consumable'})
        self.assertEqual((result['rarity_band'], result['gold_per_impact'], result['amount']), ('Common', 10, 70))
        self.assertEqual(result['impact_calculation'], '2d4+2 = 7 (single use)')

    def test_decanter_of_endless_water_360_rounds_to_400(self):
        result = pricing.price({'item': 'Decanter of Endless Water', 'impact_kind': 'utility',
                                'utility': 'reusable', 'entry_level': 5, 'category': 'Utility'})
        self.assertEqual(result['amount'], 400)
        self.assertEqual(pricing.trace_text(result), '\n'.join((
            'Item: Decanter of Endless Water',
            'Impact Calculation: reusable utility effect 6',
            'Rarity Band: Uncommon', 'Item Category: Utility', 'Gold Per Impact: 60',
            'Final Price: 6 x 60 = 360 -> 400 gp')))

    def test_official_dmg_price_overrides_the_formula(self):
        result = pricing.price({'item': 'Potion of Healing', 'impact_kind': 'consumable', 'dice': '2d4+2',
                                'entry_level': 1, 'category': 'Consumable', 'official_price_gp': 50})
        self.assertEqual(result['amount'], 50)
        self.assertIn('official DMG price overrides formula 70 gp', result['final_price'])

    def test_bands_categories_and_the_rounding_rule(self):
        self.assertEqual([pricing.rarity_band(level) for level in (1, 4, 5, 8, 9, 12, 13, 16)],
                         ['Common', 'Common', 'Uncommon', 'Uncommon', 'Rare', 'Rare', 'Very Rare', 'Very Rare'])
        with self.assertRaises(InvalidChange):
            pricing.rarity_band(17)
        with self.assertRaises(InvalidChange):
            pricing.price({'item': 'x', 'impact_kind': 'utility', 'utility': 'minor', 'entry_level': 2,
                           'category': 'Weapon'})
        cases = {7: 10, 44: 40, 45: 50, 150: 200, 360: 400, 949: 900, 1240: 1000, 1250: 1500,
                 9800: 10000, 156800: 157000}
        for raw, clean in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(pricing.clean_price(raw), clean)


class SrdTableTests(unittest.TestCase):
    def test_data_carries_cc_by_attribution_and_every_table(self):
        data = json.loads(kit_prices.SRD_FILE.read_text(encoding='utf-8'))
        self.assertIn('System Reference Document 5.1', data['_attribution'])
        self.assertIn('Creative Commons Attribution 4.0', data['_attribution'])
        tables = {entry['table'] for entry in data['entries']}
        self.assertEqual(tables, {'adventuring_gear', 'weapons', 'armor', 'tools', 'mounts_and_vehicles',
                                  'trade_goods', 'food_drink_lodging', 'services', 'lifestyle'})
        for entry in data['entries']:
            self.assertIsInstance(entry['amount'], int)
            self.assertGreater(entry['amount'], 0)
            self.assertIn(entry['unit'], ('cp', 'sp', 'ep', 'gp', 'pp'))

    def test_known_srd_prices(self):
        for name, amount, unit in (('Ale, mug', 4, 'cp'), ('Ale, gallon', 2, 'sp'), ('Longsword', 15, 'gp'),
                                   ('Rope, hempen (50 feet)', 1, 'gp'), ('Inn stay, modest (per day)', 5, 'sp'),
                                   ('Wine, fine (bottle)', 10, 'gp'), ('Chain mail', 75, 'gp'),
                                   ("Thieves' Tools", 25, 'gp'), ('Horse, riding', 75, 'gp'),
                                   ('Silk (1 sq. yd.)', 10, 'gp'), ('Lifestyle, modest (per day)', 1, 'gp')):
            with self.subTest(name=name):
                result = kit_prices.price_for('x', {'srd_entry': name})
                self.assertEqual((result['amount'], result['unit'], result['source']), (amount, unit, 'srd'))
                self.assertTrue(result['basis'].startswith('SRD 5.1 '))

    def test_a_local_variant_is_priced_by_its_closest_entry_and_records_which(self):
        result = kit_prices.price_for('the house "Grave Dirt" stout', {'srd_entry': 'Ale, mug'})
        self.assertEqual(result['item'], 'the house "Grave Dirt" stout')
        self.assertEqual(result['basis'], 'SRD 5.1 food_drink_lodging: Ale, mug')
        with self.assertRaisesRegex(InvalidChange, 'No SRD 5.1 entry'):
            kit_prices.price_for('stout', {'srd_entry': 'Stout, mug'})

    def test_closest_entry_hint(self):
        hint = kit_prices.lookup_hint('How much for a mug of ale?')
        self.assertEqual(hint['closest'][0], 'SRD 5.1 food_drink_lodging: Ale, mug')
        self.assertEqual(kit_prices.lookup_hint('How much is a longsword?')['closest'][0],
                         'SRD 5.1 weapons: Longsword')
        # The entry's head noun must be named: a glass eye is not a glass bottle.
        self.assertEqual(kit_prices.lookup_hint('How much for his glass eye?')['status'], 'unpriced')
        self.assertIn("SRD 5.1 services: Ship's passage (per mile)",
                      kit_prices.lookup_hint('What does passage on a ship cost?')['closest'])


class PrecedenceTests(unittest.TestCase):
    source_prices = [(name, fact) for name, fact in json.loads(FIXTURE.read_text())['numeric_facts'].items()
                     if isinstance(fact, dict)]

    def test_source_adventure_price_beats_everything(self):
        hint = kit_prices.lookup_hint('How much for passage through the door?', self.source_prices)
        self.assertEqual((hint['status'], hint['name'], hint['amounts']), ('source', 'passage_toll', [10]))
        # The ring's worth is the source's, never an SRD metal price.
        hint = kit_prices.lookup_hint('How much for the silver ring?', self.source_prices)
        self.assertEqual((hint['status'], hint['name']), ('source', 'ring_value'))
        result = kit_prices.price_for('toll', {'source_price': {'amount': 10, 'unit': 'gp', 'basis': 'area 6c'},
                                               'srd_entry': 'Road or gate toll'})
        self.assertEqual((result['amount'], result['source']), (10, 'adventure'))

    def test_dmg_official_then_srd_then_formula(self):
        potion = {'impact_kind': 'consumable', 'dice': '2d4+2', 'entry_level': 1, 'category': 'Consumable'}
        official = kit_prices.price_for('Potion of Healing', {'magic_item': {**potion, 'official_price_gp': 50}})
        self.assertEqual((official['amount'], official['source']), (50, 'dmg_official'))
        formula = kit_prices.price_for('Potion of Healing', {'magic_item': potion})
        self.assertEqual((formula['amount'], formula['source']), (70, 'formula'))
        mundane = kit_prices.price_for('rope', {'srd_entry': 'Rope, silk (50 feet)'})
        self.assertEqual((mundane['amount'], mundane['source']), (10, 'srd'))

    def test_unlisted_stays_unpriced_with_a_flag(self):
        self.assertIs(kit_prices.price_for('a dragon egg'), kit_prices.UNPRICED)
        hint = kit_prices.lookup_hint('How much for the stone tub?', self.source_prices)
        self.assertEqual(hint['status'], 'unpriced')
        self.assertIn('do not invent one', hint['flag'])


if __name__ == '__main__':
    unittest.main()
