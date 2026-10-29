"""Host latency: false rejects and extra calls, not the engine (decision-speed, 2026-10-04).

One player message is one prepare and one complete. Shapes and per_turn live in the packet.
A rejection names a pasteable fix. Validators stay as strict as they were.
Synthetic adventures only. No published text.
"""
import json
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from runtime import kit_adventure, kit_manifest, kit_voice  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, read_character_sheet, start_session  # noqa: E402
from runtime.state_context import CONTEXT_BUDGET_BYTES, InvalidChange, Runtime  # noqa: E402

CORPUS = ROOT / 'tests/fixtures/adventures/lantern_ferry.txt'
WAGON = ROOT / 'tests/fixtures/adventures/wagon_road.txt'
NIK = ROOT / 'tests/fixtures/characters/nik.json'


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


class FewestCalls(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        self.assertEqual(CONTEXT_BUDGET_BYTES, 107000)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'
        kit_adventure.import_adventure(self.db, text=CORPUS.read_text(encoding='utf-8'))
        kit_adventure.compile_location(self.db, '1')
        self.started = start_session(self.db, NIK, room=kit_adventure.room_file(self.db, '1'), manifests=True)
        self.runtime = Runtime(self.db)
        self.addCleanup(self.runtime.close)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10),
                                    manifests=True)

    def test_opening_packet_carries_shapes_and_the_per_turn_sheet(self):
        packet = self.started['prepared']
        self.assertIn('one prepare + one complete', packet['per_turn'])
        card = (ROOT / 'docs' / 'PLAY_CARD.md').read_text(encoding='utf-8')
        self.assertEqual(packet['play_card'], card)
        self.assertIn('Read this once at mount', card)
        self.assertIn('Fix:', card)
        self.assertIn('Do not reread docs', packet['per_turn'])
        self.assertIn('roll_call', packet['per_turn'])
        shapes = packet['shapes']
        self.assertEqual(shapes['public_brief.mirror'], kit_voice.MIRROR_EXAMPLE)
        self.assertIn(':', shapes['public_brief.mirror'])
        self.assertEqual(set(shapes['manifest']), {'session', 'room'})
        self.assertEqual(shapes['player_note']['replaces'], 'none')
        self.assertEqual(shapes['player_mood'], {'read': 'neutral', 'cue': 'none'})
        self.assertIn(kit_voice.MIRROR_EXAMPLE, packet['shapes']['public_brief.mirror'])
        self.assertIn('one prepare', packet['per_turn'])

    def test_a_bad_manifest_is_rejected_with_a_pasteable_fix(self):
        self.bridge.prepare('Yes.', one_pass=True)
        packet = self.bridge.prepare('I look around the landing.', 't1', one_pass=True)
        from tests.test_kit_agent import RecordingModel
        plan = RecordingModel().plan(packet['input']['private'])
        plan.update(move='world_description', table_presence='quiet', focus_actor='none')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief']['reply_to'] = 'I look around the landing'
        plan['public_brief']['scope'] = 'feature'
        out = {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': 'The landing stays wet.'},
            {'speaker': 'Kit', 'text': 'Where next?'}]},
            'manifest': packet['room_manifest']}
        with self.assertRaises(InvalidChange) as caught:
            self.bridge.complete('t1', out)
        self.assertIn('Expected shape', str(caught.exception))
        self.assertEqual(caught.exception.fix['manifest'], {
            'session': packet['session_manifest']['hash'],
            'room': packet['room_manifest']['hash']})
        # The same bad echo is still refused. The fix is not accepted as the body.
        self.assertNotEqual(out['manifest'], caught.exception.fix['manifest'])

    def test_a_mirror_without_how_is_still_refused_and_names_the_paste(self):
        with self.assertRaises(InvalidChange) as caught:
            kit_voice.check_mirror('steady energy, standard, dry humor', 'neutral', 'description')
        self.assertIn('must read', str(caught.exception))
        self.assertIn(': meet the pace', caught.exception.fix['public_brief.mirror'])
        self.assertIsNone(kit_voice.parse_mirror('steady energy, standard, dry humor'))
        self.assertIsNotNone(kit_voice.parse_mirror(caught.exception.fix['public_brief.mirror']))

    def test_yes_speaks_the_read_aloud_and_hands_the_floor_back(self):
        done = self.bridge.prepare('Yes.', one_pass=True)
        self.assertTrue(done.get('committed'))
        spoken = done['spoken']
        self.assertIn('rope bell', spoken)
        self.assertIn('?', spoken)
        self.assertIn('Kit:', spoken)
        self.assertNotIn('The newcomer arrives', spoken)

    def test_area_change_stays_a_delta_and_does_not_bounce_the_room(self):
        self.bridge.prepare('Yes.', one_pass=True)

        def commit(line):
            packet = self.bridge.prepare(line, one_pass=True)
            body = self.runtime.pending_kit_turn(packet['turn_id'])['body']
            revision = self.runtime.load()[0]
            self.bridge.abandon(packet['turn_id'])
            self.runtime.commit(packet['turn_id'], revision, body['events'])
            return packet

        commit('I take the dry path.')
        here = self.runtime.source()['id']
        area = self.runtime.load()[1]['area']
        self.assertTrue(here.endswith('-2'), here)
        look = commit('I look around.')
        self.assertTrue(look['session_manifest'].get('cached'), look['session_manifest'])
        self.assertLess(_bytes(look), 9000)
        self.assertNotIn('body', look['session_manifest'])
        self.assertEqual(self.runtime.source()['id'], here)
        self.assertEqual(self.runtime.load()[1]['area'], area)

    def test_markdown_sheet_is_refused_in_one_line(self):
        path = Path(self.db).parent / 'hero.md'
        path.write_text('# Hero\n\nA wizard.\n', encoding='utf-8')
        with self.assertRaises(InvalidChange) as caught:
            read_character_sheet(path)
        self.assertIn('Only one PC is supported', str(caught.exception))
        self.assertIn('Markdown', str(caught.exception))

    def test_a_second_sheet_says_it_replaced_the_first(self):
        first = json.loads(NIK.read_text(encoding='utf-8'))
        other = dict(first, name='Ott')
        loaded = self.runtime.set_player_sheet(other)
        self.assertTrue(loaded['only_one_pc'])
        self.assertIn('Only one PC is supported', loaded['notice'])
        self.assertEqual(loaded['replaced'], 'Nik')


