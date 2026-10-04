#!/usr/bin/env python3
"""Re-run the room-loader review findings against the current checkout.

Evidence for the review of PR #87 (branch kit-room-loader, head when written:
999d4cd). Each row is a finding already posted on that PR. The script exits 0
when every recorded finding still holds, and 1 when one no longer reproduces,
which means the code has moved and the review should be re-read against the
new head.

No model, no network, no API key. Synthetic rooms only.

    env -u PYTHONPATH python3 scripts/room_loader_review_probe.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_agenda, kit_brief, kit_guards, kit_rooms  # noqa: E402
from runtime.kit_agent import (PendingRuling, RoomAdjudicator,  # noqa: E402
                               check_public_content, kit_memory, prepare_opening,
                               prepare_turn, room_intent, room_words)
from runtime.state_context import InvalidChange, Runtime  # noqa: E402

WATCH = ROOT / 'tests/fixtures/rooms/watchroom.json'
SHEET = json.loads((ROOT / 'tests/fixtures/characters/example_pc.json').read_text(encoding='utf-8'))
SECRET = 'doppelganger'
ROWS = []


def record(tag, name, holds, detail):
    ROWS.append((tag, name, bool(holds), detail))
    mark = 'HOLDS' if holds else 'MOVED'
    print(f'  [{tag}] {mark:5}  {name}')
    if detail:
        print(f'         {detail}')


def base_room(rid, inside, link=None, leak=None):
    areas = {
        inside: {'name': f'{rid} room', 'called': f'the {rid} room', 'arrival': f'You reach {rid}.'},
        'beyond': {'name': f'Beyond {rid}', 'called': 'the far side', 'outside': True},
    }
    if link:
        areas['beyond']['room_link'] = link
    source = {
        'id': rid, 'fixture_only': True, 'starting_area': inside, 'areas': areas,
        'exits': {f'{rid}_out': {'name': 'the back stair', 'areas': [inside, 'beyond'], 'secret': False,
                                 'labels': {inside: 'A back stair.', 'beyond': 'The stair up.'}}},
        'facts': {
            f'{rid}_crate': {'area': inside, 'visible': True, 'text': 'A crate.',
                             'handling': {'nouns': ['crate'], 'holds': f'{rid}_in',
                                          'look': f'The {rid} crate holds rope.',
                                          'enter': 'Too small.', 'move': 'Bolted down.'}},
            f'{rid}_in': {'area': inside, 'visible': False, 'text': 'Rope.'},
        },
        'actors': {f'{rid}_a': {'name': 'Keeper', 'location': inside, 'status': 'alive', 'visible': True,
                                'motive': 'Guard the crate.'}},
        'resources': {},
    }
    if leak:
        source['leak_phrases'] = {'phrases': list(leak), 'player_may_name': []}
    return source


def write_room(directory, name, source):
    path = directory / name
    path.write_text(json.dumps(source), encoding='utf-8')
    return path


def mount_outcome(source):
    """'mounted', 'refused', or the exception class a bad file actually raises."""
    with tempfile.TemporaryDirectory() as raw:
        path = write_room(Path(raw), 'room.json', source)
        try:
            kit_rooms.load_room(path)
            return 'mounted'
        except kit_rooms.RoomMountError:
            return 'refused'
        except Exception as exc:
            return type(exc).__name__


def skeleton(**extra):
    return {
        'id': 'probe', 'fixture_only': True, 'starting_area': 'hall',
        'areas': {'hall': {'name': 'Hall'}}, 'exits': {},
        'facts': {'f': {'area': 'hall', 'visible': True, 'text': 'A table.'}},
        'actors': {'a': {'name': 'Local', 'location': 'hall', 'status': 'alive'}},
        'resources': {}, **extra,
    }


def session(directory, source, area, name='room.json'):
    path = write_room(directory, name, source)
    runtime = Runtime(str(directory / f'{name}.sqlite'))
    runtime.initialize(kit_rooms.load_room(path), area)
    runtime.set_player_sheet(SHEET)
    return runtime


def fixed_long_lived_host(directory):
    """The earlier P1: one bridge kept room A's source after room B mounted."""
    directory.mkdir(parents=True, exist_ok=True)
    roomb = write_room(directory, 'roomb.json', base_room('roomb', 'hall'))
    rooma = base_room('rooma', 'parlour', link={'room': str(roomb), 'area': 'hall'})
    runtime = session(directory, rooma, 'parlour', 'rooma.json')
    adjudicator = RoomAdjudicator()
    turns = iter(range(10))

    def commit(action):
        revision, body, _ = prepare_turn(runtime, adjudicator, action, one_pass=True)
        runtime.commit(f't{next(turns)}', revision, body['events'])
        return body['public_event']

    commit('I look in the crate.')
    commit('I go through the back stair.')
    mounted = runtime.source()['id']
    try:
        looked = commit('I look in the crate.')
    except PendingRuling as exc:
        looked = f'PENDING: {exc}'
    runtime.close()
    record('fixed', 'long-lived host reads room B after the mount',
           mounted == 'roomb' and looked.startswith('The roomb crate'),
           f'mounted {mounted}; look -> {looked}')


