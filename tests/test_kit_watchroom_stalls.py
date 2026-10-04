"""The nine watchroom stalls tagged [open — not in #87] in
tests/playtests/2026-10-04-watchroom-nik.md, each written as a failing test first on the
watchroom fixture (or the 17a stub), never 6c. Dice pinned; no model."""
import json
import unittest

from runtime import kit_agent, kit_brief, kit_rooms
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator
from runtime.state_context import InvalidChange, encode
from test_kit_room_review import STUB, WATCH, Base

NARRATION = ('Lamplight pools on a scarred table where a warden in a dented helm hums over a ledger, a heavy '
             'chest bolted to the floor behind him, a back stair dropping away in the far corner, the air thick '
             'with lamp oil and old iron, his spear propped within easy reach of his hand.')
LANDING = ('Lamplight leaks through the gap in the iron door and lays a thin bright stripe across the landing '
           'stones. Behind the door someone hums the same four notes over and over, and a chair creaks when he '
           'shifts. A stair winds on down past the door into the dark, cold and quiet, and nothing climbs it.')


LANDING_MORE = ('The post is awake. Whoever keeps it is watching the stair rather than sleeping on it, and the '
                'door stands ajar the width of a hand, the light inside steady and close and warm.')


def landing(text=LANDING):
    return {'segments': [{'speaker': 'Narrator', 'text': text}, {'speaker': 'Narrator', 'text': LANDING_MORE}]}


def inside_only(source):
    """Every string that belongs inside the watchroom and must not reach the approach."""
    inside = set(kit_rooms.room_areas(source))
    secret = [f['text'] for f in source['facts'].values() if f['area'] in inside]
    warden = source['actors']['warden']
    secret += [warden['motive'], *warden['knowledge'], *warden['communication_profile'].values()]
    for story in source['story'].values():
        secret += [story['about'], *story['endings'], *(h['text'] for h in story['hooks'])]
    return secret + ['who sent you', 'where are you going']


QUIET = {'kind': 'none', 'reason': 'the description stands on its own; the player acts next'}


class Stalls(Base):
    def setUp(self):
        super().setUp()
        self.runtime = self.start(WATCH)
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))

    def plan_for(self, packet, **update):
        from test_kit_agent import RecordingModel
        plan = RecordingModel().plan(packet['input']['private'])
        plan.update({'move': 'world_description', 'table_presence': 'quiet', 'focus_actor': 'none',
                     # Kit declares how the turn hands over (#102 review). These fixtures replay
                     # watchroom description beats that end on the scene, not on a prompt.
                     'hands_off': QUIET, **update})
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        return plan

    def go_in(self):
        revision, _ = self.runtime.load()
        self.runtime.commit('in', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'In.'}])


class S1ApproachBriefFrames(Stalls):
    """T0: the doorway brief was thin (no hooks, no context). Tease-only, but never empty."""

    def test_the_approach_brief_gives_kit_enough_to_frame(self):
        made = kit_brief.brief(self.runtime.source(), self.runtime.load()[1])
        self.assertEqual(made['stage'], 'approach')
        self.assertTrue(made['about'])
        self.assertEqual([v for v in made['visible']],
                         ['The iron door stands ajar; lamplight shows beyond it.',
                          'Someone behind the door hums the same four notes over and over.'])
        self.assertIn('An iron door, standing ajar.', made['ways_on'])
        self.assertIn('A stair winds down past the door.', made['ways_on'])
        self.assertTrue(made['purposes'])  # what the approach is for, so Kit can frame it
        self.assertTrue(made['hooks_waiting'])  # a hook waits inside: named by id, never by text
        self.assertEqual(made['hooks_waiting'][0], {'id': 'challenge', 'by': 'Watch warden', 'inside': True})
        text = encode(made).casefold()
        for secret in inside_only(self.runtime.source()):
            with self.subTest(secret):
                self.assertNotIn(secret.casefold(), text)

    def test_the_17a_doorway_brief_is_never_empty(self):
        runtime = self.start(STUB)
        made = kit_brief.brief(runtime.source(), runtime.load()[1])
        for key in ('about', 'visible', 'ways_on', 'purposes'):
            with self.subTest(key):
                self.assertTrue(made[key])


class S2InsideActorsAreOnlyHeard(Stalls):
    """T0: the landing's speaker list named the warden, who is inside."""

    def test_the_landing_speakers_do_not_list_the_warden(self):
        packet = self.bridge.prepare('I wait on the landing and listen.', 'l', one_pass=True)
        public = packet['input']['public']
        self.assertNotIn('Watch warden', public['speakers'])
        self.assertEqual(public['heard'], [{'speaker': 'Watch warden', 'heard': (
            'a man humming four notes over and over; a chair creaks when he shifts')}])

    def test_inside_the_warden_is_a_speaker(self):
        self.go_in()
        packet = self.bridge.prepare('I nod to him.', 'i', one_pass=True)
        self.assertIn('Watch warden', packet['input']['public']['speakers'])
        self.assertNotIn('heard', packet['input']['public'])


