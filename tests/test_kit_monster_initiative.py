"""Monster-initiated combat (PR-M): a data-only room trigger starts the fight, hidden actors
stay out of every Kit-visible field until it fires, SRD surprise, and a monster attack whose
save rider asks the player to roll the save. Non-6c fixture: tests/fixtures/rooms/carcass.json
(a dead basilisk with two giant centipedes under it, Area 17a's shape)."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import kit_acts, kit_rolls, kit_rooms, kit_triggers, srd_creatures
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, turn_speakers
from runtime.state_context import InvalidChange, Runtime

ROOT = Path(__file__).resolve().parents[1]
CARCASS = ROOT / 'tests' / 'fixtures' / 'rooms' / 'carcass.json'
NIK = ROOT / 'tests' / 'fixtures' / 'characters' / 'nik.json'
HIDDEN_WORDS = ('centipede', 'banded', 'rust-red')
ROLL = {'target': 'carcass', 'act': 'roll'}  # Kit's declaration for 'I roll the carcass over.'


def carcass(**changes):
    source = json.loads(CARCASS.read_text())
    for key, value in changes.items():
        source[key] = value
    return source


class Room:
    """The carcass room with every die pinned: ``roll`` is the monsters' attack d20s,
    ``npc_roll`` their Stealth d20 against the PC's passive Perception (Nik: 14)."""

    def __init__(self, test, source=None, start='hall', roll=lambda: 10, npc_roll=lambda: 1):
        temp = self._temp = tempfile.TemporaryDirectory()  # held: a probe's throwaway test case may go
        test.addCleanup(temp.cleanup)
        self.runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        test.addCleanup(self.runtime.close)
        with mock.patch('runtime.state_context.secrets.token_hex', return_value=f'{7:032x}'):
            self.runtime.initialize(kit_rooms.check_room(source or carcass()), start)
        self.runtime.set_player_sheet(json.loads(NIK.read_text()))
        self.adjudicator = RoomAdjudicator(roll=roll, npc_roll=npc_roll, source=self.runtime.source())

    def act(self, action, handles=None, downed=None):
        """Resolve one player line. ``handles``/``downed``: Kit's declared acts this turn
        (runtime/kit_acts.py), validated against the turn's offer and resolved as the bridge
        does at commit."""
        revision, state = self.runtime.load()
        result = self.adjudicator.resolve(action, revision, state)
        events = list(result.events)
        plan = {**({'handles': handles} if handles else {}), **({'downed': {'act': downed}} if downed else {})}
        if plan:
            acts = kit_acts.check(plan, {'acts': result.offers or {}})
            after = self.runtime.preview_state(revision, events)
            if hasattr(self.adjudicator, 'declared_acts'):
                declared = self.adjudicator.declared_acts(acts, action, revision, after)
            else:  # before the act family resolved more than handles
                declared = self.adjudicator.declared_handling(acts['handles'], action, revision, after)
            events += list(declared.events)
            result = declared.__class__(declared.kind, f'{declared.public_event}', events, declared.handoff,
                                        result.offers)
        self.runtime.commit(f't{revision}', revision, events)
        return result

    @property
    def state(self):
        return self.runtime.load()[1]


def kit_visible(packet):
    """The packet with dm_only removed: everything Kit or the player may see."""
    packet = copy.deepcopy(packet)
    packet.get('input', {}).get('private', {}).get('dm_context', {}).pop('dm_only', None)
    return json.dumps(packet).casefold()


