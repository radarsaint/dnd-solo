"""#97 review (Nagatha, 9c24cd1): the engine fires a room's disturb trigger only from the act Kit
declares (``handles``, runtime/kit_acts.py), never from English read by a regex; plus the P1/P2
fixes that review found. Every probe in /workspace/review-97-probes (p4, p5) is a test here.
Room-agnostic: the carcass room, a coffin beside it, an altar room, and 6c's tub (no trigger,
which must play exactly as on main). Every die is pinned."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_acts, kit_claims, kit_combat, kit_rolls, kit_rooms, kit_triggers
from runtime.kit_agent import ONE_PASS_SCHEMA, KitChatBridge, PendingRuling, RoomAdjudicator, start_session
from runtime.state_context import InvalidChange, Runtime
from test_kit_agent import RecordingModel
from test_kit_monster_initiative import NIK, ROLL, Room, carcass, with_coffin

ROOT = Path(__file__).resolve().parents[1]
SIXC = ROOT / 'tests' / 'fixtures' / 'level_01_area_06c.json'
WATCHROOM = ROOT / 'tests' / 'fixtures' / 'rooms' / 'watchroom.json'


class T(unittest.TestCase):
    def runTest(self):
        pass


def altar():
    """A third room shape: an altar whose candle and skull are parts and whose idol it holds;
    disturbing it wakes a hidden skeleton (no carcass words anywhere)."""
    source = carcass()
    source['id'] = 'synthetic-altar-v1'
    facts = source['facts']
    facts.pop('carcass')
    facts.pop('orb')
    facts['altar'] = {'area': 'hall', 'visible': True, 'text': 'A black altar stands under the pillars.',
                      'handling': {'nouns': ['altar', 'slab'], 'parts': ['candle', 'skull'], 'holds': 'idol',
                                   'handle': 'Wax and bone shift under your fingers.',
                                   'move': 'The slab grinds a finger-width on its plinth.',
                                   'look': 'Old wax and older stains.'}}
    facts['idol'] = {'area': 'hall', 'visible': True, 'text': 'A jade idol squats on the altar.',
                     'handling': {'nouns': ['idol', 'statuette'], 'look': 'Jade, cold and greasy.'}}
    source['actors'].pop('centipede_b')
    source['actors']['centipede_a'].update(name='Skeleton', stat_block={'srd': 'Giant Centipede'})
    source['triggers'] = [{'id': 'altar_disturbed', 'on': {'disturb': 'altar'}, 'actors': ['centipede_a'],
                           'reveal': 'Bones knit together behind the altar.'}]
    return source


# Phrasings that put no hands on the watched feature: a step, a look, cover, a path, a question.
NEGATIVE = {
    'carcass': ['I take a step toward the claw.', 'I break line of sight with the carcass.',
                'I pull my dagger and edge toward the claw.', 'I take cover behind the carcass.',
                'I take a look at the claw.', 'I take a closer look at the orb.',
                'I pick a spot far from the body and sit.', 'I slide along the wall away from the carcass.',
                'I take a deep breath and stare at the basilisk.', 'I pick my way around the carcass.',
                'I break into a run past the basilisk.', 'I touch nothing and look at the claw.',
                'I tell Kit "don\'t take the orb"', 'I cut a path wide of the hide.',
                'I force myself to look at the claw.', 'I pull back from the carcass.',
                'I lift my lantern toward the claw.', 'I examine the pillars near the carcass.',
                'What is in the claw?', 'I look at the carcass.', 'I glance at the basilisk from the doorway.',
                'Is there an orb?', 'I look at the orb.'],
    'coffin': ['I take a step toward the coffin.', 'I take cover behind the sarcophagus.',
               'I take a look at the lid.', 'I lean my staff against the coffin.', 'What is under the lid?',
               'I pull back from the coffin.', 'I pick my way around the sarcophagus.'],
    'altar': ['I take a step toward the altar.', 'I take a look at the candle.', 'I kneel and pray near the altar.',
              'I take cover behind the slab.', 'I pull back from the altar.', 'I lift my torch toward the skull.',
              'What is on the altar?', 'I break line of sight with the altar.'],
}
# The tub has no trigger: these play exactly as on main (2804b79), and never show the stash.
SIXC_ON_MAIN = {
    'I take a step toward the tub.': 'PENDING',
    'I take a look at the tub.': 'observe',
    'I pull up a stool near the tub.': 'PENDING',
    'I grab the coins by the tub.': 'combat_round',  # the table coins, not the tub (P1-3)
}


def resolve(room, action):
    revision, state = room.runtime.load()
    try:
        return room.adjudicator.resolve(action, revision, state)
    except PendingRuling:
        return None


class NothingFiresFromWordsTests(unittest.TestCase):
    """P1-1, P1-4, P2 false fires: no phrasing fires a trigger or shows a held item by itself."""

    def rooms(self):
        return {'carcass': (carcass, 'orb'), 'coffin': (with_coffin, 'signet'), 'altar': (altar, 'idol')}

    def test_the_negative_corpus_fires_nothing_shows_nothing_and_hints_nothing(self):
        for name, (build, held) in self.rooms().items():
            for action in NEGATIVE[name]:
                with self.subTest(room=name, action=action):
                    room = Room(self, source=build())
                    known = set(room.state['known_facts'])
                    result = resolve(room, action)
                    if result is None:
                        continue  # a pending ruling commits nothing
                    types = [e['type'] for e in result.events]
                    self.assertNotIn('trigger_fired', types)
                    self.assertNotIn('combat_state', types)
                    revealed = {e.get('fact') for e in result.events if e['type'] == 'reveal_fact'}
                    self.assertFalse(revealed - known, f'{action!r} revealed {revealed}')
                    self.assertIsNone(((result.offers or {}).get('handles') or {}).get('hint'),
                                      f'{action!r} hinted a handling')

    def test_even_a_plain_hands_on_line_fires_nothing_without_kit(self):
        for build, action in ((carcass, 'I pry the claw open.'), (carcass, 'I roll the carcass over.'),
                              (carcass, 'I climb onto the carcass.'), (carcass, 'I stab the carcass.'),
                              (with_coffin, 'I pry the lid off.'), (altar, 'I snap the candle off the altar.')):
            with self.subTest(action=action):
                room = Room(self, source=build())
                result = room.act(action)
                self.assertNotIn('trigger_fired', [e['type'] for e in result.events])
                self.assertTrue(all(a['status'] == 'hidden' for k, a in room.state['actors'].items()
                                    if k.startswith('centipede')))
                self.assertTrue(result.offers['handles']['hint'])

    def test_the_hint_names_the_verbs_own_object_not_the_first_noun_in_the_file(self):
        room = Room(self, source=with_coffin())
        result = room.act('I lift the lid next to the basilisk.')
        self.assertEqual(result.offers['handles']['hint'], {'target': 'lid', 'act': 'lift'})
        room = Room(self, source=with_coffin())
        result = room.act('I pry the lid off the coffin while staring at the claw.')
        self.assertEqual(result.offers['handles']['hint'], {'target': 'lid', 'act': 'pry'})
        # Declared on the coffin, only the coffin's trigger fires (P1-4).
        room = Room(self, source=with_coffin())
        room.act('I lift the lid next to the basilisk.', {'target': 'lid', 'act': 'lift'})
        self.assertEqual(room.state['triggers_fired'], ['coffin_disturbed'])
        self.assertEqual(room.state['actors']['centipede_a']['status'], 'hidden')


class SixCRegressionTests(unittest.TestCase):
    """P1-2 and P1-3: 6c's tub (no trigger) routes as on main; the coins are the table's."""

    def room(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'k.sqlite')
        self.addCleanup(runtime.close)
        runtime.initialize(kit_rooms.check_room(json.loads(SIXC.read_text())), 'area_06c')
        runtime.set_player_sheet(json.loads(NIK.read_text()))
        return runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 1, source=runtime.source())

    def test_the_tub_phrasings_play_as_on_main(self):
        for action, kind in SIXC_ON_MAIN.items():
            with self.subTest(action=action):
                runtime, adjudicator = self.room()
                revision, state = runtime.load()
                try:
                    result = adjudicator.resolve(action, revision, state)
                except PendingRuling:
                    self.assertEqual(kind, 'PENDING')
                    continue
                self.assertEqual(result.kind, kind)
                self.assertNotIn('tub_stash', [e.get('fact') for e in result.events])
                self.assertIsNone(result.offers)

    def test_grabbing_the_coins_by_the_tub_takes_the_table_coins(self):
        runtime, adjudicator = self.room()
        revision, state = runtime.load()
        result = adjudicator.resolve('I grab the coins by the tub.', revision, state)
        self.assertIn('table coins', result.public_event)
        scene = next(e['state'] for e in result.events if e['type'] == 'scene_state')
        self.assertEqual(scene['pc_took'], ['the table coins'])

    def test_a_room_without_table_loot_has_no_coins_to_take(self):
        room = Room(self, source=with_coffin())
        result = resolve(room, 'I take the ring near the carcass.')
        self.assertTrue(result is None or 'scene_state' not in [e['type'] for e in result.events])


class DeclaredHandlesTests(unittest.TestCase):
    """The design steer: Kit's decision declares handles {target, act}; validated, then resolved."""

    def test_kits_ruling_fires_the_trigger_for_stab_climb_snatch_hook_and_kick(self):
        for action, handles, known in (('I stab the carcass.', {'target': 'carcass', 'act': 'stab'}, ()),
                                       ('I climb onto the carcass.', {'target': 'carcass', 'act': 'climb'}, ()),
                                       ('I snatch the orb.', {'target': 'orb', 'act': 'take'}, ('orb',)),
                                       ('I hook the orb out with my staff.', {'target': 'orb', 'act': 'hook'}, ('orb',)),
                                       ('I kick the carcass.', {'target': 'carcass', 'act': 'kick'}, ())):
            with self.subTest(action=action):
                room = Room(self)
                if known:
                    revision, _ = room.runtime.load()
                    room.runtime.commit('seen', revision, [{'type': 'reveal_fact', 'fact': f, 'evidence': 'seen'}
                                                           for f in known])
                result = room.act(action, handles)
                self.assertEqual(room.state['triggers_fired'], ['carcass_disturbed'])
                self.assertTrue(result.public_event.endswith('Roll initiative.'))

    def test_lifting_a_part_is_the_parts_handling_not_the_whole_carcass_moving(self):
        room = Room(self)
        result = room.act('I lift the foreleg.', {'target': 'foreleg', 'act': 'lift'})
        self.assertTrue(result.public_event.startswith('The stiff grey limb shifts'))
        room = Room(self)
        result = room.act('I lift the carcass.', {'target': 'carcass', 'act': 'lift'})
        self.assertTrue(result.public_event.startswith('You put your shoulder to the carcass'))

    def test_an_unseen_held_item_is_no_handle(self):
        room = Room(self)
        result = room.act('I pry the claw open.')
        self.assertNotIn('orb', result.offers['handles']['targets']['carcass'])
        with self.assertRaises(InvalidChange):
            kit_acts.check({'handles': {'target': 'orb', 'act': 'take'}}, {'acts': result.offers})
        self.assertIsNone(resolve(Room(self), 'I take the orb.'), 'naming the unseen orb is no act on it')

    def test_a_declaration_must_name_what_was_offered(self):
        offer = {'handles': {'targets': {'carcass': ['claw']}}}
        for bad, words in (({'target': 'pillars', 'act': 'take'}, 'not offered'),
                           ({'target': 'carcass', 'act': 'juggle'}, 'handles.act'),
                           ({'target': 'carcass'}, '{target, act}')):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(InvalidChange, words):
                    kit_acts.check({'handles': bad}, {'acts': offer})
        with self.assertRaisesRegex(InvalidChange, 'Nothing here can be handled'):
            kit_acts.check({'handles': {'target': 'carcass', 'act': 'take'}}, {'acts': {}})
        with self.assertRaisesRegex(InvalidChange, 'question'):
            kit_acts.check({'handles': {'target': 'carcass', 'act': 'take'}, 'ask_player': {'q': 1}}, {'acts': offer})
        for none in (None, 'none', {'target': 'none', 'act': 'none'}):
            self.assertEqual(kit_acts.check({'handles': none}, {'acts': {}}), {})
        self.assertEqual(kit_acts.check({'handles': {'target': 'claw', 'act': 'pry'}}, {'acts': offer}),
                         {'handles': {'feature': 'carcass', 'part': 'claw', 'act': 'pry'}})

    def test_barging_in_and_kicking_offers_the_carcass_in_the_room_he_lands_in(self):
        room = Room(self, start='stair')
        revision, _ = room.runtime.load()
        room.runtime.commit('see', revision, [{'type': 'reveal_exit', 'exit': 'stair', 'evidence': 'seen'}])
        result = room.act('I barge down the stair and kick the carcass.', {'target': 'carcass', 'act': 'kick'})
        self.assertEqual(room.state['area'], 'hall')
        self.assertEqual(room.state['triggers_fired'], ['carcass_disturbed'])
        self.assertIn('Roll initiative.', result.public_event)

    def test_the_family_shares_one_schema_style(self):
        decision = ONE_PASS_SCHEMA['properties']['decision']['properties']
        for field, schema in kit_acts.SCHEMAS.items():
            self.assertIs(decision[field], schema)
            self.assertIn(field, kit_acts.FIELDS)


