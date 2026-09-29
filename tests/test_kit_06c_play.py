"""Playtest 03 fixes in area 6c (tests/playtests/2026-09-29-area-06c-voice-spec-nik.md):
Kit's asides answer what happened; the router hears an answer to the dealer as speech;
the detail oracle and canon ledger answer "What game is it?"; and the card game is a
procedure the runtime runs, marked deck and all."""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_cards, kit_voice
from runtime.kit_agent import KitAgent, Room6CAdjudicator, npc_addressed_player, room_intent
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import DEALER_EXCHANGES, FIXTURE, RecordingModel

OPENING_DEALER = ("A guest at the turn of a card. How extravagantly lucky for us. My companion would finish "
                  "the hand; I would improve it. If you've coin, I'll make space. If you've a question, ask "
                  "it before I deal. But do tell me, traveler—what were you hoping to find when you opened "
                  "that door?")
NIK_WISH = ("I was hoping to find. I dunno. An exceedingly hot elvin maiden whose all sex crazed and ready "
            "to heap treasure at me.")
GAME_ASK = 'What game is it?'
GAME_SLOT = 'area_06c/card_table/game'


def seg(speaker, text, reacts_to=None):
    return {'speaker': speaker, 'text': text, **({'reacts_to': reacts_to} if reacts_to else {})}


class KitAsideTests(unittest.TestCase):
    """Fix 1: every Kit aside quotes what it reacts to, and cannot deny what just happened."""

    def check(self, segments, action='[scene entry]', event='A newcomer has reached the card room.',
              kind='opening'):
        kit_voice.check_kit_asides(segments, action, event, kind)

    def test_the_playtest_line_is_rejected_after_the_welcome(self):
        segments = [seg('Dealer', OPENING_DEALER),
                    seg('Kit', 'He could have said hello. Apparently there\'s no money in it.',
                        reacts_to='A guest at the turn of a card')]
        with self.assertRaisesRegex(InvalidChange, 'greeting'):
            self.check(segments)

    def test_reacts_to_is_required_and_must_be_verbatim(self):
        with self.assertRaisesRegex(InvalidChange, 'reacts_to'):
            self.check([seg('Dealer', OPENING_DEALER), seg('Kit', 'Extravagantly lucky. Sure.')])
        with self.assertRaisesRegex(InvalidChange, 'reacts_to'):
            self.check([seg('Dealer', OPENING_DEALER),
                        seg('Kit', 'Lucky, he says.', reacts_to='the luckiest guest alive')])

    def test_a_true_reaction_passes(self):
        self.check([seg('Dealer', OPENING_DEALER),
                    seg('Kit', 'He offered to improve the hand. Watch that verb.', reacts_to='I would improve it')])

    def test_a_kit_reaction_to_the_players_words(self):
        kit_voice.check_kit_asides([seg('Kit', 'You asked a card sharp for a miracle. Bold.',
                                        reacts_to='heap treasure at me'),
                                    seg('Dealer', DEALER_EXCHANGES[1][1])],
                                   NIK_WISH, NIK_WISH, 'social')


