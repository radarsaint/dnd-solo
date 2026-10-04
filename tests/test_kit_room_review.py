"""Claude's adversarial review of the room loader (#87 at 999d4cd), written as tests from
his descriptions (his repro scripts were not reachable). P1: malformed rooms fail fast with
Kit's plain line; the secrecy blocks are validated at mount; room A's secrets do not reach
room B through Kit's memory, plan, or decision input; the approach (doorway) brief carries
the room's tease. P2: exit verbs, retracing, the opening and first_look, pivoting straight
to resolution, and capped room context. All dice pinned."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime import kit_agent, kit_brief, kit_rooms  # noqa: E402
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import InvalidChange, Runtime, encode  # noqa: E402
import room_chain_walkthrough as chain  # noqa: E402

STUB = 'rooms/level_01_area_17a.json'
WATCH = 'tests/fixtures/rooms/watchroom.json'
SIXC = 'tests/fixtures/level_01_area_06c.json'
NIK = ROOT / 'tests/fixtures/characters/nik.json'
MISSING = object()
WRONG = [MISSING, None, 0, True, 'x', [], {}, '']


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.count = 0

    def write(self, body):
        self.count += 1
        path = self.folder / f'room-{self.count}.json'
        path.write_text(body if isinstance(body, str) else json.dumps(body), encoding='utf-8')
        return path

    def start(self, room, area=None):
        self.count += 1
        db = self.folder / f's-{self.count}.sqlite'
        started = start_session(db, NIK, room=room, area=area)
        runtime = Runtime(db)
        self.addCleanup(runtime.close)
        KitChatBridge(runtime, RoomAdjudicator()).abandon(started['prepared']['turn_id'])
        return runtime

    def resolve(self, runtime, line, **kw):
        revision, state = runtime.load()
        return RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10, source=runtime.source()).resolve(
            line, revision, state, **kw)

    def moved(self, runtime, line, **kw):
        return [e['exit'] for e in self.resolve(runtime, line, **kw).events if e.get('type') == 'move']


# --------------------------------------------------------------------------- P1 1
class MalformedRoomsFailFast(Base):
    """Every top-level field missing, of the wrong type, or empty: the mount either succeeds
    and plays a turn, or raises RoomMountError with Kit's plain line. Never a traceback."""

    def attempt(self, body, label):
        path = self.write(body)
        try:
            runtime = self.start(path)
        except kit_rooms.RoomMountError as exc:
            self.assertEqual(exc.table_line, kit_rooms.TABLE_LINE, label)
            self.assertTrue(exc.problems, label)
            return 'refused'
        try:
            KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10)).prepare(
                'I look around.', one_pass=True)
        except (PendingRuling, InvalidChange):
            pass
        return 'mounted'

    def fuzz(self, ref):
        base = kit_rooms.read_room(ref)
        crashes = []
        keys = sorted(set(base) | set(kit_rooms.REQUIRED) | {'id'})
        for key in keys:
            for value in WRONG:
                body = copy.deepcopy(base)
                if value is MISSING:
                    body.pop(key, None)
                else:
                    body[key] = copy.deepcopy(value)
                label = f'{ref} {key}={"<missing>" if value is MISSING else repr(value)}'
                try:
                    self.attempt(body, label)
                except AssertionError:
                    raise
                except Exception as exc:  # noqa: BLE001 - the point of the test
                    crashes.append(f'{label}: {type(exc).__name__}: {exc}'[:160])
        for block in ('areas', 'exits', 'facts', 'actors'):
            first = next((k for k in base.get(block) or {} if not k.startswith('_')), None)
            for value in ('x', [], 0, None):
                body = copy.deepcopy(base)
                body[block] = dict(body.get(block) or {}, **{first or 'extra': value})
                label = f'{ref} {block}.{first}={value!r}'
                try:
                    self.attempt(body, label)
                except AssertionError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    crashes.append(f'{label}: {type(exc).__name__}: {exc}'[:160])
        self.assertEqual(crashes, [], "\n" + "\n".join(crashes))

    def test_fuzz_the_watchroom(self):
        self.fuzz(WATCH)

    def test_fuzz_the_17a_stub(self):
        self.fuzz(STUB)

    def test_fuzz_6c(self):
        self.fuzz(SIXC)

    def test_an_area_that_is_not_an_object_and_a_bad_id_are_named(self):
        body = kit_rooms.read_room(WATCH)
        body['areas']['landing'] = 'a landing'
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            kit_rooms.load_room(self.write(body))
        self.assertIn('area landing must be an object', caught.exception.problems)
        for bad in (5, ['x'], '', None):
            with self.subTest(id=bad), self.assertRaises(kit_rooms.RoomMountError) as caught:
                kit_rooms.load_room(self.write(dict(kit_rooms.read_room(WATCH), id=bad)))
            self.assertIn('id must be a non-empty string', caught.exception.problems)


