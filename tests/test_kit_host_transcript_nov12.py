"""Host-transcript tests for playable layout fallback and prepare-time asks.

All adventure material below is original synthetic prose. No published text.
Each play test drives the real prepare/complete cycle (or a prepare that
already speaks the engine line).
"""
import json
import tempfile
import unittest
from pathlib import Path
from shutil import which
from unittest import mock

from runtime import kit_adventure, kit_skim, kit_scene_contract
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import Runtime
from test_kit_adventure_pdf import make_pdf
from test_kit_agent import RecordingModel
from test_kit_scene_contract_gpt import SHEET


def _row(left, right, width=72):
    return left + ' ' * max(3, width - len(left)) + right + '\n'


class MultiLaneAndBurstOnly(unittest.TestCase):

    def _triple(self, left, mid, right, left_w=22, mid_w=44):
        return left.ljust(left_w) + '   ' + mid.ljust(mid_w) + '   ' + right + '\n'

    def test_three_lane_layout_keeps_the_opening_encounter(self):
        burst = 'A red lantern sways above the ferry dock.'
        # Three printed lanes on one row: setup | opening | later room.
        source = (
            self._triple('Setup notes', '1. Ferry Dock', '2. Upper Mill')
            + self._triple('A clerk lists fares.', '> ' + burst, '> An iron wheel turns.')
            + self._triple('Keep the fares handy.', 'Two porters wait by the ropes.', 'The mill is locked.')
        )
        span = kit_skim._same_column_encounter(source, burst)
        self.assertIn('Two porters wait by the ropes.', span)
        self.assertIn(burst, ' '.join(span.split()))
        self.assertNotIn('iron wheel', span)
        self.assertNotIn('clerk lists fares', span)

    def test_burst_only_scene_names_a_word_from_the_read_aloud(self):
        spoken = 'A wagon rolls toward the bridge at dawn.'
        scene = kit_skim._burst_only_scene(spoken, 'Marsh Road')
        self.assertEqual(scene['people'], [])
        self.assertEqual(scene['discoveries'], [])
        self.assertEqual(scene['pressures'], [])
        self.assertIn(scene['place']['name'].casefold(), spoken.casefold())
        self.assertEqual(scene['place']['quote'], spoken)
        errors = kit_scene_contract.validate(scene, spoken, spoken)
        self.assertFalse(errors, errors)


