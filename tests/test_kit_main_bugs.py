"""Bugs still on main after PR 145 (/workspace/kit2/pr145-bugs.md), fixed in the PR stacked on
#150. Watchroom fixture, dice pinned, no model."""
import json
import unittest
import unittest.mock

from runtime import kit_agent, kit_rooms
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator
from runtime.state_context import InvalidChange, Runtime, encode
from test_kit_watchroom_stalls import Stalls


def find(node, key):
    """Every value under `key` anywhere in a packet."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from find(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from find(v, key)


class HiddenFactsArriveOnTheEntryTurn(Stalls):
    def test_entry_turn_carries_the_rooms_hidden_facts(self):
        packet = self.bridge.prepare('I go through the iron door.', 'in', one_pass=True)
        hidden = set()
        for facts in find(packet, 'unrevealed_facts'):
            hidden |= set(facts)
        self.assertIn('chest_contents', hidden)
        self.assertNotIn('humming', hidden)

    def test_a_turn_without_a_move_is_unchanged(self):
        packet = self.bridge.prepare('I wait on the landing and listen.', 'l', one_pass=True)
        hidden = set()
        for facts in find(packet, 'unrevealed_facts'):
            hidden |= set(facts)
        self.assertNotIn('chest_contents', hidden)


class EntryActsAndPeeks(Stalls):
    """Item 2: an act declared on entry survives; 'not going in yet' is not entering."""

    def test_an_act_on_entry_is_kept(self):
        result = self.resolve(self.runtime, 'I step through the iron door and search the chest.')
        self.assertEqual(result.events[0]['type'], 'move')
        self.assertEqual(result.kind, 'check_request')  # the search on entry is a bid for a check

    def test_not_going_in_is_a_look(self):
        for line in ("I'm not going in yet, just peeking through the door.",
                     "Not going in yet, I look through the doorway.",
                     "I don't step in; I just peek through the door gap."):
            with self.subTest(line):
                result = self.resolve(self.runtime, line)
                self.assertEqual(result.kind, 'threshold_look')
                self.assertNotIn('move', [e['type'] for e in result.events])


class BackToTheDoorIsAPosition(Stalls):
    """Item 3: backing up to a doorway is a position the state keeps until the PC moves."""

    def commit(self, line, turn):
        result = self.resolve(self.runtime, line)
        revision, _ = self.runtime.load()
        self.runtime.commit(turn, revision, result.events)
        return result

    def test_backing_up_sets_and_a_move_clears_the_position(self):
        self.go_in()
        for line in ('I back up to the doorway and look around.', 'I step back to the door and listen.'):
            with self.subTest(line):
                self.commit(line, 'b' + str(len(line)))
                self.assertEqual(self.runtime.load()[1]['pc_position']['at_exit'], 'iron_door')
        revision, _ = self.runtime.load()
        self.runtime.commit('out', revision, [{'type': 'move', 'exit': 'iron_door', 'evidence': 'Out.'}])
        self.assertNotIn('pc_position', self.runtime.load()[1])

    def test_a_plain_look_sets_no_position(self):
        self.go_in()
        result = self.resolve(self.runtime, 'I look around the room.')
        self.assertNotIn('pc_position', [e['type'] for e in result.events])

    def test_a_position_needs_an_adjacent_exit(self):
        revision, _ = self.runtime.load()
        with self.assertRaises(InvalidChange):
            self.runtime.commit('x', revision, [{'type': 'pc_position', 'at_exit': 'back_stair', 'evidence': 'x'}])


class ShieldUpIsHeld(unittest.TestCase):
    """Item 4: 'Shield up.' puts the shield in hand for this turn's roll."""

    def test_declared_held(self):
        from runtime.kit_agenda import declared_held
        for line in ('Shield up.', 'I raise my shield and advance.', 'Shield ready, I step in.',
                     'I hold my shield in front of me.'):
            with self.subTest(line):
                self.assertTrue(declared_held(line, 'Shield'))
        for line in ('I sling my shield on my back.', 'Shield down, I listen.', 'I look at my shield.',
                     'Sword up.'):
            with self.subTest(line):
                self.assertFalse(declared_held(line, 'Shield'))

    def test_an_item_cause_accepts_the_declared_shield(self):
        from runtime.kit_agenda import check_roll_call
        call = {'skill': 'athletics', 'mode': 'advantage', 'cause': {'kind': 'item', 'ref': 'Shield'}}
        state = {'area': 'a', 'actors': {}, 'player_sheet': {'equipment': ['Shield']}}
        with self.assertRaises(InvalidChange):
            check_roll_call(call, {'facts': {}}, state, action='I shove the door.')
        check_roll_call(call, {'facts': {}}, state, action='Shield up. I shove the door.')


