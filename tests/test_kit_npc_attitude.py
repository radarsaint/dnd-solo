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

from runtime import kit_agent, kit_attitude, kit_brief, kit_cards, kit_twenty_one
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


class HiddenNpcChecks(Base):
    def test_reading_the_backs_gets_a_hidden_dealer_perception_that_moves_him(self):
        self.seat()
        result = self.resolve(T10, npc=18)  # dealer Perception +0: 18 vs Nik's passive Sleight of Hand 17
        [moved] = shifts(result.events)
        self.assertEqual(moved['check']['id'], 'dealer_sees_reading')
        self.assertTrue(moved['check']['success'])
        self.assertEqual(moved['shifts'], [{'actor': 'uktarl', 'from': 'indifferent', 'to': 'unfriendly'}])
        self.assertIn('Behind the screen', moved['evidence'])
        for word in ('perception', 'd20', 'behind', 'notice', 'wary'):
            self.assertNotIn(word, result.public_event.casefold())
        self.commit(list(result.events))
        state = self.runtime.load()[1]
        self.assertEqual(kit_attitude.level(SOURCE, state, 'uktarl'), 'unfriendly')
        here = self.runtime.context()['dm_context']['dm_only']['attitudes_here']
        self.assertEqual(here['uktarl']['attitude'], 'unfriendly')
        self.assertIn('reading the backs', here['uktarl']['moved_by'])
        # Once per scene: the dealer does not roll again on the next read.
        self.seat()
        self.assertEqual(shifts(self.resolve(T10, npc=20).events), [])

    def test_a_missed_check_re_arms_with_a_rising_chance(self):
        # Call 10 ("repeatedly"): a miss is not spent for the scene; the next read rolls again,
        # +2 per earlier miss, until the dealer notices. Then it stays noticed.
        self.seat()
        result = self.resolve(T10, npc=1)  # T10's behind-screen roll: a natural 1
        [missed] = shifts(result.events)
        self.assertFalse(missed['check']['success'])
        self.assertEqual(missed['shifts'], [])
        self.commit(list(result.events))
        state = self.runtime.load()[1]
        self.assertEqual(kit_attitude.level(SOURCE, state, 'uktarl'), 'indifferent')
        self.assertEqual(state['npc_checks']['scene-1/area_06c']['dealer_sees_reading']['misses'], 1)
        self.seat()
        again = shifts(self.resolve(T10, npc=15).events)[0]  # 15 + 0 + 2 = 17 vs passive 17
        self.assertTrue(again['check']['success'])
        self.assertIn('+2 for 1 earlier misses', again['evidence'])
        self.commit([again])
        self.seat()
        self.assertEqual(shifts(self.resolve(T10, npc=20).events), [])

    def test_a_new_scene_re_arms_a_noticed_check(self):
        self.seat()
        self.commit(shifts(self.resolve(T10, npc=18).events))
        state = copy.deepcopy(self.runtime.load()[1])
        adjudicator = RoomAdjudicator(source=SOURCE, roll=lambda: 10, npc_roll=lambda: 18)
        self.assertEqual(shifts(adjudicator.resolve(T10, 99, state).events), [])
        state['scene_id'] = 'scene-2'  # KRABS §8 scene ids (#59): a later scene in the same room
        self.assertEqual(len(shifts(adjudicator.resolve(T10, 99, state).events)), 1)

    def test_holding_gear_with_a_hidden_edge_at_the_table_is_contested(self):
        self.seat()
        self.runtime.set_pc_state(held=['Sentinel Shield'])
        result = self.resolve('"Another round, then." Nik rests his hand on the shield at his side.', npc=19)
        [moved] = shifts(result.events)
        self.assertEqual((moved['check']['id'], moved['check']['by']), ('table_sees_held_edge', 'bandit_b'))
        self.assertEqual({s['actor'] for s in moved['shifts']}, {'uktarl', 'bandit_b'})
        # Set aside (the seated default), there is no edge to hide and no check.
        self.runtime.set_pc_state(held=[])
        self.assertEqual(shifts(self.resolve('"Another round, then."', npc=19).events), [])

    def test_a_missed_gear_check_waits_for_the_next_round(self):
        self.seat()
        self.runtime.set_pc_state(held=['Sentinel Shield'])
        self.commit(shifts(self.resolve('"Another round, then."', npc=1).events))
        self.assertEqual(shifts(self.resolve('"Still thinking."', npc=19).events), [])  # same round
        game = copy.deepcopy(self.runtime.load()[1]['procedures']['twenty_one'])
        game['public']['rounds_played'] += 1
        self.commit([{'type': 'procedure_state', 'procedure': 'twenty_one', 'state': game, 'evidence': 'Test.'}])
        [again] = shifts(self.resolve('"Deal me in."', npc=17).events)  # 17 + 0 + 2 = 19 vs 17
        self.assertTrue(again['check']['success'])

    def test_the_watch_covers_the_dealers_own_draws(self):
        config = SOURCE['procedures']['twenty_one']
        for seed in (f'{SEED}:{n}' for n in range(200)):
            table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 4, 'perception': 4}, seed,
                                                  passives={'perception': 14})
            _, live, _ = table.resolve('card_mode_play', 'I play it out.', 1, kit_cards.initial_state(config))
            if live['public']['round']['phase'] != 'play':
                continue
            text, after, reveals = table.resolve('card_stand', T10, 2, live)
            log = [e for e in after['private']['cheat_log'] if e.get('draw') == 'dealer']
            if log:
                break
        else:
            self.fail('no seed dealt a second on the dealer\'s draw')
        self.assertTrue(log[0]['watched'] and log[0]['caught'])
        self.assertTrue(after['public']['round']['cheat_seen'])
        self.assertEqual(reveals, [config['cheat']['reveals_fact']])
        self.assertIn(config['cheat']['caught_text'], text)
        # The same stand without eyes on the deck: he deals the second unseen.
        _, unseen, reveals = table.resolve('card_stand', "I'll stand.", 2, live)
        self.assertFalse([e for e in unseen['private']['cheat_log'] if e.get('draw') == 'dealer'])
        self.assertEqual(reveals, [])
        self.assertTrue(unseen['private']['cheated'])
        # Caught, the call on the settled hand is backed in front of the table.
        call, called, _ = table.resolve('card_accuse', 'You dealt yourself the second!', 3, after)
        self.assertIn('saw the second deal', call)
        self.assertTrue(called['public']['accusations'][-1]['backed'])