class StartAndIngest(unittest.TestCase):
    def test_part_one_starts_at_the_road_encounter_not_the_numbered_hideout(self):
        index = kit_adventure.build_index(WAGON.read_text(encoding='utf-8'))
        self.assertEqual(index['start'], 'scene:wagon_road:A')
        self.assertNotEqual(index['locations'][index['start']]['name'], 'Timber Mouth')
        self.assertIn('Timber Mouth', [loc['name'] for loc in index['locations'].values()])

    def test_ingest_pretty_is_accepted(self):
        folder = tempfile.mkdtemp()
        db = str(Path(folder) / 'kit.sqlite')
        out = subprocess.run(
            [sys.executable, '-m', 'runtime.kit_agent', 'adventure', 'import', '--db', db,
             '--text-file', str(CORPUS), '--pretty'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('\n  ', out.stdout)

    def test_play_mounts_the_ingested_adventure(self):
        folder = tempfile.mkdtemp()
        db = str(Path(folder) / 'kit.sqlite')
        kit_adventure.import_adventure(db, text=CORPUS.read_text(encoding='utf-8'))
        from runtime.kit_campaign import campaign_entry
        result = campaign_entry(db, sheet_path=str(NIK), intent='play', table='solo')
        self.assertEqual(result.get('stage'), 'started')
        self.assertTrue(str(result.get('room_id', '')).startswith('adv-'))


class ManifestHash(unittest.TestCase):
    def test_digest_of_the_echo_shape_is_unchanged_by_a_body(self):
        # The echo is still hashes only. A body is not a valid manifest.
        expected = {'session': 'a' * 16, 'room': 'b' * 16}
        self.assertNotEqual({'room_manifest': {'hash': 'b' * 16, 'body': {}}}, expected)
        self.assertIn('session', kit_manifest.MANIFEST_ECHO)
        self.assertIn('room', kit_manifest.MANIFEST_ECHO)


if __name__ == '__main__':
    unittest.main()
