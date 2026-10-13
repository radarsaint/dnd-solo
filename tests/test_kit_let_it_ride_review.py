"""Nagatha's #103 review: hidden watchers never named or hinted at, a woken watcher noticed at
once, 'runs' is not a new approach, room-neutral failed-Stealth text, a lifted purse is
Sleight of Hand, SRD passives, and the NPC surprise roll allowlisted. Three synthetic rooms
built from the watchroom shape (invented content, no book text, no 6c), plus a #97-style
ambusher hidden in each; dice pinned or left to the player; no model."""
import copy
import json
import re
import unittest

from runtime import kit_agent, kit_claims
from runtime.kit_agent import KitChatBridge, RoomAdjudicator
from test_kit_room_review import ROOT, WATCH
from test_kit_watchroom_stalls import Stalls

ROOMS = {
    'mill': dict(id='review-grain-mill', room='Millhouse', key='miller', name='Floury miller',
                 chest='A sack of grain slumps against the millstone.'),
    'ferry': dict(id='review-ferry-house', room='Ferry house', key='ferryman', name='Old ferryman',
                  chest='A tar-stained toll box sits by the window.'),
    'chapel': dict(id='review-bone-chapel', room='Bone chapel', key='sexton', name='Hollow-eyed sexton',
                   chest='An ossuary niche holds a row of skulls.'),
}
LURKER = 'Knife-hand cutpurse'


def room(kind, lurker=None):
    """The watchroom shape renamed for ``kind``. ``lurker``: None, 'asleep' (a hidden watcher who
    wakes later), 'ambush' (a hidden watcher lying in wait, awake), or 'away' (hidden, next door)."""
    spec = ROOMS[kind]
    r = json.loads((ROOT / WATCH).read_text())
    r['id'] = spec['id']
    r['areas']['watchroom'].update(name=spec['room'], called='the ' + spec['room'].lower())
    r['facts']['chest']['text'] = spec['chest']
    keeper = r['actors'].pop('warden')
    keeper.update(name=spec['name'])
    r['actors'][spec['key']] = keeper
    text = json.dumps(r).replace('"warden"', json.dumps(spec['key']))
    r = json.loads(text)
    if lurker:
        r['actors']['lurker'] = {
            'name': LURKER, 'location': 'stair_down' if lurker == 'away' else 'watchroom',
            'status': 'asleep' if lurker == 'asleep' else 'alive', 'visible': False,
            'motive': 'Rob the next stranger.', 'knowledge': [], 'secrets': [],
            'communication_profile': {'rhythm': 'Whispers.'}, 'armed': True, 'stat_block': {'srd': 'Guard'}}
    return r


def events_of(result, kind):
    return [e for e in result.events if e.get('type') == kind]


class Rooms(Stalls):
    def open(self, kind, lurker=None):
        self.runtime = self.start(str(self.write(room(kind, lurker))))
        self.bridge = KitChatBridge(self.runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10))
        self.go_in()

    def act(self, line, state=None):
        revision, current = self.runtime.load()
        result = RoomAdjudicator(npc_roll=lambda: 10, source=self.runtime.source()).resolve(
            line, revision, state or current)
        if state is None:
            self.runtime.commit(f't{revision}', revision, list(result.events))
        return result

    def standing(self):
        return self.runtime.load()[1].get('standing_check')

    def assert_hidden_kept(self, result):
        for word in (LURKER, 'cutpurse', 'lurker', 'watching', 'someone', 'somebody', 'eyes'):
            self.assertNotIn(word.casefold(), result.public_event.casefold(), result.public_event)

    def each(self):
        for kind in ROOMS:
            with self.subTest(room=kind):
                yield kind


class HiddenWatchersStayHidden(Rooms):
    def test_a_hidden_watcher_who_wakes_triggers_a_neutral_call(self):
        for kind in self.each():
            self.open(kind, 'asleep')
            self.act('I creep along the wall. Stealth check: 1d20 (20) + 2 = 22')
            revision, _ = self.runtime.load()
            self.runtime.commit('wake', revision, [{'type': 'actor_status', 'actor': 'lurker', 'status': 'alive',
                                                    'evidence': 'The cutpurse wakes.'}])
            result = self.act('I keep creeping along the same wall')
            self.assertEqual(result.kind, 'check_called')
            self.assertEqual(events_of(result, 'pending_check')[0]['check']['skill'], 'stealth')
            self.assert_hidden_kept(result)

    def test_an_ambusher_lying_in_wait_watches_and_is_never_named(self):
        for kind in self.each():
            self.open(kind, 'ambush')
            for line in ('I creep along the wall. Stealth check: 1d20 (20) + 2 = 22',
                         'I keep creeping along the same wall',
                         'I creep along the wall. Stealth check: 1d20 (2) + 2 = 4'):
                self.assert_hidden_kept(self.act(line))
            # The ambusher counts as a watcher (its passive is in the private evidence only).
            self.assertIn('lurker', json.dumps(self.runtime.load()[1].get('standing_check') or {}) +
                          ' '.join(e.get('evidence', '') for e in self.act('I creep along the wall. Stealth 22').events))

    def test_a_hidden_watcher_who_steps_in_is_a_neutral_change_and_a_visible_one_is_named(self):
        for kind in self.each():
            self.open(kind, 'away')
            self.act('I creep along the wall. Stealth check: 1d20 (20) + 2 = 22')
            _, state = self.runtime.load()
            moved = copy.deepcopy(state)
            moved['actors']['lurker']['location'] = 'watchroom'
            result = self.act('I keep creeping along the same wall', state=moved)
            self.assertEqual(result.kind, 'check_called')
            self.assert_hidden_kept(result)
            self.assertEqual(events_of(result, 'pending_check')[0]['check']['target'], 'none')
            shown = copy.deepcopy(moved)
            shown['actors']['lurker']['visible'] = True
            self.assertIn(LURKER, self.act('I keep creeping along the same wall', state=shown).public_event)

    def test_a_hidden_actor_is_not_who_the_player_talks_to_or_who_blocks_the_way(self):
        for kind in self.each():
            self.open(kind, 'ambush')
            _, state = self.runtime.load()
            alone = copy.deepcopy(state)
            alone['actors'][ROOMS[kind]['key']]['location'] = 'stair_down'
            alone['actors']['lurker']['guards'] = ['back_stair']
            alone['known_exits'] = sorted(set(alone['known_exits']) | {'back_stair'})
            result = self.act('I take the back stair down.', state=alone)
            self.assert_hidden_kept(result)
            self.assertNotEqual(result.kind, 'exit_contested')


