"""Coherence, declared inventions, and the addressed-reply router (2026-09-29 Nik playtest,
tests/playtests/2026-09-29-area-06c-voice-spec-nik.md).

Brendon's rule: "Nonsensical is not entertaining. That's a fiction we need to burn."
The host judges coherence; these tests cover the structure that makes it answerable
(reacts_to anchors, the self-check) and the lexical guards that catch the plain cases.
"""
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_coherence as kc
from runtime.kit_agent import (KitChatBridge, PendingRuling, Room6CAdjudicator, player_was_addressed,
                               room_intent)
from runtime.state_context import InvalidChange, Runtime

from test_kit_agent import FIXTURE, RecordingModel, with_check

NIK_LINE = ('I was hoping to find. I dunno. An exceedingly hot elvin maiden whose all sex crazed and '
            'ready to heap treasure at me.')

OPENING = [
    {'speaker': 'Narrator', 'text': (
        'The south door opens beside a card table, and the dealer stops a card halfway between his '
        'fingers and the worn wood. Three other faces wait for it to land. One player watches the '
        'doorway; another leans over a small pile of coins. The fourth taps the table for the deal to '
        'continue. On the north wall, tiny dwarves crowd a carved mountain.')},
    {'speaker': 'Fourth player', 'text': 'Your deal. Finish it.'},
    {'speaker': 'Dealer', 'text': (
        "A guest at the turn of a card. How extravagantly lucky for us. My companion would finish the "
        "hand; I would improve it. If you've coin, I'll make space. If you've a question, ask it before "
        "I deal. But do tell me, traveler, what were you hoping to find when you opened that door?")},
]
HELLO = {'speaker': 'Kit', 'text': "He could have said hello. Apparently there's no money in it.",
         'reacts_to': 'A guest at the turn of a card'}


def kit(text, anchor):
    return {'speaker': 'Kit', 'text': text, 'reacts_to': anchor}


class AnchorAndClaimTests(unittest.TestCase):
    def test_the_hello_aside_after_a_full_welcome_is_a_contradiction(self):
        with self.assertRaisesRegex(InvalidChange, 'Contradiction.*greeted'):
            kc.check_claims_against_lines(OPENING + [HELLO], 'none')
        # The same quip is fine when nobody spoke to the visitor.
        kc.check_claims_against_lines([OPENING[0], HELLO], 'none')

    def test_claims_of_silence_or_not_asking_are_checked_against_the_lines(self):
        with self.assertRaisesRegex(InvalidChange, 'did not ask'):
            kc.check_claims_against_lines(OPENING + [kit("He didn't even ask your name.", 'x y')], 'none')
        with self.assertRaisesRegex(InvalidChange, 'silent'):
            kc.check_claims_against_lines(OPENING + [kit('Not a single word from him, as usual.', 'x y')], 'none')

    def test_the_previous_turn_counts_as_what_was_said(self):
        history = [{'player_input': 'none', 'spoken': 'Dealer: Welcome, stranger. Sit.'}]
        with self.assertRaisesRegex(InvalidChange, 'Contradiction'):
            kc.check_claims_against_lines([HELLO], NIK_LINE, history)

    def test_every_kit_segment_quotes_a_real_anchor(self):
        with self.assertRaisesRegex(InvalidChange, 'needs reacts_to'):
            kc.check_kit_anchors(OPENING + [{'speaker': 'Kit', 'text': 'Well then.'}], 'none', 'x')
        with self.assertRaisesRegex(InvalidChange, 'needs reacts_to'):
            kc.check_kit_anchors(OPENING + [kit('Well then.', 'none')], 'none', 'x')
        with self.assertRaisesRegex(InvalidChange, 'does not quote anything'):
            kc.check_kit_anchors(OPENING + [kit('Well then.', 'he never greeted you')], 'none', 'x')
        # An aside may not anchor to a line that comes after it.
        with self.assertRaisesRegex(InvalidChange, 'does not quote anything'):
            kc.check_kit_anchors([kit('Well then.', 'Your deal. Finish it.')] + OPENING, 'none', 'x')
        kc.check_kit_anchors(OPENING + [kit('Improve it, he says, holding the deck.', 'I would improve it')],
                             'none', 'x')

    def test_other_speakers_carry_no_anchor(self):
        segments = [dict(OPENING[1], reacts_to='Your deal')]
        with self.assertRaisesRegex(InvalidChange, 'Kit segments only'):
            kc.check_kit_anchors(segments, 'none', 'x')

    def test_the_players_words_and_the_last_turn_are_anchors(self):
        kc.check_kit_anchors([kit('Ambitious.', 'exceedingly hot elvin maiden')], NIK_LINE, 'x')
        history = [{'player_input': 'none', 'spoken': 'Dealer: What were you hoping to find?'}]
        kc.check_kit_anchors([kit('A fair question.', 'hoping to find')], 'I shrug.', 'x', history)


