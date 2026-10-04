"""Source-to-room authoring (docs/architecture/SOURCE_TO_ROOM.md): Kit writes a room file from
the book's keyed text; the engine validates it, allows one repair, falls back cleanly, and
caches it per session. The keyed text here is SYNTHETIC (tests/fixtures/authoring), written
in the style of a published adventure, with three kinds of area: an NPC room with a toll and
an alarm (1), a trapped hall with sub-areas (2, 2a, 2b), and a monster lair (3). No book text."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_author, kit_rooms, kit_source
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, start_session
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'tests/fixtures/authoring'
TEXT = (FIX / 'keyed_text.txt').read_text(encoding='utf-8')
MAP_INDEX = FIX / 'MAP_INDEX.md'
LEDGER = FIX / 'geometry/LEVEL_01.json'
NIK = ROOT / 'tests/fixtures/characters/nik.json'


def book(text=TEXT, ledger=None):
    return kit_author.Book(1, text=text, map_index=MAP_INDEX, ledger=ledger or FIX / 'no-ledger.json')


def lair_room(**changes):
    """A room for area 3 (the lair) as Kit would write it from the packet."""
    room = {
        'id': 'authored-level-01-area-3', 'source_ref': 'Level 1 / 3. Spider Loft (authored)',
        'starting_area': 'loft_mouth',
        'areas': {
            'loft_mouth': {'name': 'Below the loft', 'called': 'the foot of the loft', 'source_area': '3',
                           'outside': True,
                           'tease': {'text': 'Torn webbing sags from the beams above a slope of rubble; the air '
                                             'smells of old dust and something sour.', 'heard': []}},
            'loft': {'name': 'Spider Loft', 'called': 'the loft', 'source_area': '3',
                     'arrival': 'A newcomer climbs into the loft.'},
            'hall_end': {'name': 'The needle hall', 'called': 'the hall', 'source_area': '2', 'outside': True,
                         'beyond': True, 'room_link': {'author': {'level': '01', 'area': '2'}}},
        },
        'exits': {
            'loft_climb': {'name': 'the rubble slope', 'areas': ['loft_mouth', 'loft'], 'secret': False,
                           'labels': {'loft_mouth': 'A rubble slope climbs into the loft.',
                                      'loft': 'The rubble slope back down.'}},
            'west_hall': {'name': 'the hall west', 'areas': ['loft', 'hall_end'], 'secret': False,
                          'labels': {'loft': 'The hall runs west.', 'hall_end': 'The loft, back east.'}},
        },
        'facts': {
            'rubble': {'area': 'loft', 'visible': True, 'text': 'Rubble fills the west half of the loft.',
                       'handling': {'nouns': ['rubble'], 'look': 'You shift a few stones.',
                                    'move': 'You drag a slab aside.'}},
            'webbing': {'area': 'loft', 'visible': True, 'text': 'Torn webbing sags from the beams.'},
            'pouch': {'area': 'loft', 'visible': False, 'text': 'A dead prospector under the rubble wears a '
                                                                'pouch holding 12 gp.'},
        },
        'actors': {
            f'centipede_{n}': {'name': 'Giant centipede', 'location': 'loft', 'status': 'hidden', 'visible': False,
                               'motive': 'Feed.', 'knowledge': [], 'secrets': [],
                               'communication_profile': {'rhythm': 'Clicking.', 'humor': 'None.'},
                               'stat_block': {'srd': 'Giant Centipede'}}
            for n in 'abc'},
        'triggers': [{'id': 'loft_entered', 'on': {'enter': 'loft'}, 'starts_combat': True,
                      'actors': ['centipede_a', 'centipede_b', 'centipede_c'], 'surprise': {'stealth': None},
                      'reveal': 'The rubble heaves and three giant centipedes pour out of it.'}],
        'story': {'loft': {'about': 'A nest that wakes the moment anyone climbs in.',
                           'endings': ['The PC kills the nest and finds the pouch.', 'The PC backs out.']}},
        'resources': {},
    }
    room.update(changes)
    return room


class Session(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = self.folder / 'play.sqlite'
        self.session = kit_author.Session(kit_author.session_dir(self.db))


class KeyedTextExtraction(unittest.TestCase):
    def test_areas_are_split_by_their_key_headings_in_index_order(self):
        areas = book().areas
        self.assertEqual(list(areas), ['1', '2', '2a', '2b', '3'])
        self.assertEqual(areas['2']['subareas'], ['2a', '2b'])
        self.assertEqual(areas['2a']['parent'], '2')
        self.assertEqual(areas['3']['title'], 'Spider Loft')

    def test_a_numbered_sidebar_and_the_next_level_are_not_areas(self):
        areas = book().areas
        self.assertNotIn('toll-keeper count', json.dumps(areas))  # the sidebar "1." before the level
        self.assertNotIn('Flooded Stair', json.dumps(areas))     # the next level's "1."
        self.assertNotIn('Chapter Two', json.dumps(areas['3']))

    def test_cross_references_and_level_notes(self):
        self.assertEqual(kit_source.area_refs('east into area 2, then (areas 3 and 4) or area 2b'),
                         ['2', '3', '4', '2b'])
        inputs = kit_author.area_inputs(book(), '1')
        notes = inputs['level_notes']
        self.assertTrue(any('Gatehouse' in line for line in notes['mentions']))
        self.assertEqual([npc['name'] for npc in notes['npcs']], ['Brannoc Vell'])  # named in its keyed text
        self.assertEqual(len(notes['geometry_rules']), 2)
        lair = kit_author.area_inputs(book(), '3')['level_notes']
        self.assertTrue(any('Areas 2–3' in line for line in lair['mentions']))  # a range covers 3
        self.assertEqual(lair['npcs'], [])


class AuthoringPacket(unittest.TestCase):
    def test_it_carries_the_slice_geometry_schema_and_rules(self):
        packet = kit_author.packet(book(), '2a')
        self.assertIn('pressure plate', ' '.join(packet['area']['keyed_text']).lower())
        self.assertEqual(packet['area']['parent']['key'], '2')
        self.assertIn('Tiny holes pock both walls', ' '.join(packet['area']['parent']['intro']))
        self.assertEqual({n['area'] for n in packet['named_neighbours']}, {'1', '3', '2b'})
        self.assertFalse(packet['geometry']['bound'])
        self.assertIn('Invent no corridors', packet['geometry']['rule'])
        self.assertEqual(packet['schema']['limits']['dm_only_bytes'], kit_rooms.DM_ONLY_ROOM_MAX_BYTES)
        self.assertIn('giant centipede', packet['schema']['srd_creatures'])
        rules = ' '.join(packet['hard_rules'])
        for must in ('Emit triggers yourself', '"status": "hidden"', 'alarm', 'stat_block', 'Data only'):
            self.assertIn(must, rules)

    def test_it_never_carries_another_area_s_text(self):
        others = {'1': 'Brannoc Vell, a bald toll-keeper', '2b': 'dead rat lies stiff', '3': 'Three giant centipedes',
                  '2a': 'loose flagstone'}
        for key in ('1', '2a', '2b', '3'):
            text = json.dumps(kit_author.packet(book(), key), ensure_ascii=False)
            for other, line in others.items():
                if other != key:
                    self.assertNotIn(line, text, f'{key} leaks {other}')

    def test_a_geometry_ledger_binds_the_exits(self):
        packet = kit_author.packet(book(ledger=LEDGER), '2a')
        self.assertTrue(packet['geometry']['bound'])
        self.assertEqual([e['to'] for e in packet['geometry']['exits']], ['2b', '1'])

    def test_the_packet_is_small(self):
        self.assertLess(len(json.dumps(kit_author.packet(book(), '1')).encode()), 9000)


class ValidateAndRepair(Session):
    def test_a_valid_room_loads_mounts_and_keeps_its_ambushers_hidden(self):
        result = self.session.submit(book(), '3', lair_room(), self.db)
        self.assertEqual(result['stage'], 'accepted', result)
        self.assertEqual(result['attempt'], 1)
        started = start_session(self.folder / 'run.sqlite', NIK, room=result['room_path'])
        public = json.dumps(started['prepared'])
        self.assertNotIn('centipede', public.lower())  # at the approach, nothing of them

    def test_an_invalid_room_gets_a_repair_packet_and_passes_on_the_second_try(self):
        bad = lair_room()
        del bad['triggers']                                            # the ambush, left to improvise
        bad['areas']['loft_mouth']['tease']['text'] = 'Centipedes click somewhere in the rubble.'  # a hidden actor
        bad['areas']['hall_end']['source_area'] = '9'                  # invented geometry
        bad['facts']['rubble']['code'] = 'import os'                   # not data
        first = self.session.submit(book(), '3', bad, self.db)
        self.assertEqual(first['stage'], 'repair')
        self.assertEqual(first['attempts_left'], 1)
        errors = ' | '.join(first['errors'])
        for named in ('declares no triggers', 'names a hidden actor', "source_area '9'", 'data only',
                      'hidden but no trigger wakes it'):
            self.assertIn(named, errors)
        self.assertEqual(first['packet']['previous_room'], bad)
        self.assertIn('keyed_text', first['packet']['area'])
        second = self.session.submit(book(), '3', lair_room(), self.db)
        self.assertEqual((second['stage'], second['attempt']), ('accepted', 2))

    def test_a_second_failure_falls_back_to_the_keyed_text_flagged(self):
        bad = lair_room(id='lair')
        self.assertEqual(self.session.submit(book(), '3', bad, self.db)['stage'], 'repair')
        result = self.session.submit(book(), '3', bad, self.db)
        self.assertEqual((result['stage'], result['flag'], result['improvise_from']),
                         ('fallback', 'authoring_fallback', 'keyed_text'))
        self.assertIn('Giant Centipedes. Three giant centipedes nest in the rubble. They attack all who enter.',
                      result['keyed_text'])
        self.assertIn("id must be 'authored-level-01-area-3'", result['errors'])
        # Final: a third submit does not reopen it, and asking again returns the fallback.
        self.assertEqual(self.session.submit(book(), '3', lair_room(), self.db)['stage'], 'fallback')
        self.assertEqual(self.session.request(book(), '3', self.db)['stage'], 'fallback')
        with self.assertRaises(kit_author.RoomNotAuthored) as caught:
            self.session.resolve_link({'author': {'level': '01', 'area': '3'}})
        self.assertEqual(caught.exception.host_view()['authoring']['flag'], 'authoring_fallback')

    def test_alarms_triggers_stat_blocks_and_ledger_geometry_are_checked(self):
        room = gate_room()
        room['facts']['bell'].pop('alarm')                      # a bell nobody answers
        room['actors']['brannoc'].pop('stat_block')             # armed, no numbers
        problems = kit_author.validate(room, kit_author.area_inputs(book(), '1'))['errors']
        self.assertTrue(any('looks like an alarm' in p for p in problems), problems)
        self.assertTrue(any('actor brannoc can fight but has no usable stat_block' in p for p in problems), problems)
        hall = {'id': 'authored-level-01-area-2a', 'source_ref': '2a', 'starting_area': 'west',
                'areas': {'west': {'name': 'West end', 'source_area': '2a', 'outside': True,
                                   'tease': {'text': 'A long hall, its walls pocked at knee height.', 'heard': []}},
                          'plate': {'name': 'Mid-hall', 'source_area': '2a'},
                          'loft': {'name': 'Loft', 'source_area': '3', 'outside': True, 'beyond': True}},
                'exits': {'w': {'name': 'the hall', 'areas': ['west', 'plate'], 'secret': False,
                                'labels': {'west': 'On.', 'plate': 'Back.'}},
                          'e': {'name': 'the loft way', 'areas': ['plate', 'loft'], 'secret': False,
                                'labels': {'plate': 'On to the loft.', 'loft': 'Back.'}}},
                'facts': {}, 'actors': {}}
        problems = kit_author.validate(hall, kit_author.area_inputs(book(ledger=LEDGER), '2a'))['errors']
        self.assertIn('exit e joins 3, which the geometry ledger does not connect to 2a', problems)


def gate_room():
    return {
        'id': 'authored-level-01-area-1', 'source_ref': 'Level 1 / 1. Gatehouse', 'starting_area': 'tunnel',
        'areas': {'tunnel': {'name': 'The tunnel', 'source_area': '1', 'outside': True,
                             'tease': {'text': 'Lamplight in a gatehouse window, and a pen scratching.',
                                       'points_to': 'toll', 'heard': [{'actor': 'brannoc', 'sound': 'a pen scratching'}]}},
                  'gate': {'name': 'Gatehouse', 'source_area': '1'}},
        'exits': {'window': {'name': 'the gate', 'areas': ['tunnel', 'gate'], 'secret': False,
                             'labels': {'tunnel': 'The gatehouse.', 'gate': 'The tunnel.'}}},
        'facts': {'bell': {'area': 'gate', 'visible': True, 'text': 'A brass bell hangs by the window.',
                           'alarm': {'responders': [{'who': 'guards from the barracks', 'count': 2,
                                                     'stat_block': {'srd': 'Guard'}}], 'arrives_in_rounds': 2}}},
        'actors': {'brannoc': {'name': 'Brannoc Vell', 'location': 'gate', 'status': 'alive', 'visible': True,
                               'motive': 'Skim the toll.', 'knowledge': [], 'secrets': ['He pockets half the toll.'],
                               'communication_profile': {'rhythm': 'Clipped.', 'humor': 'Dry.'},
                               'armed': True, 'stat_block': {'srd': 'Bandit'}}},
        'story': {'gate': {'about': 'Pay or argue.', 'hooks': [
            {'id': 'toll', 'primary': True, 'by': 'brannoc', 'within_beats': 2,
             'text': 'Brannoc names the toll: five silver a head.',
             'delivered_when': {'said': {'by': ['brannoc'], 'any': ['silver', 'toll'], 'challenge': True}}}]}},
        'resources': {},
    }


class CacheAndLinks(Session):
    def test_re_entry_hits_the_cache_and_a_changed_source_misses_it(self):
        self.assertEqual(self.session.request(book(), '3', self.db)['stage'], 'author_room')
        accepted = self.session.submit(book(), '3', lair_room(), self.db)
        again = self.session.request(book(), '3', self.db)
        self.assertEqual((again['stage'], again['room_path']), ('cached', accepted['room_path']))
        changed = TEXT.replace('12 gp', '13 gp')
        self.assertEqual(self.session.request(book(changed), '3', self.db)['stage'], 'author_room')

    def test_an_author_link_is_requested_ahead_refused_until_authored_then_mounts(self):
        gate = gate_room()
        gate['areas']['east'] = {'name': 'East hall', 'source_area': '2', 'outside': True, 'beyond': True,
                                 'room_link': {'author': {'level': '01', 'area': '3'}}}
        gate['exits']['east'] = {'name': 'the east passage', 'areas': ['gate', 'east'], 'secret': False,
                                 'labels': {'gate': 'A passage east.', 'east': 'Back to the gatehouse.'}}
        gate['areas']['east']['room_link']['author']['area'] = '3'
        path = self.folder / 'gate.json'
        path.write_text(json.dumps(gate), encoding='utf-8')
        started = start_session(self.db, NIK, room=str(path), area='gate')
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))
        bridge.abandon(started['prepared']['turn_id'])
        packet = bridge.prepare('I look around the gatehouse.', one_pass=True)
        ahead = packet['author_ahead']
        self.assertEqual([(a['area'], a['status']) for a in ahead], [('3', 'not_requested')])
        self.assertIn('kit_author request', ahead[0]['request'])
        bridge.abandon(packet['turn_id'])
        revision, state = runtime.load()
        adjudicator = RoomAdjudicator(roll=lambda: 10, source=runtime.source())
        adjudicator.authored = runtime.authored_dir()
        with self.assertRaises(PendingRuling) as caught:
            adjudicator.resolve('I take the east passage.', revision, state)
        self.assertEqual(caught.exception.host_error['error'], 'room_not_authored')
        self.assertEqual(runtime.load()[0], revision)  # nothing committed
        self.assertEqual(self.session.submit(book(), '3', lair_room(), self.db)['stage'], 'accepted')
        result = adjudicator.resolve('I take the east passage.', revision, state)
        runtime.commit('move-east', revision, list(result.events))
        self.assertEqual(runtime.source()['id'], 'authored-level-01-area-3')
        self.assertEqual(runtime.load()[1]['area'], 'loft_mouth')

    def test_the_cli_requests_and_submits(self):
        env = {**os.environ, 'KIT_SOURCE_TEXT': str(FIX / 'keyed_text.txt')}
        env.pop('PYTHONPATH', None)
        base = [sys.executable, '-m', 'runtime.kit_author', '--db', str(self.db), '--level', '1', '--area', '3',
                '--map-index', str(MAP_INDEX)]
        run = lambda cmd, *extra: subprocess.run([*base[:3], cmd, *base[3:], *extra], cwd=ROOT, env=env,
                                                 capture_output=True, text=True)
        requested = json.loads(run('request').stdout)
        self.assertEqual(requested['stage'], 'author_room')
        self.assertIn('kit_author submit', requested['submit'])
        room = self.folder / 'room.json'
        room.write_text(json.dumps(lair_room()), encoding='utf-8')
        self.assertEqual(json.loads(run('submit', '--input-file', str(room)).stdout)['stage'], 'accepted')
        self.assertEqual(json.loads(run('request').stdout)['stage'], 'cached')
        missing = subprocess.run([*base[:3], 'request', *base[3:]], cwd=ROOT, capture_output=True, text=True,
                                 env={k: v for k, v in env.items() if k != 'KIT_SOURCE_TEXT'})
        if kit_source.source_text_path() is None:
            self.assertEqual(missing.returncode, 2)
            self.assertIn('never committed', missing.stderr)


class BookTextNeverInTheRepo(unittest.TestCase):
    """The licensed book text is read from a local path and never committed. Skipped on a
    machine with no configured source."""

    def test_no_long_line_of_the_configured_source_is_in_a_tracked_file(self):
        path = kit_source.source_text_path()
        if path is None or not path.is_file():
            self.skipTest('no book text configured (KIT_SOURCE_TEXT or config/kit_source.json)')
        lines = [l.strip() for l in path.read_text(encoding='utf-8').splitlines() if len(l.strip()) >= 120]
        self.assertTrue(lines)
        # Distinctive spans: 60 characters from the middle of every long line (plain text, no regex).
        probes = sorted({l[len(l) // 2 - 30:len(l) // 2 + 30] for l in lines})
        patterns = Path(tempfile.mkstemp(suffix='.txt')[1])
        self.addCleanup(patterns.unlink)
        patterns.write_text('\n'.join(probes) + '\n', encoding='utf-8')
        found = subprocess.run(['git', 'grep', '-l', '-F', '-I', '-f', str(patterns)], cwd=ROOT,
                               capture_output=True, text=True)
        self.assertEqual(found.stdout.strip(), '', 'tracked files carry book text: ' + found.stdout)

    def test_the_source_config_and_session_caches_are_gitignored(self):
        for path in ('config/kit_source.json', 'play.sqlite.authored/01-3-abc.json'):
            ignored = subprocess.run(['git', 'check-ignore', '-q', path], cwd=ROOT)
            self.assertEqual(ignored.returncode, 0, path)


if __name__ == '__main__':
    unittest.main()