class BridgeTests(unittest.TestCase):
    """Through prepare and complete, as a live host runs it."""

    def turn(self, room, action, handles=None, turn_id='t1'):
        bridge = KitChatBridge(room.runtime, room.adjudicator)
        packet = bridge.prepare(action, turn_id, one_pass=True)
        plan = RecordingModel().plan(packet['input']['private'])
        plan['improv_read'].update(actor_ref='none', actor_basis='none')
        plan.update(move='world_description', focus_actor='none')
        for key in ('objective', 'visible_cue', 'player_opening'):
            plan['public_brief'].pop(key, None)
        plan['public_brief']['scope'] = 'call'
        if handles:
            plan['handles'] = handles
        speech = {'segments': [{'speaker': 'Narrator', 'text': 'You kneel by the grey claw and work your fingers '
                                                               'under the stiff talons.'}]}
        return packet, bridge, bridge.complete(turn_id, {'decision': plan, 'performance': speech})

    def test_a_declared_pry_commits_the_ambush_after_kits_line_and_logs_the_handoff(self):
        room = Room(self)
        packet, bridge, result = self.turn(room, 'I pry the claw open.', {'target': 'claw', 'act': 'pry'})
        self.assertEqual(packet['input']['private']['acts']['handles']['hint'], {'target': 'claw', 'act': 'pry'})
        self.assertTrue(any(line.startswith('acts.handles:') for line in packet['first_try']))
        lines = result['spoken'].split('\n')
        self.assertTrue(lines[0].startswith('Narrator: You kneel'))
        self.assertTrue(lines[-1].endswith('Roll initiative.'))
        self.assertEqual(room.state['triggers_fired'], ['carcass_disturbed'])
        self.assertIn('orb', room.state['known_facts'])
        self.assertEqual(result['timing']['handoff']['trigger'], 'carcass_disturbed')
        self.assertEqual(room.state['combat']['status'], 'awaiting_initiative')

    def test_kit_saying_no_handling_leaves_the_room_asleep(self):
        room = Room(self)
        _, _, result = self.turn(room, 'I take a step toward the claw.')
        self.assertNotIn('Roll initiative', result['spoken'])
        self.assertEqual(room.state.get('triggers_fired') or [], [])

    def test_a_declaration_on_a_turn_that_offered_nothing_is_rejected(self):
        room = Room(self)
        with self.assertRaisesRegex(InvalidChange, 'Nothing here can be handled'):
            self.turn(room, 'I look around the hall.', {'target': 'carcass', 'act': 'roll'})
        self.assertEqual(room.state.get('triggers_fired') or [], [])

    def test_a_turn_with_no_trigger_room_carries_no_acts_block(self):
        source = carcass(triggers=[])
        for actor in source['actors'].values():
            actor.update(status='alive', visible=True)
        room = Room(self, source=source)
        bridge = KitChatBridge(room.runtime, room.adjudicator)
        packet = bridge.prepare('I search the carcass.', 'q', one_pass=True)
        self.assertNotIn('acts', packet['input']['private'])


