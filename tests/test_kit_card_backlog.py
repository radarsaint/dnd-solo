"""Card backlog (issue #45 asks a and c).

(a) A new stake named in passing, beside a read, a watch, a check or table talk ("Twenty gold
on the next hand. I read the dealer for a lie. Insight 14."), was dropped: the ruling went to
the read and the bet never reached the table. Now any seated, non-card ruling that names a
stake with a betting cue also keeps the bet for the next hand and says so.
(c) "I deal in with a copper." routed as table talk with no narration, and "I'll play a hand
for one copper." silently played at the 10 gp default. Now "deal in" asks for the game, and a
copper or silver offered at a gold table is told the stake in gold.

The engine pieces (next_bet, SMALL_COIN, the resolve-level bet) are general; the 6c table is
fixture data. The last class runs a table that is not 6c's. All dice are pinned."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_cards, kit_twenty_one
from runtime.kit_agent import Room6CAdjudicator
from runtime.state_context import Runtime
from test_kit_agent import FIXTURE

SOURCE = json.loads(FIXTURE.read_text())
NIK = json.loads((Path(__file__).parent / 'fixtures/characters/nik.json').read_text())


class Base(unittest.TestCase):
    SEED = 'card-backlog-0'

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)
        self.runtime.initialize(copy.deepcopy(SOURCE), 'area_06c')
        self.runtime.set_player_sheet(NIK)
        self.turns = 0

    def play(self, *lines):
        result = None
        for line in lines:
            revision, state = self.runtime.load()
            adjudicator = Room6CAdjudicator(source=self.runtime.source(), roll=lambda: 10, npc_roll=lambda: 10)
            state['roll_seed'] = self.SEED  # pin the deck (the runtime draws a fresh seed)
            result = adjudicator.resolve(line, revision, state)
            self.turns += 1
            self.runtime.commit(f'b{self.turns}', revision, list(result.events))
        return result

    def public(self):
        return self.runtime.load()[1]['procedures']['twenty_one']['public']


class BetBesideARead(Base):
    def test_the_pinned_first_hand_is_still_live(self):
        self.play("I'll play a hand. Ten gold.")
        self.assertIsNotNone(self.public()['round'])

    def assert_kept(self, result):
        self.assertIn('Your next hand is for 20 gp.', result.public_event)
        self.assertEqual(self.public()['pending_bet'], 20)

    def test_mid_hand_watch_keeps_the_bet(self):
        self.assert_kept(self.play("I'll play a hand. Ten gold.", 'Make it twenty gold. I watch his hands.'))

    def test_mid_hand_lie_read_keeps_the_bet(self):
        result = self.play("I'll play a hand. Ten gold.",
                           'Twenty gold on the next hand. I read the dealer for a lie. Insight 14.')
        self.assertIn('the dealer means it', result.public_event)
        self.assert_kept(result)

    def test_mid_hand_check_keeps_the_bet(self):
        result = self.play("I'll play a hand. Ten gold.",
                           'I bet twenty on the next one and study the backs of the cards. Investigation 18.')
        self.assertIn('Faint marks', result.public_event)
        self.assert_kept(result)

    def test_between_hands_table_talk_keeps_the_bet(self):
        self.assert_kept(self.play("I'll play a hand. Ten gold.", 'I stand.',
                                   "Twenty gold this time. I watch the other players' faces. Perception 15."))

    def test_the_kept_bet_is_the_next_hands_stake(self):
        self.play("I'll play a hand. Ten gold.", 'Twenty gold on the next hand. I read the dealer for a lie. Insight 14.',
                  'I stand.')
        result = self.play('Deal me another.')
        self.assertIn('20 gp a side', result.public_event)

    def test_gold_named_without_a_betting_cue_is_not_a_bet(self):
        result = self.play("I'll play a hand. Ten gold.", 'I stand.', 'I lost twenty gold in Waterdeep. I watch the dealer.')
        self.assertNotIn('Your next hand is for', result.public_event)
        self.assertNotIn('pending_bet', self.public())

    def test_no_bet_when_not_seated(self):
        result = self.play('Twenty gold on the next hand, I say to the dealer.')
        self.assertNotIn('Your next hand is for', result.public_event)


class CopperAtAGoldTable(Base):
    def test_deal_in_with_a_copper_is_a_request_told_the_table_plays_gold(self):
        result = self.play('I deal in with a copper.')
        self.assertEqual(result.kind, 'card_offer')
        self.assertTrue(result.public_event.startswith('The table plays for gold, not copper.'))

    def test_a_hand_for_one_copper_says_the_gold_stake(self):
        result = self.play("I'll play a hand for one copper.")
        self.assertIn('The table plays for gold, not copper: the stake is 10 gp.', result.public_event)
        self.assertIn('10 gp a side', result.public_event)

    def test_gold_named_gets_no_copper_note(self):
        result = self.play("I'll play a hand. Ten gold.")
        self.assertNotIn('copper', result.public_event)


class NotSixC(unittest.TestCase):
    """A different table (another name, dealer, stakes): the same general behavior."""
    def config(self):
        config = copy.deepcopy(SOURCE['procedures']['twenty_one'])
        config.update(name='the ferry game', default_stake=5, max_stake=40)
        return config

    def test_next_bet_needs_a_seat_and_a_cue(self):
        state = kit_cards.initial_state(self.config())
        self.assertIsNone(kit_cards.next_bet('Thirty gold on the next hand.', state))  # not seated
        state['public']['player'] = {'net': 0, 'purse': None, 'unwelcome': False}
        self.assertEqual(kit_cards.next_bet('Thirty gold on the next hand.', state), 30)
        self.assertEqual(kit_cards.next_bet('Make it thirty gold.', state), 30)
        self.assertIsNone(kit_cards.next_bet('I owe thirty gold to the ferryman.', state))
        self.assertIsNone(kit_cards.next_bet('Thirty gold on the next hand.', {'public': {'game': 'other'}}))

    def test_silver_at_a_gold_table_plays_the_default_and_says_so(self):
        config = self.config()
        table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 1, 'perception': 1}, 'ferry-0')
        text, game, _ = table.resolve('card_mode_play', 'I play a hand for two silver.', 1,
                                      kit_cards.initial_state(config))
        self.assertIn('The table plays for gold, not silver: the stake is 5 gp.', text)
        self.assertEqual(game['public']['round']['stake'], 5)

    def test_the_bet_line_caps_at_this_tables_most(self):
        config = self.config()
        table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 1, 'perception': 1}, 'ferry-1')
        _, game, _ = table.resolve('card_mode_play', 'I play it out.', 1, kit_cards.initial_state(config))
        text, game, _ = table.resolve('card_bet', 'Bet ninety on the next hand.', 2, game)
        self.assertIn('Your next hand is for 40 gp.', text)
        self.assertEqual(game['public']['pending_bet'], 40)


if __name__ == '__main__':
    unittest.main()
