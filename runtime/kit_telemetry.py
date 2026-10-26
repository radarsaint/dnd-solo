"""Per-turn latency telemetry and the compact opening packet (priority 4, latency research).

Two jobs, both stdlib only:

* Telemetry. Every ``kit_agent`` CLI call appends one JSON line to ``<db>.telemetry.jsonl``
  next to the save (git-ignored: ``*.telemetry.jsonl``). Python records only what Python can
  measure: its own run time (``engine_ms``), the time to serialize the reply
  (``serialization_ms``), the reply's UTF-8 size and SHA-256, and how many tool calls this turn
  has taken so far. Everything only the host or the model provider knows (model wait, cache
  hits, first visible text, complete time, tokens, retries) is written as ``null``. It is
  never estimated. ``kit_agent telemetry report --db kit.sqlite`` prints medians and p95.
  Telemetry never changes what the player sees and never breaks a turn: a failed write is
  dropped silently. ``KIT_TELEMETRY=0`` turns it off.

* Packet mode. ``full`` (default) is the packet as it has always been. ``compact`` is opt-in
  (``start --compact`` records it in the save; ``prepare --compact`` for one turn). A compact
  packet keeps the operating contract (instructions, schema, limits), the whole turn delta
  (active scene, character state, reveal and story brief, first_try), live constraints, and
  the room's hidden facts for the current area and the areas one exit away. It leaves out the
  personality core (already read at load; ``persona`` prints it) and hidden facts of far areas.
  ``rehydrate --turn-id T`` returns both bodies in full. See docs/latency/experiment-protocol.md.
"""
import hashlib
import json
import os
import sqlite3
import statistics
import time
import uuid
from pathlib import Path

PACKET_MODES = ('full', 'compact')
# What only the host or the provider can know. Always null from Python; never guessed.
HOST_ONLY = ('model_wait_ms', 'cache_hit', 'first_visible_ms', 'complete_ms',
             'input_tokens', 'output_tokens', 'retries')
FIELDS = ('turn_id', 'session_id', 'host', 'command', 'packet_mode', 'exit_code', 'engine_ms',
          'serialization_ms', 'packet_bytes', 'packet_sha256', 'tool_calls') + HOST_ONLY
RETRIEVAL = {
    'rule': ('Compact packet: everything this scene needs is here. Fetch the rest only when the '
             'scene turns to it; never guess at it.'),
    'personality_core': 'python3 -m runtime.kit_agent persona',
    'full_manifests': 'python3 -m runtime.kit_agent rehydrate --db <db> --turn-id <turn_id>',
    'player_view': 'python3 -m runtime.kit_agent view --db <db>',
}


# ---------- packet mode ----------

def set_packet_mode(db, mode):
    if mode not in PACKET_MODES:
        raise ValueError(f'packet mode must be one of {PACKET_MODES}')
    con = sqlite3.connect(str(db))
    try:
        con.execute('CREATE TABLE IF NOT EXISTS kit_packet_mode (id INTEGER PRIMARY KEY CHECK (id = 1), '
                    'mode TEXT NOT NULL)')
        con.execute('INSERT INTO kit_packet_mode (id, mode) VALUES (1, ?) '
                    'ON CONFLICT(id) DO UPDATE SET mode=excluded.mode', (mode,))
        con.commit()
    finally:
        con.close()


def packet_mode(con):
    """The recorded mode on an open connection; 'full' when none was recorded."""
    try:
        row = con.execute('SELECT mode FROM kit_packet_mode WHERE id=1').fetchone()
    except sqlite3.Error:
        return 'full'
    return row[0] if row and row[0] in PACKET_MODES else 'full'


def near_areas(dm_only, area):
    """The current area and every area one exit away (by the room geometry)."""
    near = {area}
    for link in ((dm_only or {}).get('geometry') or {}).values():
        areas = (link or {}).get('areas') or ()
        if area in areas:
            near.update(areas)
    return near