class SelfCheckTests(unittest.TestCase):
    def test_answers_are_required_and_a_found_contradiction_blocks_commit(self):
        with self.assertRaisesRegex(InvalidChange, 'host self-check'):
            kc.check_self_check(None, OPENING)
        with self.assertRaisesRegex(InvalidChange, 'found a contradiction'):
            kc.check_self_check({'contradiction': 'Kit says no hello after a welcome',
                                 'aside_follows': 'no aside'}, OPENING)
        with self.assertRaisesRegex(InvalidChange, 'aside_follows'):
            kc.check_self_check({'contradiction': 'none', 'aside_follows': 'yes'}, OPENING + [HELLO])
        kc.check_self_check({'contradiction': 'none', 'aside_follows': 'no aside'}, OPENING)


class BridgeCoherenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.model = RecordingModel()
        self.bridge = KitChatBridge(self.runtime, Room6CAdjudicator())

    def open_room(self):
        staged = self.bridge.prepare(turn_id='open', opening=True, one_pass=True)
        plan = self.model.plan(staged['input']['private'])
        plan.update(move='world_description', table_presence='brief')
        return staged, plan

    def test_prepare_and_decide_hand_the_host_the_self_check(self):
        staged, _ = self.open_room()
        self.assertEqual(staged['host_self_check'], kc.HOST_SELF_CHECK)
        self.assertIn('Nonsensical is not entertaining', staged['host_self_check']['rule'])
        staged = self.bridge.prepare("Hello there, what's the game?", 'staged')
        decided = self.bridge.decide('staged', self.model.plan(staged['input']))
        self.assertEqual(decided['host_self_check'], kc.HOST_SELF_CHECK)

    def test_the_nik_opening_with_the_hello_aside_is_rejected_and_the_clean_one_commits(self):
        _, plan = self.open_room()
        with self.assertRaisesRegex(InvalidChange, 'Contradiction'):
            self.bridge.complete('open', {'decision': plan, 'performance': with_check(
                {'segments': OPENING + [HELLO]})})
        with self.assertRaisesRegex(InvalidChange, 'self-check'):
            self.bridge.complete('open', {'decision': plan, 'performance': {'segments': OPENING}})
        result = self.bridge.complete('open', {'decision': plan, 'performance': with_check({'segments': OPENING})})
        self.assertEqual(result['revision'], 1)

    def test_a_spoken_invention_is_saved_and_handed_back_as_canon(self):
        _, plan = self.open_room()
        plan['inventions'] = [{'kind': 'name', 'detail': 'The dealer calls his deck Old Margery.'}]
        speech = with_check({'segments': OPENING[:2] + [dict(OPENING[2], text=OPENING[2]['text'] +
                                                             ' Old Margery here never lies.')]})
        self.bridge.complete('open', {'decision': plan, 'performance': speech})
        _, state = self.runtime.load()
        self.assertEqual(state['dm_inventions'][0]['detail'], 'The dealer calls his deck Old Margery.')
        self.assertEqual(state['dm_inventions'][0]['kind'], 'name')
        staged = self.bridge.prepare(NIK_LINE, 'next', one_pass=True)
        self.assertIn('Old Margery', json.dumps(staged['input']['public']['established_inventions']))
        self.assertIn('Old Margery', json.dumps(staged['input']['private']['dm_inventions']))

    def test_an_unspoken_invention_is_not_saved(self):
        _, plan = self.open_room()
        plan['inventions'] = [{'kind': 'history', 'detail': 'The tub was carved by a drowned mason.'}]
        self.bridge.complete('open', {'decision': plan, 'performance': with_check({'segments': OPENING})})
        _, state = self.runtime.load()
        self.assertEqual(state.get('dm_inventions') or [], [])


