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


def _cross_page_book():
    """A long two-column book: filler pages, then a boxed opening that
    continues after a page break, then a later keyed area."""
    burst = 'You reach the stepping stones while the current pulls at the reeds.'
    pages = ['Part 1: The Long Ridge\n']
    for tag in range(1, 7):
        pages.append(_filler_page(tag))
        pages.append('\f')
    # Headings stand on their own line so the index can record them; body
    # rows stay two-column, and the boxed opening continues after a break.
    pages.append('The Willow Crossing\n')
    pages.append(_row('> ' + burst, 'A clerk lists fares for the crossing.'))
    pages.append('\f')
    pages.append(_row(
        'Two herons stand in the shallows below the crossing.',
        'The clerk keeps the ledger dry.'))
    pages.append('1. The Brick Kiln\n')
    pages.append(_row(
        'The kiln door is still, and you smell damp clay.',
        'A sealed latch hides the vault.'))
    return ''.join(pages), burst


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


if __name__ == '__main__':
    unittest.main()