# --------------------------------------------------------------------------- P1 2
class SecrecyBlocksValidated(Base):
    def refused(self, **blocks):
        body = dict(kit_rooms.read_room(SIXC), **blocks)
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            kit_rooms.load_room(self.write(body))
        return ' | '.join(caught.exception.problems)

    def test_malformed_leak_keywords_are_refused_at_mount(self):
        good = kit_rooms.read_room(SIXC)['leak_keywords']
        cases = {
            'not an object': ('x', 'leak_keywords must be an object'),
            'set not an object': ({**good, 'bad': ['card', 'marked']}, 'leak_keywords bad must be an object'),
            'no groups': ({**good, 'bad': {'revealed_by': 'marked_deck'}}, 'leak_keywords bad needs groups'),
            'flat groups': ({**good, 'bad': {'groups': ['card', 'marked']}}, 'leak_keywords bad needs groups'),
            'no group': ({**good, 'bad': {'groups': []}}, 'leak_keywords bad needs groups'),
            'empty word': ({**good, 'bad': {'groups': [['card'], ['']]}}, 'leak_keywords bad needs groups'),
            'dangling revealed_by': ({**good, 'bad': {'revealed_by': 'no_such_fact', 'groups': [['a'], ['b']]}},
                                     "leak_keywords bad revealed_by names no fact: 'no_such_fact'"),
            'revealed_by wrong type': ({**good, 'bad': {'revealed_by': 3, 'groups': [['a'], ['b']]}},
                                       'leak_keywords bad revealed_by must name a fact or a list of facts'),
        }
        for name, (value, problem) in cases.items():
            with self.subTest(name):
                self.assertIn(problem, self.refused(leak_keywords=value))

    def test_malformed_leak_phrases_are_refused_at_mount(self):
        cases = {
            'not an object': (['doppelganger'], 'leak_phrases must be an object'),
            'phrases not a list': ({'phrases': 'doppelganger'}, 'leak_phrases phrases must be a list of non-empty strings'),
            'phrase not a string': ({'phrases': ['ok', 3]}, 'leak_phrases phrases must be a list of non-empty strings'),
            'player_may_name not a list': ({'phrases': ['uktarl'], 'player_may_name': 'uktarl'},
                                           'leak_phrases player_may_name must be a list of non-empty strings'),
            'player_may_name not a phrase': ({'phrases': ['uktarl'], 'player_may_name': ['harria']},
                                             "leak_phrases player_may_name 'harria' is not one of the phrases"),
        }
        for name, (value, problem) in cases.items():
            with self.subTest(name):
                self.assertIn(problem, self.refused(leak_phrases=value))

    def test_the_shipped_rooms_still_mount(self):
        for ref in (SIXC, WATCH, STUB):
            kit_rooms.load_room(ref)


# --------------------------------------------------------------------------- P1 3
class SecretsStayInTheirRoom(Base):
    """A real 6c secret (the dealer is the doppelganger; a leak phrase) in Kit's memory, her
    appraisal, a player note, and the move turn's own decision, then the chain moves on."""
    SECRET = 'The dealer is the doppelganger, not Uktarl.'

    def record(self, line, public):
        return {'player_input': line, 'public_event': public, 'spoken': 'Kit: ' + public,
                'trace': {'appraisal': {'read': self.SECRET}, 'observed_event': public,
                          'move': 'Keep the doppelganger secret.', 'goal': self.SECRET,
                          'player_note': {'note': 'The player suspects the doppelganger.',
                                          'evidence_turns': ['this_turn'], 'replaces': 'none'}}}

    def test_no_secret_from_room_a_reaches_room_b(self):
        first = chain.build_chain(self.folder)
        runtime = self.start(first)
        revision, _ = runtime.load()
        runtime.commit_kit_turn('a1', revision, [{'type': 'beat', 'tags': ['watch'], 'evidence': 'Watching.'}], self.record('I watch the dealer.', 'You watch the dealer.'))
        revision, state = runtime.load()
        self.assertIn(self.SECRET, encode(state['kit']))  # room A's memory holds it
        move = self.resolve(runtime, 'I walk out the south door.')
        runtime.commit_kit_turn('a2', revision, list(move.events), self.record('I walk out the south door.',
                                                                                move.public_event))
        self.assertEqual(runtime.source()['id'], 'synthetic-watchroom-v1')
        _, state = runtime.load()
        self.assertEqual(state['kit']['episodes'], [])
        self.assertIsNone(state['kit']['current_appraisal'])
        packet = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10)).prepare('I look around.', one_pass=True)
        text = encode(packet).casefold()
        for secret in ['doppelganger', 'uktarl', 'harria'] + [f['text'].casefold()[:60] for f in
                                                              kit_rooms.read_room(SIXC)['facts'].values()
                                                              if isinstance(f, dict) and not f.get('visible')]:
            self.assertNotIn(secret, text)
        # Kept with room A: restored as it was if the PC goes back.
        archived = state['rooms']['dotmm-level-01-area-06c-testbed-v1']['state']
        self.assertEqual([e['turn_id'] for e in archived['kit']['episodes']], ['a1', 'a2'])


