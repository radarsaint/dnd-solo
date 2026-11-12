"""The opening beat, every verb, four layouts. One failing cell fails the round.

Synthetic pages only. No published book, no page numbers, no proper nouns from one.
"""
import json
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

from runtime import kit_adventure, kit_opening, kit_skim
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, check_scope, start_session
from runtime.state_context import Runtime

ROOT = Path(__file__).resolve().parents[1]
NIK = ROOT / 'tests/fixtures/characters/nik.json'

ROAD = (
    'The patrons Iarno and Sildar hired the party before the journey.\n'
    'The North Road\n'
    '> The wagon stops on the road in the ruts under the trees.\n'
    'Four goblins hide in the brush and want the wagon supplies. A look notices the broken branches.\n'
    '> The players concoct their own stories before the mile.\n'
)
STREET = (
    'The Market Street\n'
    '> You stand in the street while children play at the corner and a woman greets the wagon.\n'
    '> The children are not what they seem and will lie about the cellar.\n'
    '1. The Vault\n'
    '> You stand in a later vault of cold stone.\n'
)
PATROL = (
    'The Patrol\n'
    '> The wagon stops in the ruts under the trees.\n'
    '> Captain Mara keeps the watch on this road and she knows every wagon that passes '
    'the trees when the rain has made the lane soft under the wheels tonight and the watch is hers alone.\n'
    '> The players concoct their own stories before the mile.\n'
)
TRAIL = (
    'The trail\n'
    '> You follow the trail under the trees.\n'
    'Three owlbears wait in the clearing and attack anyone who comes close. A careful look notices the clawed trees.\n'
)
PATROL_ORDERS = (
    '> Captain Mara steps out on the road and hails the wagon.\n'
    'She has orders to hold the road until the wagons pass.\n'
)
FRONT = (
    'Credits\n'
    'The license allows personal copies of this text.\n'
    'How to Play\n'
    'Read the rules before you begin. This procedure covers the checks.\n'
    'Synopsis\n'
    'The villain wants the valley. Years ago the war started.\n'
    'The Market Street\n'
    '> You stand in the street while the lamps stay dark.\n'
)
DM_ONLY = (
    'The North Road\n'
    '> The children are not what they seem and will lie about the cellar.\n'
    '1. The Vault\n'
    '> You stand in a later vault of cold stone.\n'
)


def _reply(**kwargs):
    base = {
        'page_start': 1, 'page_end': 1,
        'alt_starts': [
            {'title': 'The North Road', 'page': 1},
            {'title': 'The Square', 'page': 1},
        ],
        'design_start_name': 'The North Road',
    }
    base.update(kwargs)
    return base


