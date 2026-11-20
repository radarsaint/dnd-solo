"""A knowledge question never comes back as the player's own words under an engine label.

Live failure (#211 playtest): a local character asked what they know about their home village
inside a move line; the host's narration failed and the engine line spoke
'Narrator: Table talk to Kit: "<the player's words>"'. The engine line now answers the
background baseline with no roll (or hands off), and no engine label reaches the player.
Synthetic clock-loft fixture only.
"""
import unittest

from runtime import kit_agent
from runtime.state_context import InvalidChange
from test_kit_agent import RecordingModel
import test_kit_rulings

MIXED = 'I follow, keeping close. What do I know about this town, growing up here? Anything going on lately?'


class KnowledgeEchoNeverReachesThePlayer(unittest.TestCase):
    intro = test_kit_rulings.KnowledgeLookup.intro
    _ingest = test_kit_rulings.KnowledgeLookup._ingest
    _bridge = test_kit_rulings.KnowledgeLookup._bridge

    def _echo_complete(self, bridge, prepared):
        """The host's failed narration seen live: the player's words under the label."""
        plan = RecordingModel().plan(prepared['input']['private'])
        plan.update(move='ruling', focus_actor='none', table_presence='present', turn_mode='meta')
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan['public_brief'].update(reply_to='what do I know about this town', scope='call')
        output = {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': 'Table talk to Kit: "%s"' % MIXED, 'reacts_to': 'none'}]}}
        for _ in range(4):
            try:
                return bridge.complete(prepared['turn_id'], output)
            except InvalidChange:
                continue
        self.fail('the engine line never committed')

    def test_mixed_move_and_local_question_gets_a_baseline_answer(self):
        _db, _runtime, bridge = self._bridge(local=True)
        prepared = bridge.prepare(MIXED, one_pass=True)
        self.assertEqual(prepared.get('stage'), 'one_pass', prepared)
        self.assertEqual(((prepared.get('host_facts') or {}).get('knowledge') or {}).get('gate'), 'baseline')
        self.assertIn('no roll', prepared.get('knowledge') or '')
        record = self._echo_complete(bridge, prepared)
        spoken = record.get('spoken') or ''
        self.assertTrue(spoken.startswith('Kit:'), spoken)
        self.assertIn('lampwick', spoken.casefold())
        self.assertNotIn('table talk', spoken.casefold())
        self.assertNotIn('I follow, keeping close', spoken)
        self.assertNotIn('DC', spoken)
        for fenced in ('glass wyrm', 'brine vaults', 'cistern'):
            self.assertNotIn(fenced, spoken.casefold())

    def test_mixed_move_and_beyond_baseline_question_calls_a_check(self):
        _db, _runtime, bridge = self._bridge(local=False)
        prepared = bridge.prepare(
            'I follow her up the stairs. What do I know about the old wars that carved this ridge?',
            one_pass=True)
        self.assertEqual(prepared.get('stage'), 'called_roll', prepared)
        self.assertIn('Roll History.', prepared.get('spoken') or '')
        self.assertNotIn('dc', (prepared.get('spoken') or '').casefold())


class InternalLabels(unittest.TestCase):

    def test_validator_rejects_the_label(self):
        with self.assertRaises(InvalidChange):
            kit_agent.check_no_internal_labels('Narrator: Table talk to Kit: "What now?"')
        kit_agent.check_no_internal_labels('Kit: You grew up here. What do you do?')
        self.assertIn('check_no_internal_labels', kit_agent.VALIDATOR_KINDS)

    def test_table_talk_fallback_never_echoes(self):
        body = {'public_event': kit_agent.table_talk_event('Hmm, what about the weather lately?'),
                'table_talk': True, 'public_view': {}, 'action': 'Hmm, what about the weather lately?'}
        spoken = kit_agent.public_fallback(body)
        self.assertEqual(spoken, kit_agent.TABLE_TALK_HANDOFF)
        body['knowledge_answer'] = 'Kit: No roll needed; you know this much. Lampwick is home. What do you do?'
        self.assertEqual(kit_agent.public_fallback(body), body['knowledge_answer'])

    def test_knowledge_answer_line_keeps_fenced_terms_out(self):
        facts = {'knowledge': {'gate': 'baseline'}, 'spoiler_fence': ['Glass Wyrm'],
                 'party': ['A glass wyrm sleeps below.', 'You are from the town of Lampwick.'], 'section': []}
        line = kit_agent.knowledge_answer_line(facts)
        self.assertIn('Lampwick', line)
        self.assertNotIn('wyrm', line.casefold())
        self.assertIsNone(kit_agent.knowledge_answer_line({'knowledge': {'gate': 'check'}, 'party': ['x.']}))


if __name__ == '__main__':
    unittest.main()
