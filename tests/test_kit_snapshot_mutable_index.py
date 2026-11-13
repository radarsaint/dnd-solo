"""Immutable book-source snapshot, mutable selected scene/index metadata."""
import tempfile
import unittest
from pathlib import Path
from runtime import kit_adventure as a


class IndexMetadataVsSource(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / 'game.sqlite'
        self.beginning = '1. Marsh Road\n> A cart halts beside the trees.\n'
        a.import_adventure(self.db, text=self.beginning)

    def test_reindex_after_skim_metadata_changes_keeps_immutable_source(self):
        original, text = a._load(self.db)
        stored = a.folder_for(self.db) / 'sources' / original['sha256'] / 'index.json'
        saved_snapshot = stored.read_bytes()
        original['start'] = 'scene:book:C'
        original['starts'][0]['default'] = False
        a._write_json(a.folder_for(self.db) / 'index.json', original)
        a.import_adventure(self.db, text=self.beginning +
                           '2. Bridge\n> A watchman stands beside a gate.\n')
        new, full = a._load(self.db)
        self.assertIn('2. Bridge', full)
        self.assertNotEqual(new['sha256'], original['sha256'])
        self.assertEqual(stored.read_bytes(), saved_snapshot)

    def test_tampered_structural_source_index_still_fails_closed(self):
        index, text = a._load(self.db)
        index['pages'][0]['chars'] += 100
        a._write_json(a.folder_for(self.db) / 'index.json', index)
        with self.assertRaisesRegex(a.IngestError, 'immutable adventure source snapshot mismatch'):
            a.import_adventure(self.db, text=self.beginning +
                               '2. Bridge\n> A watchman stands beside a gate.\n')

    def test_modified_archived_source_is_not_tolerated(self):
        index, _ = a._load(self.db)
        archived = a.folder_for(self.db) / 'sources' / index['sha256'] / 'source.txt'
        archived.write_text('corrupt', encoding='utf-8')
        with self.assertRaisesRegex(a.IngestError, 'source and index hash'):
            a.import_adventure(self.db, text=self.beginning + '2. Bridge\n')


if __name__ == '__main__':
    unittest.main()