class RouterTests(unittest.TestCase):
    """Fix 3: an answer to the dealer's question is social speech, not a physical action."""

    def test_nik_exact_reply_after_the_dealer_asked_routes_social(self):
        self.assertTrue(npc_addressed_player(f'Narrator: The dealer keeps the card aloft.\nDealer: {OPENING_DEALER}'))
        self.assertEqual(room_intent(NIK_WISH, addressed=True), 'social')

    def test_physical_actions_and_stealth_still_route_as_before(self):
        self.assertEqual(room_intent('I sneak past the table toward the far door.', addressed=True), 'stealth')
        self.assertEqual(room_intent('I tip the stone tub over and use it as cover.', addressed=True), 'tip_tub')
        self.assertEqual(room_intent('I attack Uktarl in the middle of the game.', addressed=True), 'combat')

    def test_the_whole_turn_commits_through_the_agent(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        agent = KitAgent(runtime, RecordingModel(), Room6CAdjudicator(perception=0, insight=0, roll=lambda: 20))
        agent.turn('I nod to the dealer.', 'nod')  # the dealer's reply asks the player a question
        self.assertTrue(npc_addressed_player(runtime.recent_kit_turns()[-1]['spoken']))
        result = agent.turn(NIK_WISH, 'wish')
        self.assertEqual(runtime.recent_kit_turns()[-1]['public_event'], kit_agent.social_event(NIK_WISH))
        self.assertIn('Dealer:', result['spoken'])


class GameModel(RecordingModel):
    """Answers "What game is it?" by the oracle: picks the Three-Dragon Ante card and
    declares its procedure, and performs that answer."""

    def plan(self, payload):
        plan = super().plan(payload)
        oracle = payload.get('detail_oracle')
        if oracle and oracle['status'] == 'open' and oracle['slot'] == GAME_SLOT:
            # The decision's lean view: draw_id, entry, handle, procedure (no roots or basis).
            dealt = next(card for card in oracle['deal'] if card['draw_id'].endswith('.three_dragon_ante'))
            plan['detail'] = {
                'request': payload['player_action'], 'slot': oracle['slot'], 'choice': dealt['draw_id'],
                'candidates': [], 'typical': -1, 'chosen': -1,
                'owner': 'uktarl: a game where knowing the cards pays',
                'handle': 'buy in, bet, fold, or watch the deal',
                'because': 'true because the four play cards at this table with coins in front of them',
                'price_quote': [],
                'inventions': [{'slot': oracle['slot'], 'kind': 'procedure', 'fact': dealt['entry'],
                                'basis': 'published: Three-Dragon Ante, a DM choice', 'public': True, 'scope': 'location',
                                'procedure': dealt['procedure'], 'change_reason': 'none'}]}
        return plan

    def perform(self, payload, performance_variant='current'):
        if 'new_procedures' not in payload:
            return super().perform(payload, performance_variant)
        self.performances.append(payload.copy())
        narration = ('The dealer fans dragon cards in five colors across the worn felt: Three-Dragon Ante, '
                     'three to a hand, the stakes climbing before the reveal.')
        return {'segments': [
            {'speaker': 'Kit', 'text': 'A real game, then. Good.', 'reacts_to': 'Three-Dragon Ante'},
            {'speaker': 'Narrator', 'text': narration},
            {'speaker': 'Dealer', 'text': DEALER_EXCHANGES[2][1]}]}


class GameDetailTests(unittest.TestCase):
    """Fix 2 through the general mechanism: the oracle deals, the decision picks, the
    ledger keeps it, and the game it names is a procedure the runtime runs."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.model = GameModel()
        self.agent = KitAgent(self.runtime, self.model, Room6CAdjudicator(
            perception=2, insight=1, sleight_of_hand=3, roll=lambda: 20))

    def test_the_decision_sees_the_deal_and_the_performer_never_does(self):
        self.agent.turn(GAME_ASK, 'game')
        oracle = self.model.plans[-1]['detail_oracle']
        self.assertEqual((oracle['slot'], oracle['status']), (GAME_SLOT, 'open'))
        self.assertEqual({card['draw_id'].split('.', 1)[1] for card in oracle['deal']},
                         {'three_dragon_ante', 'holdem_graves', 'blackjack_coffins', 'last_widow'})
        self.assertNotIn('roots', json.dumps(oracle), 'the decision sees a lean view of the deal')
        performed = json.dumps(self.model.performances[-1])
        self.assertNotIn('detail_oracle', performed)
        self.assertNotIn('holdem_graves', performed)
        self.assertEqual(self.model.performances[-1]['new_details'][0]['slot'], GAME_SLOT)

    def test_the_game_is_canon_and_its_procedure_starts(self):
        self.agent.turn(GAME_ASK, 'game')
        state = self.runtime.load()[1]
        entry = state['canon'][GAME_SLOT]
        self.assertEqual((entry['procedure'], entry['public'], entry['scope']),
                         ('three_dragon_ante', True, 'location'))
        self.assertTrue(entry['roots'])
        self.assertIn('three_dragon_ante', state['procedures'])
        self.assertIn('three_dragon_ante', state['oracle']['used']['area_06c'])
        view = self.runtime.player_view()
        self.assertEqual(view['established_details'][0]['slot'], GAME_SLOT)
        self.assertIn('three_dragon_ante', view['table_procedures'])
        # Asking again reuses canon: no new deal.
        again = kit_agent.detail_oracle(self.runtime, state, 'So what game is this, again?', 'social')
        self.assertEqual(again['status'], 'canon_supplied')

    def test_card_actions_route_to_the_procedure_once_it_is_declared(self):
        adjudicator = Room6CAdjudicator(perception=2, insight=1, sleight_of_hand=3, roll=lambda: 20)
        revision, state = self.runtime.load()
        adjudicator.source = self.runtime.source()
        before = adjudicator.resolve('I buy in with 20 gold. Deal me in.', revision, state)
        self.assertNotEqual(before.kind, 'card_join', 'no game is running until one is declared')
        self.agent.turn(GAME_ASK, 'game')
        revision, state = self.runtime.load()
        adjudicator.source = self.runtime.source()
        resolution = adjudicator.resolve('I buy in with 20 gold. Deal me in.', revision, state)
        self.assertEqual(resolution.kind, 'card_join')
        self.assertIn('procedure_state', [event['type'] for event in resolution.events])

    def test_the_staged_bridge_carries_the_oracle_from_prepare_to_commit(self):
        bridge = kit_agent.KitChatBridge(self.runtime, self.agent.adjudicator)
        prepared = bridge.prepare(GAME_ASK, 'bridge-game')
        self.assertEqual(prepared['input']['detail_oracle']['slot'], GAME_SLOT)
        plan = self.model.plan(prepared['input'])
        bad = {**plan, 'detail': {**plan['detail'], 'choice': 'd9.nothing.dealt'}}
        with self.assertRaisesRegex(InvalidChange, 'Pick a dealt card'):
            bridge.decide('bridge-game', bad)
        performance = bridge.decide('bridge-game', plan)
        self.assertNotIn('detail_oracle', json.dumps(performance['input']))
        bridge.finish('bridge-game', self.model.perform(performance['input']))
        self.assertEqual(self.runtime.load()[1]['canon'][GAME_SLOT]['procedure'], 'three_dragon_ante')

    def test_a_price_question_gets_the_source_toll(self):
        state = self.runtime.load()[1]
        oracle = kit_agent.detail_oracle(self.runtime, state, 'How much for passage through the door?', 'social')
        self.assertEqual((oracle['status'], oracle['price']['status'], oracle['price']['amounts']),
                         ('priced', 'source', [10]))
        self.assertEqual(oracle['slot'], 'area_06c/price/passage_toll')


class CardTableTests(unittest.TestCase):
    """The marked deck is playable: the dealer cheats by rule, the player can catch it,
    counter it, or accuse, and every coin is persisted in procedure state."""

    config = json.loads(FIXTURE.read_text())['procedures']['three_dragon_ante']

    def table(self, **modifiers):
        return kit_cards.CardTable('three_dragon_ante', self.config,
                                   {'perception': modifiers.get('perception', 0),
                                    'insight': modifiers.get('insight', 0),
                                    'sleight_of_hand': modifiers.get('sleight_of_hand', 0)}, 'seed-1')

    def play(self, table, kind, action, state, revision=1):
        return table.resolve(kind, action, revision, state)

    def test_buy_in_needs_a_stated_purse_and_covers_the_ante(self):
        state = kit_cards.initial_state(self.config)
        with self.assertRaises(kit_cards.NeedsRuling):
            self.play(self.table(), 'card_join', 'I sit in.', state)
        text, state, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold.', state)
        self.assertEqual(state['public']['player']['gp'], 20)
        self.assertIn('ante 2 gp', text)

    def test_a_deal_takes_the_ante_and_keeps_the_private_half_private(self):
        state = kit_cards.initial_state(self.config)
        _, state, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold and deal me in.', state)
        hand = state['public']['hand']
        self.assertEqual(len(hand['your_cards']), kit_cards.HAND_SIZE)
        self.assertEqual(state['public']['player']['gp'], 18)
        self.assertNotIn('hands', state['public']['hand'])
        dealt = state['private']['hands']['1']['hands']
        self.assertEqual(set(dealt), {'player', 'bandit_a', 'bandit_b', 'doppelganger', 'uktarl'})
        for card_ in dealt['uktarl']:
            self.assertNotIn(kit_cards.card_name(card_), hand['your_cards'])

    def test_the_player_may_supply_their_own_roll(self):
        self.assertEqual(kit_cards.supplied_roll('I watch his hands. I rolled 14 + 3 = 17.'), (14, 3))
        self.assertEqual(kit_cards.supplied_roll('I watch his hands. Rolled a 15.'), (15, None))

    def cheating_seed(self):
        for number in range(200):
            seed = f'seed-{number}'
            table = kit_cards.CardTable('three_dragon_ante', self.config,
                                        {'perception': 0, 'insight': 0, 'sleight_of_hand': 0}, seed)
            _, state, _ = table.resolve('card_join', 'I buy in with 20 gold and deal me in.', 1,
                                        kit_cards.initial_state(self.config))
            if state['private']['hands']['1']['cheated']:
                return seed
        self.fail('no cheating deal in 200 seeds')

    @staticmethod
    def gold(state):
        public = state['public']
        return (sum(public['stacks'].values()) + (public['player'] or {}).get('gp', 0) +
                ((public['hand'] or {}).get('pot') or 0))

    def test_watching_the_deal_can_catch_the_marked_deck_and_proof_voids_the_hand(self):
        seed = self.cheating_seed()
        table = kit_cards.CardTable('three_dragon_ante', self.config,
                                    {'perception': 5, 'insight': 0, 'sleight_of_hand': 0}, seed)
        state = kit_cards.initial_state(self.config)
        _, state, _ = table.resolve('card_join', 'I buy in with 20 gold.', 1, state)
        total = self.gold(state)
        state['public']['player']['watch_next_deal'] = True
        text, state, reveals = table.resolve('card_join', 'Deal me in. I rolled 20 + 5 = 25.', 2, state)
        self.assertEqual(self.gold(state), total, 'the ante moves coins, it never makes them')
        self.assertTrue(state['private']['hands']['1']['cheated'])
        self.assertEqual(reveals, ['marked_deck'])
        self.assertTrue(state['public']['hand']['cheat_seen'])
        self.assertIn(self.config['cheat']['caught_text'], text)
        text, state, _ = table.resolve('card_accuse', 'I accuse him of dealing seconds!', 3, state)
        self.assertEqual(state['public']['player']['gp'], 20, 'every stake goes back to whoever paid it')
        self.assertEqual(self.gold(state), total)
        self.assertIn('does not confess', text)

    def test_an_accusation_without_proof_stops_the_game_and_refunds_nothing(self):
        state = kit_cards.initial_state(self.config)
        _, state, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold and deal me in.', state)
        text, state, _ = self.play(self.table(), 'card_accuse', 'You are cheating!', state, revision=2)
        self.assertEqual(state['public']['player']['gp'], 18)
        self.assertEqual(state['public']['table_mood'], 'tense: accused without proof')
        self.assertIn('Nothing on the table proves it', text)

    def test_seats_that_checked_before_a_raise_call_it_or_fold(self):
        """QA PR #15: a seat acting before the raiser stayed in the hand for the ante alone."""
        checked = 0
        for number in range(200):
            table = kit_cards.CardTable('three_dragon_ante', self.config,
                                        {'perception': 0, 'insight': 0, 'sleight_of_hand': 0}, f'raise-{number}')
            _, state, _ = table.resolve('card_join', 'I buy in with 20 gold and deal me in.', 1,
                                        kit_cards.initial_state(self.config))
            hand = state['public']['hand']
            if not hand['raised_by']:
                continue
            for seat in hand['in_hand']:
                self.assertEqual(hand['paid'][seat], state['public']['ante'] + state['public']['raise'])
            checked += 1
        self.assertGreater(checked, 0)

    def test_a_proven_accusation_keeps_the_remainder_carried_from_the_last_hand(self):
        """QA PR #15: voiding the hand zeroed the pot, destroying a split remainder."""
        for number in range(3000):
            table = kit_cards.CardTable('three_dragon_ante', self.config,
                                        {'perception': 5, 'insight': 0, 'sleight_of_hand': 0}, f'carry-{number}')
            _, state, _ = table.resolve('card_join', 'I buy in with 20 gold and deal me in.', 1,
                                        kit_cards.initial_state(self.config))
            _, state, _ = table.resolve('card_bet', 'I call.', 2, state)
            if not state['public']['hand']['pot']:
                continue
            state['public']['player']['watch_next_deal'] = True
            _, state, _ = table.resolve('card_join', 'Deal me in. I rolled 20 + 5 = 25.', 3, state)
            if not state['public']['hand']['cheat_seen']:
                continue
            total = self.gold(state)
            _, state, _ = table.resolve('card_accuse', 'You are cheating!', 4, state)
            self.assertEqual(self.gold(state), total)
            return
        self.fail('no carried remainder with a caught cheat in 3000 seeds')

    def test_betting_words_are_ordinary_words_without_a_live_hand(self):
        state = kit_cards.initial_state(self.config)
        _, state, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold.', state)
        self.assertIsNone(kit_cards.card_intent('What do they call this game?', state))
        _, state, _ = self.play(self.table(), 'card_join', 'Deal me in.', state, revision=2)
        _, state, _ = self.play(self.table(), 'card_bet', 'I call.', state, revision=3)
        self.assertIsNone(kit_cards.card_intent('I call.', state), 'no bet on a finished hand')

    def test_leaving_mid_hand_folds_it_so_the_table_can_deal_again(self):
        """QA PR #15: cashing out mid-hand left the hand in betting forever."""
        state = kit_cards.initial_state(self.config)
        _, state, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold and deal me in.', state)
        total = self.gold(state)
        text, state, _ = self.play(self.table(), 'card_leave', 'I cash out.', state, revision=2)
        self.assertEqual(state['public']['hand']['phase'], 'done')
        self.assertIn('You fold.', text)
        self.assertEqual(self.gold(state) + 18, total, 'your 18 gp left with you; the rest stayed')
        _, state, _ = self.play(self.table(), 'card_join', 'I buy in with 10 gold and deal me in.', state,
                                revision=3)
        self.assertEqual(state['public']['hand']['phase'], 'betting')

    def test_the_public_table_names_seats_only_by_their_labels(self):
        """QA PR #15: public stack keys were actor ids ("doppelganger"), and the public
        dm_choice named the marked deck, which also switched off the literal leak check."""
        state = kit_cards.initial_state(self.config)
        _, state, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold and deal me in.', state)
        public = json.dumps(kit_cards.public_view(self.config, state['public'])).casefold()
        for secret in ('doppelganger', 'uktarl', 'bandit', 'marked'):
            self.assertNotIn(secret, public)
        self.assertIn('fourth player', public)

    def test_combat_and_stealth_keep_their_rulings_at_the_card_table(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        source = json.loads(FIXTURE.read_text())
        runtime.initialize(source, 'area_06c')
        state = runtime.load()[1]
        table = kit_cards.initial_state(self.config)
        _, table, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold and deal me in.', table)
        state['procedures'] = {'three_dragon_ante': table}
        adjudicator = Room6CAdjudicator(perception=0, insight=0, sleight_of_hand=0, source=source)
        with self.assertRaisesRegex(kit_agent.PendingRuling, 'Combat'):
            adjudicator.resolve('I raise my crossbow and shoot the dealer.', 1, state)
        with self.assertRaisesRegex(kit_agent.PendingRuling, 'Stealth'):
            adjudicator.resolve('I sneak out while they check their hands.', 1, state)
        self.assertEqual(adjudicator.resolve('I raise.', 1, state).kind, 'card_bet')
        view = json.dumps(Runtime._player_view(source, state)).casefold()
        self.assertNotIn('doppelganger', view)

    def test_the_card_intents_need_a_declared_game(self):
        self.assertIsNone(kit_cards.card_intent('I buy in with 20 gold.', None))
        state = kit_cards.initial_state(self.config)
        self.assertEqual(kit_cards.card_intent('I buy in with 20 gold.', state), 'card_join')

    def test_the_config_is_valid_and_the_cheat_reveals_the_marked_deck(self):
        kit_cards.check_config(self.config)
        self.assertEqual(self.config['cheat']['reveals_fact'], 'marked_deck')
        self.assertIn('Texas hold', self.config['dm_choice'])


if __name__ == '__main__':
    unittest.main()
