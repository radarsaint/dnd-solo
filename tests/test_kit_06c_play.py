"""Playtest 03 fixes in area 6c (tests/playtests/2026-09-29-area-06c-voice-spec-nik.md):
Kit's asides answer what happened; the router hears an answer to the dealer as speech;
the detail oracle and canon ledger answer "What game is it?"; and the card game is a
procedure the runtime runs, marked deck and all."""
import copy
import json
import tempfile
import unittest
from unittest import mock
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


def tda_source():
    """The 6c source with Three-Dragon Ante offered again, for the tests of that engine.
    Table call 1 retired it at 6c (offered: false); the engine itself is still general."""
    source = json.loads(FIXTURE.read_text())
    source['procedures']['three_dragon_ante'].pop('offered', None)
    def walk(node):
        if isinstance(node, dict):
            if node.get('id') == 'three_dragon_ante' and 'procedure' in node:
                node['procedure'] = 'three_dragon_ante'
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(source)
    return source


class GameModel(RecordingModel):
    """Answers "What game is it?" by the oracle: picks the twenty-one card (table call 1:
    a simple real game) and declares its procedure, and performs that answer."""

    pick = 'blackjack_coffins'

    def plan(self, payload):
        plan = super().plan(payload)
        oracle = payload.get('detail_oracle')
        if oracle and oracle['status'] == 'open' and oracle['slot'] == GAME_SLOT:
            # The decision's lean view: draw_id, entry, handle, procedure (no roots or basis).
            dealt = next(card for card in oracle['deal'] if card['draw_id'].endswith('.' + self.pick))
            plan['detail'] = {
                'request': payload['player_action'], 'slot': oracle['slot'], 'choice': dealt['draw_id'],
                'candidates': [], 'typical': -1, 'chosen': -1,
                'owner': 'uktarl: a game where knowing the cards pays',
                'handle': 'sit in for a hand, settle a round with one check, or watch the deal',
                'because': 'true because the four play cards at this table with coins in front of them',
                'price_quote': [],
                'inventions': [{'slot': oracle['slot'], 'kind': 'procedure', 'fact': dealt['entry'],
                                'basis': 'real: blackjack, a DM choice', 'public': True, 'scope': 'location',
                                'procedure': dealt['procedure'], 'change_reason': 'none'}]}
        return plan

    def perform(self, payload, performance_variant='current'):
        if 'new_procedures' not in payload:
            return super().perform(payload, performance_variant)
        self.performances.append(payload.copy())
        narration = ('The dealer squares a worn deck on the felt: Twenty-One Coffins, plain blackjack, '
                     'closest to twenty-one without going over takes the pot.')
        return {'segments': [
            {'speaker': 'Kit', 'text': 'A real game, then. Good.', 'reacts_to': 'Twenty-One Coffins'},
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
                         ('twenty_one', True, 'location'))
        self.assertTrue(entry['roots'])
        self.assertIn('twenty_one', state['procedures'])
        self.assertIn('blackjack_coffins', state['oracle']['used']['area_06c'])
        view = self.runtime.player_view()
        self.assertEqual(view['established_details'][0]['slot'], GAME_SLOT)
        self.assertIn('twenty_one', view['table_procedures'])
        # Asking again reuses canon: no new deal.
        again = kit_agent.detail_oracle(self.runtime, state, 'So what game is this, again?', 'social')
        self.assertEqual(again['status'], 'canon_supplied')

    def test_card_actions_route_to_the_procedure_once_it_is_declared(self):
        adjudicator = Room6CAdjudicator(perception=2, insight=1, sleight_of_hand=3, roll=lambda: 20)
        revision, state = self.runtime.load()
        adjudicator.source = self.runtime.source()
        before = adjudicator.resolve('I bet 10 gold. Deal me in.', revision, state)
        # Table call 1: asking to play declares the area's offered game and puts the choice
        # (one check or play it out) to the player, rather than stalling until it is named.
        self.assertEqual(before.kind, 'card_offer')
        self.agent.turn(GAME_ASK, 'game')
        revision, state = self.runtime.load()
        adjudicator.source = self.runtime.source()
        resolution = adjudicator.resolve('I bet 10 gold. Deal me in.', revision, state)
        self.assertEqual(resolution.kind, 'card_offer')
        self.assertIn('procedure_state', [event['type'] for event in resolution.events])

    def test_a_long_card_event_commits_through_the_decision(self):
        # Fix-pass host play: a round of play reported more than 500 characters, and the
        # decision (which must restate the event) hit the social bound. The deal is seeded,
        # so this seed and sequence reproduce a 540-character round.
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'seeded.sqlite')
        self.addCleanup(self.runtime.close)
        with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{6:032x}'):
            self.runtime.initialize(tda_source(), 'area_06c')
        model = GameModel()
        model.pick = 'three_dragon_ante'
        self.agent = KitAgent(self.runtime, model, Room6CAdjudicator(
            perception=2, insight=1, sleight_of_hand=3, roll=lambda: 20))
        actions = [GAME_ASK, 'I buy in with 20 gold. Deal me in.', 'I ante my strongest card.',
                   'I play my strongest card.', 'I play my strongest card.', 'I play my strongest card.']
        for index, action in enumerate(actions):
            self.agent.turn(action, action[:8] + str(index))
        events = [turn['public_event'] for turn in self.runtime.recent_kit_turns()]
        self.assertEqual(len(events), len(actions))
        self.assertGreater(max(map(len, events)), kit_agent.EVENT_MAX_CHARS)
        self.assertTrue(all(len(event) <= kit_agent.CARD_EVENT_MAX_CHARS for event in events))

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
        self.assertEqual(self.runtime.load()[1]['canon'][GAME_SLOT]['procedure'], 'twenty_one')

    def test_a_price_question_gets_the_source_toll(self):
        state = self.runtime.load()[1]
        oracle = kit_agent.detail_oracle(self.runtime, state, 'How much for passage through the door?', 'social')
        self.assertEqual((oracle['status'], oracle['price']['status'], oracle['price']['amounts']),
                         ('priced', 'source', [10]))
        self.assertEqual(oracle['slot'], 'area_06c/price/passage_toll')


