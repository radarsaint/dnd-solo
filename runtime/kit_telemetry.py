"""Per-turn latency telemetry (docs/latency/experiment-protocol.md).

Every CLI call that names a save (``--db``) appends one JSON line to ``<db>.telemetry.jsonl``
next to the save (git-ignored: ``*.telemetry.jsonl``). It records only what Python measures
itself; everything that happens outside Python is written as ``null`` and never estimated:

* measured: ``engine_ms`` (the command's work), ``serialization_ms`` (JSON encoding of the
  output), ``packet_bytes`` (UTF-8 bytes printed), ``packet_sha256``, ``tool_calls`` (CLI calls
  for this turn so far, this one included), ``packet_mode`` (full / layered / compact).
* always null here: ``model_wait_ms``, ``cache_hit``, ``first_visible_ms``, ``complete_ms``,
  ``input_tokens``, ``output_tokens``, ``retries``. Python cannot see them. A person filling
  them in from a stopwatch uses ``telemetry note`` (a separate, labelled record).

Telemetry never changes play: it prints nothing during play, and any failure to write it is
swallowed. ``KIT_TELEMETRY=0`` turns it off. Stdlib only.
"""
import argparse
import hashlib
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path

UNKNOWN = ('model_wait_ms', 'cache_hit', 'first_visible_ms', 'complete_ms', 'input_tokens',
           'output_tokens', 'retries')
MEASURED = ('engine_ms', 'serialization_ms', 'packet_bytes', 'tool_calls')
HOST_ENV = 'KIT_HOST'

_serialization_ns = 0


def enabled():
    return os.environ.get('KIT_TELEMETRY', '1') != '0'


def log_path(db):
    return Path(f'{db}.telemetry.jsonl')


def dumps(obj, **kwargs):
    """json.dumps, with its time added to this process's serialization total."""
    global _serialization_ns
    start = time.perf_counter_ns()
    try:
        return json.dumps(obj, **kwargs)
    finally:
        _serialization_ns += time.perf_counter_ns() - start


def reset():
    global _serialization_ns
    _serialization_ns = 0


def serialization_ns():
    return _serialization_ns


def session_id(db):
    """Stable for one save: the first 12 hex of the SHA-256 of its absolute path."""
    return hashlib.sha256(str(Path(db).resolve()).encode('utf-8')).hexdigest()[:12]


def turn_id_of(text, fallback=None):
    if fallback:
        return fallback
    for line in reversed((text or '').strip().splitlines()):
        try:
            out = json.loads(line)
        except ValueError:
            continue
        if isinstance(out, dict):
            prepared = out.get('prepared') if isinstance(out.get('prepared'), dict) else {}
            return out.get('turn_id') or prepared.get('turn_id')
    return None


def packet_mode(text):
    if '"packet_mode":"compact"' in text or '"packet_mode": "compact"' in text:
        return 'compact'
    if '"session_manifest"' in text:
        return 'layered'
    return 'full'


def _rows(db):
    path = log_path(db)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def record(db, command, total_ns, ser_ns, output, turn_id=None, host=None, exit_code=0):
    """Append one record. Returns it, or None if telemetry is off or could not be written."""
    if not enabled() or not db:
        return None
    try:
        if not Path(db).parent.is_dir():
            return None
        data = (output or '').encode('utf-8')
        turn = turn_id_of(output, turn_id)
        calls = 1 + sum(1 for row in _rows(db) if turn and row.get('turn_id') == turn
                        and row.get('kind') == 'cli')
        row = {'kind': 'cli', 'turn_id': turn, 'session_id': session_id(db),
               'host': host or os.environ.get(HOST_ENV) or None, 'command': command,
               'exit_code': exit_code,
               'engine_ms': round(max(total_ns - ser_ns, 0) / 1e6, 3),
               # A command that prints through its own json.dumps (e.g. adventure) is not split:
               # serialization is null there and engine_ms includes it.
               'serialization_ms': round(ser_ns / 1e6, 3) if ser_ns or not data else None,
               'packet_bytes': len(data), 'packet_sha256': hashlib.sha256(data).hexdigest(),
               'packet_mode': packet_mode(output or ''), 'tool_calls': calls,
               'recorded_at': round(time.time(), 3),
               **{key: None for key in UNKNOWN}}
        with log_path(db).open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
        return row
    except Exception:  # telemetry must never break a turn
        return None