class TriggerSchemaTests(unittest.TestCase):
    def test_the_fixture_mounts_and_the_trigger_compiles(self):
        source = kit_rooms.check_room(carcass())
        (trigger,) = kit_triggers.compile_triggers(source)
        self.assertEqual(trigger['on'], {'disturb': 'carcass'})
        self.assertEqual(trigger['actors'], ['centipede_a', 'centipede_b'])

    def test_bad_triggers_are_refused_at_mount_naming_the_problem(self):
        good = carcass()['triggers'][0]
        for bad, words in (({**good, 'on': {'disturb': 'nowhere'}}, 'unknown fact'),
                           ({**good, 'on': {'enter': 'attic'}}, 'unknown area'),
                           ({**good, 'on': {'sing': 'carcass'}}, 'on'),
                           ({**good, 'actors': ['ghost']}, 'unknown actor'),
                           ({**good, 'surprise': {'stealth': 'high'}}, 'surprise'),
                           ({**good, 'id': ''}, 'id')):
            with self.subTest(words=words):
                with self.assertRaises(kit_rooms.RoomMountError) as caught:
                    kit_rooms.check_room(carcass(triggers=[bad]))
                self.assertIn(words, str(caught.exception))

    def test_srd_giant_centipede_matches_the_srd(self):
        block = srd_creatures.stat_block({'srd': 'Giant Centipede'})
        self.assertEqual((block['ac'], block['hp'], block['initiative']), (13, 4, 2))
        (bite,) = block['attacks']
        self.assertEqual((bite['to_hit'], bite['damage'], bite['type']), (4, 4, 'piercing'))
        self.assertEqual(bite['save'], {'ability': 'con', 'dc': 11, 'damage': 10, 'type': 'poison',
                                        'half': False, 'at_zero': ['poisoned', 'paralyzed']})


class HiddenActorTests(unittest.TestCase):
    def test_hidden_actors_are_absent_from_every_kit_visible_field(self):
        room = Room(self)
        bridge = KitChatBridge(room.runtime, room.adjudicator)
        for index, action in enumerate(('I look around the hall.', 'Is anything alive in here?',
                                        '"Hello? Anyone down here?"')):
            packet = bridge.prepare(action, f'h{index}', one_pass=True)
            seen = kit_visible(packet)
            for word in HIDDEN_WORDS:
                self.assertNotIn(word, seen, f'{word} leaked on {action!r}')
            self.assertIn('centipede_a', json.dumps(packet['input']['private']['dm_context']['dm_only']))
            bridge.abandon(f'h{index}')
        self.assertNotIn('centipede', json.dumps(room.runtime.player_view()).casefold())

    def test_the_approach_view_does_not_show_them(self):
        room = Room(self, start='stair')
        bridge = KitChatBridge(room.runtime, room.adjudicator)
        packet = bridge.prepare('I look around.', 'a1', one_pass=True)
        for word in HIDDEN_WORDS:
            self.assertNotIn(word, kit_visible(packet))

    def test_a_hidden_actor_cannot_be_attacked_or_spoken_for(self):
        room = Room(self)
        revision, state = room.runtime.load()
        self.assertEqual(turn_speakers(room.runtime, {'events': []})['speakers'], ['Narrator', 'Kit'])
        try:
            result = room.adjudicator.resolve('I stab the banded centipede with my dagger.', revision, state)
        except PendingRuling:
            return
        self.assertNotIn('trigger_fired', [e['type'] for e in result.events])
        self.assertNotIn('combat_state', [e['type'] for e in result.events])

    def test_hidden_is_only_left_by_a_trigger(self):
        room = Room(self)
        revision, _ = room.runtime.load()
        with self.assertRaises(InvalidChange):
            room.runtime.commit('x', revision, [{'type': 'actor_status', 'actor': 'centipede_a',
                                                 'status': 'hidden', 'evidence': 'no'}])
        room.runtime.commit('y', revision, [{'type': 'trigger_fired', 'trigger': 'carcass_disturbed',
                                             'evidence': 'test'}])
        actor = room.state['actors']['centipede_a']
        self.assertEqual((actor['status'], actor['visible']), ('alive', True))
        revision, _ = room.runtime.load()
        with self.assertRaises(InvalidChange):
            room.runtime.commit('z', revision, [{'type': 'trigger_fired', 'trigger': 'carcass_disturbed',
                                                 'evidence': 'twice'}])


