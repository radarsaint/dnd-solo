"""Gravedigger, the card game the DM chose for area 6c (runtime/kit_table_game.py).

The adventure says only that the dealer and his three companions play cards with a
marked deck, coins on the table. These tests check that the procedure can carry out
everything the dealer's invitation promises: a deal, a draw, a round of betting, real
stakes from the table coins, the dealer's cheat, the player's chances to catch it, and
payouts that persist from turn to turn.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import kit_agent, kit_table_game as tg
from runtime.kit_agent import KitChatBridge, PendingRuling, Room6CAdjudicator
from runtime.state_context import InvalidChange, Runtime

from test_kit_agent import FIXTURE, RecordingModel, with_check

SEEDS = range(400)


def gold(game):
    return tg._gold_total(game)


def joined(seed, watch=False, purse=30, perception=2, roll=None):
    return tg.play(None, 'join watch' if watch else 'join', seed=seed, perception=perception,
                   purse_gp=purse, roll=roll)


def first_seed(predicate, **kwargs):
    for seed in SEEDS:
        move = joined(seed, **kwargs)
        if predicate(move):
            return seed, move
    raise AssertionError('no seed in range satisfies the scenario')


class ProcedureTests(unittest.TestCase):
    def test_table_coins_are_the_npc_stacks_and_the_game_is_a_declared_dm_choice(self):
        self.assertEqual(sum(tg.STARTING_STACKS_GP.values()), 85)
        self.assertIn("DM's choice", tg.DM_CHOICES)
        self.assertIn('names no game', tg.DM_CHOICES)
        self.assertNotIn('Dragon', tg.PUBLIC_RULES)

    def test_joining_needs_the_purse_and_perception(self):
        with self.assertRaisesRegex(tg.MissingInput, 'purse-gp'):
            tg.play(None, 'join', seed=1, perception=2)
        with self.assertRaisesRegex(tg.MissingInput, 'perception'):
            tg.play(None, 'join', seed=1, purse_gp=30)
        with self.assertRaisesRegex(tg.MissingInput, 'ante'):
            tg.play(None, 'join', seed=1, perception=2, purse_gp=1)

    def test_moves_outside_their_phase_are_refused(self):
        with self.assertRaisesRegex(tg.MissingInput, 'not a move right now'):
            tg.play(None, 'bet 3', seed=1)
        with self.assertRaisesRegex(InvalidChange, 'bet'):
            tg.play(joined(1).state, 'bet 11', seed=1)

    def test_a_hand_is_deterministic_and_conserves_gold(self):
        a, b = joined(7), joined(7)
        self.assertEqual(a.state, b.state)
        self.assertEqual(a.public, b.public)
        start = gold(a.state)
        self.assertEqual(start, 85 + 30)
        state = tg.play(a.state, 'keep', seed=7).state
        state = tg.play(state, 'check', seed=7).state
        if state['phase'] == 'answer_raise':
            state = tg.play(state, 'call', seed=7).state
        self.assertEqual(state['phase'], 'between_hands')
        self.assertEqual(gold(state), start)
        self.assertEqual(state['pot_gp'], 0)
        self.assertEqual(state['history'][-1]['hand_no'], 1)

    def test_many_hands_keep_gold_and_record_payouts(self):
        for seed in range(30):
            state = joined(seed, purse=40).state
            start = gold(state)
            for _ in range(4):
                if state['phase'] == 'between_hands':
                    if state['player']['purse_gp'] < tg.ANTE_GP:
                        break
                    state = tg.play(state, 'deal', seed=seed).state
                state = tg.play(state, 'swap 1', seed=seed).state
                state = tg.play(state, 'bet 2' if state['player']['purse_gp'] >= 2 else 'check', seed=seed).state
                if state['phase'] == 'answer_raise':
                    state = tg.play(state, 'fold', seed=seed).state
                self.assertEqual(state['phase'], 'between_hands')
                self.assertEqual(gold(state), start)
            net = sum(hand['player_net_gp'] for hand in state['history'])
            self.assertEqual(state['player']['purse_gp'], 40 + net)

    def test_the_dealer_uses_the_marked_deck_and_passive_perception_can_catch_the_slip(self):
        seed, move = first_seed(lambda m: m.state['this_hand']['dealer_improved'] and m.state['this_hand']['noticed'],
                                perception=8)
        record = move.state['this_hand']
        self.assertTrue(record['dealer_read_backs'])
        self.assertEqual(record['notice_basis'], 'passive')
        self.assertEqual(record['notice_total'], 18)
        self.assertGreaterEqual(record['notice_total'], record['sleight_total'])
        self.assertEqual(move.reveals, ['marked_deck'])
        self.assertIn('The backs carry small marks', move.public)

    def test_a_player_roll_is_used_for_watching_the_deal(self):
        move = joined(3, watch=True, perception=0, roll=lambda: 20)
        self.assertEqual(move.state['this_hand']['notice_total'], 20)
        self.assertEqual(move.state['this_hand']['notice_basis'], 'player roll')
        self.assertTrue(move.state['this_hand']['noticed'])
        with self.assertRaises(InvalidChange):
            joined(3, watch=True, roll=lambda: 21)

    def test_a_challenge_after_seeing_the_cheat_voids_the_hand_and_returns_every_stake(self):
        move = joined(3, watch=True, perception=0, roll=lambda: 20)
        before = dict(move.state['stacks_gp'])
        after = tg.play(move.state, 'challenge', seed=3, known_facts=['marked_deck'])
        self.assertEqual(after.state['phase'], 'between_hands')
        self.assertEqual(after.state['dealer_status'], 'exposed')
        self.assertEqual(after.state['player']['purse_gp'], 30)
        self.assertEqual(after.state['history'][-1]['result'], 'void')
        for seat, stack in before.items():
            self.assertEqual(after.state['stacks_gp'][seat], stack + tg.ANTE_GP)
        self.assertEqual(after.reveals, [])  # already known

    def test_a_blind_challenge_is_insight_against_his_deception(self):
        move = joined(5, perception=-5)
        self.assertFalse(move.state['this_hand']['noticed'])
        with self.assertRaisesRegex(tg.MissingInput, 'insight'):
            tg.play(move.state, 'challenge', seed=5)
        upheld = tg.play(move.state, 'challenge', seed=5, insight=0, roll=lambda: 20)
        # Deception is d20+4 (max 24): a natural 20 with +0 wins only on a low roll.
        failed = tg.play(move.state, 'challenge', seed=5, insight=-10, roll=lambda: 1)
        self.assertEqual(failed.state['phase'], 'draw')
        self.assertEqual(failed.state['accusations_failed'], 1)
        self.assertIn('the hand goes on', failed.public)
        self.assertIn(upheld.state['phase'], ('between_hands', 'draw'))
        if upheld.state['phase'] == 'between_hands':
            self.assertEqual(upheld.reveals, ['marked_deck'])

    def test_once_exposed_the_dealer_plays_honestly(self):
        move = joined(3, watch=True, perception=0, roll=lambda: 20)
        state = tg.play(move.state, 'challenge', seed=3).state
        state = tg.play(state, 'deal', seed=3).state
        self.assertFalse(state['this_hand']['dealer_read_backs'])
        self.assertFalse(state['this_hand']['dealer_improved'])

    def test_the_public_view_never_shows_other_hands_or_the_stock(self):
        state = joined(11).state
        view = tg.public_view(state)
        self.assertNotIn('stock', view)
        self.assertNotIn('hands', view)
        self.assertEqual(view['your_cards'], tg.hand_text(state['hands']['player']))
        for seat in tg.NPC_SEATS:
            if seat in state['hands']:
                self.assertNotIn(tg.hand_text(state['hands'][seat]), json.dumps(view))
        self.assertIn('hands', tg.private_view(state))

    def test_unnoticed_hands_say_nothing_secret(self):
        for seed in range(40):
            move = joined(seed, perception=-5)
            texts = [move.public]
            state = move.state
            for step in ('keep', 'check', 'call'):
                if step in tg.MOVES_BY_PHASE[state['phase']]:
                    move = tg.play(state, step, seed=seed)
                    state = move.state
                    texts.append(move.public)
            for text in texts:
                if not move.reveals:
                    kit_agent.check_public_content(text, {}, '')
                self.assertNotIn('doppelganger', text.lower())
                self.assertNotIn('vampire', text.lower())

    def test_leaving_keeps_the_purse_for_a_return(self):
        state = joined(2).state
        state = tg.play(state, 'fold', seed=2).state
        if state['phase'] == 'answer_raise':
            state = tg.play(state, 'fold', seed=2).state
        purse = state['player']['purse_gp']
        state = tg.play(state, 'leave', seed=2).state
        self.assertEqual(state['phase'], 'left')
        back = tg.play(state, 'join', seed=2, purse_gp=500).state
        self.assertEqual(back['player']['purse_gp'], purse - tg.ANTE_GP)


KIT_LINES = ['The cards have spoken, and they have opinions about you.',
             'Bold of you to trust a deck that has seen this many hands.',
             'Somewhere a gravedigger is laughing, and it is not at the dealer.',
             'And just like that the pot changes its mind about who it loves.']


def game_speech(event, dealer_line, kit_line=KIT_LINES[0]):
    return with_check({'segments': [
        {'speaker': 'Kit', 'text': kit_line,
         'reacts_to': ' '.join(event.split()[:4])},
        {'speaker': 'Dealer', 'text': dealer_line}]},
        aside='Kit answers the procedure result she quotes: the cards were dealt and she reacts.')


DEALER_LINE = ('Welcome to Gravedigger, friend. Your two gold sits in the pot with ours now. Keep those '
               'cards or trade one for the top of the stock, and take your time about it; the grave is '
               'patient, and so am I, mostly.')
DEALER_KEEP = ('Keeping them? Brave, or lazy, and at this table the two look the same across the wood. '
               'Now the betting, friend: check if you are shy, bet if you are not, and remember that '
               'every coin you push in is a coin I get to count.')
DEALER_AFTER = ('There it is, then. The table settles its debts before anyone draws breath, friend, and '
                'nobody here leaves owing the grave. Stay for another hand of Gravedigger if your nerve '
                'holds, or walk on while you still have something to walk with.')

DEALER_FOLD = ('Folding to a single bet, friend? The grave keeps what it is given and gives nothing '
               'back, so your coins stay right where they fell. Sit a while longer and watch how the '
               'rest of us lose, if it comforts you.')


class BridgeGameTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.db)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.model = RecordingModel()
        self.bridge = KitChatBridge(self.runtime, Room6CAdjudicator(perception=2, insight=1, purse_gp=30))

    def play(self, words, move, turn_id, line=DEALER_LINE, kit=0):
        staged = self.bridge.prepare(words, turn_id, game_move=move, one_pass=True)
        private = staged['input']['private']
        plan = self.model.plan(private)
        result = self.bridge.complete(turn_id, {
            'decision': plan, 'performance': game_speech(private['accepted_public_event'], line, KIT_LINES[kit])})
        return staged, result

    def test_a_hand_runs_across_bridge_turns_and_the_payout_persists(self):
        staged, _ = self.play('Deal me in.', 'join', 't1')
        self.assertEqual(staged['input']['private']['action_kind'], 'table_game')
        self.assertIn('Gravedigger, hand 1', staged['input']['private']['accepted_public_event'])
        self.assertEqual(staged['table_game_host']['phase'], 'draw')
        self.assertIn('keep', staged['table_game_host']['moves_now'])
        public_game = staged['input']['public']['table_game']
        self.assertNotIn('dm_only', public_game)
        self.assertIn('hands', staged['input']['private']['table_game']['dm_only'])
        _, state = self.runtime.load()
        self.assertEqual(state['table_game']['phase'], 'draw')
        self.play('I keep what I have.', 'keep', 't2', line=DEALER_KEEP, kit=1)
        _, state = self.runtime.load()
        self.assertEqual(state['table_game']['phase'], 'bet')
        self.play('I check.', 'check', 't3', line=DEALER_AFTER, kit=2)
        _, state = self.runtime.load()
        if state['table_game']['phase'] == 'answer_raise':
            self.play('I fold.', 'fold', 't4', line=DEALER_FOLD, kit=3)
            _, state = self.runtime.load()
        game = state['table_game']
        self.assertEqual(game['phase'], 'between_hands')
        self.assertEqual(gold(game), 115)
        self.assertEqual(game['player']['purse_gp'], 30 + game['history'][-1]['player_net_gp'])

    def test_prose_game_moves_mid_hand_go_back_to_the_host(self):
        self.play('Deal me in.', 'join', 't1')
        with self.assertRaisesRegex(PendingRuling, 'game_move'):
            self.bridge.prepare('I fold.', 't2', one_pass=True)

    def test_a_seat_request_without_a_move_is_talk_with_a_host_cue(self):
        staged = self.bridge.prepare('Deal me in, then.', 't1', one_pass=True)
        self.assertEqual(staged['input']['private']['action_kind'], 'social')
        self.assertIn('cue', staged['table_game_host'])

    def test_the_dealer_cannot_name_another_game_or_other_stakes(self):
        staged = self.bridge.prepare('Deal me in.', 't1', game_move='join', one_pass=True)
        private = staged['input']['private']
        plan = self.model.plan(private)
        high_card = game_speech(private['accepted_public_event'],
                                'High card, matching coin. Simple as breathing, friend. ' + DEALER_LINE)
        with self.assertRaisesRegex(InvalidChange, 'high card'):
            self.bridge.complete('t1', {'decision': plan, 'performance': high_card})
        big_bet = game_speech(private['accepted_public_event'],
                              'The pot wants fifty gold before you see another card. ' + DEALER_LINE)
        with self.assertRaisesRegex(InvalidChange, '50 gp wager'):
            self.bridge.complete('t1', {'decision': plan, 'performance': big_bet})

    def test_missing_join_inputs_commit_nothing(self):
        bridge = KitChatBridge(self.runtime, Room6CAdjudicator())
        with self.assertRaisesRegex(PendingRuling, 'purse-gp'):
            bridge.prepare('Deal me in.', 't1', game_move='join', one_pass=True)
        self.assertEqual(self.runtime.load()[0], 0)

    def test_cli_game_move_and_game_view(self):
        self.runtime.close()
        packet = self.cli('prepare', '--turn-id', 'c1', '--one-pass', '--game-move', 'join',
                          '--purse-gp', '25', '--perception', '1', '--action', 'Deal me in.')
        self.assertIn('Gravedigger, hand 1', packet['input']['private']['accepted_public_event'])
        self.assertIn('you hold 23 gp', packet['input']['private']['accepted_public_event'])
        self.assertEqual(self.cli('game')['phase'], 'idle')  # nothing committed yet

    def cli(self, *argv):
        out = io.StringIO()
        with patch('sys.argv', ['kit_agent', *argv, '--db', str(self.db)]), contextlib.redirect_stdout(out):
            self.assertEqual(kit_agent.main(), 0)
        return json.loads(out.getvalue())

if __name__ == '__main__':
    unittest.main()