def note(db, turn_id=None, condition=None, host=None, run=None, **values):
    """A hand-measured record (stopwatch / screen recording). Only the fields given are set;
    the rest stay null. Marked kind=manual so it is never mistaken for a Python measurement."""
    row = {'kind': 'manual', 'turn_id': turn_id or str(uuid.uuid4()), 'session_id': session_id(db),
           'host': host or os.environ.get(HOST_ENV) or None, 'condition': condition, 'run': run,
           'recorded_at': round(time.time(), 3), **{key: None for key in UNKNOWN}}
    row.update({key: value for key, value in values.items() if key in UNKNOWN and value is not None})
    with log_path(db).open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    return row


def percentile(values, q):
    """Nearest-rank percentile (q in 0..100) of the non-null values, or None."""
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    rank = max(1, -(-q * len(values) // 100))
    return values[int(rank) - 1]


def summary(values):
    present = [v for v in values if v is not None]
    return {'n': len(present), 'median': statistics.median(present) if present else None,
            'p95': percentile(present, 95)}


def report(db):
    """Medians and p95 per command (CLI records) and per condition (manual records)."""
    rows = _rows(db)
    cli = [row for row in rows if row.get('kind') == 'cli']
    manual = [row for row in rows if row.get('kind') == 'manual']
    by_command = {}
    for row in cli:
        by_command.setdefault(row.get('command'), []).append(row)
    turns = {}
    for row in cli:
        if row.get('turn_id'):
            turns[row['turn_id']] = max(turns.get(row['turn_id'], 0), row.get('tool_calls') or 0)
    by_condition = {}
    for row in manual:
        by_condition.setdefault(row.get('condition'), []).append(row)
    return {
        'stage': 'telemetry_report', 'log': str(log_path(db)), 'records': len(rows),
        'by_command': {cmd: {'count': len(group),
                             **{key: summary([r.get(key) for r in group])
                                for key in ('engine_ms', 'serialization_ms', 'packet_bytes')}}
                       for cmd, group in sorted(by_command.items(), key=lambda kv: str(kv[0]))},
        'tool_calls_per_turn': summary(list(turns.values())),
        'manual_by_condition': {str(cond): {'count': len(group),
                                            **{key: summary([r.get(key) for r in group])
                                               for key in ('first_visible_ms', 'complete_ms')}}
                                for cond, group in sorted(by_condition.items(), key=lambda kv: str(kv[0]))},
        'not_measured_by_python': list(UNKNOWN),
    }


def format_report(rep):
    def cell(s):
        return '-' if s['median'] is None else f"{s['median']:g} / {s['p95']:g} (n={s['n']})"
    lines = [f"Kit telemetry: {rep['log']} ({rep['records']} records). median / p95"]
    for cmd, group in rep['by_command'].items():
        lines.append(f"  {cmd}: engine_ms {cell(group['engine_ms'])}; serialization_ms "
                     f"{cell(group['serialization_ms'])}; packet_bytes {cell(group['packet_bytes'])}")
    lines.append(f"  tool calls per turn: {cell(rep['tool_calls_per_turn'])}")
    for cond, group in rep['manual_by_condition'].items():
        lines.append(f"  condition {cond} (hand-timed): first_visible_ms {cell(group['first_visible_ms'])}; "
                     f"complete_ms {cell(group['complete_ms'])}")
    lines.append('  not measured by Python (null unless hand-entered): ' + ', '.join(rep['not_measured_by_python']))
    return '\n'.join(lines)


def main(argv):
    parser = argparse.ArgumentParser(prog='kit_agent telemetry', description=__doc__.split('\n')[0])
    parser.add_argument('action', choices=['report', 'note'])
    parser.add_argument('--db', default='kit.sqlite')
    parser.add_argument('--json', action='store_true', help='report: print JSON instead of text')
    parser.add_argument('--turn-id')
    parser.add_argument('--condition', choices=['A', 'B', 'C', 'D', 'E-C', 'E-D'],
                        help='note: the experiment condition (docs/latency/experiment-protocol.md)')
    parser.add_argument('--run', type=int)
    parser.add_argument('--host')
    for key in UNKNOWN:
        kind = (lambda v: v.lower() in ('1', 'true', 'yes')) if key == 'cache_hit' else float
        parser.add_argument('--' + key.replace('_', '-'), dest=key, type=kind)
    args = parser.parse_args(argv)
    if args.action == 'report':
        rep = report(args.db)
        print(json.dumps(rep, ensure_ascii=False) if args.json else format_report(rep))
        return 0
    row = note(args.db, args.turn_id, args.condition, args.host, args.run,
               **{key: getattr(args, key) for key in UNKNOWN})
    print(json.dumps(row, ensure_ascii=False))
    return 0