def fixed_named_exit(directory):
    """The earlier P1: 'the back door' was refused because both exits say 'door'."""
    directory.mkdir(parents=True, exist_ok=True)
    source = skeleton()
    source['areas']['out0'] = {'name': 'Front', 'called': 'the front', 'outside': True}
    source['areas']['out1'] = {'name': 'Back', 'called': 'the back', 'outside': True}
    source['exits'] = {
        'e0': {'name': 'the front door', 'areas': ['hall', 'out0'], 'secret': False,
               'labels': {'hall': 'Front.', 'out0': 'Back.'}},
        'e1': {'name': 'the back door', 'areas': ['hall', 'out1'], 'secret': False,
               'labels': {'hall': 'Back.', 'out1': 'Front.'}},
    }
    runtime = session(directory, source, 'hall', 'doors.json')
    revision, state = runtime.load()
    try:
        result = RoomAdjudicator(source=runtime.source()).resolve(
            'I go through the back door.', revision, state)
        chosen = next(event['exit'] for event in result.events if event.get('type') == 'move')
    except PendingRuling as exc:
        chosen = f'ASKS: {exc}'
    runtime.close()
    record('fixed', "'the back door' picks the back door, not an ambiguity",
           chosen == 'e1', f'chose {chosen}')


def open_malformed_area():
    source = skeleton()
    source['areas'] = {'hall': 'Hall'}
    outcome = mount_outcome(source)
    record('P1', 'a non-object area escapes fail-fast as a raw error',
           outcome == 'AttributeError', f'mount outcome: {outcome}')


def open_untyped_id():
    outcome = mount_outcome(skeleton(id=[]))
    record('P1', 'a list id mounts instead of being refused',
           outcome == 'mounted', f'mount outcome: {outcome}')


def open_secrecy_blocks():
    cases = {
        'leak_keywords as a list': skeleton(leak_keywords=[{'groups': [['x']]}]),
        'leak_keywords entry with no groups': skeleton(leak_keywords={'s': {'revealed_by': 'f'}}),
        'revealed_by names a missing fact': skeleton(
            leak_keywords={'s': {'revealed_by': 'no_such_fact', 'groups': [['x']]}}),
        'leak_phrases as a list': skeleton(leak_phrases=['doppelganger']),
    }
    for label, source in cases.items():
        mounted = mount_outcome(source)
        try:
            kit_guards.leak_sets(source)
            kit_guards.leak_phrases(source)
            later = 'guard ok'
        except Exception as exc:
            later = type(exc).__name__
        record('P1', f'{label} mounts, then the guard raises',
               mounted == 'mounted' and later in ('AttributeError', 'KeyError'),
               f'mount {mounted}; guard {later}')


def open_cross_room_secret(directory):
    directory.mkdir(parents=True, exist_ok=True)
    roomb = write_room(directory, 'roomb.json', base_room('roomb', 'hall'))
    rooma = base_room('rooma', 'parlour', link={'room': str(roomb), 'area': 'hall'}, leak=[SECRET])
    runtime = session(directory, rooma, 'parlour', 'rooma.json')
    line = f'Kit: The one on the left is a {SECRET}.'
    record_a = {
        'player_input': 'I study the players.',
        'public_event': 'You study the players.',
        'spoken': 'Kit: Something about them is off.',
        'trace': {
            'appraisal': {'what': f'The PC is circling the fact that these four are a {SECRET} crew.'},
            'observed_event': f'The PC studied the {SECRET} crew without naming them.',
            'move': 'hold_the_secret',
        },
    }
    runtime.commit_kit_turn('a1', runtime.load()[0], [
        {'type': 'beat', 'tags': ['social'], 'evidence': 'Player studied the players.'}], record_a)

    def blocked(action):
        try:
            check_public_content(line, runtime.player_view(), action, (),
                                 kit_guards.leak_phrases(runtime.source()))
            return False
        except InvalidChange:
            return True

    blocked_in_a = blocked('I study the players.')
    revision = runtime.load()[0]
    runtime.commit('move', revision, [
        {'type': 'move', 'exit': 'rooma_out', 'evidence': 'The player left by the back stair.'}])
    state = runtime.load()[1]
    carried = SECRET in json.dumps(kit_memory(runtime, state, 'I look around.', True))
    blocked_in_b = blocked('I look around.')
    room = runtime.source()['id']
    runtime.close()
    record('P1', "room A's secret is sayable in room B while Kit still carries it",
           room == 'roomb' and blocked_in_a and carried and not blocked_in_b,
           f'room {room}; blocked in A {blocked_in_a}; carried {carried}; blocked in B {blocked_in_b}')


