"""Kit's memory (relevance-selected episodes and the callback carrier) and her
evidence-cited player notes (including host-recorded feedback)."""
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import kit_agent
from runtime.kit_agent import (KitAgent, KitChatBridge, MEMORY_LIMIT, Room6CAdjudicator,
                               select_episodes)
from runtime.state_context import InvalidChange, Runtime, STATE_SCHEMA_VERSION, encode
from test_kit_agent import (FIXTURE, KIT_CHOICE, QUIET_EXCHANGE_SPEECH, RecordingModel, exchange_speech,
                            with_check)

NO_NOTE = {'note': 'none', 'evidence_turns': [], 'replaces': 'none'}
COIN = 'I say, flipping my lucky silver coin onto the table: this coin never loses.'
COIN_LINE = 'That coin of yours has a greedy shine'
COIN_SPEECH = with_check({'segments': [
    {'speaker': 'Narrator', 'text': 'The dealer’s eyes follow the spinning coin until it settles.'},
    {'speaker': 'Dealer', 'text': (f'{COIN_LINE}, friend. Keep it close; tables like this one have '
                                   'a way of learning what a guest values most, and I am a very '
                                   'attentive student of such things. Will you sit?')}]})
# Picks up the earlier coin moment: "coin" and "shine" return.
CALLBACK_SPEECH = with_check({'segments': [
    {'speaker': 'Narrator', 'text': 'He deals you in, and his glance drops once to the pocket where the coin went.'},
    {'speaker': 'Dealer', 'text': ('Before the first card, that lucky coin of yours. Put it in the pot and I '
                                   'will match it with gold, since you seem so sure of its shine. Or keep '
                                   'it and play for copper like everyone else. Your choice.')}]})
# A competent reply that ignores the callback entirely.
FORGETFUL_SPEECH = with_check({'segments': [
    {'speaker': 'Narrator', 'text': 'He deals you in with a practiced snap of the wrist.'},
    {'speaker': 'Dealer', 'text': ('Ante is two silver and the house deals. Aces high, no questions about '
                                   'the order of the deck, and nobody leaves mid-hand. Those are the rules '
                                   'of my table. Do we understand each other?')}]})


def episode(turn_id, text, actor='uktarl', anchor='scene', basis='scene_state'):
    return {'turn_id': turn_id, 'player_input': text, 'player_bid': f'The player said: {text}',
            'kit_choice': 'Kit keeps it moving.', 'actor_ref': actor, 'story_anchor': anchor,
            'story_basis': basis, 'public_event': 'You address the figures at the card table.',
            'brief': {'reply_to': text, 'scope': 'exchange'}}


class Scripted(RecordingModel):
    """RecordingModel with a quiet NPC reply, an editable next plan, and queued speeches."""
    def __init__(self):
        super().__init__()
        self.edit = None
        self.speeches = []

    def plan(self, payload):
        plan = super().plan(payload)
        plan.update(memory_refs=[], move='npc_reply', table_presence='quiet')
        if self.edit:
            edit, self.edit = self.edit, None
            edit(plan, payload)
        return plan

    def perform(self, payload, performance_variant='current'):
        super().perform(payload, performance_variant)
        # Rotate the default reply: a line recycled from a recent turn is rejected as padding.
        self.performed += 1
        return json.loads(json.dumps(self.speeches.pop(0) if self.speeches
                                     else exchange_speech(self.performed - 1, kit=False)))


class MemoryTestCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'kit.sqlite'
        self.runtime = Runtime(self.path)
        self.addCleanup(lambda: self.runtime.close())
        self.runtime.initialize(json.loads(FIXTURE.read_text()), 'area_06c')
        self.model = Scripted()
        self.adjudicator = Room6CAdjudicator(perception=0, insight=0, roll=lambda: 20)
        self.agent = KitAgent(self.runtime, self.model, self.adjudicator)
        self.bridge = KitChatBridge(self.runtime, self.adjudicator)

    def play(self, action, turn_id, speech=None, edit=None):
        if speech:
            self.model.speeches.append(speech)
        self.model.edit = edit
        return self.agent.turn(action, turn_id)

    def coin_then_filler(self, filler=MEMORY_LIMIT):
        self.play(COIN, 'coin', COIN_SPEECH)
        for index in range(filler):
            self.play(f'Tell me about the weather {index}?', f'filler-{index}')