class AWokenWatcherIsNoticedAtOnce(Rooms):
    def test_the_standing_result_ends_on_the_wake_not_on_the_next_stealth_act(self):
        for kind in self.each():
            for lurker in ('asleep',):
                self.open(kind, lurker)
                self.act('I creep along the wall. Stealth check: 1d20 (20) + 2 = 22')
                self.assertIsNotNone(self.standing())
                revision, _ = self.runtime.load()
                self.runtime.commit('wake', revision, [{'type': 'actor_status', 'actor': 'lurker', 'status': 'alive',
                                                        'evidence': 'It wakes.'}])
                self.assertIsNone(self.standing())
                # A look in between does not carry the old result forward either.
                self.act('I look around the room.')
                self.assertIsNone(self.standing())


class WhatCountsAsADifferentApproach(Rooms):
    def test_water_that_runs_is_not_the_pc_running(self):
        for kind in self.each():
            self.open(kind)
            self.act('I creep along the wall. Stealth check: 1d20 (20) + 2 = 22')
            result = self.act('I sneak on, past where the water runs down the wall.')
            self.assertEqual(result.kind, 'stealth')
            self.assertFalse(events_of(result, 'pending_check'))
            self.assertEqual(self.standing()['total'], 22)
            self.assertEqual(self.act('I run for the far wall.').kind, 'check_called')


class FailedStealthIsRoomNeutral(Rooms):
    def test_no_card_table_in_a_mill(self):
        for kind in self.each():
            self.open(kind)
            result = self.act('I sneak toward the back stair. Stealth 4')
            self.assertEqual(result.kind, 'stealth')
            self.assertNotRegex(result.public_event.casefold(), r'\btable\b')
            self.assertNotIn('Eyes at the table', kit_agent.Path(kit_agent.__file__).read_text())


class LiftingAPurse(Rooms):
    def test_a_purse_off_an_npc_is_sleight_of_hand_not_table_coins(self):
        for kind in self.each():
            self.open(kind)
            line = f"I lift the purse off the {ROOMS[kind]['name'].split()[-1].lower()}'s belt."
            result = self.act(line)
            self.assertEqual(result.kind, 'check_called')
            self.assertEqual(events_of(result, 'pending_check')[0]['check']['skill'], 'sleight_of_hand')
            self.assertNotIn('table coins', result.public_event)
            rolled = self.act('Sleight of Hand: 1d20 (18) + 5 = 23')
            self.assertNotIn('table coins', rolled.public_event)
            self.assertIn('sleight_of_hand', ' '.join(e.get('evidence', '') for e in rolled.events).replace(' ', '_')
                          .casefold())


class SrdPassives(unittest.TestCase):
    def test_a_cited_srd_stat_block_sets_the_passive(self):
        self.assertEqual(kit_claims.npc_passive({'stat_block': {'srd': 'Guard'}}, 'perception'), 12)
        self.assertEqual(kit_claims.npc_passive({'stat_block': {'srd': 'Scout'}}, 'perception'), 15)
        self.assertEqual(kit_claims.npc_passive({'stat_block': {'srd': 'Commoner'}}, 'perception'), 10)
        self.assertEqual(kit_claims.npc_passive({'stat_block': {'srd': 'Scout'}}, 'insight'), 11)
        inline = {'stats': {'abilities': {'str': 10, 'dex': 10, 'con': 10, 'int': 10, 'wis': 16, 'cha': 10}},
                  'stat_block': {'srd': 'Guard'}}
        self.assertEqual(kit_claims.npc_passive(inline, 'perception'), 13)   # the room's own numbers win


class SurpriseIsAnNpcRoll(unittest.TestCase):
    def test_the_static_audit_allows_the_ambushers_surprise_roll(self):
        text = (ROOT / 'tests/test_kit_let_it_ride.py').read_text()
        self.assertIn("('kit_triggers.py', 'surprise_roll')", text)


if __name__ == '__main__':
    unittest.main()
