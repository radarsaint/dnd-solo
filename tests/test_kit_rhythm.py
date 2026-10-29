"""The check rhythm: one line asks and calls, the roll is one light commit.

Patter does not add a round trip. A move and a check in the same words both happen.
Invented sensory leads are refused. Synthetic rooms only.
"""
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from runtime import kit_adventure
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_watchroom_stalls import Stalls


class PlayCard(unittest.TestCase):
    def test_the_card_states_the_rhythm_and_the_formats_hosts_missed(self):
        from pathlib import Path
        card = Path('docs/PLAY_CARD.md').read_text(encoding='utf-8')
        self.assertIn('Feet or the door? Either way, roll me Perception.', card)
        self.assertIn('never adds a round trip', card)
        self.assertIn('reacts_to', card)
        self.assertIn('at least 2 words', card)
        self.assertIn('80 words', card)
        self.assertIn('Do not invent', card)
        self.assertIn('the landing stays wet', card)
        self.assertIn('"decision"', card)
        self.assertIn('"performance"', card)
        self.assertIn('"manifest"', card)
        self.assertIn('turn_id', card)
        self.assertIn('session_manifest.hash', card)
        self.assertIn('room_manifest.hash', card)
        self.assertIn('one message', card)
        self.assertIn('Do not post fiction before the tools', card)
        self.assertIn('sheet', card.casefold())
        self.assertIn('go-ahead to begin', card)


class CheckRhythm(Stalls):
    def _call(self):
        packet = self.bridge.prepare('Can I make a check?', 'ask', one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief', roll_call={
            'skill': 'perception', 'mode': 'normal', 'target': 'none',
            'cause': {'kind': 'position', 'ref': 'none', 'roots': []}})
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        return self.bridge.complete('ask', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'Feet or the door? Either way, roll me Perception.',
             'reacts_to': 'Can I make a check'}]}})

    def test_a_question_without_the_call_is_another_round_trip(self):
        packet = self.bridge.prepare('Can I make a check?', 'q', one_pass=True)
        plan = self.plan_for(packet, move='ask_clarification', table_presence='brief')
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        with self.assertRaisesRegex(InvalidChange, 'round trip'):
            self.bridge.complete('q', {'decision': plan, 'performance': {'segments': [
                {'speaker': 'Kit', 'text': 'What are you focusing on?',
                 'reacts_to': 'Can I make a check'}]}})

    def test_the_roll_commits_the_prepared_outcome_in_one_call(self):
        self._call()
        self.assertIn('bands', self.runtime.load()[1]['prepared_roll'])
        before = self._heavy_roll_ms()
        started = time.perf_counter()
        done = self.bridge.prepare('The door. 14.', one_pass=True)
        after_ms = (time.perf_counter() - started) * 1000
        self.assertTrue(done.get('committed'))
        self.assertEqual(done.get('calls'), 1)
        self.assertNotIn('input', done)
        self.assertIn('comes up', done['spoken'].lower())
        self.assertNotIn('DC', done['spoken'])
        self.assertLess(after_ms, before)
        self.assertLess(after_ms, 50)
        # Felt wait, milliseconds, for the roll message.
        self.assertGreater(before, after_ms)

    def _heavy_roll_ms(self):
        """The old roll message: a full prepare, because the prepared outcome was not kept."""
        other = Stalls()
        other.setUp()
        self.addCleanup(other.runtime.close)
        packet = other.bridge.prepare('Can I make a check?', 'ask2', one_pass=True)
        plan = other.plan_for(packet, move='ruling', table_presence='brief', roll_call={
            'skill': 'perception', 'mode': 'normal', 'target': 'none',
            'cause': {'kind': 'position', 'ref': 'none', 'roots': []}})
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        other.bridge.complete('ask2', {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'Feet or the door? Either way, roll me Perception.',
             'reacts_to': 'Can I make a check'}]}})
        revision = other.runtime.load()[0]
        other.runtime.commit('strip', revision, [{
            'type': 'prepared_roll', 'clear': True,
            'evidence': 'Measuring the roll without a prepared outcome.'}])
        started = time.perf_counter()
        packet = other.bridge.prepare('The door. 14.', one_pass=True)
        elapsed = (time.perf_counter() - started) * 1000
        self.assertFalse(packet.get('committed'))
        return elapsed

    def test_a_different_deed_makes_the_prepared_outcome_stale(self):
        self._call()
        packet = self.bridge.prepare('I wait on the landing.', one_pass=True)
        self.assertFalse(packet.get('committed'))
        self.assertNotIn('prepared_roll', self.runtime.load()[1])

    def test_invented_flavor_that_implies_a_lead_is_refused(self):
        packet = self.bridge.prepare('I look around the landing.', 'look', one_pass=True)
        plan = self.plan_for(packet, table_presence='brief')
        plan['public_brief'].update(reply_to='look around the landing', scope='feature')
        with self.assertRaisesRegex(InvalidChange, 'not in the book'):
            self.bridge.complete('look', {'decision': plan, 'performance': {'segments': [
                {'speaker': 'Narrator', 'text': (
                    'A twig snaps in the brush past the landing, and a scrap of cloth hangs on the thorns '
                    'where someone passed and did not come back, the fibers still moving in a draft that '
                    'has no source you can see from here on the stones by the iron door.')},
                {'speaker': 'Narrator', 'text': (
                    'The stripe of light on the landing stones does not reach that brush, and the humming '
                    'behind the door goes on, four notes, a chair creaking when the weight inside shifts.')},
                {'speaker': 'Kit', 'text': 'Leave it.', 'reacts_to': 'look around the landing'}]}})