class EpisodeMemoryTests(MemoryTestCase):
    def test_episode_saves_kit_choice_and_player_bid(self):
        self.play(COIN, 'coin', COIN_SPEECH)
        saved = self.runtime.load()[1]['kit']['episodes'][0]
        self.assertEqual(saved['kit_choice'], KIT_CHOICE)
        self.assertEqual(saved['player_bid'], f'The player declared: {COIN}')
        self.assertEqual((saved['actor_ref'], saved['story_anchor']), ('uktarl', 'scene'))

    def test_relevant_earlier_episode_beats_more_recent_irrelevant_ones(self):
        episodes = [episode('coin', COIN, actor='bandit_a')]
        # The recent talk is with nobody in particular, so only words can make 'coin' relevant.
        episodes += [episode(f'e{i}', f'Weather talk {i}', actor='none') for i in range(12)]
        chosen = [item['turn_id'] for item in select_episodes(episodes, 'Can my lucky coin buy in?')]
        self.assertIn('coin', chosen)
        self.assertEqual(chosen[-2:], ['e10', 'e11'])  # the last two always stay
        # Irrelevant history is left out, not padded in.
        self.assertEqual(chosen, ['coin', 'e10', 'e11'])
        # Actor and story thread also count, and the order stays chronological.
        episodes[-1].update(actor_ref='bandit_a', story_anchor='level', story_basis='pressure_here')
        episodes[3].update(story_anchor='level', story_basis='pressure_here')
        chosen = [item['turn_id'] for item in select_episodes(episodes, 'Hmm.')]
        self.assertEqual(chosen, ['coin', 'e2', 'e10', 'e11'])
        self.assertLessEqual(len(select_episodes(episodes * 3, 'weather talk')), MEMORY_LIMIT)

    def test_relevant_old_episode_reaches_the_decision_and_can_be_cited(self):
        self.coin_then_filler(MEMORY_LIMIT + 2)
        prepared = self.bridge.prepare('Deal me in; my lucky coin is my stake.', 'stake')
        seen = [item['turn_id'] for item in prepared['input']['kit_state']['episodes']]
        self.assertIn('coin', seen)
        self.assertNotIn('coin', [item['turn_id'] for item in
                                  self.runtime.load()[1]['kit']['episodes'][-MEMORY_LIMIT:]])
        coin = next(item for item in prepared['input']['kit_state']['episodes']
                    if item['turn_id'] == 'coin')
        self.assertIn(COIN_LINE, coin['spoken'])  # the public words, for a callback
        plan = self.model.plan(prepared['input'])
        plan['memory_refs'] = ['filler-0']  # an episode Kit was not shown
        with self.assertRaisesRegex(InvalidChange, 'Unknown or invalid memory reference'):
            self.bridge.decide('stake', plan)
        plan['memory_refs'] = ['coin']
        self.bridge.decide('stake', plan)


