#!/usr/bin/env python3
"""Record main's own outcome for the #122 fallback cases (tests/fixtures/combat_acts_main_fallback.json).

Run from a checkout of main (no #122 code) with that checkout's tests on the path:

    env -u PYTHONPATH python3 scripts/combat_acts_main_golden.py OUT.json

Each case builds its fight on a synthetic fixture room at runtime (kiln, shrine), dice pinned, and
sends the message through main's KitChatBridge.prepare. Main has no combat_acts: it answers with
its pending ruling. The JSON keeps that ruling (pending_ruling_result), the state after it and the
refused attempts, so test_kit_combat_acts_fallback can hold #122's fallback to real main's
behaviour, not a twin of it."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

from runtime.kit_agent import KitChatBridge, PendingRuling, pending_ruling_result  # noqa: E402
from test_kit_review101c import KILN_OPEN, Arena, rogue, warlock, without_shield, wizard  # noqa: E402

SHRINE_OPEN = 'Initiative 25. I stab the adept with my dagger, 3 to hit, 3 piercing.'
CASES = {
    'no reaction (warlock, kiln)': ('kiln', 'warlock', 10, 'No reaction.'),
    'avrae damage (wizard, shrine)': ('shrine', 'wizard', 10, '3d8 (5, 8, 7) = 20 psychic'),
    'backs off (rogue, kiln)': ('kiln', 'rogue', 10, 'Sorrel backs off 30 feet down the hall.'),
    'no reaction again (rogue, shrine)': ('shrine', 'rogue', 10, 'No reaction.'),
}
SHEETS = {'warlock': lambda: warlock(hp=60, gear=['dagger']), 'wizard': lambda: without_shield(wizard(hp=60)),
          'rogue': lambda: rogue(speed='30 ft.')}


def build(test, room, sheet, die):
    arena = Arena(test, room, sheet=SHEETS[sheet](), roll=lambda: die)
    arena.act(KILN_OPEN if room == 'kiln' else SHRINE_OPEN)
    return arena


def state_view(runtime):
    revision, state = runtime.load()
    return {'revision': revision, 'combat': state.get('combat'), 'actors': state.get('actors'),
            'refused_attempts': [{k: v for k, v in a.items() if k not in ('at', 'time', 'recorded_at')}
                                 for a in state.get('refused_attempts') or ()]}


def record(case):
    room, sheet, die, text = CASES[case]
    out = {}

    class Run(unittest.TestCase):
        def runTest(inner):
            arena = build(inner, room, sheet, die)
            try:
                KitChatBridge(arena.runtime, arena.adjudicator).prepare(text, 't', one_pass=True)
                out['ruling'] = None
            except PendingRuling as exc:
                out['ruling'] = pending_ruling_result(exc)
            out['after'] = state_view(arena.runtime)

    result = unittest.TestResult()
    Run().run(result)
    if result.errors or result.failures:
        raise SystemExit((result.errors or result.failures)[0][1])
    return out


def main():
    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    data = {'main_sha': head, 'cases': {name: {'room': c[0], 'sheet': c[1], 'die': c[2], 'text': c[3], **record(name)}
                                        for name, c in CASES.items()}}
    Path(sys.argv[1]).write_text(json.dumps(data, indent=1, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
