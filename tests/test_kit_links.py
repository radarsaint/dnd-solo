"""Prep-time link graph and one-hop play lookup. Synthetic fixtures only."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_adventure, kit_links, kit_opening, kit_skim


def _book():
    """Varied layouts: opening names, appendix block, cross-page body,
    a trigger-anchored sidebar, and an orphan sidebar with no anchor."""
    opening = (
        "1. The Ford\n\n"
        "> You step into the ford. Two marsh hounds (see the Marsh Hound "
        "stat block) wait on the far bank. A stone heron stands in the silt.\n\n"
        "The planks run on toward the far side."
    )
    continued = (
        "The water is still past the knee. A way leads to area 2 "
        "(see area 2). If the characters search the reeds, they find a wet satchel.\n\n"
        "Sidebar: The Wet Satchel\n"
        "If the characters search the reeds, the satchel holds a folded note "
        "about the bell. The note is damp and unsigned.\n"
    )
    later = (
        "2. The Mill\n\n"
        "The mill is quiet. A rusty wheel turns in the dark sluice. "
        "A later mention of a ridge wolf does not belong to the opening.\n\n"
        "Appendix: Creatures\n\n"
        "Marsh Hound\n"
        "Armor Class 13\n"
        "Hit Points 22 (4d8+4)\n"
        "Speed 40 ft.\n"
        "Bite. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. "
        "Hit: 6 (1d6 + 3) piercing damage.\n\n"
        "The marsh hound is a gaunt hunting dog with weed in its coat.\n\n"
        "Stone Heron\n"
        "Armor Class 12\n"
        "Hit Points 9 (2d8)\n"
        "Speed 20 ft.\n"
        "Beak. Melee Weapon Attack: +3 to hit, reach 5 ft., one target. "
        "Hit: 4 (1d4 + 2) piercing damage.\n\n"
        "The stone heron is a still, pale wader.\n\n"
        "Ridge Wolf\n"
        "Armor Class 14\n"
        "Hit Points 18 (4d8)\n"
        "Speed 50 ft.\n"
        "Bite. Melee Weapon Attack: +5 to hit, reach 5 ft., one target. "
        "Hit: 7 (1d8 + 3) piercing damage.\n\n"
        "The ridge wolf hunts the high path only.\n"
    )
    orphan = (
        "Sidebar: An Unmoored Note\n"
        "Someone wrote a rumor about a distant city here. Nothing nearby "
        "names it, asks about it, or points to it.\n\n"
    )
    front = "Chapter 1: The Green Cut\n\n"
    return orphan + front + opening + "\n\f\n" + continued + "\n" + later



def _book_without_usable_boxes():
    """Same web as _book, but the opening has no player-facing '>' line.

    A boxed DC/procedure line keeps the section playable in the index, while
    the actual start the player can stand in lives in the recorded body.
    """
    opening = (
        "1. The Ford\n\n"
        "> If the players read this, the DC is 15 and they roll a d20.\n\n"
        "You step into the ford and feel the silt. Two marsh hounds wait on the far bank. "
        "A stone heron stands in the silt.\n\n"
        "The planks run on toward the far side."
    )
    continued = (
        "The water is still past the knee. A way leads to area 2 "
        "(see area 2). If the characters search the reeds, they find a wet satchel.\n\n"
        "Sidebar: The Wet Satchel\n"
        "If the characters search the reeds, the satchel holds a folded note "
        "about the bell. The note is damp and unsigned.\n"
    )
    later = (
        "2. The Mill\n\n"
        "The mill is quiet. A rusty wheel turns in the dark sluice. "
        "A later mention of a ridge wolf does not belong to the opening.\n\n"
        "Appendix: Creatures\n\n"
        "Marsh Hound\n"
        "Armor Class 13\n"
        "Hit Points 22 (4d8+4)\n"
        "Speed 40 ft.\n"
        "Bite. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. "
        "Hit: 6 (1d6 + 3) piercing damage.\n\n"
        "The marsh hound is a gaunt hunting dog with weed in its coat.\n"
    )
    return "Chapter 1: The Green Cut\n\n" + opening + "\n\f\n" + continued + "\n" + later


class LinkGraph(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.report = kit_adventure.import_adventure(self.db, text=_book())
        self.index, self.text = kit_adventure._load(self.db)
        self.start = self.index['start']

    def test_import_reports_structural_counts(self):
        counts = self.report.get('link_counts') or kit_links.counts(self.index)
        self.assertEqual(counts, self.index.get('link_counts') or counts)
        self.assertGreaterEqual(counts['confirmed'], 2)
        self.assertGreaterEqual(counts['likely'], 1)
        self.assertGreaterEqual(counts['unlinked'], 1)
        self.assertEqual(counts['unlinked'],
                         sum(1 for box in self.index['boxes'] if box.get('unlinked')))

    def test_cross_page_continuation_is_a_confirmed_hop(self):
        hops = [link for link in kit_links.links_from(self.index, self.start)
                if link.get('kind') == 'continuation']
        self.assertEqual(len(hops), 1, hops)
        self.assertEqual(hops[0]['confidence'], kit_links.CONFIRMED)
        span = kit_links.load_hop(self.index, self.text, hops[0])
        self.assertIn('still past the knee', span)
        self.assertNotIn('You step into the ford', span)
        self.assertTrue('\f' in self.text[self.index['locations'][self.start]['body'][0]
                                           :self.index['locations'][self.start]['body'][1]]
                        or hops[0]['to_span'][0] > 0)

    def test_opening_stat_block_name_links(self):
        names = [link for link in kit_links.links_from(self.index, self.start)
                 if link.get('kind') == 'name']
        subjects = {link['subject'].casefold(): link for link in names}
        self.assertIn('marsh hound', subjects)
        self.assertEqual(subjects['marsh hound']['confidence'], kit_links.CONFIRMED)
        self.assertIn('stone heron', subjects)
        self.assertEqual(subjects['stone heron']['confidence'], kit_links.LIKELY)
        later = [link for link in self.index['links']
                 if link.get('kind') == 'name'
                 and 'ridge wolf' in (link.get('subject') or '').casefold()]
        self.assertEqual(later, [], later)

    def test_explicit_area_pointer_resolves(self):
        pointers = [link for link in kit_links.links_from(self.index, self.start)
                    if link.get('kind') == 'pointer']
        self.assertTrue(any(link.get('to_key') and link['confidence'] == kit_links.CONFIRMED
                            for link in pointers), pointers)
        sections = [link for link in pointers
                    if link.get('to_kind') == 'section' and link.get('to_key')]
        self.assertTrue(sections, pointers)
        span = kit_links.load_hop(self.index, self.text, sections[0])
        self.assertIn('rusty wheel', span)

    def test_trigger_sidebar_is_confirmed_and_orphan_is_unlinked(self):
        boxes = self.index['boxes']
        self.assertGreaterEqual(len(boxes), 2)
        by_title = {box['title'].casefold(): box for box in boxes}
        self.assertTrue(any('wet satchel' in title for title in by_title), by_title)
        self.assertTrue(any('unmoored' in title for title in by_title), by_title)
        satchel = next(box for box in boxes if 'wet satchel' in box['title'].casefold())
        orphan = next(box for box in boxes if 'unmoored' in box['title'].casefold())
        self.assertFalse(satchel.get('unlinked'), satchel)
        self.assertEqual((satchel.get('anchor') or {}).get('kind'), 'trigger')
        self.assertTrue(orphan.get('unlinked'), orphan)
        self.assertIsNone(orphan.get('anchor'))
        hops = [link for link in kit_links.links_from(self.index, self.start)
                if link.get('kind') == 'box']
        self.assertTrue(any(link['confidence'] == kit_links.CONFIRMED
                            and 'wet satchel' in (link.get('subject') or '').casefold()
                            for link in hops), hops)
        from_hops = [link for link in self.index['links']
                     if link.get('to_key') == orphan.get('id')]
        self.assertEqual(from_hops, [], from_hops)

    def test_lookup_answers_from_attested_text_without_mechanics(self):
        hit = kit_links.answer(self.db, 'Kit, what does the book say about marsh hound?')
        self.assertIsNotNone(hit)
        self.assertTrue(hit['source_verified'])
        self.assertEqual(hit['link']['kind'], 'name')
        self.assertEqual(hit['link']['confidence'], kit_links.CONFIRMED)
        spoken = hit['spoken']
        self.assertTrue(spoken.startswith('Kit: '))
        low = spoken.casefold()
        self.assertNotIn('armor class', low)
        self.assertNotIn('hit points', low)
        self.assertNotIn('dc ', low)
        self.assertNotIn('to hit', low)
        # The descriptive sentence is attested; the invented line is not.
        span = kit_links.load_hop(
            self.index, self.text,
            kit_links.match_touch(
                'Kit, what does the book say about marsh hound?',
                kit_links.links_from(self.index, self.start)))
        self.assertTrue(kit_links.valid_quote(
            span, 'The marsh hound is a gaunt hunting dog with weed in its coat.'))
        self.assertFalse(kit_links.valid_quote(
            span, 'The hound is secretly a dragon wearing a crown.'))
        if 'gaunt hunting dog' in spoken:
            self.assertTrue(kit_links.valid_quote(span, spoken[len('Kit: '):].strip()))

    def test_sidebar_lookup_uses_the_anchored_box(self):
        hit = kit_links.answer(self.db, 'Kit, what does the book say about The Wet Satchel?')
        self.assertIsNotNone(hit)
        self.assertEqual(hit['link']['kind'], 'box')
        spoken = hit['spoken'].casefold()
        self.assertTrue(
            'folded note' in spoken or 'damp and unsigned' in spoken,
            hit['spoken'])
        self.assertNotIn('give me a second', hit['spoken'].casefold())

    def test_unlinked_or_unknown_subject_is_not_asserted(self):
        self.assertIsNone(kit_links.answer(
            self.db, 'Kit, what does the book say about An Unmoored Note?'))
        self.assertIsNone(kit_links.answer(
            self.db, 'Kit, what does the book say about a made-up relic?'))

    def test_quote_validation_refuses_an_invention(self):
        hops = [link for link in kit_links.links_from(self.index, self.start)
                if link.get('kind') == 'box']
        span = kit_links.load_hop(self.index, self.text, hops[0])
        self.assertTrue(kit_links.valid_quote(span, 'The note is damp and unsigned.'))
        self.assertFalse(kit_links.valid_quote(span, 'The satchel holds a royal charter.'))


class LinkLandingBound(unittest.TestCase):
    """Landing hands the section's own text and does not load one-hop targets."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.source = _book()
        pdf = Path(temporary.name) / 'owned.pdf'
        pdf.write_bytes(b'%PDF-1.4\nsynthetic private source\n')
        with mock.patch('runtime.kit_adventure.read_opening',
                        return_value=(self.source, 'test')):
            kit_adventure.ingest_adventure(self.db, pdf=str(pdf))
        self.burst = (
            'You step into the ford. Two marsh hounds (see the Marsh Hound '
            'stat block) wait on the far bank. A stone heron stands in the silt.'
        )

    def _honest(self):
        return {
            'burst': self.burst,
            'source_quote': self.burst,
            'page_start': 1,
            'page_end': 2,
            'alt_starts': [],
            'design_start_name': 'The Ford',
        }

    def _scene(self, request):
        spoken = (request.get('read_aloud') or self.burst).strip()
        return {
            'place': {'name': 'ford', 'quote': spoken},
            'people': [],
            'discoveries': [],
            'pressures': [],
        }

    def test_landing_does_not_load_linked_hops(self):
        holder = {'load': 0, 'prefetch': 0, 'recover': 0}
        real_load = kit_links.load_hop
        real_prefetch = kit_links.prefetch_confirmed
        real_recover = kit_skim.recover_opening_section

        def wrap_load(*args, **kwargs):
            holder['load'] += 1
            return real_load(*args, **kwargs)

        def wrap_prefetch(*args, **kwargs):
            holder['prefetch'] += 1
            return real_prefetch(*args, **kwargs)

        def wrap_recover(*args, **kwargs):
            holder['recover'] += 1
            return real_recover(*args, **kwargs)

        with mock.patch.object(kit_links, 'load_hop', wrap_load):
            with mock.patch.object(kit_links, 'prefetch_confirmed', wrap_prefetch):
                with mock.patch.object(kit_skim, 'recover_opening_section', wrap_recover):
                    first = kit_skim.accept(self.db, self._honest())
                    self.assertEqual(first.get('stage'), 'scene_required', first)
                    request = first.get('scene_request') or {}
                    source = request.get('source_span') or ''
                    self.assertTrue(
                        kit_skim._has_burst(source, self.burst),
                        'opening section missing from landing handoff')
                    self.assertIn('still past the knee', source)
                    second = kit_skim.accept(self.db, {'scene': self._scene(request)})
        self.assertEqual(second.get('stage'), 'skim_accepted', second)
        self.assertEqual(holder['load'], 0, holder)
        self.assertEqual(holder['prefetch'], 0, holder)
        self.assertEqual(holder['recover'], 1, holder)

    def test_first_touch_loads_only_one_hop(self):
        holder = {'load': 0}
        real_load = kit_links.load_hop

        def wrap_load(*args, **kwargs):
            holder['load'] += 1
            return real_load(*args, **kwargs)

        with mock.patch.object(kit_links, 'load_hop', wrap_load):
            hit = kit_links.answer(
                self.db, 'Kit, what does the book say about marsh hound?')
        self.assertIsNotNone(hit)
        self.assertEqual(holder['load'], 1, holder)



