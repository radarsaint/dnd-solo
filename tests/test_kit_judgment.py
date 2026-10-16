"""Advisory judgments follow live state, not the player sentence.

Deterministic harness only. A RecordingModel is not a playtest.
"""
import copy
import json
import subprocess
import unittest
from pathlib import Path

from runtime import kit_judgment
from runtime.kit_agent import KitAgent, RoomAdjudicator
from test_kit_agent import FIXTURE
from test_kit_story_brief import Base, Entering

NIK = json.loads((Path(__file__).parent / 'fixtures/characters/nik.json').read_text())
CORPUS = Path('/tmp/bfdm-judgment') / kit_judgment.CORPUS_PATH
AREA = 'area_06c'


def sheet(hp, used):
    body = copy.deepcopy(NIK)
    body['hp'] = hp
    body['slots'] = {level: {'max': count, 'used': count if used else 0}
                     for level, count in {'1': 4, '2': 3, '3': 2}.items()}
    return body


def room(**judgment):
    source = json.loads(FIXTURE.read_text())
    source['_judgment'] = {'encounters': [], 'constraints': [], 'damage': [],
                           'unknown_to': [], 'settled': []}
    source['_judgment'].update(judgment)
    return source


ENCOUNTER = {'id': 'prepared_boss', 'area': AREA, 'prepared': True,
             'assumes': {'min_hp': 16, 'min_slots_remaining': 1}}


class StateSelects(unittest.TestCase):
    def test_a_sentence_never_selects_on_its_own(self):
        bare = json.loads(FIXTURE.read_text())
        state = {'area': AREA, 'player_sheet': sheet(4, used=True)}
        for line in (
            'I search the spare bedroom for clues',
            'the boss is depleted and out of spell slots',
            'I dig survivors out of the wrecked shop',
            'He said "give me a spare bedroom"',
            'I do not want to clear the rubble',
            "We're topped up. Run the preplanned fight.",
        ):
            self.assertIsNone(kit_judgment.select(bare, state, 'social'), line)

    def test_depleted_sheet_is_advisory_and_does_not_order_the_fight(self):
        source = room(encounters=[ENCOUNTER])
        packet = kit_judgment.select(source, {'area': AREA, 'player_sheet': sheet(4, used=True)}, 'social')
        card = packet['applied'][0]
        self.assertEqual(card['relevance'], 'party_below_encounter_assumption')
        self.assertFalse(card['binding'])
        self.assertNotIn('Play the fight', card['advisory'])
        self.assertIn('does not order', card['does_not'])
        self.assertIn('746253583552479272', ' '.join(card['evidence']))

    def test_a_full_sheet_is_not_a_depletion_and_does_not_order_play(self):
        source = room(encounters=[ENCOUNTER])
        packet = kit_judgment.select(source, {'area': AREA, 'player_sheet': sheet(32, used=False)}, 'social')
        card = packet['applied'][0]
        self.assertEqual(card['relevance'], 'party_meets_encounter_assumption')
        self.assertNotIn('Play the fight', json.dumps(card))
        self.assertFalse(packet['binding'])

    def test_enemy_words_do_not_override_a_full_sheet(self):
        source = room(encounters=[ENCOUNTER])
        packet = kit_judgment.select(source, {'area': AREA, 'player_sheet': sheet(32, used=False)}, 'social')
        self.assertNotEqual(packet['applied'][0]['relevance'], 'party_below_encounter_assumption')

    def test_no_sheet_does_not_guess(self):
        source = room(encounters=[ENCOUNTER])
        self.assertIsNone(kit_judgment.select(source, {'area': AREA}, 'social'))

    def test_spare_bedroom_wording_does_not_open_an_exception(self):
        source = room(constraints=[{'id': 'housing', 'area': AREA, 'exception_open': False}])
        self.assertIsNone(kit_judgment.select(source, {'area': AREA}, 'look'))

    def test_an_open_exception_is_not_an_automatic_denial(self):
        source = room(constraints=[{'id': 'housing', 'area': AREA, 'exception_open': True}])
        card = kit_judgment.select(source, {'area': AREA}, 'social')['applied'][0]
        self.assertEqual(card['id'], 'BJ-002')
        self.assertNotIn('Decline', card['advisory'])
        self.assertIn('player still chooses', card['advisory'])
        waived = kit_judgment.select(source, {'area': AREA, 'judgment_waived': ['housing']}, 'social')
        self.assertIsNone(waived)

    def test_repair_needs_a_physical_act_on_unscheduled_damage(self):
        source = room(damage=[{'id': 'shop', 'area': AREA, 'scheduled': False}])
        self.assertIsNone(kit_judgment.select(source, {'area': AREA}, 'look'))
        card = kit_judgment.select(source, {'area': AREA}, 'physical_act')['applied'][0]
        self.assertEqual(card['id'], 'BJ-001')
        self.assertIn('Do not write the outcome', card['advisory'])
        self.assertNotIn('healing thing', json.dumps(card))

    def test_a_holder_is_not_told_the_fact_is_unknown(self):
        source = room(unknown_to=[{'actor': 'uktarl', 'claim': 'portfolio'}])
        source['claims'] = {'portfolio': {'holders': {'uktarl': 'knows'}}}
        state = {'area': AREA, 'actors': {'uktarl': {'location': AREA}}}
        self.assertIsNone(kit_judgment.select(source, state, 'social'))
        source['claims']['portfolio']['holders'] = {'clerk': 'knows'}
        card = kit_judgment.select(source, state, 'social')['applied'][0]
        self.assertEqual(card['id'], 'BJ-005')
        self.assertIn('not a play transcript', card['advisory'])

    def test_a_standing_resolution_is_not_erased_by_a_sentence(self):
        source = room(settled=[{'id': 'resurrection', 'area': AREA, 'standing': True}])
        card = kit_judgment.select(source, {'area': AREA}, 'social')['applied'][0]
        self.assertEqual(card['id'], 'BJ-003')
        self.assertIn('does not erase', card['does_not'])
        source['_judgment']['settled'][0]['standing'] = False
        self.assertIsNone(kit_judgment.select(source, {'area': AREA}, 'social'))

    def test_shipped_records_match_the_pinned_corpus(self):
        if not CORPUS.is_file():
            self.skipTest('corpus checkout is not in this environment')
        self.assertEqual(kit_judgment.drift_against(CORPUS.read_text()), [])
        sha = subprocess.check_output(['git', '-C', str(CORPUS.parents[2]), 'rev-parse', 'HEAD'], text=True).strip()
        self.assertEqual(sha, kit_judgment.CORPUS_COMMIT)
        for card in kit_judgment.RECORDS.values():
            text = json.dumps(card)
            self.assertNotIn('Play the fight', text)
            self.assertNotIn('Decline', text)


