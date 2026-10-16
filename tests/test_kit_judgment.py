"""The private decision input receives a curated judgment only when the line matches.

These are deterministic harness results. They show the turn path loads the packet.
They do not show that a model played a better scene.
"""
import json
import unittest

from runtime import kit_judgment
from runtime.kit_agent import KitAgent, RoomAdjudicator
from test_kit_story_brief import Base, Entering


class Selector(unittest.TestCase):
    def test_irrelevant_line_selects_nothing(self):
        self.assertIsNone(kit_judgment.for_turn('I nod to the dealer and set a copper on the table.'))
        self.assertIsNone(kit_judgment.for_turn('We look around the room.', 'opening'))

    def test_repair_keeps_its_limit_and_does_not_write_the_outcome(self):
        packet = kit_judgment.for_turn(
            'I want to clear the rubble at the money changer and help rebuild it.')
        card = packet['applied'][0]
        self.assertEqual(card['id'], 'unplanned_repair')
        self.assertIn('Do not write their outcome', card['advice'])
        self.assertIn('865565818481279018', ' '.join(card['evidence']))
        self.assertIn('designed vulnerability', card['limit'])
        self.assertEqual(card['later_judgments'], [])
        self.assertNotIn('hindsight', card)

    def test_a_house_is_not_treated_as_repair(self):
        packet = kit_judgment.for_turn(
            'Let me help rebuild the street, and give me a house: a spare bedroom of my own.')
        ids = [card['id'] for card in packet['applied']]
        self.assertEqual(ids, ['designed_constraint'])
        self.assertIn('863492563784040539', packet['applied'][0]['limit'])

    def test_a_depleted_party_reconsiders_the_prepared_fight(self):
        packet = kit_judgment.for_turn(
            'There are four of us and we are depleted, out of spell slots. Do not take us into the preplanned fight.')
        self.assertEqual(packet['applied'][0]['id'], 'party_mismatch')
        self.assertIn('not a rule', packet['applied'][0]['limit'])

    def test_a_fresh_party_does_not_skip_the_prepared_fight(self):
        packet = kit_judgment.for_turn(
            "We're topped up, not depleted. Run the preplanned fight.")
        ids = [card['id'] for card in packet['applied']]
        self.assertEqual(ids, ['prepared_fight_stands'])
        self.assertIn('first read was not the table', packet['applied'][0]['limit'])

    def test_undisclosed_knowledge_and_a_settled_resurrection_stay_narrow(self):
        secret = kit_judgment.for_turn(
            'Have him act on the clue they missed. He knows they mentioned Tasha even though they never said it.')
        self.assertEqual(secret['applied'][0]['id'], 'undisclosed_knowledge')
        self.assertIn('BCS-000172', secret['applied'][0]['limit'])
        self.assertIn('not a play transcript', secret['applied'][0]['limit'])
        rez = kit_judgment.for_turn('Nerf what already happened and undo last night\'s resurrection.')
        self.assertEqual(rez['applied'][0]['id'], 'nonretroactive_correction')
        self.assertIn('744056939096571924', rez['applied'][0]['limit'])

    def test_hindsight_requires_a_source_and_the_shipped_cards_have_none(self):
        self.assertEqual(kit_judgment._later([{'text': 'I would do it differently now'}]), [])
        kept = kit_judgment._later([{'source': 'note:2026-10-15', 'text': 'A later sourced line.', 'status': 'UNPROVEN'}])
        self.assertEqual(kept[0]['source'], 'note:2026-10-15')
        for card in kit_judgment.CARDS:
            self.assertEqual(card['later_judgments'], ())


class TurnPath(Base):
    def setUp(self):
        super().setUp()
        self.start()
        self.model = Entering()
        self.agent = KitAgent(self.runtime, self.model, RoomAdjudicator(perception=0, insight=0, roll=lambda: 15))
        self.agent.opening('entry')

    def test_a_repair_line_is_in_the_decision_and_not_in_the_performance(self):
        self.agent.turn('I want to clear the rubble and help rebuild the money changer.', 'repair')
        decision = self.model.plans[-1]
        self.assertEqual(decision['dm_judgment']['applied'][0]['id'], 'unplanned_repair')
        self.assertNotIn('dm_judgment', self.model.performances[-1])
        self.assertNotIn('865565818481279018', json.dumps(self.model.performances[-1]))

    def test_an_ordinary_line_does_not_carry_the_research(self):
        self.agent.turn('I nod to the dealer and set a copper on the table.', 'ordinary')
        self.assertNotIn('dm_judgment', self.model.plans[-1])

    def test_the_constraint_and_the_fresh_party_change_which_card_arrives(self):
        self.agent.turn('Give me a spare bedroom as my own house. It was meant to be vulnerable and I want that gone.', 'house')
        self.assertEqual(self.model.plans[-1]['dm_judgment']['applied'][0]['id'], 'designed_constraint')
        self.agent.turn("We're topped up and ready for the fight. Run the preplanned fight.", 'fresh')
        self.assertEqual(self.model.plans[-1]['dm_judgment']['applied'][0]['id'], 'prepared_fight_stands')


if __name__ == '__main__':
    unittest.main()
