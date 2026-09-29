#!/usr/bin/env python3
"""Run Kit's area 6c room with a real OpenAI model on two code versions.

This is an evidence-gathering harness, not a test. It exports the baseline ref
and the candidate ref into separate temporary directories (your checkout is not
touched), runs the same fixed player inputs through each version's own
``KitAgent`` with a real model, and writes:

  transcripts/   player-facing text only (what a player or blind reviewer sees)
  traces/        Kit's private decisions (DM-only; keep away from reviewers)
  latency.csv    per-turn wall-clock time, model calls, and token usage
  blind_pairs.json  input for scripts/blind_performance_review.py
  blind/review.md   randomized A/B reviewer packet (answer key: blind_answer_key.json)
  run.json       model, refs, SHAs, fixture hash, settings

Arms (fresh room database each):
  main               room opening, Nik's greeting, then a follow-up (P2)
  memory_relevant    opening, a lucky-coin boast, then "Deal me in" (P3)
  memory_ablated     same as memory_relevant, but Kit's episodes hidden on the probe
  memory_irrelevant  opening, the tub stunt (P6, unrelated), then the same probe
  other_scene        opening, carving investigation (P7), then the tub stunt (P6)

The runtime is hard-wired to area 6c (kit_agent.py area check, speaker and
focus_actor enums), so no second playable room or cast exists yet. ``other_scene``
is the closest available proxy: an investigation and a ruling where the dealer
should NOT carry the turn. It is not a transfer test.

Usage (requires OPENAI_API_KEY; nothing is faked without it):
  python scripts/run_kit_live_comparison.py --model gpt-5
  python scripts/run_kit_live_comparison.py --model gpt-5 --arms main,memory_relevant --samples 2
  python scripts/run_kit_live_comparison.py --check     # export + import both refs, no model calls
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = '79173a139102f7fc619f23b11b3a0253a993fbcc'
FIXTURE_REL = 'tests/fixtures/level_01_area_06c.json'

NIK_GREETING = "Hi, I'm Nik. I wasn't expecting to find people gambling. Whats going on here?"
P2_FOLLOW_UP = 'Ten gold for passage? What happens if I say no?'
P3_JOIN = 'Deal me in. What are we playing?'
RELEVANT_SETUP = 'I set my lucky silver coin on the table and tell him I never lose with it.'
P6_TUB = 'I tip the stone tub over and use it as cover.'
P7_CARVING = 'I study those tiny figures in the carving while they argue.'

# Each step: (player input or None for the opening, use_memory)
ARMS = {
    'main': [(None, True), (NIK_GREETING, True), (P2_FOLLOW_UP, True)],
    'memory_relevant': [(None, True), (RELEVANT_SETUP, True), (P3_JOIN, True)],
    'memory_ablated': [(None, True), (RELEVANT_SETUP, True), (P3_JOIN, False)],
    'memory_irrelevant': [(None, True), (P6_TUB, True), (P3_JOIN, True)],
    'other_scene': [(None, True), (P7_CARVING, True), (P6_TUB, True)],
}
EXPECTATIONS = {
    'main': 'The dealer answers Nik\'s surprise and question as spoken, tries something beyond a price, '
            'and changes tactic on the refusal question without a fabricated threat or result.',
    'memory_relevant': 'Stated in advance: the invitation should intelligibly pick up the lucky-coin boast '
                       '(dealer tactic, Kit framing, or both) without inventing a wager or outcome.',
    'memory_ablated': 'Kit\'s episodes are hidden on the probe; public dialogue history is NOT hidden. Compare '
                      'with memory_relevant to see what her own memory adds beyond the transcript.',
    'memory_irrelevant': 'The unrelated tub ruling should not redirect the card invitation.',
    'other_scene': 'The dealer should not swallow the investigation; the ruling on the fixed tub is clear, '
                   'Kit may enjoy the audacity, and a legal follow-up stays open.',
}


def git(*args):
    return subprocess.run(['git', *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def export_ref(ref, dest):
    """Extract a commit's tree with git archive; never touches the working checkout."""
    data = subprocess.run(['git', 'archive', '--format=tar', ref], cwd=REPO, check=True,
                          capture_output=True).stdout
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(dest, filter='data')


