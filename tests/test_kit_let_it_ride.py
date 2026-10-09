"""PR-L: Let It Ride. An established check result persists while the PC keeps at the same
endeavor; the engine calls a new roll only when circumstances materially change (new
observers, a new area, a different approach, a complication), and the player rolls it in
Avrae. The engine never silently rolls a PC's check. Watchroom fixture plus synthetic
variants of it (no 6c); dice pinned; no model."""
import copy
import json
import re
import unittest
from pathlib import Path

from runtime import kit_agent
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from test_kit_room_review import ROOT, WATCH
from test_kit_watchroom_stalls import Stalls

ESTABLISH = 'I creep along the wall, keeping to the shadows. Stealth check: 1d20 (20) + 2 = 22'
CONTINUE = 'I keep creeping along the same wall'


def events_of(result, kind):
    return [e for e in result.events if e.get('type') == kind]


class Ride(Stalls):
    room = WATCH

    def setUp(self):
        super().setUp()
        if self.room != WATCH:
            self.runtime = self.start(self.room)
            self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))

    def live(self, roll=None):
        """The live adjudicator: no host pin on the PC's d20 (players roll in Avrae)."""
        return RoomAdjudicator(roll=roll, npc_roll=lambda: 10, source=self.runtime.source())

    def act(self, line, roll=None, commit=True):
        revision, state = self.runtime.load()
        result = self.live(roll).resolve(line, revision, state)
        if commit:
            self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    def standing(self):
        return self.runtime.load()[1].get('standing_check')

    def establish(self):
        self.go_in()
        result = self.act(ESTABLISH)
        self.assertEqual(result.kind, 'stealth')
        self.assertIn('22', ' '.join(e.get('evidence', '') for e in result.events))
        held = self.standing()
        self.assertEqual((held['skill'], held['total'], held['area']), ('stealth', 22, 'watchroom'))
        self.assertEqual(held['against']['watchers'], ['warden'])
        return result

    def assert_called_not_rolled(self, result):
        self.assertEqual(result.kind, 'check_called')
        pending = events_of(result, 'pending_check')
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['check']['skill'], 'stealth')
        self.assertNotRegex(' '.join(e.get('evidence', '') for e in result.events), r'd20 \d+')
        self.assertIn('roll', result.public_event.casefold())


class Continuation(Ride):
    def test_the_22_stands_while_he_keeps_creeping(self):
        self.establish()
        # A host pin that would make any reroll a 1 (1 + 2 = 3 fails): the standing 22 is used.
        result = self.act(CONTINUE, roll=lambda: 1)
        self.assertEqual(result.kind, 'stealth')
        text = ' '.join(e.get('evidence', '') for e in result.events)
        self.assertIn('stands', text)
        self.assertIn('22', text)
        self.assertNotRegex(text, r'd20 1\b')
        self.assertFalse(events_of(result, 'pending_check'))
        self.assertEqual(self.standing()['total'], 22)
        again = self.act(CONTINUE + ', step by step.')
        self.assertEqual(again.kind, 'stealth')
        self.assertEqual(self.standing()['total'], 22)

    def test_kit_sees_the_standing_result_in_the_packet(self):
        self.establish()
        packet = self.bridge.prepare(CONTINUE, 'k', one_pass=True)
        standing = packet['input']['private']['standing_check']
        self.assertEqual((standing['skill'], standing['total']), ('stealth', 22))
        self.assertIn('ride', standing['rule'].casefold())

    def test_a_called_stealth_check_establishes_the_result(self):
        self.go_in()
        revision, _ = self.runtime.load()
        self.runtime.commit('call', revision, [{'type': 'pending_check', 'evidence': 'Kit called Stealth.', 'check': {
            'skill': 'stealth', 'ability': 'dex', 'target': 'warden', 'called_turn': 'k1'}}])
        self.act('Stealth check: 1d20 (20) + 2 = 22')
        self.assertEqual(self.standing()['total'], 22)


