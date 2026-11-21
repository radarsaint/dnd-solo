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

from runtime import kit_agent, kit_voice
from runtime.kit_agent import KitAgent, RoomAdjudicator, npc_addressed_player, room_intent

# The 6c room's own words (its tub, its south door) come from its file (ROOM_LOADER.md).
from runtime import kit_agent as _kit_agent
from runtime.kit_rooms import read_room as _read_room
_SIXC_WORDS = _kit_agent.room_words(_read_room('tests/fixtures/level_01_area_06c.json'),
                                    {'area': 'area_06c', 'known_exits': ['south_door']})


def room_intent(action, addressed=False):
    return _kit_agent.room_intent(action, addressed, _SIXC_WORDS)

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
        self.assertEqual(room_intent('I tip the stone tub over and use it as cover.', addressed=True), 'move_feature')
        self.assertEqual(room_intent('I attack Uktarl in the middle of the game.', addressed=True), 'combat')

    def test_the_whole_turn_commits_through_the_agent(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        agent = KitAgent(runtime, RecordingModel(), RoomAdjudicator(perception=0, insight=0, roll=lambda: 20))
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
        self.agent = KitAgent(self.runtime, self.model, RoomAdjudicator(
            perception=2, insight=1, sleight_of_hand=3, roll=lambda: 20))

    def test_a_price_question_gets_the_source_toll(self):
        state = self.runtime.load()[1]
        oracle = kit_agent.detail_oracle(self.runtime, state, 'How much for passage through the door?', 'social')
        self.assertEqual((oracle['status'], oracle['price']['status'], oracle['price']['amounts']),
                         ('priced', 'source', [10]))
        self.assertEqual(oracle['slot'], 'area_06c/price/passage_toll')


if __name__ == '__main__':
    unittest.main()
