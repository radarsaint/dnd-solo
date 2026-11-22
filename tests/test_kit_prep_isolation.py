"""Original synthetic preparation: no book or game data."""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_adventure, kit_prep


class CacheIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = self.root / 'cache'
        self.db = self.root / 'first.sqlite'
        self.folder = kit_adventure.folder_for(self.db)
        self.folder.mkdir()
        self.sha = 'a' * 64
        (self.folder / 'source.pdf.json').write_text(json.dumps({'sha256': self.sha}))
        self.mutable = self.folder / 'paths.json'
        self.original = {'db': str(self.db.resolve()), 'state': 'book-prepared'}
        self.mutable.write_text(json.dumps(self.original))
        self.entry = kit_prep.save(self.db, 'indexed', root=self.cache)

    def test_session_writes_do_not_change_cached_preparation(self):
        self.mutable.write_text(json.dumps({'state': 'session-only'}))
        cached = self.entry / 'adventure' / 'paths.json'
        self.assertEqual(json.loads(cached.read_text()), self.original)

    def test_restore_does_not_rewrite_the_first_save_or_cache(self):
        second = self.root / 'second.sqlite'
        kit_prep.restore(second, self.sha, root=self.cache)
        self.assertEqual(json.loads(self.mutable.read_text()), self.original)
        cached = self.entry / 'adventure' / 'paths.json'
        self.assertEqual(json.loads(cached.read_text()), self.original)
        restored = kit_adventure.folder_for(second) / 'paths.json'
        self.assertEqual(json.loads(restored.read_text())['db'], str(second.resolve()))
        restored.write_text(json.dumps({'state': 'second-session-only'}))
        self.assertEqual(json.loads(cached.read_text()), self.original)

    def test_reader_requests_use_separate_cache_entries(self):
        self.assertNotEqual(kit_prep._entry_name(self.sha, reader='stdlib'),
                            kit_prep._entry_name(self.sha, reader='pdfplumber'))

    def test_a_different_reader_request_cannot_restore_this_entry(self):
        second = self.root / 'second.sqlite'
        self.assertIsNone(kit_prep.restore(second, self.sha, root=self.cache, reader='stdlib'))
        self.assertFalse(kit_adventure.folder_for(second).exists())

    def test_after_skim_retains_the_requested_reader_cache(self):
        kit_prep.save(self.db, 'indexed', root=self.cache, reader='stdlib')
        kit_prep.after_skim(self.db, {'stage': 'skim_accepted'})
        entry = self.cache / kit_prep._entry_name(self.sha, reader='stdlib')
        self.assertEqual(json.loads((entry / 'meta.json').read_text())['stage'], 'skim_accepted')


if __name__ == '__main__':
    unittest.main()