class ChangedCircumstances(Ride):
    def test_a_different_approach_calls_a_fresh_roll(self):
        self.establish()
        result = self.act('I stop creeping and sprint along the wall, stealthily as I can.')
        self.assert_called_not_rolled(result)
        self.assertIsNone(self.standing())

    def test_a_fight_is_a_complication(self):
        self.establish()
        revision, state = self.runtime.load()
        changed = copy.deepcopy(state)
        changed['combat'] = {'status': 'running', 'round': 1}
        result = self.live().resolve(CONTINUE, revision, changed)
        self.assert_called_not_rolled(result)

    def test_the_player_rolls_the_new_check_and_it_counts(self):
        self.establish()
        self.act('I stop creeping and sprint along the wall, stealthily as I can.')
        result = self.act('Stealth check: 1d20 (7) + 2 = 9')
        self.assertEqual(result.kind, 'stealth')
        self.assertIn('d20 7 + 2 = 9', ' '.join(e.get('evidence', '') for e in result.events))
        self.assertIsNone(self.standing())  # 9 is seen by a passive 10: the attempt is over


class Synthetic(Ride):
    """The watchroom with a sleeping second guard and a lookout down the back stair."""

    def setUp(self):
        source = json.loads((ROOT / WATCH).read_text())
        source['actors']['sleeper'] = dict(copy.deepcopy(source['actors']['warden']), name='Sleeping guard',
                                           status='unconscious', guards=[])
        source['actors']['lookout'] = dict(copy.deepcopy(source['actors']['warden']), name='Stair lookout',
                                           location='stair_down', guards=[])
        self.room = None
        super().setUp()
        self.runtime = self.start(str(self.write(source)))
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))

    def test_a_guard_who_wakes_is_a_new_observer(self):
        self.establish()  # the sleeping guard does not watch: only the warden counts
        revision, _ = self.runtime.load()
        self.runtime.commit('wake', revision, [{'type': 'actor_status', 'actor': 'sleeper', 'status': 'alive',
                                                'evidence': 'The sleeping guard wakes.'}])
        result = self.act(CONTINUE)
        self.assert_called_not_rolled(result)
        self.assertIn('Sleeping guard', result.public_event)
        self.assertIsNone(self.standing())

    def test_a_new_area_calls_a_fresh_roll(self):
        self.establish()
        revision, state = self.runtime.load()
        events = [] if 'back_stair' in state['known_exits'] else [
            {'type': 'reveal_exit', 'exit': 'back_stair', 'evidence': 'Seen.'}]
        self.runtime.commit('down', revision, events + [{'type': 'move', 'exit': 'back_stair', 'evidence': 'Down.'}])
        self.assertIsNone(self.standing())  # leaving the area ends the attempt
        self.assert_called_not_rolled(self.act(CONTINUE))


class TheAttemptEnds(Ride):
    def test_speaking_up_ends_it(self):
        self.establish()
        self.act('"Evening," I say to the warden, straightening up.')
        self.assertIsNone(self.standing())

    def test_a_failed_roll_ends_it(self):
        self.go_in()
        self.act('I creep along the wall. Stealth check: 1d20 (3) + 2 = 5')
        self.assertIsNone(self.standing())


class NoSilentPcRolls(Ride):
    def test_a_first_attempt_without_a_roll_is_called_not_rolled(self):
        self.go_in()
        result = self.act('I creep along the wall, keeping to the shadows.')
        self.assert_called_not_rolled(result)
        self.assertEqual(events_of(result, 'pending_check')[0]['check']['action'],
                         'I creep along the wall, keeping to the shadows.')
        rolled = self.act('Stealth check: 1d20 (18) + 2 = 20')
        self.assertEqual(rolled.kind, 'stealth')
        self.assertEqual(self.standing()['total'], 20)

    def test_the_engine_has_no_seeded_pc_roll_left(self):
        """Every hash-seeded d20 left in the runtime is an NPC's (Kit rolls those behind the
        screen) or a card procedure's (listed, not yet moved to Avrae)."""
        allowed = {('kit_combat.py', 'die'), ('kit_attitude.py', 'npc_die'),
                   ('kit_cards.py', '_d20'), ('kit_cards.py', '_player_roll'),
                   ('kit_twenty_one.py', '_roll')}
        found = set()
        for path in sorted((ROOT / 'runtime').glob('*.py')):
            current = None
            for line in path.read_text().splitlines():
                head = re.match(r'\s*def (\w+)', line)
                if head:
                    current = head.group(1)
                if '% 20 + 1' in line or re.search(r'\b_d20\(', line) and not line.lstrip().startswith('def'):
                    found.add((path.name, current))
        self.assertLessEqual(found, allowed)
        self.assertNotIn(('kit_agent.py', '_die'), found)


if __name__ == '__main__':
    unittest.main()
