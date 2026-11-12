"""Opening source scope must not authorize a neighbouring PDF column.

All passages are original synthetic fixture text. This is a security boundary:
a quoted claim may be attested only to the current encounter, not a later area
that happens to share its row in pdftotext -layout output.
"""
import json
import tempfile
import unittest
from pathlib import Path
from shutil import which

from runtime import kit_adventure, kit_skim
from test_kit_adventure_pdf import make_pdf


class BoundedColumnSource(unittest.TestCase):
    def test_left_encounter_survives_next_room_in_right_column(self):
        raw = ('You stand on the road under the trees.       A distant patron sends a message.\n'
               '                                            How to Play: read the rules.\n'
               '\fTwo bandits hide beside the bridge.         2. The Locked Vault\n'
               'A careful look notices broken branches.     Inside the vault lies a silver key.\n')
        scope = kit_skim._same_column_encounter(raw, 'You stand on the road under the trees.')
        self.assertIn('Two bandits hide', scope)
        self.assertIn('broken branches', scope)
        for forbidden in ('The Locked Vault', 'silver key', 'distant patron', 'How to Play'):
            self.assertNotIn(forbidden, scope)

    def test_right_column_opening_is_selected_instead_of_left_sidebar(self):
        raw = ('A sidebar lists world lore.                You enter the market street.\n'
               'A patron waits miles away.                 A visitor approaches the stall.\n'
               '                                          3. The Dark Cellar\n'
               '                                          You descend into a cellar.\n')
        scope = kit_skim._same_column_encounter(raw, 'You enter the market street.')
        self.assertIn('A visitor approaches the stall.', scope)
        self.assertNotIn('A patron waits miles away.', scope)
        self.assertNotIn('The Dark Cellar', scope)

    @unittest.skipUnless(which('pdftotext'), 'requires pdftotext -layout')
    def test_actual_pdf_repair_packet_excludes_neighbouring_keyed_room(self):
        pages = [[
            ('text', 48, 740, 'You stand on the road under the trees.', 11),
            ('text', 360, 740, 'A distant patron sends a message.', 9),
            ('text', 360, 700, 'How to Play. Read the rules.', 9),
        ], [
            ('text', 48, 740, 'Two bandits hide beside the bridge.', 11),
            ('text', 48, 700, 'A careful look notices broken branches.', 11),
            ('text', 360, 740, '2. The Locked Vault', 12),
            ('text', 360, 700, 'Inside the vault lies a silver key.', 11),
        ]]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pdf = root / 'adventure.pdf'
            pdf.write_bytes(make_pdf(pages))
            db = root / 'kit.sqlite'
            kit_adventure.ingest_adventure(db, pdf=pdf, reader='pdftotext')
            result = kit_skim.accept(db, {
                'burst': 'You stand on the road under the trees.',
                'source_quote': 'You stand on the road under the trees.',
                'page_start': 1, 'page_end': 2,
                'alt_starts': [], 'design_start_name': 'The road',
            })
            self.assertEqual(result['stage'], 'scene_required', result)
            source = result['scene_request']['source_span']
            self.assertIn('Two bandits hide', source)
            self.assertIn('broken branches', source)
            self.assertNotIn('silver key', source)
            self.assertNotIn('Locked Vault', source)
            self.assertNotIn('distant patron', source)
            self.assertNotIn('How to Play', source)
            self.assertNotIn('beat', kit_skim._read(db))


if __name__ == '__main__':
    unittest.main()
