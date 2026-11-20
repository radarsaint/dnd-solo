"""v0.11.3: a roll answers through the host CLI with its own words as the input, a miss is
textured only from what the player perceived, a cached opening starts like a cold one, and
in-combat is one engine-owned state every turn reads.

Synthetic road scene only. No published adventure text.
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import kit_moves, kit_prep, kit_router, kit_skim, state_context
from runtime.kit_agent import RoomAdjudicator, SIMPLE_ACT_LINE
from runtime.state_context import Runtime

from test_kit_adventure_pdf import make_pdf
from test_kit_agent import RecordingModel
from test_kit_host_contract_round2 import call
from test_kit_scene_contract_gpt import ENCOUNTER, FICTION, LOW_SHEET, SCENE
from test_kit_turn_spine import CONDITION, Scene

ROOT = Path(__file__).resolve().parents[1]
QUESTION = 'Roll History. What do I know about bandits on this road?'


def cli_complete(db, prepared, reply_to, text):
    plan = RecordingModel().plan(prepared['input']['private'])
    plan.update(move='ruling', focus_actor='none', table_presence='brief')
    plan['improv_read'].update(actor_ref='none', actor_basis='none')
    plan['public_brief'].update(reply_to=reply_to, scope='call')
    reply = {'decision': plan, 'performance': {'segments': [
        {'speaker': 'Kit', 'text': text, 'reacts_to': reply_to}]}}
    session, room = prepared.get('session_manifest') or {}, prepared.get('room_manifest') or {}
    if session.get('hash') and room.get('hash'):
        reply['manifest'] = {'session': session['hash'], 'room': room['hash']}
    out = Path(db).parent / 'o.json'
    out.write_text(json.dumps(reply))
    done = subprocess.run([sys.executable, '-m', 'runtime.kit_agent', 'complete', '--db', str(db), '--turn-id',
                           prepared['turn_id'], '--input-file', str(out)], cwd=ROOT, capture_output=True,
                          text=True, timeout=30)
    text_out = done.stdout or done.stderr
    return json.loads(text_out[text_out.index('{'):])


class RollAnswersThroughTheHostCli(Scene):
    """Live: record -> rules question -> 'Roll History. What do I know...' -> '12'."""

    def test_the_roll_turn_is_the_roll_line(self):
        self._start(LOW_SHEET)
        db = self.runtime.path
        folder = Path(db).parent
        beat, action = folder / 'beat.json', folder / 'a.txt'
        beat.write_text(json.dumps({'happened': 'A stone flushed the bandits; they charge.',
                                    'revealed': ['bandit'], 'encounter': 'started'}))
        self.assertEqual(call('record', '--db', db, '--input-file', beat)['stage'], 'recorded')

        def prepare(line):
            action.write_text(line)
            return call('prepare', '--one-pass', '--db', db, '--action-file', action)
        asked = prepare('Can I stay hidden if I use my bonus action to hide?')
        self.assertEqual(asked['stage'], 'one_pass')
        done = cli_complete(db, asked, 'stay hidden if I use my bonus action',
                            'While they look for you, you stay hidden until you attack. What do you do?')
        self.assertIn('spoken', done, done)
        called = prepare(QUESTION)
        self.assertEqual(called['stage'], 'called_roll', called)
        self.assertIn('Roll History.', called['spoken'])
        answered = prepare('12')
        self.assertEqual(answered['check_outcome']['skill'], 'history', answered)
        public = answered['input']['private']['accepted_public_event']
        self.assertNotIn(QUESTION, public)
        self.assertNotIn('Table talk', public)
        self.assertIn(QUESTION, answered['knowledge'])
        done = cli_complete(db, answered, '12', 'Old tales of raiders on this road come back to you. What do you do?')
        self.assertIn('spoken', done, done)
        runtime = Runtime(str(db))
        try:
            last = runtime.recent_kit_turns(limit=1)[-1]
        finally:
            runtime.close()
        self.assertEqual(last['player_input'], '12')


class MissUsesOnlyPerceivedText(unittest.TestCase):
    def test_a_dm_note_beside_the_read_aloud_never_textures_a_miss(self):
        adjudicator = RoomAdjudicator(roll=lambda: 10)
        adjudicator.source = {'areas': {'road': {'called': 'the road'}}, 'facts': {
            'seen_1': {'area': 'road', 'visible': True, 'text': 'If you necessary.'},
            'dm_1': {'area': 'road', 'visible': True, 'text': 'If the bandits go unnoticed, they attack.'}}}
        adjudicator.perceivable = ('The caravan halts on the road beneath a leaning pine.', 'If you necessary.')
        line = adjudicator._miss_texture('I watch the road.', {'area': 'road'})
        self.assertEqual(line, 'Nothing moves that you can see. The caravan halts on the road beneath a leaning pine.')
        self.assertNotIn('necessary', line)
        self.assertNotIn('unnoticed', line)

    def test_live_bridge_reads_the_heard_read_aloud(self):
        case = Scene('run')
        case._start(LOW_SHEET)
        self.addCleanup(case.doCleanups)
        case.say('I look around.')
        heard = case.bridge.adjudicator.perceivable
        self.assertTrue(heard)
        self.assertTrue(all(line in FICTION for line in heard), heard)


class CachedOpeningStartsLikeACold(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(str(self.root), ignore_errors=True))
        self.pdf = self.root / 'book.pdf'
        self.pdf.write_bytes(make_pdf([
            [('text', 70, 735, '1. The Road', 11), ('text', 70, 700, FICTION, 9), ('text', 70, 660, ENCOUNTER, 9),
             ('text', 70, 620, CONDITION, 9)],
            [('text', 70, 735, '2. The Tower', 11), ('text', 70, 700, 'A bell rings at a distant tower.', 9)]]))

    def _seen(self, name, dirty_cache=False):
        """Every player-visible line in order: prepare, start, then Yes."""
        db = self.root / name / 'kit.sqlite'
        db.parent.mkdir()
        report = kit_prep.prepare(str(db), str(self.pdf), reader='pdftotext', root=str(self.root / 'cache'))
        seen = [report['table_line']]
        if not report['cached']:
            scene = copy.deepcopy(SCENE)
            scene['pressures'][0].update(quote=CONDITION, status='conditional', activation='failed_notice')
            accepted = kit_prep.after_skim(str(db), kit_skim.accept(db, {
                'burst': FICTION, 'source_quote': FICTION, 'page_start': 1, 'page_end': 1, 'alt_starts': [],
                'design_start_name': 'The Road', 'scene': scene}))
            self.assertEqual(accepted['stage'], 'skim_accepted')
            if dirty_cache:
                # The live cache carried one session's flags (an opening already spoken).
                clean = kit_skim._read(db)
                kit_skim._write(db, dict(clean, speak_now=True, burst_spoken=True))
                kit_prep.save(str(db), 'skim_accepted', str(self.root / 'cache'))
                kit_skim._write(db, clean)
        started = call('start', '--db', db, '--sheet', LOW_SHEET)
        seen.append(started.get('table_line') if started.get('awaiting_yes') else started.get('spoken'))
        action = db.parent / 'a.txt'
        action.write_text('Yes.')
        yes = call('prepare', '--one-pass', '--db', db, '--action-file', action)
        seen.append((yes.get('stage'), FICTION.split('.')[0] in str(yes.get('spoken'))))
        return seen

    def test_cold_and_cached_give_the_same_sequence(self):
        cold = self._seen('a', dirty_cache=True)
        self.assertEqual(cold, [kit_skim.LANDING, kit_skim.READY_LINE, ('opening_committed', True)])
        self.assertEqual(self._seen('b'), cold)


class OneCombatState(unittest.TestCase):
    def test_on_and_off(self):
        self.assertFalse(state_context.in_combat({}))
        self.assertTrue(state_context.in_combat({'combat': {'status': 'awaiting_initiative'}}))
        self.assertTrue(state_context.in_combat({'encounter': {'active': True}}))
        view = state_context.combat_view({'encounter': {'active': True, 'initiative': 'pending', 'since': 'x'}})
        self.assertTrue(view['on'] and view['initiative_pending'])
        self.assertIn('free', view['object_interaction'])
        self.assertEqual(state_context.combat_view({})['object_interaction'], 'just happens')

    def test_the_router_reads_it(self):
        routed = kit_router.route('observe', [], {'encounter': {'active': True, 'initiative': 'pending'}})
        self.assertNotEqual(routed['tier'], 'routine')
        self.assertTrue(any('in combat' in why and 'initiative pending' in why for why in routed['why']), routed)

    def test_object_cost_differs_by_it(self):
        self.assertEqual(kit_moves.object_acts('I draw my dagger and kick the stool into the fire.'), 2)
        adjudicator = RoomAdjudicator(roll=lambda: 10)
        calm = adjudicator._kit_ruling('I toss a stone into the left thicket.', {})
        self.assertEqual(calm.public_event, SIMPLE_ACT_LINE)
        fight = {'encounter': {'active': True}}
        one = adjudicator._kit_ruling('I toss a stone into the left thicket.', fight)
        self.assertEqual(one.public_event, SIMPLE_ACT_LINE)
        self.assertIn('free_object_interaction', one.events[0]['tags'])
        two = adjudicator._kit_ruling('I draw my dagger and kick the stool into the fire.', fight)
        self.assertIn('takes your action', two.public_event)


class RecordedFightReachesEveryTurn(Scene):
    def test_record_on_then_off(self):
        self._start(LOW_SHEET)
        from runtime.kit_agent import record_hand_beat
        record_hand_beat(self.runtime.path, {'happened': 'The bandits charge.', 'encounter': 'started'})
        result, _text = self.say('I wait by the cart.')
        self.assertTrue(result['combat']['on'], result.get('combat'))
        self.assertTrue(result['combat']['initiative_pending'])
        record_hand_beat(self.runtime.path, {'happened': 'The bandits flee.', 'encounter': 'ended'})
        result, _text = self.say('I wait by the cart.')
        self.assertNotIn('combat', result)


if __name__ == '__main__':
    unittest.main()


class InitiativeReadsTheCombatState(Scene):
    """v0.11.4: the initiative guard reads the one combat state, never the line."""

    def _resolve(self, line):
        from runtime.kit_agent import PendingRuling
        adjudicator = self.bridge.adjudicator
        adjudicator.mount(self.runtime.source())
        revision, state = self.runtime.load()
        with self.assertRaises(PendingRuling) as raised:
            adjudicator.resolve(line, revision, state)
        return str(raised.exception)

    def test_off_nobody_is_fighting(self):
        self._start(LOW_SHEET)
        self.assertIn('Nobody here is fighting you', self._resolve('I roll initiative: 14'))

    def test_recorded_encounter_initiative_is_pending(self):
        self._start(LOW_SHEET)
        from runtime.kit_agent import INITIATIVE_PENDING_LINE, record_hand_beat
        record_hand_beat(self.runtime.path, {'happened': 'The bandits charge.', 'encounter': 'started'})
        self.assertNotIn('combat', self.runtime.load()[1])  # no engine fight data
        said = self._resolve('I roll initiative: 14')
        self.assertEqual(said, INITIATIVE_PENDING_LINE)
        self.assertNotIn('Nobody', said)


class InitiativeNumberBindsWhileTheFightIsOn(Scene):
    """v0.11.5: through the host CLI, a number answers the pending initiative of a recorded fight."""

    def _session(self, started):
        self._start(LOW_SHEET)
        db = self.runtime.path
        folder = Path(db).parent
        if started:
            beat = folder / 'beat.json'
            beat.write_text(json.dumps({'happened': 'The bandits charge.', 'encounter': 'started'}))
            self.assertEqual(call('record', '--db', db, '--input-file', beat)['stage'], 'recorded')
        action = folder / 'a.txt'

        def prepare(line):
            action.write_text(line)
            return call('prepare', '--one-pass', '--db', db, '--action-file', action)
        return prepare

    def test_initiative_line_binds(self):
        result = self._session(True)('Initiative 14')
        self.assertEqual(result['stage'], 'initiative_rolled', result)
        self.assertNotIn('What is the', result['spoken'])
        self.assertIn('Initiative 14', result['spoken'])
        encounter = self.runtime.load()[1]['encounter']
        self.assertEqual((encounter['initiative'], encounter['initiative_total']), ('rolled', 14))

    def test_bare_number_binds(self):
        result = self._session(True)('14')
        self.assertEqual(result['stage'], 'initiative_rolled', result)
        self.assertNotIn('What is the', result['spoken'])

    def test_off_keeps_todays_reply(self):
        result = self._session(False)('14')
        self.assertEqual(result['stage'], 'roll_clarify', result)
        self.assertIn('What is the 14 for?', result['spoken'])