class S3OpeningCommitsFirstTry(Stalls):
    """T0: the opening was rejected twice (story basis; reply_to on the entry turn)."""

    def opening(self):
        return self.bridge.prepare(opening=True, one_pass=True)

    def test_the_room_entry_commits_on_the_first_try(self):
        packet = self.opening()
        plan = self.plan_for(packet)
        plan['improv_read'].update(story_anchor='scene', story_basis='tease')  # Kit's live first try
        plan['public_brief'].update(reply_to='the landing', scope='feature')
        result = self.bridge.complete(packet['turn_id'], {'decision': plan, 'performance': landing()})
        self.assertEqual(result['public_event'], packet['input']['private']['accepted_public_event'])
        trace = self.runtime.committed_kit_turn(packet['turn_id'])['trace']
        self.assertEqual(trace['public_brief']['reply_to'], 'none')
        self.assertEqual((self.runtime.kit_timing(packet['turn_id']) or {}).get('rejected_attempts', 0), 0)

    def test_the_story_bases_come_from_the_mounted_room(self):
        bases = self.opening()['input']['private']['discernment_candidates']['story_bases']
        self.assertIn('tease', bases['scene'])
        self.assertIn('challenge', bases['scene'])
        self.assertIn('scene_state', bases['scene'])

    def test_an_anchor_that_is_not_active_falls_back_to_the_scene(self):
        packet = self.opening()
        plan = self.plan_for(packet)
        plan['improv_read'].update(story_anchor='level', story_basis='level one pressure')
        plan['public_brief'].update(reply_to='none', scope='feature')
        self.bridge.complete(packet['turn_id'], {'decision': plan, 'performance': landing()})
        read = self.runtime.committed_kit_turn(packet['turn_id'])['trace']['improv_read']
        self.assertEqual((read['story_anchor'], read['story_basis']), ('scene', 'scene_state'))

    def test_a_real_actor_reference_is_still_checked(self):
        packet = self.opening()
        plan = self.plan_for(packet)
        plan['improv_read'].update(actor_ref='ghost', actor_basis='motive')
        with self.assertRaises(InvalidChange):
            self.bridge.complete(packet['turn_id'], {'decision': plan, 'performance': landing()})


PEEKS = ('Nik creeps to the hinge side of the gap and puts one eye to the opening without touching the door.',
         'I peek through the gap in the door.', 'I listen at the iron door.', 'I put my ear to the door.',
         'Nik cracks the door and looks through.', 'I look through the door.',
         'Nik edges up beside the gap and peeks in.', 'I press an eye to the crack of the door and watch.')


class S4ThresholdPerceptionIsNotMovement(Stalls):
    """T1: a peek through the door gap was read as walking out through the door."""

    def test_looking_and_listening_at_a_door_do_not_move_the_pc(self):
        for line in PEEKS:
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertEqual(result.kind, 'threshold_look')
                self.assertFalse([e for e in result.events if e.get('type') == 'move'])

    def test_going_through_still_moves(self):
        for line in ('I go through the iron door.', 'Nik steps through the door and looks around.',
                     'I slip through the iron door.'):
            with self.subTest(line):
                self.assertEqual(self.moved(self.runtime, line), ['iron_door'])


CHECK_ASKS = ('Can I make a check?', 'Can I roll for that?', 'Could I make a Perception check?',
              'Do I get a roll to spot anything?', 'Nik edges up beside the gap and peeks in. Can I make a check?',
              'May I roll Stealth to get closer?')


