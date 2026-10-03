"""Brendon's table calls for area 6c (issue #45, Stage 1 engine work).

Each test names the pass/fail check it pins (TC-xx). Checks that need a live ChatGPT
playtest (TC-1a, 1c, 3b, 3c, 4b, 4c, 6b, and the live halves of 6c-6e, 7a, 7c) are
scripted evals; the engine support for them is tested here."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_cards, kit_guards, kit_toll, kit_twenty_one
from runtime.kit_agent import Room6CAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE, RecordingModel

SOURCE = json.loads(FIXTURE.read_text())
NIK = json.loads((Path(__file__).parent / 'fixtures/characters/nik.json').read_text())
NUMBERS = r'\bDC\b|\bvs\.?\s*\d|\(\w+ \d+\)|[+-]\d+\b|\bd20\b|\bpassive \w+ \d+'
ACTORS = ('uktarl', 'bandit_a', 'bandit_b', 'doppelganger')


def table_total(public):
    """The table's gold, counting the player's net winnings (what conservation keeps)."""
    return sum(public['stacks'].values()) + ((public['player'] or {}).get('net') or 0)


def ledger(result):
    return ' '.join(event.get('evidence', '') for event in result.events)


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)
        self.runtime.initialize(copy.deepcopy(SOURCE), 'area_06c')
        self.runtime.set_player_sheet(NIK)

    def adjudicator(self, roll=15):
        return Room6CAdjudicator(source=self.runtime.source(), roll=lambda: roll)

    def resolve(self, action, roll=15, state=None):
        revision, loaded = self.runtime.load()
        return self.adjudicator(roll).resolve(action, revision, state or loaded)

    def play(self, *actions, roll=15):
        agent = KitAgent(self.runtime, RecordingModel(), self.adjudicator(roll))
        for action in actions:
            agent.turn(action)
        return self.runtime.recent_kit_turns()[-1]['public_event']


from runtime.kit_agent import KitAgent  # noqa: E402  (after Base for readability)


class Call1MentionIsNotATrigger(Base):
    """TC-1b: a card game in the scene never starts a procedure by itself."""

    def plan_declaring(self, why=None):
        plan = {'detail': {'inventions': [{'kind': 'procedure', 'procedure': 'twenty_one'}]}}
        if why:
            plan['agenda'] = {'advances': [{'agent': 'uktarl', 'does': 'waves the visitor to a chair', 'why': why}]}
        return plan

    def test_unrelated_input_starts_no_procedure(self):
        for action in ('I look around.', 'Who are you?'):
            with self.subTest(action=action):
                result = self.resolve(action)
                self.assertNotIn('procedure_state', [event['type'] for event in result.events])
                body = {'action': action, 'events': result.events}
                with self.assertRaisesRegex(InvalidChange, 'not a reason to start one'):
                    kit_agent.check_procedure_start(self.plan_declaring(), body, self.runtime.load()[1])
        self.play('I look around.')
        self.assertEqual(self.runtime.load()[1].get('procedures') or {}, {})

    def test_the_put_off_exception_needs_its_reason(self):
        body = {'action': 'Who are you?', 'events': []}
        state = self.runtime.load()[1]
        kit_agent.check_procedure_start(self.plan_declaring('stall the visitor and keep him seated'), body, state)
        self.assertIn('keep him seated', kit_agent.put_off_reason(self.plan_declaring('stall the visitor and keep him seated')))
        with self.assertRaises(InvalidChange):
            kit_agent.check_procedure_start(self.plan_declaring('he likes cards'), body, state)

    def test_asking_to_play_may_start_it(self):
        kit_agent.check_procedure_start(self.plan_declaring(), {'action': 'I play the game.', 'events': []},
                                        self.runtime.load()[1])


class Call2KeyNeedsActiveSearch(Base):
    """TC-2b: the fresco key needs an active search; a look never finds it."""

    def test_search_rolls_perception_and_success_learns_the_key(self):
        result = self.resolve('I search the carving.', roll=20)
        self.assertIn('Perception', ledger(result))
        self.assertNotRegex(result.public_event, NUMBERS)
        self.assertIn('key', result.public_event)
        learned = [e for e in result.events if e['type'] in ('claim_learned', 'reveal_fact')]
        self.assertTrue(any('fresco_key' in json.dumps(e) for e in learned))

    def test_a_look_or_whats_interesting_never_learns_the_key(self):
        for action in ('I look around.', "What's interesting here?", 'I look at the fresco.'):
            with self.subTest(action=action):
                result = self.resolve(action, roll=20)
                self.assertNotIn('fresco_key', json.dumps(result.events))
                self.assertNotIn('stone key', result.public_event)


class Call3Ruse(Base):
    """TC-3a, TC-3d, TC-3e: the ruse is in the actors' state and the room serves nothing."""

    def test_every_actor_carries_the_ruse_to_decision_and_performer(self):  # TC-3a
        actors = SOURCE['actors']
        for key in ACTORS:
            with self.subTest(actor=key):
                motive = actors[key]['motive']
                self.assertIn('vampire act', motive)
                self.assertIn('visitor', motive)
        cards = SOURCE['public_performance']['actor_cards']
        self.assertEqual(len(cards), 4)
        for name, card in cards.items():
            with self.subTest(card=name):
                objective = card['scene_objective'].casefold()
                self.assertIn('seated', objective)
                self.assertIn('drink nothing', objective)
                self.assertNotIn('vampire', objective, 'the carrier stays public-safe')
        bridge = kit_agent.KitChatBridge(self.runtime, self.adjudicator())
        prepared = bridge.prepare('I look around.', 'ruse')
        self.assertIn('vampire act', json.dumps(prepared['input']))
        performance = bridge.decide('ruse', RecordingModel().plan(prepared['input']))
        performed = json.dumps(performance['input'])
        self.assertIn('keep the visitor seated', performed)
        self.assertNotIn('vampire', performed.casefold())

    def test_something_off_routes_to_the_disguise_claim(self):  # TC-3d
        for action in ("I study them; something's off.", 'I make an Insight check.'):
            with self.subTest(action=action):
                result = self.resolve(action, roll=20)
                self.assertIn('DC 14', ledger(result))
                self.assertIn('meant to frighten you', result.public_event)
                self.assertNotRegex(result.public_event, NUMBERS)

    def test_room_has_no_food_or_drink(self):  # TC-3e
        self.assertTrue(SOURCE['areas']['area_06c']['no_refreshment'])
        text = json.dumps(SOURCE['public_performance']).casefold()
        for word in ('cordial', 'wine cup', 'goblet', 'tankard', 'beet shrub'):
            self.assertNotIn(word, text)
        with self.assertRaisesRegex(InvalidChange, 'nobody here eats or drinks'):
            kit_guards.check_no_refreshment([{'speaker': 'Dealer', 'text': 'Have some wine while you decide.'}])
        with self.assertRaisesRegex(InvalidChange, 'nobody here eats or drinks'):
            kit_guards.check_no_refreshment([{'speaker': 'Narrator', 'text': 'He pours a cup of ale by your coins.'}])
        kit_guards.check_no_refreshment([{'speaker': 'Dealer', 'text': 'Nothing to pour tonight, I am afraid; the cellar is dry.'}])


