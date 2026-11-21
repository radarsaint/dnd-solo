"""NPC attitudes, hidden NPC checks, the social-roll hook, story thresholds (issue #45, PR C).

Brendon's live 6c notes (2026-10-03): the dealer need not be oblivious to the PC reading the
backs; a watched deal must cover the dealer's own draws (T10: he dealt himself a second while
Nik read the top card, cheat_log watched=false); odd held gear with a hidden edge invites a
contested roll; a failed social roll changes the pace. Nik's post-stop turn (a quiet
accusation, Intimidation 1d20 (3) + 1 = 4) is "how we'd want players to play": the failed
roll moves the dealer's and the gang's attitude, and it is not a public exposure.
All dice are pinned (stated rolls, a fixed NPC d20, a fixed table seed)."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_agent, kit_attitude, kit_brief
from runtime.kit_agent import RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import FIXTURE

SOURCE = json.loads(FIXTURE.read_text())
NIK = json.loads((Path(__file__).parent / 'fixtures/characters/nik.json').read_text())
FEASIBILITY = json.loads((Path(__file__).parent / 'fixtures/feasibility_room.json').read_text())
GANG = ('uktarl', 'bandit_a', 'bandit_b', 'doppelganger')
T10 = "Nik reads the pricks on the top card and stands on fourteen: I'll stand."
ACCUSATION = ('Nik taps the top card, the one with the eight pricks, and leans in so only the dealer hears. '
              '"That card never left the top. You are dealing seconds. Slide my twenty back across and tell '
              'me what this game really is, and nobody else at this table needs to hear it." '
              'Intimidation: 1d20 (3) + 1 = `4`')
SEED = 'npc-attitude-0'


def shifts(events):
    return [event for event in events if event['type'] == 'attitude_shift']


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(self.runtime.close)
        self.runtime.initialize(copy.deepcopy(SOURCE), 'area_06c')
        self.runtime.set_player_sheet(NIK)
        self.turns = 0

    def commit(self, events):
        revision, _ = self.runtime.load()
        self.turns += 1
        self.runtime.commit(f'c{self.turns}', revision, events)

    def seat(self, **player):
        """A live twenty-one hand with the player seated (play mode, fixed seed)."""
        config = SOURCE['procedures']['twenty_one']
        table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 4, 'perception': 4}, SEED)
        _, state, _ = table.resolve('card_mode_play', 'I play it out.', 1, kit_cards.initial_state(config))
        state['public']['player'].update(player)
        self.commit([{'type': 'procedure_state', 'procedure': 'twenty_one', 'state': state,
                      'evidence': 'Test: a live hand.'}])

    def resolve(self, action, npc=10):
        revision, state = self.runtime.load()
        adjudicator = RoomAdjudicator(source=self.runtime.source(), roll=lambda: 10, npc_roll=lambda: npc)
        return adjudicator.resolve(action, revision, state)


class NiksQuietAccusation(Base):
    def test_social_failures_stop_at_unfriendly(self):
        # Only thresholds and combat reach hostile: two failed Persuasions leave the gang unfriendly.
        for turn in range(2):
            result = self.resolve('"Come on, friend, you can trust me." Persuasion: 1d20 (2) + 1 = `3`')
            self.assertEqual(result.kind, 'social_check')
            self.commit(list(result.events))
        state = self.runtime.load()[1]
        self.assertEqual({a: kit_attitude.level(SOURCE, state, a) for a in GANG}, {a: 'unfriendly' for a in GANG})

class TwoMoreRealTriggers(Base):
    """The prose halves of two 6c thresholds are triggers now: two wins running, and a big
    win after the dealer caught the visitor reading the backs."""

    def game(self):
        return copy.deepcopy(self.runtime.load()[1]['procedures']['twenty_one'])

    def set_game(self, game):
        self.commit([{'type': 'procedure_state', 'procedure': 'twenty_one', 'state': game, 'evidence': 'Test.'}])

    def won(self, wins, net):
        game = self.game()
        game['public']['player'].update(wins=wins, net=net)
        game['public']['last_result'] = {'round': wins, 'outcome': 'win', 'stake': 20}
        self.set_game(game)

    def notice(self):
        self.seat()
        self.commit(shifts(self.resolve(T10, npc=18).events))

    def crossing(self):
        return kit_brief.brief(SOURCE, self.runtime.load()[1])['thresholds'][1].get('crossing_now')

    def test_the_cap_keeps_every_crossing_threshold(self):
        made = {'endings': ['e'], 'purposes': [{'what': 'p', 'for': 'q'}], 'present': [],
                'thresholds': [{'when': 'a', 'then': 'b', 'crossing_now': True}, {'when': 'x' * 5200, 'then': 'y'},
                               {'when': 'c', 'then': 'd', 'crossing_now': True}, {'when': 'z' * 5200, 'then': 'y'}]}
        capped = kit_brief._capped(made)
        self.assertEqual([t['when'] for t in capped['thresholds']], ['a', 'c'])


class GeneralMechanism(unittest.TestCase):
    """Non-6c: the feasibility room with its own attitudes block and threshold."""

    def source(self, **extra):
        source = copy.deepcopy(FEASIBILITY)
        source['attitudes'] = {'start': {'sentry': 'friendly'},
                               'groups': {'watch': {'members': ['sentry', 'hidden_watcher']}}, **extra}
        return source

    def test_the_social_roll_hook_moves_the_target_and_a_following_group(self):
        source = self.source()
        state = {'area': 'entry', 'actors': copy.deepcopy(source['actors'])}
        [failed] = kit_attitude.social_roll(source, state, 'sentry', 'deception', False, 'Deception 4 vs 12.')
        self.assertEqual({s['actor']: s['to'] for s in failed['shifts']},
                         {'sentry': 'indifferent', 'hidden_watcher': 'unfriendly'})
        [won] = kit_attitude.social_roll(source, state, 'sentry', 'persuasion', True, 'Persuasion 18 vs 12.')
        self.assertEqual(won['shifts'], [{'actor': 'sentry', 'from': 'friendly', 'to': 'helpful'}])
        self.assertEqual(kit_attitude.social_roll(source, state, 'sentry', 'intimidation', True, 'x'), [])
        self.assertEqual(kit_attitude.moved('hostile', -3), 'hostile')
        self.assertEqual(kit_attitude.moved('friendly', 0, to='hostile'), 'hostile')

    def test_bad_blocks_are_refused_at_load(self):
        for bad in ({'start': {'sentry': 'furious'}}, {'groups': {'g': {'members': ['nobody']}}},
                    {'npc_checks': {'x': {'trigger': 'mind_read', 'by': ['sentry'], 'skill': 'insight',
                                          'vs': 'deception', 'note': 'n'}}}):
            with self.subTest(bad=bad), self.assertRaises(InvalidChange):
                kit_attitude.compile_attitudes({**FEASIBILITY, 'attitudes': bad})
        with tempfile.TemporaryDirectory() as temp:
            runtime = Runtime(Path(temp) / 'k.sqlite')
            self.addCleanup(runtime.close)
            with self.assertRaises(InvalidChange):
                runtime.initialize({**copy.deepcopy(FEASIBILITY), 'attitudes': {'start': {'sentry': 'x'}}}, 'entry')

    def test_a_threshold_on_attitude_crosses_in_any_room(self):
        source = self.source()
        source['story'] = {'entry': {'thresholds': [{
            'when': 'The sentry turns unfriendly.', 'then': 'He calls the watch.', 'roots': ['sentry'],
            'trigger': {'attitude_at_most': {'actor': 'sentry', 'level': 'unfriendly'}},
            'shift': {'actors': ['hidden_watcher'], 'to': 'hostile'}}]}}
        state = {'area': 'entry', 'actors': copy.deepcopy(source['actors'])}
        self.assertEqual(kit_brief.threshold_events(source, state, 't'), [])
        state['attitudes'] = {'sentry': {'level': 'unfriendly', 'history': []}}
        crossed, shift = kit_brief.threshold_events(source, state, 't')
        self.assertEqual(crossed['index'], 0)
        self.assertEqual(shift['shifts'], [{'actor': 'hidden_watcher', 'from': 'indifferent', 'to': 'hostile'}])
        bad = copy.deepcopy(source)
        bad['story']['entry']['thresholds'][0]['shift'] = {'actors': ['sentry'], 'by': 1, 'to': 'hostile'}
        with self.assertRaises(InvalidChange):
            kit_brief.compile_story(bad)

    def test_sitting_down_or_stowing_gear_is_not_a_physical_ruling(self):
        for action in ('I sling my shield onto my back and take the seat.', 'Mira takes the empty chair.',
                       'I set my staff aside and sit down.'):
            with self.subTest(action=action):
                self.assertEqual(kit_agent.room_intent(action), 'social')
        self.assertEqual(kit_agent.room_intent('I grab the ring.'), 'unsupported_action')


if __name__ == '__main__':
    unittest.main()
