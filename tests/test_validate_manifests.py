"""Current manifest shape, privacy rules, and corrupt-index rejection."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_manifests import ROOT, validate_manifests


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = ['assets/maps/index.json', 'assets/art/index.json', 'assets/handouts/index.json']
        self.data = {path: json.loads((ROOT / path).read_text()) for path in self.paths}

    def validate(self):
        for path, data in self.data.items():
            destination = self.root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(data))
        return validate_manifests(self.root)

    def test_current_indexes_pass_without_the_private_binaries(self):
        self.assertEqual(self.validate(), {'maps': 52, 'art': 33, 'handouts': 2})

    def test_wrong_version_and_old_flat_shape_fail(self):
        data = self.data[self.paths[0]]
        data['schema_version'] = 1
        with self.assertRaisesRegex(ValueError, 'unsupported schema_version'):
            self.validate()
        data['schema_version'] = 2
        data['levels'] = []
        with self.assertRaisesRegex(ValueError, 'levels object required'):
            self.validate()

    def test_duplicate_id_and_traversal_path_fail(self):
        data = next(iter(self.data[self.paths[0]]['levels'].values()))
        data['player']['id'] = data['dm']['id']
        with self.assertRaisesRegex(ValueError, 'duplicate id'):
            self.validate()
        data['player']['id'] += '-player'
        data['player']['path'] = 'assets/maps/../private.png'
        with self.assertRaisesRegex(ValueError, 'invalid asset path'):
            self.validate()

    def test_map_visibility_and_knowledge_gate_are_required(self):
        data = next(iter(self.data[self.paths[0]]['levels'].values()))
        data['dm']['visibility'] = 'player_presentation'
        with self.assertRaisesRegex(ValueError, 'private geometry authority'):
            self.validate()
        data['dm']['visibility'] = 'dm_only'
        data['player']['knowledge_gated'] = False
        with self.assertRaisesRegex(ValueError, 'knowledge gated'):
            self.validate()

    def test_index_counts_and_handout_reveal_rules_are_checked(self):
        art = self.data[self.paths[1]]
        art['migration']['indexed_entity_assets'] += 1
        with self.assertRaisesRegex(ValueError, 'count does not match'):
            self.validate()
        art['migration']['indexed_entity_assets'] -= 1
        self.data[self.paths[2]]['handouts'][0].pop('reveal_rule')
        with self.assertRaisesRegex(ValueError, 'reveal rule required'):
            self.validate()


if __name__ == '__main__':
    unittest.main()