class Call4NoNumbers(Base):
    """TC-4a: no DC, total, modifier, or die math in any public path; the ledger keeps it."""

    def test_claim_lie_stealth_and_knowledge_paths(self):
        for action in ('I search the carving.', "I study them; something's off.",
                       'I use Insight to tell if the dealer is lying about the toll.',
                       'I sneak toward the south door.', 'What do I know about the silver ring?'):
            for roll in (1, 20):
                with self.subTest(action=action, roll=roll):
                    try:
                        result = self.resolve(action, roll=roll)
                    except kit_agent.PendingRuling:
                        continue
                    self.assertNotRegex(result.public_event, NUMBERS)

    def test_card_paths_both_modes(self):
        config = SOURCE['procedures']['twenty_one']
        for seed in ('a', 'b', 'c', 'd'):
            table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 1, 'perception': 2,
                                                                        'sleight_of_hand': 3}, seed)
            state = kit_cards.initial_state(config)
            for kind, action in (('card_mode_check', 'Just roll for it.'), ('card_watch', 'I watch his hands.'),
                                 ('card_mode_play', 'I play it out.'), ('card_stand', 'stand')):
                try:
                    text, state, _ = table.resolve(kind, action, 1, state)
                except (kit_cards.NeedsRuling, AttributeError):
                    continue
                self.assertNotRegex(text, NUMBERS, (seed, kind))
            self.assertTrue(table.trace, 'numbers go to the trace')

    def test_guard_rejects_numbers_in_any_segment(self):
        for bad in ('You rolled 18 vs DC 14.', 'Perception check, +4.', '(Perception 18)', 'You get 1d20+5.'):
            with self.subTest(bad=bad), self.assertRaises(InvalidChange):
                kit_guards.check_public_numbers([{'speaker': 'Kit', 'text': bad}])
        with self.assertRaises(InvalidChange):
            kit_guards.check_public_numbers([], public_event='You find it. (Perception 18)')
        kit_guards.check_public_numbers([{'speaker': 'Kit', 'text': 'Make a Perception check.'}])
        kit_guards.check_public_numbers([{'speaker': 'Dealer', 'text': 'Ten gold a hand, friend?'}])


