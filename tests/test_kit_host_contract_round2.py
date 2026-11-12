"""Host transcript contract: the real CLI, not direct scene-contract APIs.

All printed text is original synthetic test prose. No published content.
Each test starts from a PDF, uses pdftotext, stages the host form, then drives
start -> prepare -> complete -> bare-roll prepare through Kit's own CLI.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import which

from test_kit_adventure_pdf import make_pdf
from test_kit_agent import RecordingModel
from test_kit_scene_contract_gpt import FICTION, SCENE, SHEET

ROOT = Path(__file__).resolve().parents[1]
PRESENCE = 'Two bandits hide by the ditch and want the caravan supplies.'
FIND = 'A careful look notices the broken branches under the pine.'
AFTER = '2. The Tower'


def call(*args):
    done = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, timeout=18)
    if done.returncode:
        raise AssertionError('Host CLI failure: %s\n%s' % (done.stdout, done.stderr))
    try:
        return json.loads(done.stdout)
    except ValueError:
        raise AssertionError('Non-JSON host packet: %r' % done.stdout)


@unittest.skipUnless(which('pdftotext'), 'requires pdftotext -layout')
class NormalHostPath(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)
        self.db = self.dir / 'game.sqlite'
        self.pdf = self.dir / 'source.pdf'

    def write_pdf(self, order):
        # Box precedes, follows or is interrupted by the encounter. Include a
        # contents dot leader and a sidebar so the layout is not an API fixture.
        if order == 'before':
            layout = [('text', 70, 700, FICTION, 9),
                      ('text', 70, 670, PRESENCE, 9),
                      ('text', 70, 640, FIND, 9)]
        elif order == 'after':
            layout = [('text', 70, 700, PRESENCE, 9),
                      ('text', 70, 670, FIND, 9),
                      ('text', 70, 640, FICTION, 9)]
        else:
            layout = [('text', 70, 700, PRESENCE, 9),
                      ('text', 70, 670, FICTION, 9),
                      ('text', 70, 640, FIND, 9)]
        self.pdf.write_bytes(make_pdf([
            [('text', 70, 700, 'Contents ' + '.' * 80 + ' 2', 10)],
            [('text', 70, 735, '1. The North Road', 11),
             ('text', 323, 700, 'A sidebar about supplies and weather.', 9),
             *layout,
             ('text', 70, 555, AFTER, 11),
             ('text', 70, 525, 'A bell rings on a high tower.', 9)],
        ]))

    def skim(self, order):
        self.write_pdf(order)
        received = call('ingest', self.pdf, '--reader', 'pdftotext', '--db', self.db)
        self.assertTrue(received.get('skim_request', {}).get('source_verified_required'))
        early = {
            'burst': FICTION, 'source_quote': FICTION,
            'page_start': 2, 'page_end': 2, 'alt_starts': [],
            'design_start_name': 'The North Road',
        }
        form = self.dir / 'skim.json'
        form.write_text(json.dumps(early))
        missing = call('adventure', 'skim', '--db', self.db, '--file', form)
        self.assertEqual(missing['stage'], 'scene_required', missing)
        bound = missing['scene_request']['source_span']
        self.assertIn(PRESENCE, bound)
        self.assertIn(FICTION, bound)
        self.assertIn(FIND, bound)
        self.assertNotIn('A bell rings on a high tower', bound)
        self.assertFalse(missing.get('committed'))
        # The host is given exact field errors and a source excerpt; the repair
        # is a scene-only JSON object, not a new room or a new skim.
        bad = json.loads(json.dumps(SCENE))
        bad['people'][0]['quote'] = 'A fabricated sentry.'
        form.write_text(json.dumps({'scene': bad}))
        repair = call('adventure', 'skim', '--db', self.db, '--file', form)
        self.assertEqual(repair['stage'], 'scene_required', repair)
        self.assertIn('people[0]', ' '.join(repair['scene_request']['problems']))
        form.write_text(json.dumps({'scene': SCENE}))
        accepted = call('adventure', 'skim', '--db', self.db, '--file', form)
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        self.assertNotIn('source_span', json.dumps(accepted))
        return accepted

    def action(self, text):
        path = self.dir / 'action.txt'
        path.write_text(text)
        return call('prepare', '--one-pass', '--db', self.db, '--action-file', path)

    def start(self):
        started = call('start', '--db', self.db, '--sheet', SHEET)
        self.assertEqual(started['stage'], 'started', started)
        opening = self.action('Yes.')
        self.assertIn(FICTION, opening.get('spoken') or '')
        return opening

    def complete_check(self, packet):
        self.assertEqual(packet.get('stage'), 'one_pass', packet)
        private = packet['input']['private']
        plan = RecordingModel().plan(private)
        plan.update(move='ruling', table_presence='brief', focus_actor='none', roll_call={
            'skill': 'perception', 'mode': 'normal', 'target': 'none',
            'cause': {'kind': 'position', 'ref': 'none', 'roots': []}})
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(reply_to='look around', scope='call')
        payload = {'decision': plan,
                   'performance': {'segments': [
                       {'speaker': 'Kit', 'text': 'Roll Perception for it.', 'reacts_to': 'look around'}]}}
        # The real host response supplies the manifest when the CLI sends it.
        session = packet.get('session_manifest') or {}
        room = packet.get('room_manifest') or {}
        if session.get('hash') and room.get('hash'):
            payload['manifest'] = {'session': session['hash'], 'room': room['hash']}
        file = self.dir / 'output.json'
        file.write_text(json.dumps(payload))
        response = call('complete', '--db', self.db, '--turn-id', packet['turn_id'], '--input-file', file)
        self.assertIn('Roll Perception', response.get('spoken') or '')
        return response

    def test_normal_host_path_handles_missing_form_repair_roll_and_restart(self):
        for order in ('before', 'after', 'middle'):
            with self.subTest(order=order):
                # One independent save and synthetic source per layout.
                self.db = self.dir / (order + '.sqlite')
                self.skim(order)
                self.start()
                called = self.action('I look around.')
                self.complete_check(called)
                found = self.action('18')
                self.assertEqual(found['stage'], 'called_roll', found)
                self.assertIn('Bandit', found.get('spoken') or '')
                self.assertNotIn('DC', found.get('spoken') or '')
                self.assertNotIn('surprised', found.get('spoken') or '')
                self.pdf.unlink()
                # The PDF retained with the save survives removal of the upload.
                indexed = call('adventure', 'index', '--db', self.db)
                self.assertEqual(indexed.get('stage'), 'index_deep', indexed)
                # Recovery uses a fresh process for every CLI call.
                again = self.action('18')
                self.assertEqual(again['stage'], 'roll_clarify', again)
                self.assertIn('What is the 18 for?', again['spoken'])
    def test_unwritten_action_reaches_a_committed_table_ready_clarification(self):
        self.skim('before')
        self.start()
        packet = self.action('I burn the wagon.')
        self.assertEqual(packet.get('stage'), 'one_pass', packet)
        goal = packet['input']['private']['accepted_public_event']
        self.assertIn('set it alight', goal)
        self.assertNotIn('rules the act', goal)
        plan = RecordingModel().plan(packet['input']['private'])
        plan.update(move='ruling', table_presence='brief', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(reply_to='I burn the wagon.', scope='call')
        payload = {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': goal, 'reacts_to': 'I burn the wagon.'}]}}
        session = packet.get('session_manifest') or {}
        room = packet.get('room_manifest') or {}
        if session.get('hash') and room.get('hash'):
            payload['manifest'] = {'session': session['hash'], 'room': room['hash']}
        out = self.dir / 'clarify.json'
        out.write_text(json.dumps(payload))
        result = call('complete', '--db', self.db, '--turn-id', packet['turn_id'], '--input-file', out)
        self.assertIn('set it alight', result.get('spoken') or '')
        self.assertEqual((result.get('timing') or {}).get('outcome'), 'committed', result)
        self.assertNotIn('rules the act', result.get('spoken') or '')


    def test_sneak_and_roll_use_real_complete_path_without_free_bypass(self):
        self.skim('middle')
        self.start()
        packet = self.action('I sneak past the bandits.')
        self.assertEqual(packet.get('stage'), 'one_pass', packet)
        self.assertIn('Roll Stealth', packet['input']['private']['accepted_public_event'])
        plan = RecordingModel().plan(packet['input']['private'])
        plan.update(move='ruling', table_presence='brief', focus_actor='none', roll_call={
            'skill': 'stealth', 'mode': 'normal', 'target': 'none',
            'cause': {'kind': 'position', 'ref': 'none', 'roots': []}})
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(reply_to='I sneak past the bandits.', scope='call')
        payload = {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'Roll Stealth for it.',
             'reacts_to': 'I sneak past the bandits.'}]}}
        session = packet.get('session_manifest') or {}
        room = packet.get('room_manifest') or {}
        if session.get('hash') and room.get('hash'):
            payload['manifest'] = {'session': session['hash'], 'room': room['hash']}
        output = self.dir / 'stealth.json'
        output.write_text(json.dumps(payload))
        completed = call('complete', '--db', self.db, '--turn-id', packet['turn_id'],
                         '--input-file', output)
        self.assertIn('Roll Stealth', completed.get('spoken') or '')
        self.assertEqual(completed['timing']['outcome'], 'committed')
        rolled = self.action('18')
        self.assertEqual(rolled['stage'], 'called_roll', rolled)
        self.assertNotIn('You slip past.', rolled.get('spoken') or '')
        self.assertNotIn('Roll initiative', rolled.get('spoken') or '')


class StagedSceneTests(unittest.TestCase):
    """A read-aloud character reaches the actual persistent social bridge on Go on."""

    def test_mentioned_later_character_enters_on_go_on_not_before(self):
        from runtime import kit_adventure, kit_skim
        from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
        from runtime.state_context import Runtime
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / 'stage.sqlite'
            intro = 'The caravan halts on the road beneath a leaning pine.'
            next_line = 'Captain Mara steps onto the road and hails the caravan.'
            orders = 'Captain Mara has orders to hold the road until the wagons pass.'
            source = ('1. The North Road\n> ' + intro + '\n'
                      'Decide marching order before reaching the pass.\n'
                      '> ' + next_line + '\n' + orders + '\n'
                      '2. The Tower\n> A bell rings on a high tower.\n')
            kit_adventure.ingest_adventure(db, text=source)
            scene = {'place': {'name': 'road', 'quote': intro},
                     'people': [{'id': 'captain_mara', 'name': 'Captain Mara',
                                 'quote': next_line, 'visibility': 'staged', 'kind': 'person',
                                 'goal': {'quote': orders, 'status': 'established'},
                                 'knowledge': []}],
                     'discoveries': [], 'pressures': []}
            reply = {'burst': intro, 'source_quote': intro,
                     'page_start': 1, 'page_end': 1,
                     'alt_starts': [], 'design_start_name': 'The North Road',
                     'scene': scene}
            accepted = kit_skim.accept(db, reply)
            self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
            start_session(str(db), str(SHEET))
            runtime = Runtime(str(db))
            self.addCleanup(runtime.close)
            bridge = KitChatBridge(runtime, RoomAdjudicator())
            first = bridge.prepare('Yes.')
            self.assertIn(intro, first.get('spoken') or '')
            self.assertNotIn('Captain Mara', first.get('spoken') or '')
            self.assertEqual(runtime.load()[1]['actors']['captain_mara']['status'], 'hidden')
            second = bridge.prepare('Go on')
            self.assertIn(next_line, second.get('spoken') or '')
            self.assertNotIn('Decide marching order', second.get('spoken') or '')
            self.assertEqual(runtime.load()[1]['actors']['captain_mara']['status'], 'alive')
            third = bridge.prepare('I talk to Captain Mara.', one_pass=True)
            self.assertEqual(third.get('stage'), 'one_pass', third)
            event = third['input']['private']['accepted_public_event']
            self.assertIn('Captain Mara', event)
            self.assertNotIn('the room', event)
            self.assertNotIn('call out across', event)
            fourth = bridge.prepare('Go on')
            self.assertNotIn(next_line, fourth.get('spoken') or '')

