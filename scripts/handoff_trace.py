#!/usr/bin/env python3
"""Dump a session's per-turn handoff trace (runtime/kit_handoff.py).

    scripts/handoff_trace.py SESSION_DIR | SESSION.sqlite | SESSION.handoff.jsonl [--json] [--db SESSION.sqlite]

Latency is refreshed from the session database's timing stamps when it is found (the host
may stamp shown_at after the turn committed)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import kit_handoff  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('path')
    parser.add_argument('--db', help='session database (default: the one .sqlite next to the trace)')
    parser.add_argument('--json', action='store_true', help='print the rows as JSON')
    args = parser.parse_args(argv)
    path = Path(args.path)
    db = Path(args.db) if args.db else None
    if path.suffix == '.sqlite':
        db, path = db or path, path.parent / f'{path.stem}{kit_handoff.SUFFIX}'
    elif path.is_dir():
        found = sorted(path.glob(f'*{kit_handoff.SUFFIX}'))
        if len(found) != 1:
            print(f'{len(found)} handoff traces in {path}; name one', file=sys.stderr)
            return 2
        path = found[0]
    if db is None:
        candidate = path.parent / (path.name[:-len(kit_handoff.SUFFIX)] + '.sqlite')
        db = candidate if candidate.exists() else None
    lines = kit_handoff.read(path)
    timings = {}
    if db and db.exists():
        from runtime.state_context import Runtime
        runtime = Runtime(db)
        try:
            timings = {line['turn_id']: runtime.kit_timing(line['turn_id']) for line in lines
                       if line.get('event') == 'turn'}
        finally:
            runtime.close()
    rows = kit_handoff.summary(lines, timings)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print(f'no turns in {path}')
        return 0
    for row in rows:
        floor = {True: 'yes', False: 'NO', None: '-'}[row['floor_to_player']]
        latency = f"{row['latency_s']:.2f}s" if row['latency_s'] is not None else '-'
        print(f"{row['turn_id'][:12]:12}  {row['kind'][:18]:18}  {str(row['handoff'] or '-'):18}  "
              f"{latency:>7}  floor={floor:3}  attempts={row['attempts']}  {row['input'][:50]!r}")
        if row['handoff']:
            print(f"{'':14}trigger: {row['trigger']}; {row['how'] or 'awaiting the next input'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