class Call6Toll(Base):
    """TC-6a, TC-6c, TC-6d, TC-6e: the toll is an exchange with persisted state."""

    def tolls(self):
        return self.runtime.player_view().get('tolls') or {}

    def test_bare_toll_beside_game_talk_is_rejected(self):  # TC-6a
        bare = [{'speaker': 'Dealer', 'text': 'Cards, friend. Passage is ten gold a head. Sit if you like.'}]
        with self.assertRaisesRegex(InvalidChange, 'real exchange'):
            kit_guards.check_toll_exchange(bare, 10, False)
        with self.assertRaisesRegex(InvalidChange, "NPC's demand"):
            kit_guards.check_toll_exchange([{'speaker': 'Narrator', 'text': 'Passage costs ten gold a head.'}], 10, False)
        demand = [{'speaker': 'Dealer', 'text': 'The night has teeth, and we keep them off this door. '
                   'Ten gold a head for passage. Will you pay it?'}]
        kit_guards.check_toll_exchange(demand, 10, False)

    def test_every_response_commits_and_persists(self):  # TC-6c
        cases = [('I pay the toll.', 'paid'), ('I offer five gold for passage.', 'negotiated'),
                 ('I refuse to pay the toll.', 'refused'), ('I play for the toll.', 'staked')]
        for action, status in cases:
            with self.subTest(action=action):
                self.setUp()
                before = self.runtime.load()[0]
                self.play(action)
                self.assertEqual(self.runtime.load()[0], before + 1, 'the turn committed')
                self.assertEqual(self.tolls()['passage_toll']['status'], status)
        self.assertEqual(self.tolls()['passage_toll'].get('agreed'), None)

    def test_haggle_below_the_floor_and_a_counter(self):
        self.play('I offer 2 gold for passage.')
        self.assertEqual(self.tolls()['passage_toll']['status'], 'countered')

    def test_negotiated_amount_is_backed_for_the_numeric_guard(self):  # TC-6c
        self.play('I offer five gold for passage.')
        view = self.runtime.player_view()
        guards = kit_agent.guard_context(self.runtime.source(), {'public_view': view})
        self.assertIn(5, guards['numeric_facts']['passage_toll']['allowed_amounts'])
        line = [{'speaker': 'Dealer', 'text': 'Five gold for passage, then. Done.'}]
        kit_guards.check_numeric_facts(line, guards['numeric_facts'], 'I offer five gold for passage.')
        fresh = kit_agent.guard_context(self.runtime.source(), {'public_view': {}})
        with self.assertRaises(InvalidChange):
            kit_guards.check_numeric_facts([{'speaker': 'Dealer', 'text': 'Seven gold for passage, then.'}],
                                           fresh['numeric_facts'], 'I nod.')

    def test_refusal_escalates_and_persists(self):  # TC-6d
        first = self.play('I refuse to pay the toll.')
        self.assertEqual(len(self.runtime.load()[1]['tolls']['passage_toll']['consequences']), 1)
        second = self.play('I still refuse to pay the toll.')
        self.assertNotEqual(first, second)
        self.assertIn('Xanathar', second)
        self.assertEqual(self.tolls()['passage_toll']['status'], 'refused')

    def test_game_talk_defers_and_play_for_folds_only_if_carriable(self):  # TC-6e
        revision, state = self.runtime.load()
        state = copy.deepcopy(state)
        body = kit_toll.initial(kit_toll.compile_tolls(SOURCE)['passage_toll'])
        body.update(status='demanded', demanded_by='uktarl')
        state['tolls'] = {'passage_toll': body}
        result = self.adjudicator().resolve('Deal me in, I want to play a hand first.', revision, state)
        tolls = [e for e in result.events if e['type'] == 'toll_state']
        self.assertEqual(tolls[-1]['state']['status'], 'deferred', 'the toll stays pending, not dropped')
        self.assertTrue(kit_cards.can_carry(SOURCE['procedures']['twenty_one'], 'toll'))
        self.assertFalse(kit_cards.can_carry({'kind': 'card_game'}, 'toll'))
        self.play('I play for the toll.', 'Just roll for it.', roll=20)
        self.assertIn(self.tolls()['passage_toll']['status'], ('waived', 'paid'))