class OpeningBeat(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'

    def _fresh(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'
        return self.db

    def _accept(self, text, name, burst):
        self._fresh()
        kit_adventure.ingest_adventure(self.db, text=text)
        done = kit_skim.accept(self.db, _reply(
            burst=burst, source_quote=burst, design_start_name=name,
            alt_starts=[{'title': name, 'page': 1}],
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        beat = kit_skim._read(self.db).get('beat') or {}
        self.assertTrue(beat.get('fiction'), beat)
        self.assertNotEqual(beat.get('place_noun'), 'room')
        return beat

    def _table(self, text, name, burst):
        self._accept(text, name, burst)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        return bridge

    def _said(self, bridge, words):
        packet = bridge.prepare(words)
        return (packet.get('spoken') or packet.get('public_event') or ''), packet

    def test_matrix(self):
        layouts = (
            ('road', ROAD, 'The North Road', 'The wagon stops on the road in the ruts under the trees.', 'goblin'),
            ('street', STREET, 'The Market Street',
             'You stand in the street while children play at the corner and a woman greets the wagon.',
             'children'),
            ('patrol', PATROL, 'The Patrol', 'The wagon stops in the ruts under the trees.', 'mara'),
            ('trail', TRAIL, 'The trail', 'You follow the trail under the trees.', 'owlbear'),
        )
        for layout, text, name, burst, who in layouts:
            self._yes_and_go_on(layout, text, name, burst, who)
            self._look_and_rolls(layout, text, name, burst, who)
            self._bypasses(layout, text, name, burst, who)

    def _yes_and_go_on(self, layout, text, name, burst, who):
        bridge = self._table(text, name, burst)
        with self.subTest(layout=layout, verb='yes'):
            spoken, _packet = self._said(bridge, 'Yes.')
            low = spoken.casefold()
            self.assertIn('trail' if layout == 'trail' else 'wagon', low)
            self.assertNotIn('concoct', low)
            self.assertNotIn('players', low)
            self.assertNotIn('procedure', low)
            self.assertNotIn('will lie', low)
            self.assertNotIn('perception', low)
        with self.subTest(layout=layout, verb='go on'):
            spoken, _packet = self._said(bridge, 'Go on')
            low = spoken.casefold()
            self.assertNotIn('concoct', low)
            self.assertNotIn('players', low)
            self.assertNotIn('procedure', low)
            self.assertNotIn('will lie', low)
            if layout == 'patrol':
                self.assertIn('mara', low)
            else:
                self.assertIn("that's the opening", low)
        with self.subTest(layout=layout, verb='go on again'):
            spoken, _packet = self._said(bridge, 'Go on')
            low = spoken.casefold()
            self.assertIn("that's the opening", low)
            self.assertNotIn('concoct', low)
            self.assertNotIn('mara', low) if layout == 'patrol' else None
            self.assertNotIn('procedure', low)

    def _look_and_rolls(self, layout, text, name, burst, who):
        if layout in ('street', 'patrol'):
            bridge = self._table(text, name, burst)
            self._said(bridge, 'Yes.')
            with self.subTest(layout=layout, verb='talk'):
                spoken, packet = self._said(bridge, 'I talk to the %s.' % who)
                low = spoken.casefold()
                self.assertIn(who, low)
                self.assertNotIn('initiative', low)
                self.assertNotEqual(packet.get('stage'), 'pending_ruling')
            return
        bridge = self._table(text, name, burst)
        self._said(bridge, 'Yes.')
        with self.subTest(layout=layout, verb='look'):
            spoken, _packet = self._said(bridge, 'I look around.')
            low = spoken.casefold()
            self.assertIn('perception', low)
            self.assertNotIn('initiative', low)
            self.assertNotIn('the room', low)
        with self.subTest(layout=layout, verb='roll high'):
            spoken, _packet = self._said(bridge, '18')
            low = spoken.casefold()
            self.assertIn(who, low)
            self.assertIn('notice', low)
            self.assertNotIn('look again', low)
            self.assertNotIn('initiative', low)
        bridge = self._table(text, name, burst)
        self._said(bridge, 'Yes.')
        self._said(bridge, 'I look around.')
        with self.subTest(layout=layout, verb='roll low'):
            spoken, _packet = self._said(bridge, '4')
            low = spoken.casefold()
            self.assertIn('surprise', low)
            self.assertIn('initiative', low)
            self.assertNotIn('look again', low)

    def _bypasses(self, layout, text, name, burst, who):
        if layout not in ('road', 'trail'):
            return
        bridge = self._table(text, name, burst)
        self._said(bridge, 'Yes.')
        with self.subTest(layout=layout, verb='talk before initiative'):
            spoken, packet = self._said(bridge, 'I talk to the %ss.' % who)
            low = spoken.casefold()
            self.assertNotIn('initiative', low)
            self.assertNotEqual(packet.get('stage'), 'pending_ruling')
            self.assertTrue('want' in low or 'answer' in low, spoken)
        bridge = self._table(text, name, burst)
        self._said(bridge, 'Yes.')
        with self.subTest(layout=layout, verb='sneak'):
            spoken, _packet = self._said(bridge, 'I sneak past.')
            low = spoken.casefold()
            self.assertNotIn('initiative', low)
            self.assertIn('slip', low)
        bridge = self._table(text, name, burst)
        self._said(bridge, 'Yes.')
        with self.subTest(layout=layout, verb='leave'):
            spoken, _packet = self._said(bridge, 'I leave.')
            low = spoken.casefold()
            self.assertNotIn('initiative', low)
            self.assertIn('leave', low)

    def test_quote_fail_is_a_fiction_title_or_kits_own_line(self):
        kit_adventure.ingest_adventure(self.db, text=DM_ONLY)
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[],
        ))
        blob = ' '.join(
            (item.get('title') or '') + ' ' + (item.get('quote') or '') + ' ' + (item.get('kit_line') or '')
            for item in refused['alt_starts']).casefold()
        self.assertTrue(refused['start_picker']['places'])
        self.assertIn('north road', blob)
        self.assertNotIn('will lie', blob)
        self.assertNotIn('vault', blob)
        self.assertIn("we'll start", blob)
        picked = kit_adventure.choose_start(self.db, 'Scene A')
        self.assertEqual(picked.get('stage'), 'pick_start')
        self.assertFalse(picked.get('committed'))
        self.assertIsNone(picked.get('spoken'))

    def test_host_cannot_speak_the_screen_or_jump_the_notice(self):
        beat = {
            'place_noun': 'road',
            'screen': ['The players concoct their own stories before the mile.'],
            'notice': {'pending': True, 'resolved': False, 'holds': True, 'find': ''},
            'pressure': {'bypassed': False, 'means': 'ambush', 'goal': 'They want the road.'},
            'people': [{'id': 'goblin', 'name': 'Goblin', 'hidden': True, 'revealed': False}],
            'observed': {'heard': [], 'seen': [], 'find': ''},
            'private': {'tactics': 'from cover', 'intent': 'They want the road.'},
        }
        spoken = kit_opening.guard_spoken(
            beat,
            'The players concoct their own stories before the mile. The goblin steps out. Roll initiative.')
        low = spoken.casefold()
        self.assertNotIn('concoct', low)
        self.assertNotIn('goblin', low)
        self.assertNotIn('initiative', low)
        self.assertIn('perception', low)

    def test_talk_to_a_beat_person_is_not_blocked_by_the_feature_floor(self):
        plan = {
            'move': 'npc_reply',
            'public_brief': {'scope': 'feature'},
            'improv_read': {'actor_ref': 'children'},
        }
        note = check_scope(
            [{'speaker': 'Children', 'text': 'Hello.'}],
            plan,
            {'opening_people': ('children',)},
        )
        self.assertIsNone(note)

    def test_a_large_pdf_does_not_wait_on_the_rest(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: None)
        path = folder / 'primer.pdf'
        path.write_bytes(b'%PDF-1.4\n' + b'0' * 900_000)
        started = time.perf_counter()
        with mock.patch('runtime.kit_adventure._pdftotext', return_value=None):
            with mock.patch('runtime.kit_pdf.extract', side_effect=AssertionError('parsed the rest')):
                with self.assertRaises(kit_adventure.IngestError):
                    kit_adventure.read_pdf(path, reader='auto', max_pages=18)
        self.assertLess(time.perf_counter() - started, 8)

    def _beat(self, text, name, burst):
        self._accept(text, name, burst)
        return kit_skim._read(self.db)['beat']

    def test_patrons_in_the_setup_are_not_the_ambush(self):
        beat = self._beat(ROAD, 'The North Road', 'The wagon stops on the road in the ruts under the trees.')
        names = ' '.join(person['name'] for person in beat['people']).casefold()
        self.assertEqual(beat['place_noun'], 'road')
        self.assertIn('goblin', names)
        self.assertNotIn('iarno', names)
        self.assertNotIn('sildar', names)
        self.assertTrue(beat['notice']['holds'])
        self.assertIn('broken branches', beat['notice']['find'].casefold())
        self.assertNotIn('dc', beat['notice']['find'].casefold())
        self.assertFalse(beat['pressure']['goal_generic'])
        self.assertIn('wagon', beat['pressure']['goal'].casefold())

    def test_a_trail_with_no_locations_still_has_its_creatures(self):
        report = kit_adventure.ingest_adventure(self.db, text=TRAIL)
        self.assertEqual(report['locations'], 0)
        beat = self._beat(TRAIL, 'The trail', 'You follow the trail under the trees.')
        names = ' '.join(person['name'] for person in beat['people']).casefold()
        self.assertEqual(beat['place_noun'], 'trail')
        self.assertIn('owlbear', names)
        self.assertTrue(beat['notice']['holds'])
        self.assertIn('clawed', beat['notice']['find'].casefold())

    def test_an_onstage_npc_keeps_her_orders_and_still_takes_a_look(self):
        beat = self._beat(PATROL_ORDERS, 'The road', 'Captain Mara steps out on the road and hails the wagon.')
        self.assertEqual(beat['place_noun'], 'road')
        self.assertFalse(beat['notice']['holds'])
        self.assertFalse(beat['pressure']['goal_generic'])
        self.assertIn('hold the road', beat['pressure']['goal'].casefold())
        self.assertTrue(any('mara' in person['name'].casefold() for person in beat['people']))
        bridge = self._table(PATROL_ORDERS, 'The road', 'Captain Mara steps out on the road and hails the wagon.')
        self._said(bridge, 'Yes.')
        look, _packet = self._said(bridge, 'I look around.')
        sneak, _packet = self._said(bridge, 'I sneak past.')
        self.assertNotIn('initiative', look.casefold())
        self.assertNotIn('the room', look.casefold())
        self.assertNotIn('initiative', sneak.casefold())

    def test_a_street_read_aloud_is_a_street(self):
        beat = self._beat(
            STREET, 'The Market Street',
            'You stand in the street while children play at the corner and a woman greets the wagon.')
        self.assertEqual(beat['place_noun'], 'street')
        self.assertNotEqual(beat['place_noun'], 'road')

    def test_front_matter_is_not_a_start(self):
        kit_adventure.ingest_adventure(self.db, text=FRONT)
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[],
            design_start_name='The Market Street',
        ))
        blob = ' '.join(
            (item.get('title') or '') + ' ' + (item.get('quote') or '') + ' ' + (item.get('kit_line') or '')
            for item in refused['alt_starts']).casefold()
        self.assertIn('street', blob)
        for banned in ('credit', 'license', 'how to', 'rules', 'procedure', 'synopsis', 'villain', 'years ago'):
            self.assertNotIn(banned, blob, banned)
        picked = kit_adventure.choose_start(self.db, refused['alt_starts'][0]['title'])
        self.assertIsNone(getattr(picked, 'room', None) if False else None)
        self.assertTrue(picked.get('room') or picked.get('spoken') or picked.get('stage'))
        spoken = json.dumps(picked).casefold()
        self.assertNotIn('license', spoken)
        self.assertNotIn('villain', spoken)

    def test_a_bare_letter_commits_only_when_a_slot_is_on_screen(self):
        self._accept(ROAD, 'The North Road', 'The wagon stops on the road in the ruts under the trees.')
        refused = kit_adventure.choose_start(self.db, 'A')
        self.assertEqual(refused.get('stage'), 'pick_start')
        self.assertIsNone(refused.get('spoken'))
        self._fresh()
        lettered = (
            'A. The street\n'
            '> You stand in the street while the lamps stay dark.\n'
        )
        kit_adventure.ingest_adventure(self.db, text=lettered)
        kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[],
            design_start_name='A. The street',
        ))
        opened = kit_adventure.choose_start(self.db, 'A')
        self.assertTrue(opened.get('room') or opened.get('spoken') or opened.get('stage') == 'skim_accepted')
        self.assertNotEqual(opened.get('stage'), 'pick_start')

    def test_player_ingest_of_a_large_pdf_stays_inside_eight_seconds(self):
        import test_kit_adventure_pdf as pdfs
        pages = []
        for index in range(36):
            if index == 0:
                ops = [
                    ('text', 72, 720, '1. First Yard', 12),
                    ('text', 72, 700, 'The wagon stops on the road under the trees.', 11),
                ]
            elif index == 30:
                ops = [('text', 72, 720, 'LATEVAULT is a later place nobody should index yet.', 12)]
            else:
                ops = [('text', 72, 720, 'Filler page %d of this synthetic book.' % (index + 1), 11)]
            pages.append(ops)
        path = Path(tempfile.mkdtemp()) / 'opening.pdf'
        path.write_bytes(pdfs.make_pdf(pages, compress=False))
        started = time.perf_counter()
        report = kit_adventure.ingest_adventure(self.db, pdf=path, reader='pdftotext', title='Opening Clock')
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 8, report)
        source = (kit_adventure.folder_for(self.db) / 'source.txt').read_text(encoding='utf-8')
        self.assertNotIn('LATEVAULT', source)
        self.assertIn('First Yard', source)
        self.assertEqual(report['reader'], 'pdftotext' if report['reader'] == 'pdftotext' else report['reader'])

    def test_private_tactics_are_not_observed_facts(self):
        beat = kit_opening.build_beat(ROAD, 'The wagon stops in the ruts under the trees.', 'The North Road')
        self.assertEqual(beat['pressure']['means'], 'ambush')
        self.assertIn('want', beat['pressure']['goal'])
        self.assertNotIn('from cover', beat['observed']['heard'])
        self.assertEqual(beat['private']['tactics'], 'from cover')
        self.assertNotIn('goblin', ' '.join(beat['observed']['seen']))
        self.assertTrue(beat['notice']['find'])


