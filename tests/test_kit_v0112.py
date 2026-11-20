"""v0.11.2: object use is not a fight, no host-tool names in player text, refusals name the
field, a hand-resolved beat recorded into the engine, a pending roll outlasts table talk,
a missed scan keeps the scene.

Synthetic road scene only (test_kit_turn_spine.Scene). No published adventure text.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_moves, kit_perform, state_context
from runtime.kit_agent import (SIMPLE_ACT_LINE, PendingRuling, RoomAdjudicator, check_no_internal_labels,
                               record_hand_beat, rejection_fix_line)
from runtime.state_context import InvalidChange

from test_kit_scene_contract_gpt import LOW_SHEET
from test_kit_turn_spine import Scene

ROOT = Path(__file__).resolve().parents[1]
TOSS = 'I stay where I am and toss a stone into the left thicket, ready to cast.'


class ObjectUseIsNotAFight(Scene):
    def test_object_lines_are_use(self):
        for line in (TOSS, 'I throw a pebble at the far wall.', 'I knock on the door.', 'I push the crate into the pit.',
                     'I poke the brush with my staff.', 'I drop a coin into the well.'):
            self.assertTrue(kit_moves.object_act(line), line)
            self.assertEqual(kit_moves.classify(line), 'use', line)

    def test_harm_at_a_creature_is_still_a_fight(self):
        for line in ('I throw a rock at the bandit to hurt him.', 'I attack the guard with my staff.'):
            self.assertFalse(kit_moves.object_act(line), line)
        self.assertEqual(RoomAdjudicator.__dict__ and kit_moves.classify('I attack the guard with my staff.'), 'fight')

    def test_tossing_a_stone_happens_without_a_combat_refusal(self):
        self._start(LOW_SHEET)
        result, text = self.say(TOSS)
        self.assertEqual(result['stage'], 'one_pass', result)
        self.assertIn(SIMPLE_ACT_LINE, text)
        self.assertNotIn('attacking', text)
        self.assertNotIn('How are you doing that', text)

    def test_readied_spell_is_not_a_cast(self):
        self._start(LOW_SHEET)
        _result, text = self.say('I wait by the cart, ready to cast.')
        self.assertNotIn('cast a spell', text)


class NoHostToolNames(unittest.TestCase):
    def test_refusals_carry_no_tool_name(self):
        for message in ('Who are you attacking, and with what? Name the target and the weapon or spell '
                        '(with the Avrae roll if you have it). No turn was committed.',
                        'Roll the attack for your dagger in Avrae.', "Roll its damage in Avrae (1d6), then say so.",
                        'The blow waits on its Avrae attack roll.'):
            said = str(PendingRuling(message))
            self.assertNotIn('avrae', said.casefold(), said)
            self.assertIsNone(kit_moves.internal_label(said), said)

    def test_speaking_check_rejects_tool_and_file_names(self):
        for line in ('Kit: Roll it in Avrae and tell me.', 'Kit: I saved that to kit.sqlite.',
                     'Kit: Your turn_id is open.', 'Kit: Check o.json for the result.'):
            self.assertTrue(kit_moves.internal_label(line), line)
            self.assertTrue(any('host-tool' in p for p in kit_moves.speaking_problems(line)), line)
            with self.assertRaises(InvalidChange):
                check_no_internal_labels(line)

    def test_in_fiction_words_pass(self):
        self.assertIsNone(kit_moves.internal_label('Narrator: The rope bridge sways over the engine house.'))


class RefusalsNameTheField(unittest.TestCase):
    def test_fenced_spoiler_quotes_the_words_and_the_field(self):
        problems = kit_perform.performance_problems(
            {'segments': [{'speaker': 'Narrator', 'text': 'The road is quiet.'},
                          {'speaker': 'Narrator', 'text': 'Far off, the Glass Warden stirs in its hall.'}]},
            {'kind': 'lookup', 'spoiler_fence': ['Glass Warden']})
        fenced = [p for p in problems if 'fenced spoiler' in p]
        self.assertTrue(fenced, problems)
        self.assertIn('performance.segments[1].text', fenced[0])
        self.assertIn('"Far off, the Glass Warden stirs in its"', fenced[0])
        self.assertIn('Fix:', fenced[0])

    def test_no_generic_fix_line(self):
        line = rejection_fix_line(InvalidChange('a DC or bonus was spoken'))
        self.assertNotIn('field named above', line)
        self.assertIn('performance.segments', line)
        self.assertIn('decision.kit_choice',
                      rejection_fix_line(InvalidChange('decision.kit_choice is not one of the offered moves')))

    def test_changed_event_names_the_field(self):
        staged = {'action': 'I wait.', 'public_event': 'You wait.', 'events': [{'type': 'beat', 'tags': []}]}
        said = state_context._event_changed(staged, {'player_input': 'I wait.', 'public_event': 'You run.'},
                                            [{'type': 'beat', 'tags': []}], staged['events'], False, False)
        self.assertIn('public_event', said)
        self.assertIn('Fix:', said)
        said = state_context._event_changed(staged, {'player_input': 'I run.', 'public_event': 'You wait.'},
                                            staged['events'], staged['events'], False, False)
        self.assertIn('player_input', said)


class RecordHandResolvedBeat(Scene):
    def test_record_reveals_and_flags_the_encounter(self):
        self._start(LOW_SHEET)
        self.assertEqual(self.runtime.load()[1]['actors']['bandit_1']['status'] if 'bandit_1' in
                         self.runtime.load()[1]['actors'] else 'hidden', 'hidden')
        out = record_hand_beat(self.runtime.path, {
            'happened': 'A tossed stone flushed the bandits from the ditch; they rush the caravan.',
            'revealed': ['bandit'], 'facts': ['The bandits are out of hiding.'], 'encounter': 'started'})
        self.assertEqual(out['stage'], 'recorded', out)
        state = self.runtime.load()[1]
        self.assertTrue(state['encounter']['active'])
        self.assertIn('bandit', state['revealed_terms'])
        hidden = [k for k, a in state['actors'].items() if 'bandit' in k and a.get('status') == 'hidden']
        self.assertEqual(hidden, [])
        self.assertEqual(kit_perform._unfenced(self.runtime, ['Bandits', 'Glass Warden']), ['Glass Warden'])

    def test_record_names_a_bad_field(self):
        self._start(LOW_SHEET)
        with self.assertRaisesRegex(InvalidChange, 'unknown field mood'):
            record_hand_beat(self.runtime.path, {'happened': 'x', 'mood': 'tense'})
        with self.assertRaisesRegex(InvalidChange, 'hand_beat.encounter'):
            record_hand_beat(self.runtime.path, {'happened': 'x', 'encounter': 'maybe'})

    def test_rules_question_mid_encounter_is_table_talk(self):
        self._start(LOW_SHEET)
        record_hand_beat(self.runtime.path, {'happened': 'The bandits attack.', 'revealed': ['bandit'],
                                              'encounter': 'started'})
        result, text = self.say('Can I stay hidden if I use my bonus action to hide?')
        self.assertTrue(result.get('player_move', '').startswith('ask_dm'), result.get('player_move'))
        self.assertNotIn('speak to the room', text)
        self.assertIn('An encounter is on', json.dumps(result))

    def test_cli(self):
        self._start(LOW_SHEET)
        with tempfile.TemporaryDirectory() as folder:
            beat = Path(folder) / 'beat.json'
            beat.write_text(json.dumps({'happened': 'The bandits charge.', 'encounter': 'started'}))
            done = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'record', '--db', str(self.runtime.path),
                                   '--input-file', str(beat)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(done.stdout)['stage'], 'recorded', done.stdout + done.stderr)


class PendingRollOutlastsTableTalk(Scene):
    def test_rules_questions_route_ask_dm_whatever_the_stance(self):
        for line in ('Do I need to roll for that?', 'Can I use my bonus action to hide?',
                     'I keep low. Do I need to roll to stay hidden?'):
            self.assertEqual(kit_moves.classify(line), 'ask_dm', line)

    def test_table_talk_keeps_the_call(self):
        for event in ({'type': 'beat', 'tags': ['table_talk']}, {'type': 'beat', 'tags': ['table_talk', 'ask_dm']}):
            self.assertTrue(state_context.keeps_pending_check(event))
        self.assertFalse(state_context.keeps_pending_check({'type': 'beat', 'tags': ['social']}))

    def test_bare_number_after_a_question_answers_the_call(self):
        self._start(LOW_SHEET)
        self.call_old('perception')
        result, text = self.say('Do I need to roll for that?')
        self.assertTrue(result.get('player_move', '').startswith('ask_dm'), result.get('player_move'))
        self.assertNotIn('speak to the room', text)
        revision, _ = self.runtime.load()
        self.runtime.commit('talk', revision, [{'type': 'beat', 'tags': ['table_talk', 'ask_dm'],
                                                'evidence': 'Rules question answered by Kit.'}])
        self.assertEqual(self.pending()['skill'], 'perception')
        for turn_id, in self.runtime.db.execute('SELECT turn_id FROM kit_pending').fetchall():
            self.runtime.discard_pending_kit_turn(turn_id)
        result, text = self.say('I rolled 18')
        self.assertIsNone(self.pending(), result)
        self.assertNotIn('Table talk', text)


class MissKeepsTheScene(Scene):
    def test_miss_line_shows_what_is_there(self):
        self._start(LOW_SHEET)
        adjudicator = self.bridge.adjudicator
        adjudicator.source = self.runtime.source()
        line = adjudicator._miss_texture('I watch the road ahead.', self.runtime.load()[1])
        self.assertNotIn('do not spot anyone', line)
        self.assertIn('road', line.casefold())
        self.assertFalse(kit_moves.bare_result(line))

    def test_miss_without_visible_facts_still_has_a_place(self):
        adjudicator = RoomAdjudicator(roll=lambda: 10)
        adjudicator.source = {'facts': {}, 'areas': {'yard': {'called': 'the yard'}}}
        self.assertIn('the yard', adjudicator._miss_texture('I look around.', {'area': 'yard'}))


if __name__ == '__main__':
    unittest.main()
