"""Room loader (docs/architecture/ROOM_LOADER.md): any room file mounts and runs; stages are
read from state, not a rail; rooms chain in one session; a room that cannot mount fails fast.

Headline: one character through several rooms in one session (scripts/room_chain_walkthrough.py,
transcript in tests/playtests/). Then the pieces: the 17a stub and a non-6c fixture mount and
run, barge-in and bypass on both, broken rooms fail fast with Kit's plain line, and the
runtime code names no 6c id. All dice and decks are pinned."""
import copy
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime import kit_agent, kit_brief, kit_rooms  # noqa: E402
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import Runtime  # noqa: E402
import room_chain_walkthrough as chain  # noqa: E402

STUB = 'rooms/level_01_area_17a.json'
WATCH = 'tests/fixtures/rooms/watchroom.json'
SIXC = 'tests/fixtures/level_01_area_06c.json'
NIK = ROOT / 'tests/fixtures/characters/nik.json'
FIRST_FRAMING_MS = 500  # generous: measured ~5-40 ms on the box; a regression guard, not a benchmark


class ChainOfRooms(unittest.TestCase):
    """Brendon's acceptance test: seamless exploration across rooms in one session."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.records, cls.runtime = chain.run(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.runtime.close()
        cls.temp.cleanup()

    def mounts(self):
        return [r for r in self.records if r.get('mounted')]

    def test_each_room_mounts_on_arrival_with_no_host_step(self):
        self.assertEqual([r['mounted'] for r in self.mounts()],
                         ['synthetic-watchroom-v1', 'dotmm-level-01-area-17a-stub-v0', 'synthetic-watchroom-v1'])
        self.assertEqual(len({r['room'] for r in self.records}), 3)

    def test_rooms_left_resolve_and_are_restored_on_return(self):
        last = self.records[-1]
        self.assertEqual(last['rooms'], {'dotmm-level-01-area-06c-testbed-v1': 'left',
                                         'dotmm-level-01-area-17a-stub-v0': 'bypassed'})
        state = self.runtime.load()[1]
        self.assertIn('chest_contents', state['known_facts'])  # the watchroom as it was left
        self.assertEqual(last['stage'], 'resolution')
        archived = state['rooms']['dotmm-level-01-area-06c-testbed-v1']['state']
        self.assertIn('tub_stash', archived['known_facts'])
        self.assertEqual(archived['procedures']['twenty_one']['public']['player']['net'], -10)

    def test_nothing_from_the_room_left_crosses_into_the_next(self):
        state = self.runtime.load()[1]
        for key in ('procedures', 'tolls', 'combat', 'scene', 'claims'):
            self.assertNotIn(key, state)
        self.assertEqual(set(state['actors']), {'warden'})
        source = self.runtime.source()
        view = json.dumps(self.runtime._player_view(source, state)).casefold()
        brief = json.dumps(kit_brief.brief(source, state)).casefold()
        bridge = KitChatBridge(self.runtime, RoomAdjudicator(source=source))
        packet = bridge.prepare(opening=True, one_pass=True)
        bridge.abandon(packet['turn_id'])
        whole = json.dumps(packet, ensure_ascii=False).casefold()
        for word in ('dealer', 'tub', 'uktarl', 'basilisk', 'twenty-one', 'toll', 'vampire', 'card room'):
            self.assertNotIn(word, view)
            self.assertNotIn(word, brief)
            self.assertNotIn(word, whole)  # the whole first packet in the room returned to

    def test_hp_gold_and_what_was_taken_carry_over(self):
        sheet = self.runtime.load()[1]['player_sheet']
        self.assertEqual(sheet['hp'], 32 - 14)       # the fourth player's two hits in 6c
        self.assertEqual(sheet['gold_gp'], 805 - 10)  # the hand lost at the 6c table
        carried = self.runtime.load()[1]['carried']
        self.assertEqual([c['from'] for c in carried], ['dotmm-level-01-area-06c-testbed-v1'])

    def test_stage_pivots_mid_chain(self):
        by_line = {r['line'].splitlines()[0]: r for r in self.records}
        barged = by_line['I shove the iron door open and charge in.']
        self.assertEqual(barged['stage'], 'first_look')
        acted = by_line['I open the chest and look inside.']
        self.assertEqual(acted['stage'], 'explore')        # no look first: straight to exploring
        self.assertIn('challenge', acted['brief']['raise_now'])  # and the hook is still delivered
        self.assertEqual(by_line['I walk on down the side passage.']['rooms']['dotmm-level-01-area-17a-stub-v0'],
                         'bypassed')

    def test_a_room_that_cannot_mount_fails_fast_mid_chain_without_breaking_the_session(self):
        refused = next(r for r in self.records if r['kind'] == 'pending')
        self.assertTrue(refused['public'].startswith(kit_rooms.TABLE_LINE))
        self.assertEqual(refused['host_error']['error'], 'room_unmountable')
        self.assertIn('missing starting_area', refused['host_error']['problems'])
        after = self.records[self.records.index(refused) + 1]
        self.assertEqual(after['kind'], 'exit')  # the next line plays on
        self.assertEqual(refused['room'], 'dotmm-level-01-area-17a-stub-v0')

    def test_every_doorway_brief_carries_the_room_s_tease(self):
        doorways = [r for r in self.records if r.get('stage') == 'approach' and r.get('brief')]
        self.assertGreaterEqual(len(doorways), 2)  # the watchroom landing and the 17a doors
        for record in doorways:
            self.assertTrue(record['brief']['tease']['text'], record['line'])

    def test_first_framing_in_each_new_room_is_fast(self):
        for record in self.mounts():
            self.assertLess(record['ms_transition'], FIRST_FRAMING_MS, record['mounted'])
        self.assertLess(self.records[0]['ms_to_first_packet'], FIRST_FRAMING_MS)


class Mounting(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def start(self, room, area=None):
        db = self.folder / f'{len(list(self.folder.iterdir()))}.sqlite'
        started = start_session(db, NIK, room=room, area=area)
        runtime = Runtime(db)
        self.addCleanup(runtime.close)
        KitChatBridge(runtime, RoomAdjudicator()).abandon(started['prepared']['turn_id'])
        return runtime, started

    def play(self, runtime, line):
        revision, state = runtime.load()
        result = RoomAdjudicator(roll=lambda: 10, source=runtime.source()).resolve(line, revision, state)
        runtime.commit(f'p{revision}', revision, list(result.events))
        return result, runtime.load()[1]

    def broken(self, body):
        path = self.folder / f'broken-{len(list(self.folder.glob("broken-*")))}.json'
        path.write_text(body if isinstance(body, str) else json.dumps(body), encoding='utf-8')
        return path

    def test_the_17a_stub_mounts_and_runs_a_basic_turn(self):
        runtime, started = self.start(STUB)
        self.assertTrue(kit_rooms.read_room(STUB)['stub'])
        state = runtime.load()[1]
        self.assertEqual(kit_rooms.stage(runtime.source(), state), 'approach')
        self.assertEqual(started['prepared']['stage'], 'one_pass')
        result, state = self.play(runtime, 'I push the foyer doors open and go in.')
        self.assertEqual(result.kind, 'exit')
        self.assertEqual(state['area'], 'area_17a')
        self.assertIn('dead_basilisk', state['known_facts'])
        self.assertEqual(kit_rooms.stage(runtime.source(), state), 'first_look')
        result, state = self.play(runtime, 'I look around.')
        self.assertEqual(result.kind, 'observe')
        self.assertEqual(kit_rooms.stage(runtime.source(), state), 'explore')

    def test_the_non_6c_fixture_mounts_with_its_own_feature_and_hook(self):
        runtime, _ = self.start(WATCH)
        result, state = self.play(runtime, 'I walk through the iron door.')
        self.assertEqual(state['area'], 'watchroom')
        result, state = self.play(runtime, 'I try to tip the chest over.')
        self.assertEqual((result.kind, result.public_event), ('move_feature', 'The chest is bolted to the floor and will not shift.'))
        words = kit_agent.room_words(runtime.source(), state)
        self.assertEqual(words.features, (('chest', 'chest'),))
        self.assertNotEqual(kit_agent.room_intent('I look in the tub.', room=words), 'inspect_feature')  # 6c's tub

    def test_the_feasibility_fixture_mounts_too(self):
        runtime, _ = self.start('tests/fixtures/feasibility_room.json')
        result, state = self.play(runtime, 'I walk out through the doorway in the east wall.')
        self.assertEqual(state['area'], 'hall')

    def test_barge_in_straight_to_full_exploration_keeps_the_hook(self):
        for room, area, act, hook in ((WATCH, 'watchroom', 'I open the chest and look inside.', 'challenge'),):
            runtime, _ = self.start(room, area=area)  # skip the doorway entirely
            self.assertEqual(kit_rooms.stage(runtime.source(), runtime.load()[1]), 'first_look')
            revision, state = runtime.load()
            result = RoomAdjudicator(roll=lambda: 10, source=runtime.source()).resolve(act, revision, state)
            events = list(result.events)
            for _ in range(2):  # two turns of exploring without anyone raising the hook
                after = runtime.preview_state(revision, events)
                events.append(kit_brief.beat_event(runtime.source(), after, None, 't'))
            runtime.commit('barge', revision, events)
            state = runtime.load()[1]
            self.assertEqual(kit_rooms.stage(runtime.source(), state), 'explore')
            self.assertIn(hook, kit_brief.brief(runtime.source(), state)['raise_now'])
        # The 17a stub: barge straight into the foyer from the start.
        runtime, _ = self.start(STUB, area='area_17a')
        result, state = self.play(runtime, 'I look around.')
        self.assertEqual(kit_rooms.stage(runtime.source(), state), 'explore')

    def test_bypass_is_a_resolution(self):
        runtime, _ = self.start(WATCH)
        result, state = self.play(runtime, 'I head down the stair.')
        self.assertEqual(state['area'], 'stair_down')
        source = runtime.source()
        self.assertEqual((kit_rooms.stage(source, state), kit_rooms.resolution(source, state)), ('resolution', 'bypassed'))
        self.assertEqual(kit_brief.brief(source, state)['resolved'], 'bypassed')
        # The 17a stub with a way past (its real neighbours are GPT's content: added here only).
        stub = kit_rooms.read_room(STUB)
        stub['areas']['onward'] = {'name': 'Onward', 'outside': True}
        stub['exits']['onward_way'] = {'name': 'the onward passage', 'areas': ['area_17a_doors', 'onward'], 'secret': False,
                                       'labels': {'area_17a_doors': 'A passage runs on.', 'onward': 'Back to the doors.'}}
        path = self.folder / '17a-onward.json'
        path.write_text(json.dumps(stub), encoding='utf-8')
        runtime, _ = self.start(path)
        result, state = self.play(runtime, 'I walk on down the onward passage.')
        self.assertEqual((kit_rooms.stage(runtime.source(), state), kit_rooms.resolution(runtime.source(), state)),
                         ('resolution', 'bypassed'))

    def test_6c_still_starts_by_default_and_reads_its_behaviour_from_its_file(self):
        runtime, started = self.start(None)
        self.assertEqual(runtime.source()['id'], 'dotmm-level-01-area-06c-testbed-v1')
        self.assertEqual(kit_rooms.stage(runtime.source(), runtime.load()[1]), 'first_look')
        result, _ = self.play(runtime, 'I look in the tub.')
        self.assertEqual(result.public_event, kit_rooms.read_room(SIXC)['facts']['tub']['handling']['look'])

    def test_a_room_without_a_card_game_loads_no_card_machinery(self):
        runtime, _ = self.start(WATCH, area='watchroom')
        self.assertIsNone(kit_agent.card_procedure(runtime.source(), runtime.load()[1]))
        revision, state = runtime.load()
        try:
            result = RoomAdjudicator(roll=lambda: 10, source=runtime.source()).resolve("I'll play a hand.", revision, state)
            self.assertFalse(result.kind.startswith('card_'))
        except PendingRuling:
            pass
        self.assertNotIn('procedures', runtime.load()[1])

    def test_broken_rooms_fail_fast_with_the_plain_line_and_a_named_problem(self):
        cases = [
            (self.folder / 'none.json', 'no room file'),
            (self.broken('{"id": "x",'), 'not valid JSON'),
            (self.broken({'id': 'x', 'areas': {'a': {'name': 'A'}}}), 'missing starting_area'),
            (self.broken({'id': 'x', 'starting_area': 'b', 'areas': {'a': {'name': 'A'}}, 'exits': {}, 'facts': {}, 'actors': {}}),
             "starting_area 'b' is not one of the areas"),
            (self.broken({'id': 'x', 'starting_area': 'a', 'areas': {'a': {'name': 'A'}}, 'exits': {}, 'facts': {}, 'actors': {},
                          'puzzles': {}}), "unsupported block 'puzzles'"),
            (self.broken({'id': 'x', 'starting_area': 'a', 'areas': {'a': {'name': 'A'}}, 'exits': {}, 'facts': {}, 'actors': {},
                          'procedures': {'dice': {'kind': 'dice_game'}}}), "unsupported kind 'dice_game'"),
            (self.broken({'id': 'x', 'starting_area': 'a', 'areas': {'a': {'name': 'A'}}, 'exits': {}, 'facts': {}, 'actors': {},
                          'procedures': {'p': {'kind': 'card_game', 'game': 'poker'}}}), "unsupported card game 'poker'"),
        ]
        for block in ('exits', 'facts', 'actors'):  # a list where an object belongs
            for value in ([], [{'areas': ['a', 'a']}]):
                body = {'id': 'x', 'starting_area': 'a', 'areas': {'a': {'name': 'A'}}, 'exits': {}, 'facts': {}, 'actors': {}}
                cases.append((self.broken(dict(body, **{block: value})), f'{block} must be an object'))
        for path, problem in cases:
            with self.subTest(problem=problem, path=path.name):
                started = time.perf_counter()
                with self.assertRaises(kit_rooms.RoomMountError) as caught:
                    start_session(self.folder / 'never.sqlite', NIK, room=path)
                self.assertLess((time.perf_counter() - started) * 1000, FIRST_FRAMING_MS)
                self.assertTrue(any(problem in p for p in caught.exception.problems), caught.exception.problems)
                self.assertEqual(caught.exception.table_line, kit_rooms.TABLE_LINE)
                self.assertFalse((self.folder / 'never.sqlite').exists())  # nothing was created

    def test_a_link_to_a_missing_area_fails_before_the_move_is_accepted(self):
        watch = kit_rooms.read_room(WATCH)
        watch['areas']['stair_down']['room_link'] = {'room': STUB, 'area': 'area_17a_doorz'}
        path = self.folder / 'watch-badlink.json'
        path.write_text(json.dumps(watch), encoding='utf-8')
        runtime, _ = self.start(path)
        revision, state = runtime.load()
        with self.assertRaises(PendingRuling) as caught:
            RoomAdjudicator(roll=lambda: 10, source=runtime.source()).resolve('I head down the stair.', revision, state)
        self.assertTrue(str(caught.exception).startswith(kit_rooms.TABLE_LINE))
        self.assertIn("room_link area 'area_17a_doorz' is not one of its areas", caught.exception.host_error['problems'])
        self.assertEqual(runtime.load()[0], revision)  # nothing committed

    def test_the_cli_prints_the_host_error_and_table_line(self):
        path = self.broken({'id': 'x', 'areas': {}})
        done = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'start', '--db',
                               str(self.folder / 'cli.sqlite'), '--room', str(path)],
                              cwd=ROOT, capture_output=True, text=True, env={'PATH': '/usr/bin:/bin'})
        self.assertEqual(done.returncode, 2)
        out = json.loads(done.stderr)
        self.assertEqual((out['error'], out['table_line']), ('room_unmountable', kit_rooms.TABLE_LINE))
        self.assertIn('missing starting_area', out['problems'])

    def test_kit_line_is_plain_and_brief(self):
        self.assertLessEqual(len(kit_rooms.TABLE_LINE.split()), 25)
        self.assertNotRegex(kit_rooms.TABLE_LINE.casefold(), r'json|file|loader|mount|error|runtime')


class LongLivedHost(unittest.TestCase):
    """One bridge and one adjudicator for the whole session, A -> B -> A, the way a chat
    host or KitAgent runs (Codex P1 on #87): each mount must refresh what the adjudicator and
    router read from the room (source, feature nouns, exits)."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        chain.build_chain(folder)
        started = start_session(folder / 'host.sqlite', NIK, room=folder / 'watchroom.json')
        self.runtime = Runtime(folder / 'host.sqlite')
        self.addCleanup(self.runtime.close)
        self.adjudicator = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10)
        self.bridge = KitChatBridge(self.runtime, self.adjudicator)
        self.bridge.abandon(started['prepared']['turn_id'])

    def step(self, line):
        """Prepare through the long-lived bridge, then commit the adjudicated events."""
        revision, _ = self.runtime.load()
        packet = self.bridge.prepare(line, one_pass=True)
        body = self.runtime.pending_kit_turn(packet['turn_id'])['body']
        self.assertEqual(self.adjudicator.source['id'], self.runtime.source()['id'])
        self.bridge.abandon(packet['turn_id'])
        self.runtime.commit(packet['turn_id'], revision, body['events'])
        return body, self.runtime.source()['id'], self.runtime.load()[1]

    def test_a_to_b_to_a_in_one_host(self):
        watch, stub = 'synthetic-watchroom-v1', 'dotmm-level-01-area-17a-stub-v0'
        body, room, state = self.step('I go through the iron door.')
        self.assertEqual((room, state['area']), (watch, 'watchroom'))
        body, room, state = self.step('I open the chest and look inside.')
        self.assertEqual(body['kind'], 'inspect_feature')
        body, room, state = self.step('I head down the back stair.')
        self.assertEqual((room, state['area'], body['kind']), (watch, 'watchroom', 'exit_contested'))  # the warden
        body, room, state = self.step('Acrobatics 25')
        self.assertEqual((room, state['area']), (stub, 'area_17a_doors'))  # B mounted by the commit
        self.assertNotIn('chest', [noun for noun, _ in kit_agent.room_words(self.adjudicator.source, state).features])
        body, room, state = self.step('I walk on down the side passage.')  # refused on 9f0c07c: still A's words
        self.assertEqual((room, state['area'], body['kind']), (watch, 'stair_down', 'exit'))
        body, room, state = self.step('I go up the back stair.')
        self.assertEqual((room, state['area']), (watch, 'watchroom'))
        body, room, state = self.step('I open the chest and look inside.')  # A's feature again
        self.assertEqual(body['kind'], 'inspect_feature')