def compact_parts(session, room, area):
    """(session, room) for a compact packet. Nothing else in the packet changes."""
    session = {k: v for k, v in session.items() if k != 'personality_core'}
    session['personality_ref'] = {'command': RETRIEVAL['personality_core'],
                                      'note': 'You read this at load; it is unchanged. Run it if you no longer have it.'}
    room = dict(room)
    dm_only = room.get('dm_only')
    if isinstance(dm_only, dict) and isinstance(dm_only.get('unrevealed_facts'), dict) and area:
        near = near_areas(dm_only, area)
        kept = {k: v for k, v in dm_only['unrevealed_facts'].items()
                if not isinstance(v, dict) or v.get('area') in near or v.get('area') is None}
        far = sorted(set(dm_only['unrevealed_facts']) - set(kept))
        room['dm_only'] = {**dm_only, 'unrevealed_facts': kept}
        if far:
            room['far_facts_withheld'] = {'ids': far, 'fetch': RETRIEVAL['full_manifests']}
    return session, room


# ---------- telemetry ----------

def path_for(db):
    return Path(f'{db}.telemetry.jsonl')


def enabled():
    return os.environ.get('KIT_TELEMETRY', '1') not in ('0', 'false', 'off', '')


def read(db):
    path = path_for(db)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _session_id(rows, given):
    if given:
        return given
    for row in reversed(rows):
        if row.get('session_id'):
            return row['session_id']
    return uuid.uuid4().hex[:16]


def record(db, *, command, turn_id=None, host=None, session_id=None, packet_mode=None, exit_code=None,
           engine_ns=None, serialization_ns=None, packet=None):
    """Append one record. Returns it, or None if telemetry is off or the write failed."""
    if not enabled():
        return None
    try:
        rows = read(db)
        data = packet.encode('utf-8') if isinstance(packet, str) else None
        out = dict.fromkeys(FIELDS)
        out.update({
            'turn_id': turn_id, 'session_id': _session_id(rows, session_id),
            'host': host or os.environ.get('KIT_HOST') or None, 'command': command,
            'packet_mode': packet_mode, 'exit_code': exit_code,
            'engine_ms': None if engine_ns is None else round(engine_ns / 1e6, 3),
            'serialization_ms': None if serialization_ns is None else round(serialization_ns / 1e6, 3),
            'packet_bytes': None if data is None else len(data),
            'packet_sha256': None if data is None else hashlib.sha256(data).hexdigest(),
            'tool_calls': (1 + sum(1 for r in rows if r.get('turn_id') == turn_id)) if turn_id else None,
        })
        with path_for(db).open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')
        return out
    except Exception:  # noqa: BLE001 - telemetry must never break a turn
        return None


def _p95(values):
    ordered = sorted(values)
    return ordered[max(0, -(-95 * len(ordered) // 100) - 1)]  # nearest-rank


def summarize(values):
    values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not values:
        return None
    return {'n': len(values), 'median': round(statistics.median(values), 3), 'p95': round(_p95(values), 3)}


def report(db):
    """Medians and p95 per command and packet mode. Host-only fields are reported only as how
    many records carry a value (from Python, none do)."""
    rows = read(db)
    groups = {}
    for row in rows:
        groups.setdefault(f"{row.get('command')}|{row.get('packet_mode') or '-'}", []).append(row)
    turns = {}
    for row in rows:
        if row.get('turn_id'):
            turns[row['turn_id']] = max(turns.get(row['turn_id'], 0), row.get('tool_calls') or 0)
    return {
        'file': str(path_for(db)), 'records': len(rows),
        'sessions': len({r.get('session_id') for r in rows}),
        'by_command': {key: {'records': len(group),
                             **{name: summarize(r.get(name) for r in group)
                                for name in ('engine_ms', 'serialization_ms', 'packet_bytes')}}
                       for key, group in sorted(groups.items())},
        'tool_calls_per_turn': summarize(turns.values()),
        'host_only_fields': {name: sum(1 for r in rows if r.get(name) is not None) for name in HOST_ONLY},
        'note': ('engine_ms and serialization_ms are Python only. Model, host and player-visible '
                 'time are not measured here; see docs/latency/experiment-protocol.md.'),
    }


def now_ns():
    return time.perf_counter_ns()
