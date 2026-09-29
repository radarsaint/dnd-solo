"""D&D Solo feasibility prototype: trusted DM backend, not a complete game.

Python standard library only. All write operations are for an adjudicating DM
or future validated server adapter, never direct player tool access.
"""
import copy
import hashlib
import json
import re
import secrets
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERSONALITY_CORE = PROJECT_ROOT / 'docs/personality/dm-personality-core.md'
RHYTHM_EVIDENCE_MAX_CHARS = 600  # per recent_rhythm entry; 12 entries stay inside context()

# Version 2 adds Kit's player_notes and richer episodes (player_bid, kit_choice,
# actor and story thread). Older snapshots are upgraded in memory on load; the
# stored history is never rewritten, and the next commit saves the new shape.
STATE_SCHEMA_VERSION = 2
KIT_EPISODE_LIMIT = 24       # stored; the decision sees a relevance-selected subset
PLAYER_NOTE_LIMIT = 8
PLAYER_NOTE_MAX_CHARS = 300
PLAYER_NOTE_MAX_EVIDENCE = 4
PLAYER_NOTE_SOURCES = ('observed', 'feedback')
EPISODE_DEFAULTS = {'player_bid': None, 'kit_choice': None, 'actor_ref': None,
                    'story_anchor': None, 'story_basis': None}
# Notes describe what the player did or said. They are not a relationship meter.
_SCORE_PATTERN = r'\b\d+\s*(/|out of)\s*\d+\b|%|\b(score|meter|affection|rating)\b'


class InvalidChange(ValueError):
    pass


class StaleTurn(InvalidChange):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def require(condition, message):
    if not condition:
        raise InvalidChange(message)


def upgrade_state(state):
    """Bring an older snapshot up to STATE_SCHEMA_VERSION without inventing history.

    Version 1 Kit state had only episodes and current_appraisal. Missing episode
    fields are filled with None (unknown), never guessed from other fields.
    """
    if state.get('schema_version', 1) >= STATE_SCHEMA_VERSION:
        return state
    kit = state.setdefault('kit', {})
    kit.setdefault('episodes', [])
    kit.setdefault('current_appraisal', None)
    kit.setdefault('player_notes', [])
    for episode in kit['episodes']:
        for key, default in EPISODE_DEFAULTS.items():
            episode.setdefault(key, default)
    state['schema_version'] = STATE_SCHEMA_VERSION
    return state


def check_player_note_text(text):
    require(isinstance(text, str) and 0 < len(text.strip()) <= PLAYER_NOTE_MAX_CHARS,
            f'A player note must be 1–{PLAYER_NOTE_MAX_CHARS} characters')
    require(re.search(_SCORE_PATTERN, text.casefold()) is None,
            'A player note records observed behavior or feedback, not a score or meter')


