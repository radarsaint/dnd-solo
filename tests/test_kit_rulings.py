"""Prep-time if-rulings and cheap next-move prep. Synthetic fixtures only."""
import tempfile
import unittest
from pathlib import Path
from runtime import kit_adventure, kit_links, kit_prefetch, kit_rulings, kit_skim


def _book():
    """Varied layouts: an opening if-sentence, a party talk ruling, a likely
    'creatures that' line, a DC sentence that must not leak, and a later area."""
    opening = (
        "1. The Ford\n\n"
        "> You step into the ford and feel the silt. Two marsh hounds wait "
        "on the far bank. A stone heron stands in the silt.\n\n"
        "If a character searches the reeds, they find a wet satchel.\n"
        "If the party talks to the miller, he warns them about the latch.\n"
        "Creatures that drink the sluice water grow still.\n"
        "If a character forces the gate, they must succeed on a DC 15 Strength check.\n"
        "The planks run on toward the far side.\n"
    )
    later = (
        "2. The Mill\n\n"
        "The mill is quiet. A rusty wheel turns in the dark sluice.\n"
        "If the characters climb the wheel, they reach the loft unnoticed.\n"
        "A later mention of a ridge wolf does not belong to the opening.\n"
    )
    return "Chapter 1: The Green Cut\n\n" + opening + "\n\\f\n" + later


class RulingGraph(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        # The fixture uses a literal form-feed escape in the file; normalize it.
        self.source = _book().replace('\\f', '\f')
        self.report = kit_adventure.import_adventure(self.db, text=self.source)
        self.index, self.text = kit_adventure._load(self.db)
        self.start = self.index['start']

    def test_import_reports_structural_ruling_counts(self):
        counts = self.report.get('ruling_counts') or kit_rulings.counts(self.index)
        self.assertEqual(counts, self.index.get('ruling_counts') or counts)
        self.assertGreaterEqual(counts['confirmed'], 2)
        self.assertGreaterEqual(counts['likely'], 1)
        self.assertTrue(self.report.get('opening_rulings'))

    def test_search_if_is_confirmed_and_surfaces_verbatim(self):
        hit = kit_rulings.for_action(
            self.db, 'I search the reeds for a satchel.', self.start)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('source_verified'))
        self.assertEqual(hit.get('confidence'), kit_links.CONFIRMED)
        self.assertIn('wet satchel', hit.get('quote'))
        self.assertTrue(kit_links.valid_quote(
            self.text[self.index['locations'][self.start]['body'][0]:
                      self.index['locations'][self.start]['body'][1]],
            hit.get('quote')))
        self.assertFalse(hit.get('has_mechanics'))

    def test_talk_ruling_attaches_to_a_person_trigger(self):
        found = [item for item in kit_rulings.rulings_from(self.index, self.start)
                 if 'miller' in (item.get('quote') or '').casefold()]
        self.assertTrue(found, 'talk ruling missing')
        self.assertEqual(found[0].get('trigger_kind'), 'npc')
        hit = kit_rulings.for_action(self.db, 'I talk to the miller about the latch.', self.start)
        self.assertIsNotNone(hit)
        self.assertIn('warns them about the latch', hit.get('quote'))

    def test_creatures_that_is_likely(self):
        found = [item for item in kit_rulings.rulings_from(self.index, self.start)
                 if 'sluice' in (item.get('quote') or '').casefold()]
        self.assertTrue(found)
        self.assertEqual(found[0].get('confidence'), kit_links.LIKELY)
        hit = kit_rulings.for_action(self.db, 'We drink the sluice water.', self.start)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get('confidence'), kit_links.LIKELY)

    def test_mechanics_ruling_is_recorded_but_flagged(self):
        found = [item for item in kit_rulings.rulings_from(self.index, self.start)
                 if item.get('has_mechanics')]
        self.assertTrue(found)
        hit = kit_rulings.for_action(self.db, 'I force the gate.', self.start)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('has_mechanics'))
        self.assertIn('DC', hit.get('quote') or '')

    def test_a_later_section_ruling_is_not_used_at_the_opening(self):
        hit = kit_rulings.for_action(self.db, 'I climb the wheel to the loft.', self.start)
        self.assertIsNone(hit)
        mill = [key for key, loc in (self.index.get('locations') or {}).items()
                if 'mill' in str(loc.get('name') or '').casefold()]
        self.assertTrue(mill)
        later = kit_rulings.for_action(self.db, 'I climb the wheel to the loft.', mill[0])
        self.assertIsNotNone(later)
        self.assertIn('loft', later.get('quote'))

    def test_unrelated_action_does_not_invent_a_ruling(self):
        self.assertIsNone(kit_rulings.for_action(self.db, 'I wave from the bank.', self.start))


class NextMovePrep(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.source = _book().replace('\\f', '\f')
        kit_adventure.import_adventure(self.db, text=self.source)

    def test_prepare_next_is_cheap_and_covers_obvious_moves(self):
        found = kit_prefetch.prepare_next(self.db)
        self.assertTrue(found and found.get('ready'))
        self.assertGreater(found.get('area_chars') or 0, 0)
        self.assertGreaterEqual(found.get('ruling_n') or 0, 1)
        obvious = found.get('obvious') or {}
        self.assertGreaterEqual(obvious.get('look') or 0, 1)
        self.assertGreaterEqual(obvious.get('talk') or 0, 1)

    def test_landing_and_pick_do_not_stash_next_move_prep(self):
        burst = (
            'You step into the ford and feel the silt. Two marsh hounds wait '
            'on the far bank. A stone heron stands in the silt.'
        )
        first = kit_skim.accept(self.db, {
            'burst': burst, 'source_quote': burst,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Ford',
        })
        # Accept / pick writes the opening; next-move prep waits until the
        # opening is already up (opening_line / Yes).
        self.assertNotIn(first.get('stage'), ('error',), first)
        data = kit_skim._read(self.db)
        self.assertFalse(data.get('next_move_prep'), data.get('next_move_prep'))
        # Direct stash also refuses until the opening has been accepted or spoken.
        kit_skim._write(self.db, {'status': 'skimmed'})
        self.assertIsNone(kit_prefetch.stash(self.db))

    def test_stash_runs_after_the_opening_is_up(self):
        kit_skim._write(self.db, {'status': 'accepted', 'burst_spoken': True,
                                  'scene_key': kit_adventure._load(self.db)[0].get('start')})
        found = kit_prefetch.stash(self.db)
        self.assertTrue(found and found.get('ready'))
        data = kit_skim._read(self.db)
        self.assertTrue((data.get('next_move_prep') or {}).get('ready'))
        # Second call does not rebuild.
        again = kit_prefetch.stash(self.db)
        self.assertEqual(again.get('area_key'), found.get('area_key'))


if __name__ == '__main__':
    unittest.main()