class CallbackTests(MemoryTestCase):
    def _callback_turn(self, callback, refs=('coin',)):
        prepared = self.bridge.prepare('Deal me in.', 'deal')
        plan = self.model.plan(prepared['input'])
        plan['memory_refs'] = list(refs)
        plan['public_brief']['callback'] = callback
        return plan

    def test_callback_must_quote_public_words_from_a_cited_turn(self):
        self.play(COIN, 'coin', COIN_SPEECH)
        self.play('What are the stakes?', 'stakes')
        for callback, refs, reason in [
            ('your coin is cursed', ('coin',), 'must quote words said or shown in public'),
            (COIN_LINE, ('stakes',), 'must quote words said or shown in public'),
            (COIN_LINE, (), 'listed in memory_refs'),
            ('coin', ('coin',), 'at least two words'),
            ('x ' * 90, ('coin',), 'exceeds 160'),
        ]:
            with self.subTest(callback=callback[:20], refs=refs), \
                    self.assertRaisesRegex(InvalidChange, reason):
                self.bridge.decide('deal', self._callback_turn(callback, refs))
        # The player's own earlier words, or the dealer's, quoted loosely for case and quotes.
        self.bridge.decide('deal', self._callback_turn('my LUCKY silver coin'))

    def test_callback_reaches_performer_with_its_public_source_but_no_private_memory(self):
        self.play(COIN, 'coin', COIN_SPEECH)
        self.play('What are the stakes?', 'stakes')
        payload = self.bridge.decide('deal', self._callback_turn(COIN_LINE))['input']
        self.assertEqual(payload['selected_move']['brief']['callback'], COIN_LINE)
        self.assertIn(COIN_LINE, payload['callback_source']['line'])
        self.assertEqual(payload['callback_source']['player_input'], COIN)
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(KIT_CHOICE, text)
        self.assertNotIn('The player declared', text)  # the episode's private player_bid
        self.assertNotIn('kit_state', payload)
        self.assertNotIn('episodes', text)

    def test_staged_performer_is_told_how_to_use_callback(self):
        self.play(COIN, 'coin', COIN_SPEECH)
        instructions = self.bridge.decide('deal', self._callback_turn(COIN_LINE))['instructions']
        for phrase in ('callback', 'callback_source', 'reacting from their own motives',
                       'without re-quoting it at length'):
            self.assertIn(phrase, instructions)

    def test_performance_that_ignores_the_callback_is_rejected(self):
        self.play(COIN, 'coin', COIN_SPEECH)
        plan = self._callback_turn(COIN_LINE)
        plan.update(move='npc_reply', table_presence='quiet')
        self.bridge.decide('deal', plan)
        with self.assertRaisesRegex(InvalidChange, 'ignored the callback'):
            self.bridge.finish('deal', FORGETFUL_SPEECH)
        self.assertEqual(self.runtime.load()[0], 1)
        result = self.bridge.finish('deal', CALLBACK_SPEECH)
        self.assertIn('lucky coin', result['spoken'])
        # The callback is remembered with the new episode.
        self.assertEqual(self.runtime.load()[1]['kit']['episodes'][-1]['brief']['callback'], COIN_LINE)

    def test_callback_quoting_a_players_secret_word_passes_the_brief_leak_check(self):
        self.play('I accuse that player of being a doppelganger.', 'accuse')
        prepared = self.bridge.prepare('Deal me in.', 'deal')
        plan = self.model.plan(prepared['input'])
        plan.update(memory_refs=['accuse'])
        plan['public_brief']['callback'] = 'being a doppelganger'
        self.bridge.decide('deal', plan)

    def test_one_pass_host_is_told_how_to_fill_and_use_callback(self):
        self.play(COIN, 'coin', COIN_SPEECH)
        prepared = self.bridge.prepare('Deal me in.', 'fast', one_pass=True)
        brief_schema = prepared['schema']['properties']['decision']['properties']['public_brief']
        self.assertIn('callback', brief_schema['required'])
        self.assertIn('player_note', prepared['schema']['properties']['decision']['required'])
        for phrase in ('callback', 'memory_refs', 'player_notes', 'evidence_turns', 'never a score',
                       'Do not copy improv_read, appraisal, episode, or player note text'):
            self.assertIn(phrase, prepared['instructions'])
        plan = self.model.plan(prepared['input']['private'])
        plan.update(memory_refs=['coin'], move='npc_reply', table_presence='quiet')
        plan['public_brief']['callback'] = COIN_LINE
        with self.assertRaisesRegex(InvalidChange, 'ignored the callback'):
            self.bridge.complete('fast', {'decision': plan, 'performance': FORGETFUL_SPEECH})
        self.assertEqual(self.bridge.complete('fast', {'decision': plan,
                                                       'performance': CALLBACK_SPEECH})['revision'], 2)