class Compound(unittest.TestCase):
    def test_creeping_the_path_while_watching_moves_and_checks(self):
        import tempfile
        from pathlib import Path
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'kit.sqlite'
        text = Path('tests/fixtures/adventures/revisit_road.txt').read_text(encoding='utf-8')
        report = kit_adventure.ingest_adventure(db, text=text)
        from runtime.kit_agent import start_session
        started = start_session(db, 'tests/fixtures/characters/nik.json', room=report['start_room'])
        runtime = Runtime(db)
        self.addCleanup(runtime.close)
        bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))
        bridge.prepare('Yes.', one_pass=True)
        revision, state = runtime.load()
        bridge.adjudicator.mount(runtime.source())
        result = bridge.adjudicator.resolve(
            'I creep along the path watching for traps.', revision, state)
        self.assertEqual(result.kind, 'check_request')
        self.assertTrue(any(event.get('type') == 'move' for event in result.events), result.events)


class OpeningAndExits(unittest.TestCase):
    def test_the_book_opens_on_scene_a_and_yes_commits_it(self):
        import tempfile
        from pathlib import Path
        from runtime.kit_agent import start_session
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = Path(folder.name) / 'kit.sqlite'
        text = Path('tests/fixtures/adventures/wagon_road.txt').read_text(encoding='utf-8')
        report = kit_adventure.ingest_adventure(db, text=text)
        self.assertTrue(str(report['start_location']).endswith(':A'), report['start_location'])
        self.assertNotIn('timber', report['start_location'].casefold())
        picks = {item['pick']: item['id'] for item in report['starts']}
        self.assertIn('A', picks)
        self.assertIn('1', picks)
        other = kit_adventure.choose_start(db, '1')
        self.assertIn('-1', other['location'])
        scene = kit_adventure.choose_start(db, 'A')
        self.assertTrue(scene['location'].endswith(':A'))
        started = start_session(db, 'tests/fixtures/characters/nik.json', room=report['start_room'])
        self.assertTrue(started.get('committed'))
        self.assertTrue(started.get('character_loaded'))
        self.assertEqual(started.get('opened_room'), started.get('room_id'))
        self.assertIn('wagon', (started.get('spoken') or '').lower())

    def test_a_bell_in_the_path_sentence_is_not_an_exit(self):
        raw = (
            'PART 1: THE POST\n\n'
            '1. Landing\n'
            '> A rope bell hangs on a post beside the track.\n'
            'A dry path runs past the bell rope to area 2.\n\n'
            '2. Bank\n'
            '> The bank is bare.\n'
            'The path leads back to area 1.\n'
        )
        text = kit_adventure.prepare_source(raw)
        index = kit_adventure.build_index(text)
        room, _side = kit_adventure.draft_room('kit.sqlite', 'post-1', index, text)
        aliases = []
        for edge in room['exits'].values():
            aliases.extend(edge.get('aliases') or [])
        self.assertIn('path', aliases)
        self.assertNotIn('bell', aliases)
        self.assertNotIn('rope', aliases)
        from runtime.kit_agent import room_intent, room_words
        state = {'area': 'here', 'known_exits': list(room['exits']), 'known_facts': [], 'actors': {}}
        words = room_words(room, state)
        self.assertNotEqual(room_intent('I take the bell rope.', room=words), 'exit')
        self.assertEqual(room_intent('I go along the path.', room=words), 'exit')

    def test_a_bad_mirror_keeps_its_fix_through_complete(self):
        packet = self_bridge = None
        stalls = Stalls()
        stalls.setUp()
        self.addCleanup(stalls.runtime.close)
        packet = stalls.bridge.prepare('I look around the landing.', 'm', one_pass=True)
        plan = stalls.plan_for(packet)
        plan['public_brief'].update(reply_to='look around the landing', scope='call')
        plan['public_brief']['mirror'] = 'steady energy, standard, dry humor'
        with self.assertRaises(InvalidChange) as caught:
            stalls.bridge.complete('m', {'decision': plan, 'performance': {'segments': [
                {'speaker': 'Kit', 'text': 'Where next?', 'reacts_to': 'look around the landing'}]}})
        self.assertIn('Fix:', str(caught.exception))
        self.assertIn('public_brief.mirror', str(caught.exception))
        self.assertIn(': meet the pace', caught.exception.fix['public_brief.mirror'])


if __name__ == '__main__':
    unittest.main()
