"""Pick recovery reuses the index next-keyed-area bound.

All adventure material below is original synthetic prose. No published text.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_adventure, kit_skim


def _row(left, right, width=72):
    return left + ' ' * max(3, width - len(left)) + right + '\n'


def _count_calls(fn, holder, key):
    def wrapped(*args, **kwargs):
        holder[key] = holder.get(key, 0) + 1
        return fn(*args, **kwargs)
    return wrapped


def _filler_page(tag, rows=40):
    out = []
    for index in range(rows):
        left = 'Travel notes continue along the ridge path %s item %s.' % (tag, index)
        right = 'A sidebar lists weather and watch rotations %s item %s.' % (tag, index)
        out.append(_row(left, right))
    return ''.join(out)


def _cross_page_book(later_pages=0, interleave=False):
    """A long two-column book: filler pages, then a boxed opening that
    continues after a page break, then a later keyed area.

    later_pages adds trailing layout after the keyed area so a whole-book
    search would walk far past the recorded body. interleave puts facing
    column words between boxed words so a contiguous full-source scan fails.
    """
    burst = 'You reach the stepping stones while the current pulls at the reeds.'
    pages = ['Part 1: The Long Ridge\n']
    for tag in range(1, 7):
        pages.append(_filler_page(tag))
        pages.append('\f')
    # Headings stand on their own line so the index can record them; body
    # rows stay two-column, and the boxed opening continues after a break.
    pages.append('The Willow Crossing\n')
    if interleave:
        pages.append(_row('> You reach the stepping stones',
                          'A clerk lists fares'))
        pages.append(_row('while the current pulls at the reeds.',
                          'for the crossing today.'))
    else:
        pages.append(_row('> ' + burst, 'A clerk lists fares for the crossing.'))
    pages.append('\f')
    pages.append(_row(
        'Two herons stand in the shallows below the crossing.',
        'The clerk keeps the ledger dry.'))
    pages.append('1. The Brick Kiln\n')
    pages.append(_row(
        'The kiln door is still, and you smell damp clay.',
        'A sealed latch hides the vault.'))
    for tag in range(100, 100 + later_pages):
        pages.append('\f')
        pages.append(_filler_page(tag))
    return ''.join(pages), burst



def _two_column_canonical_book():
    """Two-column official opening plus a decoy line in the same recorded section.

    An unsplit picker quote fuses the boxed left opening with the facing
    column, which would recover a different window than landing. Landing
    uses the official burst. Pick of the same heading key must return
    those exact bytes.
    """
    burst = 'You reach the stepping stones while the current pulls at the reeds.'
    decoy = 'A painted sign names the crossing for travelers passing through.'
    pages = ['Part 1: The Long Ridge\n']
    pages.append('The Willow Crossing\n')
    pages.append(_row(decoy, 'Fare notices hang from a nail.'))
    pages.append(_row('> ' + burst, 'A clerk lists fares for the crossing.'))
    pages.append('\f')
    pages.append(_row(
        'Two herons stand in the shallows below the crossing.',
        'The clerk keeps the ledger dry.'))
    pages.append('1. The Brick Kiln\n')
    pages.append(_row(
        'The kiln door is still, and you smell damp clay.',
        'A sealed latch hides the vault.'))
    return ''.join(pages), burst, decoy


class BoundSectionStreamWork(unittest.TestCase):

    def test_large_stream_finds_the_burst_without_a_prefix_scan(self):
        burst = 'You reach the stepping stones while the current pulls at the reeds.'
        lines = [
            'Travel notes continue along the ridge path item %s.' % index
            for index in range(800)
        ]
        lines.extend([
            'The Willow Crossing',
            '> ' + burst,
            'Two herons stand in the shallows below the crossing.',
            '1. The Brick Kiln',
            'The kiln door is still, and you smell damp clay.',
        ])
        stream = '\n'.join(lines)
        holder = {'has_burst': 0}
        real = kit_skim._has_burst
        with mock.patch.object(
                kit_skim, '_has_burst', _count_calls(real, holder, 'has_burst')):
            piece, begin, finish = kit_skim._bound_section_stream(stream, burst)
        self.assertIn('herons stand in the shallows', piece)
        self.assertIn(burst, ' '.join(piece.split()))
        self.assertNotIn('kiln door', piece)
        # One stream search plus a short confirmation or binary search.
        # A growing prefix walk would be hundreds of calls.
        self.assertLess(holder['has_burst'], 24, holder)

    def test_facing_lane_with_force_start_does_not_search_for_the_burst(self):
        burst = 'You reach the stepping stones while the current pulls at the reeds.'
        lines = [
            'A clerk lists fares for the crossing item %s.' % index
            for index in range(800)
        ]
        stream = '\n'.join(lines)
        holder = {'has_burst': 0}
        real = kit_skim._has_burst
        with mock.patch.object(
                kit_skim, '_has_burst', _count_calls(real, holder, 'has_burst')):
            piece, begin, finish = kit_skim._bound_section_stream(
                stream, burst, force_start=0, force_finish=10)
        self.assertTrue(piece.strip())
        self.assertEqual(holder['has_burst'], 0, holder)


class IndexBoundedPickRecovery(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'case.sqlite'
        self.source, self.burst = _cross_page_book()
        pdf = Path(self.temp.name) / 'owned.pdf'
        pdf.write_bytes(b'%PDF-1.4\nsynthetic private source\n')
        with mock.patch('runtime.kit_adventure.read_opening',
                        return_value=(self.source, 'test')):
            kit_adventure.ingest_adventure(self.db, pdf=str(pdf))

    def test_index_slice_stops_at_the_recorded_keyed_area(self):
        slice_text = kit_skim._index_body_for_burst(self.db, self.burst)
        self.assertTrue(slice_text)
        self.assertIn(self.burst, ' '.join(slice_text.split()))
        self.assertIn('herons stand in the shallows', slice_text)
        self.assertNotIn('sealed latch', slice_text)

    def test_recover_uses_the_index_and_does_not_reextract_sources(self):
        holder = {'has_burst': 0, 'sources': 0}
        real_burst = kit_skim._has_burst
        real_sources = kit_skim._section_sources
        with mock.patch.object(
                kit_skim, '_has_burst',
                _count_calls(real_burst, holder, 'has_burst')):
            with mock.patch.object(
                    kit_skim, '_section_sources',
                    _count_calls(real_sources, holder, 'sources')):
                text, columns = kit_skim.recover_opening_section(
                    self.db, self.burst, self.source)
        self.assertTrue(text)
        blob = ' '.join(text.split())
        self.assertIn(self.burst, blob)
        self.assertIn('herons stand in the shallows', text)
        self.assertNotIn('sealed latch', text)
        self.assertEqual(holder['sources'], 0, holder)
        self.assertLess(holder['has_burst'], 40, holder)
        self.assertGreaterEqual(len(columns), 1)

    def test_naming_the_playable_title_returns_the_bounded_scene_form(self):
        refused = kit_skim.accept(self.db, {
            'burst': 'A dragon lands on the bakery and the crowd cheers.',
            'source_quote': 'A dragon lands on the bakery and the crowd cheers.',
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Willow Crossing',
        })
        titles = [item.get('title') or '' for item in refused.get('alt_starts') or []]
        self.assertTrue(titles, refused)
        holder = {'sources': 0, 'has_burst': 0}
        real_sources = kit_skim._section_sources
        real_burst = kit_skim._has_burst
        with mock.patch.object(
                kit_skim, '_section_sources',
                _count_calls(real_sources, holder, 'sources')):
            with mock.patch.object(
                    kit_skim, '_has_burst',
                    _count_calls(real_burst, holder, 'has_burst')):
                picked = kit_adventure.choose_start(self.db, titles[0])
        self.assertEqual(picked.get('stage'), 'scene_required', picked)
        source = (picked.get('scene_request') or {}).get('source_span') or ''
        self.assertIn(self.burst, ' '.join(source.split()))
        self.assertIn('herons stand in the shallows', source)
        self.assertNotIn('sealed latch', source)
        self.assertEqual(holder['sources'], 0, holder)
        # accept also uses burst checks on the skim window; stay far below a
        # prefix walk of the filler pages.
        self.assertLess(holder['has_burst'], 80, holder)

    def test_a_later_short_duplicate_does_not_replace_the_section(self):
        # After a start, the index may grow a short derived scene that repeats
        # the boxed words. The section is still the earlier body that contains
        # the first source offset, through the recorded keyed-area end.
        index, text = kit_adventure._load(self.db)
        extra = '\nThe Later Copy\n> ' + self.burst + '\n'
        combined = text + extra
        start = len(text)
        locations = dict(index.get('locations') or {})
        locations['scene:skim:Z'] = {
            'key': 'scene:skim:Z', 'type': 'scene', 'name': 'The Later Copy',
            'offset': start, 'body': [start, start + len(extra)],
            'page': 99, 'playable_start': True,
        }
        index = dict(index)
        index['locations'] = locations
        with mock.patch('runtime.kit_adventure._load', return_value=(index, combined)):
            slice_text = kit_skim._index_body_for_burst(self.db, self.burst)
            recovered, columns = kit_skim.recover_opening_section(
                self.db, self.burst, combined)
        self.assertTrue(slice_text)
        self.assertIn('herons stand in the shallows', slice_text)
        self.assertNotIn('The Later Copy', slice_text)
        self.assertIn(self.burst, ' '.join((recovered or '').split()))
        self.assertIn('herons stand in the shallows', recovered)
        self.assertNotIn('sealed latch', recovered)
        self.assertGreater(len(slice_text), len(extra) * 4)


class LandingPathWork(unittest.TestCase):
    """Landing recovers the recorded section once and does not search later pages."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'case.sqlite'
        self.source, self.burst = _cross_page_book(later_pages=40, interleave=True)
        pdf = Path(self.temp.name) / 'owned.pdf'
        pdf.write_bytes(b'%PDF-1.4\nsynthetic private source\n')
        with mock.patch('runtime.kit_adventure.read_opening',
                        return_value=(self.source, 'test')):
            kit_adventure.ingest_adventure(self.db, pdf=str(pdf))
        self.source_len = len(kit_adventure._load(self.db)[1])

    def _honest(self):
        return {
            'burst': self.burst,
            'source_quote': self.burst,
            'page_start': 1,
            'page_end': 1,
            'alt_starts': [],
            'design_start_name': 'The Willow Crossing',
        }

    def _scene(self, request):
        spoken = (request.get('read_aloud') or self.burst).strip()
        return {
            'place': {'name': 'stones', 'quote': spoken},
            'people': [],
            'discoveries': [],
            'pressures': [],
        }

    def test_landing_recovers_once_and_does_not_search_the_whole_source(self):
        holder = {'recover': 0, 'find_quote_big': 0, 'find_quote': 0}
        source_len = self.source_len
        real_recover = kit_skim.recover_opening_section
        real_quote = kit_skim.find_quote

        def wrap_recover(*args, **kwargs):
            holder['recover'] += 1
            return real_recover(*args, **kwargs)

        def wrap_quote(page_text, quote):
            holder['find_quote'] += 1
            if len(page_text or '') >= (source_len * 8) // 10:
                holder['find_quote_big'] += 1
            return real_quote(page_text, quote)

        with mock.patch.object(kit_skim, 'recover_opening_section', wrap_recover):
            with mock.patch.object(kit_skim, 'find_quote', wrap_quote):
                first = kit_skim.accept(self.db, self._honest())
                self.assertEqual(first.get('stage'), 'scene_required', first)
                request = first.get('scene_request') or {}
                source = request.get('source_span') or ''
                columns = request.get('source_columns') or []
                self.assertTrue(
                    kit_skim._has_burst(source, self.burst) or any(
                        kit_skim._has_burst(item.get('text') or '', self.burst)
                        for item in columns if isinstance(item, dict)),
                    'burst missing from recovered section')
                self.assertIn('herons stand in the shallows', source)
                self.assertNotIn('sealed latch', source)
                second = kit_skim.accept(self.db, {'scene': self._scene(request)})
        self.assertEqual(second.get('stage'), 'skim_accepted', second)
        self.assertTrue(second.get('source_verified'), second)
        self.assertEqual(holder['recover'], 1, holder)
        self.assertEqual(holder['find_quote_big'], 0, holder)



