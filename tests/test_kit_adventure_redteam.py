"""Independent source-authority adversarial checks on the shipped runtime.

All fixtures are synthetic; rejected host tampering is a required invariant.
"""
import tempfile
import unittest
from pathlib import Path

from runtime import kit_adventure as a

SOURCE = Path(__file__).parent / 'fixtures/adventures/lantern_ferry.txt'


class SourceAuthorityReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'kit.sqlite'
        a.import_adventure(self.db, text=SOURCE.read_text(encoding='utf-8'))
        self.index, self.text = a._load(self.db)

    def compile_expect_rejection(self, key, mutate):
        room, provenance = a.draft_room(self.db, key, self.index, self.text)
        mutate(room, provenance)
        with self.assertRaises(a.IngestError):
            a.compile_location(self.db, key, draft={'room': room, 'provenance': provenance}, neighbours=False)

    def test_reject_unsourced_attack_damage_type(self):
        self.compile_expect_rejection('4', lambda room, _: room['actors']['reed_lurker']['stat_block']['attacks'][0].update(type='radiant'))

    def test_reject_unsourced_attack_name(self):
        self.compile_expect_rejection('4', lambda room, _: room['actors']['reed_lurker']['stat_block']['attacks'][0].update(name='meteor smash'))

    def test_reject_unsourced_third_multiattack(self):
        def third(room, source):
            room['actors']['reed_lurker']['stat_block']['attacks'].append(dict(room['actors']['reed_lurker']['stat_block']['attacks'][0]))
            source['fields']['actors.reed_lurker.stat_block.attacks.2'] = dict(source['fields']['actors.reed_lurker.stat_block.attacks.0'])
        self.compile_expect_rejection('4', third)

    def test_reject_reveal_of_source_hidden_creature(self):
        self.compile_expect_rejection('4', lambda room, _: room['actors']['reed_lurker'].update(status='alive', visible=True))

    def test_reject_unsourced_room_link_target_path(self):
        a.compile_location(self.db, '1', neighbours=False)
        self.compile_expect_rejection('2', lambda room, _: room['areas']['to_3']['room_link'].update(room=str(a.room_file(self.db, '1'))))

    def test_reject_unsourced_room_link_target_area(self):
        self.compile_expect_rejection('2', lambda room, _: room['areas']['to_3']['room_link'].update(area='here'))

    def test_reject_unsourced_room_link_adventure_target(self):
        self.compile_expect_rejection('2', lambda room, _: room['areas']['to_3']['room_link']['adventure'].update(location='1'))

    def test_reject_quote_offset_outside_its_location(self):
        room, sidecar = a.draft_room(self.db, '1', self.index, self.text)
        duplicate = sidecar['fields']['facts.seen_1']['quote']
        # Place identical truthful words in a different part of the same book.
        a.import_adventure(self.db, text=duplicate + '\n\n' + SOURCE.read_text(encoding='utf-8'))
        index, text = a._load(self.db)
        room, sidecar = a.draft_room(self.db, '1', index, text)
        self.assertLess(text.index(duplicate), index['locations']['1']['body'][0])
        sidecar['fields']['facts.seen_1']['offset'] = text.index(duplicate)
        with self.assertRaises(a.IngestError):
            a.compile_location(self.db, '1', draft={'room': room, 'provenance': sidecar}, neighbours=False)

    def test_direct_validator_guards_source_triggers(self):
        room, sidecar = a.draft_room(self.db, '2', self.index, self.text)
        room['triggers'][0]['starts_combat'] = False
        self.assertTrue(a.validate(room, sidecar, self.index, self.text))

    def test_old_room_link_not_orphaned_by_source_reimport(self):
        compiled = a.compile_location(self.db, '1', neighbours=False)
        link = a._read_json(compiled['room'])['areas']['to_2']['room_link']
        old_target = Path(link['room'])
        self.assertFalse(old_target.exists())
        rewritten = self.text.replace('A rope bell hangs', 'A brass bell hangs')
        a.import_adventure(self.db, text=rewritten)
        a.ensure_compiled(link)  # Called by room loader when an old room is still active
        # This assertion currently fails: a NEW-SHA room is compiled but old link stays absent.
        self.assertTrue(old_target.is_file())


if __name__ == '__main__':
    unittest.main()