def open_approach_brief(directory):
    directory.mkdir(parents=True, exist_ok=True)
    runtime = session(directory, json.loads(WATCH.read_text(encoding='utf-8')), 'landing', 'watch.json')
    made = kit_brief.brief(runtime.source(), runtime.load()[1])
    runtime.close()
    record('P1', 'the approach brief carries no hooks, purposes, or present actors',
           kit_rooms.stage(json.loads(WATCH.read_text(encoding='utf-8')), {'area': 'landing', 'visited': ['landing']})
           == 'approach' and not made.get('hooks') and not made.get('purposes') and not made.get('present'),
           f"stage {made.get('stage')}; about {made.get('about')!r}; hooks {made.get('hooks')!r}")


def room_words_for(runtime):
    return room_words(runtime.source(), runtime.load()[1])


def open_exit_verbs(directory):
    """The verbs are the gap: each line names an exit the file actually has."""
    directory.mkdir(parents=True, exist_ok=True)
    source = skeleton()
    source['areas'].update({
        'out0': {'name': 'Below', 'called': 'the foot of the stair', 'outside': True},
        'out1': {'name': 'Tunnel', 'called': 'the tunnel', 'outside': True},
        'out2': {'name': 'Back', 'called': 'the back', 'outside': True},
    })
    source['exits'] = {
        'e0': {'name': 'the stair down', 'areas': ['hall', 'out0'], 'secret': False,
               'labels': {'hall': 'A stair.', 'out0': 'Back.'}},
        'e1': {'name': 'the low tunnel', 'areas': ['hall', 'out1'], 'secret': False,
               'labels': {'hall': 'A tunnel.', 'out1': 'Back.'}},
        'e2': {'name': 'the back door', 'areas': ['hall', 'out2'], 'secret': False,
               'labels': {'hall': 'A door.', 'out2': 'Back.'}},
    }
    runtime = session(directory, source, 'hall', 'verbs.json')
    words = room_words_for(runtime)
    runtime.close()
    samples = ["I take the stair down.", "I climb the stair.", "I duck through the tunnel.",
               "I use the back door."]
    missed = [text for text in samples if room_intent(text, room=words) != 'exit']
    record('P2', 'ordinary exit verbs still stop as unsupported physical acts',
           missed == samples, f'not routed as exit: {missed}')


def open_going_back(directory):
    """'back' is an exit stopword, so room_words() never offers it and the phrasing
    GOING_BACK exists for does not route as an exit."""
    directory.mkdir(parents=True, exist_ok=True)
    source = skeleton()
    source['areas']['out0'] = {'name': 'Front', 'called': 'the front', 'outside': True}
    source['areas']['out1'] = {'name': 'Back', 'called': 'the back', 'outside': True}
    source['exits'] = {
        'e0': {'name': 'the front door', 'areas': ['hall', 'out0'], 'secret': False,
               'labels': {'hall': 'Front.', 'out0': 'Back.'}},
        'e1': {'name': 'the back door', 'areas': ['hall', 'out1'], 'secret': False,
               'labels': {'hall': 'Back.', 'out1': 'Front.'}},
    }
    runtime = session(directory, source, 'hall', 'back.json')
    words = room_words_for(runtime)
    text = 'I head back the way I came.'
    runtime.close()
    record('P2', 'GOING_BACK never reaches the exit chooser',
           room_intent(text, room=words) != 'exit',
           f'exit words {words.exits}; {text!r} -> {room_intent(text, room=words)}')


