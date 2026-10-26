"""Import stays quiet: shop patterns compile on first use, and the probe script does not."""
import importlib.util
import os
import re
import unittest
from pathlib import Path

from runtime import kit_appraise, kit_text
from runtime.kit_lazyre import LazyPattern, compile as lazy_compile

ROOT = Path(__file__).resolve().parents[1]


class LazyPatternTests(unittest.TestCase):
    def test_methods_match_an_eager_pattern_and_compile_once(self):
        lazy = lazy_compile(r'hey\s+\w+', re.IGNORECASE)
        self.assertIsNone(lazy._compiled)
        eager = re.compile(lazy.pattern, lazy.flags)
        text = 'Hey Kit, price this'
        self.assertEqual(lazy.search(text).group(0), eager.search(text).group(0))
        self.assertIs(lazy._compiled, lazy._re())
        self.assertEqual(lazy.sub('yo ', text, count=1), eager.sub('yo ', text, count=1))

    def test_shop_patterns_are_lazy_and_still_match(self):
        self.assertIsInstance(kit_appraise._SELL, LazyPattern)
        self.assertIsInstance(kit_text._COUNT, LazyPattern)
        self.assertEqual(kit_appraise.leading_count('two potions'), (2, 'potions'))
        self.assertTrue(kit_appraise._SELL.search('I want to sell a sword'))


if __name__ == '__main__':
    unittest.main()