class S5ACheckRequestIsKitsCall(Stalls):
    """T1: no engine path for 'Can I make a check?'; it routed as a social declaration."""

    def test_asking_for_a_check_is_a_check_request(self):
        for line in CHECK_ASKS:
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertEqual(result.kind, 'check_request')
                self.assertNotIn('You declare', result.public_event)
                self.assertFalse(any('d20' in e.get('evidence', '') for e in result.events))  # nothing rolled

    def test_the_packet_says_kit_calls_the_check_or_declines(self):
        packet = self.bridge.prepare('Could I make a Perception check?', 'c', one_pass=True)
        ask = packet['input']['private']['check_request']
        self.assertIn('Kit decides', ask['rule'])
        self.assertEqual(ask['player_named'], 'perception')  # a request, never the call

    def answer(self, turn, **update):
        packet = self.bridge.prepare('Can I make a check?', turn, one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief', **update)
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        return self.bridge.complete(turn, {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': text, 'reacts_to': 'Can I make a check'}
            for text in [update.pop('_say', None) or 'Make a Dexterity (Stealth) check.']]}})

    def test_kit_calls_a_check(self):
        call = {'skill': 'stealth', 'mode': 'normal', 'target': 'warden',
                'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}
        self.answer('call', roll_call=call)
        self.assertEqual(self.runtime.load()[1]['pending_check']['skill'], 'stealth')

    def test_kit_may_decline(self):
        packet = self.bridge.prepare('Can I make a check?', 'no', one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief')
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        self.bridge.complete('no', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'No roll needed: you hear him humming plainly from here.',
             'reacts_to': 'Can I make a check'}]}})
        self.assertNotIn('pending_check', self.runtime.load()[1])


class S6ThresholdView(Stalls):
    """T2: no view for peeking into the next area."""

    def test_a_peek_gets_the_next_area_s_approach_view(self):
        packet = self.bridge.prepare(PEEKS[0], 'p', one_pass=True)
        view = packet['input']['private']['threshold_view']
        self.assertEqual(view['through'], 'the iron door')
        self.assertEqual(view['into'], 'the watchroom')
        self.assertEqual(view['tease'], self.runtime.source()['areas']['landing']['tease']['text'])
        self.assertEqual(view['heard'], [{'speaker': 'Watch warden', 'heard': (
            'a man humming four notes over and over; a chair creaks when he shifts')}])
        self.assertEqual(self.runtime.load()[1]['area'], 'landing')
        text = encode(packet['input']).casefold()
        for secret in inside_only(self.runtime.source()):
            with self.subTest(secret):
                self.assertNotIn(secret.casefold(), text)

    def test_the_check_kit_called_on_the_peek_keeps_the_view(self):
        packet = self.bridge.prepare(PEEKS[0], 'p', one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief', roll_call={
            'skill': 'stealth', 'mode': 'normal', 'target': 'warden',
            'cause': {'kind': 'position', 'ref': 'none', 'roots': []}})
        plan['public_brief'].update(reply_to='puts one eye to the opening', scope='call')
        self.bridge.complete('p', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'Make a Dexterity (Stealth) check.', 'reacts_to': 'puts one eye to'}]}})
        rolled = self.bridge.prepare('Stealth check: 1d20 (13) + 2 = 15', 'r', one_pass=True)
        self.assertEqual(rolled['input']['private']['threshold_view']['through'], 'the iron door')
        self.assertEqual(self.runtime.load()[1]['area'], 'landing')

    def test_no_view_on_an_ordinary_turn(self):
        packet = self.bridge.prepare('I wait on the landing.', 'w', one_pass=True)
        self.assertNotIn('threshold_view', packet['input']['private'])


class S7WatchAndAskKeepsEveryIntent(Stalls):
    """T3: a turn mixing watching with questions stalled on 'needs a ruling'."""

    LINES = (('Nik watches the man for a moment. Is the chest locked? Is there a bell, a horn, or a cord he '
              'could use to raise an alarm?', ('watches the man', 'Is the chest locked?', 'raise an alarm?')),
             ('Nik watches the warden. Is there anywhere to hide? Could he reach the bell?',
              ('watches the warden', 'anywhere to hide?', 'reach the bell?')),
             ('I study the warden\'s hands. Could I grab the spear before he moves?',
              ('study the warden', 'grab the spear before he moves?')))

    def test_watching_and_asking_never_stall(self):
        self.go_in()
        for line, parts in self.LINES:
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                for part in parts:
                    self.assertIn(part, result.public_event)
                self.assertFalse([e for e in result.events if e.get('type') in ('move', 'reveal_fact')])

    def test_a_declared_grab_is_still_a_physical_act(self):
        self.go_in()
        with self.assertRaises(PendingRuling):
            self.resolve(self.runtime, 'I grab the spear.')


