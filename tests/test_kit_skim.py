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

    def test_words_in_order_across_a_mixed_column_are_the_player_line(self):
        page = (
            'You stand on the lane The gate is shut as the rain starts.\n'
            'The North Road\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        self._ingest(page)
        done = kit_skim.accept(self.db, _reply(
            burst='You stand on the lane as the rain starts.',
            source_quote='You stand on the lane as the rain starts.',
            design_start_name='The North Road',
            alt_starts=[{'title': 'The North Road', 'page': 1}, {'title': 'The Square', 'page': 1}],
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        room = Path(done['room']).read_text(encoding='utf-8').casefold()
        self.assertIn('rain starts', room)
        self.assertNotIn('gate is shut', room)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        first = bridge.prepare('Yes.')
        self.assertIn('rain starts', (first.get('spoken') or '').casefold())
        self.assertNotIn('gate is shut', (first.get('spoken') or '').casefold())
        more = bridge.prepare('Go on')
        self.assertNotIn('gate is shut', (more.get('spoken') or '').casefold())

    def test_a_dm_title_does_not_commit_as_narrator(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Cellar\n'
            'The characters must find the secret door. This chapter explains the skill check.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[
                {'title': 'The North Road', 'page': 1},
                {'title': 'The Cellar', 'page': 1},
                {'title': 'The Square', 'page': 1},
            ],
        ))
        self.assertEqual(refused['stage'], 'skim_rejected')
        titles = [item.get('line') or item.get('title') for item in refused['start_picker']['places']]
        self.assertNotIn('The Cellar', titles)
        self.assertIn('The Square', titles)
        picked = kit_adventure.choose_start(self.db, 'The Cellar')
        self.assertEqual(picked['stage'], 'pick_start')
        self.assertFalse(picked['committed'])
        self.assertIsNone(picked.get('spoken'))
        self.assertFalse(picked.get('character_loaded'))
        blob = json.dumps(picked).casefold()
        self.assertNotIn('skill check', blob)
        self.assertNotIn('secret door', blob)
        index, _text = kit_adventure._load(self.db)
        key = next(k for k, loc in index['locations'].items() if loc.get('name') == 'The Cellar')
        compiled = kit_adventure.compile_location(self.db, key, neighbours=False)
        opened = start_session(str(self.db), str(NIK), room=compiled['room'])
        self.assertEqual(opened['stage'], 'pick_start')
        self.assertFalse(opened.get('committed'))
        self.assertIsNone(opened.get('spoken'))
        self.assertNotIn('skill check', json.dumps(opened).casefold())

    def test_go_on_reads_the_rest_of_the_boxed_opening(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            '> A crow calls once from the pines.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        first = bridge.prepare('Yes.')
        self.assertIn('wagon', (first.get('spoken') or '').casefold())
        self.assertNotIn('crow', (first.get('spoken') or '').casefold())
        more = bridge.prepare('Go on')
        self.assertIn('crow', (more.get('spoken') or '').casefold())
        self.assertNotIn("that's the span", (more.get('spoken') or '').casefold())
        self.assertNotIn('They speak to the room', more.get('spoken') or '')

    def test_landing_does_not_ask_for_a_whole_book_label(self):
        report = self._ingest(
            'The North Road\n> The wagon stops in the ruts under the trees.\n'
            'The Square\n> A baker waves from the stall.\n'
        )
        self.assertIsNone(report.get('label_request'))
        self.assertNotIn('label', ' '.join(report['landing']['same_exchange']))
        card = (ROOT / 'docs' / 'PLAY_CARD.md').read_text(encoding='utf-8').casefold()
        self.assertIn('do not label the book', card)
        self.assertIn('before `go on`', card)

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
        more = bridge.prepare('Go on')
        self.assertNotIn('bandit', (more.get('spoken') or '').casefold())
        self.assertNotIn('throne', (more.get('spoken') or '').casefold())
        bridge.adjudicator.mount(runtime.source())
        revision, state = runtime.load()
        greeted = bridge.adjudicator.resolve('Hello there.', revision, state)
        self.assertTrue(any(event.get('type') in ('combat_state', 'trigger_fired')
                            for event in greeted.events), greeted.events)

    def test_words_in_the_window_are_accepted_when_the_declared_page_is_off(self):
        self._ingest(
            'A title leaf.\n\f'
            'The North Road\n'
            '> The \ufb01rst street-lamp gutters as the rain starts.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The first street lamp gutters as the rain starts.',
            source_quote='The first street lamp gutters as the rain starts.',
            page_start=1, page_end=1,
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)

    def test_a_column_can_put_the_printed_order_ahead_of_the_extract(self):
        # The printed line reads down the left side. The extract put the right side first.
        self._ingest(
            'The North Road\n'
            'as the rain starts    The gate is shut\n'
            'You stand on the lane    against the wood.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='You stand on the lane as the rain starts.',
            source_quote='You stand on the lane as the rain starts.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        room = Path(done['room']).read_text(encoding='utf-8').casefold()
        self.assertIn('rain starts', room)
        self.assertNotIn('gate is shut', room)

    def test_go_on_skips_a_dm_note_and_the_captain_is_on_stage(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            '> Captain Mara steps out and raises a hand.\n'
            'Introduce the characters. Their patron wants the wagon found.\n'
            'Use this tracking procedure before the next scene.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        room = json.loads(Path(done['room']).read_text(encoding='utf-8'))
        names = [actor.get('name', '').casefold() for actor in (room.get('actors') or {}).values()]
        self.assertTrue(any('mara' in name for name in names), names)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        more = bridge.prepare('Go on')
        spoken = (more.get('spoken') or '').casefold()
        self.assertIn('mara', spoken)
        self.assertNotIn('introduce', spoken)
        self.assertNotIn('patron', spoken)
        self.assertNotIn('procedure', spoken)
        again = bridge.prepare('Go on')
        self.assertIn("that's the opening", (again.get('spoken') or '').casefold())

    def test_a_dm_scene_and_the_book_title_keep_the_picker(self):
        report = self._ingest(
            'The Sample Book\n'
            'The truth is the cellar holds a hidden cult. Do not reveal this. '
            'The characters must not know.\n'
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
        ))
        self.assertEqual(refused['stage'], 'skim_rejected')
        for title in (report['title'], 'Scene A', 'The Sample Book', 'A'):
            picked = kit_adventure.choose_start(self.db, title)
            self.assertEqual(picked.get('stage'), 'pick_start', title)
            self.assertFalse(picked.get('committed'))
            self.assertIsNone(picked.get('spoken'))
            blob = json.dumps(picked).casefold()
            self.assertNotIn('hidden cult', blob)
            self.assertNotIn('do not reveal', blob)

    def test_a_search_with_no_check_asks_instead_of_calling_a_roll(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted')
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        heard = bridge.prepare('I search the trees.')
        spoken = heard.get('spoken') or ''
        self.assertTrue('look' in spoken.casefold() or 'speak' in spoken.casefold())
        self.assertNotIn('adds nothing', spoken.casefold())
        self.assertNotIn('on the page', spoken.casefold())
        self.assertNotIn('You search', spoken)
        self.assertNotEqual(heard.get('stage'), 'pending_ruling')
        rolled = bridge.prepare('Perception 18')
        self.assertNotEqual(rolled.get('stage'), 'pending_ruling')
        rolled_text = (rolled.get('spoken') or '').casefold()
        self.assertNotIn('adds nothing', rolled_text)
        self.assertNotIn('on the page', rolled_text)
        self.assertNotIn('wagon, or', rolled_text)
        self.assertTrue('look' in rolled_text or 'speak' in rolled_text)

    def test_the_rest_of_the_book_waits_until_the_opening_is_spoken(self):
        self._ingest(
            'The North Road\n> The wagon stops in the ruts under the trees.\n'
            'The Square\n> A baker waves from the stall.\n'
        )
        kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        from runtime import kit_labels
        self.assertTrue(kit_skim.landing_holds(self.db))
        later = kit_adventure.deepen_index(self.db)
        self.assertEqual(later['stage'], 'index_later')
        self.assertIsNone(kit_labels.next_request(self.db))

    def test_an_accented_word_in_order_is_the_same_token(self):
        self._ingest(
            'The North Road\n'
            '> The caf\u00e9 on the lane gutters as the rain starts.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The caf\u00e9 on the lane gutters as the rain starts.',
            source_quote='The caf\u00e9 on the lane gutters as the rain starts.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)

    def test_go_on_does_not_speak_prep_or_a_rule(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            '> Captain Mara steps out and raises a hand.\n'
            '> Character introductions come before play. Their patron hired the wagon.\n'
            '> Set the marching order before the first mile.\n'
            '> If the fight starts, the scouts win and the danger returns later in the hills.\n'
            '> Call for a Wisdom (Perception) check to notice the ruts.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        more = bridge.prepare('Go on')
        spoken = (more.get('spoken') or '').casefold()
        self.assertIn('mara', spoken)
        for banned in ('introduction', 'patron', 'marching', 'if the fight', 'later in', 'perception'):
            self.assertNotIn(banned, spoken, banned)
        from runtime.scene_discernment import check_improv_read, discernment_candidates
        room = runtime.source()
        area = runtime.load()[1]['area']
        candidates = discernment_candidates({
            'scene': {'current_area': area},
            'dm_only': {'actors': room.get('actors') or {}},
        })
        key = next(k for k, actor in (room.get('actors') or {}).items()
                   if 'mara' in (actor.get('name') or '').casefold())
        self.assertIn(key, candidates['actor_bases'])
        check_improv_read({
            'story_anchor': 'scene', 'story_basis': 'scene_state',
            'actor_ref': key, 'actor_basis': 'motive',
            'kit_choice': 'Kit lets her answer the hail.',
        }, candidates)

    def test_an_unboxed_backstory_title_is_not_spoken(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Old Tale\n'
            'Years ago a family built a house on this hill. The youngest still walks.\n'
            'The Square\n'
            '> A baker waves from the stall.\n'
        )
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[
                {'title': 'The North Road', 'page': 1},
                {'title': 'The Old Tale', 'page': 1},
                {'title': 'The Square', 'page': 1},
            ],
        ))
        self.assertEqual(refused['stage'], 'skim_rejected')
        titles = [item.get('line') or item.get('title') for item in refused['start_picker']['places']]
        self.assertNotIn('The Old Tale', titles)
        picked = kit_adventure.choose_start(self.db, 'The Old Tale')
        self.assertEqual(picked.get('stage'), 'pick_start')
        self.assertFalse(picked.get('committed'))
        self.assertIsNone(picked.get('spoken'))
        self.assertNotIn('years ago', json.dumps(picked).casefold())

    def test_a_typed_title_is_a_start_not_a_ruling(self):
        self._ingest(
            'The North Road\n> The wagon stops in the ruts under the trees.\n'
            'The Square\n> A baker waves from the stall.\n'
        )
        kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
        ))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        hinted = kit_skim.named_start(runtime, 'The Square')
        self.assertEqual(hinted['stage'], 'use_start')
        self.assertFalse(hinted['committed'])
        self.assertIsNone(hinted['spoken'])
        self.assertIn('--start', hinted['next_command'])

    def test_you_may_on_a_street_is_still_the_opening(self):
        self._ingest(
            'The North Road\n'
            '> You may hear the rain on the lane as the street goes quiet tonight.\n'
            'The Square\n'
            '> A baker waves from the stall by the corner.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='You may hear the rain on the lane as the street goes quiet tonight.',
            source_quote='You may hear the rain on the lane as the street goes quiet tonight.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)

    def test_go_on_stops_at_prep_and_does_not_read_past_it(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            '> Captain Mara steps out and raises a hand.\n'
            '> The players concoct their own stories before the mile.\n'
            '> A crow calls once from the pines.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted')
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        more = bridge.prepare('Go on')
        spoken = (more.get('spoken') or '').casefold()
        self.assertIn('mara', spoken)
        self.assertNotIn('concoct', spoken)
        self.assertNotIn('players', spoken)
        again = bridge.prepare('Go on')
        later = (again.get('spoken') or '').casefold()
        self.assertIn("that's the opening", later)
        self.assertNotIn('crow', later)
        self.assertNotIn('concoct', later)

    def test_a_refusal_still_names_a_safe_title(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'The Square\n'
            '> A baker waves from the stall by the corner.\n'
        )
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[],
        ))
        self.assertEqual(refused['stage'], 'skim_rejected')
        places = refused['start_picker']['places']
        self.assertGreaterEqual(len(places), 1)
        self.assertTrue(any(item.get('pick') or item.get('title') for item in places))
        blob = json.dumps(places).casefold()
        self.assertNotIn('dragon', blob)

    def test_a_title_before_a_session_is_a_start_command(self):
        self._ingest(
            'The North Road\n> The wagon stops in the ruts under the trees.\n'
            'The Square\n> A baker waves from the stall by the corner.\n'
        )
        kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
        ))
        hinted = kit_skim.host_before_session(self.db, 'The Square')
        self.assertEqual(hinted['stage'], 'use_start')
        self.assertFalse(hinted['committed'])
        self.assertIsNone(hinted.get('spoken'))
        self.assertIn('--start', hinted['next_command'])
        self.assertNotIn('Initialize a session', json.dumps(hinted))

    def test_a_synopsis_title_is_not_a_start(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'Level Notes\n'
            'Level advancement grants experience points after the credits.\n'
            'The Square\n'
            '> A baker waves from the stall by the corner.\n'
        )
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[
                {'title': 'The North Road', 'page': 1},
                {'title': 'Level Notes', 'page': 1},
                {'title': 'The Square', 'page': 1},
            ],
        ))
        self.assertEqual(refused['stage'], 'skim_rejected')
        titles = [item.get('line') or item.get('title') or item.get('pick')
                  for item in refused['start_picker']['places']]
        self.assertNotIn('Level Notes', titles)
        self.assertTrue(any('North Road' in (item or '') or 'Square' in (item or '') for item in titles))
        picked = kit_adventure.choose_start(self.db, 'Level Notes')
        self.assertEqual(picked.get('stage'), 'pick_start')
        self.assertFalse(picked.get('committed'))
        self.assertIsNone(picked.get('spoken'))
        self.assertNotIn('experience', json.dumps(picked).casefold())

    def test_one_missing_content_word_still_accepts_the_line(self):
        self._ingest(
            'The North Road\n'
            '> You stand on the quiet lane as the heavy rain starts across the street tonight.\n'
            'The Square\n'
            '> A baker waves from the stall by the corner.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='You stand on the quiet lane as the heavy rain begins across the street tonight.',
            source_quote='You stand on the quiet lane as the heavy rain begins across the street tonight.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        self.assertIn('begins', Path(done['room']).read_text(encoding='utf-8').casefold())

    def test_go_on_does_not_replay_the_opening_or_read_prep(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            '> The wagon stops in the ruts under the trees.\n'
            '> The players concoct their own stories before the mile.\n'
            '> Decide the marching order before you leave the trees.\n'
            '> A crow calls once from the pines.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees. '
            'The players concoct their own stories before the mile.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        first = bridge.prepare('Yes.')
        self.assertIn('wagon', (first.get('spoken') or '').casefold())
        self.assertNotIn('concoct', (first.get('spoken') or '').casefold())
        more = bridge.prepare('Go on')
        spoken = (more.get('spoken') or '').casefold()
        self.assertNotIn('concoct', spoken)
        self.assertNotIn('players', spoken)
        self.assertNotIn('marching', spoken)
        self.assertIn("that's the opening", spoken)

    def test_a_later_room_is_not_a_listed_start(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            '1. The Vault\n'
            '> You stand in a later vault of cold stone.\n'
            'Level Notes\n'
            'Level advancement grants experience points after the credits.\n'
        )
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[
                {'title': 'The North Road', 'page': 1},
                {'title': 'The Vault', 'page': 1},
                {'title': 'Level Notes', 'page': 1},
            ],
        ))
        titles = ' '.join(
            (item.get('line') or item.get('title') or item.get('pick') or '')
            for item in refused['start_picker']['places'])
        self.assertNotIn('Vault', titles)
        self.assertNotIn('Level', titles)
        self.assertIn('North Road', titles)

    def test_children_on_a_street_can_be_spoken_to(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            'Two children watch from a doorway in the rain.\n'
            'Wolves are common in these woods and are not here.\n'
            'Two bandits wait in the brush.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        room = json.loads(Path(done['room']).read_text(encoding='utf-8'))
        names = [actor.get('name', '').casefold() for actor in (room.get('actors') or {}).values()]
        self.assertTrue(any('child' in name for name in names), names)
        blob = json.dumps(room).casefold()
        self.assertIn('bandit', blob)
        self.assertNotIn('wolf', blob)

    def test_go_on_releases_a_named_introduction(self):
        intro = (
            'Captain Mara keeps the watch on this road and she knows every wagon '
            'that passes the trees when the rain has made the lane soft under the '
            'wheels tonight and the watch is hers alone.'
        )
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            '> ' + intro + '\n'
            '> The players concoct their own stories before the mile.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        start_session(str(self.db), str(NIK))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        more = bridge.prepare('Go on')
        spoken = (more.get('spoken') or '').casefold()
        self.assertIn('mara', spoken)
        self.assertNotIn('concoct', spoken)
        self.assertNotIn('players', spoken)
        again = bridge.prepare('Go on')
        self.assertIn("that's the opening", (again.get('spoken') or '').casefold())
        self.assertNotIn('concoct', (again.get('spoken') or '').casefold())

    def test_a_plain_boxed_line_is_still_a_start(self):
        self._ingest(
            'The North Road\n'
            '> Thick fog covers the cobbles while the lamps stay dark tonight.\n'
            '1. The Vault\n'
            '> You stand in a later vault of cold stone.\n'
        )
        refused = kit_skim.accept(self.db, _reply(
            burst='A dragon lands on the bakery and the crowd cheers.',
            source_quote='A dragon lands on the bakery and the crowd cheers.',
            alt_starts=[],
        ))
        titles = ' '.join(
            (item.get('line') or item.get('title') or item.get('pick') or '')
            for item in refused['start_picker']['places'])
        self.assertIn('North Road', titles)
        self.assertNotIn('Vault', titles)
        self.assertGreaterEqual(len(refused['start_picker']['places']), 1)

    def test_a_greeter_in_the_opening_is_an_actor(self):
        self._ingest(
            'The North Road\n'
            '> The wagon stops in the ruts under the trees.\n'
            '> A woman greets you from the gate in the rain.\n'
            'Two bandits wait in the brush.\n'
        )
        done = kit_skim.accept(self.db, _reply(
            burst='The wagon stops in the ruts under the trees.',
            source_quote='The wagon stops in the ruts under the trees.',
        ))
        self.assertEqual(done['stage'], 'skim_accepted', done)
        room = json.loads(Path(done['room']).read_text(encoding='utf-8'))
        names = [actor.get('name', '').casefold() for actor in (room.get('actors') or {}).values()]
        self.assertTrue(any('greet' in name for name in names), names)
        self.assertIn('bandit', json.dumps(room).casefold())
