"""Source-to-room authoring (docs/architecture/SOURCE_TO_ROOM.md): Kit writes a room file from
the book's keyed text; the engine validates it, allows one repair, falls back cleanly, and
caches it per session. The keyed text here is SYNTHETIC (tests/fixtures/authoring), written
in the style of a published adventure, with four kinds of area: a lying warden with an alarm
(1), a trapped hall with sub-areas and a secret door (2, 2a, 2b), a roost that wakes when
its lantern is touched (3), and mirror duplicates over a hidden niche (4). No book text."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unittest import mock

from runtime import kit_author, kit_rooms, kit_source, srd_creatures
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, start_session
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'tests/fixtures/authoring'
TEXT = (FIX / 'keyed_text.txt').read_text(encoding='utf-8')
MAP_INDEX = FIX / 'MAP_INDEX.md'
LEDGER = FIX / 'geometry/LEVEL_01.json'
NIK = ROOT / 'tests/fixtures/characters/nik.json'


def book(text=None, ledger=None):
    if text is None:  # from the fixture file, so the session can re-check its rooms later
        return kit_author.Book(1, source=FIX / 'keyed_text.txt', map_index=MAP_INDEX,
                               ledger=ledger or FIX / 'no-ledger.json')
    return kit_author.Book(1, text=text, map_index=MAP_INDEX, ledger=ledger or FIX / 'no-ledger.json')


def lair_room(**changes):
    """A room for area 3 (a stirge loft) as Kit would write it from the packet."""
    stirges = [f'stirge_{n}' for n in 'abcd']
    room = {
        'id': 'authored-level-01-area-3', 'source_ref': 'Level 1 / 3. Cistern Loft (authored)',
        'starting_area': 'loft_stair',
        'areas': {
            'loft_stair': {'name': 'Below the loft', 'called': 'the foot of the loft', 'source_area': '3',
                           'outside': True,
                           'tease': {'text': 'Lantern light, barely, from the loft above; the planks creak.',
                                     'heard': []}},
            'loft': {'name': 'Cistern Loft', 'called': 'the loft', 'source_area': '3',
                     'arrival': 'A newcomer climbs into the loft.'},
            'hall_end': {'name': 'The needle hall', 'called': 'the hall', 'source_area': '2', 'outside': True,
                         'beyond': True, 'room_link': {'author': {'level': '01', 'area': '2'}}},
            'gallery_stair': {'name': 'The narrow stair down', 'called': 'the stair down', 'source_area': '4',
                              'outside': True, 'beyond': True,
                              'room_link': {'author': {'level': '01', 'area': '4'}}},
        },
        'exits': {
            'loft_climb': {'name': 'the way up', 'areas': ['loft_stair', 'loft'], 'secret': False,
                           'labels': {'loft_stair': 'Up into the loft.', 'loft': 'Back down.'}},
            'west_hall': {'name': 'the hall west', 'areas': ['loft', 'hall_end'], 'secret': False, 'uncertain': True,
                          'labels': {'loft': 'The hall runs west.', 'hall_end': 'The loft, back east.'}},
            'down': {'name': 'the narrow stair', 'areas': ['loft', 'gallery_stair'], 'secret': False,
                     'uncertain': True, 'labels': {'loft': 'A narrow stair leads down.', 'gallery_stair': 'Back up.'}},
        },
        'facts': {
            'lantern': {'area': 'loft', 'visible': True,
                        'text': 'A rusted lantern hangs from a hook over a dry cistern.',
                        'handling': {'nouns': ['lantern'], 'look': 'Rust, and a cold wick.',
                                     'move': 'The lantern swings on its hook.'}},
            'bones': {'area': 'loft', 'visible': True, 'text': 'Pigeon bones litter the planks.'},
            'roost': {'area': 'loft', 'visible': False, 'text': 'Four stirges roost out of sight among the rafters.'},
            'lockbox': {'area': 'loft', 'visible': False, 'text': 'A rusted lockbox on the ledge holds 12 gp.'},
        },
        'actors': {
            key: {'name': 'Stirge', 'location': 'loft', 'status': 'hidden', 'visible': False,
                  'motive': 'Feed.', 'knowledge': [], 'secrets': [], 'stat_block': {'srd': 'Stirge'}}
            for key in stirges},
        'triggers': [{'id': 'lantern_disturbed', 'on': {'disturb': 'lantern'}, 'starts_combat': True,
                      'actors': stirges, 'surprise': {'stealth': None},
                      'reveal': 'Leathery wings drop out of the dark rafters.'}],
        'story': {'loft': {'about': 'A roost that wakes when the lantern is touched.',
                           'endings': ['The PC clears the roost and finds what it guards.', 'The PC backs out.']}},
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
        self.assertEqual(list(areas), ['1', '2', '2a', '2b', '3', '4'])
        self.assertEqual(areas['2']['subareas'], ['2a', '2b'])
        self.assertEqual(areas['2a']['parent'], '2')
        self.assertEqual(areas['3']['title'], 'Cistern Loft')

    def test_a_numbered_sidebar_and_the_next_level_are_not_areas(self):
        areas = book().areas
        self.assertNotIn('warden count', json.dumps(areas))      # the sidebar "1." before the level
        self.assertNotIn('Flooded Stair', json.dumps(areas))     # the next level's "1."
        self.assertNotIn('Chapter Two', json.dumps(areas['4']))

    def test_cross_references_and_level_notes(self):
        self.assertEqual(kit_source.area_refs('east into area 2, then (areas 3 and 4) or area 2b'),
                         ['2', '3', '4', '2b'])
        self.assertEqual(kit_source.area_refs('the halls (areas 6, 8, and 9) and area 10'), ['6', '8', '9', '10'])
        inputs = kit_author.area_inputs(book(), '1')
        notes = inputs['level_notes']
        self.assertTrue(any('Gatehouse' in line for line in notes['mentions']))
        self.assertEqual([npc['name'] for npc in notes['npcs']], ['Ysolde Marr'])  # named in its keyed text
        self.assertEqual(len(notes['geometry_rules']), 2)
        lair = kit_author.area_inputs(book(), '3')['level_notes']
        self.assertTrue(any('Areas 2–3' in line for line in lair['mentions']))  # a range covers 3
        self.assertEqual(lair['npcs'], [])


class AuthoringPacket(unittest.TestCase):
    def test_it_carries_the_slice_geometry_schema_manifest_and_rules(self):
        packet = kit_author.packet(book(), '2a')
        self.assertIn('pressure plate', ' '.join(packet['area']['keyed_text']).lower())
        self.assertEqual(packet['area']['parent']['key'], '2')
        self.assertIn('Tiny holes pock both walls', ' '.join(packet['area']['parent']['intro']))
        self.assertEqual({n['area'] for n in packet['named_neighbours']}, {'1', '3', '2b'})
        self.assertFalse(packet['geometry']['bound'])
        self.assertIn('Invent no corridors', packet['geometry']['rule'])
        self.assertEqual(packet['schema']['limits']['dm_only_bytes'], kit_rooms.DM_ONLY_ROOM_MAX_BYTES)
        self.assertIn('stirge', packet['schema']['srd_creatures'])
        self.assertIn('traps', packet['schema'])
        manifest = packet['source_manifest']
        self.assertEqual(manifest['extractor'], 'keyed_prose')
        self.assertEqual(manifest['hazards'][0]['damage'], [{'dice': '2d6', 'type': 'piercing'}])
        rules = ' '.join(packet['hard_rules'])
        for must in ('source_manifest', '"status": "hidden"', 'alarm', 'stat_block', 'Data only', '"uncertain": true',
                     'needs_stats', 'source_claims', 'traps'):
            self.assertIn(must, rules)

    def test_it_never_carries_another_area_s_text(self):
        others = {'1': 'gray-haired warden named Ysolde', '2b': 'dead rat lies stiff', '3': 'Four stirges roost',
                  '2a': 'loose flagstone', '4': 'smoked glass'}
        for key in others:
            text = json.dumps(kit_author.packet(book(), key), ensure_ascii=False)
            for other, line in others.items():
                if other != key:
                    self.assertNotIn(line, text, f'{key} leaks {other}')

    def test_a_back_reference_says_whether_it_is_a_way_but_never_quotes_the_other_area(self):
        packet = kit_author.packet(book(), '4')
        exits = {e['area']: e for e in packet['source_manifest']['exits']}
        self.assertTrue(exits['2b']['way'] and exits['2b']['secret'])     # named as a secret door from 2b
        self.assertNotIn('quote', exits['2b'])
        self.assertFalse(exits['1']['way'])                               # "kept in area 1" is no way out

    def test_a_geometry_ledger_binds_the_exits(self):
        packet = kit_author.packet(book(ledger=LEDGER), '2a')
        self.assertTrue(packet['geometry']['bound'])
        self.assertEqual([e['to'] for e in packet['geometry']['exits']], ['2b', '1'])

    def test_the_packet_is_small(self):
        for key in ('1', '3', '4'):
            self.assertLess(len(json.dumps(kit_author.packet(book(), key)).encode()), 12000)


class ValidateAndRepair(Session):
    def test_a_valid_room_loads_mounts_and_keeps_its_ambushers_hidden(self):
        result = self.session.submit(book(), '3', lair_room(), self.db)
        self.assertEqual(result['stage'], 'accepted', result)
        self.assertEqual(result['attempt'], 1)
        self.assertTrue(Path(result['room_path']).is_absolute())
        started = start_session(self.folder / 'run.sqlite', NIK, room=result['room_path'])
        public = json.dumps(started['prepared'])
        self.assertNotIn('stirge', public.lower())  # at the approach, nothing of them

    def test_an_invalid_room_gets_a_repair_packet_with_every_error_and_passes_on_the_second_try(self):
        bad = lair_room()
        del bad['triggers']                                            # the roost, left to improvise
        bad['areas']['loft_stair']['tease']['text'] = 'Stirges rustle somewhere in the rafters.'  # a hidden actor
        bad['areas']['hall_end']['source_area'] = '9'                  # invented geometry
        bad['facts']['bones']['code'] = 'import os'                    # not data
        del bad['actors']['stirge_d']                                  # the source has four
        bad['facts'].pop('lockbox')                                    # the treasure
        bad['exits']['down'].pop('uncertain')                          # no ledger: not certain
        bad['facts']['lantern']['text'] += ' A DC 14 check spots the roost.'
        first = self.session.submit(book(), '3', bad, self.db)
        self.assertEqual(first['stage'], 'repair')
        self.assertEqual(first['attempts_left'], 1)
        errors = ' | '.join(first['errors'])
        for named in ('declares no triggers', 'names hidden actor', "source_area '9'", 'data only',
                      'hidden but no trigger wakes it', 'the source has 4 stirge', "missing item 'rusted lockbox'",
                      'mark it "uncertain": true', 'dc 14 is not a number the source states', 'shows a game number'):
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
        self.assertIn('Stirges. Four stirges roost out of sight among the rafters. If the lantern is disturbed, '
                      'the stirges swoop down and attack.', result['keyed_text'])
        self.assertIn("id must be 'authored-level-01-area-3'", result['errors'])
        # After a fallback, asking again gives the packet again: a good room may still replace it.
        again = self.session.request(book(), '3', self.db)
        self.assertEqual(again['stage'], 'author_room')
        self.assertEqual(again['after_fallback']['flag'], 'authoring_fallback')
        replaced = self.session.submit(book(), '3', lair_room(), self.db)
        self.assertEqual((replaced['stage'], replaced.get('replaces_fallback')), ('accepted', True))

    def test_alarms_stat_blocks_and_ledger_geometry_are_checked(self):
        room = gate_room()
        self.assertEqual(kit_author.validate(room, kit_author.area_inputs(book(), '1'))['errors'], [])
        room['facts']['bell'].pop('alarm')                      # a bell nobody answers
        room['actors']['ysolde'].pop('stat_block')              # armed, no numbers
        problems = kit_author.validate(room, kit_author.area_inputs(book(), '1'))['errors']
        self.assertTrue(any('looks like an alarm' in p for p in problems), problems)
        self.assertTrue(any('actor ysolde can fight but has no usable stat_block' in p for p in problems), problems)
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

    def test_the_liar_keeps_her_lie_public_and_her_truth_dm_side(self):
        inputs = kit_author.area_inputs(book(), '1')
        room = gate_room()
        room['actors']['ysolde']['secrets'] = []                  # the smuggling, dropped
        room['facts'].pop('truth')
        problems = kit_author.validate(room, inputs)['errors']
        self.assertTrue(any('not carried in dm-side' in p for p in problems), problems)
        room = gate_room()
        room['facts']['window'] = {'area': 'gate', 'visible': True, 'text': 'A smuggler watches from the window.'}
        problems = kit_author.validate(room, inputs)['errors']
        self.assertTrue(any('fact window text names' in p and 'smuggl' in p for p in problems), problems)

    def test_srd_references_overrides_and_needs_stats(self):
        self.assertEqual(srd_creatures.stat_block({'srd': 'Stirge'})['hp'], 2)
        self.assertEqual(srd_creatures.stat_block({'srd': 'giant rat'})['ac'], 12)
        self.assertEqual(srd_creatures.stat_block({'srd': 'Black Pudding', 'hp': 120})['hp'], 120)
        self.assertIsNone(srd_creatures.stat_block({'srd': 'No Such Beast'}))
        inputs = kit_author.area_inputs(book(), '3')
        room = lair_room()
        room['actors']['stirge_a']['stat_block'] = {'srd': 'Stirge', 'hp': 9}
        problems = kit_author.validate(room, inputs)['errors']
        self.assertIn('actor stirge_a stat_block hp 9 is not a number the source states', problems)
        room = lair_room()
        room['actors']['stirge_a'].pop('stat_block')
        room['actors']['stirge_a']['needs_stats'] = True
        problems = kit_author.validate(room, inputs)['errors']
        self.assertTrue(any('needs_stats but a trigger starts a fight with it' in p for p in problems), problems)


def gate_room():
    return {
        'id': 'authored-level-01-area-1', 'source_ref': 'Level 1 / 1. Gatehouse', 'starting_area': 'tunnel',
        'areas': {'tunnel': {'name': 'The tunnel', 'source_area': '1', 'outside': True,
                             'tease': {'text': 'Lamplight in a gatehouse window, and a chair creaking.',
                                       'points_to': 'wave', 'heard': [{'actor': 'ysolde', 'sound': 'a chair creaking'}]}},
                  'gate': {'name': 'Gatehouse', 'source_area': '1'},
                  'east': {'name': 'Needle Hall', 'called': 'the hall east', 'source_area': '2', 'outside': True,
                           'beyond': True, 'room_link': {'author': {'level': '01', 'area': '2'}}}},
        'exits': {'window': {'name': 'the gatehouse door', 'areas': ['tunnel', 'gate'], 'secret': False,
                             'labels': {'tunnel': 'The gatehouse.', 'gate': 'The tunnel.'}},
                  'east': {'name': 'the way east', 'areas': ['gate', 'east'], 'secret': False, 'uncertain': True,
                           'labels': {'gate': 'The tunnel runs east.', 'east': 'Back to the gatehouse.'}}},
        'facts': {'bell': {'area': 'gate', 'visible': True, 'text': 'A brass bell hangs from a chain beside the window.',
                           'alarm': {'responders': [{'who': 'guards from the barracks', 'count': 2,
                                                     'stat_block': {'srd': 'Guard'}}], 'arrives_in_rounds': 2}},
                  'truth': {'area': 'gate', 'visible': False,
                            'text': 'In fact, she is a smuggler waiting for a boat that is three days late.'},
                  'ledger': {'area': 'gate', 'visible': False,
                             'text': 'A successful DC 12 Wisdom (Insight) check reveals that she is lying about '
                                     'the guild.'}},
        'actors': {'ysolde': {'name': 'Ysolde Marr', 'location': 'gate', 'status': 'alive', 'visible': True,
                              'motive': 'Keep travelers moving and her boat secret.', 'knowledge': [],
                              'secrets': ['She claims that she keeps the tunnel for the salt guild; in fact she is a '
                                          'smuggler waiting for a boat that is three days late.'],
                              'armed': True, 'stat_block': {'srd': 'Bandit'}}},
        'story': {'gate': {'about': 'A warden who waves everyone on, and lies about why.', 'hooks': [
            {'id': 'wave', 'primary': True, 'by': 'ysolde', 'within_beats': 2,
             'text': 'Ysolde waves you east: the guild keeps this tunnel, she says.',
             'delivered_when': {'said': {'by': ['ysolde'], 'any': ['guild', 'east']}}}]}},
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

    def test_the_validator_version_is_in_the_hash(self):
        inputs = kit_author.area_inputs(book(), '3')
        before = kit_author.source_hash(inputs)
        with mock.patch.object(kit_author, 'VALIDATOR_VERSION', 'fidelity/999'):
            self.assertNotEqual(kit_author.source_hash(inputs), before)

    def test_a_stale_or_hand_written_cache_never_mounts_unchecked(self):
        accepted = self.session.submit(book(), '3', lair_room(), self.db)
        path = Path(accepted['room_path'])
        # Hand edits after acceptance (the roost made visible): start --room re-checks it.
        room = json.loads(path.read_text(encoding='utf-8'))
        room['actors']['stirge_a'].update(status='alive', visible=True)
        path.write_text(json.dumps(room), encoding='utf-8')
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            start_session(self.folder / 'run.sqlite', NIK, room=str(path))
        self.assertIn('the source keeps it out of sight', str(caught.exception))
        # A room and job.json written by hand, never submitted: still re-checked on mount.
        forged = lair_room()
        forged['facts'].pop('lockbox')
        forged['authoring'] = {'level': '01', 'area': '3', 'source_hash': accepted['source_hash'],
                               'validator': kit_author.VALIDATOR_VERSION}
        fake = self.session.dir / 'forged.json'
        fake.write_text(json.dumps(forged), encoding='utf-8')
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            start_session(self.folder / 'run2.sqlite', NIK, room=str(fake))
        self.assertIn("missing item 'rusted lockbox'", str(caught.exception))
        # A stamp from another source text or validator version: author it again.
        stale = {**lair_room(), 'authoring': {'level': '01', 'area': '3', 'source_hash': '0' * 16}}
        fake.write_text(json.dumps(stale), encoding='utf-8')
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            start_session(self.folder / 'run3.sqlite', NIK, room=str(fake))
        self.assertIn('author it again', str(caught.exception))

    def link_session(self, room, area):
        if room['id'].startswith('authored-'):
            path = self.session.submit(book(), room['id'].rsplit('-', 1)[-1], room, self.db)['room_path']
        else:
            path = self.folder / 'start.json'
            path.write_text(json.dumps(room), encoding='utf-8')
        started = start_session(self.db, NIK, room=str(path), area=area)
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))
        bridge.abandon(started['prepared']['turn_id'])
        return runtime, bridge

    def walk(self, runtime, action):
        revision, state = runtime.load()
        adjudicator = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=runtime.source())
        adjudicator.authored = runtime.authored_dir()
        result = adjudicator.resolve(action, revision, state)
        runtime.commit(f'move-{revision}', revision, list(result.events))
        return result

    def test_an_unauthored_link_is_entered_as_a_flagged_fallback_then_a_good_room_replaces_it(self):
        self.session.request(book(), '2', self.db)                     # binds this session to the fixture source
        runtime, bridge = self.link_session({**gate_room(), 'id': 'hand-written-gatehouse'}, 'gate')
        packet = bridge.prepare('I look around the gatehouse.', one_pass=True)
        ahead = {a['area']: a for a in packet['author_ahead']}
        self.assertEqual(ahead['2']['status'], 'requested')
        self.assertIn('kit_author request', ahead['2']['request'])
        bridge.abandon(packet['turn_id'])
        result = self.walk(runtime, 'I take the way east.')
        self.assertNotIn("can't", result.public_event.lower())
        source = runtime.source()
        self.assertEqual(runtime.load()[1]['area'], 'inside')          # the PC is in, Kit improvises
        flag = kit_author.fallback_flag(source)
        self.assertEqual((flag['area'], flag['reason']), ('2', 'not_authored_yet'))
        self.assertEqual(flag['session'], kit_author.session_id(self.db))
        self.assertEqual(kit_author.fallback_problems(source), [])
        self.assertFalse(any(f.get('visible') for f in source['facts'].values()))   # the keyed text stays dm_only
        packet = bridge.prepare('I look around.', one_pass=True)
        self.assertEqual(packet['authoring_fallback']['area'], '2')
        self.assertIn('2', {a['area'] for a in packet['author_ahead']})   # retried in the background
        bridge.abandon(packet['turn_id'])
        # Kit authors it properly; the next entry mounts the accepted room.
        from tests.authoring_rooms import faithful_room
        good = faithful_room(kit_author.area_inputs(book(), '2'))
        self.assertEqual(self.session.submit(book(), '2', good, self.db)['stage'], 'accepted')
        self.walk(runtime, 'I take the way toward the gatehouse.')    # area 1 is not authored either
        self.assertEqual(kit_author.fallback_flag(runtime.source())['area'], '1')
        self.walk(runtime, 'I take the way toward needle hall.')
        self.assertEqual(runtime.source()['id'], 'authored-level-01-area-2')

    def test_a_fallback_belongs_to_its_session(self):
        bad = lair_room(id='lair')
        self.session.submit(book(), '3', bad, self.db)
        self.assertEqual(self.session.submit(book(), '3', bad, self.db)['stage'], 'fallback')
        other = kit_author.Session(self.session.dir, session='another-session')
        self.assertEqual(other.request(book(), '3', self.db)['stage'], 'author_room')
        self.assertNotIn('after_fallback', other.request(book(), '3', self.db))

    def test_author_ahead_reaches_two_steps_from_an_approach(self):
        self.session.request(book(), '3', self.db)
        runtime, bridge = self.link_session(lair_room(), 'loft_stair')
        packet = bridge.prepare('I look up at the loft.', one_pass=True)
        ahead = {a['area']: a for a in packet['author_ahead']}
        self.assertEqual(set(ahead) >= {'2', '4'}, True)
        self.assertEqual({k for k, a in ahead.items() if a.get('depth') == 2} & {'1', '2a', '2b'} != set(), True)
        bridge.abandon(packet['turn_id'])

    def test_a_back_linked_approach_mounts(self):
        """A room whose approach stands for the area the PC came from (an author link back)."""
        inputs = kit_author.area_inputs(book(), '4')
        from tests.authoring_rooms import faithful_room
        room = faithful_room(inputs)
        room['areas']['approach'].update(source_area='3', room_link={'author': {'level': '01', 'area': '3'}})
        room['exits']['in']['uncertain'] = True
        result = self.session.submit(book(), '4', room, self.db)
        self.assertEqual(result['stage'], 'accepted', result)
        start_session(self.db, NIK, room=result['room_path'])
        runtime = Runtime(self.db)
        self.addCleanup(runtime.close)
        self.walk(runtime, 'I look around.')                           # a commit at the approach
        self.assertEqual(runtime.source()['id'], 'authored-level-01-area-4')   # not bounced back to 3
        self.assertEqual(runtime.load()[1]['area'], 'approach')

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
        submitted = json.loads(run('submit', '--input-file', str(room)).stdout)
        self.assertEqual(submitted['stage'], 'accepted', submitted)
        self.assertTrue(Path(submitted['room_path']).is_absolute())
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
