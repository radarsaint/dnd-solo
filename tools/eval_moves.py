"""Score Kit's move classifier and skill picker on the labelled set
(tests/fixtures/moves/labelled_moves.tsv). Usage: python3 tools/eval_moves.py [--misses]"""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import kit_moves  # noqa: E402

SET = ROOT / 'tests' / 'fixtures' / 'moves' / 'labelled_moves.tsv'


def rows():
    for line in SET.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            move, skill, text = line.split('\t', 2)
            yield move, (None if skill == '-' else skill), text


def score():
    per_move = defaultdict(lambda: [0, 0])
    per_skill = defaultdict(lambda: [0, 0])
    misses = []
    for move, skill, text in rows():
        got = kit_moves.classify(text)
        if move != '*':
            per_move[move][1] += 1
            if got == move:
                per_move[move][0] += 1
            else:
                misses.append(('move', move, got, text))
        if skill:
            picked, _ = kit_moves.pick_skill(text, kind=got)
            per_skill[skill][1] += 1
            if picked == skill:
                per_skill[skill][0] += 1
            else:
                misses.append(('skill', skill, picked, text))
    return per_move, per_skill, misses


def total(table):
    hit = sum(v[0] for v in table.values())
    n = sum(v[1] for v in table.values())
    return hit, n


if __name__ == '__main__':
    per_move, per_skill, misses = score()
    for name, table in (('move', per_move), ('skill', per_skill)):
        hit, n = total(table)
        print(f'{name}: {hit}/{n} = {100 * hit / n:.1f}%')
        for key in sorted(table):
            print(f'  {key}: {table[key][0]}/{table[key][1]}')
    if '--misses' in sys.argv:
        for miss in misses:
            print('MISS', *miss, sep=' | ')