# --------------------------------------------------------------------------- P1 4
class DoorwayBriefCarriesTheTease(Base):
    def test_the_watchroom_landing_brief_carries_its_tease(self):
        runtime = self.start(WATCH)
        made = kit_brief.brief(runtime.source(), runtime.load()[1])
        self.assertEqual(made['stage'], 'approach')
        tease = kit_rooms.read_room(WATCH)['areas']['landing']['tease']
        self.assertEqual(made['about'], tease['text'])
        self.assertEqual(made['tease']['points_to'], 'challenge')
        self.assertIn('who sent you', made['tease']['hook'])
        self.assertEqual([p['actor'] for p in made['present']], ['warden'])
        self.assertTrue(made['present'][0]['heard'])

    def test_the_17a_stub_doorway_brief_carries_its_tease(self):
        runtime = self.start(STUB)
        made = kit_brief.brief(runtime.source(), runtime.load()[1])
        self.assertEqual(made['stage'], 'approach')
        self.assertEqual(made['about'], kit_rooms.read_room(STUB)['areas']['area_17a_doors']['tease']['text'])

    def test_an_approach_with_no_tease_does_not_mount(self):
        body = kit_rooms.read_room(WATCH)
        del body['areas']['landing']['tease']
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            kit_rooms.load_room(self.write(body))
        self.assertTrue(any(p.startswith('area landing is an approach and needs a tease')
                            for p in caught.exception.problems), caught.exception.problems)

    def test_a_tease_must_point_at_a_hook_and_name_real_actors(self):
        body = kit_rooms.read_room(WATCH)
        body['areas']['landing']['tease'] = {'text': 'Humming.', 'points_to': 'nope',
                                             'heard': [{'actor': 'ghost', 'sound': 'a sigh'}]}
        with self.assertRaises(kit_rooms.RoomMountError) as caught:
            kit_rooms.load_room(self.write(body))
        problems = ' | '.join(caught.exception.problems)
        self.assertIn("tease points_to 'nope' is not a story hook", problems)
        self.assertIn("tease heard 'ghost' is not an actor", problems)


# --------------------------------------------------------------------------- P2
def exits_room(folder):
    body = kit_rooms.read_room(WATCH)
    body['exits']['back_door'] = {'name': 'the back door', 'areas': ['watchroom', 'stair_down'], 'secret': False,
                                  'labels': {'watchroom': 'A back door.', 'stair_down': 'The back door.'}}
    body['exits']['tunnel'] = {'name': 'the tunnel', 'areas': ['watchroom', 'stair_down'], 'secret': False,
                               'labels': {'watchroom': 'A low tunnel.', 'stair_down': 'The tunnel.'}}
    body['actors']['warden'].pop('guards', None)  # phrasing only: nobody contests these exits
    path = Path(folder) / 'exits.json'
    path.write_text(json.dumps(body), encoding='utf-8')
    return path


class ExitPhrasings(Base):
    def setUp(self):
        super().setUp()
        self.runtime = self.start(exits_room(self.folder))
        revision, _ = self.runtime.load()
        self.runtime.commit('in', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'In.'}])

    def test_more_exit_verbs(self):
        cases = {'I take the stair down.': 'back_stair', 'I use the back door.': 'back_door',
                 'I climb the stair.': 'back_stair', 'I duck through the tunnel.': 'tunnel',
                 'I slip out the back door.': 'back_door', 'I crawl into the tunnel.': 'tunnel'}
        for line, key in cases.items():
            with self.subTest(line):
                self.assertEqual(self.moved(self.runtime, line), [key])

    def test_a_door_as_an_object_is_not_leaving(self):
        for line in ('I take the key from the door.', 'I use my tools on the lock of the back door.'):
            with self.subTest(line):
                try:
                    self.assertEqual(self.moved(self.runtime, line), [])
                except PendingRuling:
                    pass

    def test_going_back_the_way_i_came(self):
        for line in ('I head back the way I came.', 'I retrace my steps.'):
            with self.subTest(line):
                self.assertEqual(self.moved(self.runtime, line), ['iron_door'])


