"""v0.11.1: fast first play. One-command prepare cached per book hash, the opening's
place named for where play starts, and every scene item shape in the skim request.

Original synthetic source only. No published adventure text.
"""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_adventure, kit_prep, kit_skim

OPENING = (
    "PART 1: THE LONG ROAD\n"
    "> You have walked the north road since dawn. Ahead, a cart lies on its side across the ruts.\n"
    "> Crows lift from the ditch as you come near.\n"
    "Two bandits hide in the ditch, one on each side of the road. They wait until someone "
    "nears the cart and then attack. They were paid in Millbrook.\n"
    "\n"
    "WATCH TOWER\n"
    "The bandits came from an old watch tower a mile north. Its door hangs open and the stair is dark.\n"
    "\n"
    "1. Tower Gate\n"
    "> A rusted gate blocks the tower stair.\n"
    "The gate is locked.\n"
    "\f"
    "PART 2: MILLBROOK\n"
    "> A mill wheel turns slowly over brown water. Smoke rises from a dozen chimneys.\n"
    "The town is quiet and wary of strangers.\n"
    "\n"
    "MARKET SQUARE\n"
    "Stalls line the square.\n"
    "\n"
    "1. Mill House\n"
    "> Flour dust hangs in the air.\n"
)


class OpeningPlaceName(unittest.TestCase):
    """A part's unnumbered opening with its own read-aloud, before a later site heading
    (a two-column page can print that heading beside the opening)."""

    def setUp(self):
        self.index = kit_adventure.build_index(kit_adventure.prepare_source(OPENING))
        self.start = self.index['locations'][self.index['start']]

    def test_the_opening_is_named_for_its_part_not_the_later_site(self):
        self.assertEqual(self.start['name'], 'The Long Road')
        self.assertNotEqual(self.start['name'].casefold(), 'watch tower')
        self.assertEqual(self.start['heading'], 'WATCH TOWER')

    def test_its_creatures_stay_even_when_a_later_part_is_named_beside_them(self):
        self.assertIn('bandit', [c['name'] for c in self.start['creatures']])

    def test_a_part_with_no_boxed_lead_in_keeps_its_heading(self):
        text = OPENING.replace(
            '> You have walked the north road since dawn. Ahead, a cart lies on its side across the ruts.\n'
            '> Crows lift from the ditch as you come near.\n',
            'This part runs along the north road, where a cart lies overturned.\n')
        index = kit_adventure.build_index(kit_adventure.prepare_source(text))
        self.assertEqual(index['locations'][index['start']]['name'], 'WATCH TOWER')


class PrepareCache(unittest.TestCase):
    def setUp(self):
        from test_kit_adventure_pdf import make_pdf
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.cache = root / 'cache'
        self.pdf = root / 'book.pdf'
        self.pdf.write_bytes(make_pdf([
            [('text', 70, 735, '1. North Road', 11),
             ('text', 70, 700, 'A lantern lights the wagon road.', 9)],
            [('text', 70, 735, '2. Bridge', 11),
             ('text', 70, 700, 'A river roars beneath the bridge.', 9)],
        ]))
        self.root = root

    def _prepare(self, name):
        db = self.root / name / 'kit.sqlite'
        db.parent.mkdir()
        return db, kit_prep.prepare(str(db), str(self.pdf), reader='pdftotext', root=str(self.cache))

    def test_one_command_ingests_and_indexes_and_times_each_step(self):
        db, report = self._prepare('a')
        self.assertEqual(report['stage'], 'adventure_prepared')
        self.assertFalse(report['cached'])
        self.assertTrue(report['index_complete'])
        for step in ('hash_ms', 'ingest_ms', 'index_ms', 'skim_request_ms'):
            self.assertIn(step, report['steps_ms'])
        self.assertEqual(report['table_line'], kit_skim.LANDING)
        self.assertTrue(report['cache_saved'])

    def test_the_same_book_in_a_fresh_save_restores_from_the_cache(self):
        first, _ = self._prepare('a')
        second, report = self._prepare('b')
        self.assertTrue(report['cached'])
        self.assertTrue(report['index_complete'])
        self.assertNotIn('ingest_ms', report['steps_ms'])
        # Every cached path now points at the new save, never the old one.
        folder = kit_adventure.folder_for(second)
        for path in folder.rglob('*.json'):
            self.assertNotIn(str(kit_adventure.folder_for(first)), path.read_text(encoding='utf-8'), path)
        self.assertIsNotNone(kit_adventure.retained_pdf_source(second))
        self.assertTrue(kit_adventure.readiness(second)['index_complete'])

    def test_an_accepted_skim_is_cached_with_the_book(self):
        db, _ = self._prepare('a')
        kit_prep.after_skim(str(db), {'stage': 'skim_accepted'})
        meta = json.loads((self.cache / kit_prep._entry_name(kit_prep.book_sha(self.pdf)) / 'meta.json').read_text())
        self.assertEqual(meta['stage'], 'skim_accepted')

    def test_a_save_not_prepared_through_prepare_is_never_cached(self):
        db = self.root / 'plain' / 'kit.sqlite'
        db.parent.mkdir()
        kit_adventure.ingest_adventure(str(db), pdf=str(self.pdf), reader='pdftotext')
        kit_prep.after_skim(str(db), {'stage': 'skim_accepted'})
        self.assertFalse(self.cache.exists())


class SceneShape(unittest.TestCase):
    def test_every_scene_item_shape_is_in_the_request(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        shape = kit_skim.request_for(Path(folder.name) / 'kit.sqlite')['scene_shape']
        self.assertEqual(set(shape['discoveries'][0]), {'quote', 'status'})
        self.assertEqual(set(shape['pressures'][0]), {'kind', 'quote', 'status', 'actors', 'activation'})
        self.assertEqual(set(shape['people'][0]['knowledge'][0]), {'quote', 'status'})


if __name__ == '__main__':
    unittest.main()
