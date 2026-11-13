"""Source authority and versioned-room security regressions.

Synthetic adversarial fixtures cover immutable book facts, provenance, and triggers.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from runtime import kit_adventure as a, kit_rooms

CORPUS = Path(__file__).parent / 'fixtures/adventures/lantern_ferry.txt'


class TestSourceAuthority(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / 'kit.sqlite'
        self.source = CORPUS.read_text(encoding='utf-8')
        a.import_adventure(self.db, text=self.source)
        self.index, self.text = a._load(self.db)

    def bad(self, location, mutate, expected):
        room, cite = a.draft_room(self.db, location, self.index, self.text)
        mutate(room, cite)
        with self.assertRaises(a.IngestError) as caught:
            a.compile_location(self.db, location, draft={'room': room, 'provenance': cite}, neighbours=False)
        self.assertIn(expected, ' '.join(caught.exception.problems))

    def test_hidden_actor_and_attack_semantics_immutable(self):
        for name, edit in (
            ('attack name', lambda r: r['actors']['reed_lurker']['stat_block']['attacks'][0].update(name='meteor smash')),
            ('damage type', lambda r: r['actors']['reed_lurker']['stat_block']['attacks'][0].update(type='radiant')),
            ('number of swings', lambda r: r['actors']['reed_lurker']['stat_block']['attacks'].append(
                dict(r['actors']['reed_lurker']['stat_block']['attacks'][0]))),
            ('visibility', lambda r: r['actors']['reed_lurker'].update(status='alive', visible=True)),
            ('combatant count', lambda r: r['actors'].pop('reed_lurker')),
        ):
            with self.subTest(name):
                self.bad('4', lambda room, _: edit(room), 'draft actors differ')

    def test_navigation_semantics_immutable(self):
        for name, edit in (
            ('target room', lambda r: r['areas']['to_3']['room_link'].update(room='surprise-room.json')),
            ('target area', lambda r: r['areas']['to_3']['room_link'].update(area='here')),
            ('source location', lambda r: r['areas']['to_3']['room_link']['adventure'].update(location='1')),
            ('public exit label', lambda r: r['exits']['way_3']['labels'].update(here='A secret vault opens here.')),
            ('approach description', lambda r: r['areas']['to_3'].update(name='A portal to Rivermead')),
            ('extra area', lambda r: r['areas'].update(unlisted={'name':'Unlisted'})),
        ):
            with self.subTest(name):
                self.bad('2', lambda room, _: edit(room), 'source')

    def test_direct_validator_rejects_trigger_policy_without_db(self):
        room, sidecar = a.draft_room(self.db, '2', self.index, self.text)
        room['triggers'][0]['surprise'] = {'dc': 40}
        self.assertIn('draft triggers differ', ' '.join(a.validate(room, sidecar, self.index, self.text)))

    def test_unsourced_agenda_and_other_blocks_refused(self):
        for name, value in (('agenda', {'agents': {}}), ('combat', {}), ('_hook', 'injected')):
            with self.subTest(name):
                self.bad('1', lambda room, _: room.update({name: value}), 'unsourced room blocks')

    def test_fact_cannot_add_an_alarm_or_hidden_handling(self):
        for edit, fragment in (
            (lambda r: r['facts']['seen_1'].update(alarm={'arrives_in_rounds':0,
                            'responders':[{'who':'Dragon','count':1,'stat_block':{'srd':'bandit'}}]}),
             'unsourced mechanics'),
            (lambda r: r['facts']['seen_1'].update(handling={'nouns':['rain'], 'holds':'dm_1'}),
             'source-derived handling'),
        ):
            self.bad('1', lambda room, _: edit(room), fragment)

    def test_no_word_bag_rephrasing_to_change_what_source_says(self):
        room, cite = a.draft_room(self.db, '1', self.index, self.text)
        original = cite['fields']['facts.seen_1']['quote']
        words = original.split()
        self.assertGreater(len(words), 5)
        room['facts']['seen_1']['text'] = ' '.join(reversed(words[:5]))
        with self.assertRaises(a.IngestError) as caught:
            a.compile_location(self.db, '1', draft={'room': room, 'provenance': cite}, neighbours=False)
        self.assertIn('changes its wording', str(caught.exception))

    def test_fact_offset_must_be_in_same_location(self):
        room, cite = a.draft_room(self.db, '1', self.index, self.text)
        quote = cite['fields']['facts.seen_1']['quote']
        a.import_adventure(self.db, text=quote + '\n\n' + self.source)
        idx, text = a._load(self.db)
        room, cite = a.draft_room(self.db, '1', idx, text)
        cite['fields']['facts.seen_1']['offset'] = text.index(quote)
        self.assertTrue(any('in its location' in m for m in a.validate(room, cite, idx, text, db=self.db)))

    def test_sidecar_authority_and_omitted_actor_refused(self):
        self.bad('4', lambda _, p: p.update(ask_player=['A new terrible monster']),
                 'source-derived gaps or creature references')
        self.bad('4', lambda r, _: r['actors'].clear(), 'draft actors differ')

    def test_snapshot_is_content_addressed_and_reusable(self):
        original = a.compile_location(self.db, '1', neighbours=False)
        original_hash = self.index['sha256']
        original_room = Path(original['room'])
        link = a._read_json(original_room)['areas']['to_2']['room_link']
        self.assertFalse(Path(link['room']).exists())
        revision = self.source.replace('A rope bell hangs', 'A brass bell hangs')
        a.import_adventure(self.db, text=revision)
        a.ensure_compiled(link)
        self.assertTrue(Path(link['room']).is_file())
        old_compiled = kit_rooms.load_link(link)
        self.assertEqual(old_compiled['id'][:12], 'adv-' + original_hash[:8])
        self.assertNotEqual(a._load(self.db)[0]['sha256'], original_hash)
        self.assertEqual(old_compiled['areas']['to_1']['room_link']['adventure']['source_sha256'], original_hash)
        self.assertIn('rope bell', original_room.read_text(encoding='utf-8'))
        self.assertNotIn('brass bell', original_room.read_text(encoding='utf-8'))
        a.compile_location(self.db, '1', neighbours=False)
        self.assertIn('brass bell', a.room_file(self.db, '1').read_text(encoding='utf-8'))

    def test_tampered_versioned_link_not_retargeted(self):
        a.compile_location(self.db, '1', neighbours=False)
        link = a._read_json(a.room_file(self.db, '1'))['areas']['to_2']['room_link']
        link['room'] = str(Path(link['room']).parent / 'other.json')
        a.ensure_compiled(link)
        self.assertFalse(Path(link['room']).exists())

    def test_current_source_corruption_fails_closed(self):
        path = a.folder_for(self.db) / 'source.txt'
        path.write_text(self.source.replace('Rain hisses','Rain stops'), encoding='utf-8')
        with self.assertRaisesRegex(a.IngestError, 'source and index hash'):
            a.compile_location(self.db, '1', neighbours=False)

    def test_archived_snapshot_corruption_fails_closed(self):
        original_sha = self.index['sha256']
        revised = self.source.replace('A rope bell hangs', 'A brass bell hangs')
        a.import_adventure(self.db, text=revised)
        old_text = a.folder_for(self.db) / 'sources' / original_sha / 'source.txt'
        old_text.write_text('malicious', encoding='utf-8')
        with self.assertRaisesRegex(a.IngestError, 'source and index hash'):
            a.compile_location(self.db, '1', neighbours=False, source_sha=original_sha)


if __name__ == '__main__':
    unittest.main()