class MonsterInitiativeTests(unittest.TestCase):
    def test_disturbing_the_carcass_starts_the_fight_without_a_player_attack(self):
        for action, act in (('I roll the carcass over.', 'roll'), ('I search the carcass.', 'search'),
                            ('I prod the basilisk carcass with my staff.', 'push')):
            with self.subTest(action=action):
                room = Room(self)
                result = room.act(action, {'target': 'carcass', 'act': act})
                self.assertEqual(result.kind, 'combat_round')
                self.assertIn('Two giant centipedes boil out', result.public_event)
                self.assertTrue(result.public_event.endswith('Roll initiative.'))
                state = room.state
                self.assertEqual(state['combat']['status'], 'awaiting_initiative')
                self.assertEqual(state['combat']['started_by'], 'trigger:carcass_disturbed')
                self.assertEqual(set(state['combat']['hp']), {'centipede_a', 'centipede_b'})
                for key in ('centipede_a', 'centipede_b'):
                    self.assertEqual(state['actors'][key]['status'], 'alive')
                self.assertEqual(state['triggers_fired'], ['carcass_disturbed'])

    def test_the_words_alone_never_fire_it_they_offer_kit_the_call(self):
        """The design steer: the regex only hints; without Kit's declared handles nothing fires."""
        for action, hint in (('I roll the carcass over.', {'target': 'carcass', 'act': 'roll'}),
                             ('I search the carcass.', {'target': 'carcass', 'act': 'search'}),
                             ('I pry the claw open.', {'target': 'claw', 'act': 'pry'})):
            with self.subTest(action=action):
                room = Room(self)
                result = room.act(action)
                self.assertEqual(result.kind, 'feature_act')
                self.assertEqual(result.offers['handles']['hint'], hint)
                self.assertNotIn('trigger_fired', [e['type'] for e in result.events])
                self.assertEqual(room.state.get('triggers_fired') or [], [])
                self.assertNotIn('orb', room.state['known_facts'])

    def test_after_the_trigger_they_are_present_and_speak(self):
        room = Room(self)
        room.act('I roll the carcass over.', ROLL)
        speakers = turn_speakers(room.runtime, {'events': []})['speakers']
        self.assertIn('Banded centipede', speakers)
        self.assertIn('Banded centipede', json.dumps(room.runtime.player_view()))

    def test_other_acts_do_not_fire_it_and_it_fires_once(self):
        room = Room(self, roll=lambda: 2)  # the centipedes miss: no save owed
        result = room.act('I look around the hall.')
        self.assertNotIn('trigger_fired', [e['type'] for e in result.events])
        self.assertIsNone(room.state.get('combat'))
        room.act('I roll the carcass over.', ROLL)
        room.act('Initiative 20')
        room.act('I hit the banded centipede with my quarterstaff: 17 to hit, 6 bludgeoning damage.')
        result = room.act('I search the carcass.')
        self.assertNotIn('trigger_fired', [e['type'] for e in result.events])
        self.assertFalse((result.offers or {}).get('handles'), 'a spent trigger offers nothing to declare')
        with self.assertRaises(InvalidChange):
            kit_acts.check({'handles': {'target': 'carcass', 'act': 'search'}}, {'acts': result.offers or {}})

    def test_entering_an_area_can_spring_an_ambush(self):
        source = carcass()
        source['triggers'][0]['on'] = {'enter': 'hall'}
        room = Room(self, source=source, start='stair')
        revision, _ = room.runtime.load()
        room.runtime.commit('see', revision, [{'type': 'reveal_exit', 'exit': 'stair', 'evidence': 'seen'}])
        result = room.act('I walk down the stair.')
        self.assertIn('move', [e['type'] for e in result.events])
        self.assertIn('trigger_fired', [e['type'] for e in result.events])
        self.assertEqual(room.state['area'], 'hall')
        self.assertEqual(room.state['combat']['status'], 'awaiting_initiative')


