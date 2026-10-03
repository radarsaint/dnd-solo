"""One message, every intent it carries; the player's own things are not loot (#45, live 6c
run 2026-10-03, transcripts/session-notes.md T2-T7).

General rules pinned here, with the live 6c messages as the regression cases and other
nouns and games for the non-6c half:
- a physical act needs its noun as the verb's own object ("takes the chair and sets a copper
  on the table" takes a chair), and the PC's own things are never loot ("into his pocket");
- a face act needs a hand-contact verb whose object is the face ("flicks his ears ... eyes on
  the dealer's face" touches nobody);
- a message with a physical act, a stated roll, a bet, or the game's name keeps every intent;
- saying the game's name, a spoken "Deal.", or a canon entry with a runnable card procedure
  declares the table."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import kit_cards, kit_combat, kit_rolls, kit_twenty_one
from runtime.kit_agent import RoomAdjudicator, card_procedure
from runtime.state_context import Runtime
from test_kit_agent import FIXTURE

SOURCE = json.loads(FIXTURE.read_text())
SEED = 's18'
NIK = json.loads((Path(__file__).parent / 'fixtures/characters/nik.json').read_text())

T2 = ('Nik takes the chair and sets a single copper on the table. "I count well enough. Twenty-one." '
      'He nods at the silver ring by the dealer\'s stack. "Someone lose that, or is it the pot?" While the '
      'dealer answers, Nik watches his face and the way he talks: does the accent hold up, is he putting on '
      'a show? Nik makes an Insight check! 1d20 (17) + 4 = `21`')
T3 = ('Nik leans back like he\'s buying the act and keeps his eyes on the dealer\'s hands. "A dwarf, huh. '
      'He get to keep his blood, at least?" He smiles a little. "Deal." He\'s watching the shuffle and the '
      'deal for anything off, like a palmed card, a crimp, or a glance at the quiet one with their hand on '
      'their chest. Perception check: 2d20kh1 (11, 5) + 4 = `15`')
T4 = ('Nik slides the copper back into his pocket and stacks ten gold in its place. "Ten. Let\'s see if the '
      'coffins like me." When his cards come, he doesn\'t look at the faces first. He tilts them toward the '
      'candle and studies the backs, because that\'s where the dealer keeps glancing. He\'s looking for '
      'whatever the dealer is reading there, like nicks, shading, or a pattern that\'s a little off. '
      'Investigation check: 1d20 (16) + 7 = `23`')
T7 = ('Nik taps the table once with two fingers. "Still hungry. Rabbits have to eat constantly, it\'s a whole '
      'condition." He flicks his ears. "Hit me." While the card slides over he keeps his eyes on the '
      'dealer\'s face instead of the deck, like a gambler on a lucky streak.')


def types(result):
    return [event['type'] for event in result.events]


def ledger(result):
    return ' '.join(event.get('evidence', '') for event in result.events)


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)
        # Pinned dice: a fixed session seed, so the seated hand is the same every run.
        with patch('runtime.state_context.secrets.token_hex', return_value=SEED):
            self.runtime.initialize(copy.deepcopy(SOURCE), 'area_06c')
        self.runtime.set_player_sheet(NIK)

    def resolve(self, action, commit=False):
        revision, state = self.runtime.load()
        result = RoomAdjudicator(source=self.runtime.source(), roll=lambda: 15).resolve(action, revision, state)
        if commit:
            self.runtime.commit(f'c{revision}', revision, result.events)
        return result

    def seat_in_a_hand(self):
        return self.resolve('I sit down and play twenty-one for 10 gold.', commit=True)


class OwnThingsAreNotLoot(Base):
    def test_taking_a_chair_and_setting_down_a_coin_is_not_a_grab(self):
        result = self.resolve(T2)
        self.assertNotIn('combat_state', types(result))
        self.assertNotIn('initiative', result.public_event.casefold())

    def test_putting_the_coin_back_in_his_own_pocket_is_not_a_grab(self):
        self.seat_in_a_hand()
        result = self.resolve(T4)
        self.assertNotIn('combat_state', types(result))
        self.assertNotIn('come away with the table coins', result.public_event)

    def test_ears_and_a_look_at_his_face_are_not_a_face_act(self):
        self.seat_in_a_hand()
        result = self.resolve(T7)
        self.assertEqual(result.kind, 'card_hit')
        self.assertNotIn('scene_state', types(result))
        self.assertNotIn('paint', result.public_event)

    def test_grabbing_the_pot_is_still_a_grab(self):
        result = self.resolve('I scoop the coins from the middle of the table into my bag.')
        self.assertEqual(result.kind, 'combat_round')


class EveryIntentKept(Base):
    def test_a_physical_act_keeps_the_card_call_made_with_it(self):
        self.seat_in_a_hand()
        result = self.resolve('Nik licks his thumb and wipes a streak of paint off the dealer\'s cheek. "Hit me."')
        self.assertEqual(result.kind, 'card_hit')
        self.assertIn('scene_state', types(result))
        self.assertIn('procedure_state', types(result))
        self.assertTrue(result.public_event.startswith('Your hand reaches the dealer'))
        self.assertIn('You take the', result.public_event)

    def test_the_games_name_and_an_insight_roll_both_resolve(self):
        result = self.resolve(T2.replace('Nik takes the chair', 'Nik sits down in the chair'))
        self.assertIn('procedure_state', types(result))
        self.assertIn('claim_learned', types(result))
        self.assertTrue(result.kind.startswith('card_'))

    def test_a_bet_mid_hand_and_a_stated_read_of_the_backs_both_resolve(self):
        self.seat_in_a_hand()
        result = self.resolve(T4)
        self.assertIn('procedure_state', types(result))
        learned = [e['claim'] for e in result.events if e['type'] == 'claim_learned']
        self.assertEqual(learned, ['marked_deck'])

    def test_speech_in_the_message_does_not_cancel_the_stated_roll(self):
        result = self.resolve('"Nice cards." Nik studies the card backs closely. Investigation check: 1d20 (16) + 7 = `23`')
        self.assertIn('claim_learned', types(result))


class TheTableIsDeclared(Base):
    def test_a_spoken_deal_seats_the_player_and_keeps_the_watch(self):
        result = self.resolve(T3)
        self.assertEqual(result.kind, 'card_watch')
        state = next(e['state'] for e in result.events if e['type'] == 'procedure_state')
        self.assertTrue(state['public']['watch_next_deal'])
        self.assertTrue(state['public']['offered'])

    def test_saying_the_games_name_starts_it_but_asking_or_counting_does_not(self):
        self.assertIn('procedure_state', types(self.resolve('"Twenty-one." Nik pulls up a chair.')))
        self.assertNotIn('procedure_state', types(self.resolve('"Is it twenty-one you play?"')))
        config = self.runtime.source()['procedures']['twenty_one']
        self.assertFalse(kit_cards.game_called(config, 'I count twenty-one gold on the table.'))

    def test_a_canon_entry_with_the_procedure_declares_the_table(self):
        revision, _ = self.runtime.load()
        self.runtime.commit('canon', revision, [{
            'type': 'canon_entry', 'slot': 'area_06c/card_table/game', 'kind': 'procedure',
            'fact': 'The table plays Twenty-One Coffins.', 'basis': 'DM choice: twenty-one.', 'public': True,
            'scope': 'location', 'procedure': 'twenty_one', 'roots': ['card_table'], 'choice': 'self',
            'price': None, 'evidence': 'Kit named the game.'}])
        table = card_procedure(self.runtime.source(), self.runtime.load()[1])
        self.assertEqual(table[0], 'twenty_one')
        result = self.resolve('I bet 10 gold.')
        self.assertTrue(result.kind.startswith('card_'))
        self.assertIn('procedure_state', types(result))


class AvraeTitleRoll(Base):
    def test_avrae_title_with_backticks_counts_as_the_insight_roll(self):
        title = "Nik studies them; something's off. Nik makes an Insight check! 1d20 (17) + 4 = `21`"
        plain = "Nik studies them; something's off. Insight check: 1d20 (17) + 4 = `21`"
        self.assertEqual(kit_rolls.stated_skill(title), 'insight')
        result = self.resolve(title)
        self.assertIn('claim_learned', types(result))
        self.assertEqual(ledger(result).replace(title, plain), ledger(self.resolve(plain)))
        # The title names the skill that gates the reveal (here Investigation on the backs).
        backs = 'Nik studies the card backs closely. Nik makes an Investigation check! 1d20 (16) + 7 = `23`'
        self.assertEqual(kit_rolls.stated_skill(backs), 'investigation')
        result = self.resolve(backs)
        self.assertIn('marked_deck', [e.get('claim') for e in result.events])
        self.assertIn('Investigation', ledger(result))


class OtherNounsAndGames(unittest.TestCase):
    """Not 6c: the same guards on other rooms' words and another game's name."""

    def test_own_items_and_incidental_nouns(self):
        pcs = ('mira',)
        quiet = ('mira takes the stool and sets a gem on the bar.',
                 'mira slides the gold back into her purse.',
                 'mira takes her gold back.',
                 'mira sheathes her dagger and picks up the lantern.')
        for text in quiet:
            with self.subTest(text=text):
                self.assertEqual(kit_combat.taken_valuables(text, pcs), (None, None))
        for text in ('she pockets the gold.', 'mira grabs the merchant and takes his gold.',
                     'i help myself to the silver on the counter.'):
            with self.subTest(text=text):
                self.assertIsNotNone(kit_combat.taken_valuables(text, pcs)[0])
        self.assertFalse(kit_combat.touched_face('mira wipes her face and rubs her ears.', pcs))
        self.assertFalse(kit_combat.touched_face("mira tugs her hood and watches the guard's face.", pcs))
        self.assertTrue(kit_combat.touched_face("mira wipes the soot off the guard's cheek.", pcs))
        self.assertEqual(kit_combat.pc_names({'player_sheet': {'name': 'Mira Vey'}}), ('mira', 'vey'))

    def test_a_games_own_name_declares_it(self):
        config = {'name': "Three-Dragon Ante (Kit's table rules)"}
        self.assertEqual(kit_cards.game_names(config), ('three-dragon ante',))
        self.assertTrue(kit_cards.game_called(config, 'Fine. Three-dragon ante.'))
        self.assertFalse(kit_cards.game_called(config, 'Is that three-dragon ante?'))
        self.assertTrue(kit_cards.game_called({'name': 'x', 'called': ['liar\'s dice']}, "Liar's dice, then."))

    def test_a_spoken_deal_is_only_the_bare_call(self):
        self.assertTrue(kit_twenty_one.SPOKEN_DEAL.search('He nods. "Deal."'))
        self.assertFalse(kit_twenty_one.SPOKEN_DEAL.search('"What a deal that was."'))


if __name__ == '__main__':
    unittest.main()