class StagesNotARail(Base):
    def test_the_opening_does_not_use_up_first_look(self):
        runtime = self.start(WATCH, area='watchroom')
        revision, body, _ = kit_agent.prepare_opening(runtime)
        runtime.commit('open', revision, list(body['events']))
        self.assertEqual(kit_rooms.stage(runtime.source(), runtime.load()[1]), 'first_look')

    def test_pivot_straight_to_resolution(self):
        runtime = self.start(WATCH, area='stair_down')
        source, state = runtime.source(), runtime.load()[1]
        self.assertEqual(kit_rooms.stage(source, state), 'resolution')
        self.assertEqual(kit_brief.brief(source, state)['resolved'], 'bypassed')


class RoomContextIsCapped(Base):
    def test_an_oversized_room_fails_loudly_instead_of_trimming_memory(self):
        body = kit_rooms.read_room(WATCH)
        for n in range(40):
            body['facts'][f'hidden_{n}'] = {'area': 'landing', 'visible': False, 'text': 'A hidden thing. ' * 20}
        with self.assertRaises(kit_rooms.RoomMountError) as caught:  # at start: the opening packet
            self.start(self.write(body))
        self.assertEqual(caught.exception.table_line, kit_rooms.TABLE_LINE)
        self.assertIn('dm_only', str(caught.exception))
        self.assertIn(f'(cap {kit_rooms.DM_ONLY_ROOM_MAX_BYTES})', str(caught.exception))
        # Mid-chain, the same: Kit's plain line and the named block, not a trimmed memory.
        folder = self.folder / 'chain'
        folder.mkdir()
        chain.build_chain(folder)
        heavy = json.loads((folder / 'watchroom.json').read_text(encoding='utf-8'))
        heavy['facts'].update({k: v for k, v in body['facts'].items() if k.startswith('hidden_')})
        (folder / 'watchroom.json').write_text(json.dumps(heavy), encoding='utf-8')
        runtime = self.start(folder / '6c.json')
        revision, _ = runtime.load()
        with self.assertRaises(PendingRuling) as caught:  # refused before the move: the session stays
            self.resolve(runtime, 'I walk out the south door.')
        self.assertTrue(str(caught.exception).startswith(kit_rooms.TABLE_LINE))
        self.assertIn('dm_only', ' '.join(caught.exception.host_error['problems']))
        self.assertEqual((runtime.load()[0], runtime.source()['id']), (revision, 'dotmm-level-01-area-06c-testbed-v1'))

    def test_trimmed_memory_is_reported_to_the_host(self):
        runtime = self.start(WATCH)
        original = kit_agent.fit_to_budget

        def trimming(planning_input, *args, **kwargs):
            planning_input['kit_state']['memory_trimmed'] = {'episodes_dropped': 1}
            return original(planning_input, *args, **kwargs)
        kit_agent.fit_to_budget = trimming
        self.addCleanup(setattr, kit_agent, 'fit_to_budget', original)
        packet = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10)).prepare('I look around.', one_pass=True)
        self.assertEqual(packet['context_warning'], kit_agent.MEMORY_TRIMMED_NOTE)

    def test_the_caps_admit_6c_at_its_largest(self):
        # 6c's peaks across the suite (measured at 999d4cd and here): 9,554 B and 3,057 B.
        self.assertGreaterEqual(kit_rooms.DM_ONLY_ROOM_MAX_BYTES, 9554)
        self.assertGreaterEqual(kit_rooms.CLAIMS_HERE_MAX_BYTES, 3057)
        self.assertLessEqual(kit_rooms.DM_ONLY_ROOM_MAX_BYTES + kit_rooms.CLAIMS_HERE_MAX_BYTES, 9554 + 3057 + 300)


