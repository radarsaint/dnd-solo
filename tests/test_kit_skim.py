"""Host skim, Python validate. Synthetic pages only. No published names.

The host returns a quote. Python accepts it only as a contiguous substring of the
page window, and never walks forward to a later room when the check fails.
"""
import hashlib
import json
import unittest
import warnings
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_adventure, kit_skim  # noqa: E402
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import Runtime  # noqa: E402

NIK = ROOT / 'tests/fixtures/characters/nik.json'


def _book(early, late_at):
    """`early` pages, then filler, then one late page. Page 1 is early[0]."""
    pages = list(early)
    while len(pages) < late_at - 1:
        pages.append('Notes for the reader. Nothing here is a place to begin.\n')
    return '\f'.join(pages)


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


class SkimValidate(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        import tempfile
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'

    def _ingest(self, text):
        report = kit_adventure.ingest_adventure(self.db, text=text)
        self.assertIn('skim_request', report)
        self.assertNotIn('label_request', report)
        self.assertLess(report['ingest_ms'], 8000)
        self.assertIn("who's walking in", report['landing']['table_line'].casefold())
        return report

    def test_an_invented_opening_is_rejected(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery roof and the crowd cheers.',
            source_quote='A dragon lands on the bakery roof and the crowd cheers.',
        ))
        self.assertEqual(done['stage'], 'skim_rejected', done)
        self.assertTrue(any('window' in item or 'substring' in item or 'contiguous' in item
                            for item in done['problems']))
        self.assertIsNone(done.get('opened_room'))
        self.assertFalse(done.get('advanced'))
        titles = [item['line'] for item in done['start_picker']['places']]
        self.assertGreaterEqual(len(titles), 2)
        self.assertLessEqual(len(titles), 4)
        self.assertIn('The North Road', titles)
        self.assertNotIn('throne', ' '.join(titles).casefold())

    def test_a_secret_in_the_burst_is_rejected_even_when_verbatim(self):
        self._ingest(
            'The North Road\n'
            '> The secret passage opens behind the casks.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The secret passage opens behind the casks.',
            source_quote='The secret passage opens behind the casks.',
        ))
        self.assertEqual(done['stage'], 'skim_rejected', done)
        self.assertTrue(any('secret' in item or 'tip' in item for item in done['problems']))
        self.assertIsNone(done.get('opened_room'))

    def test_a_fused_tip_is_rejected_rather_than_split_into_an_opening(self):
        self._ingest(
            'The North Road\n'
            "When you're ready, read the boxed text: The wagon stops in the ruts under the trees.\n"
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        quote = "When you're ready, read the boxed text: The wagon stops in the ruts under the trees."
        done = kit_skim.accept(self.db, _reply(burst=quote, source_quote=quote))
        self.assertEqual(done['stage'], 'skim_rejected', done)
        self.assertFalse(done.get('advanced'))

    def test_a_failed_check_offers_early_titles_and_not_a_later_room(self):
        pages = [
            'The North Road\n> The wagon stops in the ruts under the trees.\n',
            'The Square\n> A baker waves from the stall.\n',
        ]
        text = _book(pages, 30)
        text += '\f99. The Vault\n> The throne room burns.\n'
        self._ingest(text)
        done = kit_skim.accept(self.db, _reply(
            burst='The throne room burns.',
            source_quote='The throne room burns.',
            page_start=30, page_end=30,
            alt_starts=[
                {'title': 'The North Road', 'page': 1},
                {'title': 'The Square', 'page': 2},
                {'title': 'The Vault', 'page': 30},
                {'title': 'The Vault', 'page': 1},
            ],
        ))
        self.assertEqual(done['stage'], 'skim_rejected', done)
        titles = [item['line'] for item in done['start_picker']['places']]
        self.assertIn('The North Road', titles)
        self.assertIn('The Square', titles)
        self.assertNotIn('The Vault', titles)
        self.assertLessEqual(len(titles), 4)
        self.assertIn('muddy', done['table_line'].casefold())
        self.assertIn('describe how you arrive', done['table_line'].casefold())
        opened = start_session(str(self.db), str(NIK))
        self.assertNotEqual(opened.get('stage'), 'greeting')
        self.assertIsNone(opened.get('opened_room'))
        self.assertTrue(opened.get('sheet_kept'))
        self.assertNotIn('vault', (opened.get('table_line') or '').casefold())
        self.assertNotIn('throne', (opened.get('table_line') or '').casefold())

    def test_a_short_window_expands_once_and_does_not_open_the_climax(self):
        early = ['Notes for the reader. Nothing here is a place to begin.\n'] * 10
        early.append('Still notes, and still not a start.\n')
        early.append(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        text = _book(early, 30)
        text += '\f99. The Vault\n> The throne room burns.\n'
        self._ingest(text)
        too_far = kit_skim.accept(self.db, _reply(
            burst='The throne room burns.',
            source_quote='The throne room burns.',
            page_start=31, page_end=31,
        ))
        self.assertEqual(too_far['stage'], 'skim_rejected', too_far)
        self.assertTrue(any('once' in item or 'window' in item for item in too_far['problems']))
        widened = kit_skim.accept(self.db, {'expand': True})
        self.assertEqual(widened['stage'], 'skim_expanded', widened)
        self.assertEqual(widened['skim_request']['expands_left'], 0)
        self.assertLessEqual(widened['skim_request']['window_pages'], kit_skim.FIRST_WINDOW + kit_skim.EXPAND_ONCE)
        good = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
            page_start=12, page_end=12,
        ))
        self.assertEqual(good['stage'], 'skim_accepted', good)
        self.assertNotIn('throne', (good.get('room') or '').casefold())
        again = kit_skim.accept(self.db, {'expand': True})
        self.assertEqual(again['stage'], 'skim_rejected', again)
        self.assertTrue(any('once' in item for item in again['problems']))
        room = Path(good['room']).read_text(encoding='utf-8').casefold()
        self.assertIn('wagon', room)
        self.assertNotIn('throne', room)

    def test_yes_speaks_the_burst_and_go_on_stays_in_the_span(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees. A crow calls once from the pines.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
            '\n99. The Vault\n> The throne room burns.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees. A crow calls once from the pines.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        self.assertLessEqual(done['burst_words'], 100)
        self.assertIn('road', done['handoff'].casefold())
        opened = start_session(str(self.db), str(NIK))
        self.assertTrue(opened.get('character_loaded'))
        self.assertNotEqual(opened.get('stage'), 'greeting')
        self.assertFalse(opened.get('committed'))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        heard = bridge.prepare('Yes.')
        spoken = heard.get('spoken') or ''
        self.assertIn('wagon stops', spoken.casefold())
        self.assertNotIn('crow', spoken.casefold())
        self.assertNotIn('throne', spoken.casefold())
        self.assertIn('road', spoken.casefold())
        narrator = spoken.split('\nKit:')[0]
        self.assertLessEqual(len(narrator.split()), 120)
        more = bridge.prepare('Go on.')
        self.assertTrue(more.get('committed'))
        self.assertIn('crow', (more.get('spoken') or '').casefold())
        self.assertNotIn('throne', (more.get('spoken') or '').casefold())
        self.assertNotIn('You declare', more.get('spoken') or '')
        self.assertNotIn('They speak to the room', more.get('spoken') or '')
        self.assertNotIn('go on', (more.get('public_event') or '').casefold())

    def test_no_numbered_places_still_open_a_scene_with_the_sheet(self):
        self._ingest(
            'Ferry Night\n'
            '> The ferry bumps the pilings and the rope goes tight.\n\n'
            'Hill Path\n'
            '> The hill path is empty and the wind is cold.\n'
        )
        index, _text = kit_adventure._load(self.db)
        numbered = [loc for loc in index['locations'].values() if loc.get('type') != 'scene']
        done = kit_skim.accept(self.db, {
            'burst': 'The ferry bumps the pilings and the rope goes tight.',
            'source_quote': 'The ferry bumps the pilings and the rope goes tight.',
            'page_start': 1, 'page_end': 1,
            'alt_starts': [{'title': 'Ferry Night', 'page': 1}, {'title': 'Hill Path', 'page': 1}],
            'design_start_name': 'Ferry Night',
        })
        self.assertEqual(done['stage'], 'skim_accepted', done)
        self.assertTrue(str(done['scene_key']).startswith('scene:'), done['scene_key'])
        opened = start_session(str(self.db), str(NIK))
        self.assertEqual(opened.get('stage'), 'started')
        self.assertTrue(opened.get('character_loaded'))
        self.assertNotEqual(opened.get('stage'), 'greeting')
        self.assertFalse(numbered)
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        heard = KitChatBridge(runtime, RoomAdjudicator()).prepare('Yes.')
        self.assertIn('ferry bumps', (heard.get('spoken') or '').casefold())

    def test_a_high_check_speaks_a_crumb_and_not_a_bare_clean(self):
        self._ingest(
            'The Track\n'
            '> The road is empty and the ruts are old.\n'
            'Check: a close look finds fresh ruts in the mud.\n'
            'The Square\n'
            '> A baker waves from the stall.\n\n'
            '1. The Post\n'
            'A post stands by the road.\n'
        )
        done = kit_skim.accept(self.db, {
            'burst': 'The road is empty and the ruts are old.',
            'source_quote': 'The road is empty and the ruts are old.',
            'page_start': 1, 'page_end': 1,
            'alt_starts': [{'title': 'The Track', 'page': 1}, {'title': 'The Square', 'page': 1}],
            'design_start_name': 'The Track',
        })
        self.assertEqual(done['stage'], 'skim_accepted', done)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        source = runtime.source()
        area = runtime.load()[1]['area']
        from runtime.kit_agent import check_reveal_text
        cited = check_reveal_text(source, area)
        self.assertIn('fresh ruts', cited.casefold())
        line = kit_skim.success_line(source, area, 'perception', cited)
        self.assertIn('fresh ruts', line.casefold())
        self.assertNotIn('comes up clean', line.casefold())
        revision = runtime.load()[0]
        runtime.commit('called', revision, [
            {'type': 'pending_check', 'check': {
                'skill': 'perception', 'ability': 'wis', 'target': 'none',
                'called_turn': 'c1', 'dc': 12,
            }, 'evidence': 'Kit called for perception.'},
            {'type': 'prepared_roll', 'roll': {
                'skill': 'perception', 'dc': 12,
                'bands': {
                    'fail': "The perception check doesn't turn anything up.",
                    'pass': 'The perception check comes up.',
                    'high': line,
                },
            }, 'evidence': 'The outcome is prepared.'},
        ])
        heard = bridge.prepare('The ruts. 20.')
        self.assertTrue(heard.get('committed'), heard)
        self.assertIn('fresh ruts', (heard.get('spoken') or '').casefold())
        self.assertNotIn('comes up clean', (heard.get('spoken') or '').casefold())

    def test_looking_around_does_not_invent_a_fight(self):
        self._ingest(
            'The Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Square\n'
            '> A baker waves from the stall.\n\n'
            '99. The Vault\n'
            'Four bandits guard the throne with weapons drawn.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
            design_start_name='The Road',
            alt_starts=[{'title': 'The Road', 'page': 1}, {'title': 'The Square', 'page': 1}],
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        room = Path(done['room']).read_text(encoding='utf-8').casefold()
        self.assertNotIn('throne', room)
        self.assertNotIn('weapons drawn', room)
        self.assertNotIn('triggers', room)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        bridge.adjudicator.mount(runtime.source())
        revision, state = runtime.load()
        looked = bridge.adjudicator.resolve('I look around.', revision, state)
        self.assertNotEqual(looked.kind, 'combat_round')
        self.assertFalse(any(event.get('type') == 'combat_state' for event in looked.events))
        self.assertNotIn('You try that', looked.public_event)
        self.assertNotIn('You declare', looked.public_event)


class SkimRound6(unittest.TestCase):
    setUp = SkimValidate.setUp
    _ingest = SkimValidate._ingest
    def test_a_curly_apostrophe_still_matches_the_printed_line(self):
        self._ingest(
            'The North Road\n'
            '> The wagon won\u2019t stop in the ruts under the trees.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst="The wagon won't stop in the ruts under the trees.",
            source_quote="The wagon won't stop in the ruts under the trees.",
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        self.assertIn('won', Path(done['room']).read_text(encoding='utf-8').casefold())
        opened = start_session(str(self.db), str(NIK))
        self.assertNotEqual(opened.get('stage'), 'greeting')
        self.assertTrue(opened.get('character_loaded'))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        heard = KitChatBridge(runtime, RoomAdjudicator()).prepare('Yes.')
        self.assertIn("won't", (heard.get('spoken') or '').casefold().replace('\u2019', "'"))
        self.assertIn('road', (heard.get('spoken') or '').casefold())

    def test_a_mixed_column_read_aloud_is_accepted_without_the_other_column(self):
        self._ingest(
            'You stand on the lane as the rain starts. | The secret door pays the party.\n'
            'The North Road | The Square\n'
        )
        # The printed line is the left column. The extract put both columns on one line.
        page = (
            'You stand on the lane | The secret door pays the party.\n'
            'as the rain starts. | Reward the party with a coin.\n'
            'The North Road | The Square\n'
        )
        # Rebuild the source as the mixed extract the reader actually stored.
        folder = kit_adventure.folder_for(self.db)
        (folder / 'source.txt').write_text(page, encoding='utf-8')
        index = json.loads((folder / 'index.json').read_text(encoding='utf-8'))
        import hashlib
        index['sha256'] = hashlib.sha256(page.encode('utf-8')).hexdigest()
        index['chars'] = len(page)
        (folder / 'index.json').write_text(json.dumps(index), encoding='utf-8')
        done = kit_skim.accept(self.db, _reply(
            burst='You stand on the lane as the rain starts.',
            source_quote='You stand on the lane as the rain starts.',
            design_start_name='The North Road',
            alt_starts=[{'title': 'The North Road', 'page': 1}, {'title': 'The Square', 'page': 1}],
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        room = Path(done['room']).read_text(encoding='utf-8').casefold()
        self.assertIn('rain starts', room)
        self.assertNotIn('secret door', room)
        self.assertNotIn('reward the party', room)

    def test_a_picker_title_opens_player_fiction_and_not_a_secret(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Cellar\n'
            'The secret door is behind the casks. Reward the party with a coin.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery roof and the crowd cheers.',
            source_quote='A dragon lands on the bakery roof and the crowd cheers.',
            alt_starts=[
                {'title': 'The North Road', 'page': 1},
                {'title': 'The Cellar', 'page': 1},
                {'title': 'The Square', 'page': 1},
            ],
        ))
        self.assertEqual(refused['stage'], 'skim_rejected')
        titles = [item['line'] for item in refused['start_picker']['places']]
        self.assertIn('The Square', titles)
        self.assertNotIn('The Cellar', titles)
        picked = kit_adventure.choose_start(self.db, 'The Square')
        opened = start_session(str(self.db), str(NIK), room=picked['room'])
        spoken = (opened.get('spoken') or '').casefold()
        self.assertIn('baker', spoken)
        self.assertNotIn('secret', spoken)
        self.assertNotIn('reward', spoken)
        self.assertNotEqual(opened.get('stage'), 'greeting')
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        # The scene is up. A later line does not die with an empty session.
        KitChatBridge(runtime, RoomAdjudicator()).prepare('I look around.')

    def test_go_on_after_the_burst_is_not_them_speaking(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees. A crow calls once from the pines.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees. A crow calls once from the pines.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        more = bridge.prepare('Go on')
        self.assertNotIn('They speak to the room', more.get('spoken') or '')
        self.assertIn('crow', (more.get('spoken') or '').casefold())

    def test_a_high_check_is_not_the_opening_or_a_tip(self):
        self._ingest(
            'The Track\n'
            '> The road is empty and the ruts are old.\n'
            "When you're ready, read the boxed text and mark the wheels.\n"
            'Check: a close look finds fresh ruts in the mud.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, {
            'burst': 'The road is empty and the ruts are old.',
            'source_quote': 'The road is empty and the ruts are old.',
            'page_start': 1, 'page_end': 1,
            'alt_starts': [{'title': 'The Track', 'page': 1}, {'title': 'The Square', 'page': 1}],
            'design_start_name': 'The Track',
        })
        self.assertEqual(done['stage'], 'skim_accepted', done)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        from runtime.kit_agent import check_reveal_text
        source = runtime.source()
        area = runtime.load()[1]['area']
        line = kit_skim.success_line(source, area, 'perception', check_reveal_text(source, area))
        self.assertIn('fresh ruts', line.casefold())
        self.assertNotIn('when you', line.casefold())
        self.assertNotIn('comes up clean', line.casefold())
        self.assertNotIn('the road is empty', line.casefold())

    def test_a_span_trigger_can_fire_and_a_later_monster_cannot(self):
        self._ingest(
            'The Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'Two bandits wait in the brush.\n'
            'The Square\n'
            '> A baker waves from the stall.\n\n'
            '99. The Vault\n'
            'Four bandits guard the throne with weapons drawn.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
            design_start_name='The Road',
            alt_starts=[{'title': 'The Road', 'page': 1}, {'title': 'The Square', 'page': 1}],
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        room = Path(done['room']).read_text(encoding='utf-8').casefold()
        self.assertNotIn('throne', room)
        self.assertNotIn('weapons drawn', room)
        self.assertIn('bandit', room)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        bridge.adjudicator.mount(runtime.source())
        revision, state = runtime.load()
        greeted = bridge.adjudicator.resolve('Hello there.', revision, state)
        self.assertTrue(any(event.get('type') in ('combat_state', 'trigger_fired')
                            for event in greeted.events), greeted.events)