class SceneScopeTests(unittest.TestCase):
    def test_room_now_is_only_for_a_room_that_keys_table_loot(self):
        """P1-5: 6c's table, coins and ring never show in another room's view."""
        room = Room(self, roll=lambda: 2)
        room.act('I roll the carcass over.', ROLL)
        room.act('Initiative 20')
        self.assertNotIn('room_now', room.runtime.player_view())
        self.assertFalse(kit_combat.table_scene(room.runtime.source()))
        self.assertTrue(kit_combat.table_scene(json.loads(SIXC.read_text())))


class EnterTriggerTests(unittest.TestCase):
    """P1-6: an enter trigger fires when the PC starts there, and after a room_link arrival."""

    def test_starting_in_the_area_fires_on_his_first_turn(self):
        source = carcass()
        source['triggers'][0]['on'] = {'enter': 'hall'}
        room = Room(self, source=source)
        result = room.act('I look around the hall.')
        self.assertIn('trigger_fired', [e['type'] for e in result.events])
        self.assertEqual(room.state['combat']['status'], 'awaiting_initiative')

    def test_arriving_through_a_room_link_fires_it(self):
        temp = Path(tempfile.mkdtemp())
        source = carcass()
        source['triggers'][0]['on'] = {'enter': 'hall'}
        (temp / 'carcass_enter.json').write_text(json.dumps(source))
        watch = json.loads(WATCHROOM.read_text())
        watch['areas']['stair_down']['room_link'] = {'room': str(temp / 'carcass_enter.json'), 'area': 'hall'}
        (temp / 'watch.json').write_text(json.dumps(watch))
        started = start_session(temp / 's.sqlite', NIK, room=temp / 'watch.json', area='landing')
        runtime = Runtime(temp / 's.sqlite')
        self.addCleanup(runtime.close)
        KitChatBridge(runtime, RoomAdjudicator()).abandon(started['prepared']['turn_id'])

        def play(line):
            revision, state = runtime.load()
            result = RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 1,
                                     source=runtime.source()).resolve(line, revision, state)
            runtime.commit(f'p{revision}', revision, list(result.events))
            return result
        play('I take the stair down.')
        self.assertEqual(runtime.source()['id'], 'synthetic-carcass-v1')
        result = play('I look around.')
        self.assertIn('trigger_fired', [e['type'] for e in result.events])
        state = runtime.load()[1]
        self.assertEqual(state['triggers_fired'], ['carcass_disturbed'])
        self.assertEqual(state['combat']['status'], 'awaiting_initiative')