class Runtime:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS source (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots (revision INTEGER PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, digest TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS ledger (seq INTEGER PRIMARY KEY, turn_id TEXT NOT NULL REFERENCES turns(id), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS kit_turns (turn_id TEXT PRIMARY KEY REFERENCES turns(id), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS kit_pending (
                turn_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                body TEXT NOT NULL, plan TEXT
            );
            -- Timing telemetry is deliberately outside turns/ledger/kit_turns: it never
            -- enters a turn digest, so an identical retry stays idempotent.
            CREATE TABLE IF NOT EXISTS kit_telemetry (
                seq INTEGER PRIMARY KEY, turn_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL
            );
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
            'schema_version': STATE_SCHEMA_VERSION, 'area': area, 'elapsed_seconds': 0,
            'visited': [area], 'known_facts': [], 'known_exits': [],
            'actors': copy.deepcopy(source['actors']),
            'resources': copy.deepcopy(source['resources']), 'rhythm': [],
            'kit': {'episodes': [], 'current_appraisal': None, 'player_notes': []},
            'roll_seed': secrets.token_hex(16),
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
        return row[0], upgrade_state(json.loads(row[1]))

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
        return self._commit(turn_id, expected_revision, events)

    def commit_kit_turn(self, turn_id, expected_revision, events, record, consume_pending=False):
        """Commit world events, a private Kit episode, and the public turn together."""
        require(isinstance(record, dict), 'Kit turn record required')
        require(isinstance(record.get('player_input'), str) and record['player_input'].strip(),
                'Player input required')
        require(isinstance(record.get('public_event'), str) and record['public_event'].strip(),
                'Public event required')
        require(isinstance(record.get('spoken'), str) and record['spoken'].strip(),
                'Player-facing turn required')
        trace = record.get('trace')
        require(isinstance(trace, dict) and isinstance(trace.get('appraisal'), dict)
                and isinstance(trace.get('observed_event'), str)
                and isinstance(trace.get('move'), str), 'Private Kit decision required')
        require(all(len(encode(record[key]).encode()) <= 12000 for key in
                    ('player_input', 'public_event', 'spoken', 'trace')), 'Kit turn exceeds size limit')
        return self._commit(turn_id, expected_revision, events, record, consume_pending)

    def stage_kit_turn(self, turn_id, expected_revision, body):
        """Save an uncommitted chat turn so a host can perform the two model stages."""
        require(isinstance(turn_id, str) and bool(turn_id.strip()), 'Turn ID required')
        require(isinstance(body, dict), 'Pending turn body required')
        serialized = encode(body)
        require(len(serialized.encode()) <= 16000, 'Pending turn exceeds size limit')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            require(self.db.execute('SELECT 1 FROM turns WHERE id=?', (turn_id,)).fetchone() is None,
                    'Turn ID already committed')
            revision, _ = self.load()
            if revision != expected_revision:
                raise StaleTurn(f'Expected revision {expected_revision}; current is {revision}')
            row = self.db.execute('SELECT revision, body FROM kit_pending WHERE turn_id=?',
                                  (turn_id,)).fetchone()
            if row:
                require(row == (expected_revision, serialized), 'Turn ID already staged differently')
            else:
                self.db.execute('INSERT INTO kit_pending VALUES (?, ?, ?, NULL)',
                                (turn_id, expected_revision, serialized))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def pending_kit_turn(self, turn_id):
        row = self.db.execute('SELECT revision, body, plan FROM kit_pending WHERE turn_id=?',
                              (turn_id,)).fetchone()
        require(row is not None, 'No pending Kit turn with that ID')
        return {'revision': row[0], 'body': json.loads(row[1]),
                'plan': json.loads(row[2]) if row[2] is not None else None}

    def save_kit_plan(self, turn_id, expected_revision, plan):
        serialized = encode(plan)
        require(len(serialized.encode()) <= 12000, 'Private Kit decision exceeds size limit')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            revision, _ = self.load()
            if revision != expected_revision:
                raise StaleTurn(f'Expected revision {expected_revision}; current is {revision}')
            row = self.db.execute('SELECT revision, plan FROM kit_pending WHERE turn_id=?',
                                  (turn_id,)).fetchone()
            require(row is not None and row[0] == expected_revision, 'No matching pending Kit turn')
            require(row[1] is None or row[1] == serialized, 'Private decision already fixed for this turn')
            if row[1] is None:
                self.db.execute('UPDATE kit_pending SET plan=? WHERE turn_id=?',
                                (serialized, turn_id))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _commit(self, turn_id, expected_revision, events, kit_record=None, consume_pending=False):
        require(isinstance(turn_id, str) and bool(turn_id.strip()), 'Turn ID required')
        require(type(expected_revision) is int and expected_revision >= 0, 'Invalid revision')
        require(isinstance(events, list) and 0 < len(events) <= 100, 'Expected 1–100 events')
        payload = events if kit_record is None else {'events': events, 'kit_record': kit_record}
        digest = hashlib.sha256(encode(payload).encode()).hexdigest()
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
            if consume_pending:
                pending = self.db.execute('SELECT revision, body, plan FROM kit_pending WHERE turn_id=?',
                                          (turn_id,)).fetchone()
                require(pending is not None and pending[0] == expected_revision and
                        pending[2] == encode(kit_record['trace']), 'Pending Kit decision changed')
                staged = json.loads(pending[1])
                require(staged['action'] == kit_record['player_input'] and
                        staged['public_event'] == kit_record['public_event'] and
                        staged['events'] == events, 'Pending Kit event changed')
            source = self.source()
            for event in events:
                self._apply(state, source, event)
            next_revision = revision + 1
            if kit_record is not None:
                kit = state['kit']
                trace = kit_record['trace']
                read = trace.get('improv_read') if isinstance(trace.get('improv_read'), dict) else {}
                kit['current_appraisal'] = trace['appraisal']
                kit['episodes'].append({
                    'turn_id': turn_id, 'player_input': kit_record['player_input'],
                    'event': trace['observed_event'], 'appraisal': trace['appraisal'],
                    'goal': trace.get('goal'), 'move': trace['move'],
                    'brief': trace.get('public_brief'),
                    'public_event': kit_record['public_event'],
                    # Private: Kit's own reason and her reading of the bid, kept so a
                    # later decision can see why she did what she did.
                    'player_bid': read.get('player_bid'), 'kit_choice': read.get('kit_choice'),
                    'actor_ref': read.get('actor_ref'), 'story_anchor': read.get('story_anchor'),
                    'story_basis': read.get('story_basis'),
                })
                kit['episodes'] = kit['episodes'][-KIT_EPISODE_LIMIT:]
                note = trace.get('player_note')
                if isinstance(note, dict) and str(note.get('note', 'none')).strip().casefold() != 'none':
                    evidence = [turn_id if ref == 'this_turn' else ref
                                for ref in note.get('evidence_turns', [])]
                    self._add_player_note(state, f'n{next_revision}', 'observed', note['note'],
                                          evidence, note.get('replaces', 'none'),
                                          current_turn=turn_id)
            self.db.execute('INSERT INTO turns VALUES (?, ?, ?)', (turn_id, digest, next_revision))
            self.db.executemany('INSERT INTO ledger(turn_id, body) VALUES (?, ?)',
                                [(turn_id, encode(event)) for event in events])
            if kit_record is not None:
                self.db.execute('INSERT INTO kit_turns VALUES (?, ?)', (turn_id, encode(kit_record)))
            self.db.execute('INSERT INTO snapshots VALUES (?, ?)', (next_revision, encode(state)))
            if consume_pending:
                self.db.execute('DELETE FROM kit_pending WHERE turn_id=?', (turn_id,))
            self.db.commit()
            return next_revision
        except Exception:
            self.db.rollback()
            raise

    def preview(self, expected_revision, events):
        """Apply an adjudicated batch to a copy for pre-commit rendering."""
        revision, state = self.load()
        if revision != expected_revision:
            raise StaleTurn(f'Expected revision {expected_revision}; current is {revision}')
        source = self.source()
        for event in events:
            self._apply(state, source, event)
        return self._player_view(source, state)

    def record_kit_timing(self, turn_id, **fields):
        """Merge latency telemetry for a turn. Not part of the committed turn record."""
        require(isinstance(turn_id, str) and bool(turn_id.strip()), 'Turn ID required')
        with self.db:
            row = self.db.execute('SELECT body FROM kit_telemetry WHERE turn_id=?',
                                  (turn_id,)).fetchone()
            body = {**(json.loads(row[0]) if row else {}), **fields}
            if row:
                self.db.execute('UPDATE kit_telemetry SET body=? WHERE turn_id=?',
                                (encode(body), turn_id))
            else:
                self.db.execute('INSERT INTO kit_telemetry(turn_id, body) VALUES (?, ?)',
                                (turn_id, encode(body)))

    def kit_timing(self, turn_id):
        row = self.db.execute('SELECT body FROM kit_telemetry WHERE turn_id=?', (turn_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def recent_kit_timings(self, limit=8):
        require(type(limit) is int and 0 <= limit <= 50, 'Invalid timing limit')
        rows = self.db.execute('SELECT turn_id, body FROM kit_telemetry ORDER BY seq DESC LIMIT ?',
                               (limit,)).fetchall()
        return list(reversed([{'turn_id': row[0], **json.loads(row[1])} for row in rows]))

    def recent_kit_turns(self, limit=8):
        require(type(limit) is int and 0 <= limit <= 12, 'Invalid history limit')
        rows = self.db.execute('''SELECT kit_turns.body FROM kit_turns
            JOIN turns ON turns.id = kit_turns.turn_id
            ORDER BY turns.revision DESC LIMIT ?''', (limit,)).fetchall()
        return list(reversed([json.loads(row[0]) for row in rows]))

    def committed_kit_turn_ids(self):
        return {row[0] for row in self.db.execute('SELECT turn_id FROM kit_turns')}

    def kit_turns_by_id(self, turn_ids):
        """Committed public records for the given turns, oldest first."""
        wanted = [ref for ref in dict.fromkeys(turn_ids) if isinstance(ref, str)]
        if not wanted:
            return []
        rows = self.db.execute(
            f'''SELECT kit_turns.turn_id, kit_turns.body FROM kit_turns
            JOIN turns ON turns.id = kit_turns.turn_id
            WHERE kit_turns.turn_id IN ({','.join('?' * len(wanted))})
            ORDER BY turns.revision''', wanted).fetchall()
        return [{'turn_id': row[0], **json.loads(row[1])} for row in rows]

    def latest_kit_turn_id(self):
        row = self.db.execute('''SELECT kit_turns.turn_id FROM kit_turns
            JOIN turns ON turns.id = kit_turns.turn_id ORDER BY turns.revision DESC LIMIT 1''').fetchone()
        return row[0] if row else None

    def player_notes(self):
        return self.load()[1]['kit']['player_notes']

    def record_player_feedback(self, text, evidence_turns=None, replaces='none'):
        """Record the player's out-of-character comment as an evidence-cited note.

        It is committed like any other adjudicated change (its own revision and an
        append-only ledger entry), so a turn prepared before it must be prepared again.
        Retrying the same comment about the same turn is idempotent.
        """
        check_player_note_text(text)
        revision, _ = self.load()
        if evidence_turns is None:
            latest = self.latest_kit_turn_id()
            require(latest is not None,
                    'Feedback must cite a committed turn; play the opening first')
            evidence_turns = [latest]
        event = {'type': 'player_note', 'source': 'feedback', 'note': text.strip(),
                 'evidence_turns': list(evidence_turns), 'replaces': replaces or 'none',
                 'evidence': 'The host recorded the player\'s out-of-character feedback.'}
        # Same comment about the same turn is the same feedback: a retry after a lost
        # response returns the original revision instead of adding a duplicate note.
        digest = hashlib.sha256(encode(event).encode()).hexdigest()[:16]
        next_revision = self.commit(f'feedback-{digest}', revision, [event])
        return {'revision': next_revision, 'note': next(
            (note for note in self.player_notes() if note['id'] == f'n{next_revision}'), None)}

    def _add_player_note(self, state, note_id, source, text, evidence_turns, replaces='none',
                         current_turn=None):
        """Every note cites committed turns; notes can retire older observed notes."""
        require(source in PLAYER_NOTE_SOURCES, 'Unknown player note source')
        check_player_note_text(text)
        committed = self.committed_kit_turn_ids()
        require(isinstance(evidence_turns, list) and
                0 < len(evidence_turns) <= PLAYER_NOTE_MAX_EVIDENCE and
                all(isinstance(ref, str) and (ref in committed or ref == current_turn)
                    for ref in evidence_turns),
                f'A player note must cite 1–{PLAYER_NOTE_MAX_EVIDENCE} committed turn IDs')
        notes = state['kit']['player_notes']
        if replaces not in (None, 'none'):
            old = next((note for note in notes if note['id'] == replaces), None)
            require(old is not None, 'replaces must name an existing player note')
            require(source == 'feedback' or old['source'] == 'observed',
                    'Only new feedback can replace the player\'s own feedback')
            notes.remove(old)
        notes.append({'id': note_id, 'source': source, 'note': text.strip(),
                      'evidence_turns': list(dict.fromkeys(evidence_turns))})
        while len(notes) > PLAYER_NOTE_LIMIT:
            # Drop the oldest inferred note before any explicit feedback.
            observed = [note for note in notes if note['source'] == 'observed']
            notes.remove(observed[0] if observed else notes[0])

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
        elif kind == 'player_note':
            require(event.get('source') == 'feedback', 'Only host-recorded feedback is a note event')
            revision, _ = self.load()
            self._add_player_note(state, f'n{revision + 1}', 'feedback', event.get('note'),
                                  event.get('evidence_turns'), event.get('replaces', 'none'))
        elif kind == 'beat':
            tags = event.get('tags')
            require(isinstance(tags, list) and all(isinstance(t, str) for t in tags), 'Invalid beat tags')
            # The ledger keeps the full evidence; the rhythm window keeps a bounded
            # excerpt so long player declarations cannot exhaust the context budget.
            evidence = event['evidence']
            if len(evidence) > RHYTHM_EVIDENCE_MAX_CHARS:
                evidence = evidence[:RHYTHM_EVIDENCE_MAX_CHARS - 3] + '...'
            state['rhythm'].append({'tags': tags, 'evidence': evidence})
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
            'prototype_version': '0.1.1', 'revision': revision,
            'personality_core': personality_core,
            'dm_context': {
                'scene': {'current_area': area, 'elapsed_seconds': state['elapsed_seconds']},
                'source_id': source['id'], 'fixture_only': source['fixture_only'],
                'source_ref': source.get('source_ref'), 'map_ref': source.get('map_ref'),
                'level_context': source.get('level_context'),
                'campaign_context': source.get('campaign_context'),
                'player_perceivable': self._player_view(source, state),
                'dm_only': {
                    'room_rules': source.get('room_rules', []),
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
                    ('This is a conditional test snapshot grounded in the cited Mad Mage source, '
                     'not a campaign save.' if source.get('source_ref') else
                     'This synthetic fixture is not Mad Mage canon and is not a campaign save.'),
                ],
                'missing_production_layers': ['rules resolver', 'source retrieval', 'level story state',
                    'Halaster state', 'faction ticks', 'player model beyond evidence-cited notes',
                    'character patterns'],
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