def open_opening_consumes_first_look(directory):
    directory.mkdir(parents=True, exist_ok=True)
    source = json.loads(WATCH.read_text(encoding='utf-8'))
    runtime = session(directory, source, 'watchroom', 'watch.json')
    before = kit_rooms.stage(runtime.source(), runtime.load()[1])
    revision, body, _ = prepare_opening(runtime, one_pass=True)
    runtime.commit('opening', revision, body['events'])
    after = kit_rooms.stage(runtime.source(), runtime.load()[1])
    runtime.close()
    record('P2', 'committing the opening moves the stage from first_look to explore',
           before == 'first_look' and after == 'explore',
           f'before {before}; after the opening commits {after}')


def open_resolution_unreachable(directory):
    directory.mkdir(parents=True, exist_ok=True)
    source = json.loads(WATCH.read_text(encoding='utf-8'))
    runtime = session(directory, source, 'stair_down', 'watch.json')
    where = kit_rooms.stage(runtime.source(), runtime.load()[1])
    runtime.close()
    record('P2', 'starting on the far side reports approach, not resolution',
           where == 'approach', f'stage at stair_down: {where}')


def open_claims_undocumented(directory):
    """A puzzle room written from ROOM_LOADER.md section 2, which never lists claim fields."""
    source = skeleton(id='probe-puzzle')
    source['areas']['hall'] = {'name': 'Vault', 'called': 'the vault'}
    source['facts']['order'] = {'area': 'hall', 'visible': False,
                                'text': 'The notches are worn unevenly: three, then one, then five.'}
    source['claims'] = {'notch_order': {
        'about': 'the worn order of the dial notches', 'skill': 'investigation', 'dc': 13,
        'subject_words': ['dial', 'notches'], 'reveals': 'order',
        'knowers': {'bands': {'secret': []}},
    }}
    outcome = mount_outcome(source)
    record('P2', 'a claims block authored from the design doc is refused',
           outcome == 'refused', f'mount outcome: {outcome}')


def open_agenda_runs(directory):
    """Generality that does hold: an agenda room mounts and the agent reaches Kit."""
    directory.mkdir(parents=True, exist_ok=True)
    source = skeleton(id='probe-agenda')
    source['areas']['street'] = {'name': 'Street', 'called': 'the street', 'outside': True}
    source['exits'] = {'door': {'name': 'the street door', 'areas': ['hall', 'street'], 'secret': False,
                                'labels': {'hall': 'The street door.', 'street': 'The office.'}}}
    source['actors']['clerk'] = {'name': 'Clerk', 'location': 'hall', 'status': 'alive', 'visible': True,
                                 'motive': 'Close the book before anyone reads it.'}
    source['agenda'] = {'every': 1, 'agents': {'clerk': {
        'kind': 'npc', 'actor': 'clerk', 'disposition': 'neutral',
        'wants': 'To get the ledger shut and the stranger out.',
        'roots': ['f', 'clerk'],
        'moves': {'shut_it': {'does': 'The clerk closes the ledger.', 'roots': ['f'], 'trigger': 'any'}},
    }}}
    path = write_room(directory, 'agenda.json', source)
    try:
        runtime = Runtime(str(directory / 'agenda.sqlite'))
        runtime.initialize(kit_rooms.load_room(path), 'hall')
        agents = kit_agenda.agenda_here(runtime.source(), runtime.load()[1])['agents']
        runtime.close()
        present = 'clerk' in agents and bool(agents['clerk'].get('wants'))
    except (kit_rooms.RoomMountError, InvalidChange) as exc:
        present = False
        agents = str(exc)
    record('note', 'an agenda room mounts and its agent reaches agenda_here',
           present, f'agents: {list(agents) if isinstance(agents, dict) else agents}')


def main():
    print(f'Room loader review probe, checkout {ROOT}')
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        print('\nFixes from 999d4cd (these should still hold):')
        fixed_long_lived_host(directory / 'a')
        fixed_named_exit(directory / 'b')
        print('\nOpen findings (these should still reproduce):')
        open_malformed_area()
        open_untyped_id()
        open_secrecy_blocks()
        open_cross_room_secret(directory / 'c')
        open_approach_brief(directory / 'd')
        open_exit_verbs(directory / 'j')
        open_going_back(directory / 'i')
        open_opening_consumes_first_look(directory / 'e')
        open_resolution_unreachable(directory / 'f')
        open_claims_undocumented(directory / 'g')
        open_agenda_runs(directory / 'h')
    return finish()


def finish():
    held = [row for row in ROWS if row[2]]
    moved = [row for row in ROWS if not row[2]]
    print(f'\n{len(held)} hold, {len(moved)} moved.')
    if moved:
        print('Moved (re-read the review against this head):')
        for tag, name, _, detail in moved:
            print(f'  [{tag}] {name}: {detail}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