class OverlappingTriggerTests(unittest.TestCase):
    def test_a_trigger_whose_actors_are_dead_or_fighting_does_not_restart_the_fight(self):
        """P1-7."""
        source = carcass()
        source['triggers'].append({'id': 'hall_entered', 'on': {'enter': 'hall'},
                                   'actors': ['centipede_a', 'centipede_b'], 'reveal': 'Again!'})
        room = Room(self, source=source, start='stair', roll=lambda: 2)
        revision, _ = room.runtime.load()
        room.runtime.commit('see', revision, [{'type': 'reveal_exit', 'exit': 'stair', 'evidence': 'seen'}])
        room.act('I walk down the stair.')  # the enter trigger wakes them
        room.act('Initiative 20')
        result = room.act('I roll the carcass over.', ROLL)  # same actors, already fighting
        self.assertNotIn('Roll initiative', result.public_event)
        self.assertNotIn('Again!', result.public_event)
        self.assertEqual(room.state['combat']['status'], 'running')
        for line in ('I hit the banded centipede with my quarterstaff: 17 to hit, 6 bludgeoning damage.',
                     'I hit the rust-red centipede with my quarterstaff: 17 to hit, 6 bludgeoning damage.'):
            room.act(line)
        self.assertEqual(room.state['combat']['status'], 'over')
        self.assertEqual(set(room.state['triggers_fired']), {'carcass_disturbed', 'hall_entered'})

    def test_with_both_dead_a_late_trigger_is_spent_quietly(self):
        source = carcass()
        source['triggers'].append({'id': 'hall_entered', 'on': {'enter': 'stair'},
                                   'actors': ['centipede_a', 'centipede_b'], 'reveal': 'Again!'})
        room = Room(self, source=source, roll=lambda: 2)
        room.act('I roll the carcass over.', ROLL)
        room.act('Initiative 20')
        for line in ('I hit the banded centipede with my quarterstaff: 17 to hit, 6 bludgeoning damage.',
                     'I hit the rust-red centipede with my quarterstaff: 17 to hit, 6 bludgeoning damage.'):
            room.act(line)
        revision, _ = room.runtime.load()
        room.runtime.commit('see', revision, [{'type': 'reveal_exit', 'exit': 'stair', 'evidence': 'seen'}])
        result = room.act('I walk up the stair.')
        self.assertIn('trigger_fired', [e['type'] for e in result.events])
        self.assertNotIn('Roll initiative', result.public_event)
        self.assertEqual(room.state['combat']['status'], 'over')