class TollStakeTests(Base):
    """PR #47 review: a staked toll obeys the same purse cap as any bet, and never strands."""

    def status(self):
        return (self.runtime.load()[1].get('tolls') or {})['passage_toll']['status']

    def game(self):
        return self.runtime.load()[1]['procedures']['twenty_one']['public']

    def test_cover_uses_the_same_cap_as_any_bet(self):
        config = SOURCE['procedures']['twenty_one']
        public = kit_cards.initial_state(config)['public']
        self.assertTrue(kit_twenty_one.can_cover(public, 10), 'no purse declared: no cap but the table max')
        self.assertFalse(kit_twenty_one.can_cover(public, config['max_stake'] + 1))
        public['player'] = {'net': 0, 'purse': 5, 'unwelcome': False}
        self.assertFalse(kit_twenty_one.can_cover(public, 10))
        public['player']['net'] = 5
        self.assertTrue(kit_twenty_one.can_cover(public, 10), 'winnings count toward what they can risk')

    def test_engine_unstakes_a_toll_the_purse_cannot_cover(self):
        config = SOURCE['procedures']['twenty_one']
        table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 1, 'perception': 2}, 's')
        state = kit_cards.initial_state(config)
        state['public']['player'] = {'net': 0, 'purse': 5, 'unwelcome': False}
        state['public']['mode'] = 'check'
        state['public']['toll_stake'] = 10
        text, state, _ = table.resolve('card_round', 'Deal.', 1, state)
        self.assertEqual(table.toll_outcome, 'unstaked')
        self.assertIsNone(state['public']['toll_stake'])
        self.assertFalse(state['public']['round']['toll'])
        self.assertLessEqual(state['public']['round']['stake'], 5)
        self.assertGreaterEqual(state['public']['player']['net'], -5, 'never past the declared purse')
        self.assertIn('stays owed', text)

    def test_play_for_with_a_short_purse_keeps_the_toll_owed(self):
        # The table's d20 is seeded, not the adjudicator's roll, so the loss is stated.
        self.play('I buy in with 5 gold.', 'Just roll for it. I rolled 1 + 0 = 1.')
        self.assertEqual(self.game()['player']['net'], -5)
        before = self.runtime.load()[0]
        text = self.play('I play for the toll.')
        self.assertEqual(self.runtime.load()[0], before + 1, 'the answer still commits')
        self.assertIn('cannot cover', text.casefold())
        self.assertEqual(self.status(), 'deferred')
        self.assertIsNone(self.game()['toll_stake'])
        self.assertEqual(self.game()['player']['net'], -5)

    def test_buy_in_after_staking_caps_the_toll(self):
        self.play('I play for the toll.')
        self.assertEqual(self.status(), 'staked')
        text = self.play('I buy in with 5 gold. Just roll for it.', roll=1)
        self.assertIn('stays owed', text)
        self.assertEqual(self.status(), 'demanded')
        self.assertIsNone(self.game()['toll_stake'])
        self.assertGreaterEqual(self.game()['player']['net'], -5)

    def test_staking_and_settling_in_one_action_settles_the_toll(self):
        self.play('I buy in with 30 gold.', 'Just roll for it. I rolled 20 + 5 = 25.')
        self.play('I play for the toll. I rolled 1 + 0 = 1.')
        body = self.runtime.load()[1]['tolls']['passage_toll']
        self.assertEqual(body['status'], 'paid')
        self.assertEqual(body['paid'], 10)
        self.assertGreaterEqual(self.game()['player']['purse'] + self.game()['player']['net'], 0)

    def test_leaving_the_table_before_the_round_unstakes_the_toll(self):
        self.play('I play for the toll.')
        self.assertEqual(self.status(), 'staked')
        text = self.play('I leave the table.')
        self.assertIn('still owed', text)
        self.assertEqual(self.status(), 'demanded')
        self.assertIsNone(self.game()['toll_stake'])
        self.play('I pay the toll.')
        self.assertEqual(self.status(), 'paid', 'the toll is answerable again')

    def test_leaving_keeps_the_status_it_had_before_staking(self):
        self.play('I refuse to pay the toll.')
        self.play('I play for the toll.')
        self.assertEqual(self.status(), 'staked')
        self.play('I leave the table.')
        self.assertEqual(self.status(), 'refused')

    def test_leaving_the_room_unstakes_it_too(self):
        self.play('I play for the toll.')
        self.play('I go through the south door.')
        self.assertEqual(self.status(), 'demanded')
        self.assertIsNone(self.game()['toll_stake'])

    def test_buy_in_is_a_purse_not_a_bet(self):
        self.play('I buy in with 20 gold.', 'I play it out.')
        self.assertEqual(self.game()['round']['stake'], SOURCE['procedures']['twenty_one']['default_stake'])
        self.assertEqual(self.game()['player']['purse'], 20)