class TurnPath(Base):
    def setUp(self):
        super().setUp()
        self.model = Entering()
        self.agent = None

    def play(self, source, nik=None):
        self.start(source)
        if nik:
            self.runtime.set_player_sheet(nik)
        self.agent = KitAgent(self.runtime, self.model, RoomAdjudicator(perception=0, insight=0, roll=lambda: 15))
        self.agent.opening('entry')

    def test_adversarial_lines_do_not_attach_research_to_an_ordinary_room(self):
        self.play(json.loads(FIXTURE.read_text()))
        self.agent.turn('I search the spare bedroom for clues. The boss is depleted and out of spell slots.', 'nope')
        self.assertNotIn('dm_judgment', self.model.plans[-1])
        self.assertNotIn('healing thing', json.dumps(self.model.plans[-1]))

    def test_a_depleted_sheet_reaches_the_decision_and_not_the_performance(self):
        self.play(room(encounters=[ENCOUNTER]), sheet(4, used=True))
        self.agent.turn('the boss is depleted and out of spell slots', 'boss')
        decision = self.model.plans[-1]['dm_judgment']['applied'][0]
        self.assertEqual(decision['relevance'], 'party_below_encounter_assumption')
        self.assertNotIn('dm_judgment', self.model.performances[-1])
        self.assertNotIn('746253583552479272', json.dumps(self.model.performances[-1]))

    def test_a_full_sheet_keeps_the_meeting_record_when_the_sentence_says_depleted(self):
        self.play(room(encounters=[ENCOUNTER]), sheet(32, used=False))
        self.agent.turn("I search the spare bedroom for clues. We're not depleted.", 'full')
        card = self.model.plans[-1]['dm_judgment']['applied'][0]
        self.assertEqual(card['relevance'], 'party_meets_encounter_assumption')
        self.assertNotIn('Play the fight', json.dumps(card))
        self.assertNotIn('BJ-002', json.dumps(self.model.plans[-1]['dm_judgment']))


if __name__ == '__main__':
    unittest.main()