class MountTests(unittest.TestCase):
    def test_a_hidden_actor_must_be_invisible(self):
        """P1-8: status hidden with visible true is refused at load."""
        source = carcass()
        source['actors']['centipede_a']['visible'] = True
        with self.assertRaisesRegex(kit_rooms.RoomMountError, 'visible": false'):
            kit_rooms.check_room(source)
        del source['actors']['centipede_a']['visible']
        with self.assertRaisesRegex(kit_rooms.RoomMountError, 'visible": false'):
            kit_rooms.check_room(source)

    def test_an_orphan_hidden_actor_and_a_hidden_heard_actor_are_refused(self):
        source = carcass()
        source['triggers'][0]['actors'] = ['centipede_a']
        with self.assertRaisesRegex(kit_rooms.RoomMountError, 'centipede_b is hidden but no trigger'):
            kit_rooms.check_room(source)
        source = carcass()
        source['areas']['stair'].pop('beyond')  # the stair is the doorway: it carries the tease
        source['areas']['stair']['tease'] = {'text': 'Something clicks below.',
                                             'heard': [{'actor': 'centipede_a', 'sound': 'clicking'}]}
        problems = kit_rooms.tease_problems(source)
        self.assertTrue(any('hidden until a trigger fires' in p for p in problems), problems)