class CanonicalKeyPickMatchesLanding(unittest.TestCase):
    """Pick of the canonical heading reuses the exact recorded section landing hands over."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source, self.burst, self.decoy = _two_column_canonical_book()
        self.pdf = Path(self.temp.name) / 'owned.pdf'
        self.pdf.write_bytes(b'%PDF-1.4\nsynthetic private source\n')
        self.land_db = Path(self.temp.name) / 'land' / 'kit.sqlite'
        self.pick_db = Path(self.temp.name) / 'pick' / 'kit.sqlite'
        self.land_db.parent.mkdir()
        self.pick_db.parent.mkdir()
        with mock.patch('runtime.kit_adventure.read_opening',
                        return_value=(self.source, 'test')):
            kit_adventure.ingest_adventure(self.land_db, pdf=str(self.pdf))
            kit_adventure.ingest_adventure(self.pick_db, pdf=str(self.pdf))
        self.index, _text = kit_adventure._load(self.land_db)
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
            'design_start_name': 'The Willow Crossing',
        }

    def test_pick_and_landing_return_the_identical_recorded_section(self):
        holder = {'sources': 0, 'has_burst': 0, 'recover': 0}
        real_sources = kit_skim._section_sources
        real_burst = kit_skim._has_burst
        real_recover = kit_skim.recover_opening_section

        def wrap_recover(*args, **kwargs):
            holder['recover'] += 1
            return real_recover(*args, **kwargs)

        with mock.patch.object(
                kit_skim, '_section_sources',
                _count_calls(real_sources, holder, 'sources')):
            with mock.patch.object(
                    kit_skim, '_has_burst',
                    _count_calls(real_burst, holder, 'has_burst')):
                with mock.patch.object(
                        kit_skim, 'recover_opening_section', wrap_recover):
                    landed = kit_skim.accept(self.land_db, self._honest())
                    self.assertEqual(landed.get('stage'), 'scene_required', landed)
                    land_req = landed.get('scene_request') or {}
                    land_span = land_req.get('source_span') or ''
                    land_cols = land_req.get('source_columns') or []
                    self.assertIn(self.burst, ' '.join(land_span.split()))
                    self.assertIn('herons stand in the shallows', land_span)
                    self.assertNotIn('sealed latch', land_span)
                    self.assertGreaterEqual(len(land_cols), 2, land_cols)
                    land_burst = land_req.get('read_aloud') or ''
                    self.assertTrue(land_burst)
                    self.assertIn(self.burst, ' '.join(land_burst.split()))

                    from runtime import kit_opening
                    picks = kit_opening.playable_picker_starts(self.pick_db)
                    self.assertTrue(picks)
                    chosen = next((item for item in picks if item.get('id') == self.heading), picks[0])
                    self.assertEqual(chosen.get('id'), self.heading, chosen)
                    data = kit_skim._read(self.pick_db)
                    data['alt_starts'] = picks
                    kit_skim._write(self.pick_db, data)
                    picked = kit_skim.open_title(self.pick_db, chosen.get('title'))
                    self.assertEqual(picked.get('stage'), 'scene_required', picked)
                    pick_req = picked.get('scene_request') or {}
                    pick_span = pick_req.get('source_span') or ''
                    pick_cols = pick_req.get('source_columns') or []

        self.assertEqual(pick_span, land_span)
        self.assertEqual(
            [(c.get('lane'), c.get('text')) for c in pick_cols],
            [(c.get('lane'), c.get('text')) for c in land_cols],
        )
        pick_burst = pick_req.get('read_aloud') or ''
        self.assertEqual(pick_burst, land_burst)
        self.assertEqual(holder['sources'], 0, holder)
        # Landing recovers once. Pick reuses the recorded section, no later-source walk.
        self.assertLess(holder['has_burst'], 80, holder)
        self.assertEqual(holder['recover'], 1, holder)


if __name__ == '__main__':
    unittest.main()