class PlayerNoteTests(MemoryTestCase):
    FEEDBACK = 'Fewer menus of options please; just let the dealer push me.'

    def test_feedback_is_stored_with_evidence_and_reaches_only_the_next_decision(self):
        self.play('I take a seat.', 'seat')
        recorded = self.bridge.feedback(self.FEEDBACK)
        self.assertEqual(recorded['stage'], 'feedback_recorded')
        self.assertEqual(recorded['note'], {'id': 'n2', 'source': 'feedback', 'note': self.FEEDBACK,
                                            'evidence_turns': ['seat']})
        self.assertEqual(self.runtime.load()[0], 2)
        self.assertEqual(self.runtime.recent_kit_turns()[-1]['player_input'], 'I take a seat.')
        # Retrying the same comment about the same turn does not duplicate it.
        self.assertEqual(self.bridge.feedback(self.FEEDBACK)['revision'], 2)
        self.assertEqual(len(self.runtime.player_notes()), 1)
        prepared = self.bridge.prepare('What are the stakes?', 'stakes')
        self.assertEqual(prepared['input']['kit_state']['player_notes'][0]['note'], self.FEEDBACK)
        plan = self.model.plan(prepared['input'])
        copied = {**plan, 'public_brief': {**plan['public_brief'], 'tactic': self.FEEDBACK}}
        with self.assertRaisesRegex(InvalidChange, 'copies a private player note'):
            self.bridge.decide('stakes', copied)
        plan['public_brief']['kit_focus'] = 'Let the dealer press the visitor toward one hard choice.'
        payload = self.bridge.decide('stakes', plan)['input']
        self.assertNotIn(self.FEEDBACK, json.dumps(payload, ensure_ascii=False))
        self.assertNotIn('player_notes', json.dumps(payload))
        self.bridge.finish('stakes', self.model.perform(payload))

    def test_feedback_needs_committed_evidence_and_is_not_a_score(self):
        with self.assertRaisesRegex(InvalidChange, 'play the opening first'):
            self.bridge.feedback(self.FEEDBACK)
        self.play('I take a seat.', 'seat')
        for text, evidence, reason in [
            (self.FEEDBACK, ['never-played'], 'cite 1–4 committed turn IDs'),
            (self.FEEDBACK, [], 'cite 1–4 committed turn IDs'),
            ('Rapport with Kit: 7/10', None, 'not a score'),
            ('', None, '1–300 characters'),
        ]:
            with self.subTest(text=text, evidence=evidence), self.assertRaisesRegex(InvalidChange, reason):
                self.bridge.feedback(text, evidence)
        self.assertEqual(self.runtime.player_notes(), [])
        self.assertEqual(self.runtime.load()[0], 1)

    def test_decision_notes_need_evidence_and_may_cite_this_turn(self):
        self.play('I take a seat.', 'seat')
        note = 'Accepted the dealer’s invitation to sit at once.'
        prepared = self.bridge.prepare('Deal me in, then.', 'deal')
        plan = self.model.plan(prepared['input'])
        for bad, reason in [
            ({'note': note, 'evidence_turns': [], 'replaces': 'none'}, 'must cite'),
            ({'note': note, 'evidence_turns': ['future-turn'], 'replaces': 'none'}, 'must cite'),
            ({'note': 'none', 'evidence_turns': ['seat'], 'replaces': 'none'}, 'no evidence'),
            ({'note': 'Likes Kit: affection 3', 'evidence_turns': ['seat'], 'replaces': 'none'}, 'not a score'),
            ({'note': note, 'evidence_turns': ['seat'], 'replaces': 'n99'}, 'unknown note'),
            ({'note': note}, 'Invalid player_note'),
        ]:
            with self.subTest(bad=bad), self.assertRaisesRegex(InvalidChange, reason):
                self.bridge.decide('deal', {**plan, 'player_note': bad})
        plan['player_note'] = {'note': note, 'evidence_turns': ['seat', 'this_turn'], 'replaces': 'none'}
        payload = self.bridge.decide('deal', plan)['input']
        self.assertNotIn(note, json.dumps(payload, ensure_ascii=False))
        self.bridge.finish('deal', self.model.perform(payload))
        self.assertEqual(self.runtime.player_notes(), [
            {'id': 'n2', 'source': 'observed', 'note': note, 'evidence_turns': ['seat', 'deal']}])

    def test_new_behavior_can_retire_an_observed_note_but_not_feedback(self):
        self.play('I take a seat.', 'seat', edit=lambda plan, _: plan.update(player_note={
            'note': 'Accepts the dealer’s invitations readily.', 'evidence_turns': ['this_turn'],
            'replaces': 'none'}))
        self.bridge.feedback(self.FEEDBACK)
        self.assertEqual([n['id'] for n in self.runtime.player_notes()], ['n1', 'n2'])
        prepared = self.bridge.prepare('I tell him no: I refuse your game.', 'refuse')
        plan = self.model.plan(prepared['input'])
        with self.assertRaisesRegex(InvalidChange, 'Only new feedback'):
            self.bridge.decide('refuse', {**plan, 'player_note': {
                'note': 'Wants more options after all.', 'evidence_turns': ['this_turn'], 'replaces': 'n2'}})
        plan['player_note'] = {'note': 'Refused the dealer’s game outright.',
                               'evidence_turns': ['this_turn'], 'replaces': 'n1'}
        self.bridge.finish('refuse', self.model.perform(self.bridge.decide('refuse', plan)['input']))
        self.assertEqual([(n['id'], n['source']) for n in self.runtime.player_notes()],
                         [('n2', 'feedback'), ('n3', 'observed')])
        # The player can supersede their own feedback.
        self.bridge.feedback('Menus are fine again.', ['refuse'], replaces='n2')
        self.assertEqual([n['id'] for n in self.runtime.player_notes()], ['n3', 'n4'])

    def test_memory_ablation_hides_episodes_and_notes(self):
        self.play('I take a seat.', 'seat')
        self.bridge.feedback(self.FEEDBACK)
        prepared = self.bridge.prepare('What are the stakes?', 'blind', use_memory=False)
        self.assertEqual(prepared['input']['kit_state']['player_notes'], [])
        self.assertEqual(prepared['input']['kit_state']['episodes'], [])
        self.assertEqual(len(self.runtime.player_notes()), 1)

    def _cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['kit_agent', *argv, '--db', str(self.path)]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = kit_agent.main()
        return code, out.getvalue(), err.getvalue()

    def test_cli_feedback_and_notes_commands(self):
        self.play('I take a seat.', 'seat')
        self.runtime.close()
        try:
            code, _, err = self._cli('feedback', '--text', 'Score: 9/10')
            self.assertEqual(code, 2)
            self.assertIn('not a score', json.loads(err)['message'])
            code, out, _ = self._cli('feedback', '--text', self.FEEDBACK, '--evidence', 'seat')
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)['note']['evidence_turns'], ['seat'])
            self.assertIn('Do not show', json.loads(out)['host_note'])
            code, out, _ = self._cli('notes')
            self.assertEqual([n['note'] for n in json.loads(out)], [self.FEEDBACK])
        finally:
            self.runtime = Runtime(self.path)


