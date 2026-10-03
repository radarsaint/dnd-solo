#!/usr/bin/env python3
"""Automatic part of grading a kit_batch_runner output directory.

Reads <out>/<scenario>/turns.jsonl and prints (or writes with --md) a markdown table:
what the engine did with each scripted line (action_kind or the stall message),
rejections and abandons, latency, and the always-on checks that a regex can see:

  TC-4a/4b  numbers in public text: DC, modifiers, totals, "rolled", "+N"
  TC-3e     food or drink served or offered (flagged for a human to confirm)
  TC-5b     the turn hands back to the player (ends on a question)

Judgment checks (does the NPC play the ruse, is the toll a real exchange, does
Uktarl flee as written) need a person or a model reading transcript.md; this
script only collects the evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

NUMBERS = re.compile(r"\bDC\s*\d+|\bmodifier|\bbonus\b|[+]\s?\d+\b|\b\d+\s*vs\.?\b|\btotal of\b|\brolled (?:an? )?\d|"
                     r"\bpassive (?:perception|insight)\b", re.I)
REFRESH = re.compile(r"\b(wine|ale|beer|cordial|brandy|tea|bread|cheese|meat|refreshment|drink|cup|goblet|glass)\w*", re.I)
NEGATED = re.compile(r"\b(no|none|nothing|without|not a|never)\b[^.]{0,40}\b(wine|ale|drink|cup|bread|refreshment|crumb)", re.I)
STALLS = {'Fights are not run': 'combat stall', 'covers area 6c only': 'left the room (slice ends)',
          'needs a room/rules ruling': 'physical action refused', 'Spell effects': 'spell refused'}


def stall_label(msg):
    for key, label in STALLS.items():
        if key in (msg or ''):
            return label
    return (msg or 'stalled')[:60]


def kit_lines(spoken, player_line):
    """Public text minus the engine's restatement of the player's own words."""
    out = []
    for line in (spoken or '').splitlines():
        if player_line and player_line[:40] in line:
            continue
        out.append(line)
    return '\n'.join(out)


def grade(out):
    rows, lat_total, lat_engine, lat_dm = [], [], [], []
    for d in sorted((p for p in out.iterdir() if (p / 'turns.jsonl').exists()),
                    key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', p.name)]):
        recs = [json.loads(l) for l in (d / 'turns.jsonl').read_text().splitlines() if l.strip()]
        for r in recs:
            text = kit_lines(r.get('spoken'), r.get('player_line'))
            committed = r['outcome'] == 'committed'
            flags = []
            if committed and NUMBERS.search(text):
                flags.append('numbers:' + NUMBERS.search(text).group(0))
            if committed and REFRESH.search(text) and not NEGATED.search(text):
                flags.append('refreshment?:' + REFRESH.search(text).group(0))
            if committed and not text.rstrip().endswith('?'):
                flags.append('no handoff question')
            if r['kind'] == 'action' and committed:
                lat_total.append(r['total_ms'])
                lat_engine.append(r.get('prepare_ms', 0) + r.get('complete_ms', 0))
                lat_dm.append(r.get('dm_ms', 0))
            what = (r.get('action_kind') or ('opening' if r['kind'] == 'opening' else '')) if committed else \
                stall_label(r.get('message')) if r['outcome'] == 'pending_ruling' else r['outcome']
            rows.append({'scenario': d.name, 'step': r['step'], 'outcome': r['outcome'], 'engine_read': what,
                         'event': (r.get('accepted_event') or '')[:90], 'rejections': len(r.get('rejections') or []),
                         'degraded': bool(r.get('degraded')), 'total_s': round(r['total_ms'] / 1000, 1),
                         'flags': flags})
    def stats(xs):
        return {'n': len(xs), 'median_s': round(statistics.median(xs) / 1000, 1) if xs else None,
                'max_s': round(max(xs) / 1000, 1) if xs else None}
    return rows, {'player_turn_total': stats(lat_total), 'engine_only': stats(lat_engine), 'dm_model': stats(lat_dm)}


def to_md(rows, lat):
    out = ['| Scenario | Step | Outcome | Engine read the line as | Rejections | Degraded | Time (s) | Auto flags |',
           '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in rows:
        out.append(f"| {r['scenario']} | {r['step']} | {r['outcome']} | {r['engine_read']} | {r['rejections']} | "
                   f"{'yes' if r['degraded'] else ''} | {r['total_s']} | {'; '.join(r['flags'])} |")
    out += ['', '| Latency (committed player turns) | n | median (s) | max (s) |', '| --- | --- | --- | --- |']
    for k, v in lat.items():
        out.append(f"| {k} | {v['n']} | {v['median_s']} | {v['max_s']} |")
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--md', help='write the markdown table here')
    ap.add_argument('--json', help='write rows and latency as JSON here')
    a = ap.parse_args(argv)
    rows, lat = grade(Path(a.out))
    md = to_md(rows, lat)
    if a.md:
        Path(a.md).write_text(md + '\n')
    if a.json:
        Path(a.json).write_text(json.dumps({'rows': rows, 'latency': lat}, indent=1))
    print(md)


if __name__ == '__main__':
    main()
