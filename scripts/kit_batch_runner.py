#!/usr/bin/env python3
"""Batch runner for scripted Kit scenarios (area 6c variety set).

Each scenario gets a fresh kit.sqlite. The runner plays the PLAYER side from a
script (one line per turn, rolls reported Avrae-style) and hands every Kit turn
to a DM backend through the model-agnostic bridge: start -> complete (opening),
then prepare --one-pass -> complete for each line. It never runs `play`, never
reads OPENAI_API_KEY, and strips that variable from every child process.

DM backends
  command  Pipe a request (instructions + packet + any rejection) to a shell
           command on stdin; read one JSON object {decision, performance} from
           stdout. Works with any headless model CLI, e.g. `cursor-agent -p`.
  handoff  Write <handoff>/<scenario>/<step>.a<attempt>.request.json plus a
           compact .digest.json (fields equal to the batch's first packet are
           replaced by "=ref"), then wait for the matching .reply.json. Any agent
           (a Cursor chat, a cloud agent, a person) can be the DM this way.

Output per scenario (in --out/<id>/): kit.sqlite, turns.jsonl (one record per
turn with timings), transcript.md (what the player saw), and timing.json (the
runtime's own per-turn timing). --out/summary.json collects latency stats and
the automatic always-on flags; see scripts/kit_batch_grade.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHEET_DIRS = [REPO / 'tests' / 'fixtures' / 'characters']
MAX_ATTEMPTS = 4          # host_retry: degraded after 2 rejections, abandon after 4
DEGRADE_AFTER = 2

DM_PREFACE = (
    'You are Kit, the DM, inside the dnd-solo KitChatBridge (see AGENTS.md). Read "packet" '
    '(a prepare --one-pass result). Return ONLY one JSON object {"decision": ..., "performance": ...} '
    'that follows packet.instructions and packet.schema. If "rejection" is present, the previous '
    'submission for this same turn was rejected: keep the identical decision ("previous_reply.decision") '
    'and fix the performance per rejection.retry_instruction. No prose outside the JSON.')


def child_env():
    env = {k: v for k, v in os.environ.items() if k != 'OPENAI_API_KEY'}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def kit(*args, input_text=None):
    """Run one kit_agent bridge command; return (parsed json, exit code, ms)."""
    if args and args[0] == 'play':
        raise SystemExit('refusing to run `play`: it calls the paid API')
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', *args], cwd=REPO,
                          capture_output=True, text=True, env=child_env(), input=input_text)
    ms = round((time.perf_counter() - t0) * 1000)
    raw = proc.stdout.strip() or proc.stderr.strip()
    data = None
    for candidate in (raw, raw.splitlines()[-1] if raw else ''):
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    if data is None:
        data = {'stage': 'error', 'raw': raw[-4000:], 'exit': proc.returncode}
    elif not isinstance(data, dict):
        data = {'stage': 'list', 'items': data}
    return data, proc.returncode, ms


def find_sheet(name, extra_dirs):
    for d in [*extra_dirs, *SHEET_DIRS]:
        p = Path(d) / name
        if p.exists():
            return p.resolve()
    raise SystemExit(f'sheet {name} not found in {[str(d) for d in [*extra_dirs, *SHEET_DIRS]]}')


def roll_text(roll, sheet):
    """Avrae-style report in the sum form the engine parses: 'd20 + bonus = total'."""
    skill = roll['skill']
    bonus = int((sheet.get('skills') or {}).get(skill, 0))
    total = int(roll['total'])
    die = max(1, min(20, total - bonus))
    note = '' if die + bonus == total else f' (scripted total {total} impossible with +{bonus}; die clamped)'
    name = skill.replace('_', ' ').title()
    return f' [{name}: I rolled {die} + {bonus} = {die + bonus}]', note


# ---------------------------------------------------------------- DM backends

def dedupe(value, ref):
    if isinstance(value, dict) and isinstance(ref, dict):
        out = {}
        for k, v in value.items():
            if k in ref and v == ref[k] and len(json.dumps(v)) > 200:
                out[k] = '=ref'
            else:
                out[k] = dedupe(v, ref.get(k))
        return out
    return value


class HandoffDM:
    name = 'handoff'

    def __init__(self, root: Path, poll=0.5, timeout=3600):
        self.root, self.poll, self.timeout = root, poll, timeout
        self.root.mkdir(parents=True, exist_ok=True)
        self.ref_path = self.root / 'reference.json'

    def ask(self, scenario, step, attempt, packet, rejection=None, previous=None):
        d = self.root / scenario
        d.mkdir(parents=True, exist_ok=True)
        if not self.ref_path.exists():
            self.ref_path.write_text(json.dumps(packet, ensure_ascii=False, indent=1))
        ref = json.loads(self.ref_path.read_text())
        stem = f'{step:02d}.a{attempt}'
        req = {'scenario': scenario, 'step': step, 'attempt': attempt, 'preface': DM_PREFACE,
               'rejection': rejection, 'previous_reply': previous, 'packet': packet}
        (d / f'{stem}.request.json').write_text(json.dumps(req, ensure_ascii=False))
        digest = dict(req, packet=dedupe(packet, ref), reference=str(self.ref_path))
        reply_path = d / f'{stem}.reply.json'
        (d / f'{stem}.digest.json').write_text(json.dumps(digest, ensure_ascii=False, indent=1))
        (self.root / 'WAITING').write_text(str(reply_path))
        t0 = time.monotonic()
        while not reply_path.exists():
            if time.monotonic() - t0 > self.timeout:
                raise TimeoutError(f'no reply at {reply_path}')
            time.sleep(self.poll)
        time.sleep(0.2)  # let the writer finish
        (self.root / 'WAITING').unlink(missing_ok=True)
        return json.loads(reply_path.read_text())


class CommandDM:
    name = 'command'

    def __init__(self, cmd, timeout=900):
        self.cmd, self.timeout = cmd, timeout

    def ask(self, scenario, step, attempt, packet, rejection=None, previous=None):
        req = json.dumps({'preface': DM_PREFACE, 'rejection': rejection, 'previous_reply': previous,
                          'packet': packet}, ensure_ascii=False)
        proc = subprocess.run(self.cmd, shell=True, input=req, capture_output=True, text=True,
                              timeout=self.timeout, env=child_env())
        out = proc.stdout
        start, end = out.find('{'), out.rfind('}')
        if start < 0:
            raise ValueError(f'DM command returned no JSON: {out[-500:]} {proc.stderr[-500:]}')
        return json.loads(out[start:end + 1])


# ---------------------------------------------------------------- one scenario

def outcome_of(result):
    if result.get('stage'):
        return result['stage']
    return 'committed' if result.get('revision') is not None and 'spoken' in result else 'unknown'


def spoken_of(result):
    return result.get('spoken') or result.get('committed_result', {}).get('spoken') or ''


def dm_turn(dm, db, scen, step, packet, log):
    """Ask the DM, complete, retry per host_retry. Returns (result, record fields)."""
    turn_id = packet['turn_id']
    rejection = previous = None
    dm_ms = complete_ms = 0
    rejections = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        t0 = time.perf_counter()
        try:
            reply = dm.ask(scen, step, attempt, packet, rejection, previous)
        except Exception as exc:  # noqa: BLE001 - recorded, not hidden
            dm_ms += round((time.perf_counter() - t0) * 1000)
            return {'stage': 'dm_error', 'message': str(exc)}, dict(dm_ms=dm_ms, complete_ms=complete_ms,
                                                                   attempts=attempt, rejections=rejections)
        dm_ms += round((time.perf_counter() - t0) * 1000)
        f = Path(db).parent / f'reply-{step:02d}-a{attempt}.json'
        f.write_text(json.dumps(reply, ensure_ascii=False))
        args = ['complete', '--db', db, '--turn-id', turn_id, '--input-file', str(f)]
        if attempt > DEGRADE_AFTER:
            args.append('--degraded')
        result, code, ms = kit(*args)
        complete_ms += ms
        if result.get('stage') != 'rejected':
            return result, dict(dm_ms=dm_ms, complete_ms=complete_ms, attempts=attempt,
                                rejections=rejections, degraded=attempt > DEGRADE_AFTER)
        rejections.append({k: result.get(k) for k in ('message', 'retry_instruction', 'failed_check')
                           if result.get(k)})
        rejection, previous = result, reply
        if result.get('next_step') == 'prepare_again':
            break
    kit('abandon', '--db', db, '--turn-id', turn_id)
    return {'stage': 'abandoned_after_rejections', 'last': rejection}, dict(
        dm_ms=dm_ms, complete_ms=complete_ms, attempts=MAX_ATTEMPTS, rejections=rejections)


def run_scenario(scen, out_root, dm, sheet_dirs):
    sid = scen['id']
    out = out_root / sid
    out.mkdir(parents=True, exist_ok=True)
    db = out / 'kit.sqlite'
    for p in (db, out / 'turns.jsonl'):
        p.unlink(missing_ok=True)
    sheet_path = find_sheet(scen['sheet'], sheet_dirs)
    sheet = json.loads(sheet_path.read_text())
    records = []

    def log(rec):
        records.append(rec)
        with open(out / 'turns.jsonl', 'a') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(f"[{sid} step {rec['step']}] {rec['outcome']} total={rec['total_ms']}ms", flush=True)

    t0 = time.perf_counter()
    started, code, prep_ms = kit('start', '--db', str(db), '--sheet', str(sheet_path))
    packet = started.get('prepared')
    if not packet:
        log({'step': 0, 'kind': 'opening', 'outcome': 'start_failed', 'detail': started, 'total_ms': prep_ms})
        return records
    result, extra = dm_turn(dm, str(db), sid, 0, packet, log)
    log({'step': 0, 'kind': 'opening', 'player_line': None, 'outcome': outcome_of(result),
         'spoken': spoken_of(result), 'prepare_ms': prep_ms, **extra,
         'total_ms': round((time.perf_counter() - t0) * 1000), 'result_excerpt': excerpt(result)})

    for i, turn in enumerate(scen['turns'], 1):
        line = turn['line']
        note = ''
        if turn.get('roll'):
            text, note = roll_text(turn['roll'], sheet)
            line += text
        t0 = time.perf_counter()
        af = out / f'action-{i:02d}.txt'
        af.write_text(line)
        prepared, code, prep_ms = kit('prepare', '--one-pass', '--db', str(db), '--action-file', str(af))
        stage = prepared.get('stage')
        rec = {'step': i, 'kind': 'action', 'player_line': line, 'when': turn.get('when'), 'roll_note': note,
               'prepare_ms': prep_ms}
        if stage != 'one_pass':
            rec.update(outcome=stage, message=prepared.get('message') or prepared.get('raw'),
                       spoken=prepared.get('message', ''), dm_ms=0, complete_ms=0,
                       total_ms=round((time.perf_counter() - t0) * 1000))
            log(rec)
            continue
        result, extra = dm_turn(dm, str(db), sid, i, prepared, log)
        rec.update(outcome=outcome_of(result), spoken=spoken_of(result), **extra,
                   total_ms=round((time.perf_counter() - t0) * 1000),
                   accepted_event=prepared.get('input', {}).get('public', {}).get('accepted_public_event'),
                   action_kind=prepared.get('input', {}).get('public', {}).get('action_kind'),
                   result_excerpt=excerpt(result))
        log(rec)

    timing, _, _ = kit('timing', '--db', str(db))
    (out / 'timing.json').write_text(json.dumps(timing, ensure_ascii=False, indent=1))
    write_transcript(scen, sheet, records, out / 'transcript.md', dm.name)
    return records


def excerpt(result):
    keep = {k: result[k] for k in ('stage', 'committed', 'message', 'degraded', 'soft_warnings', 'revision',
                                   'public_event', 'asked')
            if k in result}
    return keep


def write_transcript(scen, sheet, records, path, backend):
    lines = [f"# {scen['id']}: {scen['title']}", '',
             f"PC: {sheet.get('name')} ({sheet.get('ancestry')} {sheet.get('class')}), sheet `{scen['sheet']}`. "
             f"DM backend: {backend}. Times are wall-clock per turn (prepare + DM + complete).", '']
    for r in records:
        if r['kind'] == 'opening':
            lines += [f"## Opening ({r['outcome']}, {r['total_ms'] / 1000:.1f}s)", '']
        else:
            lines += [f"## Turn {r['step']} ({r['outcome']}, {r['total_ms'] / 1000:.1f}s)", '',
                      f"**Player:** {r['player_line']}", '']
        if r.get('rejections'):
            lines += [f"_Rejected {len(r['rejections'])}x before commit: "
                      + '; '.join((x.get('message') or '')[:160] for x in r['rejections']) + '_', '']
        body = r.get('spoken') or r.get('message') or ''
        lines += ['**Kit:**', '', *(f'> {ln}' if ln else '>' for ln in body.splitlines()), '']
    path.write_text('\n'.join(lines))


# ---------------------------------------------------------------- summary

def summarize(out_root, all_records):
    lat = [r['total_ms'] for recs in all_records.values() for r in recs if r['outcome'] == 'committed']
    summary = {'scenarios': {}, 'latency_ms': {}}
    for sid, recs in all_records.items():
        summary['scenarios'][sid] = [{k: r.get(k) for k in ('step', 'outcome', 'total_ms', 'prepare_ms',
                                                              'dm_ms', 'complete_ms', 'attempts')} for r in recs]
    if lat:
        summary['latency_ms'] = {'n': len(lat), 'median': statistics.median(lat), 'max': max(lat)}
    (out_root / 'summary.json').write_text(json.dumps(summary, indent=1))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--scenarios', default=str(REPO / 'tests' / 'scenarios' / '6c_variety.json'))
    ap.add_argument('--only', help='comma-separated scenario ids, e.g. V1,V3')
    ap.add_argument('--out', required=True)
    ap.add_argument('--sheets-dir', action='append', default=[],
                    help='extra directory for scenario sheets (e.g. bfdm-corpus 6c-variety-sheets)')
    ap.add_argument('--backend', choices=['handoff', 'command'], required=True)
    ap.add_argument('--dm-cmd', help='command backend: shell command reading the request on stdin')
    ap.add_argument('--handoff-dir', help='handoff backend: exchange directory (default <out>/handoff)')
    ap.add_argument('--timeout', type=int, default=3600, help='seconds to wait for one DM reply')
    args = ap.parse_args(argv)
    if os.environ.get('OPENAI_API_KEY'):
        print('note: OPENAI_API_KEY is set in this shell; it is stripped from every child process '
              'and never used.', file=sys.stderr)
    spec = json.loads(Path(args.scenarios).read_text())
    wanted = set(args.only.split(',')) if args.only else None
    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    if args.backend == 'command':
        if not args.dm_cmd:
            ap.error('--backend command needs --dm-cmd')
        dm = CommandDM(args.dm_cmd, timeout=args.timeout)
    else:
        dm = HandoffDM(Path(args.handoff_dir or out_root / 'handoff').resolve(), timeout=args.timeout)
    all_records = {}
    for scen in spec['scenarios']:
        if wanted and scen['id'] not in wanted:
            continue
        all_records[scen['id']] = run_scenario(scen, out_root, dm, [Path(d) for d in args.sheets_dir])
    print(json.dumps(summarize(out_root, all_records)['latency_ms']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
