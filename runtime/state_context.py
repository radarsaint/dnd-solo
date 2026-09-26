"""D&D Solo feasibility prototype: trusted DM backend, not a complete game.

Python standard library only. All write operations are for an adjudicating DM
or future validated server adapter, never direct player tool access.
"""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERSONALITY_CORE = PROJECT_ROOT / 'docs/personality/dm-personality-core.md'


class InvalidChange(ValueError):
    pass


class StaleTurn(InvalidChange):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def require(condition, message):
    if not condition:
        raise InvalidChange(message)


class Runtime:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS source (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots (revision INTEGER PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, digest TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS ledger (seq INTEGER PRIMARY KEY, turn_id TEXT NOT NULL REFERENCES turns(id), body TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS immutable_ledger_update BEFORE UPDATE ON ledger
                BEGIN SELECT RAISE(ABORT, 'Ledger is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_ledger_delete BEFORE DELETE ON ledger
                BEGIN SELECT RAISE(ABORT, 'Ledger is append-only'); END;
        """)

    def close(self):
        self.db.close()

    def initialize(self, source, area):
        """Create a fresh fixture session. Refuse to overwrite a running game."""
        require(area in source['areas'], 'Unknown starting area')
        for exit_id, edge in source['exits'].items():
            require(len(edge['areas']) == 2 and len(set(edge['areas'])) == 2,
                    'Each exit must connect two distinct areas')
            require(all(a in source['areas'] for a in edge['areas']), 'Unknown exit endpoint')
        for fact in source['facts'].values():
            require(fact['area'] in source['areas'], 'Unknown fact area')
        for actor in source['actors'].values():
            require(actor['location'] in source['areas'], 'Unknown actor area')
        state = {
            'schema_version': 1, 'area': area, 'elapsed_seconds': 0,
            'visited': [area], 'known_facts': [], 'known_exits': [],
            'actors': copy.deepcopy(source['actors']),
            'resources': copy.deepcopy(source['resources']), 'rhythm': [],
        }
        self._observe(state, source)
        with self.db:
            self.db.execute('INSERT INTO source VALUES (1, ?)', (encode(source),))
            self.db.execute('INSERT INTO snapshots VALUES (0, ?)', (encode(state),))

    def source(self):
        row = self.db.execute('SELECT body FROM source WHERE id=1').fetchone()
        require(row is not None, 'Initialize a session first')
        return json.loads(row[0])

    def load(self):
        row = self.db.execute('SELECT revision, body FROM snapshots ORDER BY revision DESC LIMIT 1').fetchone()
        require(row is not None, 'Initialize a session first')
        return row[0], json.loads(row[1])

    @staticmethod
    def _observe(state, source):
        # Fixture visibility is explicit. A production adapter must supply perception,
        # light, concealment, and discovery rulings before accepting a reveal.
        for key, fact in source['facts'].items():
            if fact['area'] == state['area'] and fact['visible'] and key not in state['known_facts']:
                state['known_facts'].append(key)
        for key, edge in source['exits'].items():
            if state['area'] in edge['areas'] and not edge['secret'] and key not in state['known_exits']:
                state['known_exits'].append(key)

    def commit(self, turn_id, expected_revision, events):
        """Atomically accept an adjudicated event batch; safe to retry identically."""
        require(isinstance(turn_id, str) and bool(turn_id.strip()), 'Turn ID required')
        require(type(expected_revision) is int and expected_revision >= 0, 'Invalid revision')
        require(isinstance(events, list) and 0 < len(events) <= 100, 'Expected 1–100 events')
        digest = hashlib.sha256(encode(events).encode()).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            prior = self.db.execute('SELECT digest, revision FROM turns WHERE id=?', (turn_id,)).fetchone()
            if prior:
                require(prior[0] == digest, 'Turn ID already used with different events')
                self.db.rollback()
                return prior[1]
            revision, state = self.load()
            if revision != expected_revision:
                raise StaleTurn(f'Expected revision {expected_revision}; current is {revision}')
            source = self.source()
            for event in events:
                self._apply(state, source, event)
            next_revision = revision + 1
            self.db.execute('INSERT INTO turns VALUES (?, ?, ?)', (turn_id, digest, next_revision))
            self.db.executemany('INSERT INTO ledger(turn_id, body) VALUES (?, ?)',
                                [(turn_id, encode(event)) for event in events])
            self.db.execute('INSERT INTO snapshots VALUES (?, ?)', (next_revision, encode(state)))
            self.db.commit()
            return next_revision
        except Exception:
            self.db.rollback()
            raise

    def _apply(self, state, source, event):
        require(isinstance(event, dict), 'Event must be an object')
        require(isinstance(event.get('evidence'), str) and bool(event['evidence'].strip()),
                'Record the adjudication or evidence for each event')
        kind = event.get('type')
        if kind == 'reveal_fact':
            key = event.get('fact')
            require(key in source['facts'], 'Unknown fact')
            require(source['facts'][key]['area'] == state['area'], 'Remote reveal unsupported')
            if key not in state['known_facts']:
                state['known_facts'].append(key)
        elif kind == 'reveal_exit':
            key = event.get('exit')
            require(key in source['exits'], 'Unknown exit')
            require(state['area'] in source['exits'][key]['areas'], 'Exit not adjacent')
            if key not in state['known_exits']:
                state['known_exits'].append(key)
        elif kind == 'move':
            key = event.get('exit')
            require(key in state['known_exits'], 'Exit not discovered')
            edge = source['exits'][key]
            require(state['area'] in edge['areas'], 'Exit not adjacent')
            state['area'] = next(a for a in edge['areas'] if a != state['area'])
            if state['area'] not in state['visited']:
                state['visited'].append(state['area'])
            self._observe(state, source)
        elif kind == 'actor_status':
            key = event.get('actor')
            require(key in state['actors'], 'Unknown actor')
            actor = state['actors'][key]
            require(actor['location'] == state['area'], 'Remote actor update unsupported')
            status = event.get('status')
            require(status in {'alive', 'unconscious', 'dead', 'fled'}, 'Unknown status')
            require(actor['status'] != 'dead' or status == 'dead', 'Resurrection needs a future explicit rules operation')
            actor['status'] = status
        elif kind == 'spend_resource':
            key, amount = event.get('resource'), event.get('amount')
            require(key in state['resources'], 'Unknown resource')
            require(type(amount) is int and amount > 0, 'Spend must be a positive integer')
            require(state['resources'][key] >= amount, 'Insufficient resource')
            state['resources'][key] -= amount
        elif kind == 'advance_time':
            seconds = event.get('seconds')
            require(type(seconds) is int and seconds > 0, 'Time increment must be a positive integer')
            state['elapsed_seconds'] += seconds
        elif kind == 'beat':
            tags = event.get('tags')
            require(isinstance(tags, list) and all(isinstance(t, str) for t in tags), 'Invalid beat tags')
            state['rhythm'].append({'tags': tags, 'evidence': event['evidence']})
            state['rhythm'] = state['rhythm'][-12:]
        else:
            raise InvalidChange(f'Unsupported event: {kind}')

    @staticmethod
    def _player_view(source, state):
        exits = []
        for key in state['known_exits']:
            edge = source['exits'][key]
            if state['area'] not in edge['areas']:
                continue
            other = next(a for a in edge['areas'] if a != state['area'])
            exits.append({'id': key, 'description': edge['labels'][state['area']],
                          'known_destination': source['areas'][other]['name'] if other in state['visited'] else None})
        return {
            'area': source['areas'][state['area']]['name'],
            'known_facts_here': [source['facts'][k]['text'] for k in state['known_facts']
                                 if source['facts'][k]['area'] == state['area']],
            'exits': exits,
            'actors': [{'name': a['name'], 'status': a['status']} for a in state['actors'].values()
                       if a['location'] == state['area'] and a['visible'] and a['status'] != 'fled'],
            'resources': state['resources'], 'elapsed_seconds': state['elapsed_seconds'],
        }

    def player_view(self):
        _, state = self.load()
        return self._player_view(self.source(), state)

    def context(self, personality_core=None, max_bytes=24000):
        if personality_core is None:
            personality_core = PERSONALITY_CORE.read_text(encoding='utf-8')
        revision, state = self.load()
        source, area = self.source(), state['area']
        packet = {
            'prototype_version': '0.1.0', 'revision': revision,
            'personality_core': personality_core,
            'dm_context': {
                'scene': {'current_area': area, 'elapsed_seconds': state['elapsed_seconds']},
                'source_id': source['id'], 'fixture_only': source['fixture_only'],
                'player_perceivable': self._player_view(source, state),
                'dm_only': {
                    'unrevealed_facts': {k: f for k, f in source['facts'].items()
                                         if f['area'] == area and k not in state['known_facts']},
                    'geometry': {k: e for k, e in source['exits'].items() if area in e['areas']},
                    'actors': {k: a for k, a in state['actors'].items()
                               if a['location'] == area and a['status'] != 'fled'},
                },
                'recent_rhythm': state['rhythm'],
                'constraints': [
                    'Player output must respect player_perceivable and accepted reveals.',
                    'DM-only facts and actor secrets are private.',
                    'The source graph is immutable. Missing connections are not invented.',
                    'Writes require adjudication; this prototype does not check D&D legality.',
                    'This fixture is not Mad Mage canon and is not a campaign save.',
                ],
                'missing_production_layers': ['rules resolver', 'source retrieval', 'level story state',
                    'Halaster state', 'faction ticks', 'player model', 'character patterns'],
            },
        }
        require(len(encode(packet).encode()) <= max_bytes, 'Context budget exceeded; narrow the source adapter')
        return packet


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'view', 'context', 'commit'])
    parser.add_argument('--db', default='session.sqlite')
    parser.add_argument('--fixture', default=str(PROJECT_ROOT / 'tests/fixtures/feasibility_room.json'))
    parser.add_argument('--core', default=str(PERSONALITY_CORE))
    parser.add_argument('--turn-file', help='JSON object with turn_id, expected_revision, events')
    args = parser.parse_args()
    runtime = Runtime(args.db)
    try:
        if args.command == 'init':
            source = json.loads(Path(args.fixture).read_text(encoding='utf-8'))
            runtime.initialize(source, source['starting_area'])
            output = runtime.player_view()
        elif args.command == 'view':
            output = runtime.player_view()
        elif args.command == 'context':
            output = runtime.context(Path(args.core).read_text(encoding='utf-8'))
        else:
            if not args.turn_file:
                parser.error('--turn-file is required')
            output = {'revision': runtime.commit(**json.loads(Path(args.turn_file).read_text(encoding='utf-8')))}
        print(json.dumps(output, indent=2, ensure_ascii=False))
    finally:
        runtime.close()