class RollOutcome(unittest.TestCase):
    """Item 5: ties go to the actor on a check; a save that only ties the DC fails."""

    def test_rules(self):
        from runtime.kit_rolls import roll_outcome
        self.assertEqual(roll_outcome(15, 15), 'pass')
        self.assertEqual(roll_outcome(14, 15), 'fail')
        self.assertEqual(roll_outcome(16, 15), 'pass')
        self.assertEqual(roll_outcome(15, 15, save=True), 'fail')
        self.assertEqual(roll_outcome(16, 15, save=True), 'pass')


class CalledCheckOutcome(Stalls):
    """Items 5 and 8: Kit's DC gives her a private pass/fail; the DC never goes public; the
    recap keeps the call and the raw roll (advantage die included)."""

    def call(self, dc, turn='call'):
        packet = self.bridge.prepare('Can I make a check?', turn, one_pass=True)
        plan = self.plan_for(packet, move='ruling', table_presence='brief', roll_call={
            'skill': 'stealth', 'mode': 'normal', 'target': 'warden', 'dc': dc,
            'cause': {'kind': 'position', 'ref': 'none', 'roots': []}})
        plan['public_brief'].update(reply_to='Can I make a check', scope='call')
        self.bridge.complete(turn, {'decision': plan, 'performance': {'segments': [
            {'speaker': 'Kit', 'text': 'Make a Dexterity (Stealth) check.', 'reacts_to': 'Can I make a check'}]}})

    def outcome(self, dc):
        self.call(dc)
        self.assertEqual(self.runtime.load()[1]['pending_check']['dc'], dc)
        packet = self.bridge.prepare('Stealth check: 1d20 (13) + 2 = 15', 'r', one_pass=True)
        return packet

    def test_pass_fail_and_tie(self):
        for dc, want in ((12, 'pass'), (15, 'pass'), (16, 'fail')):
            with self.subTest(dc=dc):
                self.setUp()
                packet = self.outcome(dc)
                self.assertEqual(next(find(packet, 'check_outcome'))['result'], want)

    def test_a_failed_or_passed_called_check_reveals_nothing_unclaimed(self):
        for dc, tag in ((16, 'fail'), (12, 'pass')):
            with self.subTest(dc=dc):
                self.setUp()
                self.call(dc)
                result = self.resolve(self.runtime, 'Stealth check: 1d20 (13) + 2 = 15')
                self.assertIn(tag, result.events[0]['tags'])
                self.assertNotIn('reveal_fact', [e['type'] for e in result.events])
                self.assertNotIn(str(dc), result.public_event)

    def test_dc_never_public(self):
        packet = self.outcome(17)
        public = encode(packet['input'].get('public') or {}) + encode(packet.get('player_view') or {})
        self.assertNotIn('DC', public)
        self.assertNotIn('"dc"', public)

    def test_no_dc_no_outcome(self):
        packet = self.bridge.prepare('I wait.', 'w', one_pass=True)
        self.assertEqual(list(find(packet, 'check_outcome')), [])

    def test_recap_keeps_the_call(self):
        self.call(12)
        rhythm = self.runtime.load()[1]['rhythm']
        self.assertTrue(any('waiting on the roll' in encode(entry) for entry in rhythm))


class RecapKeepsTheAdvantageDie(CalledCheckOutcome):
    """Item 8: the evidence keeps the stated roll, both advantage dice included.
    (Item 7, no engine echo, is pinned in test_kit_watchroom_stalls and test_kit_hardening.)"""

    def test_the_stated_roll_keeps_both_dice(self):
        self.call(12)
        packet = self.bridge.prepare('Stealth check with advantage: 2d20kh1 (4, 13) + 2 = 15', 'r', one_pass=True)
        self.assertIn('(4, 13)', encode(packet['input']['private']))