class CanonicalSectionIdentity(unittest.TestCase):
    """The session starts from the recorded heading key, even if compile rebuilds."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.source = _book()
        pdf = Path(temporary.name) / 'owned.pdf'
        pdf.write_bytes(b'%PDF-1.4\nsynthetic private source\n')
        with mock.patch('runtime.kit_adventure.read_opening',
                        return_value=(self.source, 'test')):
            kit_adventure.ingest_adventure(self.db, pdf=str(pdf))
        self.burst = (
            'You step into the ford. Two marsh hounds (see the Marsh Hound '
            'stat block) wait on the far bank. A stone heron stands in the silt.'
        )
        self.index, _text = kit_adventure._load(self.db)
        self.heading = self.index['start']
        self.assertTrue(self.heading)
        self.assertFalse(str(self.heading).startswith('scene:skim:'), self.heading)

    def _honest(self):
        return {
            'burst': self.burst,
            'source_quote': self.burst,
            'page_start': 1,
            'page_end': 2,
            'alt_starts': [],
            'design_start_name': 'The Ford',
        }

    def _scene(self, request):
        spoken = (request.get('read_aloud') or self.burst).strip()
        return {
            'place': {'name': 'ford', 'quote': spoken},
            'people': [],
            'discoveries': [],
            'pressures': [],
        }

    def test_lookup_is_a_one_hop_touch_when_start_would_differ_from_the_heading_key(self):
        first = kit_skim.accept(self.db, self._honest())
        self.assertEqual(first.get('stage'), 'scene_required', first)
        request = first.get('scene_request') or {}
        # Force the rebuild path that used to emit a derived scene:skim start.
        with mock.patch.object(kit_skim, '_try_compile_opening', return_value=None):
            second = kit_skim.accept(self.db, {'scene': self._scene(request)})
        self.assertEqual(second.get('stage'), 'skim_accepted', second)
        self.assertEqual(second.get('scene_key'), self.heading, second)
        index, _text = kit_adventure._load(self.db)
        self.assertEqual(index.get('start'), self.heading)
        self.assertFalse(str(index.get('start')).startswith('scene:skim:'))
        action = 'Kit, what does the book say about marsh hound?'
        hit = kit_links.answer(self.db, action, second.get('scene_key'))
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('source_verified'))
        self.assertNotIn('give me a second', (hit.get('spoken') or '').casefold())
        # A leftover derived start name is the same section, not a second graph.
        aliased = kit_links.answer(self.db, action, 'scene:skim:A')
        self.assertIsNotNone(aliased)
        self.assertEqual(aliased.get('link'), hit.get('link'))
        self.assertEqual(kit_links.section_key(index, 'scene:skim:A'), self.heading)




class CanonicalPickWithoutBoxedMarkers(unittest.TestCase):
    """A typography-messy opening still picks and looks up on the heading key."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / 'kit.sqlite'
        self.source = _book_without_usable_boxes()
        pdf = Path(temporary.name) / 'owned.pdf'
        pdf.write_bytes(b'%PDF-1.4\nsynthetic private source\n')
        with mock.patch('runtime.kit_adventure.read_opening',
                        return_value=(self.source, 'test')):
            kit_adventure.ingest_adventure(self.db, pdf=str(pdf))
        self.index, self.text = kit_adventure._load(self.db)
        self.heading = self.index['start']
        self.assertTrue(self.heading)
        self.assertFalse(str(self.heading).startswith('scene:skim:'), self.heading)

    def test_pick_reaches_the_heading_key_and_lookup_is_a_one_hop_touch(self):
        picks = kit_opening.playable_picker_starts(self.db)
        self.assertTrue(picks)
        chosen = next((item for item in picks if item.get('id') == self.heading), picks[0])
        self.assertEqual(chosen.get('id'), self.heading, chosen)
        self.assertTrue((chosen.get('quote') or '').strip(), chosen)
        self.assertFalse(chosen.get('kit_line'), chosen)
        self.assertIn('step into the ford', chosen['quote'])
        data = kit_skim._read(self.db)
        data['alt_starts'] = picks
        kit_skim._write(self.db, data)
        first = kit_skim.open_title(self.db, chosen.get('title'))
        self.assertEqual(first.get('stage'), 'scene_required', first)
        spoken = (first.get('scene_request') or {}).get('read_aloud') or chosen['quote']
        scene = {
            'place': {'name': 'ford', 'quote': spoken},
            'people': [],
            'discoveries': [],
            'pressures': [],
        }
        second = kit_skim.accept(self.db, {'scene': scene})
        self.assertEqual(second.get('stage'), 'skim_accepted', second)
        self.assertEqual(second.get('scene_key'), self.heading, second)
        hit = kit_links.answer(self.db, 'Kit, what does the book say about marsh hound?',
                               second.get('scene_key'))
        self.assertIsNotNone(hit)
        self.assertTrue(hit.get('source_verified'))
        self.assertNotIn('give me a second', (hit.get('spoken') or '').casefold())


if __name__ == '__main__':
    unittest.main()
