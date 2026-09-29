"""QA PR #15 fix pass: secrets hinted by prepared details, scene fit (who the player
is, what the deal was, what can be staked), and the rules/stakes guard while a game
runs. Each test is a regression for a failure seen in the PR #15 host play."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_cards, kit_detail, kit_guards, kit_texture
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE

SOURCE = json.loads(FIXTURE.read_text())
PALETTE = SOURCE['texture_palette']['areas']['area_06c']


def seg(speaker, text):
    return {'speaker': speaker, 'text': text}


def palette_strings(palette):
    found = []
    for item in palette.get('items', []):
        found.append((item['id'], item['text']))
    for cards in palette.get('decks', {}).values():
        for card in cards:
            found += [(card['id'], card['entry']), (card['id'], card['handle'])]
    return found


class LeakClassTests(unittest.TestCase):
    """Item 1: the prepared details that hinted at secrets are rewritten, and the leak
    check catches the class (hints of concealment, a performance, a prop, a loose
    carving), not only the literal words."""

    OLD = {
        'beet_shrub': 'A beet-and-vinegar shrub, red enough to pass for something worse, and sour enough '
                      'to make them wince in character',
        'costume_pride': 'The four sit like people who rehearsed sitting.',
        'clove_smoke': 'Cloves, heavy, as if someone burned a handful to cover something else',
        'clove_handle': 'ask what the cloves are covering',
        'loose_dwarf': 'One carved dwarf is loose in its niche.',
    }

    def leaks(self, text):
        kit_guards.check_paraphrased_leaks(text, {}, '', kit_guards.leak_sets(SOURCE))

    def test_the_old_hinting_details_are_rejected(self):
        for name, text in self.OLD.items():
            with self.subTest(name), self.assertRaisesRegex(InvalidChange, 'paraphrases a private fact'):
                self.leaks(text)

    def test_the_class_not_just_the_words(self):
        for text in ('The dwarf third from the left sits proud of the stone.',
                     'One little carved figure wobbles when the door slams.',
                     'Everyone at this table is hiding something.',
                     'Their pale faces look posed, like players in costume.',
                     'The cordial is dark enough to pass for blood.'):
            with self.subTest(text), self.assertRaises(InvalidChange):
                self.leaks(text)

    def test_ordinary_scene_lines_still_pass(self):
        for text in ('The tiny dwarves are cut mid-song, mouths open, beards braided into the rock seams.',
                     'The dealer fans the cards with a theatrical drawl of his wrist.',
                     'A stone tub is sunk into the floor beneath the fresco.',
                     'Cloves and orange peel smoulder in the brazier.'):
            with self.subTest(text):
                self.leaks(text)

    def test_the_new_palette_passes_and_the_old_strings_are_gone(self):
        kit_texture.check_palette(SOURCE)
        strings = ' '.join(text for _, text in palette_strings(PALETTE)).casefold()
        for phrase in ('pass for something worse', 'in character', 'rehearsed', 'cover something',
                       'covering', 'bathwater'):
            self.assertNotIn(phrase, strings)

    def test_the_palette_check_rejects_an_old_hinting_string(self):
        for text in (self.OLD['beet_shrub'], self.OLD['clove_smoke'], self.OLD['costume_pride']):
            broken = copy.deepcopy(SOURCE)
            broken['texture_palette']['areas']['area_06c']['items'][0]['text'] = text
            with self.subTest(text), self.assertRaises(InvalidChange):
                kit_texture.check_palette(broken)


class PlayerIdentityTests(unittest.TestCase):
    """Item 2a: NPC lines must not misstate the player character (Nik is a Harengon)."""

    NIK = {'name': 'Nik', 'ancestry': 'Harengon', 'class': 'Rogue', 'level': 3}

    def check(self, *segments):
        kit_guards.check_player_identity(list(segments), self.NIK)

    def test_the_playtest_elf_line_is_rejected(self):
        with self.assertRaisesRegex(InvalidChange, 'Harengon'):
            self.check(seg('Dealer', 'A love-struck elf with a purse to empty. Sit.'))
        for text in ("You're an elf, then? Sit.", 'Sit down, elf, and ante.', 'Not bad for an elf, you.',
                     'A lucky little elf like you should quit early.'):
            with self.subTest(text), self.assertRaises(InvalidChange):
                self.check(seg('Door-side player', text))

    def test_the_right_ancestry_and_possessives_pass(self):
        self.check(seg('Dealer', 'A long-eared harengon with a purse to empty. Sit.'),
                   seg('Fourth player', 'The rabbit wants a seat? Fine.'),
                   seg('Narrator', 'Somewhere far above, an elf sings in a tavern.'),
                   seg('Dealer', 'Your elf friend is not here to save you.'))

    def test_no_character_recorded_means_no_check(self):
        kit_guards.check_player_identity([seg('Dealer', 'A love-struck elf with a purse to empty.')], None)

    def test_the_character_is_recorded_and_public(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        result = runtime.set_player_character('Nik', 'Harengon', 'Rogue', 3)
        self.assertEqual(result['revision'], 1)
        self.assertEqual(runtime.player_view()['your_character'], self.NIK)
        with self.assertRaises(InvalidChange):
            runtime.set_player_character('Nik', 'Harengon', 'Rogue', 40)
        # Recording the character first does not use up the room entry.
        prepared = kit_agent.KitChatBridge(runtime, kit_agent.Room6CAdjudicator()).prepare(
            None, 'entry', one_pass=True, opening=True)
        self.assertEqual(prepared['input']['private']['action_kind'], 'opening')
        self.assertEqual(prepared['input']['private']['dm_context']['player_perceivable']['your_character'],
                         self.NIK)


class CleanDealTests(unittest.TestCase):
    """Item 2b: narration can't describe a clean deal when the game state says the
    dealer cheated it."""

    def test_clean_deal_narration_is_rejected_on_a_cheated_deal(self):
        for text in ('His fingers stay clear of the deck the whole deal.', 'A clean deal, every card off the top.',
                     'The deal was honest.', 'He deals straight off the top.'):
            with self.subTest(text), self.assertRaisesRegex(InvalidChange, 'clean deal'):
                kit_guards.check_clean_deal([seg('Narrator', text)], True)
        with self.assertRaises(InvalidChange):
            kit_guards.check_clean_deal([seg('Kit', 'Clean deal. Boring.')], True)

    def test_perception_npcs_and_honest_deals_pass(self):
        kit_guards.check_clean_deal([seg('Narrator', 'Nothing about the deal looks wrong to you.'),
                                     seg('Dealer', 'A clean deal, friend. Always.')], True)
        kit_guards.check_clean_deal([seg('Narrator', 'His fingers stay clear of the deck.')], False)

    def test_scene_facts_read_the_state_after_this_turns_events(self):
        config = SOURCE['procedures']['three_dragon_ante']
        for number in range(60):
            table = kit_cards.CardTable('three_dragon_ante', config, {}, f'clean{number}')
            text, body, _ = table.resolve('card_join', 'I buy in with 30 gold and deal me in.', 1,
                                          kit_cards.initial_state(config))
            events = [{'type': 'procedure_state', 'procedure': 'three_dragon_ante', 'state': body}]
            facts = kit_agent.scene_facts({'procedures': {}}, events)
            self.assertEqual(facts['dealer_cheated'], body['private']['cheated'])
        self.assertEqual(kit_agent.scene_facts({}, [])['dealer_cheated'], False)

    def test_guard_context_carries_the_flag_but_the_performer_input_does_not(self):
        body = {'public_view': {}, 'scene_facts': {'dealer_cheated': True}}
        self.assertTrue(kit_agent.guard_context(SOURCE, body)['dealer_cheated'])


class StakeOfferTests(unittest.TestCase):
    """Item 2c: NPCs can't offer to stake what the game can't carry (ring, toll)."""

    def test_uncarried_stakes_are_rejected(self):
        for text in ("I'll stake the ring against your purse.", 'The ring? Put it in the pot, then.',
                     'Win a gambit and the toll is waived.', 'We could play for safe passage.',
                     'Bet your sword on it.'):
            with self.subTest(text), self.assertRaisesRegex(InvalidChange, 'stakes only gp'):
                kit_guards.check_stake_offers([seg('Dealer', text)])

    def test_gold_stakes_and_narration_pass(self):
        kit_guards.check_stake_offers([seg('Dealer', 'Stakes are eleven gold a head. Ante a card.'),
                                       seg('Narrator', 'The silver ring lies beside the stakes.'),
                                       seg('Dealer', 'The ring stays where it is. Bet gold.')])


class RunningGameGuardTests(unittest.TestCase):
    """Item 6: the rules/stakes guard stays on while a game runs, and stake amounts are
    never accepted as ring or toll prices."""

    RUNNING = ('three_dragon_ante',)

    def check(self, text, speaker='Dealer'):
        kit_detail.check_detail_performance([seg(speaker, text)], self.RUNNING, kit_cards.RULE_TERMS)

    def test_another_games_rules_are_rejected_while_a_game_runs(self):
        for text in ('Highest card takes the pot.', 'One card apiece, and the high card wins.',
                     'Rules are simple: closest to twenty-one wins.'):
            with self.subTest(text), self.assertRaisesRegex(InvalidChange, 'running game'):
                self.check(text)

    def test_the_running_games_own_rules_and_stakes_pass(self):
        self.check('The stakes are whatever the strongest ante card says.')
        self.check('Each player antes a card; the strongest flight takes the stakes.')
        self.check('High card, low card, who cares.', speaker='Kit')

    def test_no_game_running_keeps_the_old_rule(self):
        with self.assertRaisesRegex(InvalidChange, 'Undeclared procedure'):
            kit_detail.check_detail_performance([seg('Dealer', 'The stakes are two gold.')], ())

    def numeric(self, text, stakes=(11,)):
        kit_guards.check_numeric_facts([seg('Dealer', text)], kit_guards.numeric_facts(SOURCE), '',
                                       stakes, kit_cards.RULE_TERMS)

    def test_stake_amounts_are_not_ring_or_toll_prices(self):
        self.numeric('Stakes are eleven gold a head.')
        self.numeric('The strongest ante card was an eleven, so the stakes are 11 gold each.')
        for text in ('The ring? Eleven gold, and the stakes are yours.', 'Passage through is 11 gold.',
                     'Win the stakes and passage is 11 gold.'):
            with self.subTest(text), self.assertRaisesRegex(InvalidChange, 'Source fact'):
                self.numeric(text)

    def test_the_ring_value_may_be_stated(self):
        """Brendon: NPCs may state the ring's 25 gp; small stuff isn't a secret."""
        self.numeric('That ring is worth 25 gold, no more.')

    def test_guard_context_never_merges_stakes_into_fixed_amounts(self):
        view = {'table_procedures': {'three_dragon_ante': {'stacks': {'Dealer': 11}, 'player': {'gp': 7}}}}
        guards = kit_agent.guard_context(SOURCE, {'public_view': view})
        self.assertEqual(guards['numeric_facts']['ring_value']['allowed_amounts'], [25])
        self.assertEqual(guards['numeric_facts']['passage_toll']['allowed_amounts'], [10])
        self.assertEqual(guards['stake_amounts'], [7, 11])


class SpokenAmountTests(unittest.TestCase):
    """Item 4 (amount parsing): whole numbers only, spoken forms accepted."""

    def test_spoken_amounts(self):
        cases = {'25 gp': [(25, 'gp')], '125 gp': [(125, 'gp')], 'five silver': [(5, 'sp')],
                 '63,000 gp': [(63000, 'gp')], 'sixty-three thousand gold': [(63000, 'gp')],
                 'twenty-five gold pieces': [(25, 'gp')], 'a hundred and ten gold': [(110, 'gp')],
                 'three coppers and two silver': [(3, 'cp'), (2, 'sp')]}
        for text, expected in cases.items():
            with self.subTest(text):
                self.assertEqual(kit_guards.spoken_amounts(text), expected)
        self.assertNotIn(25, [amount for amount, _ in kit_guards.spoken_amounts('It costs 125 gp.')])


if __name__ == '__main__':
    unittest.main()