# --------------------------------------------------------------------------- live watchroom
class LiveWatchroomPlaytest(Base):
    """Kit's live watchroom turn at 999d4cd (9 engine calls, ~5 min of workarounds)."""

    def setUp(self):
        super().setUp()
        self.runtime = self.start(WATCH)

    def go_in(self):
        revision, _ = self.runtime.load()
        self.runtime.commit('in', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'In.'}])

    def test_a_speech_and_threshold_business_keep_every_intent(self):
        for line in ('I ease the door open, stay on the threshold, and hold up empty hands. '
                     '"Easy. I\'m only passing through."',
                     'Nik eases the iron door open, stays on the threshold, and holds up empty hands. "Evening."'):
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertEqual(result.kind, 'social')
                self.assertIn('threshold', result.public_event)
                self.assertIn('"', result.public_event)  # the quoted line is kept
                self.assertFalse([e for e in result.events if e.get('type') == 'move'])

    def test_f_narration_around_quoted_speech_is_kept(self):
        line = 'I set my pack by the door. "Who keeps this post?" I keep my hands open.'
        result = self.resolve(self.runtime, line)
        self.assertEqual(result.kind, 'social')
        for part in ('pack by the door', 'Who keeps this post?', 'hands open'):
            self.assertIn(part, result.public_event)

    def test_b_steps_and_goes_are_movement(self):
        for line in ('Nik steps through the iron door.', 'Nik goes through the iron door.', 'I step in.',
                     'Nik steps inside.'):
            with self.subTest(line):
                self.assertEqual(self.moved(self.runtime, line), ['iron_door'])

    def test_b_stepping_in_once_inside_is_not_leaving(self):
        runtime = self.start(SIXC)  # the 6c probe line that a bare "step in" rule took out the door
        line = "I step in and let my eyes catch the light. 'Cousins. I didn't know there were others.'"
        self.assertEqual(self.resolve(runtime, line).kind, 'social')

    def test_c_the_room_s_people_can_speak_on_the_turn_the_pc_enters(self):
        packet = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10)).prepare(
            'I go through the iron door.', one_pass=True)
        private = packet['input']['private']
        self.assertIn('warden', private['discernment_candidates']['actor_bases'])
        self.assertEqual(private['story_brief']['stage'], 'first_look')
        self.assertEqual([p['actor'] for p in private['story_brief']['present']], ['warden'])
        self.assertIn('Watch warden', packet['input']['public']['speakers'])

    def test_c_the_warden_challenges_nik_as_he_walks_in(self):
        from test_kit_agent import RecordingModel
        bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10))
        packet = bridge.prepare('I go through the iron door.', 'in', one_pass=True)
        plan = RecordingModel().plan(packet['input']['private'])
        plan.update(move='npc_reply', table_presence='quiet', focus_actor='warden')
        plan['improv_read'].update(actor_ref='warden', actor_basis='motive')
        narration = ('Lamplight pools on a scarred table where a warden in a dented helm hums over a ledger, a '
                     'heavy chest bolted to the floor behind him, a back stair dropping away in the far corner, '
                     'the air thick with lamp oil and old iron, his crossbow propped within easy reach.')
        challenge = ('Hold there, stranger, and keep those hands where I can see them. Who sent you up my stair, '
                     'and what business brings you to this post at this hour of the night? Speak plain, and quick.')
        result = bridge.complete('in', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': narration}, {'speaker': 'Watch warden', 'text': challenge}]}})
        self.assertIn('Watch warden: Hold there', result['spoken'])
        self.assertEqual(self.runtime.load()[1]['area'], 'watchroom')

    def test_d_a_bare_roll_resolves_the_check_kit_called(self):
        self.go_in()
        revision, state = self.runtime.load()
        plan = {'roll_call': {'skill': 'perception', 'mode': 'normal', 'target': 'warden',
                              'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}}
        body = {'events': [{'type': 'beat', 'tags': ['call'], 'evidence': 'Kit calls for Perception.'}]}
        events = kit_agent.turn_events(self.runtime, body, plan, 't-call')
        self.runtime.commit('t-call', revision, events)
        pending = self.runtime.load()[1]['pending_check']
        self.assertEqual(pending, {'skill': 'perception', 'ability': 'wis', 'target': 'warden',
                                   'called_turn': 't-call'})
        for line in ('Perception 22', '22', 'I rolled a 22.'):
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertEqual(result.kind, 'called_check')
                self.assertIn('22', result.public_event)
                self.assertIn({'type': 'pending_check', 'check': None},
                              [{k: e.get(k) for k in ('type', 'check')} for e in result.events])
                self.assertTrue(any('perception' in e.get('evidence', '').casefold() and 't-call' in e['evidence']
                                    for e in result.events))
        revision, _ = self.runtime.load()
        self.runtime.commit('t-roll', revision, list(self.resolve(self.runtime, 'Perception 22').events))
        self.assertIsNone(self.runtime.load()[1].get('pending_check'))

    def test_d_a_called_check_finds_the_hidden_claim_it_was_aimed_at(self):
        runtime = self.start(SIXC)
        revision, _ = runtime.load()
        plan = {'roll_call': {'skill': 'insight', 'mode': 'normal', 'target': 'uktarl',
                              'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}}
        events = kit_agent.turn_events(runtime, {'events': [{'type': 'beat', 'tags': ['call'],
                                                             'evidence': 'Kit calls for Insight.'}]}, plan, 't-call')
        runtime.commit('t-call', revision, events)
        result = self.resolve(runtime, 'Insight 22')
        self.assertEqual(result.kind, 'check')
        self.assertTrue(any('false_vampires' in e.get('evidence', '') for e in result.events))
        self.assertEqual(result.events[-1]['type'], 'pending_check')

    def test_d_a_called_check_lasts_one_player_turn(self):
        self.go_in()
        revision, _ = self.runtime.load()
        plan = {'roll_call': {'skill': 'perception', 'mode': 'normal', 'target': 'none',
                              'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}}
        self.runtime.commit('t-call', revision, kit_agent.turn_events(
            self.runtime, {'events': [{'type': 'beat', 'tags': ['call'], 'evidence': 'Call.'}]}, plan, 't-call'))
        revision, _ = self.runtime.load()
        self.runtime.commit('t-other', revision, list(self.resolve(self.runtime, 'I look around the room.').events))
        self.assertNotIn('pending_check', self.runtime.load()[1])
        with self.assertRaises(PendingRuling):  # no call is open: a bare roll is a question again
            self.resolve(self.runtime, 'I rolled a 22.')

    def test_d_a_roll_call_target_must_be_real(self):
        from runtime import kit_agenda
        state = self.runtime.load()[1]
        with self.assertRaises(InvalidChange):
            kit_agenda.check_roll_call({'skill': 'perception', 'mode': 'normal', 'target': 'ghost',
                                        'cause': {'kind': 'position', 'ref': 'none', 'roots': []}},
                                       self.runtime.source(), state)

    def test_e_watching_toward_a_feature_does_not_handle_it(self):
        self.go_in()
        for line in ("I watch whether the warden's eyes flick toward the stair or toward the chest.",
                     "Nik looks to see whether the guard's eyes flick toward the stair or toward the chest.",
                     'I look at the chest.', 'I glance toward the chest.'):
            with self.subTest(line):
                try:
                    result = self.resolve(self.runtime, line)
                except PendingRuling:
                    continue
                self.assertNotEqual(result.kind, 'inspect_feature')
                self.assertFalse([e for e in result.events if e.get('type') == 'reveal_fact'])
        self.assertEqual(self.resolve(self.runtime, 'I open the chest.').kind, 'inspect_feature')
        self.assertEqual(self.resolve(self.runtime, 'I look inside the chest.').kind, 'inspect_feature')

    def test_e_a_feature_out_of_reach_is_not_handled(self):
        try:  # on the landing, at the threshold: the chest is across the room
            result = self.resolve(self.runtime, 'I open the chest.')
        except PendingRuling:
            return
        self.assertFalse([e for e in result.events if e.get('type') == 'reveal_fact'])


class LiveWatchroomRules(Base):
    """(g)-(k): 6c-shaped engine rules that broke the watchroom at 999d4cd."""

    def setUp(self):
        super().setUp()
        self.runtime = self.start(WATCH)

    go_in = LiveWatchroomPlaytest.go_in

    def plan_for(self, packet, **update):
        from test_kit_agent import RecordingModel
        plan = RecordingModel().plan(packet['input']['private'])
        plan.update({'move': 'npc_reply', 'table_presence': 'quiet', **update})
        return plan

    def test_g_common_emotions_are_accepted(self):
        bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10))
        packet = bridge.prepare('I hold up empty hands.', 'g', one_pass=True)
        body = packet['input']['private']
        for label, kept in (('anger', 'anger'), ('suspicion', 'suspicion'), ('contempt', 'contempt'),
                            ('fear', 'fear'), ('Angry', 'anger'), ('wary', 'suspicion')):
            with self.subTest(label):
                plan = self.plan_for(packet, focus_actor='none', move='world_description')
                plan['improv_read'].update(actor_ref='none', actor_basis='none')
                plan['appraisal'] = {'label': label, 'intensity': 2, 'cause': 'The warden glares at the stranger.',
                                     'goal_effect': 'neutral', 'target': 'npc'}
                kit_agent.check_plan(plan, [], body['accepted_public_event'], body['action_kind'],
                                     body['discernment_candidates'], 'I hold up empty hands.')
                self.assertEqual(plan['appraisal']['label'], kept)

    def warden_turn(self, action, line, turn='w1', **update):
        bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10))
        packet = bridge.prepare(action, turn, one_pass=True)
        plan = self.plan_for(packet, focus_actor='warden', **update)
        plan['improv_read'].update(actor_ref='warden', actor_basis='motive')
        narration = ('The warden sets down his quill and looks the stranger over from boots to hood, one hand '
                     'resting near the crossbow, the lamp hissing between them while the four hummed notes '
                     'die away and the chair creaks under his weight as he leans forward to listen.')
        return bridge.complete(turn, {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': narration}, {'speaker': 'Watch warden', 'text': line}]}})

    def test_h_a_terse_guard_passes(self):
        self.go_in()
        result = self.warden_turn('I nod to him.', 'Name. Business. Now.')
        self.assertIn('Watch warden: Name. Business. Now.', result['spoken'])

    def test_h_the_floor_is_room_data(self):
        cards = json.loads((ROOT / SIXC).read_text())['public_performance']['actor_cards']
        self.assertIs(cards['Dealer'].get('speech_floor'), True)  # 6c keeps its dealer floor, as data

    def test_i_a_challenge_through_the_door_delivers_the_hook(self):
        self.warden_turn('I knock on the iron door.', 'Who goes there? Speak.')
        story = self.runtime.load()[1].get('story') or {}
        self.assertIn('challenge', (story.get('watchroom') or {}).get('delivered', []))
        self.assertEqual((story.get('watchroom') or {}).get('beats', 0), 0)
        self.go_in()
        from runtime import kit_brief
        self.assertEqual(kit_brief.due_hooks(self.runtime.source(), self.runtime.load()[1]), [])

    def test_i_a_challenge_on_the_entry_turn_delivers_the_hook(self):
        self.warden_turn('I go through the iron door.', 'Hold. Who are you?', turn='w-in')
        story = self.runtime.load()[1]['story']['watchroom']
        self.assertIn('challenge', story['delivered'])

    def call(self, skill, target):
        revision, _ = self.runtime.load()
        plan = {'roll_call': {'skill': skill, 'mode': 'normal', 'target': target,
                              'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}}
        self.runtime.commit('t-call', revision, kit_agent.turn_events(
            self.runtime, {'events': [{'type': 'beat', 'tags': ['call'], 'evidence': 'Call.'}]}, plan, 't-call'))

    def test_j_a_called_persuasion_records_the_attitude_shift(self):
        self.go_in()
        self.call('persuasion', 'warden')
        result = self.resolve(self.runtime, '4')
        self.assertEqual(result.kind, 'social_check')
        revision, _ = self.runtime.load()
        self.runtime.commit('t-roll', revision, list(result.events))
        state = self.runtime.load()[1]
        self.assertEqual(state['attitudes']['warden']['level'], 'unfriendly')
        self.assertNotIn('pending_check', state)

    def test_k_a_guard_beside_the_stair_contests_the_exit(self):
        self.go_in()
        result = self.resolve(self.runtime, 'I take the back stair down.')
        self.assertEqual(result.kind, 'exit_contested')
        self.assertFalse([e for e in result.events if e.get('type') == 'move'])
        revision, _ = self.runtime.load()
        self.runtime.commit('t-try', revision, list(result.events))
        self.assertEqual(self.runtime.load()[1]['pending_check']['exit'], 'back_stair')
        lost = self.resolve(self.runtime, 'Athletics 5')
        self.assertFalse([e for e in lost.events if e.get('type') == 'move'])
        won = self.resolve(self.runtime, 'Acrobatics 25')
        self.assertEqual([e['exit'] for e in won.events if e.get('type') == 'move'], ['back_stair'])

    def test_k_control_an_asleep_or_friendly_guard_lets_the_pc_go(self):
        self.go_in()
        for change in ({'status': 'asleep'}, {'attitude': 'friendly'}):
            with self.subTest(change):
                revision, state = self.runtime.load()
                state = json.loads(json.dumps(state))
                if 'status' in change:
                    state['actors']['warden']['status'] = 'asleep'
                else:
                    state.setdefault('attitudes', {})['warden'] = {'level': 'friendly'}
                result = RoomAdjudicator(roll=lambda: 10, source=self.runtime.source()).resolve(
                    'I take the back stair down.', revision, state)
                self.assertEqual([e['exit'] for e in result.events if e.get('type') == 'move'], ['back_stair'])

    def test_k_an_unguarded_exit_stays_instant(self):
        self.go_in()
        self.assertEqual(self.moved(self.runtime, 'I go back through the iron door.'), ['iron_door'])


class FightersHaveStatBlocks(Base):
    """(l) Every actor who can fight has a stat block the engine can use (watchroom playtest)."""

    def test_a_fighter_without_a_stat_block_fails_to_mount(self):
        body = kit_rooms.read_room(WATCH)
        del body['actors']['warden']['stat_block']
        with self.assertRaisesRegex(kit_rooms.RoomMountError, 'warden can fight but has no usable stat_block'):
            kit_rooms.load_room(self.write(body))
        body['actors']['warden']['stat_block'] = {'srd': 'Dragon Turtle'}
        with self.assertRaisesRegex(kit_rooms.RoomMountError, 'warden can fight'):
            kit_rooms.load_room(self.write(body))

    def test_an_inline_stat_block_mounts(self):
        body = kit_rooms.read_room(WATCH)
        body['actors']['warden']['stat_block'] = {'ac': 14, 'hp': 9, 'attacks': [{'name': 'club', 'to_hit': 2, 'damage': 3}]}
        kit_rooms.load_room(self.write(body))

    def test_the_warden_enters_initiative_on_engine(self):
        runtime = self.start(WATCH)
        revision, _ = runtime.load()
        runtime.commit('in', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'In.'}])
        result = self.resolve(runtime, 'I attack the warden with my rapier. Attack 17')
        self.assertEqual(result.kind, 'combat_round')
        revision, _ = runtime.load()
        runtime.commit('hit', revision, list(result.events))
        self.assertEqual(runtime.load()[1]['combat']['hp'], {'warden': 11})  # SRD Guard
        result = self.resolve(runtime, 'Initiative 15')
        revision, _ = runtime.load()
        runtime.commit('init', revision, list(result.events))
        fight = runtime.load()[1]['combat']
        self.assertEqual(fight['status'], 'running')
        self.assertIn('warden', fight['order'])

    def test_an_alarm_says_who_answers_it(self):
        import warnings
        body = kit_rooms.read_room(WATCH)
        alarm = body['facts']['bell']['alarm']
        self.assertEqual((alarm['responders'][0]['count'], alarm['responders'][0]['stat_block'],
                          alarm['arrives_in_rounds']), (2, {'srd': 'Guard'}, 2))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            kit_rooms.load_room(WATCH)
        self.assertEqual([w for w in caught if issubclass(w.category, kit_rooms.RoomWarning)], [])
        del body['facts']['bell']['alarm']
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            kit_rooms.load_room(self.write(body))  # mounts, but loudly
        self.assertTrue(any('bell' in str(w.message) and 'no responders' in str(w.message) for w in caught))
        body['facts']['bell']['alarm'] = {'responders': [{'who': 'guards', 'count': 2}], 'arrives_in_rounds': 2}
        with self.assertRaisesRegex(kit_rooms.RoomMountError, 'bell alarm needs responders'):
            kit_rooms.load_room(self.write(body))

    def test_the_shipped_rooms_declare_their_fighters(self):
        for ref in (SIXC, STUB, WATCH):
            with self.subTest(ref):
                self.assertEqual(kit_rooms.fighter_problems(kit_rooms.read_room(ref)), [])


class ReviewNotes(Base):
    """P3s fixed in passing."""

    def test_a_second_file_with_a_room_id_already_left_is_refused(self):
        first = chain.build_chain(self.folder)
        twin = json.loads((self.folder / 'watchroom.json').read_text(encoding='utf-8'))
        twin['id'] = 'dotmm-level-01-area-06c-testbed-v1'  # 6c's id, a different file
        (self.folder / 'watchroom.json').write_text(json.dumps(twin), encoding='utf-8')
        runtime = self.start(first)
        with self.assertRaises(PendingRuling) as caught:
            self.resolve(runtime, 'I walk out the south door.')
        self.assertIn("room id 'dotmm-level-01-area-06c-testbed-v1' is already used by another room file",
                      caught.exception.host_error['problems'])

    def test_a_float_hp_still_takes_the_room_s_damage(self):
        state = {'player_sheet': {'hp': 20.0}, 'combat': {'pc_damage': 5}}
        sheet, _, _ = kit_rooms.fold_pc({'id': 'x'}, state)
        self.assertEqual(sheet['hp'], 15.0)

    def test_no_doubled_place_name(self):
        body = kit_rooms.read_room(WATCH)
        body['areas']['watchroom']['called'] = 'the iron door'
        runtime = self.start(self.write(body))
        self.assertEqual(self.resolve(runtime, 'I go through the iron door.').public_event, 'You go through the iron door.')

    def test_the_room_path_is_in_the_first_snapshot(self):
        runtime = self.start(WATCH)
        self.assertEqual(runtime.load()[1]['room']['path'], WATCH)


if __name__ == '__main__':
    unittest.main()
