"""Private PDF retention and cold-host recovery. All PDF data are synthetic."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from runtime import kit_adventure, kit_skim


class RetainedPdfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'test.sqlite'

    def _ingest(self):
        original = Path(self.tmp.name) / 'uploaded.pdf'
        content = b'%PDF-1.4\n' + b'private synthetic pages\n' * 8
        original.write_bytes(content)
        text = '1. Entry Road\n> A lantern swings above the road.\n2. Lookout\n> A bell rings.\n'
        with mock.patch('runtime.kit_adventure.read_opening', return_value=(text, 'test')):
            result = kit_adventure.ingest_adventure(self.db, pdf=str(original))
        return original, content, result

    def test_deeper_read_uses_owned_verified_copy_after_original_deleted(self):
        original, content, result = self._ingest()
        self.assertEqual(result['source_pdf_sha256'], hashlib.sha256(content).hexdigest())
        stored = kit_adventure.retained_pdf_source(self.db)
        self.assertNotEqual(stored, original)
        self.assertEqual(stored.read_bytes(), content)
        original.unlink()
        with mock.patch('runtime.kit_adventure.read_pdf', return_value=(
                '1. Entry Road\n> A lantern swings above the road.\n2. Lookout\n> A bell rings.\n', 'test')) as reader:
            report = kit_adventure.deepen_index(self.db)
        self.assertEqual(report['stage'], 'index_deep')
        self.assertEqual(Path(reader.call_args.args[0]), stored)

    def test_full_index_preserves_the_accepted_pdf_scene_and_spoken_cursor(self):
        self._ingest()
        opening = 'A lantern swings above the road.'
        scene = {
            'place': {'name': 'road', 'quote': opening},
            'people': [], 'discoveries': [], 'pressures': [],
        }
        result = kit_skim.accept(self.db, {
            'burst': opening, 'source_quote': opening,
            'page_start': 1, 'page_end': 1,
            'alt_starts': [], 'design_start_name': 'Entry Road',
            'scene': scene,
        })
        self.assertEqual(result['stage'], 'skim_accepted', result)
        self.assertIn(opening, kit_skim.opening_line(self.db))
        before = kit_skim._read(self.db)
        self.assertTrue(before['burst_spoken'])
        self.assertTrue(before['beat']['source_verified'])

        full_text = ('1. Entry Road\n> A lantern swings above the road.\n'
                     '2. Lookout\n> A bell rings.\n'
                     '3. Depot\n> Crates fill the depot.\n')
        with mock.patch('runtime.kit_adventure.read_pdf',
                        return_value=(full_text, 'test')):
            indexed = kit_adventure.deepen_index(self.db)
        self.assertEqual(indexed['stage'], 'index_deep')
        self.assertEqual(kit_skim._read(self.db), before)
        index, source = kit_adventure._load(self.db)
        self.assertIn('3. Depot', source)
        self.assertEqual(index['start'], before['scene_key'])

    def test_landing_parses_the_retained_bytes_not_mutable_upload_path(self):
        original = Path(self.tmp.name) / 'host-upload.pdf'
        initial = b'%PDF-1.4\n' + b'original synthetic source\n' * 4
        original.write_bytes(initial)
        text = '1. Entry Road\n> A lantern swings above the road.\n'
        def read_this_exact_source(path, reader='auto'):
            self.assertNotEqual(Path(path), original)
            self.assertEqual(Path(path).read_bytes(), initial)
            original.write_bytes(b'%PDF-1.4\nmodified by outside process')
            return text, 'test'
        with mock.patch('runtime.kit_adventure.read_opening', side_effect=read_this_exact_source):
            report = kit_adventure.ingest_adventure(self.db, pdf=str(original))
        self.assertEqual(kit_adventure.retained_pdf_source(self.db).read_bytes(), initial)
        self.assertEqual(report['source_pdf_sha256'], hashlib.sha256(initial).hexdigest())

    def test_corrupted_retained_pdf_refuses_before_deepening(self):
        _, _, _ = self._ingest()
        copy = kit_adventure.retained_pdf_source(self.db)
        copy.write_bytes(b'%PDF-1.4\ncorrupted\n')
        with self.assertRaisesRegex(kit_adventure.IngestError, 'checksum'):
            kit_adventure.deepen_index(self.db)

    def test_missing_retained_pdf_refuses_instead_of_trusting_old_path(self):
        old, _, _ = self._ingest()
        kit_adventure.retained_pdf_source(self.db).unlink()
        old.write_bytes(b'%PDF-1.4\nchanged on disk\n')
        with self.assertRaisesRegex(kit_adventure.IngestError, 'unavailable'):
            kit_adventure.deepen_index(self.db)

    def test_same_content_is_reused_without_duplicate_copies(self):
        original, _, _ = self._ingest()
        with mock.patch('runtime.kit_adventure.read_opening', return_value=(
                '1. Entry Road\n> A lantern swings above the road.\n', 'test')):
            kit_adventure.ingest_adventure(self.db, pdf=str(original))
        self.assertEqual(len(list((kit_adventure.folder_for(self.db) / 'pdf_sources').glob('*.pdf'))), 1)


if __name__ == '__main__':
    unittest.main()