@unittest.skipUnless(which('pdftotext'), 'requires pdftotext')
class RetainedPdfAndHostCycle(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)
        self.db = self.dir / 'game.sqlite'
        self.pdf = self.dir / 'source.pdf'
        self.burst = 'The cart halts near a bent tree.'
        self.presence = 'Two scouts wait beside the path.'
        self.find = 'A careful look notices broken twigs under the tree.'
        self.later = 'A bell rings on a high tower.'
        self.pdf.write_bytes(make_pdf([[
            ('text', 70, 735, '1. Marsh Road', 11),
            ('text', 70, 700, '> ' + self.burst, 10),
            ('text', 70, 670, self.presence, 10),
            ('text', 70, 640, self.find, 10),
            ('text', 330, 700, '2. Far Chapel', 11),
            ('text', 330, 670, self.later, 10),
        ]]))

    def _ingest(self):
        return kit_adventure.ingest_adventure(self.db, pdf=str(self.pdf))

    def _form(self, scene=None):
        answer = {
            'burst': self.burst, 'source_quote': self.burst,
            'page_start': 1, 'page_end': 1,
            'alt_starts': [], 'design_start_name': 'Marsh Road',
        }
        if scene is not None:
            answer['scene'] = scene
        return answer

    def test_retained_pdf_recovers_when_ingested_lanes_fail(self):
        self._ingest()
        with mock.patch.object(kit_skim, '_same_column_encounter', return_value=''):
            result = kit_skim.accept(self.db, self._form())
        self.assertEqual(result['stage'], 'scene_required', result)
        span = result['scene_request']['source_span']
        self.assertIn(self.burst, span)
        self.assertIn(self.presence, span)
        self.assertNotIn(self.later, span)

    def test_failed_recovery_is_a_playable_burst_only_start(self):
        self._ingest()
        with mock.patch.object(kit_skim, 'recover_opening_section', return_value=('', [])):
            result = kit_skim.accept(self.db, self._form())
        self.assertEqual(result['stage'], 'skim_accepted', result)
        self.assertEqual(result.get('layout_recovery'), 'burst_only')
        self.assertTrue(result.get('source_verified'))
        self.assertFalse(result.get('people_attested'))
        self.assertTrue(result.get('turn_id') or result.get('scene_key'))
        self.assertIn('read-aloud only', result.get('table_line') or '')
        self.assertIn('start_picker', result)
        start_session(str(self.db), str(SHEET))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        spoken = KitChatBridge(runtime, RoomAdjudicator()).prepare('Yes.')
        self.assertIn(self.burst, spoken.get('spoken') or '')
        self.assertNotEqual(spoken.get('stage'), 'scene_required')

    def _accepted_ambush(self, with_spring=False):
        # Play-cycle tests use a one-column manuscript so the attested
        # encounter is unambiguous. Two-column recovery is covered above.
        manuscript = (
            '1. Marsh Road\n> ' + self.burst + '\n' +
            self.presence + '\n' + self.find + '\n'
            '2. Far Chapel\n> ' + self.later + '\n'
        )
        kit_adventure.ingest_adventure(self.db, text=manuscript)
        pressure = []
        if with_spring:
            condition = (
                'If the scouts go unnoticed, they spring from hiding and attack.')
        scene = {
            'place': {'name': 'tree', 'quote': self.burst},
            'people': [{
                'id': 'scout_1', 'name': 'scouts',
                'quote': self.presence,
                'visibility': 'hidden', 'kind': 'creature',
                'goal': None, 'knowledge': [],
            }],
            'discoveries': [{
                'quote': self.find, 'status': 'established',
            }],
            'pressures': pressure,
        }
        accepted = kit_skim.accept(self.db, self._form(scene))
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        start_session(str(self.db), str(SHEET))
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        opening = bridge.prepare('Yes.')
        self.assertIn(self.burst, opening.get('spoken') or '')
        return runtime, bridge

    def test_look_asks_perception_at_prepare_time(self):
        runtime, bridge = self._accepted_ambush()
        looked = bridge.prepare('I look around.', one_pass=True)
        self.assertEqual(looked.get('stage'), 'called_roll', looked)
        self.assertTrue(looked.get('committed'), looked)
        self.assertTrue(looked.get('turn_id'), looked)
        self.assertIn('Roll Perception', looked.get('spoken') or '')
        self.assertNotIn('DC', looked.get('spoken') or '')
        rolled = bridge.prepare('18', one_pass=True)
        self.assertEqual(rolled.get('stage'), 'called_roll', rolled)
        self.assertNotIn('DC', rolled.get('spoken') or '')

    def test_failed_perception_does_not_spring_without_a_governing_sentence(self):
        runtime, bridge = self._accepted_ambush(with_spring=False)
        looked = bridge.prepare('I look around.', one_pass=True)
        self.assertEqual(looked.get('stage'), 'called_roll', looked)
        failed = bridge.prepare('4', one_pass=True)
        self.assertEqual(failed.get('stage'), 'called_roll', failed)
        spoken = (failed.get('spoken') or '').casefold()
        self.assertNotIn('initiative', spoken)
        self.assertFalse(runtime.load()[1].get('combat'))

    def test_sneak_asks_stealth_at_prepare_time(self):
        runtime, bridge = self._accepted_ambush()
        sneaked = bridge.prepare('I sneak past the scouts.', one_pass=True)
        self.assertEqual(sneaked.get('stage'), 'called_roll', sneaked)
        self.assertTrue(sneaked.get('turn_id'), sneaked)
        self.assertIn('Roll Stealth', sneaked.get('spoken') or '')
        rolled = bridge.prepare('18', one_pass=True)
        self.assertEqual(rolled.get('stage'), 'called_roll', rolled)
        self.assertNotIn('DC', rolled.get('spoken') or '')

    def test_burning_a_cart_is_a_spoken_ruling_with_a_turn_id(self):
        runtime, bridge = self._accepted_ambush()
        burned = bridge.prepare('I burn the cart.', one_pass=True)
        self.assertEqual(burned.get('stage'), 'engine_ruling', burned)
        self.assertTrue(burned.get('committed'), burned)
        self.assertTrue(burned.get('turn_id'), burned)
        self.assertIn('set it alight', burned.get('spoken') or '')
        self.assertNotEqual(burned.get('stage'), 'pending_ruling')
        self.assertNotIn('DC', burned.get('spoken') or '')


