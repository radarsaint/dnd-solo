"""Source-general regression tests for PDF encounter-column recovery.

All adventure material below is original synthetic prose. No published text.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_adventure, kit_skim, kit_scene_contract


def _row(left, right, width=66):
    return left + ' ' * max(3, width - len(left)) + right + '\n'


class EncounterColumnReconstruction(unittest.TestCase):
    def test_incidental_inner_space_does_not_replace_the_real_gutter(self):
        burst = 'A wagon rolls toward the bridge at dawn.'
        source = (
            _row('1. Marsh Road', '2. Stone Vault')
            + _row('> A wagon rolls    toward the bridge at dawn.',
                   '> A locked chest glows in the vault.')
            + _row('Two scouts wait beside the bridge.',
                   'The vault holds a spectral guard.')
        )
        span = kit_skim._same_column_encounter(source, burst)
        self.assertIn('Two scouts wait beside the bridge.', span)
        self.assertIn(burst, ' '.join(span.split()))
        self.assertNotIn('Stone Vault', span)
        self.assertNotIn('locked chest', span)
        self.assertNotIn('spectral guard', span)

    def test_right_column_box_keeps_its_encounter_not_left_column_setup(self):
        burst = 'A brass bell rings over the eastern harbor.'
        source = (
            _row('The guide gives directions to the ferry.',
                 '1. East Harbor')
            + _row('Visitors can ask about the routes.',
                   '> A brass bell rings over the eastern harbor.')
            + _row('The guide waits in the square.',
                   'Captain Mara guards the pier after sunset.')
        )
        span = kit_skim._same_column_encounter(source, burst)
        self.assertIn('Captain Mara guards the pier after sunset.', span)
        self.assertNotIn('guide gives directions', span)
        self.assertNotIn('guide waits in the square', span)

    def test_right_column_continuation_stays_in_the_opening(self):
        burst = 'The lantern sways above a narrow stone gate.'
        source = (
            _row('1. Gate Road', 'A silent watchman waits beyond the gate.')
            + _row('> The lantern sways above a narrow stone gate.',
                   'The watchman only opens the gate at sunrise.')
            + _row('A cracked step lies beneath the arch.', '')
        )
        span = kit_skim._same_column_encounter(source, burst)
        self.assertIn('cracked step', span)
        self.assertIn('silent watchman', span)
        self.assertIn('only opens', span)

    def test_marked_pipe_separates_an_unrelated_next_room(self):
        burst = 'A wooden bridge shakes beneath your feet.'
        source = (
            '1. Bridge | 2. Sealed Archive\n'
            '> A wooden bridge shakes beneath your feet. | > A silver key glows.\n'
            'A keeper watches from the far shore. | The archive has a trap.\n'
        )
        span = kit_skim._same_column_encounter(source, burst)
        self.assertIn('keeper watches', span)
        self.assertNotIn('silver key', span)
        self.assertNotIn('archive has a trap', span)

    def test_opening_split_across_adjacent_pages_is_not_lost(self):
        burst = 'A slow river pushes reeds against the ruined causeway.'
        source = (
            '1. Causeway\n> A slow river pushes reeds\f'
            'against the ruined causeway.\n'
            'Two guards hide beside the bank.\n'
            '2. Upper Mill\nAn iron wheel turns.\n'
        )
        span = kit_skim._same_column_encounter(source, burst)
        self.assertIn('Two guards hide beside the bank.', span)
        self.assertNotIn('iron wheel', span)

    def test_no_supported_layout_never_returns_an_ersatz_encounter(self):
        source = '1. Unrelated Hall\n> Lamps line the hall.\nA watchman stands guard.\n'
        self.assertEqual(
            kit_skim._same_column_encounter(
                source, 'An entirely different opening appears at the gate.'), '')

    def test_only_sourced_actors_can_be_attested(self):
        burst = 'A wagon rolls toward the bridge at dawn.'
        source = (
            _row('1. Marsh Road', '2. Stone Vault')
            + _row('> A wagon rolls toward the bridge at dawn.',
                   '> A locked chest glows in the vault.')
            + _row('Two scouts wait beside the bridge.',
                   'A spectral guard stands beside the chest.')
        )
        span = kit_skim._same_column_encounter(source, burst)
        claimed = {
            'place': {'name': 'bridge', 'quote': burst},
            'people': [{
                'id': 'ghost', 'name': 'spectral guard',
                'quote': 'A spectral guard stands beside the chest.',
                'visibility': 'hidden', 'kind': 'creature',
                'goal': None, 'knowledge': [],
            }],
            'discoveries': [], 'pressures': [],
        }
        errors = kit_scene_contract.validate(claimed, span, burst)
        self.assertTrue(errors)
        self.assertTrue(any('outside' in e or 'not contiguous' in e for e in errors), errors)


class PublicPdfSceneBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'case.sqlite'
        pdf = Path(self.temp.name) / 'owned.pdf'
        pdf.write_bytes(b'%PDF-1.4\nsynthetic private source\n')
        self.burst = 'The cart halts near a bent tree.'
        self.text = ('1. Marsh Road\n> ' + self.burst +
                     '\nTwo scouts wait beside the path.\n'
                     '2. Far Chapel\nThe door is locked.\n')
        with mock.patch('runtime.kit_adventure.read_opening',
                        return_value=(self.text, 'test')):
            kit_adventure.ingest_adventure(self.db, pdf=str(pdf))

    def _skim(self, scene=None):
        answer = {
            'burst': self.burst, 'source_quote': self.burst,
            'page_start': 1, 'page_end': 1,
            'alt_starts': [], 'design_start_name': 'Marsh Road',
        }
        if scene is not None:
            answer['scene'] = scene
        return kit_skim.accept(self.db, answer)

    def test_pdf_host_receives_nonempty_local_encounter_not_later_room(self):
        result = self._skim()
        self.assertEqual(result['stage'], 'scene_required', result)
        source = result['scene_request']['source_span']
        self.assertIn(self.burst, source)
        self.assertIn('Two scouts wait beside the path.', source)
        self.assertNotIn('Far Chapel', source)

    def test_missing_reconstruction_blocks_both_skim_and_scene_retry(self):
        scene = {
            'place': {'name': 'cart', 'quote': self.burst},
            'people': [], 'discoveries': [], 'pressures': [],
        }
        with mock.patch.object(kit_skim, '_same_column_encounter',
                               return_value=''):
            first = self._skim()
            self.assertEqual(first['stage'], 'scene_required', first)
            self.assertEqual(first['scene_request']['source_span'], '')
            self.assertIn('cannot be reconstructed',
                          ' '.join(first['scene_request']['problems']))
            retried = kit_skim.accept(self.db, {'scene': scene})
            self.assertEqual(retried['stage'], 'scene_required', retried)
            self.assertFalse(retried['source_verified'])
            self.assertNotEqual(kit_skim._read(self.db).get('status'), 'accepted')


if __name__ == '__main__':
    unittest.main()
