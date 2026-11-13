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
        with mock.patch.object(kit_skim, 'recover_encounter_span', return_value=''):
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
                {'speaker': 'Captain Mara',
                 'text': 'I have orders to hold the road until the wagons pass.'},
                {'speaker': 'Kit',
                 'text': 'What do you say back?',
                 'reacts_to': 'ask Captain Mara what'},
            ]},
        })
        spoken = answered.get('spoken') or ''
        self.assertNotEqual(answered.get('stage'), 'rejected', answered)
        self.assertIn('Captain Mara:', spoken)
        self.assertIn('orders to hold the road', spoken)
        # The officer spoke; this is not a narrator-only fallback.
        self.assertTrue(
            any(part.startswith('Captain Mara:') for part in spoken.splitlines()),
            spoken)