class S8EngineLineNeverAfterTheHandoff(Stalls):
    """T6: 'You go through the iron door…' was printed after Kit's handoff."""

    def test_the_entry_line_comes_before_the_performance(self):
        packet = self.bridge.prepare('I go through the iron door.', 'in', one_pass=True)
        plan = self.plan_for(packet, move='npc_reply', focus_actor='warden', table_presence='brief')
        plan['improv_read'].update(actor_ref='warden', actor_basis='motive')
        result = self.bridge.complete('in', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': NARRATION},
            {'speaker': 'Watch warden', 'text': 'Hold there. Who sent you?'},
            {'speaker': 'Kit', 'text': 'Your move.', 'reacts_to': 'Hold there'}]}})
        lines = result['spoken'].splitlines()
        self.assertEqual(lines[-1], 'Kit: Your move.')
        self.assertTrue(lines[0].startswith('Narrator: You go through the iron door'))

    def test_a_leaving_line_never_follows_kit(self):
        self.go_in()
        packet = self.bridge.prepare('I go back through the iron door.', 'out', one_pass=True)
        plan = self.plan_for(packet, move='npc_reply', focus_actor='warden', table_presence='brief')
        plan['improv_read'].update(actor_ref='warden', actor_basis='motive')
        result = self.bridge.complete('out', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Narrator', 'text': NARRATION},
            {'speaker': 'Watch warden', 'text': 'And stay out. Who sent you?'},
            {'speaker': 'Kit', 'text': 'Out you go.', 'reacts_to': 'And stay out'}]}})
        self.assertEqual(result['spoken'].splitlines()[-1], 'Kit: Out you go.')


PAID = {'segments': [
    {'speaker': 'Narrator', 'text': 'Far down the stair, boots that had been climbing have stopped. Whoever wears them '
                                    'is standing still in the dark below, listening up toward the landing, and the '
                                    'humming behind the iron door goes on as if nothing happened.'},
    {'speaker': 'Narrator', 'text': 'A long breath later the boots start again, going down this time, unhurried, '
                                    'until the turn of the stair swallows the sound.'}]}


class S9OpenThreads(Stalls):
    """The hook Kit planted ('something below stops moving') never paid off."""

    def turn(self, turn, line, threads, more=None):
        packet = self.bridge.prepare(line, turn, one_pass=True)
        plan = self.plan_for(packet, open_threads=threads)
        plan['public_brief'].update(reply_to=line[:12], scope='exchange')
        self.bridge.complete(turn, {'decision': plan, 'performance': more or landing()})
        return packet

    def test_a_planted_thread_is_listed_until_paid_off(self):
        self.turn('a', 'I wait on the landing.', {'plant': [{'id': 'below', 'hint': 'Something below stops moving.'}]})
        threads = self.runtime.load()[1]['open_threads']
        self.assertEqual(threads['below']['hint'], 'Something below stops moving.')
        listed = self.bridge.prepare('I keep listening.', 'b', one_pass=True)['input']['private']['open_threads']
        self.assertEqual([t['id'] for t in listed['threads']], ['below'])
        self.assertIn('pay off or clean up', listed['rule'])
        self.bridge.abandon('b')
        self.turn('c', 'I keep listening.', {'pay': ['below']}, more=PAID)
        self.assertNotIn('below', self.runtime.load()[1].get('open_threads') or {})

    def test_paying_an_unknown_thread_is_refused(self):
        with self.assertRaises(InvalidChange):
            self.turn('a', 'I wait on the landing.', {'pay': ['nothing_like_it']})

    def test_threads_are_due_before_the_scene_ends(self):
        self.turn('a', 'I wait on the landing.', {'plant': [{'id': 'below', 'hint': 'Something below stops moving.'}]})
        self.go_in()
        revision, _ = self.runtime.load()
        self.runtime.commit('down', revision, [{'type': 'move', 'exit': 'back_stair', 'evidence': 'Down.'}])
        listed = self.bridge.prepare('I look around.', 'z', one_pass=True)['input']['private']['open_threads']
        self.assertTrue(listed['due'])

    def test_no_threads_no_field(self):
        packet = self.bridge.prepare('I wait on the landing.', 'n', one_pass=True)
        self.assertNotIn('open_threads', packet['input']['private'])


class FirstTryHeader(Stalls):
    """PR1: the constraints the engine already knows, stated at the top of the packet."""

    def test_the_packet_opens_with_the_first_try_lines(self):
        packet = self.bridge.prepare(opening=True, one_pass=True)
        self.assertEqual(next(iter(packet)), 'first_try')
        lines = '\n'.join(packet['first_try'])
        self.assertIn('reply_to is none', lines)
        self.assertIn('scene: scene_state, tease', lines)
        self.assertIn('anger', lines)
        self.assertIn('heard only, not here: Watch warden', lines)
        self.assertLess(len(json.dumps(packet['first_try'])), 1500)

    def test_a_terse_actor_is_named(self):
        self.go_in()
        packet = self.bridge.prepare('I nod to him.', 'n', one_pass=True)
        self.assertTrue(any(line.startswith('Terse is fine for Watch warden') for line in packet['first_try']))


if __name__ == '__main__':
    unittest.main()
