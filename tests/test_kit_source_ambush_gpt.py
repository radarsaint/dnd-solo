"""Regression: source-authored ambush timing, not a universal failed-check fight.

Original synthetic source only. No published adventure text or answer keys.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from runtime import kit_adventure, kit_scene_contract, kit_skim
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, start_session
from runtime.state_context import Runtime

from test_kit_scene_contract_gpt import FICTION, ENCOUNTER, SCENE, SHEET

CONDITION = 'If the bandits go unnoticed, they spring from their hiding place and attack.'


class SourceAuthoredAmbush(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / 'kit.sqlite'
        self.runtime = None

    def _scene(self, conditional):
        scene = copy.deepcopy(SCENE)
        if conditional:
            scene['pressures'][0].update(quote=CONDITION, status='conditional',
                                         activation='failed_notice')
        return scene

    def _room(self, conditional):
        text = ('1. The Road\n> ' + FICTION + '\n' + ENCOUNTER + '\n' +
                (CONDITION + '\n' if conditional else '') +
                '2. The Tower\n> A bell rings at a distant tower.\n')
        kit_adventure.ingest_adventure(self.db, text=text)
        response = kit_skim.accept(self.db, {'burst': FICTION, 'source_quote': FICTION,
            'page_start': 1, 'page_end': 1, 'alt_starts': [],
            'design_start_name': 'The Road', 'scene': self._scene(conditional)})
        self.assertEqual(response.get('stage'), 'skim_accepted', response)
        start_session(str(self.db), str(SHEET))
        self.runtime = Runtime(str(self.db))
        self.addCleanup(self.runtime.close)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator())
        self.bridge.prepare('Yes.')
        return response

    def _called_roll(self, total):
        revision, _state = self.runtime.load()
        self.runtime.commit('source-check-%s' % revision, revision, [{
            'type': 'pending_check', 'check': {'skill': 'perception', 'ability': 'wis',
                'target': 'none', 'called_turn': 'opening', 'action': 'I look around.'},
            'evidence': 'Player was called for notice and has not rolled yet.'}])
        return self.bridge.prepare(str(total), one_pass=True)

    def test_low_roll_starts_only_source_conditional_native_fight(self):
        self._room(True)
        self.assertEqual(self.runtime.source()['_opening_pressures'][0]['actors'],
                         ['bandit_1', 'bandit_2'])
        result = self._called_roll(4)
        self.assertEqual(result['stage'], 'called_roll', result)
        self.assertIn('Roll initiative', result['spoken'])
        self.assertNotIn('DC', result['spoken'])
        state = self.runtime.load()[1]
        self.assertEqual(state['combat']['status'], 'awaiting_initiative')
        self.assertEqual(state['combat']['surprised'], ['pc'])
        self.assertEqual(len(state['triggers_fired']), 1)
        self.assertTrue(all(state['actors'][key]['status'] == 'alive'
                            for key in ('bandit_1', 'bandit_2')))

    def test_low_roll_with_no_authored_attack_does_not_force_combat(self):
        self._room(False)
        result = self._called_roll(4)
        self.assertEqual(result['stage'], 'called_roll', result)
        self.assertNotIn('initiative', result['spoken'].casefold())
        self.assertFalse(self.runtime.load()[1].get('combat'))
        self.assertFalse(self.runtime.load()[1].get('triggers_fired'))

    def test_high_roll_notices_both_before_source_trigger(self):
        self._room(True)
        result = self._called_roll(18)
        self.assertEqual(result['stage'], 'called_roll', result)
        self.assertIn('Bandit 1', result['spoken'])
        self.assertIn('Bandit 2', result['spoken'])
        self.assertNotIn('initiative', result['spoken'].casefold())
        self.assertFalse(self.runtime.load()[1].get('combat'))

    def test_unsupported_failed_notice_activation_is_refused(self):
        bad = copy.deepcopy(SCENE)
        bad['pressures'][0]['activation'] = 'failed_notice'
        problems = kit_scene_contract.validate(bad, FICTION + '\n' + ENCOUNTER, FICTION)
        self.assertTrue(any('failed notice needs' in p for p in problems), problems)


if __name__ == '__main__':
    unittest.main()
