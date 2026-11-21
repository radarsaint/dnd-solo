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

from runtime import kit_combat, kit_rolls
from runtime.kit_agent import RoomAdjudicator
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

    def test_grabbing_the_pot_is_still_a_grab(self):
        result = self.resolve('I scoop the coins from the middle of the table into my bag.')
        self.assertEqual(result.kind, 'combat_round')


class EveryIntentKept(Base):
    def test_speech_in_the_message_does_not_cancel_the_stated_roll(self):
        result = self.resolve('"Nice cards." Nik studies the card backs closely. Investigation check: 1d20 (16) + 7 = `23`')
        self.assertIn('claim_learned', types(result))


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

if __name__ == '__main__':
    unittest.main()
