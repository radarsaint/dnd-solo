"""Source-grounded opening interpretation and the existing rules path.

All examples are original synthetic scenarios; no published adventure text.
"""
import tempfile
import unittest
from pathlib import Path

from runtime import kit_adventure, kit_scene_contract, kit_skim
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json'
FICTION = 'The caravan halts on the road beneath a leaning pine.'
ENCOUNTER = ('Two bandits hide by the ditch and want the caravan supplies. '
             'A careful look notices the broken branches under the pine.')
SOURCE = ('A caravan boss has hired the party in the distant city.\n'
          'The North Road\n> ' + FICTION + '\n' + ENCOUNTER + '\n'
          '2. The Tower\n> A bell rings on a high tower.\n')
SCENE = {
    'place': {'name': 'road', 'quote': FICTION},
    'people': [{
        'id': 'bandit', 'name': 'bandits', 'quote': 'Two bandits hide by the ditch and want the caravan supplies.',
        'visibility': 'hidden', 'kind': 'creature',
        'goal': {'quote': 'Two bandits hide by the ditch and want the caravan supplies.', 'status': 'established'},
        'knowledge': [],
    }],
    'discoveries': [{'quote': 'A careful look notices the broken branches under the pine.',
                     'status': 'conditional'}],
    'pressures': [{'kind': 'ambush', 'quote': 'Two bandits hide by the ditch and want the caravan supplies.',
                   'status': 'conditional', 'actors': ['bandit'], 'activation': 'deferred'}],
}


def _copy(data):
    import json
    return json.loads(json.dumps(data))


class SceneContractTests(unittest.TestCase):
    def test_the_host_supplies_meaning_python_attests_quotes(self):
        self.assertEqual(kit_scene_contract.validate(SCENE, FICTION + '\n' + ENCOUNTER, FICTION), [])
        beat = kit_scene_contract.build_beat(SCENE, FICTION, 'The North Road')
        self.assertTrue(beat['source_verified'])
        self.assertEqual(beat['place_noun'], 'road')
        self.assertEqual(beat['people'][0]['name'], 'bandits')
        self.assertIn('want the caravan supplies', beat['pressure']['goal'])
        self.assertTrue(beat['people'][0]['hidden'])

    def test_the_source_boundary_excludes_a_later_room(self):
        changed = _copy(SCENE)
        changed['people'][0]['quote'] = 'A bell rings on a high tower.'
        self.assertTrue(any('outside' in p for p in kit_scene_contract.validate(
            changed, FICTION + '\n' + ENCOUNTER, FICTION)))

    def test_visible_foe_needs_player_visible_source(self):
        changed = _copy(SCENE)
        changed['people'][0]['visibility'] = 'visible'
        self.assertTrue(any('visibility' in p for p in kit_scene_contract.validate(
            changed, FICTION + '\n' + ENCOUNTER, FICTION)))

    def test_conditional_fact_cannot_drop_its_if_clause(self):
        condition = 'If the warning bell rings, the sentries lower the barrier.'
        new_scene = _copy(SCENE)
        new_scene['people'][0]['goal'] = {
            'quote': 'the sentries lower the barrier.', 'status': 'established'}
        problems = kit_scene_contract.validate(new_scene, FICTION + '\n' + ENCOUNTER + '\n' + condition, FICTION)
        self.assertTrue(any('entire source sentence' in x for x in problems), problems)

    def test_unquoted_motive_and_mechanics_are_rejected(self):
        changed = _copy(SCENE)
        changed['people'][0]['goal']['quote'] = 'take over the kingdom'
        self.assertTrue(any('goal' in p for p in kit_scene_contract.validate(
            changed, FICTION + '\n' + ENCOUNTER, FICTION)))
        changed = _copy(SCENE)
        changed['pressures'][0]['dc'] = 10
        self.assertTrue(any('fields' in p for p in kit_scene_contract.validate(
            changed, FICTION + '\n' + ENCOUNTER, FICTION)))

    def test_unsupported_mechanics_do_not_promote_to_scene_facts(self):
        changed = _copy(SCENE)
        changed['pressures'][0]['status'] = 'unsupported'
        self.assertTrue(any('unsupported' in p for p in kit_scene_contract.validate(
            changed, FICTION + '\n' + ENCOUNTER, FICTION)))

    def test_scene_must_not_name_a_character_from_prior_setup(self):
        changed = _copy(SCENE)
        changed['people'][0]['name'] = 'boss'
        self.assertTrue(any('name' in p for p in kit_scene_contract.validate(
            changed, FICTION + '\n' + ENCOUNTER, FICTION)))


class ScenePlayerPathTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / 'kit.sqlite'
        kit_adventure.ingest_adventure(self.db, text=SOURCE)

    def _accept(self, scene=None):
        data = {
            'burst': FICTION, 'source_quote': FICTION,
            'page_start': 1, 'page_end': 1,
            'alt_starts': [{'title': 'The North Road', 'page': 1}],
            'design_start_name': 'The North Road',
            'scene': _copy(SCENE if scene is None else scene),
        }
        return kit_skim.accept(self.db, data)

    def test_accepted_scene_is_the_one_shared_beat(self):
        result = self._accept()
        self.assertEqual(result['stage'], 'skim_accepted', result)
        skim = kit_skim._read(self.db)
        self.assertTrue(skim['beat']['source_verified'])
        self.assertEqual(skim['beat']['place_noun'], 'road')
        self.assertIn('want the caravan supplies', skim['beat']['pressure']['goal'])
        self.assertEqual(len(skim['beat']['people']), 1)

    def test_invalid_scene_refuses_before_binding_a_room(self):
        scene = _copy(SCENE)
        scene['people'][0]['quote'] = 'Bandits who are not in this chapter appear.'
        result = self._accept(scene)
        self.assertEqual(result['stage'], 'skim_rejected')
        self.assertEqual(kit_skim._read(self.db)['status'], 'rejected')

    def test_sneak_declares_an_attempt_not_a_successful_bypass(self):
        result = self._accept()
        self.assertEqual(result['stage'], 'skim_accepted', result)
        start_session(str(self.db), str(SHEET))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        first = bridge.prepare('Yes.')
        self.assertTrue(first.get('spoken'))
        result = bridge.prepare('I sneak past the bandits.', one_pass=True)
        # Unlike the former opening handler this must not silently commit a bypass.
        self.assertNotEqual(result.get('stage'), 'bypass')
        self.assertNotIn('You slip past.', result.get('spoken') or '')
        self.assertEqual((runtime.load()[1].get('room') or {}).get('id'), runtime.source().get('id'))


