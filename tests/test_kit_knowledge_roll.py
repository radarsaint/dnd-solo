"""A rolled knowledge check resolves into what the character recalls, never only the roll.

Live failure (#211 playtest at f116075): 'Do I know any old stories about ...?' was not seen as
a knowledge question, the host called History itself, and 'I rolled a 12.' came back as only
'Kit: You roll History: 12.'. Synthetic clock-loft fixture only.
"""
import unittest

from runtime import kit_agent, kit_perform, kit_skills
from runtime.state_context import InvalidChange
from test_kit_agent import RecordingModel
import test_kit_rulings

QUESTION = 'Do I know any old stories about what lives up on the ridge?'
FENCED = ('glass wyrm', 'brine vaults', 'cistern')


class RolledKnowledgeCheck(unittest.TestCase):
    intro = test_kit_rulings.KnowledgeLookup.intro
    _ingest = test_kit_rulings.KnowledgeLookup._ingest
    _bridge = test_kit_rulings.KnowledgeLookup._bridge

    def _roll_echo_complete(self, bridge, prepared, total):
        """The host's failed narration seen live: only the roll."""
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='ruling', focus_actor='none', table_presence='present', turn_mode='meta')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        # v0.11.3: the turn's player words are the roll line, not the earlier question.
        said = 'I rolled a %d' % total
        plan['public_brief'].update(reply_to=said, scope='call')
        output = {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'You roll a %d.' % total, 'reacts_to': said}]}}
        for _ in range(4):
            try:
                return bridge.complete(prepared['turn_id'], output)
            except InvalidChange:
                continue
        self.fail('the engine line never committed')

    def test_every_tier_gets_an_answer_and_a_handoff(self):
        for total, tier in ((4, 'low'), (12, 'middle'), (18, 'high')):
            with self.subTest(total=total):
                _db, _runtime, bridge = self._bridge(local=False)
                called = bridge.prepare(QUESTION, one_pass=True)
                self.assertEqual(called.get('stage'), 'called_roll', called)
                self.assertIn('Roll History.', called.get('spoken') or '')
                rolled = bridge.prepare('I rolled a %d.' % total, one_pass=True)
                self.assertEqual(rolled.get('stage'), 'one_pass', rolled)
                self.assertEqual((rolled.get('check_outcome') or {}).get('tier'), tier, rolled)
                self.assertIn('%s tier' % tier, rolled.get('knowledge') or '')
                spoken = self._roll_echo_complete(bridge, rolled, total).get('spoken') or ''
                self.assertNotRegex(spoken, r'(?i)^kit: you roll')
                self.assertIn('What do you do?', spoken)
                self.assertNotIn('DC', spoken)
                self.assertNotIn('table talk', spoken.casefold())
                for term in FENCED:
                    self.assertNotIn(term, spoken.casefold())

    def test_old_stories_is_a_history_question(self):
        self.assertTrue(kit_perform.is_knowledge_question(QUESTION))
        self.assertEqual(kit_skills.skill_for_intent(QUESTION), 'history')
        self.assertIsNone(kit_perform.baseline_cover(QUESTION, {}, ['You are from the town of Lampwick.']))


class KnowledgeRollRouting(unittest.TestCase):

    def test_a_host_called_recall_skill_resolves_as_knowledge(self):
        for skill in ('history', 'arcana', 'religion', 'nature'):
            self.assertTrue(kit_agent.is_knowledge_roll(
                {'skill': skill, 'called_turn': 't1', 'asked': 'Have the old rites here a name?'}), skill)
        self.assertTrue(kit_agent.is_knowledge_roll(
            {'skill': 'investigation', 'called_turn': 't1', 'asked': 'What do I know about the guild?'}))
        self.assertFalse(kit_agent.is_knowledge_roll(
            {'skill': 'investigation', 'called_turn': 't1', 'asked': 'I search the desk.'}))
        # An act waiting on its roll (a climb, a search) resolves as that act.
        self.assertFalse(kit_agent.is_knowledge_roll(
            {'skill': 'history', 'called_turn': 'revision 4', 'action': 'I read the plaque.', 'asked': 'x'}))
        self.assertTrue(kit_agent.is_knowledge_roll({'skill': 'history', 'reason': 'knowledge'}))

    def test_a_reply_that_is_only_the_roll_is_rejected(self):
        for only in ('Kit: You roll History: 12.', 'Narrator: You roll Arcana: 4.', 'You rolled religion 18'):
            with self.assertRaises(InvalidChange):
                kit_agent.check_not_only_roll(only)
        kit_agent.check_not_only_roll('Kit: You roll History: 12. Only tavern talk comes back. What do you do?')
        self.assertIn('check_not_only_roll', kit_agent.VALIDATOR_KINDS)

    def test_recall_line_has_something_for_every_tier_and_keeps_the_fence(self):
        facts = {'spoiler_fence': ['Glass Wyrm'], 'visible': [], 'party': [],
                 'section': ['A glass wyrm sleeps under the ridge.']}
        for tier in ('low', 'middle', 'high'):
            line = kit_agent.knowledge_recall_line(facts, tier, QUESTION)
            self.assertTrue(line.startswith('Kit: '), line)
            self.assertIn('What do you do?', line)
            self.assertNotIn('wyrm', line.casefold())


if __name__ == '__main__':
    unittest.main()


class HostCalledRecall(unittest.TestCase):
    intro = test_kit_rulings.KnowledgeLookup.intro
    _ingest = test_kit_rulings.KnowledgeLookup._ingest
    _bridge = test_kit_rulings.KnowledgeLookup._bridge

    def test_a_history_roll_the_host_called_resolves_as_recall(self):
        _db, runtime, bridge = self._bridge(local=False)
        line = 'Whose names are carved on the brass rail, I wonder?'
        plan = {'roll_call': {'skill': 'history', 'mode': 'normal', 'target': 'none',
                              'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}}
        revision, _ = runtime.load()
        runtime.commit('t-call', revision, kit_agent.turn_events(
            runtime, {'action': line, 'events': [{'type': 'beat', 'tags': ['call'], 'evidence': 'Call.'}]},
            plan, 't-call'))
        pending = runtime.load()[1].get('pending_check') or {}
        self.assertEqual(pending.get('skill'), 'history', pending)
        self.assertEqual(pending.get('asked'), line)
        rolled = bridge.prepare('I rolled a 12.', one_pass=True)
        self.assertEqual((rolled.get('check_outcome') or {}).get('tier'), 'middle', rolled)
        self.assertNotEqual((rolled.get('spoken') or '').strip(), 'Kit: You roll History: 12.')