class Call7ChoiceAndModes(Base):
    """TC-7a, TC-7b, TC-7c and the padding hand exemption."""

    def test_bare_play_offers_both_modes_and_commits(self):  # TC-7a
        before = self.runtime.load()[0]
        text = self.play('I play the game.')
        self.assertEqual(self.runtime.load()[0], before + 1)
        self.assertIn('one check', text)
        self.assertIn('twenty-one', text)
        self.assertNotIn('Name the card', text)
        self.assertNotIn('Choose a card', text)

    def test_check_mode_moves_gold_and_keeps_the_cheat_live(self):  # TC-7b
        config = SOURCE['procedures']['twenty_one']
        moved = set()
        for seed in map(str, range(12)):
            table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 1, 'perception': 2}, seed)
            state = kit_cards.initial_state(config)
            total = table_total(state['public'])
            text, state, _ = table.resolve('card_mode_check', 'Just roll for it.', 1, state)
            self.assertNotRegex(text, NUMBERS)
            self.assertIn('Insight', text, 'the skill is named')
            self.assertEqual(table_total(state['public']), total)
            moved.add(state['public']['player']['net'])
            self.assertIn('table_beat', state['public']['last_result'])
            # The marked deck shapes the round unless the player caught it.
            self.assertTrue(any('marked deck' in line for line in table.trace), table.trace)
        self.assertTrue(moved - {0}, 'the round moves gold')
        # A watch is still possible in check mode, and a catch removes the edge.
        table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 1, 'perception': 2}, '3')
        state = table.resolve('card_mode_check', 'Just roll for it.', 1, kit_cards.initial_state(config))[1]
        text, state, reveals = table.resolve('card_watch', 'I watch his hands. I rolled 20 + 5 = 25', 2, state)
        self.assertEqual(reveals, ['marked_deck'])
        self.assertNotRegex(text, NUMBERS)
        self.assertNotIn('marked deck: dealer number', table.trace[-1])
        watched = kit_twenty_one.card_intent('I watch the dealer for cheating.', kit_cards.initial_state(config))
        self.assertEqual(watched, 'card_watch')

    def test_play_mode_is_hit_or_stand(self):  # TC-7c
        config = SOURCE['procedures']['twenty_one']
        state = kit_cards.initial_state(config)
        table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 1, 'perception': 2}, 'x')
        text, state, _ = table.resolve('card_mode_play', 'I play it out.', 1, state)
        if state['public']['round'] and state['public']['round']['phase'] == 'play':
            self.assertIn('Hit or stand', text)
            self.assertEqual(kit_twenty_one.card_intent('hit', state), 'card_hit')
            self.assertEqual(kit_twenty_one.card_intent('stand', state), 'card_stand')
        # The rules fit in one sentence a typical player already knows.
        offer = table.resolve('card_offer', 'I play.', 1, kit_cards.initial_state(config))[0]
        self.assertIn('closest to 21 without going over', offer)
        self.assertLess(len(offer.split()), 60)

    def test_conservation_over_many_rounds(self):
        config = SOURCE['procedures']['twenty_one']
        for seed in map(str, range(20)):
            table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 2, 'perception': 2}, seed)
            state = kit_cards.initial_state(config)
            total = table_total(state['public'])
            moves = [('card_mode_play', 'I play it out.'), ('card_hit', 'hit'), ('card_stand', 'stand'),
                     ('card_round', 'Deal again.'), ('card_stand', 'stand'), ('card_mode_check', 'Just roll for it.')]
            for kind, action in moves:
                live = bool(state['public']['round'] and state['public']['round']['phase'] == 'play')
                if kind in ('card_hit', 'card_stand') and not live:
                    continue
                if kind not in ('card_hit', 'card_stand') and live:
                    continue
                state = table.resolve(kind, action, 1, state)[1]
                self.assertEqual(table_total(state['public']),
                                 total, (seed, kind))
                self.assertTrue(all(gp >= 0 for gp in state['public']['stacks'].values()))

    def test_hand_reminder_is_not_padding(self):  # TC-7c
        segments = [{'speaker': 'Narrator', 'text': 'Your cards: 10 of spades and 5 of clubs, 15.'},
                    {'speaker': 'Dealer', 'text': 'Fifteen is a nervous number. Hit or stand, friend?'}]
        kit_guards.check_padding(segments, 'hit', 'card_hit', public_state='10 of spades 5 of clubs',
                                 card_words=kit_cards.card_words())

    def test_foreign_rules_ban_dropped_for_blackjack_and_poker(self):
        from runtime import kit_detail
        for line in ('We play blackjack here.', 'Five-card poker, friend.', 'Twenty-one, closest wins.'):
            self.assertIsNone(kit_detail.FOREIGN_RULES.search(line.casefold()))
        self.assertTrue(kit_detail.FOREIGN_RULES.search('high card takes it'))


if __name__ == '__main__':
    unittest.main()
