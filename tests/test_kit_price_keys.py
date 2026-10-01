"""QA PR #15 items 4 and 5: price keys name the item asked about, whole items only,
tiers keyed by the tier quoted, whole-number amounts in spoken forms, and one fact
normalization for the runtime ledger and the validator."""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_detail, kit_prices, kit_texture
from runtime.kit_detail import check_detail, check_detail_answer
from runtime.state_context import InvalidChange, Runtime, normalize_fact
from test_kit_agent import FIXTURE
from test_kit_detail import TAVERN, decide, invention, session


class PriceKeyTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.runtime = session(TAVERN)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.runtime.close)
        self.state = self.runtime.load()[1]

    def oracle(self, ask, state=None):
        return kit_texture.oracle_packet(ask, TAVERN, state or self.state, 'social',
                                         price_lookup=kit_prices.lookup_hint)

    def test_the_slot_is_the_whole_item_asked_about(self):
        oracle = self.oracle('How much is a wand of fireballs?')
        self.assertEqual(oracle['slot'], 'taproom/price/wand_of_fireballs')
        self.assertEqual(oracle['status'], 'unpriced', '"Wand" (10 gp) is not a wand of fireballs')
        self.assertEqual(self.oracle('How much for that silver ring?')['slot'], 'taproom/price/silver_ring')

    def test_worth_and_price_questions_open_the_oracle(self):
        # Fix-pass host play: "What is that silver ring worth?" opened no oracle.
        for ask in ('What is that silver ring worth?', "What's the price of that silver ring?",
                    'What would that silver ring go for?'):
            with self.subTest(ask=ask):
                self.assertTrue(kit_detail.asks_for_detail(ask))
                self.assertEqual(self.oracle(ask)['slot'], 'taproom/price/silver_ring')
        # A bargain is not a price question.
        self.assertFalse(kit_detail.asks_for_detail('I could help you get rid of Harria. What is that worth?'))

    def test_whole_item_matching(self):
        self.assertEqual(kit_prices.whole_item_matches('How much for a silver ring?'), [])
        self.assertEqual(kit_prices.whole_item_matches('How much is a wand of fireballs?'), [])
        self.assertEqual([entry['name'] for entry in kit_prices.whole_item_matches('What does a signet ring cost?')],
                         ['Signet ring'])
        self.assertEqual([entry['name'] for entry in kit_prices.whole_item_matches('How much for a pint of beer?')],
                         ['Ale, mug'])
        self.assertEqual(kit_prices.lookup_hint('How much for a silver ring?')['status'], 'unpriced')

    def test_inn_tiers_are_keyed_by_the_tier_quoted(self):
        ask = 'How much for a room at the inn?'
        oracle = self.oracle(ask)
        self.assertEqual(oracle['slot'], 'taproom/price/room_at_inn')
        self.assertEqual(len(oracle['price']['tiers']), 6)
        quote = {'item': 'room upstairs', 'srd_entry': 'Inn stay, modest (per day)', 'magic': 'none'}
        fact = 'A modest room upstairs is five silver a night.'
        wrong = decide(ask, oracle['slot'], 'priced',
                       [invention(oracle['slot'], fact, kind='price', basis='SRD 5.1 inn stay, modest tier',
                                  scope='location')], price_quote=[quote])
        with self.assertRaisesRegex(InvalidChange, 'one tier of several'):
            check_detail(wrong, ask, 'social', TAVERN, self.state, (), json.dumps(TAVERN) + ask, ['barkeep'], oracle)
        right = decide(ask, oracle['slot'], 'priced',
                       [invention(oracle['slot'] + '/modest', fact, kind='price',
                                  basis='SRD 5.1 inn stay, modest tier', scope='location')], price_quote=[quote])
        check_detail(right, ask, 'social', TAVERN, self.state, (), json.dumps(TAVERN) + ask, ['barkeep'], oracle)
        events = kit_detail.canon_events(right, 'p1', oracle)
        self.assertEqual(events[0]['slot'], 'taproom/price/room_at_inn/modest')
        self.assertEqual(events[0]['price']['amount'], 5)
        self.runtime.commit('p1', 0, events)
        state = self.runtime.load()[1]
        self.assertEqual(self.oracle('How much for a modest room at the inn?', state)['status'], 'canon_supplied')
        self.assertEqual(self.oracle('How much for a room at the inn?', state)['status'], 'canon_supplied')
        self.assertEqual(self.oracle('How much for a wealthy room at the inn?', state)['status'], 'priced',
                         'another tier is its own price')
        check_detail_answer([{'speaker': 'Barkeep', 'text': 'Five silver a night, modest, clean sheets.'}],
                            right, ask)
        with self.assertRaisesRegex(InvalidChange, 'literal question'):
            check_detail_answer([{'speaker': 'Barkeep', 'text': 'Five copper a night for the modest room.'}],
                                right, ask)

    def test_amounts_are_whole_numbers_in_spoken_forms(self):
        quote25 = {'amount': 25, 'unit': 'gp'}
        self.assertIsNone(kit_detail.quote_in('The ring is 125 gp.', [quote25]))
        self.assertEqual(kit_detail.quote_in('The ring is 25 gp.', [quote25]), quote25)
        self.assertEqual(kit_detail.quote_in('Five silver.', [{'amount': 5, 'unit': 'sp'}])['amount'], 5)
        big = {'amount': 63000, 'unit': 'gp'}
        self.assertEqual(kit_detail.quote_in('That wand is 63,000 gp.', [big]), big)
        self.assertEqual(kit_detail.quote_in('Sixty-three thousand gold, firm.', [big]), big)


class LedgerNormalizationTests(unittest.TestCase):
    def test_one_normalization_for_runtime_and_validator(self):
        self.assertEqual(normalize_fact('The toll is \u201c10 gp\u201d.'), normalize_fact('the toll is "10 gp"'))
        self.assertNotEqual(normalize_fact('The toll is 10 gp.'), normalize_fact('The toll is 12 gp.'))

    def test_restating_canon_in_another_form_is_not_a_change(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        entry = {'type': 'canon_entry', 'slot': 'area_06c/card_table/cloth', 'kind': 'object',
                 'fact': 'The felt is Waterdhavian green.', 'basis': 'DM choice: the source names no cloth',
                 'public': True, 'scope': 'location', 'procedure': None, 'change_reason': None,
                 'choice': 'self', 'roots': [], 'price': None, 'evidence': 'test'}
        runtime.commit('c1', 0, [entry])
        # Same fact, different case, quotes and final stop: the runtime and the validator agree.
        restated = {**entry, 'fact': 'the felt is Waterdhavian green'}
        runtime.commit('c2', 1, [restated])
        self.assertEqual(runtime.load()[1]['canon']['area_06c/card_table/cloth']['revision'], 1)
        state = runtime.load()[1]
        detail = {**kit_detail.NO_DETAIL, 'inventions': [{**{k: restated[k] for k in (
            'slot', 'kind', 'fact', 'basis', 'public', 'scope')}, 'procedure': 'none', 'change_reason': 'none'}]}
        kit_detail._check_inventions(detail, runtime.source(), state, (), {}, 'self',
                                     'area_06c/card_table/cloth', [])


if __name__ == '__main__':
    unittest.main()