class NativeOpeningPathTests(ScenePlayerPathTests):
    def _play(self, action, roll=None):
        self.assertEqual(self._accept()['stage'], 'skim_accepted')
        start_session(str(self.db), str(SHEET))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        opened = bridge.prepare('Yes.')
        self.assertIn('road', opened.get('spoken', '').lower())
        adjudicator = RoomAdjudicator()
        adjudicator.mount(runtime.source())
        revision, state = runtime.load()
        result = adjudicator.resolve(action, revision, state)
        committed = runtime.commit('native-%s' % revision, revision, list(result.events))
        if roll:
            revision, state = runtime.load()
            next_result = adjudicator.resolve(roll, revision, state)
            runtime.commit('native-%s' % revision, revision, list(next_result.events))
            return result, next_result, runtime
        return result, None, runtime

    def test_observe_cites_hidden_people_and_requires_a_roll(self):
        first, later, runtime = self._play('I look around.', 'Perception 18')
        self.assertEqual(first.kind, 'check_called')
        self.assertIn('Perception', first.public_event)
        self.assertNotIn('Bandit', first.public_event)
        self.assertIn('Bandit', later.public_event)
        self.assertNotIn('DC', later.public_event)
        self.assertFalse((runtime.load()[1].get('combat') or {}).get('status') == 'running')

    def test_stealth_does_not_autosucceed(self):
        first, later, runtime = self._play('I sneak past the bandits.', 'Stealth 18')
        self.assertEqual(first.kind, 'check_called')
        self.assertIn('Stealth', first.public_event)
        self.assertNotIn('slip past', first.public_event)
        self.assertEqual(later.kind, 'stealth')
        self.assertIsNotNone(runtime.load()[1].get('standing_check'))

    def test_talking_does_not_trigger_immediate_ambush(self):
        first, _, runtime = self._play('I call out to the bandits.')
        self.assertEqual(first.kind, 'social')
        self.assertIn('road', first.public_event)
        self.assertNotIn('the room', first.public_event)
        self.assertFalse(any(e['type'] == 'combat_state' for e in first.events))
        self.assertFalse((runtime.load()[1].get('combat') or {}).get('status') == 'running')

    def test_unwritten_object_action_reaches_general_adjudicator(self):
        first, _, runtime = self._play('I burn the wagon.')
        self.assertNotEqual(first.kind, 'bypass')
        self.assertNotIn('Roll initiative', first.public_event)
        self.assertFalse(any(e['type'] == 'combat_state' for e in first.events))

    def _multi_line(self):
        second = 'You hear a mule braying from the ditch.'
        kit_adventure.import_adventure(self.db, text=SOURCE.replace(
            '> ' + FICTION, '> ' + FICTION + '\n> ' + second))
        self.assertEqual(self._accept()['stage'], 'skim_accepted')
        start_session(str(self.db), str(SHEET))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        opened = bridge.prepare('Yes.')
        self.assertIn('caravan', opened.get('spoken', '').lower())
        return runtime, bridge, second

    def test_go_on_cursor_is_authoritative_in_sqlite_and_does_not_repeat(self):
        from runtime import kit_skim
        runtime, bridge, second = self._multi_line()
        line = bridge.prepare('Go on')
        self.assertIn(second, line['spoken'])
        expected = runtime.load()[1]['opening_cursor']['heard']
        self.assertGreater(expected, 0)
        stale = kit_skim._read(self.db)
        stale['beat']['heard'] = 0
        kit_skim._write(self.db, stale)
        again = bridge.prepare('Go on')
        self.assertNotIn(second, again.get('spoken', ''))
        self.assertIn('opening', again.get('spoken', '').lower())

    def test_failed_commit_does_not_advance_read_aloud_sidecar(self):
        from unittest import mock
        from runtime import kit_skim
        runtime, bridge, second = self._multi_line()
        before = kit_skim._read(self.db)['beat']['heard']
        with mock.patch.object(runtime, 'commit', side_effect=RuntimeError('database unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'database unavailable'):
                kit_skim.release(runtime, 'Go on')
        after = kit_skim._read(self.db)['beat']['heard']
        self.assertEqual(after, before)
        self.assertFalse(runtime.load()[1].get('opening_cursor'))


class PdfHostContractTests(unittest.TestCase):
    @unittest.skipUnless(__import__('shutil').which('pdftotext'), 'pdftotext is not installed')
    def test_two_column_dot_leader_pdf_opens_and_recovers_later_pages(self):
        import time
        from test_kit_adventure_pdf import make_pdf
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            pdf = folder / 'synthetic.pdf'
            pdf.write_bytes(make_pdf([
                [('text', 70, 700, 'Contents ' + '.' * 80 + ' 2', 10)],
                [('text', 70, 735, '1. The North Road', 11),
                 ('text', 70, 700, FICTION, 9),
                 ('text', 323, 700, 'A sidebar explains how to use the road.', 9),
                 ('text', 70, 670, 'Two bandits hide by the ditch and want the caravan supplies.', 9),
                 ('text', 70, 630, 'A careful look notices the broken branches under the pine.', 9),
                 ('text', 70, 555, '2. The Tower', 11),
                 ('text', 70, 525, 'A bell rings on a high tower.', 9)],
            ]))
            db = folder / 'kit.sqlite'
            started = time.perf_counter()
            report = kit_adventure.ingest_adventure(db, pdf=str(pdf), reader='pdftotext')
            elapsed = time.perf_counter() - started
            self.assertEqual(report['reader'], 'pdftotext')
            self.assertLess(elapsed, 8.0, 'synthetic local file only; not a published book benchmark')
            self.assertEqual(report['locations'], 2)
            skim = kit_skim.accept(db, {
                'burst': FICTION, 'source_quote': FICTION,
                'page_start': 2, 'page_end': 2,
                'alt_starts': [{'title': 'The North Road', 'page': 2}],
                'design_start_name': 'The North Road', 'scene': _copy(SCENE),
            })
            self.assertEqual(skim['stage'], 'skim_accepted', skim)
            self.assertEqual(kit_skim._read(db)['beat']['place_noun'], 'road')
            start_session(str(db), str(SHEET))
            runtime = Runtime(str(db))
            try:
                first = KitChatBridge(runtime, RoomAdjudicator()).prepare('Yes.')
                self.assertIn(FICTION, first['spoken'])
            finally:
                runtime.close()
            pdf.unlink()
            # Later chapters remain available even if the original upload is gone.
            deep = kit_adventure.deepen_index(db)
            self.assertEqual(deep['stage'], 'index_deep')
            self.assertEqual(deep['locations'], 2)
            compiled = kit_adventure.compile_location(db, '2', neighbours=False)
            self.assertTrue(Path(compiled['room']).is_file())
            recovered = Runtime(str(db))
            try:
                self.assertTrue(recovered.source())
            finally:
                recovered.close()


if __name__ == '__main__':
    unittest.main()