class NiksQuietAccusation(Base):
    def test_a_quiet_accusation_with_a_failed_intimidation_moves_the_gang_privately(self):
        self.seat()
        result = self.resolve(ACCUSATION, npc=1)
        self.assertEqual(result.kind, 'social_check')
        beat = result.events[0]
        self.assertIn('private_accusation', beat['tags'])
        self.assertIn('d20 3 + 1 = 4', beat['evidence'])
        self.assertIn('failure', beat['evidence'])
        social = [e for e in shifts(result.events) if 'check' not in e]
        self.assertEqual(len(social), 1)
        self.assertEqual({s['actor']: s['to'] for s in social[0]['shifts']}, {a: 'unfriendly' for a in GANG})
        self.assertNotIn('procedure_state', [e['type'] for e in result.events])
        self.commit(list(result.events))
        state = self.runtime.load()[1]
        public = state['procedures']['twenty_one']['public']
        self.assertFalse(public.get('accusations'))  # not the table's public call
        self.assertEqual(public['table_mood'], 'open')
        made = kit_brief.brief(SOURCE, state)
        self.assertFalse(made['thresholds'][1].get('crossing_now'))  # "exposes the cheat publicly"
        self.assertEqual(kit_brief.threshold_events(SOURCE, state, 't'), [])

    def test_social_failures_stop_at_unfriendly(self):
        # Only thresholds and combat reach hostile: two failed Persuasions leave the gang unfriendly.
        for turn in range(2):
            result = self.resolve('"Come on, friend, you can trust me." Persuasion: 1d20 (2) + 1 = `3`')
            self.assertEqual(result.kind, 'social_check')
            self.commit(list(result.events))
        state = self.runtime.load()[1]
        self.assertEqual({a: kit_attitude.level(SOURCE, state, a) for a in GANG}, {a: 'unfriendly' for a in GANG})

    def test_said_out_loud_it_is_still_the_tables_accusation(self):
        self.seat()
        loud = ACCUSATION.replace('leans in so only the dealer hears', 'stands up').replace(
            ', and nobody else at this table needs to hear it', '')
        result = self.resolve(loud, npc=1)
        self.assertNotEqual(result.kind, 'social_check')