class IncapacitatedTests(unittest.TestCase):
    """P1-9: a PC at 0 HP or paralyzed cannot move or act; conditions outlast the fight."""

    def dropped(self):
        room = Room(self, npc_roll=lambda: 1, roll=lambda: 15)
        room.act('I roll the carcass over.', ROLL)
        room.act('Initiative 1')
        room.runtime.set_player_sheet(dict(room.state['player_sheet'], hp=12))
        room.act('Con save 3')
        return room

    def test_he_cannot_crawl_out_or_act(self):
        room = self.dropped()
        self.assertEqual(room.state['pc_conditions'], ['poisoned', 'paralyzed'])
        for line in ('I crawl toward the stair.', 'I walk up the stair.', 'I hit the banded centipede.',
                     '"Help!"'):
            with self.subTest(line=line):
                revision, state = room.runtime.load()
                with self.assertRaisesRegex(PendingRuling, 'cannot move, act or speak'):
                    room.adjudicator.resolve(line, revision, state)
        self.assertEqual(room.state['area'], 'hall')

    def test_conditions_persist_after_the_fight_until_they_end(self):
        room = self.dropped()
        state = copy.deepcopy(room.state)
        revision, _ = room.runtime.load()
        over = dict(state['combat'], status='over', pc_down=False)
        room.runtime.commit('over', revision, [{'type': 'combat_state', 'state': over, 'evidence': 'test'}])
        self.assertEqual(room.state['pc_conditions'], ['poisoned', 'paralyzed'])
        self.assertEqual(room.runtime.player_view().get('your_conditions'), ['poisoned', 'paralyzed'])
        revision, state = room.runtime.load()
        with self.assertRaisesRegex(PendingRuling, 'paralyzed'):
            room.adjudicator.resolve('I walk up the stair.', revision, state)
        room.runtime.commit('ends', revision, [{'type': 'pc_conditions', 'conditions': [], 'evidence': 'an hour'}])
        self.assertEqual(room.state['pc_conditions'], [])
        self.assertIn('pc_conditions', kit_rooms.SESSION_KEYS)