# ---------------------------------------------------------------- worker side

class AccountBlocked(SystemExit):
    """The API account cannot serve requests (auth, quota, or billing)."""

def worker(args):
    sys.path.insert(0, str(args.root))
    from runtime import kit_agent
    from runtime.state_context import InvalidChange, Runtime

    class HarnessModel(kit_agent.OpenAIResponsesModel):
        """The version's own adapter and instructions, with timing and token capture.

        max_output_tokens is configurable because reasoning models spend output
        tokens on reasoning; both versions receive identical settings.
        """
        def __init__(self, model):
            super().__init__(model)
            self.calls = []

        def _complete(self, instructions, payload, name, schema):
            body = {'model': self.model, 'store': False, 'max_output_tokens': args.max_output_tokens,
                    'input': [{'role': 'system', 'content': instructions},
                              {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                    'text': {'format': {'type': 'json_schema', 'name': name, 'strict': True,
                                        'schema': schema}}}
            if args.reasoning_effort:
                body['reasoning'] = {'effort': args.reasoning_effort}
            request = kit_agent.urllib.request.Request(
                self.endpoint, json.dumps(body).encode(),
                {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
                method='POST')
            started = time.monotonic()
            call = {'stage': name}
            try:
                with kit_agent.urllib.request.urlopen(request, timeout=args.timeout) as response:
                    result = json.load(response)
            except kit_agent.urllib.error.HTTPError as exc:
                detail = exc.read().decode('utf-8', 'replace')[:500]
                if exc.code in (401, 403) or 'insufficient_quota' in detail:
                    # Account/billing/auth failure: nothing about Kit can be learned. Stop the
                    # whole run instead of writing a folder of rejected turns that looks like data.
                    raise AccountBlocked(f'HTTP {exc.code}: {detail}') from exc
                call.update(seconds=round(time.monotonic() - started, 3), error=f'HTTP {exc.code}: {detail}')
                self.calls.append(call)
                raise InvalidChange(f'Model request failed: HTTP {exc.code}: {detail}') from exc
            except kit_agent.urllib.error.URLError as exc:
                call.update(seconds=round(time.monotonic() - started, 3), error=str(exc))
                self.calls.append(call)
                raise InvalidChange('Model request could not connect') from exc
            call.update(seconds=round(time.monotonic() - started, 3), status=result.get('status'),
                        usage=result.get('usage'), model=result.get('model'))
            self.calls.append(call)
            if result.get('status') != 'completed':
                raise InvalidChange(f"Model did not complete: {result.get('status')} "
                                    f"{result.get('incomplete_details')}")
            texts = [item.get('text') for output in result.get('output', [])
                     for item in output.get('content', []) or [] if item.get('type') == 'output_text']
            if len(texts) != 1:
                raise InvalidChange('Model returned no single structured result')
            return json.loads(texts[0])

    fixture = json.loads((args.root / FIXTURE_REL).read_text(encoding='utf-8'))
    results = []
    with tempfile.TemporaryDirectory() as temp:
        for arm in args.arms:
            for sample in range(1, args.samples + 1):
                db = Path(temp) / f'{arm}-{sample}.sqlite'
                runtime = Runtime(str(db))
                runtime.initialize(fixture, fixture['starting_area'])
                model = HarnessModel(args.model)
                agent = kit_agent.KitAgent(runtime, model, kit_agent.Room6CAdjudicator(
                    perception=args.perception, insight=args.insight))
                for step, (action, use_memory) in enumerate(ARMS[arm]):
                    before = len(model.calls)
                    started = time.monotonic()
                    turn = {'arm': arm, 'sample': sample, 'step': step,
                            'player_input': action or '[scene entry]', 'use_memory': use_memory}
                    try:
                        result = agent.opening() if action is None else agent.turn(action, use_memory=use_memory)
                        turn.update(outcome='committed', spoken=result['spoken'],
                                    public_event=result['public_event'],
                                    runtime_timing=result.get('timing'),
                                    trace=runtime.recent_kit_turns(limit=1)[-1]['trace'])
                    except kit_agent.PendingRuling as exc:
                        turn.update(outcome='pending_ruling', spoken=str(exc))
                    except InvalidChange as exc:
                        turn.update(outcome='rejected', spoken=None, error=str(exc))
                    turn['wall_s'] = round(time.monotonic() - started, 3)
                    turn['model_calls'] = model.calls[before:]
                    results.append(turn)
                    print(f"  {args.label} {arm}#{sample} step {step}: {turn['outcome']} "
                          f"{turn['wall_s']}s", file=sys.stderr, flush=True)
                runtime.close()
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


# ----------------------------------------------------------- orchestrator side

def transcript_markdown(label_hidden, turns):
    lines = [f'# Spoken transcript: {label_hidden}', '',
             'Player-facing text only: no private trace or DM-only fact. The filename names the version; use blind_pairs.json for blind review.', '']
    for turn in turns:
        lines += [f"**Player:** {turn['player_input']}", '']
        if turn['outcome'] == 'committed':
            lines += [turn['spoken'], '']
        elif turn['outcome'] == 'pending_ruling':
            lines += [f"_(pending ruling, no turn committed)_ {turn['spoken']}", '']
        else:
            lines += ['_(turn rejected by validation; nothing was shown to the player)_', '']
    return '\n'.join(lines)


def spoken_block(turns):
    parts = []
    for turn in turns:
        parts.append(f"Player: {turn['player_input']}")
        parts.append(turn['spoken'] if turn['outcome'] != 'rejected' else '(turn rejected; nothing shown)')
    return '\n\n'.join(parts)


def orchestrate(args):
    refs = {'baseline': args.baseline_ref, 'candidate': args.candidate_ref}
    shas = {label: git('rev-parse', ref) for label, ref in refs.items()}
    if not args.check and not os.environ.get('OPENAI_API_KEY'):
        print('OPENAI_API_KEY is not set. Nothing was run and no output was written.', file=sys.stderr)
        return 2
    if not args.check and not args.model:
        print('--model is required for a real run.', file=sys.stderr)
        return 2
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or REPO / 'tests/playtests/live-runs' / f'{stamp}-{args.model or "check"}'
    with tempfile.TemporaryDirectory() as temp:
        raw, jobs = {}, []
        for label, sha in shas.items():
            root = Path(temp) / label
            export_ref(sha, root)
            if args.check:
                probe = subprocess.run([sys.executable, '-c', (
                    'import sys, json, tempfile, pathlib; sys.path.insert(0, sys.argv[1]);'
                    'from runtime.kit_agent import KitChatBridge; from runtime.state_context import Runtime;'
                    'd = tempfile.mkdtemp(); r = Runtime(str(pathlib.Path(d) / "x.sqlite"));'
                    f'f = json.loads((pathlib.Path(sys.argv[1]) / "{FIXTURE_REL}").read_text());'
                    'r.initialize(f, f["starting_area"]);'
                    'p = KitChatBridge(r).prepare(opening=True, turn_id="probe");'
                    'print(sorted(p["schema"]["properties"]["public_brief"]["properties"]))'), str(root)],
                    capture_output=True, text=True)
                status = 'ok' if probe.returncode == 0 else 'FAILED'
                print(f'{label} {sha[:7]}: import/prepare {status}; brief fields {probe.stdout.strip()}'
                      f'{probe.stderr.strip()[-400:]}')
                continue
            # One worker per (version, arm); --jobs of them run at once. Turns inside an
            # arm stay sequential, and latency is timed per request inside each worker.
            for arm in args.arms:
                output = Path(temp) / f'{label}-{arm}.json'
                command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--label', label,
                           '--root', str(root), '--output', str(output), '--model', args.model,
                           '--arms', arm, '--samples', str(args.samples),
                           '--perception', str(args.perception), '--insight', str(args.insight),
                           '--max-output-tokens', str(args.max_output_tokens), '--timeout', str(args.timeout)]
                if args.reasoning_effort:
                    command += ['--reasoning-effort', args.reasoning_effort]
                jobs.append((label, root, output, command))
        if not args.check:
            print(f'Running {len(jobs)} workers with {args.model}, {args.jobs} at a time...', file=sys.stderr)
            pending, running = list(jobs), []
            while pending or running:
                while pending and len(running) < args.jobs:
                    label, root, output, command = pending.pop(0)
                    running.append((subprocess.Popen(command, cwd=root), label, output))
                for item in list(running):
                    if item[0].poll() is not None:
                        running.remove(item)
                        if item[0].returncode != 0:
                            for other in running:
                                other[0].kill()
                            raise SystemExit(f'Worker for {item[1]} failed ({item[0].returncode}); '
                                             'no output was written.')
                time.sleep(0.5)
            for label, _, output, _ in jobs:
                raw.setdefault(label, []).extend(json.loads(output.read_text(encoding='utf-8')))
        if args.check:
            return 0
    write_outputs(out, raw, refs, shas, args, stamp)
    return 0


def write_outputs(out, raw, refs, shas, args, stamp):
    (out / 'transcripts').mkdir(parents=True, exist_ok=True)
    (out / 'traces').mkdir(exist_ok=True)
    pairs = []
    with open(out / 'latency.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['version', 'sha', 'arm', 'sample', 'step', 'player_input', 'outcome', 'wall_s',
                         'model_calls', 'call_seconds', 'input_tokens', 'output_tokens', 'reasoning_tokens'])
        for label, turns in raw.items():
            for turn in turns:
                usage = [call.get('usage') or {} for call in turn['model_calls']]
                writer.writerow([
                    label, shas[label][:7], turn['arm'], turn['sample'], turn['step'], turn['player_input'],
                    turn['outcome'], turn['wall_s'], len(turn['model_calls']),
                    ' '.join(str(call.get('seconds')) for call in turn['model_calls']),
                    sum(u.get('input_tokens', 0) for u in usage),
                    sum(u.get('output_tokens', 0) for u in usage),
                    sum((u.get('output_tokens_details') or {}).get('reasoning_tokens', 0) for u in usage)])
    for arm in args.arms:
        for sample in range(1, args.samples + 1):
            by_label = {label: [t for t in turns if t['arm'] == arm and t['sample'] == sample]
                        for label, turns in raw.items()}
            for label, turns in by_label.items():
                name = f'{arm}-{sample}-{label}'
                (out / 'transcripts' / f'{name}.md').write_text(
                    transcript_markdown(f'{arm} sample {sample} ({label})', turns) + '\n', encoding='utf-8')
                (out / 'traces' / f'{name}.json').write_text(json.dumps(
                    [{k: t.get(k) for k in ('step', 'player_input', 'outcome', 'public_event', 'trace',
                                            'error', 'runtime_timing')} for t in turns],
                    indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            pairs.append({
                'case_id': f'{arm} sample {sample}',
                'public_context': 'A fresh area 6c room. Nik, a level 5 Harengon wizard, arrives at the card room. '
                                  'Each continuation is a complete multi-turn sample; read it as one session.',
                'player_input': ' / '.join(turn['player_input'] for turn in by_label['baseline']),
                'candidates': [{'variant_id': f'{label}-{shas[label][:7]}-{arm}-{sample}',
                                'spoken': spoken_block(turns)} for label, turns in by_label.items()]})
    (out / 'blind_pairs.json').write_text(json.dumps(
        {'experiment': f'kit-live-{stamp}', 'pairs': pairs}, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8')
    # Blind A/B packet: randomized left/right per arm/sample, answer key in a separate file.
    sys.path.insert(0, str(REPO / 'scripts'))
    import blind_performance_review as review_tool
    data, digest = review_tool.load_experiment(out / 'blind_pairs.json')
    review, key = review_tool.render_review(data, digest, args.blind_seed)
    (out / 'blind').mkdir(exist_ok=True)
    (out / 'blind' / 'review.md').write_text(review + '\n', encoding='utf-8')
    (out / 'blind_answer_key.json').write_text(json.dumps(key, indent=2, ensure_ascii=False) + '\n',
                                                 encoding='utf-8')
    fixture_bytes = (REPO / FIXTURE_REL).read_bytes()
    (out / 'run.json').write_text(json.dumps({
        'started_utc': stamp, 'model': args.model, 'refs': refs, 'shas': shas,
        'arms': {arm: {'steps': ARMS[arm], 'expectation': EXPECTATIONS[arm]} for arm in args.arms},
        'samples': args.samples, 'perception': args.perception, 'insight': args.insight,
        'max_output_tokens': args.max_output_tokens, 'reasoning_effort': args.reasoning_effort,
        'timeout_s': args.timeout, 'jobs': getattr(args, 'jobs', 1), 'blind_seed': args.blind_seed, 'fixture_sha256_candidate_checkout': hashlib.sha256(fixture_bytes).hexdigest(),
        'python': platform.python_version(),
        'note': ('Same inputs and settings for both versions. Transcripts are player-facing only; traces are '
                 'DM-only. Review transcripts blind before opening traces. Dice for keyed checks come from '
                 'each fresh session\'s random roll_seed, so check outcomes can differ between versions.'),
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {out}')
    print(f'Blind packet: {out / "blind" / "review.md"} (answer key: {out / "blind_answer_key.json"})')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--model', help='OpenAI model ID, e.g. gpt-5')
    parser.add_argument('--baseline-ref', default=DEFAULT_BASELINE)
    parser.add_argument('--candidate-ref', default='HEAD')
    parser.add_argument('--arms', default=','.join(ARMS), help=f'Comma list from: {", ".join(ARMS)}')
    parser.add_argument('--samples', type=int, default=1, help='Independent fresh runs per arm and version')
    parser.add_argument('--perception', type=int, default=4, help="Nik's Wisdom (Perception) modifier")
    parser.add_argument('--insight', type=int, default=4, help="Nik's Wisdom (Insight) modifier (playtest: +4)")
    parser.add_argument('--max-output-tokens', type=int, default=8000,
                        help='Runtime default is 1800; reasoning models may need more. Same for both versions.')
    parser.add_argument('--reasoning-effort', choices=['minimal', 'low', 'medium', 'high'])
    parser.add_argument('--timeout', type=int, default=300, help='Per-request timeout in seconds')
    parser.add_argument('--jobs', type=int, default=1, help='Concurrent (version, arm) workers')
    parser.add_argument('--blind-seed', type=int, default=19, help='Recorded seed for the blind A/B order')
    parser.add_argument('--out', type=Path, help='Output directory (default tests/playtests/live-runs/<stamp>-<model>)')
    parser.add_argument('--check', action='store_true', help='Export and import both refs; no model calls')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--label', help=argparse.SUPPRESS)
    parser.add_argument('--root', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--output', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.arms = [arm.strip() for arm in args.arms.split(',') if arm.strip()]
    unknown = set(args.arms) - set(ARMS)
    if unknown:
        parser.error(f'Unknown arm(s): {", ".join(sorted(unknown))}')
    if args.samples < 1:
        parser.error('--samples must be at least 1')
    return worker(args) if args.worker else orchestrate(args)


if __name__ == '__main__':
    sys.exit(main())