class GrantedShieldTraining(unittest.TestCase):
    """Item 9: a ruling that granted shield training adds the shield to AC."""

    def test_armor_class(self):
        from runtime.pc_sheet import armor_class
        base = {'ac': 13, 'held': ['Shield']}
        self.assertEqual(armor_class(base), 13)
        self.assertEqual(armor_class({**base, 'proficiency_sources': {'Shield': 'ruling t4'}}), 15)
        self.assertEqual(armor_class({**base, 'proficiency_sources': {'Shield': 'r'}, 'ac_counts_shield': True}), 13)
        self.assertEqual(armor_class({'ac': 13, 'proficiency_sources': {'Shield': 'r'}}), 13)


class RoomReload(Stalls):
    """Item 10: an edited room file reloads mid-game, keeping progress."""

    def edited(self, change):
        source = json.loads(encode(self.runtime.source()))
        change(source)
        return source

    def test_reload_keeps_progress_and_adds_the_edit(self):
        self.go_in()
        before = self.runtime.load()[1]
        self.runtime.db.execute('DELETE FROM kit_pending')
        source = self.edited(lambda s: s['facts'].__setitem__('scratch', {
            'area': 'watchroom', 'visible': True, 'text': 'Fresh scratches by the chest.'}))
        revision = self.runtime.reload_room(source)
        self.assertIsNotNone(revision)
        state = self.runtime.load()[1]
        self.assertEqual(state['area'], 'watchroom')
        self.assertIn('scratch', state['known_facts'])
        self.assertEqual(state['kit'], before['kit'])
        self.assertIn('scratch', self.runtime.source()['facts'])
        self.assertIsNone(self.runtime.reload_room(source))

    def test_reload_refuses_another_room_or_a_lost_area(self):
        self.runtime.db.execute('DELETE FROM kit_pending')
        with self.assertRaisesRegex(InvalidChange, 'Reload only'):
            self.runtime.reload_room(self.edited(lambda s: s.__setitem__('id', 'other')))
        with self.assertRaisesRegex(InvalidChange, "PC's area"):
            self.runtime.reload_room(self.edited(lambda s: s['areas'].pop('landing')))
        self.assertNotIn('scratch', self.runtime.source()['facts'])


class StartReloadsAnEditedRoom(unittest.TestCase):
    def test_start_on_a_running_game_reloads_an_edited_room_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            room = Path(tmp) / 'room.json'
            room.write_text(Path(kit_agent.DEFAULT_ROOM).read_text(encoding='utf-8'), encoding='utf-8')
            db = str(Path(tmp) / 'g.sqlite')
            kit_agent.start_session(db, room=str(room))
            with self.assertRaisesRegex(InvalidChange, 'new --db'):  # unchanged: still refused
                kit_agent.start_session(db, room=str(room))
            runtime = Runtime(db)
            runtime.db.execute('DELETE FROM kit_pending')
            runtime.db.commit()
            data = json.loads(room.read_text(encoding='utf-8'))
            area = next(iter(data['areas']))
            data['facts']['added_mid_game'] = {'area': area, 'visible': False, 'text': 'A new note.'}
            room.write_text(json.dumps(data), encoding='utf-8')
            result = kit_agent.start_session(db, room=str(room), runtime=runtime)
            self.assertEqual(result['stage'], 'reloaded')
            self.assertIn('added_mid_game', runtime.source()['facts'])
            runtime.close()


class TeaseNeedsARealTarget(unittest.TestCase):
    """Item 11: a doorway tease whose points_to names nothing in the file warns; one that
    names a fact (rooms5 level_01_area_11: 'throne') or a declared hook is fine."""

    def warnings_for(self, points_to, story=None):
        source = {'areas': {'door': {'tease': {'text': 'Humming.', 'points_to': points_to, 'heard': []}}},
                  'facts': {'throne': {}}, 'actors': {}, 'story': story or {}}
        with unittest.mock.patch.object(kit_rooms, 'approaches', return_value=['door']):
            return kit_rooms.tease_warnings(source), kit_rooms.tease_problems(source)

    def test_a_dangling_points_to_warns(self):
        warned, problems = self.warnings_for('ghost')
        self.assertTrue(any("'ghost'" in line for line in warned))
        self.assertEqual(problems, [])

    def test_a_fact_target_is_fine(self):
        self.assertEqual(self.warnings_for('throne'), ([], []))

    def test_with_hooks_a_missing_hook_still_refuses(self):
        warned, problems = self.warnings_for('ghost', {'main': {'hooks': [{'id': 'h1'}]}})
        self.assertEqual(warned, [])
        self.assertTrue(any("'ghost'" in p for p in problems))

if __name__ == '__main__':
    unittest.main()