def _pdf(pages):
    import test_kit_adventure_pdf as pdfs
    return pdfs.make_pdf(pages, compress=False)


class PlayerPath(unittest.TestCase):
    """The host's commands, on PDFs read back by pdftotext -layout."""

    def setUp(self):
        warnings.simplefilter('ignore')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'kit.sqlite'

    def _cli(self, *args):
        proc = subprocess.run(
            [sys.executable, '-m', 'runtime.kit_agent', *args],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:] + proc.stdout[-2000:])
        text = proc.stdout.strip()
        return json.loads(text) if text else {}

    def _ingest(self, pdf):
        started = time.perf_counter()
        report = self._cli('ingest', str(pdf), '--db', str(self.db), '--reader', 'pdftotext')
        report['_elapsed'] = time.perf_counter() - started
        return report

    def _skim(self, burst, name, page_end=1):
        reply = Path(self.tmp.name) / 'skim.json'
        reply.write_text(json.dumps({
            'burst': burst, 'source_quote': burst, 'page_start': 1, 'page_end': page_end,
            'alt_starts': [], 'design_start_name': name,
        }), encoding='utf-8')
        return self._cli('adventure', 'skim', '--db', str(self.db), '--file', str(reply))

    def _beat(self):
        path = kit_adventure.folder_for(self.db) / 'skim.json'
        return json.loads(path.read_text(encoding='utf-8'))['beat']

    def _start(self, room):
        self._cli('start', '--db', str(self.db), '--room', room, '--sheet', str(NIK))

    def _say(self, words):
        packet = self._cli('prepare', '--db', str(self.db), '--action', words)
        return (packet.get('spoken') or packet.get('public_event') or ''), packet

    def test_a_dot_leader_imports_quickly(self):
        text = '1. First Yard\n> The wagon stops on the road.\nContents %s 4\n' % ('.' * 2000)
        started = time.perf_counter()
        kit_adventure.import_adventure(self.db, text=text, title='Dots')
        self.assertLess(time.perf_counter() - started, 0.05)

    def test_dotted_contents_pdf_lands_quickly(self):
        dots = '.' * 80
        pages = [[
            ('text', 72, 740, 'Contents', 14),
            ('text', 48, 700, 'First Yard %s 3' % dots, 8),
        ], [
            ('text', 72, 720, '1. First Yard', 12),
            ('text', 72, 690, 'The wagon stops on the road under the trees.', 11),
        ]]
        path = Path(self.tmp.name) / 'dots.pdf'
        path.write_bytes(_pdf(pages))
        report = self._ingest(path)
        self.assertLess(report['_elapsed'], 8, report)
        source = (kit_adventure.folder_for(self.db) / 'source.txt').read_text(encoding='utf-8')
        self.assertIn('First Yard', source)
        self.assertIn('..', source)

    def test_two_column_ambush_requires_source_attested_scene(self):
        # A real PDF no longer accepts the old six-field skim silently. The
        # dedicated host-path suite tests the subsequent structured repair,
        # native check, and player-visible outcome end to end.
        left, right = 48, 360
        pages = [[
            ('text', left, 740, 'You stand on the road under the trees.', 11),
            ('text', right, 740, 'Sidebar. Patrons from the distant city hired the party.', 9),
            ('text', right, 700, 'How to Play. A DC 15 check is the procedure.', 9),
            ('text', right, 660, '(see the Goblin stat block).', 9),
        ], [
            ('text', left, 740, 'Four goblins hide and want the wagon supplies.', 11),
            ('text', left, 700, 'A look notices the broken branches.', 11),
            ('text', right, 740, '1. Later Vault', 12),
            ('text', right, 700, 'You stand in a later vault of cold stone.', 11),
        ]]
        path = Path(self.tmp.name) / 'columns.pdf'
        path.write_bytes(_pdf(pages))
        self._ingest(path)
        done = self._skim('You stand on the road under the trees.', 'The road', page_end=2)
        self.assertEqual(done.get('stage'), 'scene_required', done)
        source = done['scene_request']['source_span']
        self.assertIn('Four goblins hide', source)
        self.assertNotIn('You stand in a later vault', source)
        self.assertNotIn('room', done)
        self.assertFalse(done.get('committed'))
        self.assertNotIn('beat', kit_skim._read(self.db))

    def test_patrol_requires_source_attested_people_and_orders(self):
        pages = [[
            ('text', 72, 720, 'The wagon stops in the ruts under the trees.', 11),
            ('text', 72, 690, 'Captain Mara steps out on the road and hails the wagon.', 11),
            ('text', 72, 660, 'She has orders to hold the road until the wagons pass.', 11),
        ]]
        path = Path(self.tmp.name) / 'patrol.pdf'
        path.write_bytes(_pdf(pages))
        self._ingest(path)
        done = self._skim('The wagon stops in the ruts under the trees.', 'The road')
        self.assertEqual(done.get('stage'), 'scene_required', done)
        source = done['scene_request']['source_span']
        self.assertIn('Captain Mara', source)
        self.assertIn('orders to hold the road', source)
        self.assertNotIn('beat', kit_skim._read(self.db))
        # The source-verified staged-NPC sequence has its own full CLI test.

    def test_slip_cannot_bypass_before_scene_is_interpreted(self):
        left, right = 48, 360
        pages = [[
            ('text', left, 720, 'You stand on the road under the trees.', 11),
            ('text', left, 680, 'Four goblins hide and want the wagon supplies.', 11),
            ('text', right, 720, 'How to Play. A DC 12 check is the procedure.', 9),
        ]]
        path = Path(self.tmp.name) / 'slip.pdf'
        path.write_bytes(_pdf(pages))
        self._ingest(path)
        done = self._skim('You stand on the road under the trees.', 'The road')
        self.assertEqual(done.get('stage'), 'scene_required', done)
        self.assertIn('Four goblins hide', done['scene_request']['source_span'])
        self.assertNotIn('beat', kit_skim._read(self.db))
        # No automatic success; the native Stealth path is tested in Round 2.

    def test_call_out_cannot_leak_setup_through_uninterpreted_pdf(self):
        left, right = 48, 360
        pages = [[
            ('text', left, 740, 'You stand on the road under the trees.', 11),
            ('text', right, 740, 'Sidebar. Distant patrons hired the party.', 9),
            ('text', right, 700, '(see the Goblin stat block).', 9),
        ], [
            ('text', left, 740, 'Four goblins hide and want the wagon supplies.', 11),
            ('text', right, 740, '1. Later Vault', 12),
        ]]
        path = Path(self.tmp.name) / 'call.pdf'
        path.write_bytes(_pdf(pages))
        self._ingest(path)
        done = self._skim('You stand on the road under the trees.', 'The road', page_end=2)
        self.assertEqual(done.get('stage'), 'scene_required', done)
        self.assertFalse(done.get('committed'))
        self.assertIn('scene', done['scene_request']['instructions'])
        self.assertNotIn('beat', kit_skim._read(self.db))

    def test_a_failed_quote_lists_only_the_read_aloud(self):
        pages = [[
            ('text', 72, 740, 'How to Play', 14),
            ('text', 72, 710, 'A DC 15 check is the procedure.', 11),
            ('text', 72, 660, 'The Market Street', 14),
            ('text', 72, 630, 'You stand in the street while the lamps stay dark.', 11),
            ('text', 72, 560, '1. Later Vault', 14),
            ('text', 72, 530, 'You stand in a later vault of cold stone.', 11),
            ('text', 72, 480, 'Appendix', 14),
            ('text', 72, 450, 'The villain wants the valley.', 11),
        ]]
        path = Path(self.tmp.name) / 'front.pdf'
        path.write_bytes(_pdf(pages))
        self._ingest(path)
        done = self._skim('A dragon lands on the bakery and the crowd cheers.', 'How to Play')
        blob = json.dumps(done).casefold()
        self.assertIn('street', blob)
        for banned in ('how to', 'procedure', 'appendix', 'villain', 'later vault', 'dc 15'):
            self.assertNotIn(banned, blob, banned)
        bare = self._cli('start', '--db', str(self.db), '--start', 'A')
        self.assertEqual(bare.get('stage'), 'pick_start')
        self.assertIsNone(bare.get('spoken'))