class MigrationTests(MemoryTestCase):
    def _downgrade_snapshots(self):
        """Rewrite stored snapshots to the version 1 shape an older DB would have."""
        db = sqlite3.connect(self.path)
        for revision, body in db.execute('SELECT revision, body FROM snapshots').fetchall():
            state = json.loads(body)
            state['schema_version'] = 1
            state['kit'].pop('player_notes')
            for item in state['kit']['episodes']:
                for key in ('player_bid', 'kit_choice', 'actor_ref', 'story_anchor', 'story_basis'):
                    item.pop(key)
            db.execute('UPDATE snapshots SET body=? WHERE revision=?', (json.dumps(state), revision))
        db.commit()
        db.close()

    def test_version_1_database_upgrades_on_load_and_keeps_playing(self):
        self.play(COIN, 'coin', COIN_SPEECH)
        self.runtime.close()
        self._downgrade_snapshots()
        self.runtime = Runtime(self.path)
        self.agent.runtime = self.bridge.runtime = self.runtime
        revision, state = self.runtime.load()
        self.assertEqual((revision, state['schema_version']), (1, STATE_SCHEMA_VERSION))
        self.assertEqual(state['kit']['player_notes'], [])
        self.assertIsNone(state['kit']['episodes'][0]['kit_choice'])  # unknown, not guessed
        # Old episodes still take part in relevance selection and callbacks.
        prepared = self.bridge.prepare('Deal me in; my lucky coin is my stake.', 'deal')
        self.assertEqual(prepared['input']['kit_state']['episodes'][0]['turn_id'], 'coin')
        plan = self.model.plan(prepared['input'])
        plan.update(memory_refs=['coin'], move='npc_reply', table_presence='quiet')
        plan['public_brief']['callback'] = COIN_LINE
        self.bridge.decide('deal', plan)
        self.bridge.finish('deal', CALLBACK_SPEECH)
        self.bridge.feedback('More of the dealer, please.')
        db = sqlite3.connect(self.path)
        stored = {rev: json.loads(body)['schema_version']
                  for rev, body in db.execute('SELECT revision, body FROM snapshots')}
        db.close()
        self.assertEqual(stored, {0: 1, 1: 1, 2: 2, 3: 2})  # history is not rewritten
        self.assertEqual(self.runtime.load()[1]['kit']['episodes'][-1]['kit_choice'], KIT_CHOICE)

    def test_decision_saved_before_the_upgrade_can_still_finish(self):
        self.play('I take a seat.', 'seat')
        prepared = self.bridge.prepare('What are the stakes?', 'old-plan')
        plan = self.model.plan(prepared['input'])
        del plan['player_note']
        del plan['public_brief']['callback']
        self.runtime.db.execute('UPDATE kit_pending SET plan=? WHERE turn_id=?',
                                (encode(plan), 'old-plan'))
        self.runtime.db.commit()
        self.assertEqual(self.bridge.finish('old-plan', QUIET_EXCHANGE_SPEECH)['revision'], 2)
        self.assertEqual(self.runtime.player_notes(), [])


if __name__ == '__main__':
    unittest.main()