class WhichExit(unittest.TestCase):
    """Two doors in one non-6c room (Codex P1 on #87): the most specific name wins; a shared
    word narrows to the exit in view or, going back, the one the PC came in by, only when
    that leaves one; otherwise Kit asks one short question and nothing is committed."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        watch = kit_rooms.read_room(WATCH)
        watch['exits']['oak_door'] = {'name': 'the oak door', 'areas': ['watchroom', 'stair_down'], 'secret': False,
                                      'labels': {'watchroom': 'An oak door in the far wall.',
                                                 'stair_down': 'The oak door up to the watchroom.'}}
        path = Path(temp.name) / 'two-doors.json'
        path.write_text(json.dumps(watch), encoding='utf-8')
        start_session(Path(temp.name) / 'doors.sqlite', NIK, room=path)
        self.runtime = Runtime(Path(temp.name) / 'doors.sqlite')
        self.addCleanup(self.runtime.close)
        revision, state = self.runtime.load()
        self.runtime.commit('in', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'In by the iron door.'}])
        self.adjudicator = RoomAdjudicator(roll=lambda: 10, source=self.runtime.source())

    def exit(self, line, last_said=''):
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(line, revision, state, last_said=last_said)
        return [e['exit'] for e in result.events if e.get('type') == 'move']

    def asks(self, line, last_said=''):
        revision, state = self.runtime.load()
        with self.assertRaises(PendingRuling) as caught:
            self.adjudicator.resolve(line, revision, state, last_said=last_said)
        self.assertEqual(self.runtime.load()[0], revision)
        return str(caught.exception)

    def test_the_named_door_wins_over_the_shared_word(self):
        self.assertEqual(self.exit('I walk through the oak door.'), ['oak_door'])
        self.assertEqual(self.exit('I leave by the iron door.'), ['iron_door'])
        self.assertEqual(self.exit('I go out the oak one, the door.'), ['oak_door'])

    def test_a_bare_door_is_asked_about_in_one_short_line(self):
        self.assertEqual(self.asks('I walk through the door.'), 'The iron door or the oak door? No turn was committed.')

    def test_the_door_in_view_or_the_way_back_settles_it_only_when_unambiguous(self):
        self.assertEqual(self.exit('I walk through the door.', last_said='The oak door creaks in a draught.'),
                         ['oak_door'])
        self.assertEqual(self.exit('I go back out the door.'), ['iron_door'])  # came in by it
        self.asks('I walk through the door.', last_said='The iron door and the oak door both stand shut.')
        self.asks('I go back out the door.', last_said='The oak door creaks in a draught.')  # two pulls: ask


class NoSixCInRuntimeCode(unittest.TestCase):
    """6c's ids and nouns live in its file. Runtime code may mention 6c in comments and
    docstrings (history), not in string literals that drive behaviour."""

    IDS = ("'area_06c'", "'south_door'", "'tub_stash'", "'south_passage'", "'uktarl'", "'tub'",
           "kit-06c.sqlite", 'card room', 'bedroll', 'recessed tub')

    def test_no_6c_ids_in_runtime_string_literals(self):
        import ast
        for path in (ROOT / 'runtime').glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                          if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                          and node.body and isinstance(node.body[0], ast.Expr)
                          and isinstance(getattr(node.body[0], 'value', None), ast.Constant)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                    for word in self.IDS:
                        bare = word.strip("'")
                        hit = node.value == bare if word.startswith("'") else bare in node.value.casefold()
                        self.assertFalse(hit, f'{path.name}: {node.value[:60]!r}')


if __name__ == '__main__':
    unittest.main()
