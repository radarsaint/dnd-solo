"""Scorecard items 2-5 of the 6c variety baseline (2026-10-03): toll intent, social checks
rolled in conversation, card-table robustness, and validator noise. Every die is pinned:
the player's rolls are stated the way Avrae reports them, and Kit's own d20 is overridden."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_agent, kit_guards
from runtime.kit_agent import RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_voice import HardeningGuardTests, SHOWTIME_SPEECH, VoiceTestCase

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'level_01_area_06c.json'
SHEETS = ROOT / 'tests' / 'fixtures' / 'characters'


class Room:
    def __init__(self, test, sheet='example_pc.json', toll=True, roll=lambda: 10, seed=3):
        temp = tempfile.TemporaryDirectory()
        test.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        test.addCleanup(self.runtime.close)
        with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{seed:032x}'):
            self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.runtime.set_player_sheet(json.loads((SHEETS / sheet).read_text()))
        if toll:
            revision, state = self.runtime.load()
            events = []
            for key, (config, body) in kit_toll.here(self.runtime.source(), state).items():
                body.update(status='demanded', demanded_by=config['demanded_by'])
                events.append(kit_toll.event(key, body, 'The dealer demanded the toll.'))
            self.runtime.commit('toll', revision, events)
        self.adjudicator = RoomAdjudicator(roll=roll, source=self.runtime.source())

    def act(self, action):
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(action, revision, state)
        self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    @property
    def state(self):
        return self.runtime.load()[1]

    def toll(self):
        return self.state['tolls']['passage_toll']

    def game(self):
        return self.state['procedures']['twenty_one']['public']


class SocialCheckTests(unittest.TestCase):
    def test_avrae_format_counts_and_the_total_is_used(self):
        room = Room(self, toll=False)
        result = room.act("'You don't want trouble with me.' [Persuasion: 1d20 (3) + 2 = 5]")
        self.assertEqual(result.kind, 'social_check')
        self.assertIn('not moved', result.public_event)
        self.assertIn('d20 3 + 2 = 5', json.dumps(result.events))

    def test_a_bare_stated_number_is_the_total_and_the_bonus_is_not_added_again(self):
        room = Room(self, sheet='nik.json', toll=False)
        bonus = json.loads((SHEETS / 'nik.json').read_text())['skills']['deception']
        result = room.act("'I'm with the Watch.' I rolled 17 for Deception.")
        self.assertIn(f'd20 {17 - bonus} + {bonus} = 17', json.dumps(result.events))
        self.assertEqual(result.public_event, 'The dealer believes you.')

    def test_each_social_skill_counts(self):
        for skill in ('Deception', 'Persuasion', 'Intimidation', 'Athletics'):
            with self.subTest(skill=skill):
                room = Room(self, toll=False)
                result = room.act(f"'Sit down.' [{skill}: 1d20 (20) + 0 = 20]")
                self.assertEqual(result.kind, 'social_check')

    def test_insight_rolled_while_talking_reads_the_group(self):
        room = Room(self, toll=False)
        result = room.act("I lean over the dealer and breathe in. 'Which nest turned you?' [Insight: 1d20 (19) + 1 = 20]")
        self.assertEqual(result.kind, 'check')
        self.assertIn('false_vampires', room.state['known_facts'])


class AvraeAtTheTableTests(unittest.TestCase):
    """6c rerun blockers (2026-10-03, Avrae's real output): a die face, modifier, or total is
    never a bet or an amount; a check title names the skill; "just roll" honors the skill
    the player chose."""
    INVESTIGATION = 'Wren makes an Investigation check! 1d20 (12) + 3 = `15`'
    SLEIGHT = 'Wren makes a Sleight of Hand check! 1d20 (6) + 7 = `13`'

    def test_avrae_check_title_counts_as_the_social_skill(self):
        room = Room(self, toll=False)
        result = room.act("'Sit down.'\nWren makes a Persuasion check! 1d20 (20) + 0 = `20`")
        self.assertEqual(result.kind, 'social_check')
        self.assertIn('Persuasion', json.dumps(result.events))


class ValidatorNoiseTests(VoiceTestCase):
    ACTION = HardeningGuardTests.ACTION
    guarded = HardeningGuardTests.guarded
    showtime_plan = HardeningGuardTests.showtime_plan

    def test_every_problem_is_reported_at_once(self):
        speech = {'segments': SHOWTIME_SPEECH['segments'] + [
            {'speaker': 'Narrator', 'text': 'You agree to pay, and you feel terrified.'},
            {'speaker': 'Dealer', 'text': 'Uktarl never loses.'}]}
        with self.assertRaises(InvalidChange) as caught:
            self.guarded(speech, self.showtime_plan())
        message = str(caught.exception)
        self.assertRegex(message, r'^\d+ problems; fix all of them')
        self.assertIn('private fact', message)
        self.assertIn('(2)', message)

    def test_all_problems_keeps_a_single_message_as_is(self):
        self.assertEqual(kit_agent.all_problems(['One thing.', 'One thing.']), 'One thing.')

    def test_a_name_the_player_said_stays_usable_on_later_turns(self):
        phrases = {**kit_guards.leak_phrases(self.runtime.source()), 'player_said': ['harria']}
        kit_agent.check_public_content('Dealer: Harria sends nobody.', {}, 'I nod.', phrases=phrases)
        with self.assertRaises(InvalidChange):
            kit_agent.check_public_content('Dealer: Harria sends nobody.', {}, 'I nod.',
                                           phrases={**phrases, 'player_said': []})

    def test_the_turn_records_the_names_the_player_has_said(self):
        self.assertEqual(kit_agent.player_named(self.runtime, 'Harria sent me.'), ['harria'])


class GuardFalseAlarmTests(unittest.TestCase):
    def test_a_mountain_dwarf_is_a_dwarf(self):
        kit_guards.check_player_identity([{'speaker': 'Dealer', 'text': 'Sit down, dwarf.'}],
                                         {'name': 'Brakka', 'ancestry': 'Dwarf (Mountain)'})
        with self.assertRaises(InvalidChange):
            kit_guards.check_player_identity([{'speaker': 'Dealer', 'text': "You're an elf."}],
                                             {'name': 'Brakka', 'ancestry': 'Dwarf (Mountain)'})

    def test_a_speaker_label_is_not_a_leak_keyword(self):
        sets = kit_guards.leak_sets(json.loads(FIXTURE.read_text()))
        kit_guards.check_paraphrased_leaks('The Fresco-side player lifted his cup.', {}, '', sets,
                                           labels=('Fresco-side player', 'Dealer'))
        with self.assertRaises(InvalidChange):
            kit_guards.check_paraphrased_leaks('One carved dwarf lifted slightly.', {}, '', sets,
                                               labels=('Fresco-side player',))

    def test_asking_what_is_in_the_tub_reads_the_source_not_an_invention(self):
        room = Room(self, toll=False)
        result = room.act("I crouch by the stone tub. What's in it?")
        self.assertEqual(result.kind, 'inspect_feature')
        self.assertIn('tub_stash', room.state['known_facts'])


if __name__ == '__main__':
    unittest.main()
