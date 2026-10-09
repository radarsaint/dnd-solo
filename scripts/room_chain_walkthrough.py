#!/usr/bin/env python3
"""Scripted walkthrough: one character through several rooms in one session (room loader
acceptance test, docs/architecture/ROOM_LOADER.md). No model, no network, dice pinned.

The chain: area 6c -> the synthetic watchroom (barged into) -> the Area 17a stub (a broken
room refused mid-chain, then bypassed) -> back to the watchroom, restored as it was left.
Room files are not edited: the links between them are added to temporary copies, because
which rooms truly connect is room content (GPT's for 17a), not loader data.

    env -u PYTHONPATH python3 scripts/room_chain_walkthrough.py [--write tests/playtests/<file>.md]

tests/test_kit_room_loader.py runs the same chain and asserts on it.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_brief, kit_rooms  # noqa: E402
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import Runtime  # noqa: E402

SHEET = ROOT / 'tests/fixtures/characters/nik.json'
SEED = 'room-chain-0'
LINES = [
    ('6c', "I'll play a hand. Ten gold."),
    ('6c', 'I stand.'),
    ('6c', 'I look in the tub.'),
    ('6c', "While they're gaping, I scoop a handful of coins from the pot and pocket them.\n"
           'Nik makes a Sleight of Hand check! 1d20 (14) + 10 = `24`'),
    ('6c', 'I cast Fireball at the middle of the card table.\nNik casts Fireball!\n'
           '**Damage**: 8d6 (4, 3, 5, 2, 6, 1, 4, 3) [fire] = `28`'),
    ('6c', 'Rolling initiative.\n**Initiative**: 1d20 (12) + 2 = `14`'),
    ('6c', "Whoever's still standing, I hit with Fire Bolt.\nNik casts Fire Bolt!\n"
           '**To Hit**: 1d20 (12) + 7 = `19`\n**Damage**: 2d10 (4, 5) [fire] = `9`'),
    ('6c', 'I walk out the south door.'),
    ('watchroom', 'I shove the iron door open and charge in.'),           # barge in: no look first
    ('watchroom', 'I open the chest and look inside.'),                   # full exploration at once
    ('watchroom', 'I head down the back stair.'),                         # the warden guards it: a contest
    ('watchroom', 'Acrobatics 25'),                                       # past him; only now the PC moves
    ('17a', 'I go through the collapsed arch.'),                          # a room that cannot mount
    ('17a', 'I walk on down the side passage.'),                          # bypass 17a
]


def build_chain(folder):
    """Temporary copies of the three room files, linked into a chain, plus a broken room."""
    folder = Path(folder)
    read = lambda p: json.loads((ROOT / p).read_text(encoding='utf-8'))  # noqa: E731
    sixc, watch, stub = (read('tests/fixtures/level_01_area_06c.json'),
                         read('tests/fixtures/rooms/watchroom.json'), read('rooms/level_01_area_17a.json'))
    sixc['areas']['south_passage']['room_link'] = {'room': str(folder / 'watchroom.json'), 'area': 'landing'}
    watch['areas']['stair_down']['room_link'] = {'room': str(folder / '17a.json'), 'area': 'area_17a_doors'}
    stub['areas']['side_passage'] = {'name': 'Side passage', 'outside': True,
                                     'room_link': {'room': str(folder / 'watchroom.json'), 'area': 'stair_down'}}
    stub['areas']['arch'] = {'name': 'Collapsed arch', 'outside': True,
                             'room_link': {'room': str(folder / 'broken.json'), 'area': 'hall'}}
    stub['exits']['side'] = {'name': 'the side passage', 'areas': ['area_17a_doors', 'side_passage'], 'secret': False,
                             'go_text': {'area_17a_doors': 'You walk on down the side passage, past the foyer doors.'},
                             'labels': {'area_17a_doors': 'A side passage runs on past the doors.',
                                        'side_passage': 'Back to the foyer doors.'}}
    stub['exits']['arch_way'] = {'name': 'the collapsed arch', 'areas': ['area_17a_doors', 'arch'], 'secret': False,
                                 'labels': {'area_17a_doors': 'A collapsed arch, half blocked.',
                                            'arch': 'Back to the foyer doors.'}}
    for name, body in (('6c', sixc), ('watchroom', watch), ('17a', stub)):
        (folder / f'{name}.json').write_text(json.dumps(body), encoding='utf-8')
    (folder / 'broken.json').write_text('{"id": "broken-room", "areas": {"hall": {"name": "Hall"}}}', encoding='utf-8')
    return folder / '6c.json'


def first_packet(bridge):
    """Kit's first framing in the room now mounted: time to the prepared packet."""
    started = time.perf_counter()
    packet = bridge.prepare(opening=True, one_pass=True)
    elapsed = (time.perf_counter() - started) * 1000
    bridge.abandon(packet['turn_id'])
    return packet, elapsed


def snapshot(runtime):
    source, state = runtime.source(), runtime.load()[1]
    sheet = kit_rooms.fold_pc(source, state)[0] or {}  # HP and gold as they stand, room effects included
    return {'room': source['id'], 'area': state['area'], 'stage': kit_rooms.stage(source, state),
            'hp': sheet.get('hp'), 'gold': sheet.get('gold_gp'), 'carried': [c['item'] for c in state.get('carried') or []],
            'rooms': {key: body['resolution'] for key, body in (state.get('rooms') or {}).items()}}


