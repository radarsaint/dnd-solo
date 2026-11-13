"""Canonical source-authority, action economy, and versioned-room regressions.

All fixtures are synthetic and must run on the shipped runtime.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from runtime import kit_adventure


CORPUS = Path(__file__).resolve().parent / 'fixtures/adventures/lantern_ferry.txt'


class AdventureSourceIntegrity(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.text = CORPUS.read_text(encoding='utf-8')
        kit_adventure.import_adventure(self.db, text=self.text)
        self.index, self.text = kit_adventure._load(self.db)

    def test_reimport_different_adventure_does_not_reuse_cached_scene(self):
        old = kit_adventure.compile_location(self.db, '1', neighbours=False)
        old_path = Path(old['room'])
        old_id = old['room_id']
        revised = self.text.replace('A rope bell hangs', 'A brass bell hangs')
        self.assertNotEqual(revised, self.text)
        new_import = kit_adventure.import_adventure(self.db, text=revised)
        self.assertEqual(new_import['locations_compiled'], [])
        new_path = kit_adventure.room_file(self.db, '1')
        self.assertNotEqual(old_path, new_path)
        self.assertTrue(old_path.exists(), 'old campaign cache should be preserved for diagnosis')
        self.assertFalse(new_path.exists())
        rebuilt = kit_adventure.compile_location(self.db, '1', neighbours=False)
        self.assertNotEqual(rebuilt['room_id'], old_id)
        self.assertIn('brass bell', new_path.read_text(encoding='utf-8'))
        self.assertNotIn('brass bell', old_path.read_text(encoding='utf-8'))

    def test_rejects_host_demoting_a_secret_exit(self):
        room, sidecar = kit_adventure.draft_room(self.db, '2', self.index, self.text)
        self.assertTrue(room['exits']['way_3']['secret'])
        room['exits']['way_3']['secret'] = False
        with self.assertRaises(kit_adventure.IngestError) as error:
            kit_adventure.compile_location(self.db, '2', draft={'room': room, 'provenance': sidecar})
        self.assertIn('secret flag disagrees with the source', ' '.join(error.exception.problems))

    def test_rejects_host_switching_exit_endpoints(self):
        room, sidecar = kit_adventure.draft_room(self.db, '2', self.index, self.text)
        room['exits']['way_3']['areas'] = ['here', 'to_1']
        with self.assertRaises(kit_adventure.IngestError) as error:
            kit_adventure.compile_location(self.db, '2', draft={'room': room, 'provenance': sidecar})
        self.assertIn('changes source connection endpoints', ' '.join(error.exception.problems))

    def test_rejects_false_offset_even_when_quote_is_genuine(self):
        room, sidecar = kit_adventure.draft_room(self.db, '1', self.index, self.text)
        sidecar['fields']['facts.seen_1']['offset'] = 0
        with self.assertRaises(kit_adventure.IngestError) as error:
            kit_adventure.compile_location(self.db, '1', draft={'room': room, 'provenance': sidecar})
        self.assertIn('source offset does not identify', ' '.join(error.exception.problems))

    def test_rejects_encounter_trigger_authoring_without_source(self):
        room, sidecar = kit_adventure.draft_room(self.db, '2', self.index, self.text)
        self.assertTrue(room['triggers'])
        room['triggers'][0]['starts_combat'] = False
        with self.assertRaises(kit_adventure.IngestError) as error:
            kit_adventure.compile_location(self.db, '2', draft={'room': room, 'provenance': sidecar})
        self.assertIn('draft triggers differ', ' '.join(error.exception.problems))
        room, sidecar = kit_adventure.draft_room(self.db, '2', self.index, self.text)
        room['triggers'][0]['surprise'] = {'dc': 30}
        with self.assertRaises(kit_adventure.IngestError) as error:
            kit_adventure.compile_location(self.db, '2', draft={'room': room, 'provenance': sidecar})
        self.assertIn('draft triggers differ', ' '.join(error.exception.problems))

    def test_alternative_weapon_actions_do_not_become_extra_swings(self):
        source = ("Cliff Gremlin\nArmor Class 12\nHit Points 18\n"
                  "Bite. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. "
                  "Hit: 6 (1d6 + 3) piercing damage.\n"
                  "Claw. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. "
                  "Hit: 5 (1d4 + 3) slashing damage.\n")
        block, provenance, warnings = kit_adventure.parse_stat_block(source, {'offset': 0})
        self.assertEqual([attack['name'] for attack in block['attacks']], ['bite'])
        self.assertIn('alternatives', ' '.join(warnings))
        self.assertEqual(list(provenance['attacks.0']), ['offset', 'quote'])

    def test_simple_book_multiattack_preserves_exact_named_swings(self):
        original = self.index['stat_blocks']['reed lurker']
        block, provenance, warnings = kit_adventure.parse_stat_block(self.text, original)
        self.assertEqual([attack['name'] for attack in block['attacks']], ['bite', 'tail'])
        self.assertFalse(any('Multiattack wording cannot' in w for w in warnings))
        self.assertTrue(any('Recharge' in w for w in warnings))

    def test_unsupported_multiattack_defaults_to_one_swing_and_flags_it(self):
        source = ("Cliff Gremlin\nArmor Class 12\nHit Points 18\n"
                  "Multiattack. The creature makes three attacks of its choice.\n"
                  "Bite. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. "
                  "Hit: 6 (1d6 + 3) piercing damage.\n"
                  "Claw. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. "
                  "Hit: 5 (1d4 + 3) slashing damage.\n")
        block, _, warnings = kit_adventure.parse_stat_block(source, {'offset': 0})
        self.assertEqual(len(block['attacks']), 1)
        self.assertIn('cannot be safely executed', ' '.join(warnings))

    def test_baseline_deterministic_locations_still_compile(self):
        for key in ('1', '2', '3', '4'):
            with self.subTest(key=key):
                result = kit_adventure.compile_location(self.db, key, neighbours=False)
                self.assertTrue(Path(result['room']).is_file())


if __name__ == '__main__':
    unittest.main()