class StoryThresholds(Base):
    def test_a_threshold_crosses_once_and_moves_the_named_npcs(self):
        self.seat(net=30)
        state = self.runtime.load()[1]
        made = kit_brief.brief(SOURCE, state)
        self.assertTrue(made['thresholds'][0]['crossing_now'])
        events = kit_brief.threshold_events(SOURCE, state, 't1')
        self.assertEqual([e['type'] for e in events], ['threshold_crossed', 'attitude_shift'])
        self.assertEqual({s['actor'] for s in events[1]['shifts']}, {'uktarl', 'bandit_b'})
        self.commit(events)
        state = self.runtime.load()[1]
        self.assertTrue(kit_brief.brief(SOURCE, state)['thresholds'][0]['crossed'])
        self.assertEqual(kit_brief.threshold_events(SOURCE, state, 't2'), [])
        self.assertEqual(kit_attitude.level(SOURCE, state, 'bandit_b'), 'unfriendly')

    def test_exposure_turns_the_table_hostile(self):
        self.seat()
        revision, state = self.runtime.load()
        game = copy.deepcopy(state['procedures']['twenty_one'])
        game['public']['accusations'] = [{'round': 1, 'backed': True}]
        self.commit([{'type': 'procedure_state', 'procedure': 'twenty_one', 'state': game, 'evidence': 'Test.'}])
        events = kit_brief.threshold_events(SOURCE, self.runtime.load()[1], 't')
        self.assertEqual({s['to'] for s in events[-1]['shifts']}, {'hostile'})


class TwoMoreRealTriggers(Base):
    """The prose halves of two 6c thresholds are triggers now: two wins running, and a big
    win after the dealer caught the visitor reading the backs."""

    def game(self):
        return copy.deepcopy(self.runtime.load()[1]['procedures']['twenty_one'])

    def set_game(self, game):
        self.commit([{'type': 'procedure_state', 'procedure': 'twenty_one', 'state': game, 'evidence': 'Test.'}])

    def test_two_wins_running_cross_the_first_threshold(self):
        config = SOURCE['procedures']['twenty_one']
        table = kit_twenty_one.TwentyOneTable('twenty_one', config, {'insight': 4, 'perception': 4}, SEED)
        game = kit_cards.initial_state(config)
        game['public']['player'] = {'net': 0, 'purse': None, 'unwelcome': False}
        game['public']['round'] = {'number': 1, 'mode': 'play', 'stake': 10, 'toll': False, 'phase': 'play'}
        table._settle(game['public'], game['private'], 'win')
        self.assertEqual(game['public']['player']['streak'], 1)
        self.set_game(game)
        self.assertFalse(kit_brief.brief(SOURCE, self.runtime.load()[1])['thresholds'][0].get('crossing_now'))
        game['public']['round'] = {'number': 2, 'mode': 'play', 'stake': 5, 'toll': False, 'phase': 'play'}
        table._settle(game['public'], game['private'], 'push')
        game['public']['round'] = {'number': 3, 'mode': 'play', 'stake': 5, 'toll': False, 'phase': 'play'}
        table._settle(game['public'], game['private'], 'win')
        self.assertEqual((game['public']['player']['streak'], game['public']['player']['net']), (2, 15))
        self.set_game(game)
        crossed = kit_brief.threshold_events(SOURCE, self.runtime.load()[1], 't')
        self.assertEqual(crossed[0]['index'], 0)  # under 30 gp up, on the run alone
        table._settle(game['public'], game['private'], 'lose')
        self.assertEqual(game['public']['player']['streak'], 0)

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

    def test_one_big_win_after_being_caught_does_not_turn_the_table(self):
        self.notice()
        self.won(1, 20)  # one 20 gp win: not "keeps winning"
        self.assertFalse(self.crossing())
        self.assertEqual(kit_brief.threshold_events(SOURCE, self.runtime.load()[1], 't'), [])

    def test_two_wins_or_30_gp_since_being_caught_do(self):
        self.notice()
        self.won(2, 5)  # two wins since, up overall
        self.assertTrue(self.crossing())
        events = kit_brief.threshold_events(SOURCE, self.runtime.load()[1], 't')
        self.assertEqual(events[0]['index'], 1)
        self.assertEqual({s['actor']: s['to'] for s in events[1]['shifts']}, {'uktarl': 'hostile', 'bandit_b': 'hostile'})
        self.won(1, 30)  # or 30 gp up since, in one win and some luck
        self.assertTrue(self.crossing())

    def test_wins_from_before_anyone_noticed_do_not_count(self):
        self.seat()
        self.won(3, 45)
        self.assertFalse(self.crossing())  # nobody noticed
        self.commit(shifts(self.resolve(T10, npc=18).events))  # noticed now, at 3 wins / +45
        self.assertFalse(self.crossing())
        self.won(4, 55)
        self.assertFalse(self.crossing())  # one more win, +10 since
        self.won(5, 65)
        self.assertTrue(self.crossing())

    def test_broke_uses_the_sheets_gold_without_a_buy_in(self):
        self.seat(net=-NIK['gold_gp'])
        self.assertTrue(kit_brief.holds({'broke': 'twenty_one'}, SOURCE, self.runtime.load()[1]))
        self.seat(net=-10)
        self.assertFalse(kit_brief.holds({'broke': 'twenty_one'}, SOURCE, self.runtime.load()[1]))

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