class InventionTests(unittest.TestCase):
    NIK_BRIEF = {'objective': 'Press the visitor to sit and play.',
                 'tactic': 'The dealer names the simple stakes of the current hand.',
                 'visible_cue': 'none', 'player_opening': 'none', 'kit_focus': 'none', 'npc_notice': 'none'}

    def test_the_playtest_brief_asking_for_unsupplied_stakes_is_flagged(self):
        with self.assertRaisesRegex(InvalidChange, 'stakes'):
            kc.check_brief_supported(self.NIK_BRIEF, [], (), 'Gravedigger', 'Whats going on here?')
        with self.assertRaisesRegex(InvalidChange, 'declared in inventions'):
            kc.check_brief_supported(self.NIK_BRIEF, [], (), None, 'none')

    def test_a_brief_that_uses_the_table_game_or_a_declared_invention_passes(self):
        kc.check_brief_supported(dict(self.NIK_BRIEF, tactic='The dealer names the Gravedigger stakes.'),
                                 [], (), 'Gravedigger', 'none')
        kc.check_brief_supported(self.NIK_BRIEF, [{'kind': 'stake', 'detail': 'Simple stakes: a toast per hand.'}],
                                 (), None, 'none')
        kc.check_brief_supported(self.NIK_BRIEF, [], (), 'Gravedigger', 'What are the stakes?')

    def test_card_game_stakes_cannot_be_invented_beside_the_table_game(self):
        with self.assertRaisesRegex(InvalidChange, 'Gravedigger'):
            kc.check_inventions([{'kind': 'rule', 'detail': 'High card wins, matching coin.'}], 'Gravedigger')
        kc.check_inventions([{'kind': 'name', 'detail': 'The dealer calls himself Sir Ukt.'}], 'Gravedigger')
        with self.assertRaisesRegex(InvalidChange, 'at most'):
            kc.check_inventions([{'kind': 'name', 'detail': 'x'}] * 4)

    def test_other_games_are_only_named_when_the_player_named_them(self):
        high = [{'speaker': 'Dealer', 'text': 'High card, matching coin. Simple as breathing.'}]
        with self.assertRaisesRegex(InvalidChange, 'high card'):
            kc.check_other_games(high, 'Whats going on here?', 'Gravedigger')
        kc.check_other_games(high, 'Can we play high card instead?', 'Gravedigger')

    def test_wager_amounts_come_from_the_procedure(self):
        segs = [{'speaker': 'Dealer', 'text': 'Ante is two gold. Bet ten gold if you dare.'}]
        kc.check_wager_amounts(segs, {2, 10}, 'none', 'Gravedigger')
        with self.assertRaisesRegex(InvalidChange, '10 gp wager'):
            kc.check_wager_amounts(segs, {2}, 'none', 'Gravedigger')
        kc.check_wager_amounts(segs, {2}, 'I bet ten gold.', 'Gravedigger')


class AddressedReplyRouterTests(unittest.TestCase):
    ASKED = {'player_input': 'none', 'spoken': (
        'Narrator: The dealer stops a card halfway.\n'
        'Dealer: But do tell me, traveler, what were you hoping to find when you opened that door?')}

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')

    def test_niks_exact_reply_to_the_dealers_question_is_social_speech(self):
        self.assertTrue(player_was_addressed(self.ASKED))
        self.assertEqual(room_intent(NIK_LINE), 'unsupported_action')  # the playtest failure, unaddressed
        self.assertEqual(room_intent(NIK_LINE, addressed=True), 'social')
        revision, state = self.runtime.load()
        resolution = Room6CAdjudicator().resolve(NIK_LINE, revision, state, addressed=True)
        self.assertEqual(resolution.kind, 'social')

    def test_the_bridge_routes_the_reply_after_the_opening_question(self):
        bridge = KitChatBridge(self.runtime, Room6CAdjudicator())
        model = RecordingModel()
        staged = bridge.prepare(turn_id='open', opening=True, one_pass=True)
        plan = model.plan(staged['input']['private'])
        plan.update(move='world_description', table_presence='quiet')
        bridge.complete('open', {'decision': plan, 'performance': with_check({'segments': OPENING})})
        staged = bridge.prepare(NIK_LINE, 'nik', one_pass=True)
        self.assertEqual(staged['input']['private']['action_kind'], 'social')

    def test_physical_actions_and_sneaking_still_need_their_rulings(self):
        self.assertEqual(room_intent('I sneak past the table to the far door.', addressed=True), 'stealth')
        self.assertEqual(room_intent('I grab the coins.', addressed=True), 'unsupported_action')
        self.assertEqual(room_intent('I attack the dealer.', addressed=True), 'combat')
        revision, state = self.runtime.load()
        with self.assertRaisesRegex(PendingRuling, 'Stealth'):
            Room6CAdjudicator().resolve('I sneak past the table to the far door.', revision, state,
                                        addressed=True)

    def test_what_counts_as_being_addressed(self):
        self.assertFalse(player_was_addressed(None))
        self.assertFalse(player_was_addressed({'spoken': 'Narrator: Cards slap the table.'}))
        self.assertTrue(player_was_addressed({'spoken': 'Dealer: Sit down, you look tired.'}))
        self.assertTrue(player_was_addressed({'spoken': 'Kit: So, what now?'}))
        self.assertFalse(player_was_addressed({'spoken': 'Narrator: Who deals next?'}))


if __name__ == '__main__':
    unittest.main()
