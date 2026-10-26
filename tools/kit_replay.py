#!/usr/bin/env python3
"""Replay a Kit II playtest log's player lines deterministically, with no model (stdlib only).

  python3 tools/kit_replay.py extract /workspace/kit2/pr150c-log.md -o tests/fixtures/replay/pr150c.json --room vault
  python3 tools/kit_replay.py run tests/fixtures/replay/pr150c.json            # diff against the stored outcomes
  python3 tools/kit_replay.py run tests/fixtures/replay/pr150c.json --update   # store the current outcomes

``extract`` pulls the quoted player lines out of a log (first-person or "Nik ..." actions,
Avrae roll lines, questions), drops engine output and notes, and writes a fixture. Review
it before committing: this repo is public, so replace any adventure names with the synthetic
room's SRD-generic objects. ``run`` plays the lines in order on one session in the chosen
synthetic room (tests/fixtures/fuzz/), committing each turn with tools/kit_fuzz.py's stub
Kit, and reports each line's outcome and any leak. With stored outcomes it exits 1 when an
outcome changed or anything leaked, so a playtest's bug round can be rerun in seconds.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_fuzz  # noqa: E402

QUOTED = re.compile(r'["\u201c]([^"\u201d\n]{6,240})["\u201d]')
ENGINE = re.compile(r'^(?:You |The |Nothing |That one|Expected|Incomplete|Invalid|Feature|Exchange|Kit |acts\.|Narrator:|'
                    r'Turn order|Roll |Your |No |This |Spell effects|Call scope|Private decision|Degraded|Padding)')
PLAYER = re.compile(r"^(?:I\b|I'|Nik\b|He\b|Ok|Okay|Fine|Wait|Hang on|Hmm|Ooh|Deal|Yes|No,|Scratch|Forget|Take|"
                    r"Looks?\b|Casting|With\b|Standing|Matching)|\d+d\d+|!r\b|!cast\b|\bcheck!", re.I)


def extract(text):
    lines = []
    for match in QUOTED.finditer(text):
        line = match.group(1).strip()
        if ENGINE.match(line) or not PLAYER.search(line) or '...' in line or '\u2026' in line:
            continue
        if len(line.split()) < 2 or line in lines:
            continue
        lines.append(line)
    return lines


def replay(fixture):
    harness = kit_fuzz.Harness(rooms={fixture['room']: kit_fuzz.ROOMS[fixture['room']]})
    try:
        runtime, _ = harness.fresh(fixture['room'])
        bridge = kit_fuzz.KitChatBridge(runtime, kit_fuzz.RoomAdjudicator(roll=lambda: 2, npc_roll=lambda: 2))
        secrets = harness.secrets[fixture['room']]
        results = []
        for i, line in enumerate(fixture['lines']):
            out = {'line': line, 'leaks': []}
            try:
                packet = bridge.prepare(line, f'r{i}', one_pass=True)
            except kit_fuzz.PendingRuling as exc:
                text = str(exc)
                out.update(outcome='attack' if kit_fuzz.ATTACK_ASK.search(text) else
                           'clarify' if kit_fuzz.CLARIFY_ASK.search(text) else 'refused', public=text,
                           leaks=kit_fuzz.scan(text, secrets, line))
                results.append(out)
                continue
            except kit_fuzz.InvalidChange as exc:
                out.update(outcome='error', public=str(exc))
                results.append(out)
                continue
            public = packet['input']['public']
            out.update(outcome=kit_fuzz.classify(public), public=public.get('accepted_public_event', ''))
            out['leaks'] = kit_fuzz.scan(kit_fuzz.public_text(public), secrets, line, kit_fuzz.revealed(public))
            result, why = kit_fuzz.complete(bridge, packet)
            out['committed'] = result is not None
            results.append(out)
        runtime.close()
        return results
    finally:
        harness.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description='Replay a playtest log with no model.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    ex = sub.add_parser('extract')
    ex.add_argument('log')
    ex.add_argument('-o', '--out', required=True)
    ex.add_argument('--room', default='vault', choices=sorted(kit_fuzz.ROOMS))
    run = sub.add_parser('run')
    run.add_argument('fixture')
    run.add_argument('--update', action='store_true')
    args = ap.parse_args(argv)
    if args.cmd == 'extract':
        lines = extract(Path(args.log).read_text(encoding='utf-8'))
        fixture = {'source': Path(args.log).name, 'room': args.room, 'lines': lines, 'outcomes': None}
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(fixture, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'{len(lines)} player lines -> {args.out} (review for adventure text before committing)')
        return 0
    path = Path(args.fixture)
    fixture = json.loads(path.read_text(encoding='utf-8'))
    results = replay(fixture)
    stored = fixture.get('outcomes') or []
    bad = 0
    for i, r in enumerate(results):
        was = stored[i] if i < len(stored) else None
        flag = ''
        if was is not None and was != r['outcome']:
            flag, bad = f'  CHANGED (was {was})', bad + 1
        if r['leaks']:
            flag, bad = flag + '  LEAK ' + '; '.join(r['leaks']), bad + 1
        print(f"{r['outcome']:<9} {r['line'][:90]!r}{flag}")
    if args.update:
        fixture['outcomes'] = [r['outcome'] for r in results]
        path.write_text(json.dumps(fixture, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'stored {len(results)} outcomes in {path}')
        return 0
    print(f'{len(results)} lines replayed, {bad} changed or leaking')
    return 1 if bad and stored else 0


if __name__ == '__main__':
    sys.exit(main())