def run(folder):
    """Play the chain; returns (records, runtime). Every turn's events plus the story beat
    the bridge would add are committed together, as turn_events does."""
    first = build_chain(folder)
    db = Path(folder) / 'chain.sqlite'
    started = time.perf_counter()
    started_packet = start_session(db, SHEET, room=first)
    records = [{'line': '[start --room 6c]', 'kind': 'start', 'public': started_packet['prepared'].get('turn_id') and
                'Opening packet staged.', 'ms_to_first_packet': round((time.perf_counter() - started) * 1000, 1),
                **snapshot(Runtime(db))}]
    runtime = Runtime(db)
    # One adjudicator and one bridge for the whole session, as a long-lived host runs.
    adjudicator = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10)
    bridge = KitChatBridge(runtime, adjudicator)
    bridge.abandon(started_packet['prepared']['turn_id'])
    for number, (_, line) in enumerate(LINES, 1):
        revision, state = runtime.load()
        state['roll_seed'] = SEED
        source = runtime.source()
        adjudicator.mount(source)  # what prepare_turn does every turn
        record = {'line': line}
        try:
            resolution = adjudicator.resolve(line, revision, state)
        except PendingRuling as exc:
            record.update(kind='pending', public=str(exc), host_error=getattr(exc, 'host_error', None),
                          **snapshot(runtime))
            records.append(record)
            continue
        events = list(resolution.events)
        after = runtime.preview_state(revision, events)
        beat = kit_brief.beat_event(source, after, None, f't{number}')
        if beat:
            events.append(beat)
        began = time.perf_counter()
        runtime.commit(f't{number}', revision, events)
        record.update(kind=resolution.kind, public=resolution.public_event,
                      ms_commit=round((time.perf_counter() - began) * 1000, 1))
        if runtime.source()['id'] != source['id']:
            packet, elapsed = first_packet(bridge)
            record.update(mounted=runtime.source()['id'], ms_first_packet=round(elapsed, 1),
                          ms_transition=round(record['ms_commit'] + elapsed, 1))
        now = runtime.source(), runtime.load()[1]
        made = kit_brief.brief(*now)
        record['brief'] = {k: v for k, v in made.items() if k in ('stage', 'resolved', 'raise_now', 'tease')}
        record['brief']['heard'] = [f"{p['label']} ({p['heard']})" for p in made['present'] if p.get('heard')]
        record.update(snapshot(runtime))
        records.append(record)
        # The scripted player declines every reaction the engine offers (PR-H checkpoints), so
        # the chain's damage stays what the 6c walkthrough documents.
        guard = 0
        while ((runtime.load()[1].get('combat') or {}).get('awaiting') or {}).get('kind') == 'reaction_window' \
                and guard < 8:
            guard += 1
            revision, state = runtime.load()
            answer = adjudicator.resolve('No, let it hit.', revision, state, choice={'react': 'decline'})
            runtime.commit(f't{number}r{guard}', revision, list(answer.events))
            records.append({'line': 'No, let it hit.', 'kind': answer.kind, 'public': answer.public_event,
                            **snapshot(runtime)})
    return records, runtime


def markdown(records):
    out = ['# Room loader walkthrough: one character, several rooms, one session', '',
           'Generated by `scripts/room_chain_walkthrough.py` (no model; dice and deck pinned). Engine '
           'output only: the `public` line is the adjudicated event Kit voices, not Kit\'s prose. '
           'Times are this box, one run; see the PR for medians.', '',
           'Chain: 6c -> watchroom (synthetic, barged into) -> 17a stub (broken arch refused, then '
           'bypassed) -> back to the watchroom as it was left.', '']
    for n, r in enumerate(records):
        out.append(f"## {n}. `{r['line'].splitlines()[0]}`")
        out.append('')
        out.append(f"- room `{r['room']}`, area `{r['area']}`, stage **{r['stage']}**; HP {r['hp']}, gold {r['gold']}"
                   + (f", carrying {len(r['carried'])} taken item(s)" if r['carried'] else ''))
        out.append(f"- `{r['kind']}`: {r['public']}")
        if r.get('mounted'):
            out.append(f"- **mounted `{r['mounted']}`** on arrival: commit+mount {r['ms_commit']} ms, first packet "
                       f"{r['ms_first_packet']} ms (transition {r['ms_transition']} ms). Rooms behind: {r['rooms']}")
        if r.get('ms_to_first_packet'):
            out.append(f"- start to first packet: {r['ms_to_first_packet']} ms")
        if r.get('host_error'):
            out.append(f"- host error: {r['host_error']['problems']}")
        if r.get('brief', {}).get('raise_now'):
            out.append(f"- brief raise_now: {r['brief']['raise_now']}")
        if r.get('brief', {}).get('tease'):
            tease = r['brief']['tease']
            out.append(f"- doorway brief: \"{tease['text']}\"" + (f" -> hook `{tease['points_to']}`" if tease.get('points_to') else '')
                       + (f"; heard: {', '.join(r['brief']['heard'])}" if r['brief']['heard'] else ''))
        out.append('')
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', help='write the markdown transcript here')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        records, runtime = run(folder)
        runtime.close()
    text = markdown(records)
    if args.write:
        Path(args.write).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