class PresentNpcReplyCycle(unittest.TestCase):
    def test_present_npc_answers_when_the_host_uses_a_short_name(self):
        intro = 'The caravan halts on the road beneath a leaning pine.'
        next_line = 'Captain Mara steps onto the road and hails the caravan.'
        orders = 'Captain Mara has orders to hold the road until the wagons pass.'
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'talk.sqlite'
        source = ('1. The North Road\n> ' + intro + '\n'
                  'Decide marching order before reaching the pass.\n'
                  '> ' + next_line + '\n' + orders + '\n'
                  '2. The Tower\n> A bell rings on a high tower.\n')
        kit_adventure.ingest_adventure(db, text=source)
        scene = {
            'place': {'name': 'road', 'quote': intro},
            'people': [{
                'id': 'captain_mara', 'name': 'Captain Mara',
                'quote': next_line, 'visibility': 'staged', 'kind': 'person',
                'goal': {'quote': orders, 'status': 'established'},
                'knowledge': [],
            }],
            'discoveries': [], 'pressures': [],
        }
        accepted = kit_skim.accept(db, {
            'burst': intro, 'source_quote': intro,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The North Road', 'scene': scene,
        })
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        start_session(str(db), str(SHEET))
        runtime = Runtime(str(db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        first = bridge.prepare('Yes.')
        self.assertIn(intro, first.get('spoken') or '')
        second = bridge.prepare('Go on')
        self.assertIn(next_line, second.get('spoken') or '')
        self.assertEqual(runtime.load()[1]['actors']['captain_mara']['status'], 'alive')
        third = bridge.prepare('I talk to Captain Mara.', one_pass=True)
        self.assertEqual(third.get('stage'), 'one_pass', third)
        plan = RecordingModel().plan(third['input']['private'])
        plan.update(move='npc_reply', focus_actor='captain_mara',
                    table_presence='brief')
        plan['improv_read'].update(actor_ref='captain_mara',
                                   actor_basis='immediate_goal')
        plan['public_brief'].update(reply_to='I talk to Captain Mara.',
                                    scope='exchange')
        # A short, natural speaker label the host might use instead of the full name.
        answered = bridge.complete(third['turn_id'], {
            'decision': plan,
            'performance': {'segments': [
                {'speaker': 'Mara', 'text': 'I have orders to hold the road until the wagons pass.'},
            ]},
        })
        self.assertIn('Captain Mara:', answered.get('spoken') or '')
        self.assertIn('orders to hold the road', answered.get('spoken') or '')
        self.assertNotIn('Invalid spoken segment', json.dumps(answered))
        self.assertNotEqual(answered.get('stage'), 'rejected')
        self.assertEqual(runtime.load()[1]['actors']['captain_mara']['status'], 'alive')




class TwoColumnSectionHandoff(unittest.TestCase):
    """The host receives both columns of the opening section, not a guessed slice.

    Hidden ambushers in the facing column after the read-aloud stay in the
    section. A later keyed room does not.
    """

    def _layout(self):
        burst = 'The cart halts near a bent tree.'
        presence = 'Two scouts hide in the brush beside the path.'
        notice = 'A careful look notices broken twigs under the tree.'
        condition = 'If the scouts go unnoticed, they spring from hiding and attack.'
        later = 'A bell rings on a high tower.'
        raw = (
            kit_skim_row('1. Marsh Road', 'Trail notes')
            + kit_skim_row('> ' + burst, presence)
            + kit_skim_row('The road bends west.', notice)
            + kit_skim_row('Dust hangs in the afternoon light.', condition)
            + kit_skim_row('2. Far Chapel', 'The chapel door is locked.')
            + kit_skim_row('> ' + later, 'A rope hangs in the belfry.')
        )
        return raw, burst, presence, notice, condition, later

    def test_section_includes_facing_column_hidden_presence(self):
        raw, burst, presence, notice, condition, later = self._layout()
        span, columns = kit_skim.opening_section_from_text(raw, burst)
        blob = ' '.join((span or '').split())
        lanes = ' '.join((item.get('text') or '') for item in columns)
        combined = blob + ' ' + ' '.join(lanes.split())
        self.assertIn(burst, combined)
        self.assertIn('Two scouts hide', combined)
        self.assertIn('broken twigs', combined)
        self.assertIn('spring from hiding', combined)
        self.assertNotIn('chapel door', combined)
        self.assertNotIn('bell rings', combined)
        self.assertNotIn('belfry', combined)
        self.assertGreaterEqual(len(columns), 2, columns)

    def test_host_form_from_facing_column_asks_look_and_sneak(self):
        raw, burst, presence, notice, condition, later = self._layout()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        db = root / 'game.sqlite'
        # A real PDF keeps the host-attested scene contract (not legacy text).
        # Hidden ambushers sit in the facing column under the same heading.
        pdf = root / 'source.pdf'
        pdf.write_bytes(make_pdf([[
            ('text', 70, 740, '1. Marsh Road', 11),
            ('text', 70, 705, '> ' + burst, 10),
            ('text', 70, 670, 'The road bends west.', 10),
            ('text', 70, 635, 'Dust hangs in the afternoon light.', 10),
            ('text', 340, 740, 'Trail notes', 11),
            ('text', 340, 705, presence, 10),
            ('text', 340, 670, notice, 10),
            ('text', 340, 635, condition, 10),
        ], [
            ('text', 70, 740, '2. Far Chapel', 11),
            ('text', 70, 705, '> ' + later, 10),
            ('text', 340, 740, 'The chapel door is locked.', 10),
        ]]))
        kit_adventure.ingest_adventure(db, pdf=str(pdf))
        first = kit_skim.accept(db, {
            'burst': burst, 'source_quote': burst,
            'page_start': 1, 'page_end': 2, 'alt_starts': [],
            'design_start_name': 'Marsh Road',
        })
        self.assertEqual(first['stage'], 'scene_required', first)
        span = first['scene_request']['source_span']
        lanes = first['scene_request'].get('source_columns') or []
        combined = span + ' ' + ' '.join(item.get('text') or '' for item in lanes)
        self.assertIn('Two scouts hide', combined)
        self.assertNotIn('chapel door', combined)
        scene = {
            'place': {'name': 'tree', 'quote': burst},
            'people': [{
                'id': 'scout_1', 'name': 'scouts',
                'quote': presence, 'visibility': 'hidden', 'kind': 'creature',
                'goal': None, 'knowledge': [],
            }],
            'discoveries': [{'quote': notice, 'status': 'established'}],
            'pressures': [{
                'kind': 'ambush', 'quote': condition, 'status': 'conditional',
                'actors': ['scout_1'], 'activation': 'failed_notice',
            }],
        }
        accepted = kit_skim.accept(db, {'scene': scene})
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        start_session(str(db), str(SHEET))
        runtime = Runtime(str(db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        opening = bridge.prepare('Yes.')
        self.assertIn(burst, opening.get('spoken') or '')
        looked = bridge.prepare('I look around carefully.', one_pass=True)
        self.assertEqual(looked.get('stage'), 'called_roll', looked)
        self.assertIn('Roll Perception', looked.get('spoken') or '')
        self.assertNotIn('DC', looked.get('spoken') or '')
        sneak_runtime = Runtime(str(db))
        self.addCleanup(sneak_runtime.close)
        sneaked = KitChatBridge(sneak_runtime, RoomAdjudicator()).prepare(
            'I sneak around the edges and slip past.', one_pass=True)
        self.assertEqual(sneaked.get('stage'), 'called_roll', sneaked)
        self.assertIn('Roll Stealth', sneaked.get('spoken') or '')
        self.assertNotIn('DC', sneaked.get('spoken') or '')


class RulesHeadingFictionPicker(unittest.TestCase):
    """Boxed or second-person fiction may be offered even under a rules heading."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / 'picker.sqlite'
        self.source = (
            'How to Play\n'
            '> You stand in the street while the lamps stay dark.\n'
            'Make sure you look around the trail\n'
            'This procedure explains a 6-sided die and advantage or disadvantage.\n'
        )
        kit_adventure.ingest_adventure(self.db, text=self.source)

    def _refuse(self):
        return kit_skim.accept(self.db, {
            'burst': 'A dragon lands on the bakery and the crowd cheers.',
            'source_quote': 'A dragon lands on the bakery and the crowd cheers.',
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'How to Play',
        })

    def test_fiction_under_a_rules_heading_is_offered_without_that_title(self):
        refused = self._refuse()
        titles = [item.get('title') or '' for item in refused.get('alt_starts') or []]
        blob = ' '.join(titles).casefold()
        self.assertTrue(titles, refused)
        self.assertTrue(any('street' in title.casefold() or 'lamp' in title.casefold()
                            for title in titles), titles)
        for banned in ('how to', 'make sure', 'look around the trail', 'sided die',
                       'advantage', 'procedure'):
            self.assertNotIn(banned, blob, titles)

    def test_naming_a_coaching_heading_commits_nothing(self):
        self._refuse()
        picked = kit_adventure.choose_start(self.db, 'Make sure you look around the trail')
        self.assertEqual(picked.get('stage'), 'pick_start', picked)
        self.assertFalse(picked.get('committed'))
        self.assertFalse(picked.get('room'))
        self.assertIsNone(picked.get('spoken'))


if __name__ == '__main__':
    unittest.main()


class FailedQuotePicker(unittest.TestCase):
    """A failed opening quote offers only playable read-alouds, never a how-to heading."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / 'picker.sqlite'
        self.source = (
            'Some guidelines to help you arbitrate\n'
            'This procedure explains advantage and the checks.\n'
            'How to Play\n'
            'Read the rules before you begin.\n'
            'The Market Street\n'
            '> You stand in the street while the lamps stay dark.\n'
        )
        kit_adventure.ingest_adventure(self.db, text=self.source)

    def test_failed_quote_picker_omits_rules_and_how_to_headings(self):
        refused = kit_skim.accept(self.db, {
            'burst': 'A dragon lands on the bakery and the crowd cheers.',
            'source_quote': 'A dragon lands on the bakery and the crowd cheers.',
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Market Street',
        })
        titles = [item.get('title') or '' for item in refused.get('alt_starts') or []]
        blob = ' '.join(titles).casefold()
        self.assertTrue(any('street' in title.casefold() for title in titles), titles)
        for banned in ('guideline', 'arbitrate', 'how to', 'rules', 'procedure'):
            self.assertNotIn(banned, blob, titles)

    def test_naming_a_rules_heading_does_not_start_a_session(self):
        kit_skim.accept(self.db, {
            'burst': 'A dragon lands on the bakery and the crowd cheers.',
            'source_quote': 'A dragon lands on the bakery and the crowd cheers.',
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Market Street',
        })
        picked = kit_adventure.choose_start(self.db, 'Some guidelines to help you arbitrate')
        self.assertEqual(picked.get('stage'), 'pick_start', picked)
        self.assertFalse(picked.get('committed'))
        self.assertFalse(picked.get('room'))
        self.assertIsNone(picked.get('spoken'))


class TwoColumnEncounterWiden(unittest.TestCase):
    """A short ingested lane must not hide follow-on notice text that is on the page."""

    def test_recovered_span_includes_hidden_presence_below_the_burst(self):
        burst = 'The cart halts near a bent tree.'
        presence = 'Two scouts hide in the brush beside the path.'
        notice = 'A careful look notices broken twigs under the tree.'
        condition = 'If the scouts go unnoticed, they spring from hiding and attack.'
        later = 'A bell rings on a high tower.'
        # Facing columns: opening encounter on the left, a later room on the right.
        raw = (
            kit_skim_row('1. Marsh Road', '2. Far Chapel')
            + kit_skim_row('> ' + burst, '> ' + later)
            + kit_skim_row(presence, 'The chapel door is locked.')
            + kit_skim_row(notice, 'A rope hangs in the belfry.')
            + kit_skim_row(condition, 'The bell is later.')
        )
        span = kit_skim._same_column_encounter(raw, burst)
        self.assertIn(burst, ' '.join(span.split()))
        self.assertIn('Two scouts hide', span)
        self.assertIn('broken twigs', span)
        self.assertIn('spring from hiding', span)
        self.assertNotIn('chapel door', span)
        self.assertNotIn('bell rings', span)
        self.assertNotIn('belfry', span)


def kit_skim_row(left, right, width=66):
    return left + ' ' * max(3, width - len(left)) + right + '\n'


class AttestedCreaturePresenceCycle(unittest.TestCase):
    """A source-attested creature is present for Look, Stealth, and talk even without a stat block."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / 'game.sqlite'
        self.burst = 'The cart halts near a bent tree.'
        self.presence = 'Two scouts hide in the brush beside the path.'
        self.find = 'A careful look notices broken twigs under the tree.'
        manuscript = (
            '1. Marsh Road\n> ' + self.burst + '\n'
            + self.presence + '\n' + self.find + '\n'
            '2. Far Chapel\n> A bell rings on a high tower.\n'
        )
        kit_adventure.ingest_adventure(self.db, text=manuscript)
        scene = {
            'place': {'name': 'tree', 'quote': self.burst},
            'people': [{
                'id': 'scout_1', 'name': 'scouts',
                'quote': self.presence,
                'visibility': 'hidden', 'kind': 'creature',
                'goal': None, 'knowledge': [],
            }],
            'discoveries': [{'quote': self.find, 'status': 'established'}],
            'pressures': [],
        }
        accepted = kit_skim.accept(self.db, {
            'burst': self.burst, 'source_quote': self.burst,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'Marsh Road', 'scene': scene,
        })
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        start_session(str(self.db), str(SHEET))
        self.runtime = Runtime(str(self.db))
        self.addCleanup(self.runtime.close)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator())
        opening = self.bridge.prepare('Yes.')
        self.assertIn(self.burst, opening.get('spoken') or '')

    def test_look_and_sneak_ask_at_prepare_and_the_actor_is_present(self):
        state = self.runtime.load()[1]
        self.assertIn('scout_1', state.get('actors') or {})
        self.assertEqual(state['actors']['scout_1']['status'], 'hidden')
        looked = self.bridge.prepare('I look around carefully.', one_pass=True)
        self.assertEqual(looked.get('stage'), 'called_roll', looked)
        self.assertIn('Roll Perception', looked.get('spoken') or '')
        self.assertNotIn('DC', looked.get('spoken') or '')
        # Independent sneak from the opening, not after the Perception ask.
        runtime = Runtime(str(self.db))
        self.addCleanup(runtime.close)
        sneak_bridge = KitChatBridge(runtime, RoomAdjudicator())
        sneaked = sneak_bridge.prepare('I sneak around the edges and slip past.', one_pass=True)
        self.assertEqual(sneaked.get('stage'), 'called_roll', sneaked)
        self.assertIn('Roll Stealth', sneaked.get('spoken') or '')
        self.assertNotIn('DC', sneaked.get('spoken') or '')


class VisibleNpcReplyCycle(unittest.TestCase):
    """A present, addressable person answers in character through prepare/complete."""

    def test_visible_officer_answers_and_does_not_fall_back_to_narrator(self):
        intro = 'Captain Mara stands in the road and hails the caravan.'
        orders = 'Captain Mara has orders to hold the road until the wagons pass.'
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'talk.sqlite'
        source = (
            '1. The North Road\n> ' + intro + '\n' + orders + '\n'
            '2. The Tower\n> A bell rings on a high tower.\n'
        )
        kit_adventure.ingest_adventure(db, text=source)
        scene = {
            'place': {'name': 'road', 'quote': intro},
            'people': [{
                'id': 'captain_mara', 'name': 'Captain Mara',
                'quote': intro, 'visibility': 'visible', 'kind': 'person',
                'goal': {'quote': orders, 'status': 'established'},
                'knowledge': [],
            }],
            'discoveries': [], 'pressures': [],
        }
        accepted = kit_skim.accept(db, {
            'burst': intro, 'source_quote': intro,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The North Road', 'scene': scene,
        })
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        start_session(str(db), str(SHEET))
        runtime = Runtime(str(db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        first = bridge.prepare('Yes.')
        self.assertIn(intro, first.get('spoken') or '')
        self.assertEqual(runtime.load()[1]['actors']['captain_mara']['status'], 'alive')
        line = 'I ask Captain Mara what we should do next.'
        third = bridge.prepare(line, one_pass=True)
        self.assertEqual(third.get('stage'), 'one_pass', third)
        plan = RecordingModel().plan(third['input']['private'])
        plan.update(move='npc_reply', focus_actor='captain_mara',
                    table_presence='brief')
        plan['improv_read'].update(actor_ref='captain_mara',
                                   actor_basis='immediate_goal')
        plan['public_brief'].update(reply_to=line, scope='exchange')
        answered = bridge.complete(third['turn_id'], {
            'decision': plan,
            'performance': {'segments': [
                {'speaker': 'Narrator',
                 'text': 'Captain Mara keeps her post in the road and answers you.',
                 'reacts_to': 'none'},
                {'speaker': 'Captain Mara',
                 'text': 'I have orders to hold the road until the wagons pass.',
                 'reacts_to': 'none'},
                {'speaker': 'Kit',
                 'text': 'What do you say back?',
                 'reacts_to': 'ask Captain Mara what'},
            ]},
        })
        spoken = answered.get('spoken') or ''
        lines = [part for part in spoken.splitlines() if part.strip()]
        prefixes = [part.split(':', 1)[0] for part in lines]
        self.assertNotEqual(answered.get('stage'), 'rejected', answered)
        self.assertFalse(answered.get('engine_line'), answered)
        self.assertIn('Captain Mara', prefixes, spoken)
        self.assertIn('Kit', prefixes, spoken)
        self.assertIn('orders to hold the road', spoken)
        # The officer's line is their own speaker line, not folded into Narrator.
        officer = [part for part in lines if part.startswith('Captain Mara:')]
        self.assertTrue(officer, spoken)
        narrator = [part for part in lines if part.startswith('Narrator:')]
        for line in narrator:
            self.assertNotIn('orders to hold the road', line)
        self.assertTrue(any(part.startswith('Kit:') for part in lines), spoken)


    def test_an_invented_speaker_is_refused(self):
        intro = 'Captain Mara stands in the road and hails the caravan.'
        orders = 'Captain Mara has orders to hold the road until the wagons pass.'
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'talk.sqlite'
        source = (
            '1. The North Road\n> ' + intro + '\n' + orders + '\n'
            '2. The Tower\n> A bell rings on a high tower.\n'
        )
        kit_adventure.ingest_adventure(db, text=source)
        scene = {
            'place': {'name': 'road', 'quote': intro},
            'people': [{
                'id': 'captain_mara', 'name': 'Captain Mara',
                'quote': intro, 'visibility': 'visible', 'kind': 'person',
                'goal': {'quote': orders, 'status': 'established'},
                'knowledge': [],
            }],
            'discoveries': [], 'pressures': [],
        }
        accepted = kit_skim.accept(db, {
            'burst': intro, 'source_quote': intro,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The North Road', 'scene': scene,
        })
        self.assertEqual(accepted['stage'], 'skim_accepted', accepted)
        start_session(str(db), str(SHEET))
        runtime = Runtime(str(db))
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator())
        bridge.prepare('Yes.')
        line = 'I ask Captain Mara what we should do next.'
        third = bridge.prepare(line, one_pass=True)
        self.assertEqual(third.get('stage'), 'one_pass', third)
        plan = RecordingModel().plan(third['input']['private'])
        plan.update(move='npc_reply', focus_actor='captain_mara',
                    table_presence='brief')
        plan['improv_read'].update(actor_ref='captain_mara',
                                   actor_basis='immediate_goal')
        plan['public_brief'].update(reply_to=line, scope='exchange')
        from runtime.kit_agent import InvalidChange
        with self.assertRaises(InvalidChange):
            bridge.complete(third['turn_id'], {
                'decision': plan,
                'performance': {'segments': [
                    {'speaker': 'Invented Sage',
                     'text': 'I am not on this road and should not speak.',
                     'reacts_to': 'none'},
                    {'speaker': 'Kit',
                     'text': 'What do you say back?',
                     'reacts_to': 'ask Captain Mara what'},
                ]},
            })


class PlayablePickerOnly(unittest.TestCase):
    """The fallback picker never offers rules, how-to, or coaching headings."""

    def _titles(self, source, design='The Market Street'):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'picker.sqlite'
        kit_adventure.ingest_adventure(db, text=source)
        refused = kit_skim.accept(db, {
            'burst': 'A dragon lands on the bakery and the crowd cheers.',
            'source_quote': 'A dragon lands on the bakery and the crowd cheers.',
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': design,
        })
        return refused, [item.get('title') or '' for item in refused.get('alt_starts') or []]

    def test_coaching_and_instruction_titles_are_not_offered(self):
        source = (
            'If the fun is waning tonight\n'
            'That is up to you when the players ask.\n'
            'Example a character cannot walk through a wall.\n'
            'If you do some of the checks, use a 20-sided die.\n'
            'How to Play\n'
            'Appendix\n'
            'Credits\n'
            'The Market Street\n'
            '> You stand in the street while the lamps stay dark.\n'
        )
        refused, titles = self._titles(source)
        blob = ' '.join(titles).casefold()
        self.assertTrue(any('street' in title.casefold() or 'lamp' in title.casefold()
                            for title in titles), titles)
        for banned in ('fun is waning', 'up to you', 'example', 'if you',
                       'sided die', 'how to', 'appendix', 'credits', 'character cannot'):
            self.assertNotIn(banned, blob, titles)

    def test_naming_a_coaching_heading_still_commits_nothing(self):
        source = (
            'If the fun is waning tonight\n'
            'The Market Street\n'
            '> You stand in the street while the lamps stay dark.\n'
        )
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'picker.sqlite'
        kit_adventure.ingest_adventure(db, text=source)
        kit_skim.accept(db, {
            'burst': 'A dragon lands on the bakery and the crowd cheers.',
            'source_quote': 'A dragon lands on the bakery and the crowd cheers.',
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Market Street',
        })
        picked = kit_adventure.choose_start(db, 'If the fun is waning tonight')
        self.assertEqual(picked.get('stage'), 'pick_start', picked)
        self.assertFalse(picked.get('committed'))
        self.assertFalse(picked.get('room'))
        self.assertIsNone(picked.get('spoken'))

    def test_rules_only_window_gives_a_working_start(self):
        source = (
            'How to Play\n'
            'Read the rules before you begin.\n'
            'This procedure explains advantage or disadvantage and a 20-sided die.\n'
            'That is up to you when the players ask.\n'
        )
        refused, titles = self._titles(source, design='How to Play')
        blob = ' '.join(titles).casefold()
        for banned in ('how to', 'sided die', 'advantage', 'up to you', 'procedure'):
            self.assertNotIn(banned, blob, titles)
        line = (refused.get('table_line') or '').casefold()
        self.assertIn("we'll start here", line)
        self.assertTrue(titles, refused)
        folder_line = ' '.join(
            (item.get('kit_line') or '') for item in refused.get('alt_starts') or []).casefold()
        self.assertIn("we'll start", folder_line or line)


class GuardSpokenKeepsSpeakers(unittest.TestCase):

    def test_labelled_npc_reply_is_not_folded_into_narrator(self):
        from runtime import kit_opening
        beat = {
            'place_noun': 'road',
            'screen': [],
            'notice': {'pending': False, 'resolved': True, 'holds': False},
            'pressure': {'bypassed': True},
            'people': [{'id': 'captain_mara', 'name': 'Captain Mara',
                        'hidden': False, 'revealed': True}],
            'observed': {'heard': [], 'seen': ['captain_mara'], 'find': ''},
            'private': {},
        }
        spoken = kit_opening.guard_spoken(beat, (
            'Narrator: Captain Mara keeps her post in the road and answers you.\n'
            'Captain Mara: I have orders to hold the road until the wagons pass.\n'
            'Kit: What do you say back?'
        ))
        lines = [part for part in spoken.splitlines() if part.strip()]
        self.assertTrue(any(part.startswith('Captain Mara:') for part in lines), spoken)
        self.assertTrue(any(part.startswith('Kit:') for part in lines), spoken)
        for line in lines:
            if line.startswith('Narrator:'):
                self.assertNotIn('orders to hold the road', line)


class TornLaneYieldsToReadingOrder(unittest.TestCase):
    """A torn two-column gutter yields to a cleaner reading-order extract."""

    def _torn_row(self, left, right, width=36):
        return left.ljust(width) + '    ' + right

    def test_torn_gutter_does_not_beat_a_clean_later_extract(self):
        burst = 'The cart halts near a bent tree.'
        presence = 'Two scouts hide in the brush beside the path.'
        # Consistent wide gutter that splits each sentence mid-thought.
        torn = '\n'.join((
            self._torn_row('1. Marsh Road', 'Side notes'),
            self._torn_row('> The cart halts near a', 'bent tree.'),
            self._torn_row('Two scouts hide in the', 'brush beside the path.'),
            self._torn_row('A careful look notices', 'broken twigs under it.'),
            self._torn_row('If they go unnoticed they', 'spring from hiding now.'),
        ))
        clean = (
            '1. Marsh Road\n'
            '> ' + burst + '\n'
            + presence + '\n'
            'A careful look notices broken twigs under it.\n'
            'If they go unnoticed they spring from hiding now.\n'
        )
        with mock.patch.object(kit_skim, '_section_sources', return_value=[torn, clean]):
            text, columns = kit_skim.recover_opening_section(
                Path('unused.sqlite'), burst, torn)
        joined = ' '.join((text or '').split())
        self.assertIn(presence, joined)
        lanes = [item.get('lane') for item in columns or []]
        if 'left' in lanes or 'right' in lanes:
            # A two-lane result is only acceptable when a lane holds the full sentence.
            held = any(presence in ' '.join((item.get('text') or '').split())
                       for item in columns)
            self.assertTrue(held, columns)
