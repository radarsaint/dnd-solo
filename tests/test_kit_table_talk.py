"""Host-declared table talk (persona-continuity R1): `prepare --table-talk` marks a line as the
player talking to Kit mid-scene. It is answered in meta mode, never adjudicated (no check, ruling,
toll, card call, story hook, or NPC reply), recorded as table talk rather than 'You declare', and
the hidden-information guards still apply. The host decides what is a game turn; no classifier."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_agent, kit_guards
from runtime.kit_agent import KitChatBridge, RoomAdjudicator, table_talk_event
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE, RecordingModel

# Brendon's ordinary (O1-O6) and debrief (D1-D5) lines from the persona-continuity eval's
# routing pre-check (radarsaint/bfdm-corpus 6337f81): 10 of 11 were read as the PC speaking.
BRENDON_LINES = (
    'Hello, Kit.',
    'What are you?',
    'Where does that come from?',
    "What do you think we're doing wrong with this project?",
    "I'm annoyed with how that test went.",
    'Do you actually like this campaign idea?',
    'That NPC sucked. Why?',
    'What part of that scene were you proud of?',
    'Would you have run that differently now?',
    'I think I broke the encounter. What do you think?',
    'This idea is probably stupid. Tell me if it is.',
)
STOP = "Okay, let's stop there."
KIT_ANSWER = {'segments': [{'speaker': 'Kit', 'text': 'Fair. That one is on me; tell me which part bugged you most.',
                            'reacts_to': 'annoyed with how that test went'}]}


class TableTalkCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(perception=0, insight=0, roll=lambda: 20))
        self.model = RecordingModel()

    def meta_plan(self, prepared_input):
        plan = self.model.plan(prepared_input)
        plan.update(turn_mode='meta', move='ruling', focus_actor='none', table_presence='present')
        plan['public_brief']['scope'] = 'call'
        plan['improv_read']['actor_ref'] = 'none'
        plan['improv_read']['actor_basis'] = 'none'
        return plan


class BrendonsLinesAreTableTalk(TableTalkCase):
    def test_all_eleven_lines_go_to_meta_and_none_is_logged_as_the_pc(self):
        for index, line in enumerate(BRENDON_LINES + (STOP,)):
            with self.subTest(line=line):
                prepared = self.bridge.prepare(line, f'tt-{index}', one_pass=True, table_talk=True)
                private = prepared['input']['private']
                self.assertEqual(private['table_read']['mode_hint'], 'meta')
                self.assertTrue(private['table_read']['out_of_character'])
                self.assertEqual(private['accepted_public_event'], table_talk_event(line))
                self.assertNotIn('You declare', json.dumps(prepared['input'], ensure_ascii=False))
                self.assertNotIn('raise_now', prepared['input']['public'])
                self.assertNotIn('agenda_here', private)
                self.assertEqual(prepared['table_talk'], kit_agent.TABLE_TALK_NOTE)
                self.bridge.abandon(f'tt-{index}')
        # Nothing reached the room: no refused attempt, no ruling, no committed turn.
        revision, state = self.runtime.load()
        self.assertEqual(revision, 0)
        self.assertEqual(state.get('refused_attempts', []), [])

    def test_without_the_flag_stop_is_a_room_ruling(self):
        # Why the host must mark it: the room adjudicator reads it as a physical act.
        with self.assertRaises(kit_agent.PendingRuling):
            self.bridge.prepare(STOP, 'stop')

    def test_a_table_talk_turn_commits_as_kit_answering(self):
        line = BRENDON_LINES[4]
        prepared = self.bridge.prepare(line, 'annoyed', table_talk=True)
        plan = self.meta_plan(prepared['input'])
        with self.assertRaisesRegex(InvalidChange, 'turn_mode must be meta'):
            self.bridge.decide('annoyed', {**plan, 'turn_mode': 'banter'})
        self.bridge.decide('annoyed', plan)
        with self.assertRaisesRegex(InvalidChange, 'no NPC hears or answers'):
            self.bridge.finish('annoyed', {'segments': KIT_ANSWER['segments'] + [
                {'speaker': 'Dealer', 'text': 'Tests? We only test our luck here, friend.'}]})
        self.assertEqual(self.bridge.finish('annoyed', KIT_ANSWER)['revision'], 1)
        turn = self.runtime.recent_kit_turns(limit=1)[-1]
        self.assertEqual(turn['player_input'], line)
        self.assertNotIn('You declare', json.dumps(turn, ensure_ascii=False))
        state = self.runtime.load()[1]
        self.assertFalse(state.get('refused_attempts'))

    def test_hidden_facts_still_cannot_leak_in_table_talk(self):
        prepared = self.bridge.prepare('Kit, real talk: is this guy cheating?', 'cheat', table_talk=True)
        plan = self.meta_plan(prepared['input'])
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            self.bridge.decide('cheat', {**plan, 'public_brief': {
                **plan['public_brief'], 'tactic': 'Reveal the doppelganger.'}})
        self.bridge.decide('cheat', plan)
        with self.assertRaisesRegex(InvalidChange, 'private fact'):
            self.bridge.finish('cheat', {'segments': [
                {'speaker': 'Kit', 'text': 'Real talk? The doppelganger is running the table.',
                 'reacts_to': 'is this guy cheating'}]})
        self.assertEqual(self.runtime.load()[0], 0)

    def test_table_talk_carries_no_story_brief(self):
        # A direct question to Kit is answered without the scene's private story brief, so its
        # secrets (the marked deck, the act) cannot be paraphrased into the answer.
        line = 'Is the dealer cheating me?'
        played = self.bridge.prepare(line, 'in-fiction', one_pass=True)
        self.assertIn('story_brief', played['input']['private'])
        self.bridge.abandon('in-fiction')
        for one_pass in (True, False):
            with self.subTest(one_pass=one_pass):
                prepared = self.bridge.prepare(line, f'talk-{one_pass}', one_pass=one_pass, table_talk=True)
                private = prepared['input']['private'] if one_pass else prepared['input']
                self.assertNotIn('story_brief', private)
                text = json.dumps(prepared['input'], ensure_ascii=False)
                self.assertNotIn('marked deck', text.casefold())
                self.assertNotIn('shakedown', text.casefold())
                self.bridge.abandon(f'talk-{one_pass}')

    def test_table_talk_carries_no_claims_list(self):
        # The claims list (each secret's truth and which NPCs know it) stays out of table talk.
        # The whole packet is scanned except dm_context (Kit's DM view, which the leak guards
        # police): the personality core and voice files are included since GPT's #68 removed
        # the 6c marked-card example from them.
        line = 'Is the dealer cheating me?'
        secrets = [phrase for phrase in kit_guards.leak_phrases(self.runtime.source())['phrases']
                   if phrase not in kit_guards.leak_phrases(self.runtime.source())['player_may_name']]
        self.assertIn('marked deck', secrets)
        self.assertIn('doppelganger', secrets)

        def outside_dm_context(packet):
            private = packet.get('private', packet)
            rest = {key: value for key, value in private.items() if key != 'dm_context'}
            return json.dumps([rest, packet.get('public'), packet.get('instructions'),
                               packet.get('table_talk')], ensure_ascii=False).casefold()

        played = self.bridge.prepare(line, 'in-game', one_pass=True)['input']
        self.assertIn('claims_here', played['private'])
        for word in ('marked', 'doppelganger'):
            self.assertIn(word, outside_dm_context(played))
        self.bridge.abandon('in-game')
        for one_pass in (True, False):
            with self.subTest(one_pass=one_pass):
                prepared = self.bridge.prepare(line, f'talk-{one_pass}', one_pass=one_pass, table_talk=True)
                packet = {**prepared['input'], 'instructions': prepared['instructions'],
                          'table_talk': prepared.get('table_talk')}
                self.assertNotIn('claims_here', prepared['input'].get('private', prepared['input']))
                text = outside_dm_context(packet)
                for phrase in secrets:
                    self.assertNotIn(phrase.casefold(), text)
                self.bridge.abandon(f'talk-{one_pass}')

    def test_the_cli_flag_reaches_the_bridge(self):
        out = io.StringIO()
        argv = ['kit_agent', 'prepare', '--db', str(self.path), '--one-pass', '--table-talk',
                '--turn-id', 'cli', '--action', STOP]
        self.runtime.close()
        with mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(out):
            self.assertEqual(kit_agent.main(), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result['stage'], 'one_pass')
        self.assertEqual(result['input']['private']['accepted_public_event'], table_talk_event(STOP))
        self.runtime = Runtime(self.path)


class TableTalkInAnyRoom(unittest.TestCase):
    """General engine: table talk never calls the room's adjudicator, so it works in a room
    with no adjudicator rules at all."""

    def test_table_talk_skips_adjudication(self):
        class NoRoom:
            def resolve(self, *args, **kwargs):
                raise AssertionError('table talk must not be adjudicated')

        source = json.loads(FIXTURE.read_text())
        with tempfile.TemporaryDirectory() as temp:
            runtime = Runtime(Path(temp) / 'kit.sqlite')
            self.addCleanup(runtime.close)
            runtime.initialize(source, 'area_06c')
            prepared = KitChatBridge(runtime, NoRoom()).prepare('What are you?', 'any', table_talk=True)
            self.assertEqual(prepared['input']['accepted_public_event'], 'Table talk to Kit: "What are you?"')
            self.assertEqual(prepared['input']['table_read']['mode_hint'], 'meta')

    def test_the_event_is_the_players_words_to_kit(self):
        self.assertEqual(table_talk_event('  Okay,   let’s stop there. '), 'Table talk to Kit: "Okay, let\'s stop there."')
        resolution = kit_agent.table_talk_resolution('Hello, Kit.')
        self.assertEqual((resolution.kind, resolution.events[0]['tags']), ('social', ['table_talk']))


if __name__ == '__main__':
    unittest.main()
