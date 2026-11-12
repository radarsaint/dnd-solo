"""Python 3.8 portability guards for Kit's stdlib runtime.

Grammar parsing on a newer Python checks only syntax; an actual Python 3.8
interpreter must still run this module and the full suite before acceptance.
"""
import ast
import importlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimePython38Portability(unittest.TestCase):
    def test_runtime_sources_parse_with_python38_grammar(self):
        for path in sorted((ROOT / 'runtime').rglob('*.py')):
            with self.subTest(path=str(path.relative_to(ROOT))):
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=(3, 8))

    def test_runtime_avoids_python39_only_string_prefix_suffix_methods(self):
        for path in sorted((ROOT / 'runtime').rglob('*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            obsolete = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                        and n.attr in ('removeprefix', 'removesuffix')]
            self.assertFalse(obsolete, '%s uses Python 3.9-only string methods: %r' % (path, obsolete))

    def test_kit_texture_oracle_renders_without_dictionary_union(self):
        # A dictionary-union expression parses as Python 3.8 grammar but
        # crashes at runtime on 3.8. Exercise the exact source of that failure.
        from runtime import kit_texture
        from inspect import getsource
        source = getsource(kit_texture.model_view)
        tree = ast.parse(source)
        dict_unions = [node for node in ast.walk(tree)
                       if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)
                       and (isinstance(node.left, ast.Dict) or isinstance(node.right, ast.Dict))]
        self.assertFalse(dict_unions, 'model_view contains unsupported dictionary union')
        payload = {
            'deal': [{'draw_id': '1', 'entry': 'candidate', 'handle': 'c',
                      'procedure': 'game', 'kit_lean': True}],
            'status': 'selected',
        }
        result = kit_texture.model_view(payload)
        self.assertEqual(result['deal'], [
            {'draw_id': '1', 'entry': 'candidate', 'handle': 'c',
             'procedure': 'game', 'kit_lean': True},
        ])

    def test_goldscale_annotations_import_as_portable_types(self):
        pricing = importlib.import_module('runtime.goldscale.pricing')
        parser = importlib.import_module('runtime.goldscale.parser')
        clarification = importlib.import_module('runtime.goldscale.clarification')
        # Importing these modules itself used to fail on Python 3.8: list[str]
        # and tuple[...] were evaluated as runtime expressions.
        self.assertEqual(pricing.PricingResult.__annotations__['warnings'], 'list[str]')
        self.assertEqual(parser.ItemData.__annotations__['warnings'], 'list[str]')
        self.assertIn('PendingAppraisals', vars(clarification))
        self.assertEqual(len(clarification.PendingKey.__args__), 3)


if __name__ == '__main__':
    unittest.main()