class FightDetailTests(unittest.TestCase):
    def test_con_colon_and_named_saves_parse(self):
        for text, total in (('Con: 14', 14), ('con save: 9', 9), ('Constitution 12', 12), ('Con save 14, then I run', 14)):
            with self.subTest(text=text):
                self.assertEqual(kit_combat.save_total(text, 'con'), total)
        self.assertIsNone(kit_combat.save_total('Dex save 18', 'con'))

    def test_a_save_then_a_spell_keeps_the_spell_for_his_turn(self):
        room = Room(self, npc_roll=lambda: 1, roll=lambda: 15)
        room.act('I roll the carcass over.', ROLL)
        room.act('Initiative 1')
        room.act('Con save 14, then I cast magic missile at the banded centipede')
        self.assertEqual(room.state['combat']['declared_next'], 'I cast magic missile at the banded centipede')
        result = room.act('Con save 15')
        self.assertIn('Magic Missile', result.public_event)

    def test_every_save_rider_in_a_turn_is_asked_in_turn(self):
        source = carcass()
        source['actors']['centipede_a']['stat_block'] = {
            'ac': 13, 'hp': 4, 'initiative': 2,
            'attacks': [{'name': 'Bite', 'to_hit': 4, 'damage': 1, 'type': 'piercing',
                         'save': {'ability': 'con', 'dc': 11, 'damage': 2, 'type': 'poison', 'half': False}},
                        {'name': 'Sting', 'to_hit': 4, 'damage': 1, 'type': 'piercing',
                         'save': {'ability': 'dex', 'dc': 11, 'damage': 2, 'type': 'acid', 'half': False}}]}
        room = Room(self, source=source, npc_roll=lambda: 1, roll=lambda: 15)
        room.act('I roll the carcass over.', ROLL)
        room.act('Initiative 1')
        room.decline_open()  # Nik lets the bite through (no Shield, #101's window)
        self.assertEqual(room.state['combat']['awaiting']['save'], 'con')
        result = room.act('Con save 15')
        self.assertIn('Dexterity saving throw', result.public_event)
        self.assertEqual(room.state['combat']['awaiting']['save'], 'dex')

    def test_the_attacker_key_from_101_is_read_too(self):
        self.assertEqual(kit_combat.attacker({'attacker': 'centipede_b'}), 'centipede_b')
        self.assertEqual(kit_combat.attacker({'from': 'centipede_a'}), 'centipede_a')

    def test_a_monster_joining_mid_fight_takes_its_initiative_place(self):
        source = carcass()
        source['triggers'] = [{'id': 'carcass_disturbed', 'on': {'disturb': 'carcass'}, 'actors': ['centipede_a']},
                              {'id': 'stair_watch', 'on': {'enter': 'stair'}, 'actors': ['centipede_b']}]
        room = Room(self, source=source, roll=lambda: 2)
        room.act('I roll the carcass over.', ROLL)
        room.act('Initiative 5')  # centipede 12, you 5
        self.assertEqual(room.state['combat']['order'], ['centipede_a', 'pc'])
        revision, _ = room.runtime.load()
        room.runtime.commit('see', revision, [{'type': 'reveal_exit', 'exit': 'stair', 'evidence': 'seen'}])
        room.act('I walk up the stair.')
        order = room.state['combat']['order']
        self.assertEqual(order.index('centipede_b'), order.index('centipede_a') + 1, order)
        self.assertLess(order.index('centipede_b'), order.index('pc'))

    def test_a_surprised_pc_has_no_reaction_in_round_one(self):
        room = Room(self, npc_roll=lambda: 20, roll=lambda: 2)
        room.act('I roll the carcass over.', ROLL)
        fight = kit_combat.Fight(room.runtime.source(), room.state, 0, 'x', check=None)
        self.assertFalse(fight.pc_can_react())
        self.assertTrue(room.runtime.player_view()['fight']['you_are_surprised'])
        room = Room(self, npc_roll=lambda: 1, roll=lambda: 2)
        room.act('I roll the carcass over.', ROLL)
        fight = kit_combat.Fight(room.runtime.source(), room.state, 0, 'x', check=None)
        self.assertTrue(fight.pc_can_react())


