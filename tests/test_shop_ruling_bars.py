"""Acceptance bars for the shop rebuild. Each of these failed on main before it."""
import unittest

from runtime import kit_appraise


class ShopRulingBars(unittest.TestCase):

    def test_mundane_sell_is_half_the_srd_price(self):
        # Longsword lists at 15 gp; Brendon's ruling sells it for half.
        self.assertEqual(kit_appraise.appraise('sell my longsword'),
                         'longsword sells for 7 gp 5 sp.\nSelling is half the listed price.')

    def test_ambiguous_name_asks_which_entry(self):
        self.assertEqual(kit_appraise.appraise('how much is a rope'),
                         'Which one: hempen rope (50 feet) (1 gp) or silk rope (50 feet) (10 gp)?')

    def test_unlisted_name_is_unknown_not_a_neighbor(self):
        row = kit_appraise.read_items('blorbo')[0]
        self.assertEqual(row['item'], 'unknown item')
        self.assertIsNone(row['price'])


if __name__ == '__main__':
    unittest.main()
