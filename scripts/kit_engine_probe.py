#!/usr/bin/env python3
"""Offline engine probe for the 6c variety scenarios: no model, no network, no API key.

Each scenario line goes through Room6CAdjudicator (the engine read of the player's act) and,
when it resolves, its events are committed so later lines see the changed room. The output is
the engine's read per line: the resolution kind and its public event, or the pending ruling.
This checks the engine half of the batch runner (PR #48); the DM model's voice is not run.

    env -u PYTHONPATH python3 scripts/kit_engine_probe.py tests/scenarios/6c_variety.json \
        --sheets DIR [--fixture tests/fixtures/level_01_area_06c.json] [--seed 0] [--json OUT]
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.pop('OPENAI_API_KEY', None)

from runtime.kit_agent import PendingRuling, Room6CAdjudicator  # noqa: E402
from runtime.state_context import InvalidChange, Runtime  # noqa: E402


def roll_text(line, sheet):
    """The batch runner's report, in Avrae's real output format: a check as
    '<PC> makes a Deception check! 1d20 (12) + 10 = `22`', then any scripted 'avrae' block
    (To Hit / Damage / Initiative / spell output), each on its own line after the player's."""
    if not isinstance(line, dict):
        return ''
    text = ''
    roll = line.get('roll')
    if roll:
        skill = roll['skill']
        bonus = int(((sheet or {}).get('skills') or {}).get(skill, 0))
        die = max(1, min(20, int(roll['total']) - bonus))
        name = skill.replace('_', ' ').title().replace(' Of ', ' of ')
        article = 'an' if name[0] in 'AEIOU' else 'a'
        sign = '+' if bonus >= 0 else '-'
        text += (f"\n{(sheet or {}).get('name', 'PC')} makes {article} {name} check! "
                 f"1d20 ({die}) {sign} {abs(bonus)} = `{die + bonus}`")
    if line.get('avrae'):
        text += '\n' + line['avrae']
    return text


def sheet_for(scenario, sheets):
    name = scenario.get('sheet') or scenario.get('character')
    if not name or not sheets:
        return None
    for candidate in (Path(sheets) / name, Path(sheets) / f'{name}.json',
                      ROOT / 'tests' / 'fixtures' / 'characters' / name):
        if candidate.is_file():
            return json.loads(candidate.read_text())
    return None


def probe(scenario, fixture, sheets, seed, raise_toll=True):
    source = json.loads(Path(fixture).read_text())
    with tempfile.TemporaryDirectory() as temp:
        runtime = Runtime(Path(temp) / 'probe.sqlite')
        with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{seed:032x}'):
            runtime.initialize(source, 'area_06c')
        sheet = sheet_for(scenario, sheets)
        if sheet:
            try:
                runtime.set_player_sheet(sheet)
            except InvalidChange as error:
                print(f'  (sheet not loaded: {error})', file=sys.stderr)
        if raise_toll:
            # The scenarios' "if they ask for money" lines assume the dealer has demanded the
            # toll, which the DM model does in a real run. Record that demand up front.
            from runtime import kit_toll
            revision, state = runtime.load()
            events = []
            for key, (toll, body) in kit_toll.here(runtime.source(), state).items():
                body.update(status='demanded', demanded_by=toll['demanded_by'])
                events.append(kit_toll.event(key, body, 'Probe: the dealer demands the toll on arrival.'))
            if events:
                runtime.commit('probe-toll', revision, events)
        adjudicator = Room6CAdjudicator(source=runtime.source())
        out = []
        for index, line in enumerate(scenario.get('lines') or scenario.get('turns') or []):
            text = (line.get('line') or line.get('text')) if isinstance(line, dict) else line
            action = text + roll_text(line, sheet)
            revision, state = runtime.load()
            try:
                result = adjudicator.resolve(action, revision, state)
                runtime.commit(f'probe-{index}', revision, list(result.events))
                out.append({'line': index + 1, 'action': action, 'kind': result.kind,
                            'public': result.public_event})
            except PendingRuling as error:
                out.append({'line': index + 1, 'action': action, 'kind': 'pending', 'public': str(error)})
            except InvalidChange as error:
                out.append({'line': index + 1, 'action': action, 'kind': 'invalid', 'public': str(error)})
        runtime.close()
        return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('scenarios')
    parser.add_argument('--fixture', default=str(ROOT / 'tests' / 'fixtures' / 'level_01_area_06c.json'))
    parser.add_argument('--sheets')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--only', nargs='*')
    parser.add_argument('--json')
    parser.add_argument('--no-toll', action='store_true', help='do not record the dealer\'s toll demand first')
    args = parser.parse_args()
    data = json.loads(Path(args.scenarios).read_text())
    scenarios = data.get('scenarios', data) if isinstance(data, dict) else data
    report = {}
    for scenario in scenarios:
        sid = scenario.get('id')
        if args.only and sid not in args.only:
            continue
        report[sid] = probe(scenario, args.fixture, args.sheets, args.seed, not args.no_toll)
        print(f'== {sid} ({scenario.get("sheet") or scenario.get("character")})')
        for row in report[sid]:
            action = row['action'].replace('\n', '\n       | ')
            print(f"  {row['line']}. [{row['kind']}] {action}\n       -> {row['public']}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
