"""Opening and later interpretations share source-backed native stat resolution."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_scene_contract as contract, kit_skim, kit_combat
from runtime.state_context import InvalidChange

BURST = 'A wolf waits in the courtyard.'
STATS = 'Ash is a wolf with 18 hit points.'


def scene():
    return {'place': {'name': 'courtyard', 'quote': BURST},
            'people': [{'id': 'wolf', 'name': 'wolf', 'quote': BURST,
                'visibility': 'visible', 'kind': 'creature', 'goal': None, 'knowledge': [],
                'source_name': 'Ash', 'identity_evidence': [{'quote': STATS, 'status': 'established'}],
                'statistics': {'srd': 'wolf', 'hp': 18,
                    'evidence': [{'quote': STATS, 'status': 'established'}]}}],
            'discoveries': [], 'pressures': []}


class OpeningStatistics(unittest.TestCase):
    def test_validated_opening_updates_native_stats_and_preserves_actor_id(self):
        reading = scene()
        self.assertEqual(contract.validate(reading, BURST + '\n' + STATS, BURST), [])
        beat = contract.build_beat(reading, BURST, 'Courtyard')
        original = {'id': 'synthetic-court', 'starting_area': 'here', 'areas': {'here': {}},
                    'actors': {'wolf': {'name': 'Wolf', 'location': 'here', 'status': 'alive',
                                        'visible': True, 'stat_block': {'srd': 'wolf'}}},
                    'combat': {'actors': {'wolf': {'hp': 11}}}, 'facts': {}, 'exits': {}}
        unchanged = copy.deepcopy(original)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'room.json'
            path.write_text(json.dumps(original), encoding='utf-8')
            kit_skim._stamp_beat(path, beat)
            projected = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(original, unchanged)
        self.assertEqual(list(projected['actors']), ['wolf'])
        self.assertEqual(projected['actors']['wolf']['name'], 'Ash')
        self.assertEqual(kit_combat.config(projected)['actors']['wolf']['hp'], 18)
        self.assertEqual(projected['actors']['wolf']['statistics_provenance'], reading['people'][0]['statistics'])

    def test_false_missing_or_conditional_stat_evidence_is_rejected(self):
        for fault in ('number', 'boolean', 'base', 'quote', 'condition', 'alias', 'extra'):
            reading = scene(); person = reading['people'][0]; stats = person['statistics']
            if fault == 'number': stats['hp'] = 180
            if fault == 'boolean': stats['hp'] = True
            if fault == 'base': stats['srd'] = 'dragon'
            if fault == 'quote': stats['evidence'][0]['quote'] = 'Ash is a wolf with 180 hit points.'
            if fault == 'condition': stats['evidence'][0]['status'] = 'inferred'
            if fault == 'alias': person['source_name'] = 'Invented'
            if fault == 'extra': stats['armor_class'] = 40
            with self.subTest(fault=fault):
                self.assertTrue(contract.validate(reading, BURST + '\n' + STATS, BURST))

    def test_shared_resolver_without_override_preserves_the_srd_base(self):
        stats = {'srd': 'wolf', 'evidence': [{'quote': STATS}]}
        contract.check_statistics(stats, 'Ash', lambda claim: None)
        self.assertEqual(contract.resolve_statistics(stats)['hp'], 11)
        self.assertNotIn('hp', stats)


if __name__ == '__main__': unittest.main()
