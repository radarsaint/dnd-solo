import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime.state_context import InvalidChange, PERSONALITY_CORE, Runtime, StaleTurn


FIXTURES = Path(__file__).parent / 'fixtures'


def event(kind, **fields):
    return {'type': kind, 'evidence': 'Explicit synthetic test adjudication.', **fields}


class StateContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'session.sqlite'
        self.runtime = Runtime(self.path)
        self.addCleanup(lambda: self.runtime.close())
        self.source = json.loads((FIXTURES / 'feasibility_room.json').read_text())
        self.runtime.initialize(self.source, 'entry')

    def test_changes_survive_restart_without_respawning_from_source(self):
        turn = json.loads((FIXTURES / 'feasibility_turn.json').read_text())
        self.runtime.commit(**turn)
        self.runtime.close()
        self.runtime = Runtime(self.path)
        revision, state = self.runtime.load()
        self.assertEqual(revision, 1)
        self.assertEqual(state['actors']['sentry']['status'], 'dead')
        self.assertEqual(state['resources']['arrows'], 3)
        self.assertEqual(state['elapsed_seconds'], 6)
        packet = self.runtime.context()
        self.assertEqual(packet['dm_context']['dm_only']['actors']['sentry']['status'], 'dead')
        self.assertEqual(self.runtime.source()['actors']['sentry']['status'], 'alive')

    def test_player_projection_excludes_secrets_and_unexplored_destinations(self):
        view = self.runtime.player_view()
        text = json.dumps(view)
        for forbidden in ['cache_panel', 'concealed latch', 'brass box', 'Unseen test cache',
                          'Unseen watcher', 'spare key', 'recovering', 'knowledge', 'secrets']:
            self.assertNotIn(forbidden, text)
        self.assertIsNone(view['exits'][0]['known_destination'])
        packet = self.runtime.context()
        self.assertIn('latch', packet['dm_context']['dm_only']['unrevealed_facts'])
        self.assertIn('hidden_watcher', packet['dm_context']['dm_only']['actors'])
        self.assertEqual(packet['personality_core'], PERSONALITY_CORE.read_text())

    def test_discovery_and_travel_respect_graph_and_reveal_boundaries(self):
        with self.assertRaises(InvalidChange):
            self.runtime.commit('hidden-move', 0, [event('move', exit='cache_panel')])
        with self.assertRaises(InvalidChange):
            self.runtime.commit('invented-exit', 0, [event('reveal_exit', exit='invented_tunnel')])
        self.runtime.commit('discovery', 0, [event('reveal_exit', exit='cache_panel'), event('reveal_fact', fact='latch')])
        view = self.runtime.player_view()
        self.assertNotIn('brass box', json.dumps(view))
        self.assertIsNone(next(e for e in view['exits'] if e['id'] == 'cache_panel')['known_destination'])
        self.runtime.commit('enter-cache', 1, [event('move', exit='cache_panel')])
        self.assertIn('brass box', json.dumps(self.runtime.player_view()))
        with self.assertRaises(InvalidChange):
            self.runtime.commit('nonadjacent', 2, [event('move', exit='main_door')])

    def test_invalid_batch_rolls_back_every_change_and_ledger_entry(self):
        before = self.runtime.load()
        with self.assertRaises(InvalidChange):
            self.runtime.commit('overspend', 0, [event('advance_time', seconds=60),
                event('spend_resource', resource='arrows', amount=5)])
        self.assertEqual(self.runtime.load(), before)
        self.assertEqual(self.runtime.db.execute('SELECT count(*) FROM ledger').fetchone()[0], 0)
        self.assertEqual(self.runtime.db.execute('SELECT count(*) FROM turns').fetchone()[0], 0)

    def test_retry_is_idempotent_and_reusing_id_with_different_data_fails(self):
        events = [event('spend_resource', resource='arrows', amount=1)]
        self.assertEqual(self.runtime.commit('shot', 0, events), 1)
        self.assertEqual(self.runtime.commit('shot', 0, events), 1)
        self.assertEqual(self.runtime.load()[1]['resources']['arrows'], 3)
        with self.assertRaises(InvalidChange):
            self.runtime.commit('shot', 1, [event('spend_resource', resource='arrows', amount=2)])

    def test_stale_connection_cannot_overwrite_another_turn(self):
        other = Runtime(self.path)
        try:
            stale_revision = other.load()[0]
            self.runtime.commit('first', 0, [event('advance_time', seconds=6)])
            with self.assertRaises(StaleTurn):
                other.commit('stale', stale_revision, [event('advance_time', seconds=30)])
            self.assertEqual(other.load()[1]['elapsed_seconds'], 6)
        finally:
            other.close()

    def test_context_fails_explicitly_when_over_budget(self):
        with self.assertRaisesRegex(InvalidChange, 'Context budget exceeded'):
            self.runtime.context(max_bytes=100)

    def test_ledger_rejects_in_place_rewriting_and_deletion(self):
        self.runtime.commit('time', 0, [event('advance_time', seconds=6)])
        for sql in ['UPDATE ledger SET body = body', 'DELETE FROM ledger']:
            with self.assertRaises(sqlite3.IntegrityError):
                self.runtime.db.execute(sql)
            self.runtime.db.rollback()
        self.assertEqual(self.runtime.db.execute('SELECT count(*) FROM ledger').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