class SurpriseTests(unittest.TestCase):
    def test_an_unaware_pc_is_surprised_and_loses_round_one(self):
        # Stealth d20 20 + 2 = 22 beats Nik's passive Perception 14: he does not notice them.
        room = Room(self, npc_roll=lambda: 20, roll=lambda: 2)
        room.act('I roll the carcass over.', ROLL)
        self.assertIn('pc', room.state['combat']['surprised'])
        result = room.act('Initiative 20')
        self.assertIn('surprised', result.public_event)
        combat = room.state['combat']
        self.assertEqual(combat['round'], 2, 'his round-one turn is lost; the centipedes still act')
        self.assertEqual(combat['order'][combat['next']], 'pc')
        self.assertTrue(result.public_event.endswith('Your turn.'))

    def test_a_pc_who_notices_any_of_them_is_not_surprised(self):
        # Stealth d20 1 + 2 = 3 against passive 14.
        room = Room(self, npc_roll=lambda: 1)
        room.act('I roll the carcass over.', ROLL)
        self.assertNotIn('pc', room.state['combat']['surprised'])
        result = room.act('Initiative 20')
        self.assertNotIn('surprised', result.public_event)
        self.assertEqual(room.state['combat']['round'], 1)

    def test_a_flat_dc_works_and_no_surprise_block_means_none(self):
        source = carcass()
        source['triggers'][0]['surprise'] = {'dc': 15}
        room = Room(self, source=source)
        room.act('I roll the carcass over.', ROLL)
        self.assertIn('pc', room.state['combat']['surprised'])
        source = carcass()
        del source['triggers'][0]['surprise']
        room = Room(self, source=source, npc_roll=lambda: 20)
        room.act('I roll the carcass over.', ROLL)
        self.assertEqual(room.state['combat']['surprised'], [])

    def test_the_ambushers_are_never_surprised(self):
        room = Room(self, npc_roll=lambda: 20)
        room.act('I roll the carcass over.', ROLL)
        self.assertNotIn('centipede_a', room.state['combat']['surprised'])


class SaveRiderTests(unittest.TestCase):
    def bitten(self):
        # Not surprised; the centipedes' d20 15 + 4 = 19 hits AC 14. Nik's init 1 puts them first.
        room = Room(self, npc_roll=lambda: 1, roll=lambda: 15)
        room.act('I roll the carcass over.', ROLL)
        result = room.act('Initiative 1')
        return room, result

    def test_a_bite_that_hits_asks_the_player_for_the_save(self):
        room, result = self.bitten()
        self.assertIn('Roll a Constitution saving throw.', result.public_event)
        self.assertNotIn('DC', result.public_event)
        self.assertNotIn('11', result.public_event)
        awaiting = room.state['combat']['awaiting']
        self.assertEqual((awaiting['kind'], awaiting['awaits'], awaiting['save']), ('roll_call', 'player_roll', 'con'))
        self.assertEqual(room.state['combat']['pc_damage'], 4, 'the bite itself: 4 piercing')
        self.assertNotIn('Your turn.', result.public_event)
        view = room.runtime.player_view()['fight']
        self.assertEqual(view['roll_needed'], 'Constitution saving throw')

    def test_a_made_save_takes_no_poison_and_the_round_goes_on(self):
        room, _ = self.bitten()
        result = room.act('Con save 14')
        combat = room.state['combat']
        self.assertEqual(combat['pc_damage'], 8, 'no half damage on a success (SRD); the second bite lands')
        self.assertEqual(combat['awaiting']['from'], 'centipede_b', 'the second centipede bites: a second save')
        self.assertNotIn('Your turn.', result.public_event)
        result = room.act('Con save 15')
        combat = room.state['combat']
        self.assertEqual(combat['pc_damage'], 8)
        self.assertIsNone(combat.get('awaiting'))
        self.assertTrue(result.public_event.endswith('Your turn.'))

    def test_a_failed_save_takes_the_poison(self):
        room, result = self.bitten()
        result = room.act('Constitution saving throw: 5')
        self.assertIn('10 poison', result.public_event)
        self.assertEqual(room.state['combat']['pc_damage'], 4 + 10 + 4)

    def test_the_avrae_save_format_and_a_bare_number_count(self):
        for answer in ('Nik makes a Constitution Save!\n1d20 (4) + 2 = `6`', '6'):
            with self.subTest(answer=answer):
                room, _ = self.bitten()
                room.act(answer)
                self.assertEqual(room.state['combat']['pc_damage'], 4 + 10 + 4)

    def test_anything_else_waits_for_the_save(self):
        room, _ = self.bitten()
        revision, state = room.runtime.load()
        with self.assertRaises(PendingRuling) as caught:
            room.adjudicator.resolve('I hit the banded centipede with my staff.', revision, state)
        self.assertIn('Constitution saving throw', str(caught.exception))

    def test_poison_that_drops_the_pc_leaves_him_stable_poisoned_and_paralyzed(self):
        room, _ = self.bitten()
        revision, _ = room.runtime.load()
        sheet = dict(room.state['player_sheet'], hp=12)
        room.runtime.set_player_sheet(sheet)
        result = room.act('Con save 3')
        self.assertIn('stable', result.public_event)
        self.assertEqual(room.state['pc_conditions'], ['unconscious', 'poisoned', 'paralyzed'])


