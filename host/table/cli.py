"""`python3 -m host.table`.

serve   the loopback table
probe   measure an opening packet without printing it
smoke   Android-compatible checks that do not need a model or a device
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _estimate_tokens(nbytes):
    """Rough lower-bound-free estimate used only as a size class, not a tokenizer."""
    return max(1, nbytes // 4)


def probe(root=None):
    """Run the real engine on the watchroom fixture and report packet sizes.

    The fixture is not a campaign. Nothing from the packet is printed.
    ``local_satisfactory`` stays false: this measurement is why.
    """
    from host.table.engine import Engine

    root = Path(root or ROOT)
    engine = Engine(root)
    room = root / 'tests' / 'fixtures' / 'rooms' / 'watchroom.json'
    sheet = root / 'tests' / 'fixtures' / 'characters' / 'example_pc.json'
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / 'kit.sqlite'
        started = engine.begin_regression(db, room, sheet)
        prepared = started.get('prepared') or {}
        opening_bytes = len(json.dumps(prepared, ensure_ascii=False).encode('utf-8'))
        engine.prepare(db, action='Begin')
        later = engine.prepare(db, action='I wait on the landing and listen.')
        later_bytes = len(json.dumps(later, ensure_ascii=False).encode('utf-8'))
    report = {
        'schema': 'kit-table-probe-v1',
        'python': sys.version.split()[0],
        'device_measured': False,
        'opening_packet_bytes': opening_bytes,
        'opening_tokens_est': _estimate_tokens(opening_bytes),
        'second_packet_bytes': later_bytes,
        'second_tokens_est': _estimate_tokens(later_bytes),
        'local_satisfactory': False,
        'reason': (
            'The opening packet is the personality, the instructions, and the schema, '
            'then a strict JSON decision the engine will reject when it is wrong. '
            'A Tab S7+ (SM-T970, Snapdragon 865+, 6GB on the 128GB model or 8GB on '
            'the 256/512GB models) can run the Python engine. It cannot comfortably '
            'run a model strong enough to pass that check beside Android. '
            'A 1.5B to 3B model is the largest that might fit, and that class does '
            'not follow this schema. This probe did not run a model.'
        ),
    }
    return report


def smoke(root=None):
    """Checks a Termux install can run without a model and without claiming a device."""
    from host.table.engine import Engine, EngineError

    root = Path(root or ROOT)
    failures = []
    version = tuple(int(part) for part in sys.version.split()[0].split('.')[:2])
    if version < (3, 10):
        failures.append(f'Python {sys.version.split()[0]} is below 3.10')
    engine = Engine(root)
    try:
        text = engine.persona()
    except EngineError as exc:
        failures.append('persona failed: ' + str(exc)[:200])
        text = ''
    if not text.strip():
        failures.append('persona text is empty')
    if 'Voice warning:' in text:
        failures.append('persona reports omitted voice material')
    with tempfile.TemporaryDirectory() as folder:
        status = engine.status(Path(folder) / 'kit.sqlite')
        if status.get('state') != 'unmounted':
            failures.append('a missing save did not read as unmounted')
        if (Path(folder) / 'kit.sqlite').exists():
            failures.append('status created a database')
    report = {
        'schema': 'kit-table-smoke-v1',
        'ok': not failures,
        'python': sys.version.split()[0],
        'failures': failures,
        'device_installed': False,
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m host.table', description=__doc__)
    parser.add_argument('command', choices=['serve', 'probe', 'smoke'])
    parser.add_argument('--home', default=os.environ.get('KIT_HOME', str(Path.home() / '.kit-table')))
    parser.add_argument('--bind', default=os.environ.get('KIT_TABLE_BIND', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('KIT_TABLE_PORT', '8765')))
    parser.add_argument('--root', default=str(ROOT))
    args = parser.parse_args(argv)
    if args.command == 'probe':
        print(json.dumps(probe(args.root), indent=2, ensure_ascii=False))
        return 0
    if args.command == 'smoke':
        report = smoke(args.root)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report['ok'] else 1
    from host.table.server import serve
    serve(args.root, args.home, args.bind, args.port)
    return 0


if __name__ == '__main__':
    sys.exit(main())
