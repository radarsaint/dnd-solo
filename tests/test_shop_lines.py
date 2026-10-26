"""Shop and appraisal lines. The prices in the fixture are the lock.

A change that moves a Goldscale total, or an SRD rate, fails here. The fixture
is equipment-table names and Goldscale descriptions, not adventure text.
"""
import json
import unittest
from pathlib import Path

from runtime import kit_appraise
from runtime.kit_prices import srd_entry

ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads((ROOT / 'tests/fixtures/shop_lines.json').read_text(encoding='utf-8'))
_CP = {'cp': 1, 'sp': 10, 'gp': 100}

# Totals price() already returned before this stack. A rephrase in the corpus
# has to land on the same number.
_LOCKED = {
    "what's a potion of healing worth?": 70,
    'how much are 3 healing potions?': 210,
    'sell a potion of healing': 35,
    'a dozen potions of healing': 840,
    'potion of greater healing': 425,
    'three potions of greater healing': 1275,
    'how much for a potion of superior healing?': 2200,
    'potion of supreme healing': 9000,
    '+1 longsword uncommon weapon': 1200,
    'longsword, +1 uncommon weapon': 1200,
    'sell qty 2 +1 sword uncommon weapon': 1200,
    'wand of fireballs rare wand 8d6 aoe 7 charges': 157000,
    'price check on a wand of fireballs, rare wand, 8d6 aoe, 7 charges': 157000,
    'cloak of protection uncommon cloak +1': 1400,
    'boots of striding very rare boots broad': 3200,
    'sell +2 shield rare shield 25%': 1400,
}


def _listed(entry, quantity, selling=False):
    per = entry.get('per') or 1
    copper = entry['amount'] * _CP[entry['unit']] * quantity
    if copper % per:
        return None, None
    copper //= per
    if selling:
        copper //= 2  # Brendon's ruling: half the listed price, like Goldscale's 50%
    if copper == 0:
        return 0, 'cp'
    if copper % 100 == 0:
        return copper // 100, 'gp'
    if copper % 10 == 0:
        return copper // 10, 'sp'
    return copper, 'cp'


class ShopLineCorpusTests(unittest.TestCase):
    def test_corpus_has_two_hundred_lines_and_matches(self):
        self.assertGreaterEqual(len(CORPUS), 200)
        for row in CORPUS:
            self.assertEqual(kit_appraise.read_items(row['line']), row['items'], row['line'])

    def test_srd_rows_are_the_listed_rate(self):
        for row in CORPUS:
            for item in row['items']:
                if item['source'] != 'srd':
                    continue
                entry = srd_entry(item['item'])
                self.assertIsNotNone(entry, item['item'])
                self.assertEqual((item['price'], item['unit']), _listed(entry, item['quantity'], item['mode'] == 'sell'), row['line'])

    def test_goldscale_totals_did_not_move(self):
        by_line = {row['line']: row['items'][0] for row in CORPUS}
        for line, price in _LOCKED.items():
            self.assertEqual(by_line[line]['price'], price, line)
            self.assertEqual(by_line[line]['source'], 'goldscale', line)
            got = kit_appraise.price(line)
            total = got['transaction_total'] if got['transaction_total'] is not None else got['final_price']
            self.assertEqual(total, price, line)

    def test_unknown_lines_have_no_price(self):
        unknown = [row for row in CORPUS if row['items'][0]['item'] == 'unknown item']
        self.assertGreaterEqual(len(unknown), 12)
        for row in unknown:
            self.assertIsNone(row['items'][0]['price'], row['line'])


if __name__ == '__main__':
    unittest.main()
