"""The opening beat, every verb, four layouts. One failing cell fails the round.

Synthetic pages only. No published book, no page numbers, no proper nouns from one.
"""
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
    'The North Road\n'
    '> The wagon stops in the ruts under the trees.\n'
    'Four goblins wait in ambush in the brush. A Wisdom (Perception) check notices them in the brush.\n'
    '> The players concoct their own stories before the mile.\n'
)
STREET = (
    'The Market Street\n'
    '> You stand in the lane while children play at the corner and a woman greets the wagon.\n'
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
    'The Forest Trail\n'
    '> The wagon stops in the ruts under the trees.\n'
    'Two bandits wait in the clearing. A Wisdom (Perception) check notices the bandits in the brush.\n'
    '> Use this tracking procedure before the next scene.\n'
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
            ('road', ROAD, 'The North Road', 'The wagon stops in the ruts under the trees.', 'goblin'),
            ('street', STREET, 'The Market Street',
             'You stand in the lane while children play at the corner and a woman greets the wagon.',
             'children'),
            ('patrol', PATROL, 'The Patrol', 'The wagon stops in the ruts under the trees.', 'mara'),
            ('trail', TRAIL, 'The Forest Trail', 'The wagon stops in the ruts under the trees.', 'bandit'),
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
            self.assertIn('wagon', low)
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

    def test_private_tactics_are_not_observed_facts(self):
        beat = kit_opening.build_beat(ROAD, 'The wagon stops in the ruts under the trees.', 'The North Road')
        self.assertEqual(beat['pressure']['means'], 'ambush')
        self.assertIn('want', beat['pressure']['goal'])
        self.assertNotIn('from cover', beat['observed']['heard'])
        self.assertEqual(beat['private']['tactics'], 'from cover')
        self.assertNotIn('goblin', ' '.join(beat['observed']['seen']))
        self.assertTrue(beat['notice']['find'])
