"""Synthetic two-column encounter recovery and source-security regressions."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_adventure, kit_skim, kit_scene_contract


def row(left, right, width=66):
    return left + ' ' * max(3, width - len(left)) + right + '\n'


class ColumnRecovery(unittest.TestCase):
    def test_justified_words_are_not_a_new_sidebar(self):
        burst = 'A wagon rolls toward the bridge at dawn.'
        raw = (row('1. Marsh Road', '2. Stone Vault') +
               row('> A wagon rolls    toward the bridge at dawn.',
                   '> A locked chest glows in the vault.') +
               row('Two scouts wait beside the bridge.',
                   'A spectral guard stands beside the chest.'))
        bounded = kit_skim._same_column_encounter(raw, burst)
        self.assertIn('Two scouts wait', bounded)
        self.assertIn('A wagon rolls', bounded)
        self.assertNotIn('spectral guard', bounded)
        self.assertNotIn('locked chest', bounded)

    def test_right_lane_does_not_import_the_facing_sidebar(self):
        burst = 'A brass bell rings over the eastern harbor.'
        raw = (row('A sailor offers a rumor.', '1. East Harbor') +
               row('The sailor sits near the tavern.',
                   '> A brass bell rings over the eastern harbor.') +
               row('The sailor leaves.', 'Captain Mara guards the pier.'))
        bounded = kit_skim._same_column_encounter(raw, burst)
        self.assertIn('Captain Mara', bounded)
        self.assertNotIn('sailor', bounded)

    def test_single_lane_crosses_a_page(self):
        burst = 'A slow river pushes reeds against the ruined causeway.'
        raw = ('1. Causeway\n> A slow river pushes reeds\f'
               'against the ruined causeway.\n'
               'Two guards hide beside the bank.\n'
               '2. Upper Mill\nA wheel turns.\n')
        bounded = kit_skim._same_column_encounter(raw, burst)
        self.assertIn('Two guards', bounded)
        self.assertNotIn('wheel turns', bounded)

    def test_pipe_layout_does_not_import_next_room(self):
        burst = 'A wooden bridge shakes beneath your feet.'
        raw = ('1. Bridge | 2. Sealed Archive\n'
               '> A wooden bridge shakes beneath your feet. | > A silver key glows.\n'
               'A keeper watches from the far shore. | The archive has a trap.\n')
        bounded = kit_skim._same_column_encounter(raw, burst)
        self.assertIn('keeper watches', bounded)
        self.assertNotIn('silver key', bounded)
        self.assertNotIn('archive has a trap', bounded)

    def test_missing_quote_is_no_scene(self):
        raw = '1. Other Hall\n> A lantern moves in the window.\n'
        self.assertEqual(kit_skim._same_column_encounter(
            raw, 'A dragon lands before the party.'), '')

    def test_neighbor_actor_cannot_be_attested(self):
        burst = 'A wagon rolls toward the bridge at dawn.'
        raw = (row('1. Marsh Road', '2. Stone Vault') +
               row('> A wagon rolls toward the bridge at dawn.',
                   '> A locked chest glows in the vault.') +
               row('Two scouts wait beside the bridge.',
                   'A spectral guard stands beside the chest.'))
        bounded = kit_skim._same_column_encounter(raw, burst)
        fake = {'place': {'name': 'bridge', 'quote': burst},
                'people': [{'id': 'ghost', 'name': 'spectral guard',
                            'quote': 'A spectral guard stands beside the chest.',
                            'visibility': 'hidden', 'kind': 'creature',
                            'goal': None, 'knowledge': []}],
                'discoveries': [], 'pressures': []}
        self.assertTrue(kit_scene_contract.validate(fake, bounded, burst))


class PdfSceneIntegration(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / 'game.sqlite'
        pdf = Path(tmp.name) / 'original.pdf'
        pdf.write_bytes(b'%PDF-1.4\nsynthetic private source\n')
        self.burst = 'The cart halts near a bent tree.'
        text = ('1. Marsh Road\n> ' + self.burst + '\n'
                'Two scouts wait beside the path.\n'
                '2. Far Chapel\nThe door is locked.\n')
        with mock.patch('runtime.kit_adventure.read_opening',
                        return_value=(text, 'test')):
            kit_adventure.ingest_adventure(self.db, pdf=str(pdf))

    def test_nonempty_scope_from_public_skim(self):
        result = kit_skim.accept(self.db, {
            'burst': self.burst, 'source_quote': self.burst,
            'page_start': 1, 'page_end': 1,
            'alt_starts': [], 'design_start_name': 'Marsh Road'})
        self.assertEqual(result['stage'], 'scene_required', result)
        span = result['scene_request']['source_span']
        self.assertIn(self.burst, span)
        self.assertIn('Two scouts', span)
        self.assertNotIn('Far Chapel', span)

    def test_missing_scope_accepts_a_burst_only_start_instead_of_stalling(self):
        with mock.patch.object(kit_skim, 'recover_opening_section',
                               return_value=('', [])):
            first = kit_skim.accept(self.db, {
                'burst': self.burst, 'source_quote': self.burst,
                'page_start': 1, 'page_end': 1,
                'alt_starts': [], 'design_start_name': 'Marsh Road'})
            self.assertEqual(first['stage'], 'skim_accepted', first)
            self.assertEqual(first.get('layout_recovery'), 'burst_only')
            self.assertFalse(first.get('people_attested'))
            self.assertIn('read-aloud only', first.get('table_line') or '')
            self.assertIn('start_picker', first)
            self.assertEqual(kit_skim._read(self.db).get('status'), 'accepted')


if __name__ == '__main__':
    unittest.main()