class SaveRollParsingTests(unittest.TestCase):
    def test_abbreviated_saves_parse(self):
        for text, total in (('Con save 14', 14), ('con save: 9', 9), ('DEX saving throw 12', 12)):
            with self.subTest(text=text):
                (roll,) = kit_rolls.rolls(text)
                self.assertEqual(roll.total, total)
                self.assertTrue(roll.label.endswith('_save'))


def with_coffin():
    """The carcass room plus a second feature: a coffin whose lid (a part) and signet ring (a
    held item) wake the second centipede; the carcass wakes only the first."""
    source = carcass()
    source['facts']['coffin'] = {
        'area': 'hall', 'visible': True, 'text': 'A stone coffin rests against the far pillar, its lid askew.',
        'handling': {'nouns': ['coffin', 'sarcophagus'], 'parts': ['lid'], 'holds': 'signet',
                     'move': 'The coffin grinds an inch across the flagstones.',
                     'handle': 'Stone scrapes on stone as the lid shifts.',
                     'look': 'Dust and old linen fill the coffin.'}}
    source['facts']['signet'] = {'area': 'hall', 'visible': False,
                                 'text': 'A tarnished signet ring lies on the linen inside the coffin.',
                                 'handling': {'nouns': ['signet', 'ring'], 'look': 'A tarnished signet ring.'}}
    source['triggers'][0]['actors'] = ['centipede_a']
    source['triggers'].append({'id': 'coffin_disturbed', 'on': {'disturb': 'coffin'}, 'starts_combat': True,
                               'actors': ['centipede_b'], 'reveal': 'Something rust-red pours out of the coffin.'})
    return source


class DisturbByPartOrItemTests(unittest.TestCase):
    """Manipulating part of a feature, or taking an item from it, disturbs that feature (17a:
    'I pry the claw open', 'I take the orb from the claw')."""

    def fired(self, room):
        return room.state.get('triggers_fired') or []

    def test_prying_a_part_or_taking_the_held_item_fires_the_carcass_trigger(self):
        for action, handles in (('I pry the claw open.', {'target': 'claw', 'act': 'pry'}),
                                ("I pull the orb out of the basilisk's talon.", {'target': 'talon', 'act': 'pull'}),
                                ('I wrench the foreleg aside.', {'target': 'foreleg', 'act': 'pry'})):
            with self.subTest(action=action):
                room = Room(self)
                result = room.act(action, handles)
                self.assertEqual(self.fired(room), ['carcass_disturbed'])
                self.assertEqual(result.kind, 'combat_round')
                self.assertTrue(result.public_event.endswith('Roll initiative.'))

    def test_taking_the_item_shows_it(self):
        room = Room(self)
        result = room.act('I pry the claw open.', {'target': 'claw', 'act': 'pry'})
        self.assertIn('orb', room.state['known_facts'])
        self.assertIn({'type': 'reveal_fact', 'fact': 'orb'},
                      [{k: e[k] for k in ('type', 'fact')} for e in result.events if e['type'] == 'reveal_fact'])

    def test_another_feature_fires_its_own_trigger_only(self):
        for action, handles in (('I pry the lid off.', {'target': 'lid', 'act': 'pry'}),
                                ('I lift the lid of the sarcophagus.', {'target': 'coffin', 'act': 'lift'})):
            with self.subTest(action=action):
                room = Room(self, source=with_coffin())
                room.act(action, handles)
                self.assertEqual(self.fired(room), ['coffin_disturbed'])
                self.assertEqual(room.state['actors']['centipede_b']['status'], 'alive')
                self.assertEqual(room.state['actors']['centipede_a']['status'], 'hidden')

    def test_looking_at_a_part_disturbs_nothing(self):
        room = Room(self)
        result = room.act('I look at the claw.')
        self.assertEqual(self.fired(room), [])
        self.assertNotIn('trigger_fired', [e['type'] for e in result.events])

    def test_parts_must_be_words(self):
        source = carcass()
        source['facts']['carcass']['handling']['parts'] = 'claw'
        with self.assertRaises(kit_rooms.RoomMountError):
            kit_rooms.check_room(source)


if __name__ == '__main__':
    unittest.main()
