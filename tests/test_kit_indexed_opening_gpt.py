"""Source-verified PDF opens the indexed location, not a disconnected scene.

Synthetic PDF fixture only. These tests drive ingest, host scene repair, start,
prepare and complete using the real CLI; no published adventure text or API key.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from shutil import which

from test_kit_adventure_pdf import make_pdf
from test_kit_host_contract_round2 import call, PRESENCE, FIND
from test_kit_scene_contract_gpt import FICTION, SCENE, SHEET
from test_kit_agent import RecordingModel
from runtime import kit_adventure, kit_rooms
from runtime.state_context import Runtime


@unittest.skipUnless(which('pdftotext'), 'requires pdftotext -layout')
class IndexedOpeningHostPath(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.db = self.folder / 'game.sqlite'
        pdf = self.folder / 'synthetic.pdf'
        pdf.write_bytes(make_pdf([
            [('text', 70, 700, 'Contents ' + '.' * 80 + ' 2', 10)],
            [('text', 70, 735, '1. The North Road', 11),
             ('text', 70, 710, FICTION, 9),
             ('text', 70, 675, PRESENCE, 9),
             ('text', 70, 645, FIND, 9),
             ('text', 70, 615, 'A road leads to area 2.', 9),
             ('text', 70, 555, '2. The Tower', 11),
             ('text', 70, 525, 'A bell rings on a high tower.', 9),
             ('text', 70, 495, 'A path leads back to area 1.', 9)],
        ]))
        self.assertEqual(call('ingest', pdf, '--reader', 'pdftotext', '--db', self.db)['stage'],
                         'adventure_ingested')
        self.form = self.folder / 'skim.json'
        self.form.write_text(json.dumps({
            'burst': FICTION, 'source_quote': FICTION,
            'page_start': 2, 'page_end': 2, 'alt_starts': [],
            'design_start_name': 'The North Road',
        }))
        needed = call('adventure', 'skim', '--db', self.db, '--file', self.form)
        self.assertEqual(needed['stage'], 'scene_required')
        self.assertIn('A road leads to area 2.', needed['scene_request']['source_span'])
        self.assertNotIn('A bell rings on a high tower.', needed['scene_request']['source_span'])
        self.form.write_text(json.dumps({'scene': copy.deepcopy(SCENE)}))
        self.accepted = call('adventure', 'skim', '--db', self.db, '--file', self.form)
        self.assertEqual(self.accepted['stage'], 'skim_accepted')

    def test_indexed_route_survives_and_completes_through_the_real_host_cycle(self):
        # The old lexical pressure heuristic discarded the indexed room and
        # emitted a disconnected synthetic scene with no way to the tower.
        self.assertEqual(self.accepted['scene_key'], '1')
        opening = Path(self.accepted['room'])
        self.assertEqual(opening.name, '1.json')
        room = json.loads(opening.read_text(encoding='utf-8'))
        self.assertIn('way_2', room['exits'])
        self.assertTrue(room['_opening_verified'])
        self.assertEqual(len(room['_opening_people']), 2)
        self.assertEqual(call('start', '--db', self.db, '--sheet', SHEET)['stage'], 'started')
        action = self.folder / 'action.txt'
        action.write_text('Yes.')
        self.assertIn(FICTION, call('prepare', '--one-pass', '--db', self.db,
                                    '--action-file', action)['spoken'])
        action.write_text('I go to the Tower.')
        prepared = call('prepare', '--one-pass', '--db', self.db,
                        '--action-file', action)
        self.assertEqual(prepared['stage'], 'one_pass')
        runtime = Runtime(str(self.db))
        try:
            pending = runtime.pending_kit_turn(prepared['turn_id'])['body']['events']
            self.assertTrue(any(event.get('type') == 'move' and
                                event.get('exit') == 'way_2' for event in pending), pending)
        finally:
            runtime.close()
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='ruling', focus_actor='none', table_presence='brief')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(reply_to='I go to the Tower.', scope='call')
        reply = {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': prepared['input']['private']['accepted_public_event'],
             'reacts_to': 'I go to the Tower.'}]}}
        session = prepared.get('session_manifest') or {}
        room_manifest = prepared.get('room_manifest') or {}
        if session.get('hash') and room_manifest.get('hash'):
            reply['manifest'] = {'session': session['hash'], 'room': room_manifest['hash']}
        output = self.folder / 'decision.json'
        output.write_text(json.dumps(reply))
        done = call('complete', '--db', self.db, '--turn-id', prepared['turn_id'],
                    '--input-file', output)
        self.assertEqual(done['timing']['outcome'], 'committed')
        self.assertIn('Tower', done['spoken'])
        runtime = Runtime(str(self.db))
        try:
            self.assertTrue(runtime.source()['id'].endswith('-2'))
            self.assertEqual(runtime.load()[1]['area'], 'to_1')
        finally:
            runtime.close()

    def test_unrelated_hidden_actor_still_fails_room_validation(self):
        room = json.loads(Path(self.accepted['room']).read_text(encoding='utf-8'))
        room['actors']['unattested_orphan'] = {
            'name': 'Unattested Orphan', 'location': 'here', 'status': 'hidden',
            'visible': False, 'stat_block': {'srd': 'bandit'},
        }
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            kit_rooms.check_room(room, 'synthetic')
        self.assertIn('unattested_orphan', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