class TieRuleTests(unittest.TestCase):
    """Brendon (2026-10-04): when a creature acts on another, meet-or-beat wins: the actor wins
    ties. Each comparison: a tie, +1 and -1."""

    def test_the_helper(self):
        self.assertTrue(kit_rolls.meets_or_beats(14, 14))
        self.assertTrue(kit_rolls.meets_or_beats(15, 14))
        self.assertFalse(kit_rolls.meets_or_beats(13, 14))

    def test_monster_stealth_against_passive_perception(self):
        # Nik's passive Perception is 14; each centipede rolls d20 + 2.
        for die, surprised in ((12, True), (13, True), (11, False)):
            with self.subTest(total=die + 2):
                room = Room(self, npc_roll=lambda die=die: die)
                room.act('I roll the carcass over.', ROLL)
                self.assertEqual('pc' in room.state['combat']['surprised'], surprised)

    def test_a_flat_stealth_dc_against_passive_perception(self):
        for dc, surprised in ((14, True), (15, True), (13, False)):
            with self.subTest(dc=dc):
                source = carcass()
                source['triggers'][0]['surprise'] = {'dc': dc}
                room = Room(self, source=source)
                room.act('I roll the carcass over.', ROLL)
                self.assertEqual('pc' in room.state['combat']['surprised'], surprised)

    def test_a_monster_attack_against_the_pcs_ac(self):
        # Nik's AC 14; the bite is d20 + 4: 10 ties, 11 beats, 9 misses.
        for die, hit in ((10, True), (11, True), (9, False)):
            with self.subTest(total=die + 4):
                room = Room(self, npc_roll=lambda: 1, roll=lambda die=die: die)
                room.act('I roll the carcass over.', ROLL)
                result = room.act('Initiative 1')
                # A hit Nik could still turn (Shield, #101) stops at his reaction window first.
                window = (room.state['combat'].get('awaiting') or {}).get('trigger') == 'hit'
                self.assertEqual('hits you' in result.public_event or window, hit, result.public_event)

    def test_the_pcs_attack_against_a_monsters_ac(self):
        # Giant centipede AC 13.
        for total, hit in ((13, True), (14, True), (12, False)):
            with self.subTest(total=total):
                room = Room(self, roll=lambda: 2)
                room.act('I roll the carcass over.', ROLL)
                room.act('Initiative 20')
                result = room.act(f'I hit the banded centipede with my quarterstaff: {total} to hit, 1 bludgeoning damage.')
                self.assertEqual('misses' not in result.public_event.split('.')[0], hit, result.public_event)

    def test_the_pcs_stealth_against_the_best_passive_perception(self):
        # 6c: the best passive Perception present is 11.
        for total, unnoticed in ((11, True), (12, True), (10, False)):
            with self.subTest(total=total):
                runtime, adjudicator = SixCRegressionTests.room(self)
                revision, state = runtime.load()
                result = adjudicator.resolve(f'I sneak toward the door, Stealth {total}', revision, state)
                self.assertEqual('unnoticed' in result.public_event, unnoticed, result.public_event)

    def test_an_npc_lie_against_passive_insight(self):
        sheet = json.loads(NIK.read_text())
        from runtime import pc_sheet
        passive = pc_sheet.passive(sheet, 'insight')
        for deception, lands in ((passive - 10, True), (passive - 9, True), (passive - 11, False)):
            with self.subTest(attack=10 + deception):
                self.assertEqual(kit_claims.lie_lands({'deception': deception}, sheet)['lands'], lands)


if __name__ == '__main__':
    unittest.main()