class CardTableTests(unittest.TestCase):
    """The marked deck is playable in real Three-Dragon Ante structure: card antes set
    the stakes, three rounds of flights, color powers, special flights. The dealer cheats
    by rule at the deal, the player can catch it, counter it, or accuse, and every coin
    is persisted in procedure state and conserved."""

    config = json.loads(FIXTURE.read_text())['procedures']['three_dragon_ante']
    MODS = {'perception': 2, 'insight': 1, 'sleight_of_hand': 3}

    def table(self, seed='seed'):
        return kit_cards.CardTable('three_dragon_ante', self.config, dict(self.MODS), seed)

    def play(self, table, kind, action, state, revision=1):
        return table.resolve(kind, action, revision, state)

    def seated(self, seed='seed', action='I buy in with 30 gold and deal me in.'):
        table = self.table(seed)
        _, state, reveals = table.resolve('card_join', action, 1, kit_cards.initial_state(self.config))
        return table, state, reveals

    def finish_gambit(self, table, state, revision=2):
        """Ante the weakest card, then play the strongest each turn until the showdown."""
        state = table.resolve('card_ante', 'I ante my strongest card.', revision, state)[1]
        while state['public']['gambit']['phase'] == 'play':
            revision += 1
            state = table.resolve('card_play', 'I play my strongest card.', revision, state)[1]
        return state, revision + 1

    def seed_where(self, cheated):
        for number in range(200):
            table, state, _ = self.seated(f'seed{number}')
            if state['private']['cheated'] == cheated:
                return f'seed{number}'
        self.fail('no seed found')

    def test_buy_in_needs_a_stated_purse(self):
        state = kit_cards.initial_state(self.config)
        with self.assertRaises(kit_cards.NeedsRuling):
            self.play(self.table(), 'card_join', 'I sit in.', state)
        text, state, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold.', state)
        self.assertIn('20 gp', text)
        self.assertIsNone(state['public']['gambit'], 'no deal until the player asks for one')

    def test_a_deal_gives_six_cards_and_keeps_the_private_half_private(self):
        _, state, _ = self.seated()
        gambit = state['public']['gambit']
        self.assertEqual((gambit['phase'], gambit['to_act']), ('ante', 'player'))
        self.assertEqual(len(state['public']['player']['hand']), kit_cards.HAND_SIZE)
        for seat in gambit['seats']:
            self.assertEqual(len(state['private']['hands'][seat]), kit_cards.HAND_SIZE)
        public = json.dumps(state['public'])
        self.assertNotIn('hands', public)
        self.assertNotIn('cheated', public)

    def test_supplied_rolls_are_parsed(self):
        self.assertEqual(kit_cards.supplied_roll('I watch his hands. I rolled 14 + 3 = 17.'), (14, 3))
        # A bare stated number is Avrae's total (kit_rolls): worked back with the bonus, never
        # added to it again. Only an explicit natural is the die alone.
        self.assertEqual(kit_cards.supplied_roll('I watch his hands. Rolled a 15.'), (15, 0))
        self.assertEqual(kit_cards.supplied_roll('I watch his hands. Rolled a 15.', 4), (11, 4))
        self.assertEqual(kit_cards.supplied_roll('I watch his hands. Natural 15.'), (15, None))

    def test_the_strongest_ante_card_sets_the_stakes_and_the_lead(self):
        """QA PR #15 item 7: real Three-Dragon Ante structure, not a three-card poker hand."""
        table, state, _ = self.seated()
        before = {seat: table._gp(state['public'], seat) for seat in state['public']['gambit']['seats']}
        text, state, _ = self.play(table, 'card_ante', 'I ante my strongest card.', state, revision=2)
        gambit = state['public']['gambit']
        antes = {seat: kit_cards._parse_name(name)[1] for seat, name in gambit['antes_revealed'].items()}
        top = max(antes.values())
        self.assertEqual(gambit['ante_amount'], top)
        self.assertIn(f'Stakes {top} gp each', text)
        self.assertEqual(gambit['plays'][0][0], [s for s in gambit['seats'] if antes[s] == top][0],
                         'the strongest ante leads the first round')
        for seat, gp in before.items():
            paid = gp - table._gp(state['public'], seat)
            # paid covers the ante (all in when short), give or take powers already triggered
            self.assertTrue(paid >= min(top, gp) - 3, (seat, paid, top))

    def test_three_rounds_of_flights_powers_and_the_strongest_flight_wins(self):
        for number in range(12):
            table, state, _ = self.seated(f'rounds{number}')
            state, _ = self.finish_gambit(table, state)
            public = state['public']
            gambit = public['gambit']
            self.assertEqual(gambit['phase'], 'done')
            active = [s for s in gambit['seats'] if s not in gambit['out']]
            for seat in active:
                self.assertEqual(len(gambit['flights'][seat]), kit_cards.ROUNDS)
            # A card triggers its power when it opens a round or is no stronger than the
            # card played just before it that round.
            previous = {}
            for seat, name, round_number, triggered in gambit['plays']:
                value = kit_cards._parse_name(name)[1]
                expected = round_number not in previous or value <= previous[round_number]
                self.assertEqual(triggered, expected, (name, round_number))
                previous[round_number] = value
            result = public['last_result']
            best = max(result['flights'].values())
            self.assertEqual(sorted(result['winners']),
                             sorted(label for label, total in result['flights'].items() if total == best))

    def test_gold_is_conserved_across_many_gambits(self):
        for number in range(25):
            table, state, _ = self.seated(f'gold{number}', 'I buy in with 40 gold and deal me in.')
            total = kit_cards.table_gold(state['public'])
            revision = 2
            for _ in range(5):
                if state['public']['player']['gp'] < 1:
                    break
                if state['public']['gambit']['phase'] == 'done':
                    state = table.resolve('card_join', 'Deal again.', revision, state)[1]
                    revision += 1
                state, revision = self.finish_gambit(table, state, revision)
                self.assertEqual(kit_cards.table_gold(state['public']), total)
                self.assertTrue(all(gp >= 0 for gp in state['public']['stacks'].values()))
            self.assertLessEqual(len(json.dumps(state)), 6000, 'fits the procedure state bound')

    def test_the_dealer_deals_seconds_from_the_marked_deck(self):
        table = self.table('marks')
        state = kit_cards.initial_state(self.config)
        state = table.resolve('card_join', 'I buy in with 30 gold.', 1, state)[1]
        deck = [[color, value] for color in kit_cards.COLORS for value in kit_cards.DECK[color]]
        kit_cards._rng('marks', 'deck').shuffle(deck)
        state = table.resolve('card_join', 'Deal me in.', 2, state)[1]
        dealer = self.config['cheat']['actor']
        honest = sorted(deck[4:len(deck):5][:6])  # every fifth card from his seat, with no cheating
        self.assertEqual(state['private']['cheated'], sorted(state['private']['hands'][dealer]) != honest)

    def test_watching_the_deal_can_catch_the_marked_deck_and_proof_voids_the_gambit(self):
        seed = self.seed_where(cheated=True)
        table = self.table(seed)
        state = kit_cards.initial_state(self.config)
        state = table.resolve('card_join', 'I buy in with 30 gold.', 1, state)[1]
        total = kit_cards.table_gold(state['public'])
        before = dict(state['public']['stacks'])
        text, state, reveals = table.resolve('card_watch', 'I watch the dealer\'s hands for cheating as he '
                                             'deals. I rolled 20 + 5 = 25.', 2, state)
        self.assertEqual(reveals, ['marked_deck'])
        self.assertTrue(state['public']['gambit']['cheat_seen'])
        # Table call 2: the numbers go to the ledger, never the table.
        self.assertNotIn('Perception 25', text)
        self.assertIn('Perception d20 20 + 5 = 25', ' '.join(table.trace))
        state = table.resolve('card_ante', 'I ante my strongest card.', 3, state)[1]
        self.assertNotEqual(state['public']['stacks'], before, 'the antes are in the stakes')
        text, state, _ = table.resolve('card_accuse', 'You dealt yourself the second card.', 4, state)
        self.assertIn('void', text)
        self.assertEqual(state['public']['stacks'], before)
        self.assertEqual(state['public']['player']['gp'], 30)
        self.assertEqual(kit_cards.table_gold(state['public']), total)
        self.assertEqual(state['public']['gambit']['phase'], 'done')

    def test_a_proven_accusation_keeps_gold_carried_from_the_last_gambit(self):
        seed = self.seed_where(cheated=True)
        table = self.table(seed)
        state = kit_cards.initial_state(self.config)
        state = table.resolve('card_join', 'I buy in with 30 gold.', 1, state)[1]
        state['public']['carried'] = 3  # an odd split left over from the gambit before
        state['public']['stacks'][self.config['cheat']['actor']] -= 3
        total = kit_cards.table_gold(state['public'])
        state = table.resolve('card_watch', 'I watch the deal closely. I rolled 20 + 5 = 25.', 2, state)[1]
        state = table.resolve('card_ante', 'I ante my strongest card.', 3, state)[1]
        state = table.resolve('card_accuse', 'I accuse him of dealing seconds.', 4, state)[1]
        self.assertEqual(state['public']['carried'], 3)
        self.assertEqual(kit_cards.table_gold(state['public']), total)

    def test_an_accusation_without_proof_stops_the_game_and_refunds_nothing(self):
        table, state, _ = self.seated()
        state = table.resolve('card_ante', 'I ante my strongest card.', 2, state)[1]
        gold = copy.deepcopy((state['public']['stacks'], state['public']['player']['gp']))
        text, state, _ = table.resolve('card_accuse', 'You\'re cheating!', 3, state)
        self.assertIn('Nothing on the table proves it', text)
        self.assertEqual((state['public']['stacks'], state['public']['player']['gp']), gold)
        self.assertEqual(state['public']['table_mood'], 'tense: accused without proof')

    def test_a_failed_swap_puts_the_player_out_and_the_table_plays_on(self):
        table, state, _ = self.seated()
        total = kit_cards.table_gold(state['public'])
        state = table.resolve('card_ante', 'I ante my strongest card.', 2, state)[1]
        text, state, _ = table.resolve('card_swap', 'I palm a card. I rolled 1 + 0 = 1.', 3, state)
        self.assertTrue(state['public']['player']['unwelcome'])
        self.assertEqual(state['public']['gambit']['phase'], 'done', 'the others played it out')
        self.assertEqual(kit_cards.table_gold(state['public']), total)
        with self.assertRaises(kit_cards.NeedsRuling):
            table.resolve('card_join', 'Deal me in.', 4, state)

    def test_a_good_swap_trades_the_weakest_card(self):
        table, state, _ = self.seated()
        weakest = min(state['private']['hands']['player'], key=lambda card: card[1])
        text, state, _ = table.resolve('card_swap', 'I slip a card up my sleeve. I rolled 18 + 3 = 21.', 2, state)
        self.assertIn(kit_cards.card_name(weakest), text)
        self.assertEqual(len(state['public']['player']['hand']), kit_cards.HAND_SIZE)

    def test_leaving_mid_gambit_forfeits_it_so_the_table_can_deal_again(self):
        table, state, _ = self.seated()
        total = kit_cards.table_gold(state['public'])
        state = table.resolve('card_ante', 'I ante my strongest card.', 2, state)[1]
        purse = state['public']['player']['gp']
        text, state, _ = table.resolve('card_leave', 'I cash out.', 3, state)
        self.assertIn('You drop out of the gambit', text)
        self.assertEqual(state['public']['gambit']['phase'], 'done')
        self.assertIsNone(state['public']['player'])
        self.assertEqual(kit_cards.table_gold(state['public']) + purse, total)

    def test_card_names_parse_from_the_players_words(self):
        hand = [('red', 8), ('gold', 13), ('red', 2), ('white', 4)]
        self.assertEqual(kit_cards.parse_card('I ante the red 8.', hand), ('red', 8))
        self.assertEqual(kit_cards.parse_card('I play red eight', hand), ('red', 8))
        self.assertEqual(kit_cards.parse_card('the gold dragon, please', hand), ('gold', 13))
        self.assertEqual(kit_cards.parse_card('I lay down my weakest card', hand), ('red', 2))
        self.assertIsNone(kit_cards.parse_card('I play a red one', hand), 'two reds and no red 1')
        # Table call 1: no "Name the card" stall. A bare ante antes the weakest card.
        table, state, _ = self.seated()
        hand = state['private']['hands']['player']
        weakest = min(hand, key=lambda card: card[1])
        text, state, _ = table.resolve('card_ante', 'I ante.', 2, state)
        self.assertNotIn('Name the card', text)
        self.assertNotIn(weakest, state['private']['hands']['player'])

    def test_card_move_matching(self):
        """QA PR #15 item 3: watching is a watch, a claim is an accusation, a question
        that is not a card move is speech."""
        _, state, _ = self.seated()
        intent = kit_cards.card_intent
        self.assertEqual(intent('I watch the dealer for cheating.', state), 'card_watch')
        self.assertEqual(intent('I keep an eye on his hands for any cheating as he deals.', state), 'card_watch')
        self.assertEqual(intent('You dealt yourself the second card.', state), 'card_accuse')
        self.assertEqual(intent('He\'s dealing seconds!', state), 'card_accuse')
        self.assertEqual(intent('I accuse the dealer.', state), 'card_accuse')
        self.assertIsNone(intent('Tell me about the ring.', state))
        self.assertIsNone(intent('Tell me about the ring', state))
        self.assertIsNone(intent('Are you cheating?', state))
        self.assertIsNone(intent('What does the blue power do?', state))
        self.assertEqual(intent('I ante my strongest card.', state), 'card_ante')
        self.assertEqual(intent(f"The {state['public']['player']['hand'][0]}.", state), 'card_ante')
        self.assertEqual(intent('I read his face for a bluff.', state), 'card_read')

    def test_a_question_mid_gambit_routes_to_speech(self):
        source = json.loads(FIXTURE.read_text())
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(source, 'area_06c')
        state = runtime.load()[1]
        _, table, _ = self.seated()
        state['procedures'] = {'three_dragon_ante': table}
        adjudicator = Room6CAdjudicator(perception=0, insight=0, sleight_of_hand=0, source=source)
        self.assertEqual(adjudicator.resolve('Tell me about the ring', 1, state).kind, 'social')
        self.assertEqual(adjudicator.resolve('I watch the dealer for cheating.', 1, state).kind, 'card_watch')
        self.assertEqual(adjudicator.resolve('You dealt yourself the second card.', 1, state).kind,
                         'card_accuse')

    def test_betting_words_are_ordinary_words_without_a_live_gambit(self):
        state = kit_cards.initial_state(self.config)
        _, state, _ = self.play(self.table(), 'card_join', 'I buy in with 20 gold.', state)
        self.assertIsNone(kit_cards.card_intent('What do they call this game?', state))
        self.assertIsNone(kit_cards.card_intent('I play it cool.', state), 'no card move without a gambit')

    def test_the_public_table_names_seats_only_by_their_labels(self):
        """QA PR #15: public stack keys were actor ids ("doppelganger"), and the public
        dm_choice named the marked deck, which also switched off the literal leak check."""
        table, state, _ = self.seated()
        state = table.resolve('card_ante', 'I ante my strongest card.', 2, state)[1]
        public = json.dumps(kit_cards.public_view(self.config, state['public'])).casefold()
        for secret in ('doppelganger', 'uktarl', 'bandit', 'marked'):
            self.assertNotIn(secret, public)
        self.assertIn('fourth player', public)
        self.assertIn('strongest ante card sets the stakes', public)

    def test_the_rules_summary_is_our_own_words(self):
        """No published rulebook sentence is copied: no 8-word run from the rulebook
        phrasing the implementation was checked against appears in the rules or powers."""
        published = ('if the number on your card is equal to or lower than that of the card just '
                     'played by the person on your right or if you play first in a round you get to use '
                     'your card\'s special power otherwise ignore the power each player chooses one card '
                     'in his or her hand and puts it face down in the center of the table')
        from runtime import kit_guards
        ours = ' '.join(kit_cards.RULES) + ' ' + ' '.join(kit_cards.POWERS.values())
        self.assertFalse(kit_guards.ngrams(kit_guards.tokens(ours), 8) &
                         kit_guards.ngrams(kit_guards.tokens(published), 8))

    def test_combat_and_stealth_keep_their_rulings_at_the_card_table(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        source = json.loads(FIXTURE.read_text())
        runtime.initialize(source, 'area_06c')
        state = runtime.load()[1]
        _, table, _ = self.seated()
        state['procedures'] = {'three_dragon_ante': table}
        adjudicator = Room6CAdjudicator(perception=0, insight=0, sleight_of_hand=0, source=source)
        # A shot with no Avrae roll waits on the roll (no turn), and is never a card raise.
        with self.assertRaisesRegex(kit_agent.PendingRuling, 'Roll the attack for your crossbow in Avrae'):
            adjudicator.resolve('I raise my crossbow and shoot the dealer.', 1, state)
        with self.assertRaisesRegex(kit_agent.PendingRuling, 'Stealth'):
            adjudicator.resolve('I sneak out while they check their hands.', 1, state)
        self.assertEqual(adjudicator.resolve('I ante my strongest card.', 1, state).kind, 'card_ante')
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
